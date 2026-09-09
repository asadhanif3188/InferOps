"""The Helm upgrade and rollback descriptor, its assertions, and its record.

Three things are separated here, the same way they are separated in
`tools/kubernetes_certification`, and for the same reason.

**Loading** reads committed files and contacts nothing. The descriptor is checked
against itself and then against the record that already decides most of it: the
Kubernetes real-inference certification. This experiment installs the same chart,
into the same namespace, as the same release, on the same cluster, and reads the
same API through the same loopback forward — so the cluster block, the release
block, the request block, and every budget the two share are compared for
*equality* rather than re-derived. A second set of numbers describing one release
is a second release waiting to be discovered.

**Observing** happens while the release is installed. Nothing here operates a
cluster: `scripts/environment/helm-upgrade-rollback.sh` owns every `helm` and
`kubectl` invocation, because the guard that establishes which cluster is being
acted on already lives beside those wrappers and a second implementation of it in
another language would be a second guard. What this module reads is the file that
script wrote, at the location the descriptor fixes, as untrusted input.

**Recording** writes one whole document into the ignored evidence directory, with
the generated text deliberately not retained.

What the experiment is, and what makes each half of it hard to fake:

1. a known-good release is installed and answers a real completion;
2. it is upgraded with a controlled change — `telemetry.serviceVersion` — that
   reaches the rendered ConfigMap and therefore the pod-template checksum. A
   value that reached neither would produce a revision Helm recorded and the
   cluster never applied, and rolling *that* back would prove nothing;
3. it is upgraded again with an injected fault the chart accepts and the cluster
   cannot run: a `model.artifact.sizeBytes` that the mounted artifact cannot
   match, which fails in the `verify-model` init container of the serving
   runtime. It changes no image reference, pulls nothing, creates no object
   outside the release, and is removed by the rollback rather than by a second
   edit;
4. the failure is detected. A **decisive** signal — an init container that
   terminated non-zero, or one crash-looping — is required, because the other
   thing available is a deadline, and a deadline is a statement about time rather
   than about health. A deadline reached before the known-good rollout budget
   would be a slow start reported as a failure, and this module refuses that
   reading outright;
5. the release is rolled back to the last known-good revision, and a real
   completion is served again. Recovery is measured from the detection to that
   completion.

The one thing this module will not do is call a run successful because Helm
called a rollback successful. Helm's own bookkeeping says a revision was
recorded. Whether the rendered configuration went back, whether the fault is
gone, and whether a real model answered are three separate questions, and each is
asked of the cluster rather than of Helm.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

from inferops.adapters.llama_cpp import LLAMA_SERVER_RUNTIME_NAME
from inferops.api.surface import (
    CAPABILITY_TOKEN_USAGE,
    CORRELATION_ID_HEADER,
    EXTENSION_ADAPTER_KIND,
    EXTENSION_MEMBER,
    EXTENSION_MODEL_REF,
    REQUEST_ID_HEADER,
)
from tools.kubernetes_certification.core import (
    ApiGet,
    ApiPost,
    ApiResponse,
    Certification,
    CertificationError,
    ClusterTarget,
    ReleaseTarget,
    api_get,
    api_post,
    load_certification,
)
from tools.kubernetes_certification.core import (
    require_forwarded_base_url as _certification_forward_guard,
)
from tools.model_acquisition import load_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_PATH = REPO_ROOT / "deploy/serving/experiments/helm-upgrade-rollback.v1.json"

EXPECTED_SCHEMA = "inferops.io/v1alpha1"
EXPECTED_ID = "inferops-helm-upgrade-rollback"
EXPECTED_EVIDENCE_CLASS = "local-real-cpu"
EXPECTED_EVIDENCE_LABEL = "local real Kubernetes"
EXPECTED_CERTIFICATION_CEILING = "C2"
EXPECTED_LANE = "real-runtime"
EXPECTED_CHART_REF = "charts/inferops-llm"
EXPECTED_CERTIFICATION_REF = "docs/testing/certification.md"
EXPECTED_PROCEDURE_REF = "docs/environment/helm-upgrade-rollback.md"
EXPECTED_BASELINE_REF = "deploy/serving/certification/k8s-real-inference.v1.json"
EXPECTED_EVIDENCE_DIRECTORY = Path(".cache/inferops/experiments")
EXPECTED_LIFECYCLE_FILE = ".artifacts/helm-upgrade-rollback/lifecycle-facts.json"
EXPECTED_IMPACT_FILE = ".artifacts/helm-upgrade-rollback/impact-observations.json"
EXPECTED_CLEANUP_FILE = ".artifacts/helm-upgrade-rollback/cleanup-facts.json"

#: The one values path the controlled change may take, and the ConfigMap key it
#: has to arrive at. Both are fixed here rather than left to the descriptor: the
#: property being demonstrated is that an upgrade *reaches the running workload*,
#: and a change to a value outside `inferops-llm.derivedEnv` would leave the pod
#: template's checksum untouched and roll nothing.
CANDIDATE_VALUES_PATH = "telemetry.serviceVersion"
CANDIDATE_CONFIG_MAP_KEY = "INFEROPS_SERVICE_VERSION"

#: The one fault this experiment may inject, and the values path that injects it.
#: A byte count the mounted artifact cannot match is refused by the first check
#: in the chart's verification script, before the full artifact read, so the
#: failure is fast, decisive, and printed by the init container that made it.
FAULT_MECHANISM = "model-artifact-byte-count-mismatch"
FAULT_VALUES_PATH = "model.artifact.sizeBytes"
FAULT_WORKLOAD = "serving-runtime"
FAULT_CONTAINER = "verify-model"
FAULT_SCOPE = "release"
FAULT_REVERSED_BY = "helm-rollback"

#: A candidate is failed on evidence, not on a clock. These are the two shapes of
#: evidence the cluster can offer for the injected fault; both say the container
#: ran and stopped, and neither is a statement about elapsed time.
DECISIVE_SIGNALS: tuple[str, ...] = (
    "init-container-nonzero-exit",
    "init-container-crash-loop",
)

#: The clock, kept separate. A rollout that made no progress inside its own
#: deadline is failed, and the Deployment controller says so — but it says so
#: about progress rather than about health, so a record naming this signal has to
#: name it as what it is.
DEADLINE_SIGNAL = "progress-deadline-exceeded"

#: What is not a detection of the injected fault at all. A candidate pod that
#: never scheduled never ran the init container, so the experiment observed a
#: host that is too small rather than a fault it injected, and the honest outcome
#: is a refusal with a remedy rather than a record.
INCONCLUSIVE_SIGNALS: tuple[str, ...] = ("candidate-pod-unschedulable",)

#: The stages, in the order a run passes through them.
STAGE_LOAD = "load"
STAGE_PREREQUISITES = "prerequisites"
STAGE_BASELINE = "baseline"
STAGE_CANDIDATE = "candidate"
STAGE_FAULT = "unhealthy-candidate"
STAGE_DETECTION = "detection"
STAGE_ROLLBACK = "rollback"
STAGE_VERIFY = "verification"
STAGE_IMPACT = "impact"
STAGE_CLEANUP = "cleanup"
STAGE_EVIDENCE = "evidence"

STAGES: tuple[str, ...] = (
    STAGE_LOAD,
    STAGE_PREREQUISITES,
    STAGE_BASELINE,
    STAGE_CANDIDATE,
    STAGE_FAULT,
    STAGE_DETECTION,
    STAGE_ROLLBACK,
    STAGE_VERIFY,
    STAGE_IMPACT,
    STAGE_CLEANUP,
    STAGE_EVIDENCE,
)

#: The stage names the descriptor publishes, which are the operator-facing steps
#: rather than this module's internal vocabulary. They are checked so that the
#: procedure document and the descriptor cannot describe different experiments.
DECLARED_STAGES: tuple[str, ...] = (
    "baseline",
    "candidate",
    "unhealthy-candidate",
    "rollback",
    "cleanup",
)

#: The outcome word a stage may carry. Anything else is a collected document
#: describing something this module does not know how to read.
OUTCOME_HEALTHY = "healthy"
OUTCOME_FAILED = "failed"
OUTCOMES: tuple[str, ...] = (OUTCOME_HEALTHY, OUTCOME_FAILED)

#: What a value written into a `helm --set` and echoed into the record may
#: contain. It is not a style rule: the operating script interpolates the
#: candidate value into a command line, and the record prints it.
SAFE_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")

#: The lowest byte count the chart accepts under the real profile. `_validate.tpl`
#: refuses a zero outright, so a descriptor injecting one would be refused by
#: `helm upgrade` before anything reached the cluster — and an experiment that
#: never installed its own fault would report a detection it did not make.
MINIMUM_INJECTED_SIZE_BYTES = 1


class ExperimentError(RuntimeError):
    """The descriptor, the collected facts, or a bounded step was refused."""

    stage = STAGE_LOAD


class ExperimentRefused(ExperimentError):
    """Authorization, the forward, or a safety rule stopped the run."""

    def __init__(self, message: str, stage: str = STAGE_PREREQUISITES) -> None:
        super().__init__(message)
        self.stage = stage


class ExperimentFailed(ExperimentError):
    """The release ran and the upgrade or the rollback did not behave."""

    def __init__(self, message: str, stage: str = STAGE_BASELINE) -> None:
        super().__init__(message)
        self.stage = stage


class ExperimentInconclusive(ExperimentError):
    """The run observed something other than the fault it injected."""

    def __init__(self, message: str, stage: str = STAGE_DETECTION) -> None:
        super().__init__(message)
        self.stage = stage


class EvidenceUnwritable(ExperimentError):
    """The record could not be stored, whatever the run itself established."""

    stage = STAGE_EVIDENCE


# -- the descriptor ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CandidateChange:
    """The controlled change, and the proof that it reached the workload."""

    values_path: str
    candidate_value: str
    config_map_key: str
    reaches_pod_template: bool
    require_rollout_observed: bool
    require_release_test: bool
    require_real_inference: bool


@dataclass(frozen=True, slots=True)
class FaultInjection:
    """The unhealthy candidate, and every property that keeps it reversible."""

    mechanism: str
    values_path: str
    injected_size_bytes: int
    fails_in_container: str
    fails_in_workload: str
    scope: str
    reversible_by: str
    accepted_by_chart_schema: bool
    reaches_pod_template: bool
    creates_no_object_outside_release: bool
    pulls_no_image: bool
    changes_no_image_reference: bool
    changes_no_cluster_scoped_object: bool
    changes_no_persistent_volume_claim: bool


@dataclass(frozen=True, slots=True)
class DetectionPolicy:
    """What counts as having found the failure, and what does not."""

    decisive_signals: tuple[str, ...]
    deadline_signal: str
    inconclusive_signals: tuple[str, ...]
    poll_interval_ms: int
    require_decisive_signal: bool
    require_injected_workload: bool


@dataclass(frozen=True, slots=True)
class RollbackPolicy:
    """What a rollback has to restore before it may be called one."""

    target: str
    require_configuration_restored: bool
    require_fault_removed: bool
    require_release_test: bool
    require_real_inference: bool
    require_revision_recorded: bool


@dataclass(frozen=True, slots=True)
class ImpactPlan:
    """What a caller was asked, how often, while the candidate was failing."""

    probe_path: str
    probe_interval_ms: int
    probe_timeout_ms: int
    minimum_probes: int
    require_probe_record: bool


@dataclass(frozen=True, slots=True)
class ExperimentBudgets:
    """Every bound this workflow applies.

    Eight of these are the certification's and are compared with it for equality.
    Four are this experiment's own: how long an upgrade may take, how long a
    failure may go undetected before a deadline is accepted as the answer, how
    long a rollback may take, and how long the whole recovery may take.
    """

    install_ms: int
    runtime_startup_ms: int
    runtime_rollout_ms: int
    api_startup_ms: int
    api_rollout_ms: int
    release_test_ms: int
    forward_ms: int
    uninstall_ms: int
    upgrade_ms: int
    failure_detection_ms: int
    rollback_ms: int
    recovery_ms: int


@dataclass(frozen=True, slots=True)
class Experiment:
    """The committed upgrade-and-rollback descriptor, after validation."""

    schema_version: str
    experiment_id: str
    evidence_class: str
    evidence_label: str
    certification_ceiling: str
    lane: str
    chart_ref: str
    certification_ref: str
    procedure_ref: str
    baseline_certification_ref: str
    cluster: ClusterTarget
    release: ReleaseTarget
    declared_stages: tuple[str, ...]
    requires_terraform_prerequisites: bool
    requires_target_cluster_assertion: bool
    requires_healthy_baseline: bool
    requires_verified_model_cache: bool
    candidate: CandidateChange
    fault: FaultInjection
    detection: DetectionPolicy
    rollback: RollbackPolicy
    impact: ImpactPlan
    request_host: str
    request_path: str
    models_path: str
    readiness_path: str
    prompt: str
    request_id_prefix: str
    correlation_id: str
    request_timeout_ms: int
    required_adapter_kind: str
    prohibited_identity_substring: str
    require_usage_counts: bool
    require_nonempty_content: bool
    require_pinned_model_revision: bool
    require_strictly_increasing_revisions: bool
    require_distinct_candidate_revision: bool
    require_every_replica_ready: bool
    require_pinned_node_image: bool
    require_recovery_recorded: bool
    budgets: ExperimentBudgets
    evidence_directory: Path
    result_file: str
    diagnostics_file: str
    lifecycle_file: str
    impact_file: str
    cleanup_file: str
    retain_generated_text: bool
    uninstalls_release: bool
    removes_prerequisites: bool
    removes_cluster: bool
    removes_model_cache_claim: bool
    limitations: tuple[str, ...]

    def artifact_path(self, member: str, repo_root: Path = REPO_ROOT) -> Path:
        """Where a collected document must be, rather than wherever it is.

        Derived rather than accepted as an argument for the same reason the
        certification derives its own: the cluster half of the record is copied
        out of these files, and a flag naming them would let a run reach a real
        release and describe an environment read from somewhere else.
        """
        return repo_root.resolve() / member

    def request_id(self, stage: str) -> str:
        """One request identifier per stage, so two answers cannot be one."""
        return f"{self.request_id_prefix}-{stage}"


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExperimentError(f"the descriptor member '{field}' is not an object")
    return cast(dict[str, Any], value)


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExperimentError(
            f"the descriptor member '{field}' is not a non-empty string"
        )
    return value


def _integer(value: Any, field: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ExperimentError(
            f"the descriptor member '{field}' is not an integer of at least {minimum}"
        )
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ExperimentError(f"the descriptor member '{field}' is not a boolean")
    return value


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ExperimentError(f"the descriptor member '{field}' names nothing")
    return tuple(_string(entry, f"{field}[]") for entry in value)


def _require_keys(record: Mapping[str, Any], field: str, expected: set[str]) -> None:
    """Refuse a section with an unknown member as firmly as a missing one.

    An unknown member is the shape a waived assertion takes: a safety flag
    renamed by one letter is silently ignored by a reader that only looks for the
    names it knows, and the run then proceeds without the rule.
    """
    if set(record) != expected:
        missing = sorted(expected - set(record))
        unknown = sorted(set(record) - expected)
        raise ExperimentError(
            f"the descriptor section '{field}' has missing or unsupported members: "
            f"missing {missing}, unsupported {unknown}"
        )


def _read_cluster(cluster: Mapping[str, Any]) -> ClusterTarget:
    _require_keys(cluster, "cluster", {"name", "context", "nodeImageDigest"})
    return ClusterTarget(
        name=_string(cluster.get("name"), "cluster.name"),
        context=_string(cluster.get("context"), "cluster.context"),
        node_image_digest=_string(
            cluster.get("nodeImageDigest"), "cluster.nodeImageDigest"
        ),
    )


def _read_release(release: Mapping[str, Any]) -> ReleaseTarget:
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
            "replicas",
        },
    )
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
        replicas=_integer(release.get("replicas"), "release.replicas"),
    )


def _read_candidate(candidate: Mapping[str, Any]) -> CandidateChange:
    _require_keys(
        candidate,
        "candidate",
        {
            "description",
            "valuesPath",
            "candidateValue",
            "configMapKey",
            "reachesPodTemplate",
            "requireRolloutObserved",
            "requireReleaseTest",
            "requireRealInference",
        },
    )
    _string(candidate.get("description"), "candidate.description")
    return CandidateChange(
        values_path=_string(candidate.get("valuesPath"), "candidate.valuesPath"),
        candidate_value=_string(
            candidate.get("candidateValue"), "candidate.candidateValue"
        ),
        config_map_key=_string(candidate.get("configMapKey"), "candidate.configMapKey"),
        reaches_pod_template=_boolean(
            candidate.get("reachesPodTemplate"), "candidate.reachesPodTemplate"
        ),
        require_rollout_observed=_boolean(
            candidate.get("requireRolloutObserved"), "candidate.requireRolloutObserved"
        ),
        require_release_test=_boolean(
            candidate.get("requireReleaseTest"), "candidate.requireReleaseTest"
        ),
        require_real_inference=_boolean(
            candidate.get("requireRealInference"), "candidate.requireRealInference"
        ),
    )


def _read_fault(fault: Mapping[str, Any]) -> FaultInjection:
    _require_keys(
        fault,
        "faultInjection",
        {
            "description",
            "mechanism",
            "valuesPath",
            "injectedSizeBytes",
            "failsInContainer",
            "failsInWorkload",
            "scope",
            "reversibleBy",
            "acceptedByChartSchema",
            "reachesPodTemplate",
            "createsNoObjectOutsideRelease",
            "pullsNoImage",
            "changesNoImageReference",
            "changesNoClusterScopedObject",
            "changesNoPersistentVolumeClaim",
        },
    )
    _string(fault.get("description"), "faultInjection.description")
    return FaultInjection(
        mechanism=_string(fault.get("mechanism"), "faultInjection.mechanism"),
        values_path=_string(fault.get("valuesPath"), "faultInjection.valuesPath"),
        injected_size_bytes=_integer(
            fault.get("injectedSizeBytes"),
            "faultInjection.injectedSizeBytes",
            minimum=MINIMUM_INJECTED_SIZE_BYTES,
        ),
        fails_in_container=_string(
            fault.get("failsInContainer"), "faultInjection.failsInContainer"
        ),
        fails_in_workload=_string(
            fault.get("failsInWorkload"), "faultInjection.failsInWorkload"
        ),
        scope=_string(fault.get("scope"), "faultInjection.scope"),
        reversible_by=_string(fault.get("reversibleBy"), "faultInjection.reversibleBy"),
        accepted_by_chart_schema=_boolean(
            fault.get("acceptedByChartSchema"), "faultInjection.acceptedByChartSchema"
        ),
        reaches_pod_template=_boolean(
            fault.get("reachesPodTemplate"), "faultInjection.reachesPodTemplate"
        ),
        creates_no_object_outside_release=_boolean(
            fault.get("createsNoObjectOutsideRelease"),
            "faultInjection.createsNoObjectOutsideRelease",
        ),
        pulls_no_image=_boolean(
            fault.get("pullsNoImage"), "faultInjection.pullsNoImage"
        ),
        changes_no_image_reference=_boolean(
            fault.get("changesNoImageReference"),
            "faultInjection.changesNoImageReference",
        ),
        changes_no_cluster_scoped_object=_boolean(
            fault.get("changesNoClusterScopedObject"),
            "faultInjection.changesNoClusterScopedObject",
        ),
        changes_no_persistent_volume_claim=_boolean(
            fault.get("changesNoPersistentVolumeClaim"),
            "faultInjection.changesNoPersistentVolumeClaim",
        ),
    )


def _read_detection(detection: Mapping[str, Any]) -> DetectionPolicy:
    _require_keys(
        detection,
        "detection",
        {
            "decisiveSignals",
            "deadlineSignal",
            "inconclusiveSignals",
            "pollIntervalMs",
            "requireDecisiveSignal",
            "requireInjectedWorkload",
        },
    )
    return DetectionPolicy(
        decisive_signals=_strings(
            detection.get("decisiveSignals"), "detection.decisiveSignals"
        ),
        deadline_signal=_string(
            detection.get("deadlineSignal"), "detection.deadlineSignal"
        ),
        inconclusive_signals=_strings(
            detection.get("inconclusiveSignals"), "detection.inconclusiveSignals"
        ),
        poll_interval_ms=_integer(
            detection.get("pollIntervalMs"), "detection.pollIntervalMs", minimum=1000
        ),
        require_decisive_signal=_boolean(
            detection.get("requireDecisiveSignal"), "detection.requireDecisiveSignal"
        ),
        require_injected_workload=_boolean(
            detection.get("requireInjectedWorkload"),
            "detection.requireInjectedWorkload",
        ),
    )


def _read_rollback(rollback: Mapping[str, Any]) -> RollbackPolicy:
    _require_keys(
        rollback,
        "rollback",
        {
            "target",
            "requireConfigurationRestored",
            "requireFaultRemoved",
            "requireReleaseTest",
            "requireRealInference",
            "requireRevisionRecorded",
        },
    )
    return RollbackPolicy(
        target=_string(rollback.get("target"), "rollback.target"),
        require_configuration_restored=_boolean(
            rollback.get("requireConfigurationRestored"),
            "rollback.requireConfigurationRestored",
        ),
        require_fault_removed=_boolean(
            rollback.get("requireFaultRemoved"), "rollback.requireFaultRemoved"
        ),
        require_release_test=_boolean(
            rollback.get("requireReleaseTest"), "rollback.requireReleaseTest"
        ),
        require_real_inference=_boolean(
            rollback.get("requireRealInference"), "rollback.requireRealInference"
        ),
        require_revision_recorded=_boolean(
            rollback.get("requireRevisionRecorded"), "rollback.requireRevisionRecorded"
        ),
    )


def _read_impact(impact: Mapping[str, Any]) -> ImpactPlan:
    _require_keys(
        impact,
        "impact",
        {
            "description",
            "probePath",
            "probeIntervalMs",
            "probeTimeoutMs",
            "minimumProbes",
            "requireProbeRecord",
        },
    )
    _string(impact.get("description"), "impact.description")
    return ImpactPlan(
        probe_path=_string(impact.get("probePath"), "impact.probePath"),
        probe_interval_ms=_integer(
            impact.get("probeIntervalMs"), "impact.probeIntervalMs", minimum=1000
        ),
        probe_timeout_ms=_integer(
            impact.get("probeTimeoutMs"), "impact.probeTimeoutMs", minimum=1000
        ),
        minimum_probes=_integer(
            impact.get("minimumProbes"), "impact.minimumProbes", minimum=3
        ),
        require_probe_record=_boolean(
            impact.get("requireProbeRecord"), "impact.requireProbeRecord"
        ),
    )


def _read_budgets(readiness: Mapping[str, Any]) -> ExperimentBudgets:
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
            "forwardBudgetMs",
            "upgradeBudgetMs",
            "failureDetectionBudgetMs",
            "rollbackBudgetMs",
            "recoveryBudgetMs",
            "uninstallBudgetMs",
        },
    )
    return ExperimentBudgets(
        install_ms=_integer(readiness.get("installBudgetMs"), "installBudgetMs"),
        runtime_startup_ms=_integer(
            readiness.get("runtimeStartupBudgetMs"), "runtimeStartupBudgetMs"
        ),
        runtime_rollout_ms=_integer(
            readiness.get("runtimeRolloutBudgetMs"), "runtimeRolloutBudgetMs"
        ),
        api_startup_ms=_integer(
            readiness.get("apiStartupBudgetMs"), "apiStartupBudgetMs"
        ),
        api_rollout_ms=_integer(
            readiness.get("apiRolloutBudgetMs"), "apiRolloutBudgetMs"
        ),
        release_test_ms=_integer(
            readiness.get("releaseTestBudgetMs"), "releaseTestBudgetMs"
        ),
        forward_ms=_integer(readiness.get("forwardBudgetMs"), "forwardBudgetMs"),
        uninstall_ms=_integer(readiness.get("uninstallBudgetMs"), "uninstallBudgetMs"),
        upgrade_ms=_integer(readiness.get("upgradeBudgetMs"), "upgradeBudgetMs"),
        failure_detection_ms=_integer(
            readiness.get("failureDetectionBudgetMs"), "failureDetectionBudgetMs"
        ),
        rollback_ms=_integer(readiness.get("rollbackBudgetMs"), "rollbackBudgetMs"),
        recovery_ms=_integer(readiness.get("recoveryBudgetMs"), "recoveryBudgetMs"),
    )


def load_experiment(
    path: Path = EXPERIMENT_PATH, *, baseline: Certification | None = None
) -> Experiment:
    """Load and cross-check the descriptor without performing any real I/O."""
    try:
        document = _object(json.loads(path.read_text(encoding="utf-8")), "root")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ExperimentError("the experiment descriptor is unreadable") from error

    _require_keys(
        document,
        "root",
        {
            "schemaVersion",
            "experimentId",
            "evidenceClass",
            "evidenceLabel",
            "certificationCeiling",
            "lane",
            "chartRef",
            "certificationRef",
            "procedureRef",
            "baselineCertificationRef",
            "cluster",
            "release",
            "prerequisites",
            "stages",
            "candidate",
            "faultInjection",
            "detection",
            "rollback",
            "impact",
            "request",
            "assertions",
            "readiness",
            "evidence",
            "cleanup",
            "limitations",
        },
    )

    prerequisites = _object(document.get("prerequisites"), "prerequisites")
    _require_keys(
        prerequisites,
        "prerequisites",
        {
            "requiresTerraformPrerequisites",
            "requiresTargetClusterAssertion",
            "requiresHealthyBaseline",
            "requiresVerifiedModelCache",
        },
    )
    request = _object(document.get("request"), "request")
    _require_keys(
        request,
        "request",
        {
            "host",
            "path",
            "modelsPath",
            "readinessPath",
            "prompt",
            "requestIdPrefix",
            "correlationId",
            "timeoutMs",
        },
    )
    assertions = _object(document.get("assertions"), "assertions")
    _require_keys(
        assertions,
        "assertions",
        {
            "requiredAdapterKind",
            "prohibitedIdentitySubstring",
            "requireUsageCounts",
            "requireNonEmptyContent",
            "requirePinnedModelRevision",
            "requireStrictlyIncreasingRevisions",
            "requireDistinctCandidateRevision",
            "requireEveryReplicaReady",
            "requirePinnedNodeImage",
            "requireRecoveryRecorded",
        },
    )
    evidence = _object(document.get("evidence"), "evidence")
    _require_keys(
        evidence,
        "evidence",
        {
            "directory",
            "resultFile",
            "diagnosticsFile",
            "lifecycleFile",
            "impactFile",
            "cleanupFile",
            "retainGeneratedText",
        },
    )
    cleanup = _object(document.get("cleanup"), "cleanup")
    _require_keys(
        cleanup,
        "cleanup",
        {
            "uninstallsRelease",
            "removesPrerequisites",
            "removesCluster",
            "removesModelCacheClaim",
        },
    )

    experiment = Experiment(
        schema_version=_string(document.get("schemaVersion"), "schemaVersion"),
        experiment_id=_string(document.get("experimentId"), "experimentId"),
        evidence_class=_string(document.get("evidenceClass"), "evidenceClass"),
        evidence_label=_string(document.get("evidenceLabel"), "evidenceLabel"),
        certification_ceiling=_string(
            document.get("certificationCeiling"), "certificationCeiling"
        ),
        lane=_string(document.get("lane"), "lane"),
        chart_ref=_string(document.get("chartRef"), "chartRef"),
        certification_ref=_string(document.get("certificationRef"), "certificationRef"),
        procedure_ref=_string(document.get("procedureRef"), "procedureRef"),
        baseline_certification_ref=_string(
            document.get("baselineCertificationRef"), "baselineCertificationRef"
        ),
        cluster=_read_cluster(_object(document.get("cluster"), "cluster")),
        release=_read_release(_object(document.get("release"), "release")),
        declared_stages=_strings(document.get("stages"), "stages"),
        requires_terraform_prerequisites=_boolean(
            prerequisites.get("requiresTerraformPrerequisites"),
            "requiresTerraformPrerequisites",
        ),
        requires_target_cluster_assertion=_boolean(
            prerequisites.get("requiresTargetClusterAssertion"),
            "requiresTargetClusterAssertion",
        ),
        requires_healthy_baseline=_boolean(
            prerequisites.get("requiresHealthyBaseline"), "requiresHealthyBaseline"
        ),
        requires_verified_model_cache=_boolean(
            prerequisites.get("requiresVerifiedModelCache"),
            "requiresVerifiedModelCache",
        ),
        candidate=_read_candidate(_object(document.get("candidate"), "candidate")),
        fault=_read_fault(_object(document.get("faultInjection"), "faultInjection")),
        detection=_read_detection(_object(document.get("detection"), "detection")),
        rollback=_read_rollback(_object(document.get("rollback"), "rollback")),
        impact=_read_impact(_object(document.get("impact"), "impact")),
        request_host=_string(request.get("host"), "request.host"),
        request_path=_string(request.get("path"), "request.path"),
        models_path=_string(request.get("modelsPath"), "request.modelsPath"),
        readiness_path=_string(request.get("readinessPath"), "request.readinessPath"),
        prompt=_string(request.get("prompt"), "request.prompt"),
        request_id_prefix=_string(
            request.get("requestIdPrefix"), "request.requestIdPrefix"
        ),
        correlation_id=_string(request.get("correlationId"), "request.correlationId"),
        request_timeout_ms=_integer(request.get("timeoutMs"), "request.timeoutMs"),
        required_adapter_kind=_string(
            assertions.get("requiredAdapterKind"), "requiredAdapterKind"
        ),
        prohibited_identity_substring=_string(
            assertions.get("prohibitedIdentitySubstring"),
            "prohibitedIdentitySubstring",
        ),
        require_usage_counts=_boolean(
            assertions.get("requireUsageCounts"), "requireUsageCounts"
        ),
        require_nonempty_content=_boolean(
            assertions.get("requireNonEmptyContent"), "requireNonEmptyContent"
        ),
        require_pinned_model_revision=_boolean(
            assertions.get("requirePinnedModelRevision"), "requirePinnedModelRevision"
        ),
        require_strictly_increasing_revisions=_boolean(
            assertions.get("requireStrictlyIncreasingRevisions"),
            "requireStrictlyIncreasingRevisions",
        ),
        require_distinct_candidate_revision=_boolean(
            assertions.get("requireDistinctCandidateRevision"),
            "requireDistinctCandidateRevision",
        ),
        require_every_replica_ready=_boolean(
            assertions.get("requireEveryReplicaReady"), "requireEveryReplicaReady"
        ),
        require_pinned_node_image=_boolean(
            assertions.get("requirePinnedNodeImage"), "requirePinnedNodeImage"
        ),
        require_recovery_recorded=_boolean(
            assertions.get("requireRecoveryRecorded"), "requireRecoveryRecorded"
        ),
        budgets=_read_budgets(_object(document.get("readiness"), "readiness")),
        evidence_directory=Path(_string(evidence.get("directory"), "directory")),
        result_file=_string(evidence.get("resultFile"), "resultFile"),
        diagnostics_file=_string(evidence.get("diagnosticsFile"), "diagnosticsFile"),
        lifecycle_file=_string(evidence.get("lifecycleFile"), "lifecycleFile"),
        impact_file=_string(evidence.get("impactFile"), "impactFile"),
        cleanup_file=_string(evidence.get("cleanupFile"), "cleanupFile"),
        retain_generated_text=_boolean(
            evidence.get("retainGeneratedText"), "retainGeneratedText"
        ),
        uninstalls_release=_boolean(
            cleanup.get("uninstallsRelease"), "uninstallsRelease"
        ),
        removes_prerequisites=_boolean(
            cleanup.get("removesPrerequisites"), "removesPrerequisites"
        ),
        removes_cluster=_boolean(cleanup.get("removesCluster"), "removesCluster"),
        removes_model_cache_claim=_boolean(
            cleanup.get("removesModelCacheClaim"), "removesModelCacheClaim"
        ),
        limitations=_strings(document.get("limitations"), "limitations"),
    )
    _validate(experiment, baseline if baseline is not None else load_certification())
    return experiment


# -- what the descriptor may not say -----------------------------------------


def _validate_identity(experiment: Experiment) -> None:
    if (
        experiment.schema_version != EXPECTED_SCHEMA
        or experiment.experiment_id != EXPECTED_ID
        or experiment.evidence_class != EXPECTED_EVIDENCE_CLASS
        or experiment.evidence_label != EXPECTED_EVIDENCE_LABEL
        or experiment.certification_ceiling != EXPECTED_CERTIFICATION_CEILING
        or experiment.lane != EXPECTED_LANE
        or experiment.chart_ref != EXPECTED_CHART_REF
        or experiment.certification_ref != EXPECTED_CERTIFICATION_REF
        or experiment.procedure_ref != EXPECTED_PROCEDURE_REF
        or experiment.baseline_certification_ref != EXPECTED_BASELINE_REF
    ):
        raise ExperimentError("the experiment descriptor does not identify itself")
    if experiment.declared_stages != DECLARED_STAGES:
        raise ExperimentError(
            "the experiment declares stages other than "
            f"{list(DECLARED_STAGES)}, so the descriptor and the procedure "
            "describe different experiments"
        )
    if len(experiment.limitations) < 4:
        raise ExperimentError(
            "the experiment states fewer than four limitations. A local single-node "
            "upgrade experiment that names none is read as one that has none"
        )


def _validate_against_baseline(experiment: Experiment, baseline: Certification) -> None:
    """Refuse a descriptor that disagrees with the certification it builds on.

    Equality rather than a field-by-field re-derivation. The two descriptors
    describe one release on one cluster reached through one forward, and the
    failure this prevents is the quiet one: an experiment that installed into a
    namespace, or waited on a Deployment, or forwarded to a Service, that the
    certified workflow does not know about — and then reported a rollback of
    "the release".
    """
    if experiment.cluster != baseline.cluster:
        raise ExperimentError(
            "the experiment and the Kubernetes certification describe different "
            "clusters"
        )
    if experiment.release != baseline.release:
        raise ExperimentError(
            "the experiment and the Kubernetes certification describe different "
            "releases"
        )
    if (
        experiment.request_host != baseline.request_host
        or experiment.request_path != baseline.request_path
        or experiment.models_path != baseline.models_path
        or experiment.readiness_path != baseline.readiness_path
        or experiment.request_timeout_ms != baseline.request_timeout_ms
        or experiment.required_adapter_kind != baseline.required_adapter_kind
        or experiment.prohibited_identity_substring
        != baseline.prohibited_identity_substring
    ):
        raise ExperimentError(
            "the experiment reads the release differently from the certification "
            "that already decided how it is read"
        )
    shared = (
        (experiment.budgets.install_ms, baseline.budgets.install_ms),
        (experiment.budgets.runtime_startup_ms, baseline.budgets.runtime_startup_ms),
        (experiment.budgets.runtime_rollout_ms, baseline.budgets.runtime_rollout_ms),
        (experiment.budgets.api_startup_ms, baseline.budgets.api_startup_ms),
        (experiment.budgets.api_rollout_ms, baseline.budgets.api_rollout_ms),
        (experiment.budgets.release_test_ms, baseline.budgets.release_test_ms),
        (experiment.budgets.forward_ms, baseline.budgets.forward_ms),
        (experiment.budgets.uninstall_ms, baseline.budgets.uninstall_ms),
    )
    if any(mine != theirs for mine, theirs in shared):
        raise ExperimentError(
            "the experiment applies a different budget from the certification to "
            "the same wait"
        )
    if (
        experiment.result_file == baseline.result_file
        or experiment.diagnostics_file == baseline.diagnostics_file
        or experiment.lifecycle_file == baseline.facts_file
    ):
        raise ExperimentError(
            "the experiment would write over the certification's own record"
        )


def _validate_candidate(experiment: Experiment) -> None:
    candidate = experiment.candidate
    if (
        candidate.values_path != CANDIDATE_VALUES_PATH
        or candidate.config_map_key != CANDIDATE_CONFIG_MAP_KEY
    ):
        raise ExperimentError(
            "the controlled change must be "
            f"'{CANDIDATE_VALUES_PATH}', arriving at '{CANDIDATE_CONFIG_MAP_KEY}'. "
            "A value outside the chart's derived environment leaves the pod "
            "template's checksum untouched, so the upgrade would roll nothing and "
            "the rollback would restore nothing"
        )
    if not SAFE_VALUE.match(candidate.candidate_value):
        raise ExperimentError(
            "the candidate value is not a plain identifier. It is interpolated "
            "into a command line and printed into the record"
        )
    if not (
        candidate.reaches_pod_template
        and candidate.require_rollout_observed
        and candidate.require_release_test
        and candidate.require_real_inference
    ):
        raise ExperimentError(
            "a controlled candidate may not waive the rollout, the release test, "
            "or the real completion that establishes it is still serving"
        )


def _validate_fault(experiment: Experiment) -> None:
    fault = experiment.fault
    if fault.mechanism != FAULT_MECHANISM or fault.values_path != FAULT_VALUES_PATH:
        raise ExperimentError(
            f"the only fault this experiment may inject is '{FAULT_MECHANISM}' "
            f"through '{FAULT_VALUES_PATH}'"
        )
    if (
        fault.fails_in_container != FAULT_CONTAINER
        or fault.fails_in_workload != FAULT_WORKLOAD
    ):
        raise ExperimentError(
            "the injected fault must be declared to fail in the "
            f"'{FAULT_CONTAINER}' init container of the '{FAULT_WORKLOAD}' "
            "workload, which is where the chart compares the artifact"
        )
    if fault.scope != FAULT_SCOPE or fault.reversible_by != FAULT_REVERSED_BY:
        raise ExperimentError(
            "the injected fault must be scoped to the release and removable by a "
            "rollback. A fault removed by a second edit is a fault the rollback "
            "was not asked to reverse"
        )
    manifest = load_manifest()
    if fault.injected_size_bytes == manifest.expected_size_bytes:
        raise ExperimentError(
            "the injected byte count is the artifact's real one, so the candidate "
            "it produces is healthy and nothing would be detected"
        )
    if not (
        fault.accepted_by_chart_schema
        and fault.reaches_pod_template
        and fault.creates_no_object_outside_release
        and fault.pulls_no_image
        and fault.changes_no_image_reference
        and fault.changes_no_cluster_scoped_object
        and fault.changes_no_persistent_volume_claim
    ):
        raise ExperimentError(
            "the injected fault does not declare every property that keeps it "
            "reversible and local to this release"
        )


def _validate_detection(experiment: Experiment) -> None:
    detection = experiment.detection
    if detection.decisive_signals != DECISIVE_SIGNALS:
        raise ExperimentError(
            "the decisive detection signals must be exactly "
            f"{list(DECISIVE_SIGNALS)}. A signal this module cannot read is a "
            "detection nobody checked"
        )
    if detection.deadline_signal != DEADLINE_SIGNAL:
        raise ExperimentError(f"the deadline signal must be '{DEADLINE_SIGNAL}'")
    if detection.inconclusive_signals != INCONCLUSIVE_SIGNALS:
        raise ExperimentError(
            f"the inconclusive signals must be exactly {list(INCONCLUSIVE_SIGNALS)}"
        )
    if not (detection.require_decisive_signal and detection.require_injected_workload):
        raise ExperimentError(
            "a run may not accept a failure it did not read off the workload it "
            "injected the fault into"
        )
    if detection.poll_interval_ms > experiment.budgets.failure_detection_ms:
        raise ExperimentError(
            "the detection poll interval is longer than the detection budget, so "
            "the budget could expire before anything was asked"
        )


def _validate_rollback(experiment: Experiment) -> None:
    rollback = experiment.rollback
    if rollback.target != "last-known-good-revision":
        raise ExperimentError(
            "the rollback target must be the last known-good revision. A fixed "
            "revision one would restore the release before the controlled change "
            "as well, and the record could not tell the two apart"
        )
    if not (
        rollback.require_configuration_restored
        and rollback.require_fault_removed
        and rollback.require_release_test
        and rollback.require_real_inference
        and rollback.require_revision_recorded
    ):
        raise ExperimentError(
            "a rollback may not be called one on Helm's bookkeeping alone: the "
            "rendered configuration, the removal of the fault, the release test, "
            "and a real completion are each a separate question"
        )


def _validate_impact(experiment: Experiment) -> None:
    impact = experiment.impact
    if impact.probe_path != experiment.readiness_path:
        raise ExperimentError(
            "the impact probe must ask the release's own readiness path, which is "
            "the answer a caller in front of the Service would get"
        )
    if impact.probe_timeout_ms > impact.probe_interval_ms:
        raise ExperimentError(
            "the impact probe timeout may outlive its interval, which produces "
            "overlapping probes of one endpoint rather than a sample per interval"
        )
    if not impact.require_probe_record:
        raise ExperimentError(
            "an experiment that reports user impact must record what it asked"
        )


def _validate_budgets(experiment: Experiment) -> None:
    budgets = experiment.budgets
    if budgets.upgrade_ms < budgets.runtime_rollout_ms:
        raise ExperimentError(
            "the upgrade budget is shorter than the runtime rollout it contains, "
            "so a healthy candidate loading a model would be reported as a failed "
            "upgrade"
        )
    if budgets.failure_detection_ms < budgets.runtime_rollout_ms:
        raise ExperimentError(
            "the failure detection budget is shorter than a healthy rollout, so a "
            "slow start would be recorded as a detected failure. A deadline is a "
            "statement about time, and it may not be reached before the time a "
            "healthy release is allowed"
        )
    if budgets.rollback_ms < budgets.runtime_rollout_ms:
        raise ExperimentError(
            "the rollback budget is shorter than the rollout it may have to perform"
        )
    if budgets.recovery_ms < (
        budgets.rollback_ms + budgets.release_test_ms + experiment.request_timeout_ms
    ):
        raise ExperimentError(
            "the recovery budget cannot contain the rollback, the release test, "
            "and the completion it is measured across"
        )


def _validate_evidence(experiment: Experiment) -> None:
    if (
        experiment.evidence_directory != EXPECTED_EVIDENCE_DIRECTORY
        or experiment.lifecycle_file != EXPECTED_LIFECYCLE_FILE
        or experiment.impact_file != EXPECTED_IMPACT_FILE
        or experiment.cleanup_file != EXPECTED_CLEANUP_FILE
        or experiment.retain_generated_text
        or Path(experiment.result_file).name != experiment.result_file
        or Path(experiment.diagnostics_file).name != experiment.diagnostics_file
        or experiment.result_file == experiment.diagnostics_file
        or len(
            {
                experiment.lifecycle_file,
                experiment.impact_file,
                experiment.cleanup_file,
            }
        )
        != 3
    ):
        raise ExperimentError("the experiment evidence location is unsafe")


def _validate_cleanup(experiment: Experiment) -> None:
    if not experiment.uninstalls_release:
        raise ExperimentError("the experiment must remove the release it installed")
    if (
        experiment.removes_prerequisites
        or experiment.removes_cluster
        or experiment.removes_model_cache_claim
    ):
        raise ExperimentError(
            "the experiment may remove neither the prerequisites, the cluster, nor "
            "the model cache claim. Each outlives a release by design"
        )


def _validate(experiment: Experiment, baseline: Certification) -> None:
    """Refuse a descriptor that disagrees with any record already deciding it."""
    _validate_identity(experiment)
    _validate_against_baseline(experiment, baseline)
    _validate_candidate(experiment)
    _validate_fault(experiment)
    _validate_detection(experiment)
    _validate_rollback(experiment)
    _validate_impact(experiment)
    _validate_budgets(experiment)
    _validate_evidence(experiment)
    _validate_cleanup(experiment)
    if not (
        experiment.requires_terraform_prerequisites
        and experiment.requires_target_cluster_assertion
        and experiment.requires_healthy_baseline
        and experiment.requires_verified_model_cache
    ):
        raise ExperimentError("a prerequisite of this experiment cannot be waived")
    if not (
        experiment.require_usage_counts
        and experiment.require_nonempty_content
        and experiment.require_pinned_model_revision
        and experiment.require_strictly_increasing_revisions
        and experiment.require_distinct_candidate_revision
        and experiment.require_every_replica_ready
        and experiment.require_pinned_node_image
        and experiment.require_recovery_recorded
    ):
        raise ExperimentError("an assertion of this experiment cannot be waived")


# -- reading what the operating script collected -----------------------------


class _Facts:
    """A reader over one collected document, refusing at a named stage."""

    def __init__(self, stage: str) -> None:
        self.stage = stage

    def fail(self, message: str) -> ExperimentFailed:
        return ExperimentFailed(message, self.stage)

    def object(self, value: Any, field: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise self.fail(f"the collected member '{field}' is not an object")
        return cast(dict[str, Any], value)

    def string(self, value: Any, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise self.fail(f"the collected member '{field}' is not a non-empty string")
        return value

    def optional_string(self, value: Any, field: str) -> str:
        """A member that is allowed to be empty, and never allowed to be absent.

        `telemetry.serviceVersion` is empty in the shipped chart and in the
        baseline stage, and the difference between "the release published no
        version" and "nobody collected one" is exactly what the candidate
        assertion turns on. Absent is refused; empty is a value.
        """
        if not isinstance(value, str):
            raise self.fail(f"the collected member '{field}' is not a string")
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
class StageFacts:
    """One revision of the release, as the cluster reported it."""

    stage: str
    revision: int
    status: str
    outcome: str
    service_version: str
    artifact_size_bytes: int
    elapsed_ms: int
    ready_ms: int
    release_test_passed: bool
    runtime_pod: str
    api_pod: str


@dataclass(frozen=True, slots=True)
class DetectionFacts:
    """How the unhealthy candidate was found, and on what evidence."""

    signal: str
    workload: str
    container: str
    exit_code: int
    reason: str
    detected_after_ms: int
    candidate_pod: str
    serving_pod: str


@dataclass(frozen=True, slots=True)
class RecoveryFacts:
    """The clock across the recovery, in milliseconds from the injection."""

    injected_at_ms: int
    detected_at_ms: int
    rollback_started_at_ms: int
    rollback_finished_at_ms: int
    verified_at_ms: int

    @property
    def detection_ms(self) -> int:
        return self.detected_at_ms - self.injected_at_ms

    @property
    def rollback_ms(self) -> int:
        return self.rollback_finished_at_ms - self.rollback_started_at_ms

    @property
    def recovery_ms(self) -> int:
        """Detection to a served completion. The figure this experiment owes."""
        return self.verified_at_ms - self.detected_at_ms


@dataclass(frozen=True, slots=True)
class LifecycleFacts:
    """Everything the operating script measured, after this module checked it."""

    cluster_name: str
    kube_context: str
    server_version: str
    node_image_digest: str
    helm_version: str
    kubectl_version: str
    release_name: str
    release_namespace: str
    chart_version: str
    profile: str
    model_identifier: str
    model_revision: str
    deployment_environment: str
    stages: tuple[StageFacts, ...]
    detection: DetectionFacts
    recovery: RecoveryFacts

    def stage(self, name: str) -> StageFacts:
        for entry in self.stages:
            if entry.stage == name:
                return entry
        raise ExperimentFailed(
            f"the collected lifecycle facts describe no '{name}' stage", STAGE_LOAD
        )


def _stage(reader: _Facts, entry: Any, index: int) -> StageFacts:
    record = reader.object(entry, f"stages[{index}]")
    field = f"stages[{index}]"
    stage = reader.string(record.get("stage"), f"{field}.stage")
    outcome = reader.string(record.get("outcome"), f"{field}.outcome")
    if outcome not in OUTCOMES:
        raise reader.fail(
            f"the collected member '{field}.outcome' is '{outcome}', which is not "
            f"one of {list(OUTCOMES)}"
        )
    return StageFacts(
        stage=stage,
        revision=reader.integer(record.get("revision"), f"{field}.revision", minimum=1),
        status=reader.string(record.get("status"), f"{field}.status"),
        outcome=outcome,
        service_version=reader.optional_string(
            record.get("serviceVersion"), f"{field}.serviceVersion"
        ),
        artifact_size_bytes=reader.integer(
            record.get("artifactSizeBytes"), f"{field}.artifactSizeBytes", minimum=0
        ),
        elapsed_ms=reader.integer(record.get("elapsedMs"), f"{field}.elapsedMs"),
        ready_ms=reader.integer(record.get("readyMs"), f"{field}.readyMs"),
        release_test_passed=reader.boolean(
            record.get("releaseTestPassed"), f"{field}.releaseTestPassed"
        ),
        runtime_pod=reader.optional_string(
            record.get("runtimePod"), f"{field}.runtimePod"
        ),
        api_pod=reader.optional_string(record.get("apiPod"), f"{field}.apiPod"),
    )


def load_lifecycle_facts(
    experiment: Experiment, *, repo_root: Path = REPO_ROOT
) -> LifecycleFacts:
    """Read what the script measured across the four revisions, untrusted."""
    reader = _Facts(STAGE_LOAD)
    document = reader.document(
        experiment.artifact_path(experiment.lifecycle_file, repo_root),
        "lifecycle facts",
    )
    cluster = reader.object(document.get("cluster"), "cluster")
    tooling = reader.object(document.get("tooling"), "tooling")
    release = reader.object(document.get("release"), "release")
    configuration = reader.object(document.get("configuration"), "configuration")
    detection = reader.object(document.get("detection"), "detection")
    recovery = reader.object(document.get("recovery"), "recovery")
    stages = tuple(
        _stage(reader, entry, index)
        for index, entry in enumerate(reader.entries(document.get("stages"), "stages"))
    )
    return LifecycleFacts(
        cluster_name=reader.string(cluster.get("name"), "cluster.name"),
        kube_context=reader.string(cluster.get("context"), "cluster.context"),
        server_version=reader.string(
            cluster.get("serverVersion"), "cluster.serverVersion"
        ),
        node_image_digest=reader.optional_string(
            cluster.get("nodeImageDigest"), "cluster.nodeImageDigest"
        ),
        helm_version=reader.string(tooling.get("helm"), "tooling.helm"),
        kubectl_version=reader.string(tooling.get("kubectl"), "tooling.kubectl"),
        release_name=reader.string(release.get("name"), "release.name"),
        release_namespace=reader.string(release.get("namespace"), "release.namespace"),
        chart_version=reader.string(release.get("chart"), "release.chart"),
        profile=reader.string(release.get("profile"), "release.profile"),
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
        stages=stages,
        detection=DetectionFacts(
            signal=reader.string(detection.get("signal"), "detection.signal"),
            workload=reader.string(detection.get("workload"), "detection.workload"),
            container=reader.string(detection.get("container"), "detection.container"),
            exit_code=reader.integer(
                detection.get("exitCode"), "detection.exitCode", minimum=0
            ),
            reason=reader.string(detection.get("reason"), "detection.reason"),
            detected_after_ms=reader.integer(
                detection.get("detectedAfterMs"), "detection.detectedAfterMs"
            ),
            candidate_pod=reader.string(
                detection.get("candidatePod"), "detection.candidatePod"
            ),
            serving_pod=reader.string(
                detection.get("servingPod"), "detection.servingPod"
            ),
        ),
        recovery=RecoveryFacts(
            injected_at_ms=reader.integer(
                recovery.get("injectedAtMs"), "recovery.injectedAtMs"
            ),
            detected_at_ms=reader.integer(
                recovery.get("detectedAtMs"), "recovery.detectedAtMs"
            ),
            rollback_started_at_ms=reader.integer(
                recovery.get("rollbackStartedAtMs"), "recovery.rollbackStartedAtMs"
            ),
            rollback_finished_at_ms=reader.integer(
                recovery.get("rollbackFinishedAtMs"), "recovery.rollbackFinishedAtMs"
            ),
            verified_at_ms=reader.integer(
                recovery.get("verifiedAtMs"), "recovery.verifiedAtMs"
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class ImpactProbe:
    """One readiness answer, and when it was asked."""

    at_ms: int
    status: int
    ok: bool


@dataclass(frozen=True, slots=True)
class ImpactObservations:
    """What a caller saw while the unhealthy candidate was rolling out."""

    probe_path: str
    window_started_ms: int
    window_ended_ms: int
    probes: tuple[ImpactProbe, ...]

    @property
    def answered(self) -> int:
        return sum(1 for probe in self.probes if probe.ok)

    @property
    def refused(self) -> int:
        return len(self.probes) - self.answered

    @property
    def first_failure_at_ms(self) -> int | None:
        for probe in self.probes:
            if not probe.ok:
                return probe.at_ms
        return None


def load_impact_observations(
    experiment: Experiment, *, repo_root: Path = REPO_ROOT
) -> ImpactObservations:
    """Read the probe record the script kept across the failure window."""
    reader = _Facts(STAGE_IMPACT)
    document = reader.document(
        experiment.artifact_path(experiment.impact_file, repo_root),
        "impact observations",
    )
    window = reader.object(document.get("window"), "window")
    probes: list[ImpactProbe] = []
    for index, entry in enumerate(reader.entries(document.get("probes"), "probes")):
        record = reader.object(entry, f"probes[{index}]")
        probes.append(
            ImpactProbe(
                at_ms=reader.integer(record.get("atMs"), f"probes[{index}].atMs"),
                status=reader.integer(
                    record.get("status"), f"probes[{index}].status", minimum=0
                ),
                ok=reader.boolean(record.get("ok"), f"probes[{index}].ok"),
            )
        )
    return ImpactObservations(
        probe_path=reader.string(document.get("probePath"), "probePath"),
        window_started_ms=reader.integer(window.get("startedMs"), "window.startedMs"),
        window_ended_ms=reader.integer(window.get("endedMs"), "window.endedMs"),
        probes=tuple(probes),
    )


@dataclass(frozen=True, slots=True)
class CleanupFacts:
    """What the uninstall removed, and what it had to leave."""

    uninstall_ms: int
    release_objects_remaining: int
    helm_release_present: bool
    namespace_present: bool
    claims_before: int
    claims_after: int


def load_cleanup_facts(
    experiment: Experiment, *, repo_root: Path = REPO_ROOT
) -> CleanupFacts:
    """Read what survived the uninstall, untrusted."""
    reader = _Facts(STAGE_CLEANUP)
    document = reader.document(
        experiment.artifact_path(experiment.cleanup_file, repo_root), "cleanup facts"
    )
    return CleanupFacts(
        uninstall_ms=reader.integer(document.get("uninstallMs"), "uninstallMs"),
        release_objects_remaining=reader.integer(
            document.get("releaseObjectsRemaining"), "releaseObjectsRemaining"
        ),
        helm_release_present=reader.boolean(
            document.get("helmReleasePresent"), "helmReleasePresent"
        ),
        namespace_present=reader.boolean(
            document.get("namespacePresent"), "namespacePresent"
        ),
        claims_before=reader.integer(document.get("claimsBefore"), "claimsBefore"),
        claims_after=reader.integer(document.get("claimsAfter"), "claimsAfter"),
    )


# -- what the collected facts have to say ------------------------------------


def _check_environment(experiment: Experiment, facts: LifecycleFacts) -> None:
    if (
        facts.cluster_name != experiment.cluster.name
        or facts.kube_context != experiment.cluster.context
    ):
        raise ExperimentFailed(
            f"the collected facts describe cluster '{facts.cluster_name}' on "
            f"context '{facts.kube_context}', not this project's",
            STAGE_PREREQUISITES,
        )
    if (
        experiment.require_pinned_node_image
        and facts.node_image_digest != experiment.cluster.node_image_digest
    ):
        raise ExperimentFailed(
            "the cluster is not running the pinned node image, so the environment "
            "this record would describe is not the accepted one",
            STAGE_PREREQUISITES,
        )
    if (
        facts.release_name != experiment.release.name
        or facts.release_namespace != experiment.release.namespace
        or facts.profile != experiment.release.profile
    ):
        raise ExperimentFailed(
            "the collected facts describe another release, another namespace, or "
            "another serving profile",
            STAGE_PREREQUISITES,
        )
    manifest = load_manifest()
    if (
        experiment.require_pinned_model_revision
        and facts.model_revision != manifest.revision
    ):
        raise ExperimentFailed(
            "the installed release does not name the pinned model revision",
            STAGE_PREREQUISITES,
        )


def _check_stage_shape(experiment: Experiment, facts: LifecycleFacts) -> None:
    collected = tuple(stage.stage for stage in facts.stages)
    expected = ("baseline", "candidate", "unhealthy-candidate", "rollback")
    if collected != expected:
        raise ExperimentFailed(
            f"the collected facts describe stages {list(collected)} rather than "
            f"{list(expected)}",
            STAGE_LOAD,
        )
    if experiment.require_strictly_increasing_revisions:
        revisions = [stage.revision for stage in facts.stages]
        if any(later <= earlier for earlier, later in pairwise(revisions)):
            raise ExperimentFailed(
                f"the recorded revisions {revisions} do not increase. A rollback "
                "is a new revision restoring an old one, never a return to it",
                STAGE_ROLLBACK,
            )


def _check_baseline(experiment: Experiment, facts: LifecycleFacts) -> None:
    baseline = facts.stage("baseline")
    manifest = load_manifest()
    if baseline.outcome != OUTCOME_HEALTHY or not baseline.release_test_passed:
        raise ExperimentFailed(
            "the known-good release was not healthy before anything was upgraded, "
            "so nothing that follows is an upgrade from a known-good state",
            STAGE_BASELINE,
        )
    if baseline.artifact_size_bytes != manifest.expected_size_bytes:
        raise ExperimentFailed(
            "the known-good release did not declare the pinned artifact byte "
            "count, so the fault injected later is not a change from the pin",
            STAGE_BASELINE,
        )
    if baseline.service_version == experiment.candidate.candidate_value:
        raise ExperimentFailed(
            "the known-good release already carries the candidate value, so the "
            "upgrade would change nothing and its rollout would prove nothing",
            STAGE_BASELINE,
        )
    if baseline.ready_ms > experiment.budgets.runtime_rollout_ms:
        raise ExperimentFailed(
            f"the known-good release became ready in {baseline.ready_ms} ms, over "
            f"the {experiment.budgets.runtime_rollout_ms} ms rollout budget",
            STAGE_BASELINE,
        )


def _check_candidate(experiment: Experiment, facts: LifecycleFacts) -> None:
    baseline = facts.stage("baseline")
    candidate = facts.stage("candidate")
    if candidate.outcome != OUTCOME_HEALTHY:
        raise ExperimentFailed(
            "the controlled candidate did not become healthy, so this run has no "
            "known-good revision to roll back to",
            STAGE_CANDIDATE,
        )
    if candidate.service_version != experiment.candidate.candidate_value:
        raise ExperimentFailed(
            "the controlled change did not reach the rendered configuration: "
            f"expected '{experiment.candidate.candidate_value}', found "
            f"'{candidate.service_version}'. A revision Helm recorded and the "
            "cluster never applied is not an upgrade",
            STAGE_CANDIDATE,
        )
    if experiment.candidate.require_release_test and not candidate.release_test_passed:
        raise ExperimentFailed(
            "the controlled candidate did not pass the release's own test",
            STAGE_CANDIDATE,
        )
    if (
        experiment.candidate.require_rollout_observed
        and candidate.runtime_pod == baseline.runtime_pod
    ):
        raise ExperimentFailed(
            "the controlled candidate is served by the same pod as the known-good "
            "release, so the change reached the ConfigMap and not the workload",
            STAGE_CANDIDATE,
        )
    if candidate.elapsed_ms > experiment.budgets.upgrade_ms:
        raise ExperimentFailed(
            f"the controlled upgrade took {candidate.elapsed_ms} ms, over the "
            f"{experiment.budgets.upgrade_ms} ms budget",
            STAGE_CANDIDATE,
        )


def _check_unhealthy_candidate(experiment: Experiment, facts: LifecycleFacts) -> None:
    unhealthy = facts.stage("unhealthy-candidate")
    if unhealthy.outcome != OUTCOME_FAILED:
        raise ExperimentFailed(
            "the injected fault produced a healthy candidate. Either it was not "
            "applied or it is not a fault, and either way nothing was detected",
            STAGE_FAULT,
        )
    if unhealthy.artifact_size_bytes != experiment.fault.injected_size_bytes:
        raise ExperimentFailed(
            "the unhealthy candidate does not carry the declared injected byte "
            f"count: expected {experiment.fault.injected_size_bytes}, found "
            f"{unhealthy.artifact_size_bytes}",
            STAGE_FAULT,
        )
    if unhealthy.release_test_passed:
        raise ExperimentFailed(
            "the release test passed against a candidate this run recorded as "
            "failed. One of the two observations is wrong",
            STAGE_FAULT,
        )


def _check_detection(experiment: Experiment, facts: LifecycleFacts) -> None:
    detection = facts.detection
    unhealthy = facts.stage("unhealthy-candidate")
    if detection.signal in experiment.detection.inconclusive_signals:
        raise ExperimentInconclusive(
            f"the candidate was never run: '{detection.signal}'. The host could "
            "not schedule the surge pod beside the serving one, so this run "
            "observed its own capacity rather than the fault it injected. Free "
            "capacity, or lower the runtime's requests, and run it again"
        )
    if experiment.detection.require_decisive_signal:
        if detection.signal not in experiment.detection.decisive_signals:
            raise ExperimentFailed(
                f"the failure was detected as '{detection.signal}', which is not "
                "decisive. A deadline says a rollout stopped progressing; only a "
                "container that ran and stopped says the candidate is unhealthy",
                STAGE_DETECTION,
            )
        if detection.exit_code == 0:
            raise ExperimentFailed(
                "the detection names a decisive signal and a zero exit code, "
                "which is a container that succeeded",
                STAGE_DETECTION,
            )
    if experiment.detection.require_injected_workload and (
        detection.workload != experiment.fault.fails_in_workload
        or detection.container != experiment.fault.fails_in_container
    ):
        raise ExperimentFailed(
            f"the failure was read off '{detection.workload}/{detection.container}' "
            f"rather than the '{experiment.fault.fails_in_workload}/"
            f"{experiment.fault.fails_in_container}' the fault was injected into",
            STAGE_DETECTION,
        )
    if detection.candidate_pod == detection.serving_pod:
        raise ExperimentFailed(
            "the failing pod and the pod still serving are the same pod, so the "
            "release was not surging and the record cannot describe user impact",
            STAGE_DETECTION,
        )
    if detection.detected_after_ms > experiment.budgets.failure_detection_ms:
        raise ExperimentFailed(
            f"the failure took {detection.detected_after_ms} ms to detect, over "
            f"the {experiment.budgets.failure_detection_ms} ms budget",
            STAGE_DETECTION,
        )
    if unhealthy.elapsed_ms < detection.detected_after_ms:
        raise ExperimentFailed(
            "the unhealthy stage is recorded as shorter than the detection inside "
            "it, so the two clocks disagree",
            STAGE_DETECTION,
        )


def _check_rollback(experiment: Experiment, facts: LifecycleFacts) -> None:
    candidate = facts.stage("candidate")
    unhealthy = facts.stage("unhealthy-candidate")
    rollback = facts.stage("rollback")
    manifest = load_manifest()
    if rollback.outcome != OUTCOME_HEALTHY:
        raise ExperimentFailed(
            "the rollback did not restore a healthy release", STAGE_ROLLBACK
        )
    if experiment.rollback.require_fault_removed:
        if rollback.artifact_size_bytes == unhealthy.artifact_size_bytes:
            raise ExperimentFailed(
                "the rollback left the injected byte count in place",
                STAGE_ROLLBACK,
            )
        if rollback.artifact_size_bytes != manifest.expected_size_bytes:
            raise ExperimentFailed(
                "the rollback restored a byte count that is neither the injected "
                "one nor the pinned one",
                STAGE_ROLLBACK,
            )
    if (
        experiment.rollback.require_configuration_restored
        and rollback.service_version != candidate.service_version
    ):
        raise ExperimentFailed(
            "the rollback restored a revision other than the last known-good one: "
            f"its configuration says '{rollback.service_version}' where the "
            f"known-good candidate said '{candidate.service_version}'",
            STAGE_ROLLBACK,
        )
    if experiment.rollback.require_release_test and not rollback.release_test_passed:
        raise ExperimentFailed(
            "the rolled-back release did not pass the release's own test",
            STAGE_ROLLBACK,
        )
    if (
        experiment.require_distinct_candidate_revision
        and rollback.revision == candidate.revision
    ):
        raise ExperimentFailed(
            "the rollback is recorded as the same revision it restored, which "
            "means Helm's history was read rather than the cluster's",
            STAGE_ROLLBACK,
        )
    if rollback.elapsed_ms > experiment.budgets.rollback_ms:
        raise ExperimentFailed(
            f"the rollback took {rollback.elapsed_ms} ms, over the "
            f"{experiment.budgets.rollback_ms} ms budget",
            STAGE_ROLLBACK,
        )


def _check_recovery(experiment: Experiment, facts: LifecycleFacts) -> None:
    recovery = facts.recovery
    ordered = (
        recovery.injected_at_ms,
        recovery.detected_at_ms,
        recovery.rollback_started_at_ms,
        recovery.rollback_finished_at_ms,
        recovery.verified_at_ms,
    )
    if any(later < earlier for earlier, later in pairwise(ordered)):
        raise ExperimentFailed(
            f"the recovery timeline {list(ordered)} does not run forwards",
            STAGE_VERIFY,
        )
    if recovery.detection_ms != facts.detection.detected_after_ms:
        raise ExperimentFailed(
            "the recovery timeline and the detection record disagree about when "
            "the failure was found",
            STAGE_VERIFY,
        )
    if recovery.recovery_ms > experiment.budgets.recovery_ms:
        raise ExperimentFailed(
            f"recovery took {recovery.recovery_ms} ms, over the "
            f"{experiment.budgets.recovery_ms} ms budget",
            STAGE_VERIFY,
        )
    if experiment.require_recovery_recorded and recovery.verified_at_ms == 0:
        raise ExperimentFailed(
            "no recovery time was recorded, so the experiment measured nothing it "
            "was run to measure",
            STAGE_VERIFY,
        )


def _check_impact(
    experiment: Experiment, facts: LifecycleFacts, impact: ImpactObservations
) -> None:
    if impact.probe_path != experiment.impact.probe_path:
        raise ExperimentFailed(
            "the impact record describes a path other than the one the descriptor "
            "fixes",
            STAGE_IMPACT,
        )
    if len(impact.probes) < experiment.impact.minimum_probes:
        raise ExperimentFailed(
            f"the impact record holds {len(impact.probes)} probes, fewer than the "
            f"{experiment.impact.minimum_probes} the descriptor requires. A window "
            "nobody sampled is not a window with no impact in it",
            STAGE_IMPACT,
        )
    if impact.window_ended_ms < impact.window_started_ms:
        raise ExperimentFailed("the impact window does not run forwards", STAGE_IMPACT)
    outside = [
        probe.at_ms
        for probe in impact.probes
        if not impact.window_started_ms <= probe.at_ms <= impact.window_ended_ms
    ]
    if outside:
        raise ExperimentFailed(
            f"the impact record holds probes outside its own window: {outside}",
            STAGE_IMPACT,
        )
    if impact.window_ended_ms < facts.detection.detected_after_ms:
        raise ExperimentFailed(
            "the impact window closed before the failure was detected, so it does "
            "not cover the period it claims to describe",
            STAGE_IMPACT,
        )


def _check_cleanup(experiment: Experiment, cleanup: CleanupFacts) -> None:
    if cleanup.release_objects_remaining or cleanup.helm_release_present:
        raise ExperimentFailed("the uninstall left the release behind", STAGE_CLEANUP)
    if not cleanup.namespace_present:
        raise ExperimentFailed(
            "the uninstall removed the release namespace, which is a prerequisite "
            "and must outlive the release",
            STAGE_CLEANUP,
        )
    if cleanup.claims_after != cleanup.claims_before:
        raise ExperimentFailed(
            f"the persistent volume claim count changed across the experiment: "
            f"{cleanup.claims_before} before, {cleanup.claims_after} after",
            STAGE_CLEANUP,
        )
    if cleanup.uninstall_ms > experiment.budgets.uninstall_ms:
        raise ExperimentFailed(
            f"the uninstall took {cleanup.uninstall_ms} ms, over the "
            f"{experiment.budgets.uninstall_ms} ms budget",
            STAGE_CLEANUP,
        )


# -- what the restored release answered --------------------------------------


@dataclass(frozen=True, slots=True)
class RestoredIdentity:
    """The identity the rolled-back release published about itself."""

    adapter_kind: str
    model_identifier: str
    runtime_name: str
    runtime_version: str
    model_revision: str
    token_usage_declared: bool


@dataclass(frozen=True, slots=True)
class RestoredCompletion:
    """One completion served after the rollback; text deliberately not kept."""

    status: int
    elapsed_ms: int
    completion_characters: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    request_id_echoed: bool
    correlation_id_echoed: bool


def require_forwarded_base_url(base_url: str, baseline: Certification) -> str:
    """Reuse the certification's forward guard rather than write a second one.

    The rule — plain loopback HTTP, the descriptor's host, a port, and no path —
    is identical, and this experiment's descriptor is refused unless its request
    host is the certification's. A second implementation of the guard would be a
    second guard, and the one that drifted would be the one nobody read.
    """
    try:
        return _certification_forward_guard(base_url, baseline)
    except CertificationError as error:
        raise ExperimentRefused(str(error), STAGE_PREREQUISITES) from error


def _mapping(value: object, field: str, stage: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ExperimentFailed(f"the answer's '{field}' is not an object", stage)
    return cast(Mapping[str, object], value)


def _text(value: object, field: str, stage: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExperimentFailed(f"the answer's '{field}' is not a string", stage)
    return value


def _reached(call: Callable[[], ApiResponse]) -> ApiResponse:
    """Turn an unreachable forward into this workflow's own refusal.

    `api_get` and `api_post` are the certification's, and they raise in the
    certification's vocabulary. A run of this experiment that reported a
    `CertificationFailed` at the identity stage would send a reader to a
    workflow that was not running.
    """
    try:
        return call()
    except CertificationError as error:
        raise ExperimentFailed(
            "the forwarded InferOps Service could not be reached after the rollback",
            STAGE_VERIFY,
        ) from error


def _refuse_mock(experiment: Experiment, value: str, field: str) -> None:
    if experiment.prohibited_identity_substring in value.lower():
        raise ExperimentFailed(
            f"the restored release published '{value}' as its {field}, which "
            "carries mock identity. A rollback that restored a mock is not a "
            "rollback that restored real inference",
            STAGE_VERIFY,
        )


def observe_restored_readiness(
    experiment: Experiment, *, base_url: str, get: ApiGet
) -> None:
    """Ask the forwarded API for readiness before anything is asserted of it.

    The rollout wait and the release test both already answered, and both
    answered from inside the cluster. What this adds is that the forward itself
    reaches a ready API after the rollback: without it, a forward that opened
    onto a pod which has since gone not-ready produces a refusal at the identity
    stage, and the record would name the wrong thing.
    """
    response = _reached(
        lambda: get(
            f"{base_url}{experiment.readiness_path}",
            experiment.request_timeout_ms / 1000,
        )
    )
    if response.status != 200:
        raise ExperimentFailed(
            f"the rolled-back release answered {response.status} on "
            f"{experiment.readiness_path} rather than reporting itself ready",
            STAGE_VERIFY,
        )


def observe_restored_identity(
    experiment: Experiment, facts: LifecycleFacts, *, base_url: str, get: ApiGet
) -> RestoredIdentity:
    """Read what the rolled-back release says it is, through its own Service."""
    response = _reached(
        lambda: get(
            f"{base_url}{experiment.models_path}",
            experiment.request_timeout_ms / 1000,
        )
    )
    if response.status != 200:
        raise ExperimentFailed(
            f"the restored release answered {response.status} on "
            f"{experiment.models_path}",
            STAGE_VERIFY,
        )
    body = _mapping(response.body, "root", STAGE_VERIFY)
    extension = _mapping(body.get(EXTENSION_MEMBER), EXTENSION_MEMBER, STAGE_VERIFY)
    runtime = _mapping(extension.get("runtime"), "runtime", STAGE_VERIFY)
    capabilities = _mapping(extension.get("capabilities"), "capabilities", STAGE_VERIFY)
    entries = body.get("data")
    if not isinstance(entries, list) or len(entries) != 1:
        raise ExperimentFailed(
            "the restored release must serve exactly one model", STAGE_VERIFY
        )
    identity = RestoredIdentity(
        adapter_kind=_text(
            extension.get(EXTENSION_ADAPTER_KIND),
            EXTENSION_ADAPTER_KIND,
            STAGE_VERIFY,
        ),
        model_identifier=_text(
            _mapping(entries[0], "data[0]", STAGE_VERIFY).get("id"),
            "data[0].id",
            STAGE_VERIFY,
        ),
        runtime_name=_text(runtime.get("name"), "runtime.name", STAGE_VERIFY),
        runtime_version=_text(runtime.get("version"), "runtime.version", STAGE_VERIFY),
        model_revision=_text(
            runtime.get("modelRevision"), "runtime.modelRevision", STAGE_VERIFY
        ),
        token_usage_declared=capabilities.get(CAPABILITY_TOKEN_USAGE) is True,
    )
    if identity.adapter_kind != experiment.required_adapter_kind:
        raise ExperimentFailed(
            f"the restored release publishes adapter kind "
            f"'{identity.adapter_kind}' rather than "
            f"'{experiment.required_adapter_kind}'",
            STAGE_VERIFY,
        )
    if identity.runtime_name != LLAMA_SERVER_RUNTIME_NAME:
        raise ExperimentFailed(
            "the restored release names an unselected runtime", STAGE_VERIFY
        )
    if identity.model_identifier != facts.model_identifier:
        raise ExperimentFailed(
            "the restored release publishes a model the collected configuration "
            "does not name",
            STAGE_VERIFY,
        )
    if (
        experiment.require_pinned_model_revision
        and identity.model_revision != load_manifest().revision
    ):
        raise ExperimentFailed(
            "the restored release does not publish the pinned model revision",
            STAGE_VERIFY,
        )
    if experiment.require_usage_counts and not identity.token_usage_declared:
        # The selected real adapter declares token counting supported and the
        # committed mock declares it unsupported, so an absent or false
        # declaration here is mock capability metadata whatever else agreed.
        raise ExperimentFailed(
            "the restored release declares token usage unsupported, which is mock "
            "capability metadata",
            STAGE_VERIFY,
        )
    for field, value in (
        ("adapter kind", identity.adapter_kind),
        ("model identifier", identity.model_identifier),
        ("runtime name", identity.runtime_name),
        ("runtime version", identity.runtime_version),
        ("model revision", identity.model_revision),
    ):
        _refuse_mock(experiment, value, field)
    return identity


def observe_restored_completion(
    experiment: Experiment,
    facts: LifecycleFacts,
    *,
    base_url: str,
    post: ApiPost,
    clock: Callable[[], float] = time.monotonic,
) -> RestoredCompletion:
    """Send one request to the rolled-back release and hold it to every rule."""
    request_id = experiment.request_id("rollback")
    started = clock()
    response = _reached(
        lambda: post(
            f"{base_url}{experiment.request_path}",
            {
                "model": facts.model_identifier,
                "messages": [{"role": "user", "content": experiment.prompt}],
            },
            {
                REQUEST_ID_HEADER: request_id,
                CORRELATION_ID_HEADER: experiment.correlation_id,
            },
            experiment.request_timeout_ms / 1000,
        )
    )
    elapsed_ms = max(0, round((clock() - started) * 1000))
    if response.status != 200:
        raise ExperimentFailed(
            "the rolled-back release did not return a completion, so the rollback "
            "restored a release rather than real inference",
            STAGE_VERIFY,
        )
    body = _mapping(response.body, "root", STAGE_VERIFY)
    extension = _mapping(body.get(EXTENSION_MEMBER), EXTENSION_MEMBER, STAGE_VERIFY)
    if extension.get(EXTENSION_ADAPTER_KIND) != experiment.required_adapter_kind:
        raise ExperimentFailed(
            "the completion after the rollback was not served by the real adapter",
            STAGE_VERIFY,
        )
    if extension.get(EXTENSION_MODEL_REF) != facts.model_identifier:
        raise ExperimentFailed(
            "the completion after the rollback named an unconfigured model",
            STAGE_VERIFY,
        )
    choices = body.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ExperimentFailed("the completion carried no single choice", STAGE_VERIFY)
    message = _mapping(
        _mapping(choices[0], "choices[0]", STAGE_VERIFY).get("message"),
        "choices[0].message",
        STAGE_VERIFY,
    )
    content = message.get("content")
    if not isinstance(content, str) or (
        experiment.require_nonempty_content and not content.strip()
    ):
        raise ExperimentFailed(
            "the completion after the rollback is empty, which a Service that "
            "resolves and a runtime that loaded nothing both produce",
            STAGE_VERIFY,
        )
    counts = _mapping(body.get("usage"), "usage", STAGE_VERIFY)
    prompt_tokens = counts.get("prompt_tokens")
    completion_tokens = counts.get("completion_tokens")
    total_tokens = counts.get("total_tokens")
    if not (
        isinstance(prompt_tokens, int)
        and not isinstance(prompt_tokens, bool)
        and isinstance(completion_tokens, int)
        and not isinstance(completion_tokens, bool)
        and isinstance(total_tokens, int)
        and not isinstance(total_tokens, bool)
        and prompt_tokens > 0
        and completion_tokens > 0
        and total_tokens == prompt_tokens + completion_tokens
    ):
        raise ExperimentFailed(
            "the completion counts are absent or inconsistent, so they were not "
            "derived from the runtime's own accounting",
            STAGE_VERIFY,
        )
    return RestoredCompletion(
        status=response.status,
        elapsed_ms=elapsed_ms,
        completion_characters=len(content),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        request_id_echoed=response.headers.get(REQUEST_ID_HEADER) == request_id,
        correlation_id_echoed=(
            response.headers.get(CORRELATION_ID_HEADER) == experiment.correlation_id
        ),
    )


# -- the record --------------------------------------------------------------


def ensure_evidence_paths_safe(root: Path, targets: Sequence[Path]) -> None:
    """Refuse the fixed evidence location, or a file in it, that was redirected.

    The same rule the certification applies to its own directory, applied to
    this one. It is a second call site rather than a second rule: every segment
    of the ignored directory is checked as well as the files themselves, because
    a symlink or a Windows junction anywhere along the path turns "write a record
    into an ignored directory" into "write wherever that link points".
    """
    candidate = root
    for part in EXPECTED_EVIDENCE_DIRECTORY.parts:
        candidate = candidate / part
        if candidate.is_symlink() or os.path.isjunction(candidate):
            raise EvidenceUnwritable("the experiment evidence path is unsafe")
    for target in targets:
        if target.is_symlink() or os.path.isjunction(target):
            raise EvidenceUnwritable("the experiment evidence path is unsafe")
        if not target.resolve().is_relative_to(root):
            raise EvidenceUnwritable("the experiment evidence path is unsafe")


class EvidenceDirectory:
    """Write only this workflow's own records to the fixed ignored location."""

    def __init__(self, experiment: Experiment, *, repo_root: Path = REPO_ROOT) -> None:
        if experiment.evidence_directory != EXPECTED_EVIDENCE_DIRECTORY:
            raise EvidenceUnwritable("the experiment evidence path is unsafe")
        self.root = repo_root.resolve()
        self.directory = self.root / experiment.evidence_directory
        self.result_path = self.directory / experiment.result_file
        self.diagnostics_path = self.directory / experiment.diagnostics_file
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
                "the experiment evidence could not be written"
            ) from error
        return target


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    """A completed run, in the shape the evidence record is written from.

    There is deliberately no cleanup member. The teardown has not happened when
    this exists -- the release is still installed, because the two calls that
    produced the identity and the completion were made through a forward to it --
    and `merge_cleanup` adds that outcome to the written record afterwards.
    """

    experiment: Experiment
    facts: LifecycleFacts
    impact: ImpactObservations
    identity: RestoredIdentity
    completion: RestoredCompletion


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Why a run stopped, in this workflow's stage vocabulary."""

    stage: str
    reason: str


