"""The Kubernetes C2 descriptor, the assertions over it, and its evidence record.

Three things are deliberately separated here.

**Loading** reads committed files and contacts nothing. The descriptor is checked
against itself and then against the records that already decide the same values
elsewhere -- the runtime package's startup budget, the composition's response
budget, the runtime profile's request budget, the selected model's revision. A
descriptor that disagrees with any of them is refused before a cluster is touched.

**Observing** happens while a release is installed and a bounded forward to its
Service is open. It reads the identity the API publishes about itself, sends one
fixed request, and holds the answer to every real assertion: the real adapter
kind, the pinned model revision, runtime-derived token counts, non-empty content,
and no mock marker anywhere in the identity. Token usage is declared supported by
the selected real adapter and unsupported by the committed mock, so an absent
declaration is mock capability metadata whatever else agreed.

**Recording** writes one whole document into the ignored evidence directory, with
the generated text deliberately not retained. The record is labelled
`local real Kubernetes`; nothing here may relabel a synthetic run as a real one.

What is *not* here is any cluster operation. The script
`scripts/environment/kubernetes-certification.sh` provisions the prerequisites,
installs the release, waits for readiness, opens the forward, collects the cluster
facts this module reads, and tears the release down. That script's guards decide
which cluster is acted on, and duplicating them in Python would make two guards
where the repository has one.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from inferops.adapters.llama_cpp import (
    LLAMA_SERVER_ADAPTER_KIND,
    LLAMA_SERVER_RUNTIME_NAME,
)
from inferops.api.surface import (
    CAPABILITY_TOKEN_USAGE,
    CHAT_COMPLETIONS_PATH,
    CORRELATION_ID_HEADER,
    EXTENSION_ADAPTER_KIND,
    EXTENSION_MEMBER,
    EXTENSION_MODEL_REF,
    MODELS_PATH,
    READY_PATH,
    REQUEST_ID_HEADER,
)
from tools.local_composition import load_composition
from tools.model_acquisition import load_manifest
from tools.runtime_configuration import load_runtime_profile
from tools.runtime_packaging import load_runtime_package

REPO_ROOT = Path(__file__).resolve().parents[2]
CERTIFICATION_PATH = (
    REPO_ROOT / "deploy/serving/certification/k8s-real-inference.v1.json"
)

EXPECTED_SCHEMA = "inferops.io/v1alpha1"
EXPECTED_ID = "inferops-c2-kubernetes-real-inference"
EXPECTED_LEVEL = "C2"
EXPECTED_EVIDENCE_CLASS = "local-real-cpu"
EXPECTED_EVIDENCE_LABEL = "local real Kubernetes"
EXPECTED_LANE = "real-runtime"
EXPECTED_CHART_REF = "charts/inferops-llm"
EXPECTED_CERTIFICATION_REF = "docs/testing/certification.md"
EXPECTED_PROCEDURE_REF = "docs/serving/kubernetes-real-inference-certification.md"
EXPECTED_EVIDENCE_DIRECTORY = Path(".cache/inferops/certification")
EXPECTED_FACTS_FILE = ".artifacts/kubernetes-certification/cluster-facts.json"

#: ADR 0001 (D5): every namespace this project may install into carries this
#: prefix. The chart refuses a release namespace without it; the descriptor is
#: refused here for the same reason, before anything reads a kubeconfig.
NAMESPACE_PREFIX = "inferops-"

#: The forward this workflow observes through is opened on the loopback
#: interface by the script that owns the cluster. A base URL naming anything
#: else is refused rather than followed: the one thing a certification must
#: never do is describe a cluster nobody meant to certify.
LOOPBACK_HOST = "127.0.0.1"

#: What a pinned image reference looks like. A tag is a label that can be moved,
#: and docs/testing/certification.md requires a digest in a C2 record.
DIGEST_MARKER = "@sha256:"

#: The stages a run passes through, in order. A diagnostics record names the one
#: it stopped in, which is what turns a failure into a place to look.
STAGE_LOAD = "load"
STAGE_PREREQUISITES = "prerequisites"
STAGE_RELEASE = "release"
STAGE_READINESS = "readiness"
STAGE_IDENTITY = "identity"
STAGE_INFERENCE = "inference"
STAGE_EVIDENCE = "evidence"

STAGES: tuple[str, ...] = (
    STAGE_LOAD,
    STAGE_PREREQUISITES,
    STAGE_RELEASE,
    STAGE_READINESS,
    STAGE_IDENTITY,
    STAGE_INFERENCE,
    STAGE_EVIDENCE,
)


class CertificationError(RuntimeError):
    """The descriptor, the cluster facts, or a bounded step was refused."""

    stage = STAGE_LOAD


class PrerequisiteUnmet(CertificationError):
    """Authorization, the forward, or the collected facts were not in place."""

    stage = STAGE_PREREQUISITES


class CertificationFailed(CertificationError):
    """The release ran and the real Kubernetes path did not certify."""

    def __init__(self, message: str, stage: str = STAGE_READINESS) -> None:
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True, slots=True)
class ReleaseTarget:
    """The one release, in the one namespace, this descriptor may describe."""

    name: str
    namespace: str
    profile: str
    api_service_name: str
    api_service_port: int
    runtime_service_name: str
    instance_selector: str
    api_component: str
    runtime_component: str
    replicas: int


@dataclass(frozen=True, slots=True)
class Certification:
    """The committed Kubernetes C2 descriptor after every field is validated."""

    schema_version: str
    certification_id: str
    certification_level: str
    evidence_class: str
    evidence_label: str
    lane: str
    chart_ref: str
    certification_ref: str
    procedure_ref: str
    release: ReleaseTarget
    requires_terraform_prerequisites: bool
    requires_target_cluster_assertion: bool
    requires_pinned_runtime_image: bool
    requires_pinned_api_image: bool
    requires_verified_model_cache: bool
    install_budget_ms: int
    runtime_budget_ms: int
    api_budget_ms: int
    release_test_budget_ms: int
    request_host: str
    request_path: str
    models_path: str
    readiness_path: str
    prompt: str
    request_id: str
    correlation_id: str
    request_timeout_ms: int
    required_adapter_kind: str
    prohibited_identity_substring: str
    require_usage_counts: bool
    require_nonempty_content: bool
    require_pinned_model_revision: bool
    require_digest_pinned_images: bool
    require_every_replica_ready: bool
    require_release_test: bool
    evidence_directory: Path
    result_file: str
    diagnostics_file: str
    facts_file: str
    retain_generated_text: bool
    uninstalls_release: bool
    removes_prerequisites: bool
    removes_cluster: bool


@dataclass(frozen=True, slots=True)
class WorkloadFacts:
    """One Deployment of the release, as the cluster reported it."""

    name: str
    component: str
    images: tuple[str, ...]
    replicas_desired: int
    replicas_ready: int

    @property
    def fully_ready(self) -> bool:
        return (
            self.replicas_desired > 0 and self.replicas_ready == self.replicas_desired
        )


@dataclass(frozen=True, slots=True)
class ClusterFacts:
    """What the operating script measured, after this module has checked it.

    Every member is non-identifying on purpose. A node name, a kubeconfig path,
    a user, and a host directory are all things a contributor's cluster would
    hand over freely and none of them belong in a committed record.
    """

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


@dataclass(frozen=True, slots=True)
class ObservedIdentity:
    """The model and runtime identity the API published about itself."""

    adapter_kind: str
    model_identifier: str
    runtime_name: str
    runtime_version: str
    model_revision: str
    token_usage_declared: bool


@dataclass(frozen=True, slots=True)
class InferenceObservation:
    """One completed request, with generated text deliberately not retained."""

    status: int
    elapsed_ms: int
    completion_characters: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    request_id_echoed: bool
    correlation_id_echoed: bool


@dataclass(frozen=True, slots=True)
class KubernetesCertificationResult:
    """A completed run, in the shape the evidence record is written from."""

    certification_id: str
    certification_level: str
    evidence_class: str
    evidence_label: str
    facts: ClusterFacts
    provenance: Mapping[str, str]
    identity: ObservedIdentity
    inference: InferenceObservation


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Why a run stopped, in the stage vocabulary this workflow publishes."""

    stage: str
    reason: str
    facts: ClusterFacts | None = None


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """The status, parsed body, and headers retained from one forwarded call."""

    status: int
    body: object | None
    headers: Mapping[str, str]


