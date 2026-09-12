"""The Kubernetes pod-restart persistence descriptor, assertions, and record.

The same three-way split as `tools/kubernetes_certification` and
`tools/helm_upgrade_rollback`, for the same reasons.

**Loading** reads committed files and contacts nothing. The descriptor is checked
against itself and then against the Kubernetes real-inference certification,
which already decided the cluster, the release, the request, and every budget the
two share. This experiment installs the same chart as the same release into the
same namespace on the same cluster, so a second set of numbers describing that
would be a second release waiting to be discovered.

**Observing** happens while the release is installed.
`scripts/environment/kubernetes-pod-restart.sh` owns every `helm`, `kubectl`, and
`terraform` invocation, because the guard that establishes which cluster is being
acted on already lives beside those wrappers and a second implementation of it in
another language would be a second guard. What this module reads is the file that
script wrote, at the location the descriptor fixes, as untrusted input.

**Recording** writes one whole document into the ignored evidence directory, with
the generated text deliberately not retained.

What the experiment answers, and why each half is hard to fake.

`V1-S3-003` asked whether model artifacts survive a pod restart, and the evidence
it produced answered a different question honestly: it stopped a container on the
host and started another, and
[its own record](../../docs/proof/serving/v1-s3-003-pr1-restart-reload.md) says in
as many words that it is **not** a pod restart. There was no published API image
and no filled claim at the time, so nothing could have scheduled a replacement
pod against a surviving claim. Both of those now exist, and this is the missing
experiment.

One pod is deleted, by name. Nothing declared is changed: no Deployment, no
claim, no release revision, no cluster-scoped object, and nothing in any other
namespace. The Deployment controller creates the replacement, and what has to be
established about it is not that a pod came back — a pod comes back whether or
not anything survived — but that:

1. it is a **different** pod, by name and by UID. A pod that restarted its
   container in place would show the same UID and would be a different
   experiment, one layer down, which is the one Sprint 2 already ran;
2. it mounted the **same** Terraform-owned claim, bound to the same volume;
3. the revision-scoped artifact is still there, at the same byte count and the
   same SHA-256, compared **inside the cluster** by the release's own integrity
   init container rather than by anything this module could be told;
4. readiness genuinely left true and came back, so the replacement was observed
   rather than inferred from a Deployment that never noticed;
5. **nothing re-acquired the model.** The acquisition hook is `pre-install` and
   `pre-upgrade`; deleting a pod is neither, so no Job may appear and the Job
   count may not move. This is the half that would otherwise be invisible: a
   release that quietly re-downloaded 1.83 GB on every pod replacement would look
   identical from the outside to one that preserved it;
6. a real completion comes back afterwards, from the real adapter, with
   runtime-derived token counts.

The one thing this module will not do is call a run successful because a pod is
ready. Readiness says a probe passed. Whether the pod is a different pod, whether
the claim is the same claim, whether the bytes are the same bytes, and whether a
real model answers are four separate questions, and each is asked of the cluster.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
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
    _read_clusters,
    api_get,
    api_post,
    load_certification,
)
from tools.kubernetes_certification.core import (
    require_forwarded_base_url as _certification_forward_guard,
)

# Re-exported deliberately, so that the CLI reaches the certification's HTTP
# seams and its descriptor loader through this module rather than reaching past
# it. What this experiment asserts and what it calls should come from one place.
__all__ = ["api_get", "api_post", "load_certification"]
from tools.model_acquisition import load_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_PATH = (
    REPO_ROOT / "deploy" / "serving" / "experiments" / "kubernetes-pod-restart.v1.json"
)

SCHEMA_VERSION = "inferops.io/v1alpha1"
EXPERIMENT_ID = "inferops-kubernetes-pod-restart-persistence"
EVIDENCE_CLASS = "local-real-cpu"
EVIDENCE_LABEL = "local real Kubernetes"
CERTIFICATION_CEILING = "C2"
LANE = "real-runtime"
CHART_REF = "charts/inferops-llm"

STAGES = ("baseline", "deletion", "replacement", "recovery", "cleanup")

# Where a record may be written, and the three host-state files this workflow's
# operating script leaves for it. Literals rather than descriptor values, for the
# reason `tools/helm_upgrade_rollback` states about its own: a descriptor that
# could name any path could name one outside the ignored directory, and a record
# written there would carry this project's evidence label into version control.
EXPECTED_EVIDENCE_DIRECTORY = Path(".cache/inferops/experiments")
EXPECTED_LIFECYCLE_FILE = Path(".artifacts/kubernetes-pod-restart/lifecycle-facts.json")
EXPECTED_BASELINE_FILE = Path(
    ".artifacts/kubernetes-pod-restart/baseline-completion.json"
)
EXPECTED_READINESS_FILE = Path(
    ".artifacts/kubernetes-pod-restart/readiness-observations.json"
)
EXPECTED_CLEANUP_FILE = Path(".artifacts/kubernetes-pod-restart/cleanup-facts.json")

# The one disruption this experiment may perform, held to a literal for the same
# reason the upgrade/rollback experiment holds its fault to one: a descriptor
# that could name any mechanism could name one that deletes a declared object,
# and the record would still carry this project's evidence label.
DISRUPTION_MECHANISM = "delete-serving-runtime-pod"
DISRUPTION_TARGET = "serving-runtime"
DISRUPTION_SCOPE = "pod"
DISRUPTION_REVERSED_BY = "deployment-controller"

# What the acquisition hook prints when it finds the artifact already in place.
# Compared as a substring of the hook's own output rather than inferred from the
# absence of a download, because "no Job ran" and "a Job ran and acquired
# nothing" are different facts and only one of them is this experiment's.
ACQUISITION_ALREADY_PRESENT = (
    "model artifact already present and verified; nothing to acquire"
)

STAGE_LOAD = "load"
STAGE_PREREQUISITES = "prerequisites"
STAGE_BASELINE = "baseline"
STAGE_DELETION = "deletion"
STAGE_REPLACEMENT = "replacement"
STAGE_RECOVERY = "recovery"
STAGE_CLEANUP = "cleanup"
STAGE_EVIDENCE = "evidence"


class ExperimentError(RuntimeError):
    """Anything that stops this experiment, carrying the stage that stopped it."""

    def __init__(self, message: str, stage: str = STAGE_LOAD) -> None:
        super().__init__(message)
        self.stage = stage


class ExperimentRefused(ExperimentError):
    """A precondition was not met, so nothing was observed."""


class ExperimentFailed(ExperimentError):
    """Something was observed and it does not support a record."""


class EvidenceUnwritable(ExperimentError):
    """The record could not be written where the descriptor says it goes."""


# -- the descriptor -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModelCachePolicy:
    """What the claim and the artifact on it have to be, across the replacement."""

    claim_name: str
    owner: str
    verification_init_container: str
    require_read_only_mount: bool
    require_same_claim_remounted: bool
    require_same_bound_volume: bool
    require_revision_scoped_artifact: bool
    require_artifact_byte_count_unchanged: bool
    require_artifact_digest_unchanged: bool
    require_artifact_inode_unchanged: bool
    require_artifact_mtime_unchanged: bool


@dataclass(frozen=True, slots=True)
class Disruption:
    """The single delete, and every property that keeps it a pod-scoped one."""

    mechanism: str
    target: str
    scope: str
    deletes_declared_object: bool
    changes_no_deployment: bool
    changes_no_persistent_volume_claim: bool
    changes_no_release_revision: bool
    changes_no_cluster_scoped_object: bool
    touches_no_other_namespace: bool
    reversed_by: str


@dataclass(frozen=True, slots=True)
class ReplacementPolicy:
    """Everything the replacement pod has to establish before a record exists."""

    require_different_pod_name: bool
    require_different_pod_uid: bool
    require_same_deployment_owner: bool
    require_readiness_observed_false: bool
    require_readiness_observed_true: bool
    require_integrity_init_container_succeeded: bool
    require_no_new_acquisition_job: bool
    require_acquisition_not_repeated: bool
    require_no_release_revision_change: bool


@dataclass(frozen=True, slots=True)
class AcquisitionPolicy:
    """How "the model was not fetched again" is established rather than assumed."""

    already_present_signal: str
    require_job_count_unchanged: bool
    require_hook_not_triggered_by_pod_deletion: bool


@dataclass(frozen=True, slots=True)
class ExperimentBudgets:
    """Every bound this workflow applies.

    The eight it shares with the Kubernetes real-inference certification are
    compared against it for equality rather than re-derived; the three that are
    this experiment's own bound the delete, the replacement, and the interval
    from the delete to a served completion.
    """

    install_ms: int
    runtime_startup_ms: int
    runtime_rollout_ms: int
    api_startup_ms: int
    api_rollout_ms: int
    release_test_ms: int
    forward_ms: int
    uninstall_ms: int
    deletion_ms: int
    replacement_ms: int
    recovery_ms: int


@dataclass(frozen=True, slots=True)
class ObservationPlan:
    """How readiness across the replacement is sampled, and how much is enough."""

    poll_interval_ms: int
    minimum_samples: int
    require_readiness_record: bool


@dataclass(frozen=True, slots=True)
class Experiment:
    """The committed descriptor, after it has been checked against itself."""

    experiment_id: str
    evidence_class: str
    evidence_label: str
    certification_ceiling: str
    lane: str
    chart_ref: str
    procedure_ref: str
    baseline_certification_ref: str
    clusters: tuple[ClusterTarget, ...]
    release: ReleaseTarget
    acquisition_component: str
    stages: tuple[str, ...]
    model_cache: ModelCachePolicy
    disruption: Disruption
    replacement: ReplacementPolicy
    acquisition: AcquisitionPolicy
    budgets: ExperimentBudgets
    observation: ObservationPlan
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
    require_non_empty_content: bool
    require_pinned_model_revision: bool
    require_every_replica_ready: bool
    require_pinned_node_image: bool
    require_recovery_recorded: bool
    require_inference_before_and_after: bool
    evidence_directory: Path
    result_file: str
    diagnostics_file: str
    lifecycle_file: Path
    baseline_completion_file: Path
    readiness_file: Path
    cleanup_file: Path
    retain_generated_text: bool
    uninstalls_release: bool
    removes_prerequisites: bool
    removes_cluster: bool
    removes_model_cache_claim: bool
    limitations: tuple[str, ...]

    def request_id(self, stage: str) -> str:
        return f"{self.request_id_prefix}-{stage}"

    def artifact_path(self, relative: Path, repo_root: Path = REPO_ROOT) -> Path:
        return repo_root / relative


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExperimentError(f"experiment field '{field}' must be an object")
    return cast(dict[str, Any], value)


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExperimentError(f"experiment field '{field}' must be a non-empty string")
    return value


def _integer(value: Any, field: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ExperimentError(
            f"experiment field '{field}' must be an integer of at least {minimum}"
        )
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ExperimentError(f"experiment field '{field}' must be true or false")
    return value


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ExperimentError(f"experiment field '{field}' must be a non-empty list")
    return tuple(_string(entry, f"{field}[]") for entry in value)


def _require_keys(record: Mapping[str, Any], field: str, expected: set[str]) -> None:
    present = set(record)
    missing = expected - present
    if missing:
        raise ExperimentError(
            f"experiment section '{field}' is missing {sorted(missing)}"
        )
    unexpected = present - expected
    if unexpected:
        raise ExperimentError(
            f"experiment section '{field}' carries unknown members "
            f"{sorted(unexpected)}. A member nothing reads is a member nobody "
            "maintains"
        )


def _read_release(release: Mapping[str, Any]) -> tuple[ReleaseTarget, str]:
    """The release, plus the acquisition component this descriptor adds to it.

    `ReleaseTarget` is the certification's and is compared against it for
    equality, so the one member this experiment needs and that does not describe
    a release the certification installs is kept beside it rather than added to
    it.
    """
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
            "acquisitionComponent",
            "replicas",
        },
    )
    target = ReleaseTarget(
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
    acquisition_component = _string(
        release.get("acquisitionComponent"), "release.acquisitionComponent"
    )
    return target, acquisition_component


def _read_model_cache(cache: Mapping[str, Any]) -> ModelCachePolicy:
    _require_keys(
        cache,
        "modelCache",
        {
            "claimName",
            "owner",
            "verificationInitContainer",
            "requireReadOnlyMount",
            "requireSameClaimRemounted",
            "requireSameBoundVolume",
            "requireRevisionScopedArtifact",
            "requireArtifactByteCountUnchanged",
            "requireArtifactDigestUnchanged",
            "requireArtifactInodeUnchanged",
            "requireArtifactMtimeUnchanged",
        },
    )
    return ModelCachePolicy(
        claim_name=_string(cache.get("claimName"), "modelCache.claimName"),
        owner=_string(cache.get("owner"), "modelCache.owner"),
        verification_init_container=_string(
            cache.get("verificationInitContainer"),
            "modelCache.verificationInitContainer",
        ),
        require_read_only_mount=_boolean(
            cache.get("requireReadOnlyMount"), "modelCache.requireReadOnlyMount"
        ),
        require_same_claim_remounted=_boolean(
            cache.get("requireSameClaimRemounted"),
            "modelCache.requireSameClaimRemounted",
        ),
        require_same_bound_volume=_boolean(
            cache.get("requireSameBoundVolume"), "modelCache.requireSameBoundVolume"
        ),
        require_revision_scoped_artifact=_boolean(
            cache.get("requireRevisionScopedArtifact"),
            "modelCache.requireRevisionScopedArtifact",
        ),
        require_artifact_byte_count_unchanged=_boolean(
            cache.get("requireArtifactByteCountUnchanged"),
            "modelCache.requireArtifactByteCountUnchanged",
        ),
        require_artifact_digest_unchanged=_boolean(
            cache.get("requireArtifactDigestUnchanged"),
            "modelCache.requireArtifactDigestUnchanged",
        ),
        require_artifact_inode_unchanged=_boolean(
            cache.get("requireArtifactInodeUnchanged"),
            "modelCache.requireArtifactInodeUnchanged",
        ),
        require_artifact_mtime_unchanged=_boolean(
            cache.get("requireArtifactMtimeUnchanged"),
            "modelCache.requireArtifactMtimeUnchanged",
        ),
    )


def _read_disruption(disruption: Mapping[str, Any]) -> Disruption:
    _require_keys(
        disruption,
        "disruption",
        {
            "description",
            "mechanism",
            "target",
            "scope",
            "deletesDeclaredObject",
            "changesNoDeployment",
            "changesNoPersistentVolumeClaim",
            "changesNoReleaseRevision",
            "changesNoClusterScopedObject",
            "touchesNoOtherNamespace",
            "reversedBy",
        },
    )
    _string(disruption.get("description"), "disruption.description")
    return Disruption(
        mechanism=_string(disruption.get("mechanism"), "disruption.mechanism"),
        target=_string(disruption.get("target"), "disruption.target"),
        scope=_string(disruption.get("scope"), "disruption.scope"),
        deletes_declared_object=_boolean(
            disruption.get("deletesDeclaredObject"), "disruption.deletesDeclaredObject"
        ),
        changes_no_deployment=_boolean(
            disruption.get("changesNoDeployment"), "disruption.changesNoDeployment"
        ),
        changes_no_persistent_volume_claim=_boolean(
            disruption.get("changesNoPersistentVolumeClaim"),
            "disruption.changesNoPersistentVolumeClaim",
        ),
        changes_no_release_revision=_boolean(
            disruption.get("changesNoReleaseRevision"),
            "disruption.changesNoReleaseRevision",
        ),
        changes_no_cluster_scoped_object=_boolean(
            disruption.get("changesNoClusterScopedObject"),
            "disruption.changesNoClusterScopedObject",
        ),
        touches_no_other_namespace=_boolean(
            disruption.get("touchesNoOtherNamespace"),
            "disruption.touchesNoOtherNamespace",
        ),
        reversed_by=_string(disruption.get("reversedBy"), "disruption.reversedBy"),
    )


def _read_replacement(replacement: Mapping[str, Any]) -> ReplacementPolicy:
    _require_keys(
        replacement,
        "replacement",
        {
            "requireDifferentPodName",
            "requireDifferentPodUid",
            "requireSameDeploymentOwner",
            "requireReadinessObservedFalse",
            "requireReadinessObservedTrue",
            "requireIntegrityInitContainerSucceeded",
            "requireNoNewAcquisitionJob",
            "requireAcquisitionNotRepeated",
            "requireNoReleaseRevisionChange",
        },
    )
    return ReplacementPolicy(
        require_different_pod_name=_boolean(
            replacement.get("requireDifferentPodName"),
            "replacement.requireDifferentPodName",
        ),
        require_different_pod_uid=_boolean(
            replacement.get("requireDifferentPodUid"),
            "replacement.requireDifferentPodUid",
        ),
        require_same_deployment_owner=_boolean(
            replacement.get("requireSameDeploymentOwner"),
            "replacement.requireSameDeploymentOwner",
        ),
        require_readiness_observed_false=_boolean(
            replacement.get("requireReadinessObservedFalse"),
            "replacement.requireReadinessObservedFalse",
        ),
        require_readiness_observed_true=_boolean(
            replacement.get("requireReadinessObservedTrue"),
            "replacement.requireReadinessObservedTrue",
        ),
        require_integrity_init_container_succeeded=_boolean(
            replacement.get("requireIntegrityInitContainerSucceeded"),
            "replacement.requireIntegrityInitContainerSucceeded",
        ),
        require_no_new_acquisition_job=_boolean(
            replacement.get("requireNoNewAcquisitionJob"),
            "replacement.requireNoNewAcquisitionJob",
        ),
        require_acquisition_not_repeated=_boolean(
            replacement.get("requireAcquisitionNotRepeated"),
            "replacement.requireAcquisitionNotRepeated",
        ),
        require_no_release_revision_change=_boolean(
            replacement.get("requireNoReleaseRevisionChange"),
            "replacement.requireNoReleaseRevisionChange",
        ),
    )


def _read_acquisition(acquisition: Mapping[str, Any]) -> AcquisitionPolicy:
    _require_keys(
        acquisition,
        "acquisition",
        {
            "description",
            "alreadyPresentSignal",
            "requireJobCountUnchanged",
            "requireHookNotTriggeredByPodDeletion",
        },
    )
    _string(acquisition.get("description"), "acquisition.description")
    return AcquisitionPolicy(
        already_present_signal=_string(
            acquisition.get("alreadyPresentSignal"), "acquisition.alreadyPresentSignal"
        ),
        require_job_count_unchanged=_boolean(
            acquisition.get("requireJobCountUnchanged"),
            "acquisition.requireJobCountUnchanged",
        ),
        require_hook_not_triggered_by_pod_deletion=_boolean(
            acquisition.get("requireHookNotTriggeredByPodDeletion"),
            "acquisition.requireHookNotTriggeredByPodDeletion",
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
            "deletionBudgetMs",
            "replacementBudgetMs",
            "recoveryBudgetMs",
            "uninstallBudgetMs",
        },
    )
    return ExperimentBudgets(
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
        forward_ms=_integer(
            readiness.get("forwardBudgetMs"), "readiness.forwardBudgetMs"
        ),
        uninstall_ms=_integer(
            readiness.get("uninstallBudgetMs"), "readiness.uninstallBudgetMs"
        ),
        deletion_ms=_integer(
            readiness.get("deletionBudgetMs"), "readiness.deletionBudgetMs"
        ),
        replacement_ms=_integer(
            readiness.get("replacementBudgetMs"), "readiness.replacementBudgetMs"
        ),
        recovery_ms=_integer(
            readiness.get("recoveryBudgetMs"), "readiness.recoveryBudgetMs"
        ),
    )


def _read_observation(observation: Mapping[str, Any]) -> ObservationPlan:
    _require_keys(
        observation,
        "observation",
        {
            "description",
            "pollIntervalMs",
            "minimumSamples",
            "requireReadinessRecord",
        },
    )
    _string(observation.get("description"), "observation.description")
    return ObservationPlan(
        poll_interval_ms=_integer(
            observation.get("pollIntervalMs"), "observation.pollIntervalMs"
        ),
        minimum_samples=_integer(
            observation.get("minimumSamples"), "observation.minimumSamples"
        ),
        require_readiness_record=_boolean(
            observation.get("requireReadinessRecord"),
            "observation.requireReadinessRecord",
        ),
    )


def load_experiment(
    path: Path = EXPERIMENT_PATH, *, baseline: Certification | None = None
) -> Experiment:
    """Read the committed descriptor and refuse it before anything is installed."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ExperimentError(f"no experiment descriptor at {path}") from error
    except json.JSONDecodeError as error:
        raise ExperimentError(
            f"the experiment descriptor is not JSON: {error}"
        ) from error
    if not isinstance(document, dict):
        raise ExperimentError("the experiment descriptor must be a JSON object")

    release, acquisition_component = _read_release(
        _object(document.get("release"), "release")
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
    for member in prerequisites:
        if not _boolean(prerequisites.get(member), f"prerequisites.{member}"):
            raise ExperimentError(
                f"prerequisites.{member} is false. Every precondition this "
                "experiment names is a precondition it has, because a run that "
                "skipped one would be recording a different experiment"
            )
    request = _object(document.get("request"), "request")
    assertions = _object(document.get("assertions"), "assertions")
    evidence = _object(document.get("evidence"), "evidence")
    cleanup = _object(document.get("cleanup"), "cleanup")

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
    _require_keys(
        assertions,
        "assertions",
        {
            "requiredAdapterKind",
            "prohibitedIdentitySubstring",
            "requireUsageCounts",
            "requireNonEmptyContent",
            "requirePinnedModelRevision",
            "requireEveryReplicaReady",
            "requirePinnedNodeImage",
            "requireRecoveryRecorded",
            "requireInferenceBeforeAndAfter",
        },
    )
    _require_keys(
        evidence,
        "evidence",
        {
            "directory",
            "resultFile",
            "diagnosticsFile",
            "lifecycleFile",
            "baselineCompletionFile",
            "readinessFile",
            "cleanupFile",
            "retainGeneratedText",
        },
    )
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
        experiment_id=_string(document.get("experimentId"), "experimentId"),
        evidence_class=_string(document.get("evidenceClass"), "evidenceClass"),
        evidence_label=_string(document.get("evidenceLabel"), "evidenceLabel"),
        certification_ceiling=_string(
            document.get("certificationCeiling"), "certificationCeiling"
        ),
        lane=_string(document.get("lane"), "lane"),
        chart_ref=_string(document.get("chartRef"), "chartRef"),
        procedure_ref=_string(document.get("procedureRef"), "procedureRef"),
        baseline_certification_ref=_string(
            document.get("baselineCertificationRef"), "baselineCertificationRef"
        ),
        clusters=_read_clusters(_object(document.get("cluster"), "cluster")),
        release=release,
        acquisition_component=acquisition_component,
        stages=_strings(document.get("stages"), "stages"),
        model_cache=_read_model_cache(
            _object(document.get("modelCache"), "modelCache")
        ),
        disruption=_read_disruption(_object(document.get("disruption"), "disruption")),
        replacement=_read_replacement(
            _object(document.get("replacement"), "replacement")
        ),
        acquisition=_read_acquisition(
            _object(document.get("acquisition"), "acquisition")
        ),
        budgets=_read_budgets(_object(document.get("readiness"), "readiness")),
        observation=_read_observation(
            _object(document.get("observation"), "observation")
        ),
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
            assertions.get("requiredAdapterKind"), "assertions.requiredAdapterKind"
        ),
        prohibited_identity_substring=_string(
            assertions.get("prohibitedIdentitySubstring"),
            "assertions.prohibitedIdentitySubstring",
        ),
        require_usage_counts=_boolean(
            assertions.get("requireUsageCounts"), "assertions.requireUsageCounts"
        ),
        require_non_empty_content=_boolean(
            assertions.get("requireNonEmptyContent"),
            "assertions.requireNonEmptyContent",
        ),
        require_pinned_model_revision=_boolean(
            assertions.get("requirePinnedModelRevision"),
            "assertions.requirePinnedModelRevision",
        ),
        require_every_replica_ready=_boolean(
            assertions.get("requireEveryReplicaReady"),
            "assertions.requireEveryReplicaReady",
        ),
        require_pinned_node_image=_boolean(
            assertions.get("requirePinnedNodeImage"),
            "assertions.requirePinnedNodeImage",
        ),
        require_recovery_recorded=_boolean(
            assertions.get("requireRecoveryRecorded"),
            "assertions.requireRecoveryRecorded",
        ),
        require_inference_before_and_after=_boolean(
            assertions.get("requireInferenceBeforeAndAfter"),
            "assertions.requireInferenceBeforeAndAfter",
        ),
        evidence_directory=Path(
            _string(evidence.get("directory"), "evidence.directory")
        ),
        result_file=_string(evidence.get("resultFile"), "evidence.resultFile"),
        diagnostics_file=_string(
            evidence.get("diagnosticsFile"), "evidence.diagnosticsFile"
        ),
        lifecycle_file=Path(
            _string(evidence.get("lifecycleFile"), "evidence.lifecycleFile")
        ),
        baseline_completion_file=Path(
            _string(
                evidence.get("baselineCompletionFile"),
                "evidence.baselineCompletionFile",
            )
        ),
        readiness_file=Path(
            _string(evidence.get("readinessFile"), "evidence.readinessFile")
        ),
        cleanup_file=Path(_string(evidence.get("cleanupFile"), "evidence.cleanupFile")),
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
        removes_model_cache_claim=_boolean(
            cleanup.get("removesModelCacheClaim"), "cleanup.removesModelCacheClaim"
        ),
        limitations=_strings(document.get("limitations"), "limitations"),
    )
    _validate(experiment, baseline if baseline is not None else load_certification())
    return experiment