def _stages_document(facts: LifecycleFacts) -> list[dict[str, object]]:
    return [
        {
            "stage": stage.stage,
            "revision": stage.revision,
            "status": stage.status,
            "outcome": stage.outcome,
            "serviceVersion": stage.service_version,
            "artifactSizeBytes": stage.artifact_size_bytes,
            "elapsedMs": stage.elapsed_ms,
            "readyMs": stage.ready_ms,
            "releaseTestPassed": stage.release_test_passed,
        }
        for stage in facts.stages
    ]


def result_document(result: ExperimentResult) -> dict[str, object]:
    """The machine-readable record, carrying no prompt and no completion."""
    experiment = result.experiment
    facts = result.facts
    manifest = load_manifest()
    rollback = facts.stage("rollback")
    candidate = facts.stage("candidate")
    return {
        "experimentId": experiment.experiment_id,
        "certificationCeiling": experiment.certification_ceiling,
        "evidenceClass": experiment.evidence_class,
        "evidenceLabel": experiment.evidence_label,
        "outcome": "upgraded-and-rolled-back",
        "provenance": {
            "chart": facts.chart_version,
            "chartRef": experiment.chart_ref,
            "modelRevision": manifest.revision,
            "modelSha256": manifest.sha256,
            "nodeImageDigest": facts.node_image_digest,
            "serverVersion": facts.server_version,
            "helmVersion": facts.helm_version,
            "kubectlVersion": facts.kubectl_version,
        },
        "release": {
            "name": facts.release_name,
            "namespace": facts.release_namespace,
            "profile": facts.profile,
            "deploymentEnvironment": facts.deployment_environment,
        },
        "change": {
            "valuesPath": experiment.candidate.values_path,
            "candidateValue": experiment.candidate.candidate_value,
            "configMapKey": experiment.candidate.config_map_key,
            "candidateRevision": candidate.revision,
        },
        "fault": {
            "mechanism": experiment.fault.mechanism,
            "valuesPath": experiment.fault.values_path,
            "injectedSizeBytes": experiment.fault.injected_size_bytes,
            "pinnedSizeBytes": manifest.expected_size_bytes,
            "workload": experiment.fault.fails_in_workload,
            "container": experiment.fault.fails_in_container,
            "reversedBy": experiment.fault.reversible_by,
        },
        "stages": _stages_document(facts),
        "detection": {
            "signal": facts.detection.signal,
            "workload": facts.detection.workload,
            "container": facts.detection.container,
            "exitCode": facts.detection.exit_code,
            "reason": facts.detection.reason,
            "detectedAfterMs": facts.detection.detected_after_ms,
        },
        "recovery": {
            "detectionMs": facts.recovery.detection_ms,
            "rollbackMs": facts.recovery.rollback_ms,
            "recoveryMs": facts.recovery.recovery_ms,
            "restoredRevision": rollback.revision,
            "restoredFromRevision": candidate.revision,
            "runtimeReloaded": rollback.runtime_pod != candidate.runtime_pod,
        },
        "impact": {
            "probePath": result.impact.probe_path,
            "probes": len(result.impact.probes),
            "answered": result.impact.answered,
            "refused": result.impact.refused,
            "firstFailureAtMs": result.impact.first_failure_at_ms,
            "windowMs": result.impact.window_ended_ms - result.impact.window_started_ms,
        },
        "restoredIdentity": {
            "adapterKind": result.identity.adapter_kind,
            "modelIdentifier": result.identity.model_identifier,
            "modelRevision": result.identity.model_revision,
            "runtimeName": result.identity.runtime_name,
            "runtimeVersion": result.identity.runtime_version,
            "tokenUsageDeclared": result.identity.token_usage_declared,
        },
        "restoredCompletion": {
            "status": result.completion.status,
            "elapsedMs": result.completion.elapsed_ms,
            "completionCharacters": result.completion.completion_characters,
            "promptTokens": result.completion.prompt_tokens,
            "completionTokens": result.completion.completion_tokens,
            "totalTokens": result.completion.total_tokens,
            "requestIdEchoed": result.completion.request_id_echoed,
            "correlationIdEchoed": result.completion.correlation_id_echoed,
            "generatedTextRetained": experiment.retain_generated_text,
        },
        # Null until the release has been uninstalled. `merge_cleanup` fills it
        # in on a second write, and refuses a record that already carries one.
        "cleanup": None,
        "limitations": list(experiment.limitations),
    }