ApiGet = Callable[[str, float], ApiResponse]
ApiPost = Callable[[str, Mapping[str, object], Mapping[str, str], float], ApiResponse]


# -- reading the descriptor -------------------------------------------------


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CertificationError(f"certification field '{field}' must be an object")
    return cast(dict[str, Any], value)


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise CertificationError(f"certification field '{field}' must be a string")
    return value


def _integer(value: Any, field: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise CertificationError(
            f"certification field '{field}' must be an integer of at least {minimum}"
        )
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise CertificationError(f"certification field '{field}' must be a boolean")
    return value


def _require_keys(record: Mapping[str, Any], field: str, expected: set[str]) -> None:
    if set(record) != expected:
        raise CertificationError(
            f"certification field '{field}' has missing or unsupported members"
        )


def _read_release(release: Mapping[str, Any]) -> ReleaseTarget:
    return ReleaseTarget(
        name=_string(release.get("name"), "release.name"),
        namespace=_string(release.get("namespace"), "release.namespace"),
        profile=_string(release.get("profile"), "release.profile"),
        api_service_name=_string(
            release.get("apiServiceName"), "release.apiServiceName"
        ),
        api_service_port=_integer(
            release.get("apiServicePort"), "release.apiServicePort"
        ),
        runtime_service_name=_string(
            release.get("runtimeServiceName"), "release.runtimeServiceName"
        ),
        instance_selector=_string(
            release.get("instanceSelector"), "release.instanceSelector"
        ),
        api_component=_string(release.get("apiComponent"), "release.apiComponent"),
        runtime_component=_string(
            release.get("runtimeComponent"), "release.runtimeComponent"
        ),
        replicas=_integer(release.get("replicas"), "release.replicas"),
    )


def load_certification(path: Path = CERTIFICATION_PATH) -> Certification:
    """Load and cross-check the descriptor without performing any real I/O."""
    try:
        record = _object(json.loads(path.read_text(encoding="utf-8")), "root")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CertificationError(
            "the certification descriptor is unreadable"
        ) from error

    release = _object(record.get("release"), "release")
    prerequisites = _object(record.get("prerequisites"), "prerequisites")
    readiness = _object(record.get("readiness"), "readiness")
    request = _object(record.get("request"), "request")
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
            "release",
            "prerequisites",
            "readiness",
            "request",
            "assertions",
            "evidence",
            "cleanup",
        },
    )
    _require_keys(
        release,
        "release",
        {
            "name",
            "namespace",
            "profile",
            "apiServiceName",
            "apiServicePort",
            "runtimeServiceName",
            "instanceSelector",
            "apiComponent",
            "runtimeComponent",
            "replicas",
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
        },
    )
    _require_keys(
        readiness,
        "readiness",
        {"installBudgetMs", "runtimeBudgetMs", "apiBudgetMs", "releaseTestBudgetMs"},
    )
    _require_keys(
        request,
        "request",
        {
            "host",
            "path",
            "modelsPath",
            "readinessPath",
            "prompt",
            "requestId",
            "correlationId",
            "timeoutMs",
        },
    )
    _require_keys(
        assertions,
        "assertions",
        {
            "requiredAdapterKind",
            "prohibitedIdentitySubstring",
            "requireUsageCounts",
            "requireNonEmptyContent",
            "requirePinnedModelRevision",
            "requireDigestPinnedImages",
            "requireEveryReplicaReady",
            "requireReleaseTest",
        },
    )
    _require_keys(
        evidence,
        "evidence",
        {
            "directory",
            "resultFile",
            "diagnosticsFile",
            "factsFile",
            "retainGeneratedText",
        },
    )
    _require_keys(
        cleanup,
        "cleanup",
        {"uninstallsRelease", "removesPrerequisites", "removesCluster"},
    )

    certification = Certification(
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
        release=_read_release(release),
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
        install_budget_ms=_integer(
            readiness.get("installBudgetMs"), "readiness.installBudgetMs"
        ),
        runtime_budget_ms=_integer(
            readiness.get("runtimeBudgetMs"), "readiness.runtimeBudgetMs"
        ),
        api_budget_ms=_integer(readiness.get("apiBudgetMs"), "readiness.apiBudgetMs"),
        release_test_budget_ms=_integer(
            readiness.get("releaseTestBudgetMs"), "readiness.releaseTestBudgetMs"
        ),
        request_host=_string(request.get("host"), "request.host"),
        request_path=_string(request.get("path"), "request.path"),
        models_path=_string(request.get("modelsPath"), "request.modelsPath"),
        readiness_path=_string(request.get("readinessPath"), "request.readinessPath"),
        prompt=_string(request.get("prompt"), "request.prompt"),
        request_id=_string(request.get("requestId"), "request.requestId"),
        correlation_id=_string(request.get("correlationId"), "request.correlationId"),
        request_timeout_ms=_integer(request.get("timeoutMs"), "request.timeoutMs"),
        required_adapter_kind=_string(
            assertions.get("requiredAdapterKind"), "assertions.requiredAdapterKind"
        ),
        prohibited_identity_substring=_string(
            assertions.get("prohibitedIdentitySubstring"),
            "assertions.prohibitedIdentitySubstring",
        ),
        require_usage_counts=_boolean(
            assertions.get("requireUsageCounts"), "assertions.requireUsageCounts"
        ),
        require_nonempty_content=_boolean(
            assertions.get("requireNonEmptyContent"),
            "assertions.requireNonEmptyContent",
        ),
        require_pinned_model_revision=_boolean(
            assertions.get("requirePinnedModelRevision"),
            "assertions.requirePinnedModelRevision",
        ),
        require_digest_pinned_images=_boolean(
            assertions.get("requireDigestPinnedImages"),
            "assertions.requireDigestPinnedImages",
        ),
        require_every_replica_ready=_boolean(
            assertions.get("requireEveryReplicaReady"),
            "assertions.requireEveryReplicaReady",
        ),
        require_release_test=_boolean(
            assertions.get("requireReleaseTest"), "assertions.requireReleaseTest"
        ),
        evidence_directory=Path(
            _string(evidence.get("directory"), "evidence.directory")
        ),
        result_file=_string(evidence.get("resultFile"), "evidence.resultFile"),
        diagnostics_file=_string(
            evidence.get("diagnosticsFile"), "evidence.diagnosticsFile"
        ),
        facts_file=_string(evidence.get("factsFile"), "evidence.factsFile"),
        retain_generated_text=_boolean(
            evidence.get("retainGeneratedText"), "evidence.retainGeneratedText"
        ),
        uninstalls_release=_boolean(
            cleanup.get("uninstallsRelease"), "cleanup.uninstallsRelease"
        ),
        removes_prerequisites=_boolean(
            cleanup.get("removesPrerequisites"), "cleanup.removesPrerequisites"
        ),
        removes_cluster=_boolean(
            cleanup.get("removesCluster"), "cleanup.removesCluster"
        ),
    )
    _validate(certification)
    return certification