def _validate_identity(experiment: Experiment) -> None:
    if experiment.experiment_id != EXPERIMENT_ID:
        raise ExperimentError(f"the experiment id must be '{EXPERIMENT_ID}'")
    if experiment.evidence_class != EVIDENCE_CLASS:
        raise ExperimentError(f"the evidence class must be '{EVIDENCE_CLASS}'")
    if experiment.evidence_label != EVIDENCE_LABEL:
        raise ExperimentError(f"the evidence label must be '{EVIDENCE_LABEL}'")
    if experiment.certification_ceiling != CERTIFICATION_CEILING:
        raise ExperimentError(
            f"the certification ceiling must be '{CERTIFICATION_CEILING}'"
        )
    if experiment.lane != LANE:
        raise ExperimentError(f"the lane must be '{LANE}'")
    if experiment.chart_ref != CHART_REF:
        raise ExperimentError(f"the chart reference must be '{CHART_REF}'")
    if experiment.stages != STAGES:
        raise ExperimentError(f"the stages must be exactly {list(STAGES)}")
    if experiment.retain_generated_text:
        raise ExperimentError(
            "this experiment sends a real model a real prompt, and its record may "
            "not retain the text that came back"
        )


def _validate_against_baseline(experiment: Experiment, baseline: Certification) -> None:
    """The certification already decided most of this; disagreeing is the error.

    This experiment installs the same chart, as the same release, into the same
    namespace, on the same cluster, and reads the same API through the same
    loopback forward. A second set of numbers describing that is a second release
    waiting to be discovered, so the shared blocks are compared for equality
    rather than re-derived.
    """
    if experiment.baseline_certification_ref != (
        "deploy/serving/certification/k8s-real-inference.v1.json"
    ):
        raise ExperimentError(
            "this experiment's baseline must be the Kubernetes real-inference "
            "certification"
        )
    if experiment.clusters != baseline.clusters:
        raise ExperimentError(
            "the experiment and the certification describe different providers, "
            "cluster names, contexts, or node-image pins"
        )
    if experiment.release != baseline.release:
        raise ExperimentError(
            "the experiment and the certification describe different releases"
        )
    for name, mine, theirs in (
        ("request host", experiment.request_host, baseline.request_host),
        ("request path", experiment.request_path, baseline.request_path),
        ("models path", experiment.models_path, baseline.models_path),
        ("readiness path", experiment.readiness_path, baseline.readiness_path),
        (
            "request timeout",
            experiment.request_timeout_ms,
            baseline.request_timeout_ms,
        ),
        ("install budget", experiment.budgets.install_ms, baseline.budgets.install_ms),
        (
            "runtime startup budget",
            experiment.budgets.runtime_startup_ms,
            baseline.budgets.runtime_startup_ms,
        ),
        (
            "runtime rollout budget",
            experiment.budgets.runtime_rollout_ms,
            baseline.budgets.runtime_rollout_ms,
        ),
        (
            "api startup budget",
            experiment.budgets.api_startup_ms,
            baseline.budgets.api_startup_ms,
        ),
        (
            "api rollout budget",
            experiment.budgets.api_rollout_ms,
            baseline.budgets.api_rollout_ms,
        ),
        (
            "release test budget",
            experiment.budgets.release_test_ms,
            baseline.budgets.release_test_ms,
        ),
        ("forward budget", experiment.budgets.forward_ms, baseline.budgets.forward_ms),
        (
            "uninstall budget",
            experiment.budgets.uninstall_ms,
            baseline.budgets.uninstall_ms,
        ),
    ):
        if mine != theirs:
            raise ExperimentError(
                f"the experiment's {name} disagrees with the Kubernetes "
                "real-inference certification, which already decided it"
            )
    if experiment.model_cache.claim_name != baseline.model_cache.claim_name:
        raise ExperimentError(
            "the experiment and the certification name different model cache claims"
        )
    if (
        experiment.model_cache.verification_init_container
        != baseline.model_cache.verification_init_container
    ):
        raise ExperimentError(
            "the experiment and the certification name different integrity init "
            "containers"
        )