def diagnostics_document(diagnostics: Diagnostics) -> dict[str, object]:
    """What a failed run leaves behind, in this workflow's stage vocabulary."""
    return {
        "experimentId": EXPECTED_ID,
        "certificationCeiling": EXPECTED_CERTIFICATION_CEILING,
        "outcome": "not-completed",
        "stage": diagnostics.stage,
        "reason": diagnostics.reason,
    }


# -- the workflow ------------------------------------------------------------


def evaluate(
    experiment: Experiment,
    *,
    confirmed: bool,
    base_url: str,
    repo_root: Path = REPO_ROOT,
    baseline: Certification | None = None,
    get: ApiGet = api_get,
    post: ApiPost = api_post,
    clock: Callable[[], float] = time.monotonic,
) -> ExperimentResult:
    """Assert over everything the script collected, or raise carrying the stage.

    Nothing here operates a cluster. Every input except the two calls to the
    restored release is a file the operating script wrote while the release was
    installed, read as untrusted input at a location the descriptor fixes.
    """
    if not confirmed:
        raise ExperimentRefused(
            "the Helm upgrade and rollback experiment requires "
            "--confirm-real-kubernetes"
        )
    forwarded = require_forwarded_base_url(
        base_url, baseline if baseline is not None else load_certification()
    )
    facts = load_lifecycle_facts(experiment, repo_root=repo_root)
    impact = load_impact_observations(experiment, repo_root=repo_root)
    _check_environment(experiment, facts)
    _check_stage_shape(experiment, facts)
    _check_baseline(experiment, facts)
    _check_candidate(experiment, facts)
    _check_unhealthy_candidate(experiment, facts)
    _check_detection(experiment, facts)
    _check_rollback(experiment, facts)
    _check_recovery(experiment, facts)
    _check_impact(experiment, facts, impact)
    observe_restored_readiness(experiment, base_url=forwarded, get=get)
    identity = observe_restored_identity(experiment, facts, base_url=forwarded, get=get)
    completion = observe_restored_completion(
        experiment, facts, base_url=forwarded, post=post, clock=clock
    )
    return ExperimentResult(
        experiment=experiment,
        facts=facts,
        impact=impact,
        identity=identity,
        completion=completion,
    )