def _validate(certification: Certification) -> None:
    """Refuse a descriptor that disagrees with any record already deciding it."""
    composition = load_composition()
    package = load_runtime_package()
    profile = load_runtime_profile()
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
    ):
        raise CertificationError("the certification identity is unsupported")
    if not (
        certification.requires_terraform_prerequisites
        and certification.requires_target_cluster_assertion
        and certification.requires_pinned_runtime_image
        and certification.requires_pinned_api_image
        and certification.requires_verified_model_cache
    ):
        raise CertificationError(
            "a Kubernetes certification run may not waive a prerequisite"
        )
    if not certification.release.namespace.startswith(NAMESPACE_PREFIX):
        raise CertificationError(
            "the release namespace must carry the 'inferops-' prefix (ADR 0001 D5)"
        )
    # The mock marker itself is not re-checked for emptiness here: `_string`
    # above already refuses an empty one, and a second check that cannot fail
    # would read like a guard while defending nothing.
    if (
        certification.release.profile != "real"
        or certification.required_adapter_kind != LLAMA_SERVER_ADAPTER_KIND
        or composition.adapter_selection != LLAMA_SERVER_ADAPTER_KIND
        or composition.mock_fallback
    ):
        raise CertificationError(
            "a Kubernetes certification run may certify only the real path"
        )
    if not certification.release.api_service_name.startswith(
        certification.release.name
    ):
        raise CertificationError(
            "the API Service is not one this release's name could produce"
        )
    if (
        certification.runtime_budget_ms != package.startup_budget_ms
        or certification.api_budget_ms != composition.response_budget_ms
        or certification.request_timeout_ms != profile.request_budget_ms
    ):
        raise CertificationError("the certification budgets disagree with the profile")
    if certification.install_budget_ms < certification.runtime_budget_ms:
        # `helm install --wait` contains the model load, so an install budget
        # under the load budget is a timeout that reports a slow load as a
        # failure. It is checked here rather than in the operating script
        # because the script reads both figures from this descriptor.
        raise CertificationError(
            "the install budget is below the model load budget it has to contain"
        )
    if (
        certification.request_path != CHAT_COMPLETIONS_PATH
        or certification.models_path != MODELS_PATH
        or certification.readiness_path != READY_PATH
    ):
        raise CertificationError("the certification request path is not a served route")
    if certification.request_host != LOOPBACK_HOST:
        raise CertificationError("the certification forward must stay on loopback")
    if any(character in certification.prompt for character in "\r\n"):
        raise CertificationError("the certification prompt must be one line")
    if not (
        certification.require_usage_counts
        and certification.require_nonempty_content
        and certification.require_pinned_model_revision
        and certification.require_digest_pinned_images
        and certification.require_every_replica_ready
        and certification.require_release_test
    ):
        raise CertificationError("a certification run may not waive a real assertion")
    if (
        certification.evidence_directory != EXPECTED_EVIDENCE_DIRECTORY
        or certification.facts_file != EXPECTED_FACTS_FILE
        or certification.retain_generated_text
        or Path(certification.result_file).name != certification.result_file
        or Path(certification.diagnostics_file).name != certification.diagnostics_file
        or certification.result_file == certification.diagnostics_file
    ):
        raise CertificationError("the certification evidence location is unsafe")
    if not certification.uninstalls_release:
        raise CertificationError(
            "a certification run must remove the release it installed"
        )
    if certification.removes_prerequisites or certification.removes_cluster:
        # The prerequisite layer and the cluster outlive a release by design
        # (docs/architecture/resource-ownership.md). A workflow that removed
        # either would be a release owning what it only referenced, and it
        # would reclaim model weights this project re-downloads over a
        # transport whose certificate it does not validate.
        raise CertificationError(
            "a certification run may remove neither the prerequisites nor the cluster"
        )