def _validate_disruption(experiment: Experiment) -> None:
    disruption = experiment.disruption
    if disruption.mechanism != DISRUPTION_MECHANISM:
        raise ExperimentError(
            f"the only disruption this experiment may perform is "
            f"'{DISRUPTION_MECHANISM}'"
        )
    if disruption.target != DISRUPTION_TARGET or disruption.scope != DISRUPTION_SCOPE:
        raise ExperimentError(
            f"the disruption must be scoped to a '{DISRUPTION_SCOPE}' of the "
            f"'{DISRUPTION_TARGET}' workload"
        )
    if disruption.reversed_by != DISRUPTION_REVERSED_BY:
        raise ExperimentError(
            "the replacement must be made by the Deployment controller. A "
            "replacement this workflow created itself would be this workflow "
            "testing itself"
        )
    if disruption.deletes_declared_object:
        raise ExperimentError(
            "a pod is not a declared object. An experiment that deleted one would "
            "be removing something a tool owns, and the ownership inventory says "
            "which tool"
        )
    if not (
        disruption.changes_no_deployment
        and disruption.changes_no_persistent_volume_claim
        and disruption.changes_no_release_revision
        and disruption.changes_no_cluster_scoped_object
        and disruption.touches_no_other_namespace
    ):
        raise ExperimentError(
            "the disruption does not declare every property that keeps it one "
            "deleted pod rather than a change to the release"
        )