def merge_cleanup(
    experiment: Experiment, *, repo_root: Path = REPO_ROOT
) -> dict[str, object]:
    """Add the cleanup outcome to the record this workflow already wrote.

    The teardown happens after everything else has been established, so the
    cleanup member cannot exist when the record is first written and the record
    cannot wait for it: a run that failed its assertions still uninstalls, and a
    record produced only after a successful teardown would be a record that
    disappeared whenever the interesting thing happened.

    So the record is written twice, and the second write **adds** one member.
    Nothing else in it is re-derived here -- the identity and the completion were
    observed against a release that no longer exists, and re-deriving them would
    mean inventing them. What this does check is that the document it is adding
    to is this experiment's own record and that it does not already carry a
    cleanup, so a second teardown cannot quietly replace the first one's outcome.
    """
    evidence = EvidenceDirectory(experiment, repo_root=repo_root)
    try:
        document = json.loads(evidence.result_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ExperimentFailed(
            "there is no record to add a cleanup outcome to. The experiment has "
            "to be evaluated while the release is installed, and it was not",
            STAGE_CLEANUP,
        ) from error
    if not isinstance(document, dict):
        raise ExperimentFailed("the record is not an object", STAGE_CLEANUP)
    if document.get("experimentId") != experiment.experiment_id:
        raise ExperimentFailed(
            "the record in the evidence directory belongs to another experiment",
            STAGE_CLEANUP,
        )
    if document.get("cleanup") is not None:
        raise ExperimentFailed(
            "the record already carries a cleanup outcome. A second teardown may "
            "not replace the outcome of the first",
            STAGE_CLEANUP,
        )
    cleanup = load_cleanup_facts(experiment, repo_root=repo_root)
    _check_cleanup(experiment, cleanup)
    document["cleanup"] = {
        "uninstallMs": cleanup.uninstall_ms,
        "releaseObjectsRemaining": cleanup.release_objects_remaining,
        "namespacePresent": cleanup.namespace_present,
        "claimsBefore": cleanup.claims_before,
        "claimsAfter": cleanup.claims_after,
    }
    return cast(dict[str, object], document)