# -- the cluster facts the operating script collected ------------------------


def _facts_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CertificationFailed(
            f"the cluster facts member '{field}' is not an object", STAGE_READINESS
        )
    return cast(dict[str, Any], value)


def _facts_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CertificationFailed(
            f"the cluster facts member '{field}' is not a non-empty string",
            STAGE_READINESS,
        )
    return value


def _facts_optional_string(value: Any, field: str) -> str:
    """A recorded string that the chart is allowed to leave unset.

    `telemetry.serviceVersion` is a free string with an empty default, and the
    committed real render carries it empty. Refusing an empty value here would
    make the certification unrunnable against the very values file it names, so
    the emptiness is recorded rather than treated as a missing measurement --
    and it is still held to being a string, because a number or an object there
    is a collection defect rather than an unset field.
    """
    if not isinstance(value, str):
        raise CertificationFailed(
            f"the cluster facts member '{field}' is not a string", STAGE_READINESS
        )
    return value


def _facts_integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise CertificationFailed(
            f"the cluster facts member '{field}' is not an integer of at least "
            f"{minimum}",
            STAGE_READINESS,
        )
    return value


def _workload(entry: Any, index: int) -> WorkloadFacts:
    record = _facts_object(entry, f"workloads[{index}]")
    images = record.get("images")
    if not isinstance(images, list) or not images:
        raise CertificationFailed(
            f"the cluster facts member 'workloads[{index}].images' names no image",
            STAGE_READINESS,
        )
    return WorkloadFacts(
        name=_facts_string(record.get("name"), f"workloads[{index}].name"),
        component=_facts_string(
            record.get("component"), f"workloads[{index}].component"
        ),
        images=tuple(
            _facts_string(image, f"workloads[{index}].images[{position}]")
            for position, image in enumerate(images)
        ),
        replicas_desired=_facts_integer(
            record.get("replicasDesired"), f"workloads[{index}].replicasDesired"
        ),
        replicas_ready=_facts_integer(
            record.get("replicasReady"), f"workloads[{index}].replicasReady"
        ),
    )


