"""The multi-replica Kubernetes C2 descriptor, its assertions, and its record.

This is the second half of `V1-S3-006`. `core.py` certifies that a real model
answers one request through the release's API Service on a single-replica
release; this module certifies that **two or more ready API replicas each
received successful real requests through that Service**, and it refuses to say
so on any weaker evidence than a per-replica correlation.

Three things about it are worth reading before the code.

**The request set is sent from inside the cluster, and that is the whole point.**
`core.py` sends its one request through a `kubectl port-forward`, and the
procedure it publishes states the bound plainly: a forward is served by the API
server against **one selected endpoint**, so it never traverses the Service's
virtual IP. A forward therefore cannot distribute anything, and a multi-replica
claim built on one would be a claim about a client rather than about a Service.
So the request set is driven by a short-lived pod in the namespace, addressing
the API Service by name, one connection per request, and `kube-proxy` picks the
endpoint. What that pod is and how it is created belongs to
`scripts/environment/kubernetes-multi-replica-certification.sh`; nothing here
operates a cluster.

**The correlation mechanism is one this project already publishes, and no new
public surface is added for it.** Every `request.completed` record the InferOps
API writes carries `inferops.request.id` and `k8s.pod.name` -- the catalog places
the pod name on records and deliberately keeps it off every metric, because it is
unbounded as a label. So the request identifiers this workflow sends are joined
to the pod names the API itself logged, and the join is what proves distribution.
No response header, body member, or endpoint exposes pod identity: a test that
made a replica's name part of the API's contract would have changed the product
to observe it.

**Desired replicas prove nothing and are never treated as though they did.**
`spec.replicas: 2` is a request to a controller. What this module requires is
that each expected replica reported itself ready, that the requests actually
succeeded, and that the successful ones are distributed across at least the
declared number of distinct pods. A run in which every request happened to land
on one ready replica is a **failure** with an honest message, not a pass with a
footnote -- and the procedure states the arithmetic that makes that outcome
unlikely rather than pretending it is impossible.

What this does **not** establish is stated in the descriptor's own `limitations`
member and copied into every record: one node, one runtime replica, no
autoscaling, no routing policy, no load, and no production high availability.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from inferops.adapters.llama_cpp import LLAMA_SERVER_ADAPTER_KIND
from inferops.api.surface import CHAT_COMPLETIONS_PATH, EXTENSION_ADAPTER_KIND
from inferops.telemetry import names
from tools.model_acquisition import load_manifest
from tools.runtime_packaging import load_runtime_package

from .core import (
    DIGEST_MARKER,
    EXPECTED_CERTIFICATION_REF,
    EXPECTED_CHART_REF,
    EXPECTED_EVIDENCE_CLASS,
    EXPECTED_EVIDENCE_DIRECTORY,
    EXPECTED_EVIDENCE_LABEL,
    EXPECTED_LANE,
    EXPECTED_LEVEL,
    EXPECTED_SCHEMA,
    NAMESPACE_PREFIX,
    Certification,
    CertificationError,
    CertificationFailed,
    EvidenceUnwritable,
    ModelCacheExpectation,
    ModelCacheFacts,
    WorkloadFacts,
    _boolean,
    _integer,
    _model_cache,
    _object,
    _require_keys,
    _string,
    _workload,
    ensure_evidence_paths_safe,
    load_certification,
)

# Re-exported deliberately rather than imported for use alone: the command line
# reads it at call time so that a caller can point the whole workflow at another
# tree, and every reader below defaults to it.
from .core import REPO_ROOT as REPO_ROOT

MULTI_REPLICA_CERTIFICATION_PATH = (
    REPO_ROOT / "deploy/serving/certification/k8s-multi-replica-inference.v1.json"
)

EXPECTED_ID = "inferops-c2-kubernetes-multi-replica-inference"
EXPECTED_PROCEDURE_REF = "docs/serving/kubernetes-multi-replica-certification.md"
EXPECTED_SINGLE_REPLICA_REF = "deploy/serving/certification/k8s-real-inference.v1.json"
EXPECTED_CAPACITY_FILE = (
    ".artifacts/kubernetes-multi-replica-certification/capacity-facts.json"
)
EXPECTED_FACTS_FILE = (
    ".artifacts/kubernetes-multi-replica-certification/cluster-facts.json"
)
EXPECTED_OBSERVATIONS_FILE = (
    ".artifacts/kubernetes-multi-replica-certification/observations.json"
)
EXPECTED_CLEANUP_FILE = (
    ".artifacts/kubernetes-multi-replica-certification/cleanup-facts.json"
)

#: The one mechanism this certification accepts. It names the surface the
#: evidence is read from, so a descriptor that quietly changed to a weaker one --
#: a response header, a body member, an inferred count -- is refused at load
#: rather than at review.
EXPECTED_MECHANISM = "structured-log-correlation"

#: The smallest multi-replica certification there is. A descriptor asking for one
#: replica is not a smaller version of this workflow; it is `core.py`, and
#: accepting it here would be the silent single-replica fallback the story
#: forbids.
MINIMUM_REPLICAS = 2

#: The stages a run passes through, in order, extending the vocabulary `core.py`
#: publishes with the two this workflow adds. `capacity` is first because it is
#: the one that must refuse **before** anything is installed.
STAGE_LOAD = "load"
STAGE_CAPACITY = "capacity"
STAGE_PREREQUISITES = "prerequisites"
STAGE_RELEASE = "release"
STAGE_READINESS = "readiness"
STAGE_DISTRIBUTION = "distribution"
STAGE_CORRELATION = "correlation"
STAGE_CLEANUP = "cleanup"
STAGE_EVIDENCE = "evidence"

STAGES: tuple[str, ...] = (
    STAGE_LOAD,
    STAGE_CAPACITY,
    STAGE_PREREQUISITES,
    STAGE_RELEASE,
    STAGE_READINESS,
    STAGE_DISTRIBUTION,
    STAGE_CORRELATION,
    STAGE_CLEANUP,
    STAGE_EVIDENCE,
)


class CapacityUnmet(CertificationError):
    """The host or the cluster cannot hold the requested replicas.

    A distinct type because it is the one refusal that has to happen with the
    namespace still empty. Downgrading the replica count to fit would produce a
    record that certifies something nobody asked for, and installing anyway
    would produce a pod stuck `Pending` and a rollout that fails for a reason
    the record would describe as readiness.
    """

    stage = STAGE_CAPACITY


# -- the descriptor ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MultiReplicaRelease:
    """The one release, with the replica counts this profile requests."""

    name: str
    namespace: str
    profile: str
    api_service_name: str
    api_service_port: int
    api_deployment_name: str
    runtime_service_name: str
    runtime_deployment_name: str
    config_map_name: str
    instance_selector: str
    api_component: str
    runtime_component: str
    api_replicas: int
    runtime_replicas: int

    def desired(self, deployment: str) -> int:
        """How many replicas the named Deployment is expected to run."""
        if deployment == self.api_deployment_name:
            return self.api_replicas
        return self.runtime_replicas


@dataclass(frozen=True, slots=True)
class CapacityRequirement:
    """What this profile needs before a single object is created.

    Two figures rather than one, because they answer different questions and a
    host can satisfy either alone. `requested_*` is what the **scheduler** adds
    up: a pod whose requests do not fit in what is left of a node stays
    `Pending` forever. `peak_memory_bytes` is the sum of the memory **limits**,
    which is what the node has to survive if every container uses everything it
    is allowed -- and the container that would is the one loading a 1.83 GB
    model.
    """

    minimum_engine_memory_bytes: int
    minimum_engine_cpus: int
    requested_cpu_millis: int
    requested_memory_bytes: int
    peak_memory_bytes: int
    headroom_cpu_millis: int
    headroom_memory_bytes: int


@dataclass(frozen=True, slots=True)
class DistributionPlan:
    """The bounded request set, and what its answers have to establish."""

    mechanism: str
    driver_component: str
    driver_name: str
    driver_image: str
    path: str
    prompt: str
    request_count: int
    request_id_prefix: str
    correlation_id: str
    minimum_distinct_replicas: int
    request_timeout_ms: int

    @property
    def request_ids(self) -> tuple[str, ...]:
        """Every identifier this run will send, derived rather than listed.

        Derived so that the driver, the assertions, and the record cannot
        disagree about which requests were meant to exist: a missing answer is
        then a missing member of a known set rather than a shorter list nobody
        compared against anything.
        """
        return tuple(
            f"{self.request_id_prefix}-{index:03d}"
            for index in range(1, self.request_count + 1)
        )


@dataclass(frozen=True, slots=True)
class MultiReplicaBudgets:
    """Every bound this workflow applies, and where each one comes from.

    All but one are `core.py`'s, unchanged and compared against it at load: the
    two workflows install the same chart, and two different opinions about how
    long a model may take to load would be two opinions about the same chart.
    `distribution_ms` is this workflow's own, and it bounds the whole request
    set rather than one request.
    """

    install_ms: int
    runtime_startup_ms: int
    runtime_rollout_ms: int
    api_startup_ms: int
    api_rollout_ms: int
    release_test_ms: int
    distribution_ms: int
    uninstall_ms: int


@dataclass(frozen=True, slots=True)
class MultiReplicaCertification:
    """The committed multi-replica descriptor after every field is validated."""

    schema_version: str
    certification_id: str
    certification_level: str
    evidence_class: str
    evidence_label: str
    lane: str
    chart_ref: str
    certification_ref: str
    procedure_ref: str
    single_replica_certification_ref: str
    cluster_name: str
    cluster_context: str
    node_image_digest: str
    release: MultiReplicaRelease
    model_cache: ModelCacheExpectation
    capacity: CapacityRequirement
    budgets: MultiReplicaBudgets
    distribution: DistributionPlan
    requires_terraform_prerequisites: bool
    requires_target_cluster_assertion: bool
    requires_pinned_runtime_image: bool
    requires_pinned_api_image: bool
    requires_verified_model_cache: bool
    requires_capacity_preflight: bool
    required_adapter_kind: str
    prohibited_identity_substring: str
    require_every_replica_ready: bool
    require_every_request_successful: bool
    require_usage_counts: bool
    require_per_replica_correlation: bool
    require_pinned_model_revision: bool
    require_digest_pinned_images: bool
    require_release_test: bool
    require_pinned_node_image: bool
    evidence_directory: Path
    result_file: str
    diagnostics_file: str
    capacity_file: str
    facts_file: str
    observations_file: str
    cleanup_file: str
    retain_generated_text: bool
    uninstalls_release: bool
    removes_request_driver: bool
    removes_prerequisites: bool
    removes_cluster: bool
    limitations: tuple[str, ...]

    def artifact_path(self, member: str, repo_root: Path = REPO_ROOT) -> Path:
        """Where one collected artifact must be, rather than wherever it is.

        The location is derived from the descriptor for the same reason
        `core.py` derives its own: the cluster half of the record is copied out
        of these files, so a path accepted as an argument would let a run reach
        a real Service and describe an environment read from somewhere else.
        """
        return repo_root.resolve() / member


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise CertificationError(f"certification field '{field}' names nothing")
    return tuple(
        _string(entry, f"{field}[{position}]") for position, entry in enumerate(value)
    )


def _read_release(release: Mapping[str, Any]) -> MultiReplicaRelease:
    return MultiReplicaRelease(
        name=_string(release.get("name"), "release.name"),
        namespace=_string(release.get("namespace"), "release.namespace"),
        profile=_string(release.get("profile"), "release.profile"),
        api_service_name=_string(
            release.get("apiServiceName"), "release.apiServiceName"
        ),
        api_service_port=_integer(
            release.get("apiServicePort"), "release.apiServicePort"
        ),
        api_deployment_name=_string(
            release.get("apiDeploymentName"), "release.apiDeploymentName"
        ),
        runtime_service_name=_string(
            release.get("runtimeServiceName"), "release.runtimeServiceName"
        ),
        runtime_deployment_name=_string(
            release.get("runtimeDeploymentName"), "release.runtimeDeploymentName"
        ),
        config_map_name=_string(release.get("configMapName"), "release.configMapName"),
        instance_selector=_string(
            release.get("instanceSelector"), "release.instanceSelector"
        ),
        api_component=_string(release.get("apiComponent"), "release.apiComponent"),
        runtime_component=_string(
            release.get("runtimeComponent"), "release.runtimeComponent"
        ),
        api_replicas=_integer(release.get("apiReplicas"), "release.apiReplicas"),
        runtime_replicas=_integer(
            release.get("runtimeReplicas"), "release.runtimeReplicas"
        ),
    )


def _read_capacity(capacity: Mapping[str, Any]) -> CapacityRequirement:
    return CapacityRequirement(
        minimum_engine_memory_bytes=_integer(
            capacity.get("minimumEngineMemoryBytes"),
            "capacity.minimumEngineMemoryBytes",
        ),
        minimum_engine_cpus=_integer(
            capacity.get("minimumEngineCpus"), "capacity.minimumEngineCpus"
        ),
        requested_cpu_millis=_integer(
            capacity.get("requestedCpuMillis"), "capacity.requestedCpuMillis"
        ),
        requested_memory_bytes=_integer(
            capacity.get("requestedMemoryBytes"), "capacity.requestedMemoryBytes"
        ),
        peak_memory_bytes=_integer(
            capacity.get("peakMemoryBytes"), "capacity.peakMemoryBytes"
        ),
        headroom_cpu_millis=_integer(
            capacity.get("headroomCpuMillis"), "capacity.headroomCpuMillis", minimum=0
        ),
        headroom_memory_bytes=_integer(
            capacity.get("headroomMemoryBytes"),
            "capacity.headroomMemoryBytes",
            minimum=0,
        ),
    )


def _read_distribution(plan: Mapping[str, Any]) -> DistributionPlan:
    return DistributionPlan(
        mechanism=_string(plan.get("mechanism"), "distribution.mechanism"),
        driver_component=_string(
            plan.get("driverComponent"), "distribution.driverComponent"
        ),
        driver_name=_string(plan.get("driverName"), "distribution.driverName"),
        driver_image=_string(plan.get("driverImage"), "distribution.driverImage"),
        path=_string(plan.get("path"), "distribution.path"),
        prompt=_string(plan.get("prompt"), "distribution.prompt"),
        request_count=_integer(
            plan.get("requestCount"), "distribution.requestCount", minimum=2
        ),
        request_id_prefix=_string(
            plan.get("requestIdPrefix"), "distribution.requestIdPrefix"
        ),
        correlation_id=_string(plan.get("correlationId"), "distribution.correlationId"),
        minimum_distinct_replicas=_integer(
            plan.get("minimumDistinctReplicas"),
            "distribution.minimumDistinctReplicas",
            minimum=MINIMUM_REPLICAS,
        ),
        request_timeout_ms=_integer(
            plan.get("requestTimeoutMs"), "distribution.requestTimeoutMs"
        ),
    )


def _read_budgets(readiness: Mapping[str, Any]) -> MultiReplicaBudgets:
    return MultiReplicaBudgets(
        install_ms=_integer(
            readiness.get("installBudgetMs"), "readiness.installBudgetMs"
        ),
        runtime_startup_ms=_integer(
            readiness.get("runtimeStartupBudgetMs"), "readiness.runtimeStartupBudgetMs"
        ),
        runtime_rollout_ms=_integer(
            readiness.get("runtimeRolloutBudgetMs"), "readiness.runtimeRolloutBudgetMs"
        ),
        api_startup_ms=_integer(
            readiness.get("apiStartupBudgetMs"), "readiness.apiStartupBudgetMs"
        ),
        api_rollout_ms=_integer(
            readiness.get("apiRolloutBudgetMs"), "readiness.apiRolloutBudgetMs"
        ),
        release_test_ms=_integer(
            readiness.get("releaseTestBudgetMs"), "readiness.releaseTestBudgetMs"
        ),
        distribution_ms=_integer(
            readiness.get("distributionBudgetMs"), "readiness.distributionBudgetMs"
        ),
        uninstall_ms=_integer(
            readiness.get("uninstallBudgetMs"), "readiness.uninstallBudgetMs"
        ),
    )


def load_multi_replica_certification(
    path: Path = MULTI_REPLICA_CERTIFICATION_PATH,
) -> MultiReplicaCertification:
    """Load and cross-check the descriptor without performing any real I/O."""
    try:
        record = _object(json.loads(path.read_text(encoding="utf-8")), "root")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CertificationError(
            "the multi-replica certification descriptor is unreadable"
        ) from error

    cluster = _object(record.get("cluster"), "cluster")
    release = _object(record.get("release"), "release")
    prerequisites = _object(record.get("prerequisites"), "prerequisites")
    model_cache = _object(record.get("modelCache"), "modelCache")
    capacity = _object(record.get("capacity"), "capacity")
    readiness = _object(record.get("readiness"), "readiness")
    distribution = _object(record.get("distribution"), "distribution")
    assertions = _object(record.get("assertions"), "assertions")
    evidence = _object(record.get("evidence"), "evidence")
    cleanup = _object(record.get("cleanup"), "cleanup")
    _require_keys(
        record,
        "root",
        {
            "schemaVersion",
            "certificationId",
            "certificationLevel",
            "evidenceClass",
            "evidenceLabel",
            "lane",
            "chartRef",
            "certificationRef",
            "procedureRef",
            "singleReplicaCertificationRef",
            "cluster",
            "release",
            "prerequisites",
            "modelCache",
            "capacity",
            "readiness",
            "distribution",
            "assertions",
            "evidence",
            "cleanup",
            "limitations",
        },
    )
    _require_keys(cluster, "cluster", {"name", "context", "nodeImageDigest"})
    _require_keys(
        release,
        "release",
        {
            "name",
            "namespace",
            "profile",
            "apiServiceName",
            "apiServicePort",
            "apiDeploymentName",
            "runtimeServiceName",
            "runtimeDeploymentName",
            "configMapName",
            "instanceSelector",
            "apiComponent",
            "runtimeComponent",
            "apiReplicas",
            "runtimeReplicas",
        },
    )
    _require_keys(
        prerequisites,
        "prerequisites",
        {
            "requiresTerraformPrerequisites",
            "requiresTargetClusterAssertion",
            "requiresPinnedRuntimeImage",
            "requiresPinnedApiImage",
            "requiresVerifiedModelCache",
            "requiresCapacityPreflight",
        },
    )
    _require_keys(
        model_cache,
        "modelCache",
        {
            "claimName",
            "verificationInitContainer",
            "requireReadOnlyMount",
            "requireArtifactHashCompared",
        },
    )
    _require_keys(
        capacity,
        "capacity",
        {
            "minimumEngineMemoryBytes",
            "minimumEngineCpus",
            "requestedCpuMillis",
            "requestedMemoryBytes",
            "peakMemoryBytes",
            "headroomCpuMillis",
            "headroomMemoryBytes",
        },
    )
    _require_keys(
        readiness,
        "readiness",
        {
            "installBudgetMs",
            "runtimeStartupBudgetMs",
            "runtimeRolloutBudgetMs",
            "apiStartupBudgetMs",
            "apiRolloutBudgetMs",
            "releaseTestBudgetMs",
            "distributionBudgetMs",
            "uninstallBudgetMs",
        },
    )
    _require_keys(
        distribution,
        "distribution",
        {
            "mechanism",
            "driverComponent",
            "driverName",
            "driverImage",
            "path",
            "prompt",
            "requestCount",
            "requestIdPrefix",
            "correlationId",
            "minimumDistinctReplicas",
            "requestTimeoutMs",
        },
    )
    _require_keys(
        assertions,
        "assertions",
        {
            "requiredAdapterKind",
            "prohibitedIdentitySubstring",
            "requireEveryReplicaReady",
            "requireEveryRequestSuccessful",
            "requireUsageCounts",
            "requirePerReplicaCorrelation",
            "requirePinnedModelRevision",
            "requireDigestPinnedImages",
            "requireReleaseTest",
            "requirePinnedNodeImage",
        },
    )
    _require_keys(
        evidence,
        "evidence",
        {
            "directory",
            "resultFile",
            "diagnosticsFile",
            "capacityFile",
            "factsFile",
            "observationsFile",
            "cleanupFile",
            "retainGeneratedText",
        },
    )
    _require_keys(
        cleanup,
        "cleanup",
        {
            "uninstallsRelease",
            "removesRequestDriver",
            "removesPrerequisites",
            "removesCluster",
        },
    )

    certification = MultiReplicaCertification(
        schema_version=_string(record.get("schemaVersion"), "schemaVersion"),
        certification_id=_string(record.get("certificationId"), "certificationId"),
        certification_level=_string(
            record.get("certificationLevel"), "certificationLevel"
        ),
        evidence_class=_string(record.get("evidenceClass"), "evidenceClass"),
        evidence_label=_string(record.get("evidenceLabel"), "evidenceLabel"),
        lane=_string(record.get("lane"), "lane"),
        chart_ref=_string(record.get("chartRef"), "chartRef"),
        certification_ref=_string(record.get("certificationRef"), "certificationRef"),
        procedure_ref=_string(record.get("procedureRef"), "procedureRef"),
        single_replica_certification_ref=_string(
            record.get("singleReplicaCertificationRef"),
            "singleReplicaCertificationRef",
        ),
        cluster_name=_string(cluster.get("name"), "cluster.name"),
        cluster_context=_string(cluster.get("context"), "cluster.context"),
        node_image_digest=_string(
            cluster.get("nodeImageDigest"), "cluster.nodeImageDigest"
        ),
        release=_read_release(release),
        model_cache=ModelCacheExpectation(
            claim_name=_string(model_cache.get("claimName"), "modelCache.claimName"),
            verification_init_container=_string(
                model_cache.get("verificationInitContainer"),
                "modelCache.verificationInitContainer",
            ),
            require_read_only_mount=_boolean(
                model_cache.get("requireReadOnlyMount"),
                "modelCache.requireReadOnlyMount",
            ),
            require_artifact_hash_compared=_boolean(
                model_cache.get("requireArtifactHashCompared"),
                "modelCache.requireArtifactHashCompared",
            ),
        ),
        capacity=_read_capacity(capacity),
        budgets=_read_budgets(readiness),
        distribution=_read_distribution(distribution),
        requires_terraform_prerequisites=_boolean(
            prerequisites.get("requiresTerraformPrerequisites"),
            "prerequisites.requiresTerraformPrerequisites",
        ),
        requires_target_cluster_assertion=_boolean(
            prerequisites.get("requiresTargetClusterAssertion"),
            "prerequisites.requiresTargetClusterAssertion",
        ),
        requires_pinned_runtime_image=_boolean(
            prerequisites.get("requiresPinnedRuntimeImage"),
            "prerequisites.requiresPinnedRuntimeImage",
        ),
        requires_pinned_api_image=_boolean(
            prerequisites.get("requiresPinnedApiImage"),
            "prerequisites.requiresPinnedApiImage",
        ),
        requires_verified_model_cache=_boolean(
            prerequisites.get("requiresVerifiedModelCache"),
            "prerequisites.requiresVerifiedModelCache",
        ),
        requires_capacity_preflight=_boolean(
            prerequisites.get("requiresCapacityPreflight"),
            "prerequisites.requiresCapacityPreflight",
        ),
        required_adapter_kind=_string(
            assertions.get("requiredAdapterKind"), "assertions.requiredAdapterKind"
        ),
        prohibited_identity_substring=_string(
            assertions.get("prohibitedIdentitySubstring"),
            "assertions.prohibitedIdentitySubstring",
        ),
        require_every_replica_ready=_boolean(
            assertions.get("requireEveryReplicaReady"),
            "assertions.requireEveryReplicaReady",
        ),
        require_every_request_successful=_boolean(
            assertions.get("requireEveryRequestSuccessful"),
            "assertions.requireEveryRequestSuccessful",
        ),
        require_usage_counts=_boolean(
            assertions.get("requireUsageCounts"), "assertions.requireUsageCounts"
        ),
        require_per_replica_correlation=_boolean(
            assertions.get("requirePerReplicaCorrelation"),
            "assertions.requirePerReplicaCorrelation",
        ),
        require_pinned_model_revision=_boolean(
            assertions.get("requirePinnedModelRevision"),
            "assertions.requirePinnedModelRevision",
        ),
        require_digest_pinned_images=_boolean(
            assertions.get("requireDigestPinnedImages"),
            "assertions.requireDigestPinnedImages",
        ),
        require_release_test=_boolean(
            assertions.get("requireReleaseTest"), "assertions.requireReleaseTest"
        ),
        require_pinned_node_image=_boolean(
            assertions.get("requirePinnedNodeImage"),
            "assertions.requirePinnedNodeImage",
        ),
        evidence_directory=Path(
            _string(evidence.get("directory"), "evidence.directory")
        ),
        result_file=_string(evidence.get("resultFile"), "evidence.resultFile"),
        diagnostics_file=_string(
            evidence.get("diagnosticsFile"), "evidence.diagnosticsFile"
        ),
        capacity_file=_string(evidence.get("capacityFile"), "evidence.capacityFile"),
        facts_file=_string(evidence.get("factsFile"), "evidence.factsFile"),
        observations_file=_string(
            evidence.get("observationsFile"), "evidence.observationsFile"
        ),
        cleanup_file=_string(evidence.get("cleanupFile"), "evidence.cleanupFile"),
        retain_generated_text=_boolean(
            evidence.get("retainGeneratedText"), "evidence.retainGeneratedText"
        ),
        uninstalls_release=_boolean(
            cleanup.get("uninstallsRelease"), "cleanup.uninstallsRelease"
        ),
        removes_request_driver=_boolean(
            cleanup.get("removesRequestDriver"), "cleanup.removesRequestDriver"
        ),
        removes_prerequisites=_boolean(
            cleanup.get("removesPrerequisites"), "cleanup.removesPrerequisites"
        ),
        removes_cluster=_boolean(
            cleanup.get("removesCluster"), "cleanup.removesCluster"
        ),
        limitations=_strings(record.get("limitations"), "limitations"),
    )
    _validate(certification, load_certification())
    return certification


def _validate_identity(certification: MultiReplicaCertification) -> None:
    if (
        certification.schema_version != EXPECTED_SCHEMA
        or certification.certification_id != EXPECTED_ID
        or certification.certification_level != EXPECTED_LEVEL
        or certification.evidence_class != EXPECTED_EVIDENCE_CLASS
        or certification.evidence_label != EXPECTED_EVIDENCE_LABEL
        or certification.lane != EXPECTED_LANE
        or certification.chart_ref != EXPECTED_CHART_REF
        or certification.certification_ref != EXPECTED_CERTIFICATION_REF
        or certification.procedure_ref != EXPECTED_PROCEDURE_REF
        or certification.single_replica_certification_ref != EXPECTED_SINGLE_REPLICA_REF
    ):
        raise CertificationError("the certification identity is unsupported")


def _validate_against_single_replica(
    certification: MultiReplicaCertification, single: Certification
) -> None:
    """Hold every shared target and budget to the descriptor that already fixed it.

    Both workflows install one chart into one namespace on one cluster. Two
    descriptors that disagreed about which release that is, or about how long a
    model may take to load, would be two answers to one question -- and the one
    a reader trusted would be whichever file they opened.
    """
    release = certification.release
    budgets = certification.budgets
    if (
        certification.cluster_name != single.cluster.name
        or certification.cluster_context != single.cluster.context
        or certification.node_image_digest != single.cluster.node_image_digest
    ):
        raise CertificationError(
            "the multi-replica descriptor names a cluster the single-replica "
            "certification does not"
        )
    if (
        release.name != single.release.name
        or release.namespace != single.release.namespace
        or release.profile != single.release.profile
        or release.api_service_name != single.release.api_service_name
        or release.api_service_port != single.release.api_service_port
        or release.api_deployment_name != single.release.api_deployment_name
        or release.runtime_service_name != single.release.runtime_service_name
        or release.runtime_deployment_name != single.release.runtime_deployment_name
        or release.config_map_name != single.release.config_map_name
        or release.instance_selector != single.release.instance_selector
        or release.api_component != single.release.api_component
        or release.runtime_component != single.release.runtime_component
    ):
        raise CertificationError(
            "the multi-replica descriptor names a release the single-replica "
            "certification does not"
        )
    if certification.model_cache != single.model_cache:
        raise CertificationError(
            "the two certifications disagree about how the model cache is read"
        )
    if (
        budgets.install_ms != single.budgets.install_ms
        or budgets.runtime_startup_ms != single.budgets.runtime_startup_ms
        or budgets.runtime_rollout_ms != single.budgets.runtime_rollout_ms
        or budgets.api_startup_ms != single.budgets.api_startup_ms
        or budgets.api_rollout_ms != single.budgets.api_rollout_ms
        or budgets.release_test_ms != single.budgets.release_test_ms
        or budgets.uninstall_ms != single.budgets.uninstall_ms
    ):
        raise CertificationError(
            "the two certifications disagree about a budget for the same chart"
        )
    if (
        certification.required_adapter_kind != single.required_adapter_kind
        or certification.prohibited_identity_substring
        != single.prohibited_identity_substring
    ):
        raise CertificationError(
            "the two certifications disagree about what the real path is"
        )
    if certification.distribution.request_timeout_ms != single.request_timeout_ms:
        raise CertificationError(
            "the two certifications disagree about the per-request budget"
        )


def _validate(certification: MultiReplicaCertification, single: Certification) -> None:
    """Refuse a descriptor that disagrees with any record already deciding it."""
    package = load_runtime_package()
    release = certification.release
    capacity = certification.capacity
    plan = certification.distribution
    budgets = certification.budgets
    _validate_identity(certification)
    _validate_against_single_replica(certification, single)
    if not (
        certification.requires_terraform_prerequisites
        and certification.requires_target_cluster_assertion
        and certification.requires_pinned_runtime_image
        and certification.requires_pinned_api_image
        and certification.requires_verified_model_cache
        and certification.requires_capacity_preflight
    ):
        raise CertificationError(
            "a multi-replica certification run may not waive a prerequisite"
        )
    if not release.namespace.startswith(NAMESPACE_PREFIX):
        raise CertificationError(
            "the release namespace must carry the 'inferops-' prefix (ADR 0001 D5)"
        )
    if (
        release.profile != "real"
        or certification.required_adapter_kind != LLAMA_SERVER_ADAPTER_KIND
    ):
        raise CertificationError(
            "a multi-replica certification run may certify only the real path"
        )
    if release.api_replicas < MINIMUM_REPLICAS:
        # The refusal this descriptor exists for. A profile asking for one
        # replica is not a smaller multi-replica certification; it is the
        # single-replica one, and accepting it here would let this workflow
        # write a multi-replica record about a release that never had two.
        raise CertificationError(
            f"a multi-replica certification requests at least {MINIMUM_REPLICAS} "
            f"API replicas and this descriptor requests {release.api_replicas}"
        )
    if plan.minimum_distinct_replicas > release.api_replicas:
        raise CertificationError(
            "the descriptor requires distribution across more replicas than it requests"
        )
    if plan.request_count < plan.minimum_distinct_replicas:
        raise CertificationError(
            "the descriptor sends fewer requests than the replicas it must reach"
        )
    if plan.mechanism != EXPECTED_MECHANISM:
        raise CertificationError(
            "the correlation mechanism is not the one this certification accepts"
        )
    if plan.path != CHAT_COMPLETIONS_PATH:
        raise CertificationError("the certification request path is not a served route")
    if DIGEST_MARKER not in plan.driver_image:
        raise CertificationError("the request driver image must be named by digest")
    if any(character in plan.prompt for character in "\r\n"):
        raise CertificationError("the certification prompt must be one line")
    if not certification.node_image_digest.startswith("sha256:"):
        raise CertificationError("the pinned node image must be named by digest")
    if budgets.runtime_startup_ms < package.startup_budget_ms:
        raise CertificationError(
            "the runtime startup budget is below the adapter's own startup budget"
        )
    if (
        budgets.runtime_rollout_ms < budgets.runtime_startup_ms
        or budgets.api_rollout_ms < budgets.api_startup_ms
    ):
        raise CertificationError(
            "a rollout budget is below the startup budget it has to contain"
        )
    if budgets.distribution_ms < plan.request_count * plan.request_timeout_ms:
        # Every request may take its whole budget, and they are sent one after
        # another. A distribution budget under the sum would fail a slow but
        # correct run in the middle of the request set.
        raise CertificationError(
            "the distribution budget cannot contain the request set it bounds"
        )
    if not (
        certification.require_every_replica_ready
        and certification.require_every_request_successful
        and certification.require_usage_counts
        and certification.require_per_replica_correlation
        and certification.require_pinned_model_revision
        and certification.require_digest_pinned_images
        and certification.require_release_test
        and certification.require_pinned_node_image
    ):
        raise CertificationError("a certification run may not waive a real assertion")
    if not (
        certification.model_cache.require_read_only_mount
        and certification.model_cache.require_artifact_hash_compared
    ):
        raise CertificationError(
            "a certification run may not waive a model cache assertion"
        )
    if capacity.peak_memory_bytes < capacity.requested_memory_bytes:
        raise CertificationError(
            "the declared peak memory is below the memory the same pods request"
        )
    if (
        certification.evidence_directory != EXPECTED_EVIDENCE_DIRECTORY
        or certification.capacity_file != EXPECTED_CAPACITY_FILE
        or certification.facts_file != EXPECTED_FACTS_FILE
        or certification.observations_file != EXPECTED_OBSERVATIONS_FILE
        or certification.cleanup_file != EXPECTED_CLEANUP_FILE
        or certification.retain_generated_text
        or Path(certification.result_file).name != certification.result_file
        or Path(certification.diagnostics_file).name != certification.diagnostics_file
        or certification.result_file == certification.diagnostics_file
        or certification.result_file == single.result_file
        or certification.diagnostics_file == single.diagnostics_file
    ):
        # The last two comparisons are the ones a reader might not expect. Both
        # workflows write into the same ignored directory, and a shared file
        # name would mean one run silently replacing the other's record.
        raise CertificationError("the certification evidence location is unsafe")
    if not (certification.uninstalls_release and certification.removes_request_driver):
        raise CertificationError(
            "a certification run must remove the release and the request driver "
            "it created"
        )
    if certification.removes_prerequisites or certification.removes_cluster:
        raise CertificationError(
            "a certification run may remove neither the prerequisites nor the cluster"
        )


# -- reading what the operating script collected -----------------------------


class _Facts:
    """A reader over one collected document, refusing at a named stage.

    `core.py` has readers of the same shape fixed to the readiness stage, which
    is right there and wrong here: a malformed capacity document has to refuse
    before anything is installed, and a diagnostics record naming `readiness`
    for it would send a reader to the wrong place.
    """

    def __init__(self, stage: str) -> None:
        self.stage = stage

    def fail(self, message: str) -> CertificationFailed:
        return CertificationFailed(message, self.stage)

    def object(self, value: Any, field: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise self.fail(f"the collected member '{field}' is not an object")
        return cast(dict[str, Any], value)

    def string(self, value: Any, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise self.fail(f"the collected member '{field}' is not a non-empty string")
        return value

    def integer(self, value: Any, field: str, *, minimum: int = 0) -> int:
        if isinstance(value, bool):
            raise self.fail(f"the collected member '{field}' is a boolean")
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            value = int(value.strip())
        if not isinstance(value, int) or value < minimum:
            raise self.fail(
                f"the collected member '{field}' is not an integer of at least "
                f"{minimum}"
            )
        return value

    def boolean(self, value: Any, field: str) -> bool:
        if not isinstance(value, bool):
            raise self.fail(f"the collected member '{field}' is not a boolean")
        return value

    def entries(self, value: Any, field: str) -> list[Any]:
        if not isinstance(value, list) or not value:
            raise self.fail(f"the collected member '{field}' names nothing")
        return value

    def document(self, path: Path, description: str) -> dict[str, Any]:
        try:
            return self.object(json.loads(path.read_text(encoding="utf-8")), "root")
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise self.fail(f"the collected {description} are unreadable") from error


@dataclass(frozen=True, slots=True)
class CapacityFacts:
    """What the host and the cluster had before anything was installed."""

    engine_cpus: int
    engine_memory_bytes: int
    node_count: int
    allocatable_cpu_millis: int
    allocatable_memory_bytes: int
    committed_cpu_millis: int
    committed_memory_bytes: int

    @property
    def free_cpu_millis(self) -> int:
        return self.allocatable_cpu_millis - self.committed_cpu_millis

    @property
    def free_memory_bytes(self) -> int:
        return self.allocatable_memory_bytes - self.committed_memory_bytes


def load_capacity_facts(
    certification: MultiReplicaCertification, *, repo_root: Path = REPO_ROOT
) -> CapacityFacts:
    """Read the host and cluster figures the script measured, untrusted."""
    reader = _Facts(STAGE_CAPACITY)
    document = reader.document(
        certification.artifact_path(certification.capacity_file, repo_root),
        "capacity facts",
    )
    engine = reader.object(document.get("engine"), "engine")
    cluster = reader.object(document.get("cluster"), "cluster")
    return CapacityFacts(
        engine_cpus=reader.integer(engine.get("cpus"), "engine.cpus", minimum=1),
        engine_memory_bytes=reader.integer(
            engine.get("memoryBytes"), "engine.memoryBytes", minimum=1
        ),
        node_count=reader.integer(
            cluster.get("schedulableNodes"), "cluster.schedulableNodes", minimum=1
        ),
        allocatable_cpu_millis=reader.integer(
            cluster.get("allocatableCpuMillis"), "cluster.allocatableCpuMillis"
        ),
        allocatable_memory_bytes=reader.integer(
            cluster.get("allocatableMemoryBytes"), "cluster.allocatableMemoryBytes"
        ),
        committed_cpu_millis=reader.integer(
            cluster.get("committedCpuMillis"), "cluster.committedCpuMillis"
        ),
        committed_memory_bytes=reader.integer(
            cluster.get("committedMemoryBytes"), "cluster.committedMemoryBytes"
        ),
    )


@dataclass(frozen=True, slots=True)
class CapacityFinding:
    """One thing the host or the cluster does not have, and by how much."""

    resource: str
    required: int
    available: int
    unit: str
    remedy: str

    def __str__(self) -> str:
        return (
            f"{self.resource}: {self.available} {self.unit} available, "
            f"{self.required} {self.unit} required. {self.remedy}"
        )


def assess_capacity(
    certification: MultiReplicaCertification, facts: CapacityFacts
) -> tuple[CapacityFinding, ...]:
    """Every reason this profile will not fit, rather than the first one.

    All four checks are evaluated and reported together on purpose. A preflight
    that stopped at the first shortfall would be run, corrected, and run again
    to discover the second -- and each of those attempts costs a model load on
    the host it just told the contributor is short of memory.
    """
    need = certification.capacity
    findings: list[CapacityFinding] = []
    if facts.engine_memory_bytes < need.minimum_engine_memory_bytes:
        findings.append(
            CapacityFinding(
                "container engine memory",
                need.minimum_engine_memory_bytes,
                facts.engine_memory_bytes,
                "bytes",
                "Raise the container VM's memory allocation; ADR 0001 D7 states "
                "the minimum tier.",
            )
        )
    if facts.engine_cpus < need.minimum_engine_cpus:
        findings.append(
            CapacityFinding(
                "container engine processors",
                need.minimum_engine_cpus,
                facts.engine_cpus,
                "cpus",
                "Raise the container VM's processor allocation; ADR 0001 D7 "
                "states the minimum tier.",
            )
        )
    required_cpu = need.requested_cpu_millis + need.headroom_cpu_millis
    if facts.free_cpu_millis < required_cpu:
        findings.append(
            CapacityFinding(
                "uncommitted cluster processor",
                required_cpu,
                facts.free_cpu_millis,
                "millicores",
                "Remove other workloads from the cluster, or raise the engine's "
                "processor allocation and recreate it. Pods whose requests do "
                "not fit stay Pending rather than failing.",
            )
        )
    required_memory = need.peak_memory_bytes + need.headroom_memory_bytes
    if facts.free_memory_bytes < required_memory:
        findings.append(
            CapacityFinding(
                "uncommitted cluster memory",
                required_memory,
                facts.free_memory_bytes,
                "bytes",
                "Remove other workloads from the cluster, or raise the engine's "
                "memory allocation and recreate it. The figure is the sum of the "
                "memory limits, because the container loading a 1.83 GB model is "
                "the one that would use its whole limit.",
            )
        )
    return tuple(findings)


def require_capacity(
    certification: MultiReplicaCertification, facts: CapacityFacts
) -> None:
    """Refuse before anything is installed, naming everything that is short."""
    findings = assess_capacity(certification, facts)
    if findings:
        raise CapacityUnmet(
            "this host cannot hold the multi-replica certification profile: "
            + "; ".join(str(finding) for finding in findings)
        )


@dataclass(frozen=True, slots=True)
class ReplicaFacts:
    """One pod of the release, as the cluster reported it."""

    pod_name: str
    component: str
    ready: bool
    ready_after_ms: int
    restarts: int


@dataclass(frozen=True, slots=True)
class MultiReplicaClusterFacts:
    """What the operating script measured, after this module has checked it."""

    cluster_name: str
    kube_context: str
    server_version: str
    node_image_digest: str
    helm_version: str
    kubectl_version: str
    terraform_version: str
    release_name: str
    release_namespace: str
    release_revision: int
    release_status: str
    chart_version: str
    profile: str
    workloads: tuple[WorkloadFacts, ...]
    replicas: tuple[ReplicaFacts, ...]
    model_cache: ModelCacheFacts
    prerequisites_ms: int
    install_ms: int
    api_ready_ms: int
    runtime_ready_ms: int
    release_test_ms: int
    release_test_passed: bool
    service_version: str
    model_identifier: str
    model_revision: str
    deployment_environment: str

    def ready_pods(self, component: str) -> tuple[str, ...]:
        return tuple(
            replica.pod_name
            for replica in self.replicas
            if replica.component == component and replica.ready
        )


def load_cluster_facts(
    certification: MultiReplicaCertification, *, repo_root: Path = REPO_ROOT
) -> MultiReplicaClusterFacts:
    """Read what the script measured, and hold every value to the descriptor."""
    reader = _Facts(STAGE_READINESS)
    document = reader.document(
        certification.artifact_path(certification.facts_file, repo_root),
        "cluster facts",
    )
    cluster = reader.object(document.get("cluster"), "cluster")
    tooling = reader.object(document.get("tooling"), "tooling")
    release = reader.object(document.get("release"), "release")
    timings = reader.object(document.get("timings"), "timings")
    configuration = reader.object(document.get("configuration"), "configuration")
    model_cache = reader.object(document.get("modelCache"), "modelCache")
    workloads = reader.entries(document.get("workloads"), "workloads")
    replicas = reader.entries(document.get("replicas"), "replicas")

    service_version = configuration.get("serviceVersion")
    if not isinstance(service_version, str):
        # Empty is allowed and is what the committed real render carries;
        # anything that is not a string at all is a collection defect.
        raise reader.fail(
            "the collected member 'configuration.serviceVersion' is not a string"
        )

    facts = MultiReplicaClusterFacts(
        cluster_name=reader.string(cluster.get("name"), "cluster.name"),
        kube_context=reader.string(cluster.get("context"), "cluster.context"),
        server_version=reader.string(
            cluster.get("serverVersion"), "cluster.serverVersion"
        ),
        node_image_digest=reader.string(
            cluster.get("nodeImageDigest"), "cluster.nodeImageDigest"
        ),
        helm_version=reader.string(tooling.get("helm"), "tooling.helm"),
        kubectl_version=reader.string(tooling.get("kubectl"), "tooling.kubectl"),
        terraform_version=reader.string(tooling.get("terraform"), "tooling.terraform"),
        release_name=reader.string(release.get("name"), "release.name"),
        release_namespace=reader.string(release.get("namespace"), "release.namespace"),
        release_revision=reader.integer(
            release.get("revision"), "release.revision", minimum=1
        ),
        release_status=reader.string(release.get("status"), "release.status"),
        chart_version=reader.string(release.get("chart"), "release.chart"),
        profile=reader.string(release.get("profile"), "release.profile"),
        workloads=tuple(
            _workload(entry, index) for index, entry in enumerate(workloads)
        ),
        replicas=tuple(
            _replica(reader, entry, index) for index, entry in enumerate(replicas)
        ),
        model_cache=_model_cache(model_cache),
        prerequisites_ms=reader.integer(
            timings.get("prerequisitesMs"), "timings.prerequisitesMs"
        ),
        install_ms=reader.integer(timings.get("installMs"), "timings.installMs"),
        api_ready_ms=reader.integer(timings.get("apiReadyMs"), "timings.apiReadyMs"),
        runtime_ready_ms=reader.integer(
            timings.get("runtimeReadyMs"), "timings.runtimeReadyMs"
        ),
        release_test_ms=reader.integer(
            timings.get("releaseTestMs"), "timings.releaseTestMs"
        ),
        release_test_passed=reader.boolean(
            release.get("testPassed"), "release.testPassed"
        ),
        service_version=service_version,
        model_identifier=reader.string(
            configuration.get("modelIdentifier"), "configuration.modelIdentifier"
        ),
        model_revision=reader.string(
            configuration.get("modelRevision"), "configuration.modelRevision"
        ),
        deployment_environment=reader.string(
            configuration.get("deploymentEnvironment"),
            "configuration.deploymentEnvironment",
        ),
    )
    _check_facts(certification, facts)
    return facts


def _replica(reader: _Facts, entry: Any, index: int) -> ReplicaFacts:
    record = reader.object(entry, f"replicas[{index}]")
    return ReplicaFacts(
        pod_name=reader.string(record.get("podName"), f"replicas[{index}].podName"),
        component=reader.string(
            record.get("component"), f"replicas[{index}].component"
        ),
        ready=reader.boolean(record.get("ready"), f"replicas[{index}].ready"),
        ready_after_ms=reader.integer(
            record.get("readyAfterMs"), f"replicas[{index}].readyAfterMs"
        ),
        restarts=reader.integer(record.get("restarts"), f"replicas[{index}].restarts"),
    )


def _refuse_mock(
    certification: MultiReplicaCertification, values: Sequence[str], stage: str
) -> None:
    marker = certification.prohibited_identity_substring.casefold()
    for value in values:
        if marker in value.casefold():
            raise CertificationFailed(
                "mock identity metadata was reported on the certified Kubernetes path",
                stage,
            )


def _check_workloads(
    certification: MultiReplicaCertification, facts: MultiReplicaClusterFacts
) -> None:
    target = certification.release
    observed = {(workload.name, workload.component) for workload in facts.workloads}
    if observed != {
        (target.api_deployment_name, target.api_component),
        (target.runtime_deployment_name, target.runtime_component),
    }:
        raise CertificationFailed(
            "the release did not install exactly the API and the serving runtime "
            "under the names and component labels this certification describes",
            STAGE_RELEASE,
        )
    for workload in facts.workloads:
        expected = target.desired(workload.name)
        if workload.replicas_desired != expected:
            raise CertificationFailed(
                f"'{workload.name}' runs {workload.replicas_desired} replicas and "
                f"this certification requests {expected}",
                STAGE_RELEASE,
            )
        if certification.require_every_replica_ready and not workload.fully_ready:
            raise CertificationFailed(
                f"'{workload.name}' reported {workload.replicas_ready} of "
                f"{workload.replicas_desired} replicas ready",
                STAGE_READINESS,
            )
        if certification.require_digest_pinned_images:
            for image in workload.images:
                if DIGEST_MARKER not in image:
                    raise CertificationFailed(
                        f"'{workload.name}' runs an image that is not digest-pinned",
                        STAGE_RELEASE,
                    )


def _check_replicas(
    certification: MultiReplicaCertification, facts: MultiReplicaClusterFacts
) -> None:
    """Every expected pod, individually, rather than a controller's summary.

    `status.readyReplicas` is a count, and a count agreeing with a desired count
    is what a Deployment reports -- not what an individual replica did. The
    per-pod list is what makes "every expected replica reached actual model
    readiness" a checked sentence, and it is also the list the correlation below
    is required to be a subset of.
    """
    target = certification.release
    budgets = certification.budgets
    api_pods = [
        replica
        for replica in facts.replicas
        if replica.component == target.api_component
    ]
    runtime_pods = [
        replica
        for replica in facts.replicas
        if replica.component == target.runtime_component
    ]
    if len(api_pods) != target.api_replicas:
        raise CertificationFailed(
            f"the cluster reported {len(api_pods)} platform API pods and this "
            f"certification requests {target.api_replicas}",
            STAGE_READINESS,
        )
    if len(runtime_pods) != target.runtime_replicas:
        raise CertificationFailed(
            f"the cluster reported {len(runtime_pods)} serving runtime pods and "
            f"this certification requests {target.runtime_replicas}",
            STAGE_READINESS,
        )
    if len({replica.pod_name for replica in facts.replicas}) != len(facts.replicas):
        raise CertificationFailed(
            "the collected replicas name one pod more than once", STAGE_READINESS
        )
    unexpected = [
        replica.component
        for replica in facts.replicas
        if replica.component not in (target.api_component, target.runtime_component)
    ]
    if unexpected:
        raise CertificationFailed(
            f"the collected replicas name a component this certification does "
            f"not describe: {sorted(set(unexpected))}",
            STAGE_READINESS,
        )
    for replica in facts.replicas:
        if certification.require_every_replica_ready and not replica.ready:
            raise CertificationFailed(
                f"replica '{replica.pod_name}' never became ready",
                STAGE_READINESS,
            )
        budget = (
            budgets.api_rollout_ms
            if replica.component == target.api_component
            else budgets.runtime_rollout_ms
        )
        if replica.ready_after_ms > budget:
            raise CertificationFailed(
                f"replica '{replica.pod_name}' took {replica.ready_after_ms} ms to "
                f"become ready, over the {budget} ms budget",
                STAGE_READINESS,
            )


def _check_facts(
    certification: MultiReplicaCertification, facts: MultiReplicaClusterFacts
) -> None:
    manifest = load_manifest()
    target = certification.release
    budgets = certification.budgets
    if (
        facts.cluster_name != certification.cluster_name
        or facts.kube_context != certification.cluster_context
    ):
        raise CertificationFailed(
            "the facts describe a cluster this certification does not name",
            STAGE_PREREQUISITES,
        )
    if (
        certification.require_pinned_node_image
        and facts.node_image_digest != certification.node_image_digest
    ):
        raise CertificationFailed(
            "the cluster is running a node image that is not the pinned one",
            STAGE_PREREQUISITES,
        )
    if (
        facts.release_name != target.name
        or facts.release_namespace != target.namespace
        or facts.profile != target.profile
    ):
        raise CertificationFailed(
            "the installed release is not the one this certification describes",
            STAGE_RELEASE,
        )
    if facts.release_status != "deployed":
        raise CertificationFailed(
            f"the release is '{facts.release_status}' rather than deployed",
            STAGE_RELEASE,
        )
    _check_workloads(certification, facts)
    _check_replicas(certification, facts)
    _check_model_cache(certification, facts)
    if certification.require_release_test and not facts.release_test_passed:
        raise CertificationFailed(
            "the release's own in-cluster connection test did not pass",
            STAGE_READINESS,
        )
    if (
        certification.require_pinned_model_revision
        and facts.model_revision != manifest.revision
    ):
        raise CertificationFailed(
            "the release was configured with a model revision that is not the "
            "pinned one",
            STAGE_RELEASE,
        )
    for measured, budget, description in (
        (facts.runtime_ready_ms, budgets.runtime_rollout_ms, "the serving runtime"),
        (facts.api_ready_ms, budgets.api_rollout_ms, "the platform API"),
        (facts.install_ms, budgets.install_ms, "the install"),
        (
            facts.release_test_ms,
            budgets.release_test_ms,
            "the in-cluster connection test",
        ),
    ):
        if measured > budget:
            raise CertificationFailed(
                f"{description} took {measured} ms, over the {budget} ms budget",
                STAGE_READINESS,
            )
    _refuse_mock(
        certification,
        (
            facts.profile,
            facts.model_identifier,
            facts.chart_version,
            facts.service_version,
        ),
        STAGE_RELEASE,
    )


def _check_model_cache(
    certification: MultiReplicaCertification, facts: MultiReplicaClusterFacts
) -> None:
    expected = certification.model_cache
    observed = facts.model_cache
    if observed.claim_name != expected.claim_name:
        raise CertificationFailed(
            f"the release mounts claim '{observed.claim_name}' and this "
            f"certification describes '{expected.claim_name}'",
            STAGE_RELEASE,
        )
    if expected.require_read_only_mount and not (
        observed.volume_read_only and observed.mount_read_only
    ):
        raise CertificationFailed(
            "the model cache is not mounted read-only", STAGE_RELEASE
        )
    if expected.verification_init_container not in observed.init_containers:
        raise CertificationFailed(
            f"the serving runtime runs no '{expected.verification_init_container}' "
            "init container, so nothing checked the artifact before it was loaded",
            STAGE_RELEASE,
        )
    if expected.require_artifact_hash_compared and not observed.artifact_hash_compared:
        raise CertificationFailed(
            "the release did not compare the model artifact against its pinned "
            "hash before loading it",
            STAGE_RELEASE,
        )


# -- the request set and the correlation -------------------------------------


@dataclass(frozen=True, slots=True)
class RequestObservation:
    """One request the in-cluster driver sent, with no generated text kept."""

    request_id: str
    status: int
    adapter_kind: str
    model_identifier: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    @property
    def succeeded(self) -> bool:
        return self.status == 200


@dataclass(frozen=True, slots=True)
class ReplicaRecord:
    """One `request.completed` record an API replica wrote about one request."""

    pod_name: str
    request_id: str
    event: str
    outcome: str
    http_status: int
    adapter_kind: str
    model_identifier: str
    model_revision: str
    runtime_id: str
    duration_ms: int


@dataclass(frozen=True, slots=True)
class DistributionObservations:
    """The whole request set and every record the replicas wrote about it."""

    started_at: str
    ended_at: str
    elapsed_ms: int
    requests: tuple[RequestObservation, ...]
    records: tuple[ReplicaRecord, ...]


def load_observations(
    certification: MultiReplicaCertification, *, repo_root: Path = REPO_ROOT
) -> DistributionObservations:
    """Read the driver's results and the replicas' own records, untrusted."""
    reader = _Facts(STAGE_DISTRIBUTION)
    document = reader.document(
        certification.artifact_path(certification.observations_file, repo_root),
        "distribution observations",
    )
    requests = reader.entries(document.get("requests"), "requests")
    records = document.get("records")
    if not isinstance(records, list):
        raise reader.fail("the collected member 'records' is not a list")
    observations = DistributionObservations(
        started_at=reader.string(document.get("startedAt"), "startedAt"),
        ended_at=reader.string(document.get("endedAt"), "endedAt"),
        elapsed_ms=reader.integer(document.get("elapsedMs"), "elapsedMs"),
        requests=tuple(
            _request(reader, entry, index) for index, entry in enumerate(requests)
        ),
        records=tuple(
            _record(reader, entry, index) for index, entry in enumerate(records)
        ),
    )
    _check_requests(certification, observations)
    return observations


def _request(reader: _Facts, entry: Any, index: int) -> RequestObservation:
    record = reader.object(entry, f"requests[{index}]")
    return RequestObservation(
        request_id=reader.string(
            record.get("requestId"), f"requests[{index}].requestId"
        ),
        status=reader.integer(record.get("status"), f"requests[{index}].status"),
        adapter_kind=reader.string(
            record.get("adapterKind"), f"requests[{index}].adapterKind"
        ),
        model_identifier=reader.string(
            record.get("modelIdentifier"), f"requests[{index}].modelIdentifier"
        ),
        prompt_tokens=reader.integer(
            record.get("promptTokens"), f"requests[{index}].promptTokens"
        ),
        completion_tokens=reader.integer(
            record.get("completionTokens"), f"requests[{index}].completionTokens"
        ),
        total_tokens=reader.integer(
            record.get("totalTokens"), f"requests[{index}].totalTokens"
        ),
    )


def _record(reader: _Facts, entry: Any, index: int) -> ReplicaRecord:
    record = reader.object(entry, f"records[{index}]")
    return ReplicaRecord(
        pod_name=reader.string(record.get("podName"), f"records[{index}].podName"),
        request_id=reader.string(
            record.get("requestId"), f"records[{index}].requestId"
        ),
        event=reader.string(record.get("event"), f"records[{index}].event"),
        outcome=reader.string(record.get("outcome"), f"records[{index}].outcome"),
        http_status=reader.integer(
            record.get("httpStatus"), f"records[{index}].httpStatus"
        ),
        adapter_kind=reader.string(
            record.get("adapterKind"), f"records[{index}].adapterKind"
        ),
        model_identifier=reader.string(
            record.get("modelIdentifier"), f"records[{index}].modelIdentifier"
        ),
        model_revision=reader.string(
            record.get("modelRevision"), f"records[{index}].modelRevision"
        ),
        runtime_id=reader.string(
            record.get("runtimeId"), f"records[{index}].runtimeId"
        ),
        duration_ms=reader.integer(
            record.get("durationMs"), f"records[{index}].durationMs"
        ),
    )


def _check_requests(
    certification: MultiReplicaCertification, observations: DistributionObservations
) -> None:
    plan = certification.distribution
    expected = set(plan.request_ids)
    observed = [request.request_id for request in observations.requests]
    if len(observed) != len(set(observed)):
        raise CertificationFailed(
            "the driver reported one request identifier more than once",
            STAGE_DISTRIBUTION,
        )
    if set(observed) != expected:
        missing = sorted(expected - set(observed))
        extra = sorted(set(observed) - expected)
        raise CertificationFailed(
            f"the driver did not send exactly the planned request set; missing "
            f"{missing}, unexpected {extra}",
            STAGE_DISTRIBUTION,
        )
    if observations.elapsed_ms > certification.budgets.distribution_ms:
        raise CertificationFailed(
            f"the request set took {observations.elapsed_ms} ms, over the "
            f"{certification.budgets.distribution_ms} ms budget",
            STAGE_DISTRIBUTION,
        )
    for request in observations.requests:
        if certification.require_every_request_successful and not request.succeeded:
            raise CertificationFailed(
                f"request '{request.request_id}' answered {request.status} rather "
                "than 200",
                STAGE_DISTRIBUTION,
            )
        if request.adapter_kind != certification.required_adapter_kind:
            raise CertificationFailed(
                f"request '{request.request_id}' was answered by the "
                f"'{request.adapter_kind}' adapter kind rather than "
                f"'{certification.required_adapter_kind}'",
                STAGE_DISTRIBUTION,
            )
        if certification.require_usage_counts and not (
            request.prompt_tokens > 0
            and request.completion_tokens > 0
            and request.total_tokens
            == request.prompt_tokens + request.completion_tokens
        ):
            # A completion the runtime counted no output tokens for is not a
            # completion; a mock that reported none would land here too.
            raise CertificationFailed(
                f"request '{request.request_id}' carried absent or inconsistent "
                "token counts",
                STAGE_DISTRIBUTION,
            )
        _refuse_mock(
            certification,
            (request.adapter_kind, request.model_identifier),
            STAGE_DISTRIBUTION,
        )


@dataclass(frozen=True, slots=True)
class ReplicaDistribution:
    """One serving replica, and the requests it is recorded as having served."""

    pod_name: str
    ready_after_ms: int
    request_ids: tuple[str, ...]

    @property
    def request_count(self) -> int:
        return len(self.request_ids)


def correlate(
    certification: MultiReplicaCertification,
    facts: MultiReplicaClusterFacts,
    observations: DistributionObservations,
) -> tuple[ReplicaDistribution, ...]:
    """Join the requests to the replicas that logged them, or refuse to.

    This is the assertion the whole PR exists for, so what it will not accept is
    worth listing: a request with no record at all, a request two replicas both
    claim, a record from a pod that is not one of the ready API replicas, a
    record that is not a completion, and a set of records covering fewer distinct
    pods than the descriptor requires.
    """
    manifest = load_manifest()
    plan = certification.distribution
    target = certification.release
    ready = set(facts.ready_pods(target.api_component))
    readiness = {replica.pod_name: replica.ready_after_ms for replica in facts.replicas}
    served: dict[str, list[str]] = {}
    for record in observations.records:
        if record.pod_name not in ready:
            raise CertificationFailed(
                f"a record naming pod '{record.pod_name}' was collected, and that "
                "pod is not one of the ready platform API replicas",
                STAGE_CORRELATION,
            )
        if record.event != names.EVENT_REQUEST_COMPLETED:
            raise CertificationFailed(
                f"request '{record.request_id}' was recorded as "
                f"'{record.event}' rather than a completion",
                STAGE_CORRELATION,
            )
        if record.outcome != names.OUTCOME_SUCCESS or record.http_status != 200:
            raise CertificationFailed(
                f"request '{record.request_id}' was recorded with outcome "
                f"'{record.outcome}' and status {record.http_status}",
                STAGE_CORRELATION,
            )
        if record.adapter_kind != certification.required_adapter_kind:
            raise CertificationFailed(
                f"replica '{record.pod_name}' recorded the "
                f"'{record.adapter_kind}' adapter kind on the certified path",
                STAGE_CORRELATION,
            )
        if (
            certification.require_pinned_model_revision
            and record.model_revision != manifest.revision
        ):
            raise CertificationFailed(
                f"replica '{record.pod_name}' recorded a model revision that is "
                "not the pinned one",
                STAGE_CORRELATION,
            )
        if record.model_identifier != facts.model_identifier:
            raise CertificationFailed(
                f"replica '{record.pod_name}' recorded a model the release was "
                "not configured with",
                STAGE_CORRELATION,
            )
        _refuse_mock(
            certification,
            (
                record.adapter_kind,
                record.model_identifier,
                record.model_revision,
                record.runtime_id,
            ),
            STAGE_CORRELATION,
        )
        served.setdefault(record.pod_name, []).append(record.request_id)

    claimed: dict[str, str] = {}
    for pod_name, request_ids in served.items():
        for request_id in request_ids:
            if request_id in claimed:
                raise CertificationFailed(
                    f"request '{request_id}' was recorded by two replicas, "
                    f"'{claimed[request_id]}' and '{pod_name}'",
                    STAGE_CORRELATION,
                )
            claimed[request_id] = pod_name

    if certification.require_per_replica_correlation:
        uncorrelated = sorted(set(plan.request_ids) - set(claimed))
        if uncorrelated:
            # The failure the story names: without a record joining a successful
            # request to a pod, the run has a request count and no distribution.
            raise CertificationFailed(
                f"no replica recorded {uncorrelated}; the requests succeeded and "
                "nothing correlates them to a serving replica",
                STAGE_CORRELATION,
            )

    distribution = tuple(
        ReplicaDistribution(
            pod_name=pod_name,
            ready_after_ms=readiness.get(pod_name, 0),
            request_ids=tuple(sorted(request_ids)),
        )
        for pod_name, request_ids in sorted(served.items())
    )
    if len(distribution) < plan.minimum_distinct_replicas:
        raise CertificationFailed(
            f"successful requests reached {len(distribution)} distinct serving "
            f"replicas and this certification requires "
            f"{plan.minimum_distinct_replicas}. The requests were distributed by "
            "the Service rather than by this workflow, so this is an outcome "
            "rather than a defect -- and it is not a multi-replica certification",
            STAGE_CORRELATION,
        )
    return distribution


# -- cleanup -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CleanupFacts:
    """What the teardown removed, and what it deliberately left standing."""

    release_uninstalled: bool
    driver_removed: bool
    residue_objects: int
    helm_release_absent: bool
    namespace_survives: bool
    claims_before: int
    claims_after: int
    uninstall_ms: int


def load_cleanup_facts(
    certification: MultiReplicaCertification, *, repo_root: Path = REPO_ROOT
) -> CleanupFacts:
    """Read what the teardown reported, and hold it to the cleanup policy."""
    reader = _Facts(STAGE_CLEANUP)
    document = reader.document(
        certification.artifact_path(certification.cleanup_file, repo_root),
        "cleanup facts",
    )
    facts = CleanupFacts(
        release_uninstalled=reader.boolean(
            document.get("releaseUninstalled"), "releaseUninstalled"
        ),
        driver_removed=reader.boolean(document.get("driverRemoved"), "driverRemoved"),
        residue_objects=reader.integer(
            document.get("residueObjects"), "residueObjects"
        ),
        helm_release_absent=reader.boolean(
            document.get("helmReleaseAbsent"), "helmReleaseAbsent"
        ),
        namespace_survives=reader.boolean(
            document.get("namespaceSurvives"), "namespaceSurvives"
        ),
        claims_before=reader.integer(document.get("claimsBefore"), "claimsBefore"),
        claims_after=reader.integer(document.get("claimsAfter"), "claimsAfter"),
        uninstall_ms=reader.integer(document.get("uninstallMs"), "uninstallMs"),
    )
    _check_cleanup(certification, facts)
    return facts


def _check_cleanup(
    certification: MultiReplicaCertification, facts: CleanupFacts
) -> None:
    if certification.uninstalls_release and not facts.release_uninstalled:
        raise CertificationFailed("the release was not uninstalled", STAGE_CLEANUP)
    if certification.removes_request_driver and not facts.driver_removed:
        raise CertificationFailed(
            "the in-cluster request driver was left in the namespace",
            STAGE_CLEANUP,
        )
    if facts.residue_objects or not facts.helm_release_absent:
        raise CertificationFailed(
            f"{facts.residue_objects} object(s) carrying the release's instance "
            "label survived the uninstall",
            STAGE_CLEANUP,
        )
    if not facts.namespace_survives:
        # The namespace is Terraform's. A release that removed it took a
        # prerequisite with it, which is the opposite failure to leaving residue
        # and is the more expensive one.
        raise CertificationFailed(
            "the release namespace did not survive the uninstall, and it is a "
            "Terraform prerequisite that must outlive the release",
            STAGE_CLEANUP,
        )
    if facts.claims_after != facts.claims_before:
        raise CertificationFailed(
            f"the persistent volume claim count changed across the release: "
            f"{facts.claims_before} before, {facts.claims_after} after",
            STAGE_CLEANUP,
        )
    if facts.uninstall_ms > certification.budgets.uninstall_ms:
        raise CertificationFailed(
            f"the uninstall took {facts.uninstall_ms} ms, over the "
            f"{certification.budgets.uninstall_ms} ms budget",
            STAGE_CLEANUP,
        )


# -- the record --------------------------------------------------------------


class MultiReplicaEvidence:
    """Write only this workflow's own records to the fixed ignored location."""

    def __init__(
        self,
        certification: MultiReplicaCertification,
        *,
        repo_root: Path = REPO_ROOT,
    ) -> None:
        if certification.evidence_directory != EXPECTED_EVIDENCE_DIRECTORY:
            raise EvidenceUnwritable("the certification evidence path is unsafe")
        self.root = repo_root.resolve()
        self.directory = self.root / certification.evidence_directory
        self.result_path = self.directory / certification.result_file
        self.diagnostics_path = self.directory / certification.diagnostics_file
        self._ensure_safe()

    def _ensure_safe(self) -> None:
        ensure_evidence_paths_safe(self.root, (self.result_path, self.diagnostics_path))

    def write(self, target: Path, document: Mapping[str, object]) -> Path:
        """Write one whole record, refusing an unsafe path before and after mkdir."""
        self._ensure_safe()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._ensure_safe()
        try:
            target.write_text(
                json.dumps(document, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        except OSError as error:
            raise EvidenceUnwritable(
                "the certification evidence could not be written"
            ) from error
        return target


@dataclass(frozen=True, slots=True)
class MultiReplicaResult:
    """A completed run, in the shape the evidence record is written from."""

    certification: MultiReplicaCertification
    capacity: CapacityFacts
    facts: MultiReplicaClusterFacts
    observations: DistributionObservations
    distribution: tuple[ReplicaDistribution, ...]
    cleanup: CleanupFacts | None


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Why a run stopped, in this workflow's stage vocabulary."""

    stage: str
    reason: str


def capacity_document(
    certification: MultiReplicaCertification,
    facts: CapacityFacts,
    findings: Sequence[CapacityFinding],
) -> dict[str, object]:
    """The resource profile, as measured and as required."""
    need = certification.capacity
    return {
        "engine": {
            "cpus": facts.engine_cpus,
            "memoryBytes": facts.engine_memory_bytes,
            "minimumCpus": need.minimum_engine_cpus,
            "minimumMemoryBytes": need.minimum_engine_memory_bytes,
        },
        "cluster": {
            "schedulableNodes": facts.node_count,
            "allocatableCpuMillis": facts.allocatable_cpu_millis,
            "allocatableMemoryBytes": facts.allocatable_memory_bytes,
            "committedCpuMillis": facts.committed_cpu_millis,
            "committedMemoryBytes": facts.committed_memory_bytes,
            "freeCpuMillis": facts.free_cpu_millis,
            "freeMemoryBytes": facts.free_memory_bytes,
        },
        "profile": {
            "requestedCpuMillis": need.requested_cpu_millis,
            "requestedMemoryBytes": need.requested_memory_bytes,
            "peakMemoryBytes": need.peak_memory_bytes,
            "headroomCpuMillis": need.headroom_cpu_millis,
            "headroomMemoryBytes": need.headroom_memory_bytes,
        },
        "findings": [
            {
                "resource": finding.resource,
                "required": finding.required,
                "available": finding.available,
                "unit": finding.unit,
                "remedy": finding.remedy,
            }
            for finding in findings
        ],
        "sufficient": not findings,
    }


def _replicas_document(
    facts: MultiReplicaClusterFacts,
) -> list[dict[str, object]]:
    return [
        {
            "podName": replica.pod_name,
            "component": replica.component,
            "ready": replica.ready,
            "readyAfterMs": replica.ready_after_ms,
            "restarts": replica.restarts,
        }
        for replica in facts.replicas
    ]


def _distribution_document(
    distribution: Sequence[ReplicaDistribution],
) -> list[dict[str, object]]:
    return [
        {
            "podName": replica.pod_name,
            "readyAfterMs": replica.ready_after_ms,
            "requestCount": replica.request_count,
            "requestIds": list(replica.request_ids),
        }
        for replica in distribution
    ]


def result_document(result: MultiReplicaResult) -> dict[str, object]:
    """The machine-readable multi-replica C2 record, carrying no generated text."""
    certification = result.certification
    facts = result.facts
    plan = certification.distribution
    observations = result.observations
    package = load_runtime_package()
    manifest = load_manifest()
    cleanup = result.cleanup
    return {
        "certificationId": certification.certification_id,
        "certificationLevel": certification.certification_level,
        "evidenceClass": certification.evidence_class,
        "evidenceLabel": certification.evidence_label,
        "outcome": "certified",
        "replicas": {
            "apiRequested": certification.release.api_replicas,
            "apiReady": len(facts.ready_pods(certification.release.api_component)),
            "runtimeRequested": certification.release.runtime_replicas,
            "runtimeReady": len(
                facts.ready_pods(certification.release.runtime_component)
            ),
            "minimumDistinctReplicas": plan.minimum_distinct_replicas,
            "distinctReplicasReached": len(result.distribution),
            "perReplicaReadiness": _replicas_document(facts),
        },
        "distribution": {
            "mechanism": plan.mechanism,
            "requestCount": plan.request_count,
            "successfulRequests": sum(
                1 for request in observations.requests if request.succeeded
            ),
            "startedAt": observations.started_at,
            "endedAt": observations.ended_at,
            "elapsedMs": observations.elapsed_ms,
            "perReplica": _distribution_document(result.distribution),
            "generatedTextRetained": False,
        },
        "kubernetes": {
            "cluster": {
                "name": facts.cluster_name,
                "context": facts.kube_context,
                "serverVersion": facts.server_version,
                "nodeImageDigest": facts.node_image_digest,
            },
            "tooling": {
                "helm": facts.helm_version,
                "kubectl": facts.kubectl_version,
                "terraform": facts.terraform_version,
            },
            "release": {
                "name": facts.release_name,
                "namespace": facts.release_namespace,
                "revision": facts.release_revision,
                "status": facts.release_status,
                "chart": facts.chart_version,
                "profile": facts.profile,
                "testPassed": facts.release_test_passed,
            },
            "workloads": [
                {
                    "name": workload.name,
                    "component": workload.component,
                    "images": list(workload.images),
                    "replicasDesired": workload.replicas_desired,
                    "replicasReady": workload.replicas_ready,
                }
                for workload in facts.workloads
            ],
            "modelCache": {
                "claimName": facts.model_cache.claim_name,
                "volumeReadOnly": facts.model_cache.volume_read_only,
                "mountReadOnly": facts.model_cache.mount_read_only,
                "initContainers": list(facts.model_cache.init_containers),
                "artifactHashCompared": facts.model_cache.artifact_hash_compared,
            },
            "configuration": {
                "serviceVersion": facts.service_version,
                "modelIdentifier": facts.model_identifier,
                "modelRevision": facts.model_revision,
                "deploymentEnvironment": facts.deployment_environment,
            },
            "timings": {
                "prerequisitesMs": facts.prerequisites_ms,
                "installMs": facts.install_ms,
                "apiReadyMs": facts.api_ready_ms,
                "runtimeReadyMs": facts.runtime_ready_ms,
                "releaseTestMs": facts.release_test_ms,
            },
        },
        "resources": capacity_document(certification, result.capacity, ()),
        "provenance": {
            "chartRef": certification.chart_ref,
            "runtimeImage": package.image_reference,
            "requestDriverImage": plan.driver_image,
            "modelRepository": manifest.repository,
            "modelRevision": manifest.revision,
            "modelFile": manifest.file,
            "modelSha256": manifest.sha256,
            "modelHashComparedInCluster": str(
                facts.model_cache.artifact_hash_compared
            ).lower(),
            "apiServiceName": certification.release.api_service_name,
            "procedureRef": certification.procedure_ref,
            "singleReplicaCertificationRef": (
                certification.single_replica_certification_ref
            ),
        },
        "cleanup": (
            {"performed": False}
            if cleanup is None
            else {
                "performed": True,
                "releaseUninstalled": cleanup.release_uninstalled,
                "requestDriverRemoved": cleanup.driver_removed,
                "residueObjects": cleanup.residue_objects,
                "helmReleaseAbsent": cleanup.helm_release_absent,
                "namespaceSurvives": cleanup.namespace_survives,
                "claimsBefore": cleanup.claims_before,
                "claimsAfter": cleanup.claims_after,
                "uninstallMs": cleanup.uninstall_ms,
                "prerequisitesRemoved": certification.removes_prerequisites,
                "clusterRemoved": certification.removes_cluster,
            }
        ),
        "limitations": list(certification.limitations),
    }


def diagnostics_document(diagnostics: Diagnostics) -> dict[str, object]:
    """What a failed run leaves behind, in this workflow's stage vocabulary."""
    return {
        "certificationId": EXPECTED_ID,
        "certificationLevel": EXPECTED_LEVEL,
        "outcome": "not-certified",
        "stage": diagnostics.stage,
        "reason": diagnostics.reason,
    }


# -- the workflow ------------------------------------------------------------


def certify_multi_replica(
    certification: MultiReplicaCertification,
    *,
    confirmed: bool,
    repo_root: Path = REPO_ROOT,
) -> MultiReplicaResult:
    """Assert over everything the script collected, or raise carrying the stage.

    Nothing here contacts a cluster. Every input is a file the operating script
    wrote while the release was installed, and each one is read as untrusted
    input at a location the descriptor fixes.
    """
    if not confirmed:
        raise CertificationFailed(
            "multi-replica Kubernetes certification requires --confirm-real-kubernetes",
            STAGE_PREREQUISITES,
        )
    capacity = load_capacity_facts(certification, repo_root=repo_root)
    require_capacity(certification, capacity)
    facts = load_cluster_facts(certification, repo_root=repo_root)
    observations = load_observations(certification, repo_root=repo_root)
    distribution = correlate(certification, facts, observations)
    return MultiReplicaResult(
        certification=certification,
        capacity=capacity,
        facts=facts,
        observations=observations,
        distribution=distribution,
        cleanup=None,
    )


def adapter_kind_marker() -> str:
    """The body member the in-cluster driver greps for, spelled once.

    The driver cannot parse JSON -- it is BusyBox -- so it matches a literal
    substring of the compact response body. That literal is derived here from
    the same constant the API serialises, so a rename of the extension member
    breaks this string rather than silently making every request look
    unanswered.
    """
    return f'"{EXTENSION_ADAPTER_KIND}":"'