def _validate_model_cache(experiment: Experiment) -> None:
    cache = experiment.model_cache
    if cache.owner != "terraform":
        raise ExperimentError(
            "the model cache claim is Terraform's "
            "(docs/architecture/resource-ownership.md). An experiment that "
            "described it as anything else would be describing another claim"
        )
    if not (
        cache.require_read_only_mount
        and cache.require_same_claim_remounted
        and cache.require_same_bound_volume
        and cache.require_revision_scoped_artifact
        and cache.require_artifact_byte_count_unchanged
        and cache.require_artifact_digest_unchanged
        and cache.require_artifact_inode_unchanged
        and cache.require_artifact_mtime_unchanged
    ):
        raise ExperimentError(
            "every model cache assertion is required. A persistence experiment "
            "that did not compare the artifact would be a restart experiment"
        )


def _validate_replacement(experiment: Experiment) -> None:
    replacement = experiment.replacement
    if not (
        replacement.require_different_pod_name and replacement.require_different_pod_uid
    ):
        raise ExperimentError(
            "the replacement must be required to be a different pod by name and "
            "by UID. A container that restarted in place is a different "
            "experiment, one layer down"
        )
    if not (
        replacement.require_same_deployment_owner
        and replacement.require_readiness_observed_false
        and replacement.require_readiness_observed_true
        and replacement.require_integrity_init_container_succeeded
        and replacement.require_no_new_acquisition_job
        and replacement.require_acquisition_not_repeated
        and replacement.require_no_release_revision_change
    ):
        raise ExperimentError(
            "every replacement assertion is required. Each one names a way this "
            "experiment could look successful without having happened"
        )


def _validate_acquisition(experiment: Experiment) -> None:
    acquisition = experiment.acquisition
    if acquisition.already_present_signal != ACQUISITION_ALREADY_PRESENT:
        raise ExperimentError(
            "the already-present signal must be the line the chart's acquisition "
            "script actually prints, or this experiment would be asserting "
            "against a sentence nothing emits"
        )
    if not (
        acquisition.require_job_count_unchanged
        and acquisition.require_hook_not_triggered_by_pod_deletion
    ):
        raise ExperimentError(
            "both acquisition assertions are required. A release that silently "
            "re-acquired 1.83 GB on every pod replacement would look identical "
            "from outside to one that preserved it"
        )


def _validate_budgets(experiment: Experiment) -> None:
    budgets = experiment.budgets
    if budgets.replacement_ms < budgets.runtime_rollout_ms:
        raise ExperimentError(
            "the replacement budget is shorter than a healthy rollout is allowed "
            "to take, so a slow but correct replacement would be recorded as a "
            "failure"
        )
    if budgets.recovery_ms <= budgets.replacement_ms:
        raise ExperimentError(
            "the recovery budget must exceed the replacement budget it contains"
        )
    if budgets.deletion_ms < 1000:
        raise ExperimentError("the deletion budget must be at least one second")


def _validate_observation(experiment: Experiment) -> None:
    observation = experiment.observation
    if observation.poll_interval_ms < 1000:
        raise ExperimentError(
            "the readiness poll interval must be at least 1000 ms. Below that the "
            "wait between polls truncates to zero and the loop spins against the "
            "API server"
        )
    if not observation.require_readiness_record:
        raise ExperimentError(
            "a readiness record is required. Without it 'readiness reset and came "
            "back' is a claim with nothing behind it"
        )
    if observation.minimum_samples < 3:
        raise ExperimentError(
            "at least three readiness samples are required: one before, one "
            "during, one after"
        )


def _validate_evidence(experiment: Experiment) -> None:
    if (
        experiment.evidence_directory != EXPECTED_EVIDENCE_DIRECTORY
        or experiment.lifecycle_file != EXPECTED_LIFECYCLE_FILE
        or experiment.baseline_completion_file != EXPECTED_BASELINE_FILE
        or experiment.readiness_file != EXPECTED_READINESS_FILE
        or experiment.cleanup_file != EXPECTED_CLEANUP_FILE
        or Path(experiment.result_file).name != experiment.result_file
        or Path(experiment.diagnostics_file).name != experiment.diagnostics_file
    ):
        raise ExperimentError(
            "the evidence locations are fixed: the record goes under "
            f"'{EXPECTED_EVIDENCE_DIRECTORY.as_posix()}' and the collected files "
            "come from this workflow's own directory under '.artifacts/'. A "
            "descriptor that could name any path could name one version control "
            "does not ignore"
        )
    if not experiment.uninstalls_release:
        raise ExperimentError(
            "this experiment installs a release and must remove it. A release "
            "left behind is residue the next run would find"
        )
    if (
        experiment.removes_prerequisites
        or experiment.removes_cluster
        or experiment.removes_model_cache_claim
    ):
        raise ExperimentError(
            "this experiment removes the release and nothing else. The namespace "
            "and the claim are Terraform's and the cluster is the operator's "
            "(ADR 0011)"
        )


def _validate(experiment: Experiment, baseline: Certification) -> None:
    _validate_identity(experiment)
    _validate_against_baseline(experiment, baseline)
    _validate_disruption(experiment)
    _validate_model_cache(experiment)
    _validate_replacement(experiment)
    _validate_acquisition(experiment)
    _validate_budgets(experiment)
    _validate_observation(experiment)
    _validate_evidence(experiment)


# -- what the script collected, read as untrusted input ------------------------