def load_cluster_facts(path: Path, certification: Certification) -> ClusterFacts:
    """Read what the operating script measured, and hold it to the descriptor.

    The file is host state written by the script beside this module rather than
    a committed record, so nothing in it is trusted: the release it names, the
    namespace, the profile, the replica counts, and the image pins are each
    compared with what the descriptor says a certified run must be.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CertificationFailed(
            "the collected cluster facts are unreadable", STAGE_READINESS
        ) from error

    root = _facts_object(document, "root")
    cluster = _facts_object(root.get("cluster"), "cluster")
    tooling = _facts_object(root.get("tooling"), "tooling")
    release = _facts_object(root.get("release"), "release")
    timings = _facts_object(root.get("timings"), "timings")
    configuration = _facts_object(root.get("configuration"), "configuration")
    workloads = root.get("workloads")
    if not isinstance(workloads, list) or not workloads:
        raise CertificationFailed("the cluster facts name no workload", STAGE_READINESS)

    facts = ClusterFacts(
        cluster_name=_facts_string(cluster.get("name"), "cluster.name"),
        kube_context=_facts_string(cluster.get("context"), "cluster.context"),
        server_version=_facts_string(
            cluster.get("serverVersion"), "cluster.serverVersion"
        ),
        node_image_digest=_facts_string(
            cluster.get("nodeImageDigest"), "cluster.nodeImageDigest"
        ),
        helm_version=_facts_string(tooling.get("helm"), "tooling.helm"),
        kubectl_version=_facts_string(tooling.get("kubectl"), "tooling.kubectl"),
        terraform_version=_facts_string(tooling.get("terraform"), "tooling.terraform"),
        release_name=_facts_string(release.get("name"), "release.name"),
        release_namespace=_facts_string(release.get("namespace"), "release.namespace"),
        release_revision=_facts_integer(
            release.get("revision"), "release.revision", minimum=1
        ),
        release_status=_facts_string(release.get("status"), "release.status"),
        chart_version=_facts_string(release.get("chart"), "release.chart"),
        profile=_facts_string(release.get("profile"), "release.profile"),
        workloads=tuple(
            _workload(entry, index) for index, entry in enumerate(workloads)
        ),
        prerequisites_ms=_facts_integer(
            timings.get("prerequisitesMs"), "timings.prerequisitesMs"
        ),
        install_ms=_facts_integer(timings.get("installMs"), "timings.installMs"),
        api_ready_ms=_facts_integer(timings.get("apiReadyMs"), "timings.apiReadyMs"),
        runtime_ready_ms=_facts_integer(
            timings.get("runtimeReadyMs"), "timings.runtimeReadyMs"
        ),
        release_test_ms=_facts_integer(
            timings.get("releaseTestMs"), "timings.releaseTestMs"
        ),
        release_test_passed=release.get("testPassed") is True,
        service_version=_facts_optional_string(
            configuration.get("serviceVersion"), "configuration.serviceVersion"
        ),
        model_identifier=_facts_string(
            configuration.get("modelIdentifier"), "configuration.modelIdentifier"
        ),
        model_revision=_facts_string(
            configuration.get("modelRevision"), "configuration.modelRevision"
        ),
        deployment_environment=_facts_string(
            configuration.get("deploymentEnvironment"),
            "configuration.deploymentEnvironment",
        ),
    )
    _check_facts(certification, facts)
    return facts


def _check_facts(certification: Certification, facts: ClusterFacts) -> None:
    manifest = load_manifest()
    target = certification.release
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
    components = {workload.component for workload in facts.workloads}
    if components != {target.api_component, target.runtime_component}:
        raise CertificationFailed(
            "the release did not install exactly the API and the serving runtime",
            STAGE_RELEASE,
        )
    for workload in facts.workloads:
        if certification.require_every_replica_ready and not workload.fully_ready:
            raise CertificationFailed(
                f"'{workload.name}' reported {workload.replicas_ready} of "
                f"{workload.replicas_desired} replicas ready",
                STAGE_READINESS,
            )
        if workload.replicas_desired != target.replicas:
            raise CertificationFailed(
                f"'{workload.name}' runs {workload.replicas_desired} replicas and "
                f"this certification describes {target.replicas}",
                STAGE_RELEASE,
            )
        if certification.require_digest_pinned_images:
            for image in workload.images:
                if DIGEST_MARKER not in image:
                    raise CertificationFailed(
                        f"'{workload.name}' runs an image that is not digest-pinned",
                        STAGE_RELEASE,
                    )
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
            "the release was configured with a model revision that is not the pinned "
            "one",
            STAGE_RELEASE,
        )
    if facts.runtime_ready_ms > certification.runtime_budget_ms:
        raise CertificationFailed(
            f"the serving runtime took {facts.runtime_ready_ms} ms to become ready, "
            f"over the {certification.runtime_budget_ms} ms budget",
            STAGE_READINESS,
        )
    if facts.api_ready_ms > certification.api_budget_ms:
        raise CertificationFailed(
            f"the platform API took {facts.api_ready_ms} ms to become ready, over "
            f"the {certification.api_budget_ms} ms budget",
            STAGE_READINESS,
        )
    if facts.install_ms > certification.install_budget_ms:
        raise CertificationFailed(
            f"the install took {facts.install_ms} ms, over the "
            f"{certification.install_budget_ms} ms budget",
            STAGE_RELEASE,
        )
    _refuse_mock_identity(
        certification,
        (
            facts.profile,
            facts.model_identifier,
            facts.chart_version,
            facts.service_version,
        ),
        STAGE_RELEASE,
    )


# -- the forwarded client ----------------------------------------------------


def _response(status: int, payload: bytes, headers: Mapping[str, str]) -> ApiResponse:
    try:
        body: object | None = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        body = None
    return ApiResponse(status, body, dict(headers))


def require_forwarded_base_url(base_url: str, certification: Certification) -> str:
    """Refuse a base URL that is not the loopback forward the script opened.

    A certification that followed whatever address it was handed could describe
    a cluster nobody meant to certify, and its record would carry this project's
    evidence label while doing so. The scheme, the host, and the presence of a
    port are checked; the port number itself is the operator's, because the
    forward has to be able to move when something else already holds a port.
    """
    parsed = urlparse(base_url)
    if parsed.scheme != "http":
        raise PrerequisiteUnmet("the forwarded base URL must be plain loopback HTTP")
    if parsed.hostname != certification.request_host:
        raise PrerequisiteUnmet(
            f"the forwarded base URL must name {certification.request_host}"
        )
    if parsed.port is None:
        raise PrerequisiteUnmet("the forwarded base URL must name the forwarded port")
    if parsed.path.rstrip("/") or parsed.query or parsed.fragment:
        raise PrerequisiteUnmet("the forwarded base URL must carry no path or query")
    return f"http://{parsed.hostname}:{parsed.port}"


def api_get(url: str, timeout_seconds: float) -> ApiResponse:
    """GET one forwarded InferOps endpoint and parse only its JSON body."""
    try:
        with urlopen(Request(url, method="GET"), timeout=timeout_seconds) as response:
            return _response(response.status, response.read(), dict(response.headers))
    except HTTPError as error:
        return _response(error.code, error.read(), dict(error.headers))
    except (OSError, URLError) as error:
        raise CertificationFailed(
            "the forwarded InferOps Service could not be reached", STAGE_IDENTITY
        ) from error


def api_post(
    url: str,
    body: Mapping[str, object],
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> ApiResponse:
    """POST one bounded JSON request to the forwarded InferOps Service."""
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return _response(response.status, response.read(), dict(response.headers))
    except HTTPError as error:
        return _response(error.code, error.read(), dict(error.headers))
    except (OSError, URLError) as error:
        raise CertificationFailed(
            "the forwarded InferOps Service could not be reached", STAGE_INFERENCE
        ) from error


# -- the assertions ---------------------------------------------------------


def _mapping_member(value: object, field: str, stage: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CertificationFailed(
            f"the API response member '{field}' is not an object", stage
        )
    return cast(Mapping[str, object], value)


def _string_member(value: object, field: str, stage: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CertificationFailed(
            f"the API response member '{field}' is not a non-empty string", stage
        )
    return value


def _refuse_mock_identity(
    certification: Certification, values: Sequence[str], stage: str
) -> None:
    marker = certification.prohibited_identity_substring.casefold()
    for value in values:
        if marker in value.casefold():
            raise CertificationFailed(
                "mock identity metadata was reported on the certified Kubernetes path",
                stage,
            )


def observe_identity(
    certification: Certification, facts: ClusterFacts, *, base_url: str, get: ApiGet
) -> ObservedIdentity:
    """Read the identity the release publishes about itself through its Service."""
    stage = STAGE_IDENTITY
    response = get(
        f"{base_url}{certification.models_path}",
        certification.request_timeout_ms / 1000,
    )
    if response.status != 200:
        raise CertificationFailed(
            "the model list did not answer with a description", stage
        )
    body = _mapping_member(response.body, "root", stage)
    extension = _mapping_member(body.get(EXTENSION_MEMBER), EXTENSION_MEMBER, stage)
    runtime = _mapping_member(extension.get("runtime"), "runtime", stage)
    capabilities = _mapping_member(extension.get("capabilities"), "capabilities", stage)
    entries = body.get("data")
    if not isinstance(entries, list) or len(entries) != 1:
        raise CertificationFailed(
            "the certified release must serve exactly one model", stage
        )
    identity = ObservedIdentity(
        adapter_kind=_string_member(
            extension.get(EXTENSION_ADAPTER_KIND), EXTENSION_ADAPTER_KIND, stage
        ),
        model_identifier=_string_member(
            _mapping_member(entries[0], "data[0]", stage).get("id"), "data[0].id", stage
        ),
        runtime_name=_string_member(runtime.get("name"), "runtime.name", stage),
        runtime_version=_string_member(
            runtime.get("version"), "runtime.version", stage
        ),
        model_revision=_string_member(
            runtime.get("modelRevision"), "runtime.modelRevision", stage
        ),
        token_usage_declared=capabilities.get(CAPABILITY_TOKEN_USAGE) is True,
    )
    manifest = load_manifest()
    if identity.adapter_kind != certification.required_adapter_kind:
        raise CertificationFailed(
            "the model list did not report the required adapter kind", stage
        )
    if identity.runtime_name != LLAMA_SERVER_RUNTIME_NAME:
        raise CertificationFailed("the model list named an unselected runtime", stage)
    if identity.model_identifier != facts.model_identifier:
        raise CertificationFailed(
            "the model list names a model the release was not configured with", stage
        )
    if (
        certification.require_pinned_model_revision
        and identity.model_revision != manifest.revision
    ):
        raise CertificationFailed(
            "the model list did not name the pinned model revision", stage
        )
    if not identity.token_usage_declared:
        # The selected real adapter declares token counting supported and the
        # committed mock declares it unsupported, so an absent or false
        # declaration here is mock capability metadata whatever else agreed.
        raise CertificationFailed(
            "the certified path declares token usage unsupported, which is mock "
            "capability metadata",
            stage,
        )
    _refuse_mock_identity(
        certification,
        (
            identity.adapter_kind,
            identity.model_identifier,
            identity.runtime_name,
            identity.runtime_version,
            identity.model_revision,
        ),
        stage,
    )
    return identity


def observe_inference(
    certification: Certification,
    facts: ClusterFacts,
    *,
    base_url: str,
    post: ApiPost,
    clock: Callable[[], float] = time.monotonic,
) -> InferenceObservation:
    """Send the one fixed request and hold its answer to every real assertion."""
    stage = STAGE_INFERENCE
    started = clock()
    response = post(
        f"{base_url}{certification.request_path}",
        {
            "model": facts.model_identifier,
            "messages": [{"role": "user", "content": certification.prompt}],
        },
        {
            REQUEST_ID_HEADER: certification.request_id,
            CORRELATION_ID_HEADER: certification.correlation_id,
        },
        certification.request_timeout_ms / 1000,
    )
    elapsed_ms = max(0, round((clock() - started) * 1000))
    if response.status != 200:
        raise CertificationFailed(
            "the certified request did not return a completion", stage
        )
    body = _mapping_member(response.body, "root", stage)
    extension = _mapping_member(body.get(EXTENSION_MEMBER), EXTENSION_MEMBER, stage)
    if extension.get(EXTENSION_ADAPTER_KIND) != certification.required_adapter_kind:
        raise CertificationFailed(
            "the completion did not report the required adapter kind", stage
        )
    if extension.get(EXTENSION_MODEL_REF) != facts.model_identifier:
        raise CertificationFailed("the completion named an unconfigured model", stage)
    choices = body.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise CertificationFailed("the completion carried no single choice", stage)
    message = _mapping_member(
        _mapping_member(choices[0], "choices[0]", stage).get("message"),
        "choices[0].message",
        stage,
    )
    content = message.get("content")
    if not isinstance(content, str) or (
        certification.require_nonempty_content and not content.strip()
    ):
        raise CertificationFailed(
            "the real model returned no completion content", stage
        )
    counts = _mapping_member(body.get("usage"), "usage", stage)
    prompt_tokens = counts.get("prompt_tokens")
    completion_tokens = counts.get("completion_tokens")
    total_tokens = counts.get("total_tokens")
    if not (
        isinstance(prompt_tokens, int)
        and isinstance(completion_tokens, int)
        and isinstance(total_tokens, int)
        and prompt_tokens > 0
        and completion_tokens > 0
        and total_tokens == prompt_tokens + completion_tokens
    ):
        raise CertificationFailed(
            "the completion counts are absent or inconsistent", stage
        )
    return InferenceObservation(
        status=response.status,
        elapsed_ms=elapsed_ms,
        completion_characters=len(content),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        request_id_echoed=(
            response.headers.get(REQUEST_ID_HEADER) == certification.request_id
        ),
        correlation_id_echoed=(
            response.headers.get(CORRELATION_ID_HEADER) == certification.correlation_id
        ),
    )


# -- the evidence directory -------------------------------------------------


class EvidenceDirectory:
    """Write only this workflow's own records to the fixed ignored location."""

    def __init__(
        self, certification: Certification, *, repo_root: Path = REPO_ROOT
    ) -> None:
        if certification.evidence_directory != EXPECTED_EVIDENCE_DIRECTORY:
            raise CertificationError("the certification evidence path is unsafe")
        self.root = repo_root.resolve()
        self.directory = self.root / certification.evidence_directory
        self.result_path = self.directory / certification.result_file
        self.diagnostics_path = self.directory / certification.diagnostics_file
        self._ensure_safe()

    def _ensure_safe(self) -> None:
        candidate = self.root
        for part in EXPECTED_EVIDENCE_DIRECTORY.parts:
            candidate = candidate / part
            if candidate.is_symlink() or os.path.isjunction(candidate):
                raise CertificationError("the certification evidence path is unsafe")
        for target in (self.result_path, self.diagnostics_path):
            if target.is_symlink() or os.path.isjunction(target):
                raise CertificationError("the certification evidence path is unsafe")
            if not target.resolve().is_relative_to(self.root):
                raise CertificationError("the certification evidence path is unsafe")

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
            raise CertificationError(
                "the certification evidence could not be written"
            ) from error
        return target


