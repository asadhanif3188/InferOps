"""Prove that model artifacts survive a Kubernetes pod restart, and say how.

`V1-S3-003` asked the question and its evidence answered a narrower one honestly:
a container was stopped on the host and another started, and
`docs/proof/serving/v1-s3-003-pr1-restart-reload.md` says in as many words that it
is **not** a pod restart. Nothing could have made it one at the time — no API
image was published and the Terraform-owned claim was never filled. Both of those
exist now, and this is the experiment that was missing.

The committed descriptor is the authority for what a run does, and loading it
performs no I/O beyond reading committed files. It is cross-checked against the
Kubernetes real-inference certification, which already decided the cluster, the
release, the request, and every budget the two share.

Nothing here operates a cluster. `scripts/environment/kubernetes-pod-restart.sh`
owns every kubectl, helm, and terraform invocation, because the guard that
establishes which cluster is being acted on already lives beside those wrappers.
What lives here is the descriptor, the assertions over what the cluster did
across one deleted pod, the two calls that establish real inference came back,
and the machine-readable record.

The distinction this module exists to keep is between a pod that came back and a
model that survived. A pod comes back either way. Whether it is a *different*
pod, whether it mounted the *same* claim, whether the bytes on that claim are the
*same* bytes, and whether anything quietly re-acquired 1.83 GB while nobody was
looking are four separate questions, and each is asked of the cluster.
"""

from __future__ import annotations

from .core import (
    ACQUISITION_ALREADY_PRESENT,
    AcquisitionFacts,
    AcquisitionPolicy,
    BaselineCompletion,
    CleanupFacts,
    Diagnostics,
    Disruption,
    EvidenceDirectory,
    EvidenceUnwritable,
    Experiment,
    ExperimentBudgets,
    ExperimentError,
    ExperimentFailed,
    ExperimentRefused,
    ExperimentResult,
    LifecycleFacts,
    ModelCachePolicy,
    ObservationPlan,
    PodFacts,
    ReadinessObservations,
    ReadinessSample,
    RecoveredCompletion,
    RecoveredIdentity,
    ReplacementPolicy,
    TimingFacts,
    diagnostics_document,
    evaluate,
    load_baseline_completion,
    load_cleanup_facts,
    load_experiment,
    load_lifecycle_facts,
    load_readiness_observations,
    merge_cleanup,
    observe_completion,
    observe_identity,
    observe_readiness,
    require_forwarded_base_url,
    result_document,
    summary_lines,
)

__all__ = [
    "ACQUISITION_ALREADY_PRESENT",
    "AcquisitionFacts",
    "AcquisitionPolicy",
    "BaselineCompletion",
    "CleanupFacts",
    "Diagnostics",
    "Disruption",
    "EvidenceDirectory",
    "EvidenceUnwritable",
    "Experiment",
    "ExperimentBudgets",
    "ExperimentError",
    "ExperimentFailed",
    "ExperimentRefused",
    "ExperimentResult",
    "LifecycleFacts",
    "ModelCachePolicy",
    "ObservationPlan",
    "PodFacts",
    "ReadinessObservations",
    "ReadinessSample",
    "RecoveredCompletion",
    "RecoveredIdentity",
    "ReplacementPolicy",
    "TimingFacts",
    "diagnostics_document",
    "evaluate",
    "load_baseline_completion",
    "load_cleanup_facts",
    "load_experiment",
    "load_lifecycle_facts",
    "load_readiness_observations",
    "merge_cleanup",
    "observe_completion",
    "observe_identity",
    "observe_readiness",
    "require_forwarded_base_url",
    "result_document",
    "summary_lines",
]