class _Facts:
    """The same reader shape the other two experiments use, at one stage."""

    def __init__(self, stage: str) -> None:
        self.stage = stage

    def fail(self, message: str) -> ExperimentFailed:
        return ExperimentFailed(message, self.stage)

    def document(self, path: Path, description: str) -> dict[str, Any]:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise self.fail(f"the {description} were never written") from error
        except json.JSONDecodeError as error:
            raise self.fail(f"the {description} are not JSON: {error}") from error
        if not isinstance(loaded, dict):
            raise self.fail(f"the {description} must be a JSON object")
        return cast(dict[str, Any], loaded)

    def object(self, value: Any, field: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise self.fail(f"the collected member '{field}' is not an object")
        return cast(dict[str, Any], value)

    def entries(self, value: Any, field: str) -> list[Any]:
        if not isinstance(value, list):
            raise self.fail(f"the collected member '{field}' is not a list")
        return value

    def string(self, value: Any, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise self.fail(f"the collected member '{field}' is not a string")
        return value

    def optional_string(self, value: Any, field: str) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise self.fail(f"the collected member '{field}' is not a string")
        return value

    def integer(self, value: Any, field: str, *, minimum: int = 0) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise self.fail(
                f"the collected member '{field}' is not an integer of at least "
                f"{minimum}"
            )
        return value

    def boolean(self, value: Any, field: str) -> bool:
        if not isinstance(value, bool):
            raise self.fail(f"the collected member '{field}' is not true or false")
        return value


@dataclass(frozen=True, slots=True)
class PodFacts:
    """One serving runtime pod, as the cluster described it."""

    name: str
    uid: str
    owner_kind: str
    owner_name: str
    node_name: str
    claim_name: str
    claim_read_only: bool
    bound_volume_name: str
    init_container: str
    init_exit_code: int
    init_finished: bool
    artifact_path: str
    artifact_sub_path: str
    artifact_size_bytes: int
    artifact_sha256: str
    artifact_inode: str
    artifact_mtime_epoch: int
    ready: bool


@dataclass(frozen=True, slots=True)
class AcquisitionFacts:
    """What the acquisition hook did, and whether it did it twice."""

    job_count_before: int
    job_count_after: int
    job_uid_before: str
    job_uid_after: str
    install_log: str


@dataclass(frozen=True, slots=True)
class TimingFacts:
    """Wall-clock offsets from one origin the operating script fixed.

    Differences only. The record carries no timestamp, and what it does carry is
    one run on one host: `docs/architecture/decisions/ADR-0005-evidence-and-measurement.md`
    is why none of it is published as a benchmark.
    """

    deleted_at_ms: int
    replacement_scheduled_at_ms: int
    replacement_ready_at_ms: int
    recovered_at_ms: int

    @property
    def replacement_ms(self) -> int:
        return self.replacement_ready_at_ms - self.deleted_at_ms

    @property
    def recovery_ms(self) -> int:
        return self.recovered_at_ms - self.deleted_at_ms


@dataclass(frozen=True, slots=True)
class LifecycleFacts:
    """Everything the operating script measured, after this module checked it."""

    provider: str
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
    release_revision_before: int
    release_revision_after: int
    claim_uid: str
    claim_bound_volume_before: str
    claim_bound_volume_after: str
    before: PodFacts
    after: PodFacts
    acquisition: AcquisitionFacts
    timings: TimingFacts


def _pod(reader: _Facts, record: Mapping[str, Any], field: str) -> PodFacts:
    return PodFacts(
        name=reader.string(record.get("name"), f"{field}.name"),
        uid=reader.string(record.get("uid"), f"{field}.uid"),
        owner_kind=reader.string(record.get("ownerKind"), f"{field}.ownerKind"),
        owner_name=reader.string(record.get("ownerName"), f"{field}.ownerName"),
        node_name=reader.string(record.get("nodeName"), f"{field}.nodeName"),
        claim_name=reader.string(record.get("claimName"), f"{field}.claimName"),
        claim_read_only=reader.boolean(
            record.get("claimReadOnly"), f"{field}.claimReadOnly"
        ),
        bound_volume_name=reader.string(
            record.get("boundVolumeName"), f"{field}.boundVolumeName"
        ),
        init_container=reader.string(
            record.get("initContainer"), f"{field}.initContainer"
        ),
        # -1 is what the operating script writes when the init container has no
        # terminated state at all, which is a fact about the pod rather than a
        # malformed field -- and it is exactly the case
        # `requireIntegrityInitContainerSucceeded` exists to refuse.
        init_exit_code=reader.integer(
            record.get("initExitCode"), f"{field}.initExitCode", minimum=-1
        ),
        init_finished=reader.boolean(
            record.get("initFinished"), f"{field}.initFinished"
        ),
        artifact_path=reader.string(
            record.get("artifactPath"), f"{field}.artifactPath"
        ),
        artifact_sub_path=reader.string(
            record.get("artifactSubPath"), f"{field}.artifactSubPath"
        ),
        artifact_size_bytes=reader.integer(
            record.get("artifactSizeBytes"), f"{field}.artifactSizeBytes", minimum=1
        ),
        artifact_sha256=reader.string(
            record.get("artifactSha256"), f"{field}.artifactSha256"
        ),
        artifact_inode=reader.string(
            record.get("artifactInode"), f"{field}.artifactInode"
        ),
        artifact_mtime_epoch=reader.integer(
            record.get("artifactMtimeEpoch"), f"{field}.artifactMtimeEpoch", minimum=1
        ),
        ready=reader.boolean(record.get("ready"), f"{field}.ready"),
    )


def load_lifecycle_facts(
    experiment: Experiment, *, repo_root: Path = REPO_ROOT
) -> LifecycleFacts:
    """Read what the script measured across the replacement, untrusted."""
    reader = _Facts(STAGE_LOAD)
    document = reader.document(
        experiment.artifact_path(experiment.lifecycle_file, repo_root),
        "lifecycle facts",
    )
    cluster = reader.object(document.get("cluster"), "cluster")
    tooling = reader.object(document.get("tooling"), "tooling")
    release = reader.object(document.get("release"), "release")
    configuration = reader.object(document.get("configuration"), "configuration")
    claim = reader.object(document.get("claim"), "claim")
    acquisition = reader.object(document.get("acquisition"), "acquisition")
    timings = reader.object(document.get("timings"), "timings")
    return LifecycleFacts(
        provider=reader.string(cluster.get("provider"), "cluster.provider"),
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
        release_revision_before=reader.integer(
            release.get("revisionBefore"), "release.revisionBefore", minimum=1
        ),
        release_revision_after=reader.integer(
            release.get("revisionAfter"), "release.revisionAfter", minimum=1
        ),
        claim_uid=reader.string(claim.get("uid"), "claim.uid"),
        claim_bound_volume_before=reader.string(
            claim.get("boundVolumeBefore"), "claim.boundVolumeBefore"
        ),
        claim_bound_volume_after=reader.string(
            claim.get("boundVolumeAfter"), "claim.boundVolumeAfter"
        ),
        before=_pod(reader, reader.object(document.get("before"), "before"), "before"),
        after=_pod(reader, reader.object(document.get("after"), "after"), "after"),
        acquisition=AcquisitionFacts(
            job_count_before=reader.integer(
                acquisition.get("jobCountBefore"), "acquisition.jobCountBefore"
            ),
            job_count_after=reader.integer(
                acquisition.get("jobCountAfter"), "acquisition.jobCountAfter"
            ),
            job_uid_before=reader.optional_string(
                acquisition.get("jobUidBefore"), "acquisition.jobUidBefore"
            ),
            job_uid_after=reader.optional_string(
                acquisition.get("jobUidAfter"), "acquisition.jobUidAfter"
            ),
            install_log=reader.optional_string(
                acquisition.get("installLog"), "acquisition.installLog"
            ),
        ),
        timings=TimingFacts(
            deleted_at_ms=reader.integer(
                timings.get("deletedAtMs"), "timings.deletedAtMs"
            ),
            replacement_scheduled_at_ms=reader.integer(
                timings.get("replacementScheduledAtMs"),
                "timings.replacementScheduledAtMs",
            ),
            replacement_ready_at_ms=reader.integer(
                timings.get("replacementReadyAtMs"), "timings.replacementReadyAtMs"
            ),
            recovered_at_ms=reader.integer(
                timings.get("recoveredAtMs"), "timings.recoveredAtMs"
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class ReadinessSample:
    """One reading of the serving Deployment's ready replica count."""

    at_ms: int
    ready_replicas: int
    pod_name: str


@dataclass(frozen=True, slots=True)
class ReadinessObservations:
    """What readiness looked like across the replacement."""

    samples: tuple[ReadinessSample, ...]

    @property
    def observed_not_ready(self) -> int:
        return sum(1 for sample in self.samples if sample.ready_replicas == 0)

    @property
    def observed_ready(self) -> int:
        return sum(1 for sample in self.samples if sample.ready_replicas > 0)


def load_readiness_observations(
    experiment: Experiment, *, repo_root: Path = REPO_ROOT
) -> ReadinessObservations:
    reader = _Facts(STAGE_REPLACEMENT)
    document = reader.document(
        experiment.artifact_path(experiment.readiness_file, repo_root),
        "readiness observations",
    )
    samples = tuple(
        ReadinessSample(
            at_ms=reader.integer(
                reader.object(entry, f"samples[{index}]").get("atMs"),
                f"samples[{index}].atMs",
            ),
            ready_replicas=reader.integer(
                reader.object(entry, f"samples[{index}]").get("readyReplicas"),
                f"samples[{index}].readyReplicas",
            ),
            pod_name=reader.optional_string(
                reader.object(entry, f"samples[{index}]").get("podName"),
                f"samples[{index}].podName",
            ),
        )
        for index, entry in enumerate(
            reader.entries(document.get("samples"), "samples")
        )
    )
    return ReadinessObservations(samples=samples)


@dataclass(frozen=True, slots=True)
class BaselineCompletion:
    """One completion the release served before anything was deleted.

    "Real inference succeeds again" needs a *before*, and the release's own
    in-cluster connection test is not it: that asks two Services for a health
    endpoint, which a runtime that loaded no weights would still answer. This is
    the same call the recovery makes, made first, so the two can be compared.
    """

    status: int
    adapter_kind: str
    model_identifier: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def load_baseline_completion(
    experiment: Experiment, *, repo_root: Path = REPO_ROOT
) -> BaselineCompletion:
    reader = _Facts(STAGE_BASELINE)
    document = reader.document(
        experiment.artifact_path(experiment.baseline_completion_file, repo_root),
        "baseline completion",
    )
    return BaselineCompletion(
        status=reader.integer(document.get("status"), "status", minimum=100),
        adapter_kind=reader.string(document.get("adapterKind"), "adapterKind"),
        model_identifier=reader.string(
            document.get("modelIdentifier"), "modelIdentifier"
        ),
        prompt_tokens=reader.integer(document.get("promptTokens"), "promptTokens"),
        completion_tokens=reader.integer(
            document.get("completionTokens"), "completionTokens"
        ),
        total_tokens=reader.integer(document.get("totalTokens"), "totalTokens"),
    )


@dataclass(frozen=True, slots=True)
class CleanupFacts:
    """What the uninstall left behind, and what it deliberately did not remove."""

    release_removed: bool
    release_objects_remaining: int
    claim_present: bool
    namespace_present: bool


def load_cleanup_facts(
    experiment: Experiment, *, repo_root: Path = REPO_ROOT
) -> CleanupFacts:
    reader = _Facts(STAGE_CLEANUP)
    document = reader.document(
        experiment.artifact_path(experiment.cleanup_file, repo_root), "cleanup facts"
    )
    return CleanupFacts(
        release_removed=reader.boolean(
            document.get("releaseRemoved"), "releaseRemoved"
        ),
        release_objects_remaining=reader.integer(
            document.get("releaseObjectsRemaining"), "releaseObjectsRemaining"
        ),
        claim_present=reader.boolean(document.get("claimPresent"), "claimPresent"),
        namespace_present=reader.boolean(
            document.get("namespacePresent"), "namespacePresent"
        ),
    )


# -- what the collected facts have to say --------------------------------------


def _check_environment(experiment: Experiment, facts: LifecycleFacts) -> None:
    matches = [
        entry for entry in experiment.clusters if entry.provider_id == facts.provider
    ]
    if not matches:
        raise ExperimentFailed(
            f"the collected facts name environment provider '{facts.provider}', "
            "which this experiment does not describe",
            STAGE_PREREQUISITES,
        )
    target = matches[0]
    if facts.cluster_name != target.name or facts.kube_context != target.context:
        raise ExperimentFailed(
            f"the collected facts describe cluster '{facts.cluster_name}' on "
            f"context '{facts.kube_context}', not this project's",
            STAGE_PREREQUISITES,
        )
    if not facts.node_image_digest:
        raise ExperimentFailed(
            "the collected facts do not name the node image the run used",
            STAGE_PREREQUISITES,
        )
    if (
        experiment.require_pinned_node_image
        and target.node_image_pinned
        and facts.node_image_digest != target.node_image_digest
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
    if (
        experiment.require_pinned_model_revision
        and facts.model_revision != load_manifest().revision
    ):
        raise ExperimentFailed(
            "the installed release does not name the pinned model revision",
            STAGE_PREREQUISITES,
        )


def _check_baseline(experiment: Experiment, facts: LifecycleFacts) -> None:
    before = facts.before
    if not before.ready:
        raise ExperimentFailed(
            "the pod this experiment deleted was not ready before it was deleted, "
            "so there was no known-good state to recover to",
            STAGE_BASELINE,
        )
    if before.claim_name != experiment.model_cache.claim_name:
        raise ExperimentFailed(
            f"the pod mounted claim '{before.claim_name}' rather than the "
            f"Terraform-owned '{experiment.model_cache.claim_name}'",
            STAGE_BASELINE,
        )
    if experiment.model_cache.require_read_only_mount and not before.claim_read_only:
        raise ExperimentFailed(
            "the serving runtime mounted the model cache writable. The claim is a "
            "prerequisite this release is a guest in, and a serving replica that "
            "could write it would be a second writer nobody decided on",
            STAGE_BASELINE,
        )
    if before.init_container != experiment.model_cache.verification_init_container:
        raise ExperimentFailed(
            "the collected facts name an integrity init container the chart does "
            "not render",
            STAGE_BASELINE,
        )
    manifest = load_manifest()
    if before.artifact_size_bytes != manifest.expected_size_bytes:
        raise ExperimentFailed(
            "the artifact on the claim before the deletion is not the pinned byte "
            "count, so the baseline was not the pinned artifact",
            STAGE_BASELINE,
        )
    if before.artifact_sha256 != manifest.sha256:
        raise ExperimentFailed(
            "the artifact on the claim before the deletion is not the pinned SHA-256",
            STAGE_BASELINE,
        )
    # The revision scoping is the mount's, not the container's. The claim is
    # mounted with a `subPath` naming the repository and the revision, and the
    # container therefore sees the artifact at a flat path with no revision in
    # it -- so asking the in-container path would be asking the wrong string and
    # would fail a correctly scoped mount.
    if experiment.model_cache.require_revision_scoped_artifact and (
        facts.model_revision not in before.artifact_sub_path
    ):
        raise ExperimentFailed(
            "the model cache is not mounted at a subPath scoped to the declared "
            "model revision, so one revision's bytes could be another's",
            STAGE_BASELINE,
        )


def _check_baseline_completion(
    experiment: Experiment, facts: LifecycleFacts, baseline: BaselineCompletion
) -> None:
    """The release answered for real before anything was deleted."""
    if not experiment.require_inference_before_and_after:
        return
    if baseline.status != 200:
        raise ExperimentFailed(
            f"the release answered {baseline.status} before the deletion, so "
            "there was no working inference to recover",
            STAGE_BASELINE,
        )
    if baseline.adapter_kind != experiment.required_adapter_kind:
        raise ExperimentFailed(
            "the completion before the deletion was not served by the real adapter",
            STAGE_BASELINE,
        )
    if baseline.model_identifier != facts.model_identifier:
        raise ExperimentFailed(
            "the completion before the deletion names a model the collected "
            "configuration does not",
            STAGE_BASELINE,
        )
    if experiment.require_usage_counts and (
        baseline.prompt_tokens <= 0
        or baseline.completion_tokens <= 0
        or baseline.prompt_tokens + baseline.completion_tokens != baseline.total_tokens
    ):
        raise ExperimentFailed(
            "the completion before the deletion reports no usable token counts",
            STAGE_BASELINE,
        )


def _check_replacement(experiment: Experiment, facts: LifecycleFacts) -> None:
    policy = experiment.replacement
    before, after = facts.before, facts.after
    if policy.require_different_pod_name and after.name == before.name:
        raise ExperimentFailed(
            "the pod after the deletion carries the same name as the pod before "
            "it, so nothing was replaced",
            STAGE_REPLACEMENT,
        )
    if policy.require_different_pod_uid and after.uid == before.uid:
        raise ExperimentFailed(
            "the pod after the deletion carries the same UID as the pod before "
            "it. A container that restarted inside the same pod is a different "
            "experiment, one layer down",
            STAGE_REPLACEMENT,
        )
    if policy.require_same_deployment_owner and (
        after.owner_kind != before.owner_kind or after.owner_name != before.owner_name
    ):
        raise ExperimentFailed(
            "the replacement pod was not created by the workload that owned the "
            "deleted one",
            STAGE_REPLACEMENT,
        )
    if not after.ready:
        raise ExperimentFailed(
            "the replacement pod never became ready", STAGE_REPLACEMENT
        )
    if policy.require_integrity_init_container_succeeded and (
        not after.init_finished or after.init_exit_code != 0
    ):
        raise ExperimentFailed(
            "the replacement pod's integrity init container did not run to a zero "
            "exit, so nothing compared the surviving artifact against its pins "
            "inside the cluster",
            STAGE_REPLACEMENT,
        )
    if policy.require_no_release_revision_change and (
        facts.release_revision_after != facts.release_revision_before
    ):
        raise ExperimentFailed(
            "the release revision moved across the deletion. Deleting a pod is "
            "not a release change, and a revision that moved means something "
            "else did",
            STAGE_REPLACEMENT,
        )


def _check_persistence(experiment: Experiment, facts: LifecycleFacts) -> None:
    cache = experiment.model_cache
    before, after = facts.before, facts.after
    if cache.require_same_claim_remounted and after.claim_name != before.claim_name:
        raise ExperimentFailed(
            "the replacement pod mounted a different claim",
            STAGE_REPLACEMENT,
        )
    # Two facts, and they are not the same fact. `bound_volume_name` is the name
    # the *pod* gives the volume in its own spec -- the handle its containers
    # mount -- and `claim_bound_volume_*` is the PersistentVolume the *claim* is
    # bound to, read off the claim either side of the replacement. Comparing one
    # against the other compares a pod-local name to a cluster-scoped one, which
    # is what the first real run of this experiment did: it refused a replacement
    # that had mounted exactly the right volume.
    if cache.require_same_bound_volume:
        if after.bound_volume_name != before.bound_volume_name:
            raise ExperimentFailed(
                "the replacement pod mounts the claim under a different volume "
                "name than the pod it replaced",
                STAGE_REPLACEMENT,
            )
        if facts.claim_bound_volume_after != facts.claim_bound_volume_before:
            raise ExperimentFailed(
                "the claim is bound to a different PersistentVolume after the "
                "replacement, so what survived is not what was there",
                STAGE_REPLACEMENT,
            )
    if cache.require_read_only_mount and not after.claim_read_only:
        raise ExperimentFailed(
            "the replacement pod mounted the model cache writable",
            STAGE_REPLACEMENT,
        )
    if cache.require_artifact_byte_count_unchanged and (
        after.artifact_size_bytes != before.artifact_size_bytes
    ):
        raise ExperimentFailed(
            "the artifact's byte count changed across the replacement",
            STAGE_REPLACEMENT,
        )
    if cache.require_artifact_digest_unchanged and (
        after.artifact_sha256 != before.artifact_sha256
    ):
        raise ExperimentFailed(
            "the artifact's SHA-256 changed across the replacement, so the bytes "
            "the replacement loaded are not the bytes that were there",
            STAGE_REPLACEMENT,
        )
    if (
        after.artifact_path != before.artifact_path
        or after.artifact_sub_path != before.artifact_sub_path
    ):
        raise ExperimentFailed(
            "the replacement pod read the artifact from a different path, or "
            "through a different subPath of the claim",
            STAGE_REPLACEMENT,
        )
    # The two that separate "the same file survived" from "an identical file was
    # put back". A byte count and a digest are equal either way, because an
    # acquisition that re-copied the pinned artifact would reproduce both. What
    # an acquisition cannot reproduce is the inode and the modification time: it
    # writes a temporary file and renames it over the artifact, which allocates a
    # new inode and stamps a new mtime.
    if cache.require_artifact_inode_unchanged and (
        after.artifact_inode != before.artifact_inode
    ):
        raise ExperimentFailed(
            "the artifact carries a different inode after the replacement, so the "
            "file the replacement read was written rather than found",
            STAGE_REPLACEMENT,
        )
    if cache.require_artifact_mtime_unchanged and (
        after.artifact_mtime_epoch != before.artifact_mtime_epoch
    ):
        raise ExperimentFailed(
            "the artifact's modification time moved across the replacement, so "
            "something rewrote it",
            STAGE_REPLACEMENT,
        )


def _check_acquisition(experiment: Experiment, facts: LifecycleFacts) -> None:
    policy = experiment.acquisition
    acquisition = facts.acquisition
    if policy.require_job_count_unchanged and (
        acquisition.job_count_after != acquisition.job_count_before
    ):
        raise ExperimentFailed(
            f"the namespace held {acquisition.job_count_before} acquisition "
            f"job(s) before the deletion and {acquisition.job_count_after} after "
            "it. Deleting a pod is neither an install nor an upgrade, so no hook "
            "may have run",
            STAGE_REPLACEMENT,
        )
    if (
        policy.require_hook_not_triggered_by_pod_deletion
        and acquisition.job_uid_after != acquisition.job_uid_before
    ):
        raise ExperimentFailed(
            "an acquisition job with a different identity exists after the "
            "deletion, so the hook ran again",
            STAGE_REPLACEMENT,
        )
    if experiment.replacement.require_acquisition_not_repeated and (
        facts.after.artifact_inode != facts.before.artifact_inode
        or facts.after.artifact_mtime_epoch != facts.before.artifact_mtime_epoch
    ):
        raise ExperimentFailed(
            "the artifact the replacement read is not the file the deleted pod "
            "read. Something acquired it again, which is the thing this "
            "experiment exists to rule out",
            STAGE_REPLACEMENT,
        )


def _check_timings(experiment: Experiment, facts: LifecycleFacts) -> None:
    timings = facts.timings
    ordered = (
        timings.deleted_at_ms,
        timings.replacement_scheduled_at_ms,
        timings.replacement_ready_at_ms,
        timings.recovered_at_ms,
    )
    if list(ordered) != sorted(ordered):
        raise ExperimentFailed(
            "the collected timings are not in the order the experiment performs them",
            STAGE_RECOVERY,
        )
    if timings.replacement_ms > experiment.budgets.replacement_ms:
        raise ExperimentFailed(
            "the replacement took longer than its budget", STAGE_REPLACEMENT
        )
    if timings.recovery_ms > experiment.budgets.recovery_ms:
        raise ExperimentFailed(
            "the recovery took longer than its budget", STAGE_RECOVERY
        )


def _check_readiness(
    experiment: Experiment, observations: ReadinessObservations
) -> None:
    plan = experiment.observation
    policy = experiment.replacement
    if len(observations.samples) < plan.minimum_samples:
        raise ExperimentFailed(
            f"the readiness record holds {len(observations.samples)} sample(s) "
            f"and this experiment requires at least {plan.minimum_samples}",
            STAGE_REPLACEMENT,
        )
    if policy.require_readiness_observed_false and not observations.observed_not_ready:
        raise ExperimentFailed(
            "readiness was never observed at zero, so nothing here shows the "
            "serving Deployment noticed the pod was gone. A replacement nobody "
            "saw happen is a replacement this record cannot describe",
            STAGE_REPLACEMENT,
        )
    if policy.require_readiness_observed_true and not observations.observed_ready:
        raise ExperimentFailed(
            "readiness was never observed above zero after the deletion",
            STAGE_REPLACEMENT,
        )


def _check_cleanup(experiment: Experiment, cleanup: CleanupFacts) -> None:
    if not cleanup.release_removed:
        raise ExperimentFailed("the release was not removed", STAGE_CLEANUP)
    if cleanup.release_objects_remaining:
        raise ExperimentFailed(
            f"{cleanup.release_objects_remaining} object(s) carrying the "
            "release's instance label remained after the uninstall",
            STAGE_CLEANUP,
        )
    if not cleanup.claim_present or not cleanup.namespace_present:
        raise ExperimentFailed(
            "the uninstall removed the Terraform-owned namespace or claim. "
            "`helm uninstall` removes the release and nothing else "
            "(docs/architecture/resource-ownership.md)",
            STAGE_CLEANUP,
        )


# -- the two calls that establish a real model answered again ------------------


@dataclass(frozen=True, slots=True)
class RecoveredIdentity:
    """What the release published about itself after the replacement."""

    adapter_kind: str
    model_identifier: str
    runtime_name: str
    runtime_version: str
    model_revision: str
    token_usage_declared: bool


@dataclass(frozen=True, slots=True)
class RecoveredCompletion:
    """One completion served after the replacement; text deliberately not kept."""

    status: int
    elapsed_ms: int
    completion_characters: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    request_id_echoed: bool
    correlation_id_echoed: bool


def require_forwarded_base_url(base_url: str, baseline: Certification) -> str:
    """Reuse the certification's forward guard rather than write a second one."""
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


def _reached(call: Callable[[], ApiResponse], stage: str) -> ApiResponse:
    try:
        return call()
    except CertificationError as error:
        raise ExperimentFailed(
            "the forwarded InferOps Service could not be reached", stage
        ) from error


def _refuse_mock(experiment: Experiment, value: str, field: str, stage: str) -> None:
    if experiment.prohibited_identity_substring in value.lower():
        raise ExperimentFailed(
            f"the release published '{value}' as its {field}, which carries mock "
            "identity. A recovery that recovered a mock is not a recovery of real "
            "inference",
            stage,
        )


def observe_readiness(
    experiment: Experiment, *, base_url: str, get: ApiGet, stage: str
) -> None:
    """Ask the forwarded API for readiness before anything is asserted of it."""
    response = _reached(
        lambda: get(
            f"{base_url}{experiment.readiness_path}",
            experiment.request_timeout_ms / 1000,
        ),
        stage,
    )
    if response.status != 200:
        raise ExperimentFailed(
            f"the release answered {response.status} on "
            f"{experiment.readiness_path} rather than reporting itself ready",
            stage,
        )


def observe_identity(
    experiment: Experiment,
    facts: LifecycleFacts,
    *,
    base_url: str,
    get: ApiGet,
    stage: str,
) -> RecoveredIdentity:
    """Read what the release says it is, through its own Service."""
    response = _reached(
        lambda: get(
            f"{base_url}{experiment.models_path}",
            experiment.request_timeout_ms / 1000,
        ),
        stage,
    )
    if response.status != 200:
        raise ExperimentFailed(
            f"the release answered {response.status} on {experiment.models_path}",
            stage,
        )
    body = _mapping(response.body, "root", stage)
    extension = _mapping(body.get(EXTENSION_MEMBER), EXTENSION_MEMBER, stage)
    runtime = _mapping(extension.get("runtime"), "runtime", stage)
    capabilities = _mapping(extension.get("capabilities"), "capabilities", stage)
    entries = body.get("data")
    if not isinstance(entries, list) or len(entries) != 1:
        raise ExperimentFailed("the release must serve exactly one model", stage)
    identity = RecoveredIdentity(
        adapter_kind=_text(
            extension.get(EXTENSION_ADAPTER_KIND), EXTENSION_ADAPTER_KIND, stage
        ),
        model_identifier=_text(
            _mapping(entries[0], "data[0]", stage).get("id"), "data[0].id", stage
        ),
        runtime_name=_text(runtime.get("name"), "runtime.name", stage),
        runtime_version=_text(runtime.get("version"), "runtime.version", stage),
        model_revision=_text(
            runtime.get("modelRevision"), "runtime.modelRevision", stage
        ),
        token_usage_declared=capabilities.get(CAPABILITY_TOKEN_USAGE) is True,
    )
    if identity.adapter_kind != experiment.required_adapter_kind:
        raise ExperimentFailed(
            f"the release publishes adapter kind '{identity.adapter_kind}' rather "
            f"than '{experiment.required_adapter_kind}'",
            stage,
        )
    if identity.runtime_name != LLAMA_SERVER_RUNTIME_NAME:
        raise ExperimentFailed("the release names an unselected runtime", stage)
    if identity.model_identifier != facts.model_identifier:
        raise ExperimentFailed(
            "the release publishes a model the collected configuration does not name",
            stage,
        )
    if (
        experiment.require_pinned_model_revision
        and identity.model_revision != load_manifest().revision
    ):
        raise ExperimentFailed(
            "the release does not publish the pinned model revision", stage
        )
    if experiment.require_usage_counts and not identity.token_usage_declared:
        raise ExperimentFailed(
            "the release declares token usage unsupported, which is mock "
            "capability metadata",
            stage,
        )
    for field, value in (
        ("adapter kind", identity.adapter_kind),
        ("model identifier", identity.model_identifier),
        ("runtime name", identity.runtime_name),
        ("runtime version", identity.runtime_version),
        ("model revision", identity.model_revision),
    ):
        _refuse_mock(experiment, value, field, stage)
    return identity


def observe_completion(
    experiment: Experiment,
    facts: LifecycleFacts,
    *,
    base_url: str,
    post: ApiPost,
    stage: str,
    clock: Callable[[], float] = time.monotonic,
) -> RecoveredCompletion:
    """Send one request and hold the answer to every rule."""
    request_id = experiment.request_id(stage)
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
        ),
        stage,
    )
    elapsed_ms = max(0, round((clock() - started) * 1000))
    if response.status != 200:
        raise ExperimentFailed(
            "the release did not return a completion, so what recovered is a pod "
            "rather than real inference",
            stage,
        )
    body = _mapping(response.body, "root", stage)
    extension = _mapping(body.get(EXTENSION_MEMBER), EXTENSION_MEMBER, stage)
    if extension.get(EXTENSION_ADAPTER_KIND) != experiment.required_adapter_kind:
        raise ExperimentFailed(
            "the completion was not served by the real adapter", stage
        )
    _refuse_mock(
        experiment,
        _text(extension.get(EXTENSION_MODEL_REF), EXTENSION_MODEL_REF, stage),
        "model reference",
        stage,
    )
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ExperimentFailed("the completion carries no choices", stage)
    message = _mapping(
        _mapping(choices[0], "choices[0]", stage).get("message"),
        "choices[0].message",
        stage,
    )
    content = message.get("content")
    if not isinstance(content, str) or (
        experiment.require_non_empty_content and not content.strip()
    ):
        raise ExperimentFailed(
            "the completion carries no content, so nothing was generated", stage
        )
    usage = _mapping(body.get("usage"), "usage", stage)
    counts: dict[str, int] = {}
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            if experiment.require_usage_counts:
                raise ExperimentFailed(
                    f"the completion's '{name}' is not a positive integer, so the "
                    "runtime reported no usage",
                    stage,
                )
            counts[name] = 0
        else:
            counts[name] = value
    if experiment.require_usage_counts and (
        counts["prompt_tokens"] + counts["completion_tokens"] != counts["total_tokens"]
    ):
        raise ExperimentFailed(
            "the completion's token counts do not sum, so they were not derived "
            "from one runtime's accounting",
            stage,
        )
    return RecoveredCompletion(
        status=response.status,
        elapsed_ms=elapsed_ms,
        completion_characters=len(content),
        prompt_tokens=counts["prompt_tokens"],
        completion_tokens=counts["completion_tokens"],
        total_tokens=counts["total_tokens"],
        request_id_echoed=response.headers.get(REQUEST_ID_HEADER) == request_id,
        correlation_id_echoed=(
            response.headers.get(CORRELATION_ID_HEADER) == experiment.correlation_id
        ),
    )


# -- the result ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    """Everything a record needs, after every check has passed."""

    experiment: Experiment
    facts: LifecycleFacts
    readiness: ReadinessObservations
    baseline: BaselineCompletion
    identity: RecoveredIdentity
    completion: RecoveredCompletion


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """What is written instead of a record when a run stops."""

    stage: str
    reason: str


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
    """Hold one collected run to the descriptor, or raise naming the stage."""
    if not confirmed:
        raise ExperimentRefused(
            "this experiment deletes a running pod in a real cluster and sends a "
            "real inference request. It runs only with explicit confirmation",
            STAGE_PREREQUISITES,
        )
    certification = baseline if baseline is not None else load_certification()
    url = require_forwarded_base_url(base_url, certification)
    facts = load_lifecycle_facts(experiment, repo_root=repo_root)
    readiness = load_readiness_observations(experiment, repo_root=repo_root)
    baseline_completion = load_baseline_completion(experiment, repo_root=repo_root)
    _check_environment(experiment, facts)
    _check_baseline(experiment, facts)
    _check_baseline_completion(experiment, facts, baseline_completion)
    _check_replacement(experiment, facts)
    _check_persistence(experiment, facts)
    _check_acquisition(experiment, facts)
    _check_readiness(experiment, readiness)
    _check_timings(experiment, facts)
    observe_readiness(experiment, base_url=url, get=get, stage=STAGE_RECOVERY)
    identity = observe_identity(
        experiment, facts, base_url=url, get=get, stage=STAGE_RECOVERY
    )
    completion = observe_completion(
        experiment, facts, base_url=url, post=post, stage=STAGE_RECOVERY, clock=clock
    )
    return ExperimentResult(
        experiment=experiment,
        facts=facts,
        readiness=readiness,
        baseline=baseline_completion,
        identity=identity,
        completion=completion,
    )


def merge_cleanup(
    experiment: Experiment, *, repo_root: Path = REPO_ROOT
) -> dict[str, Any]:
    """Add the cleanup outcome to the record this workflow already wrote.

    The teardown happens after everything else has been established, so the
    cleanup member cannot exist when the record is first written and the record
    cannot wait for it: a run that failed its assertions still uninstalls, and a
    record produced only after a successful teardown would be a record that
    disappeared whenever the interesting thing happened.

    So the record is written twice, and the second write adds one member. Nothing
    else is re-derived -- the identity and the completion were observed against a
    release that no longer exists.
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
        "releaseRemoved": cleanup.release_removed,
        "releaseObjectsRemaining": cleanup.release_objects_remaining,
        "claimPresent": cleanup.claim_present,
        "namespacePresent": cleanup.namespace_present,
    }
    return cast(dict[str, Any], document)


def _pod_document(pod: PodFacts) -> dict[str, Any]:
    return {
        "name": pod.name,
        "uid": pod.uid,
        "ownerKind": pod.owner_kind,
        "ownerName": pod.owner_name,
        "nodeName": pod.node_name,
        "claimName": pod.claim_name,
        "claimReadOnly": pod.claim_read_only,
        "boundVolumeName": pod.bound_volume_name,
        "initContainer": pod.init_container,
        "initExitCode": pod.init_exit_code,
        "initFinished": pod.init_finished,
        "artifactPath": pod.artifact_path,
        "artifactSubPath": pod.artifact_sub_path,
        "artifactSizeBytes": pod.artifact_size_bytes,
        "artifactSha256": pod.artifact_sha256,
        "artifactInode": pod.artifact_inode,
        "artifactMtimeEpoch": pod.artifact_mtime_epoch,
        "ready": pod.ready,
    }


def result_document(result: ExperimentResult) -> dict[str, Any]:
    """One whole record, carrying no prompt and no completion text."""
    experiment = result.experiment
    facts = result.facts
    document: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "experimentId": experiment.experiment_id,
        "outcome": "persisted",
        "evidenceClass": experiment.evidence_class,
        "evidenceLabel": experiment.evidence_label,
        "certificationCeiling": experiment.certification_ceiling,
        "lane": experiment.lane,
        "cluster": {
            "provider": facts.provider,
            "name": facts.cluster_name,
            "context": facts.kube_context,
            "serverVersion": facts.server_version,
            "nodeImageDigest": facts.node_image_digest,
            "nodeImagePinnedByInferOps": next(
                entry.node_image_pinned
                for entry in experiment.clusters
                if entry.provider_id == facts.provider
            ),
        },
        "tooling": {"helm": facts.helm_version, "kubectl": facts.kubectl_version},
        "release": {
            "name": facts.release_name,
            "namespace": facts.release_namespace,
            "chart": facts.chart_version,
            "profile": facts.profile,
            "revisionBefore": facts.release_revision_before,
            "revisionAfter": facts.release_revision_after,
        },
        "configuration": {
            "modelIdentifier": facts.model_identifier,
            "modelRevision": facts.model_revision,
        },
        "claim": {
            "name": experiment.model_cache.claim_name,
            "owner": experiment.model_cache.owner,
            "uid": facts.claim_uid,
            "boundVolume": facts.claim_bound_volume_after,
            "boundVolumeUnchanged": (
                facts.claim_bound_volume_after == facts.claim_bound_volume_before
            ),
        },
        "disruption": {
            "mechanism": experiment.disruption.mechanism,
            "target": experiment.disruption.target,
            "scope": experiment.disruption.scope,
            "reversedBy": experiment.disruption.reversed_by,
            "deletedPod": facts.before.name,
        },
        "before": _pod_document(facts.before),
        "after": _pod_document(facts.after),
        "acquisition": {
            "jobCountBefore": facts.acquisition.job_count_before,
            "jobCountAfter": facts.acquisition.job_count_after,
            "jobIdentityUnchanged": (
                facts.acquisition.job_uid_after == facts.acquisition.job_uid_before
            ),
            "installReportedArtifactAlreadyPresent": (
                experiment.acquisition.already_present_signal
                in facts.acquisition.install_log
            ),
            "installLogObserved": bool(facts.acquisition.install_log),
            "artifactInodeUnchanged": (
                facts.after.artifact_inode == facts.before.artifact_inode
            ),
            "artifactMtimeUnchanged": (
                facts.after.artifact_mtime_epoch == facts.before.artifact_mtime_epoch
            ),
            "repeatedForPodReplacement": False,
        },
        "readiness": {
            "samples": len(result.readiness.samples),
            "observedNotReady": result.readiness.observed_not_ready,
            "observedReady": result.readiness.observed_ready,
        },
        "timings": {
            "replacementMs": facts.timings.replacement_ms,
            "recoveryMs": facts.timings.recovery_ms,
            "note": (
                "One replacement, on one host, at one moment. Not a benchmark, a "
                "service-level objective, or an availability figure."
            ),
        },
        "identity": {
            "adapterKind": result.identity.adapter_kind,
            "modelIdentifier": result.identity.model_identifier,
            "runtimeName": result.identity.runtime_name,
            "runtimeVersion": result.identity.runtime_version,
            "modelRevision": result.identity.model_revision,
            "tokenUsageDeclared": result.identity.token_usage_declared,
        },
        "baselineCompletion": {
            "status": result.baseline.status,
            "adapterKind": result.baseline.adapter_kind,
            "promptTokens": result.baseline.prompt_tokens,
            "completionTokens": result.baseline.completion_tokens,
            "totalTokens": result.baseline.total_tokens,
            "generatedTextRetained": False,
        },
        "completion": {
            "status": result.completion.status,
            "elapsedMs": result.completion.elapsed_ms,
            "completionCharacters": result.completion.completion_characters,
            "promptTokens": result.completion.prompt_tokens,
            "completionTokens": result.completion.completion_tokens,
            "totalTokens": result.completion.total_tokens,
            "requestIdEchoed": result.completion.request_id_echoed,
            "correlationIdEchoed": result.completion.correlation_id_echoed,
            "generatedTextRetained": False,
        },
        "limitations": list(experiment.limitations),
    }
    return document


def diagnostics_document(
    experiment: Experiment, diagnostics: Diagnostics
) -> dict[str, Any]:
    """Why a run stopped, in the shape a reader can compare against a record."""
    return {
        "schemaVersion": SCHEMA_VERSION,
        "experimentId": experiment.experiment_id,
        "outcome": "stopped",
        "evidenceClass": experiment.evidence_class,
        "stage": diagnostics.stage,
        "reason": diagnostics.reason,
    }


def ensure_evidence_paths_safe(root: Path, targets: Sequence[Path]) -> None:
    """Refuse the fixed evidence location, or a file in it, that was redirected.

    The same rule the certification and the upgrade/rollback experiment apply to
    their own directories, applied to this one: a symlink or a Windows junction
    anywhere along the path turns "write a record into an ignored directory" into
    "write wherever that link points". `os.path.isjunction` is named beside
    `is_symlink` because a junction is not a symlink and this project is
    developed on Windows.
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

    def write(self, target: Path, document: Mapping[str, Any]) -> Path:
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


def summary_lines(experiment: Experiment) -> Sequence[str]:
    """The offline summary `check` prints, so a reader need not open the JSON."""
    release = experiment.release
    cache = experiment.model_cache
    return (
        f"experiment    {experiment.experiment_id} "
        f"(ceiling {experiment.certification_ceiling}; {experiment.evidence_class})",
        f"lane          {experiment.lane}; outside the default check lane",
        f"chart         {experiment.chart_ref}; profile {release.profile}",
        f"release       {release.name} in {release.namespace}; "
        f"{release.replicas} replica(s) of {release.api_component} and "
        f"{release.runtime_component}",
        f"baseline      agrees with {experiment.baseline_certification_ref}",
        f"stages        {' -> '.join(experiment.stages)}",
        f"disruption    {experiment.disruption.mechanism}: one "
        f"{experiment.disruption.scope} of {experiment.disruption.target}, "
        f"replaced by the {experiment.disruption.reversed_by}",
        "              deletes no declared object, changes no Deployment, no "
        "claim, no release revision, and nothing outside the namespace",
        f"claim         {cache.claim_name}, owned by {cache.owner}, mounted read "
        f"only, verified in the '{cache.verification_init_container}' init "
        "container",
        "persistence   same claim, same bound volume, same revision-scoped path, "
        "same byte count, same SHA-256, same inode, same modification time",
        "replacement   different pod name and UID, same Deployment owner, "
        "readiness observed false then true, init container exit 0",
        "acquisition   no new job, unchanged job identity, and the same inode "
        "and modification time on the artifact either side of the replacement",
        f"budgets       deletion {experiment.budgets.deletion_ms} ms; replacement "
        f"{experiment.budgets.replacement_ms} ms; recovery "
        f"{experiment.budgets.recovery_ms} ms; uninstall "
        f"{experiment.budgets.uninstall_ms} ms",
        f"request       POST {experiment.request_path}; identity GET "
        f"{experiment.models_path}; budget {experiment.request_timeout_ms} ms",
        f"evidence      {experiment.evidence_directory.as_posix()}/"
        f"{experiment.result_file}; "
        f"labelled {experiment.evidence_label}; generated text never retained",
        "cleanup       uninstalls the release; removes neither the Terraform "
        "prerequisites, the model cache claim, nor the cluster",
        f"limitations   {len(experiment.limitations)} stated in the descriptor",
    )