def _workloads_document(workloads: Sequence[WorkloadFacts]) -> list[dict[str, object]]:
    return [
        {
            "name": workload.name,
            "component": workload.component,
            "images": list(workload.images),
            "replicasDesired": workload.replicas_desired,
            "replicasReady": workload.replicas_ready,
        }
        for workload in workloads
    ]


def _facts_document(facts: ClusterFacts) -> dict[str, object]:
    return {
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
        "workloads": _workloads_document(facts.workloads),
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
    }


def result_document(result: KubernetesCertificationResult) -> dict[str, object]:
    """The machine-readable Kubernetes C2 record, carrying no generated text."""
    return {
        "certificationId": result.certification_id,
        "certificationLevel": result.certification_level,
        "evidenceClass": result.evidence_class,
        "evidenceLabel": result.evidence_label,
        "outcome": "certified",
        "kubernetes": _facts_document(result.facts),
        "provenance": dict(result.provenance),
        "identity": {
            "adapterKind": result.identity.adapter_kind,
            "modelIdentifier": result.identity.model_identifier,
            "runtimeName": result.identity.runtime_name,
            "runtimeVersion": result.identity.runtime_version,
            "modelRevision": result.identity.model_revision,
            "tokenUsageDeclared": result.identity.token_usage_declared,
        },
        "inference": {
            "status": result.inference.status,
            "elapsedMs": result.inference.elapsed_ms,
            "completionCharacters": result.inference.completion_characters,
            "promptTokens": result.inference.prompt_tokens,
            "completionTokens": result.inference.completion_tokens,
            "totalTokens": result.inference.total_tokens,
            "requestIdEchoed": result.inference.request_id_echoed,
            "correlationIdEchoed": result.inference.correlation_id_echoed,
            "generatedTextRetained": False,
        },
    }


def diagnostics_document(diagnostics: Diagnostics) -> dict[str, object]:
    """What a failed run leaves behind, in this workflow's stage vocabulary."""
    return {
        "certificationId": EXPECTED_ID,
        "certificationLevel": EXPECTED_LEVEL,
        "outcome": "not-certified",
        "stage": diagnostics.stage,
        "reason": diagnostics.reason,
        "kubernetes": (
            None if diagnostics.facts is None else _facts_document(diagnostics.facts)
        ),
    }


def provenance(certification: Certification) -> dict[str, str]:
    """The immutable inputs a C2 record must name, and nothing host-specific."""
    package = load_runtime_package()
    manifest = load_manifest()
    return {
        "chartRef": certification.chart_ref,
        "runtimeImage": package.image_reference,
        "modelRepository": manifest.repository,
        "modelRevision": manifest.revision,
        "modelFile": manifest.file,
        "modelSha256": manifest.sha256,
        "apiServiceName": certification.release.api_service_name,
        "runtimeServiceName": certification.release.runtime_service_name,
        "procedureRef": certification.procedure_ref,
    }


# -- the workflow -----------------------------------------------------------


def certify(
    certification: Certification,
    *,
    confirmed: bool,
    base_url: str,
    facts_path: Path,
    get: ApiGet = api_get,
    post: ApiPost = api_post,
    clock: Callable[[], float] = time.monotonic,
) -> KubernetesCertificationResult:
    """Observe an installed release, or raise carrying the stage that stopped it.

    Everything this needs about the cluster has already happened: the release is
    installed, both Deployments are ready, and a loopback forward to the API
    Service is open. What is left is the part that decides whether a record may
    be written -- and it is deliberately last, so that a release which never
    became ready produces diagnostics rather than a result.
    """
    if not confirmed:
        raise PrerequisiteUnmet(
            "Kubernetes real-inference certification requires --confirm-real-kubernetes"
        )
    forwarded = require_forwarded_base_url(base_url, certification)
    facts = load_cluster_facts(facts_path, certification)
    identity = observe_identity(certification, facts, base_url=forwarded, get=get)
    inference = observe_inference(
        certification, facts, base_url=forwarded, post=post, clock=clock
    )
    return KubernetesCertificationResult(
        certification_id=certification.certification_id,
        certification_level=certification.certification_level,
        evidence_class=certification.evidence_class,
        evidence_label=certification.evidence_label,
        facts=facts,
        provenance=provenance(certification),
        identity=identity,
        inference=inference,
    )
