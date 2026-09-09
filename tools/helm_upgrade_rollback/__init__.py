"""Prove that a release change can be reversed, and say what it cost.

The committed descriptor is the authority for what a run does, and loading it
performs no I/O beyond reading committed files. It is cross-checked against the
Kubernetes real-inference certification, which already decided the cluster, the
release, the request, and eight of the twelve budgets — this experiment installs
the same chart as the same release on the same cluster, so a second set of
numbers describing it would be a second release waiting to be discovered.

Nothing here operates a cluster. `scripts/environment/helm-upgrade-rollback.sh`
owns every kubectl, helm, and terraform invocation, because the guard that
establishes which cluster is being acted on already lives beside those wrappers
and a second implementation of it in another language would be a second guard.
What lives here is the descriptor, the assertions over what the release did
across four revisions, the two calls that establish the rolled-back release
really serves a real model again, and the machine-readable record — labelled
`local real Kubernetes`, and never written from an answer carrying mock identity
or mock capability metadata.

The distinction this module exists to keep is between a rollback Helm recorded
and a rollback the cluster performed. Helm's history says a revision exists.
Whether the rendered configuration went back, whether the injected fault is gone,
and whether a real model answered are three separate questions, asked of the
cluster.
"""

from __future__ import annotations

from .core import (
    CandidateChange,
    CleanupFacts,
    DetectionFacts,
    DetectionPolicy,
    Diagnostics,
    EvidenceDirectory,
    EvidenceUnwritable,
    Experiment,
    ExperimentBudgets,
    ExperimentError,
    ExperimentFailed,
    ExperimentInconclusive,
    ExperimentRefused,
    ExperimentResult,
    FaultInjection,
    ImpactObservations,
    ImpactPlan,
    ImpactProbe,
    LifecycleFacts,
    RecoveryFacts,
    RestoredCompletion,
    RestoredIdentity,
    RollbackPolicy,
    StageFacts,
    diagnostics_document,
    evaluate,
    load_cleanup_facts,
    load_experiment,
    load_impact_observations,
    load_lifecycle_facts,
    merge_cleanup,
    result_document,
)

__all__ = [
    "CandidateChange",
    "CleanupFacts",
    "DetectionFacts",
    "DetectionPolicy",
    "Diagnostics",
    "EvidenceDirectory",
    "EvidenceUnwritable",
    "Experiment",
    "ExperimentBudgets",
    "ExperimentError",
    "ExperimentFailed",
    "ExperimentInconclusive",
    "ExperimentRefused",
    "ExperimentResult",
    "FaultInjection",
    "ImpactObservations",
    "ImpactPlan",
    "ImpactProbe",
    "LifecycleFacts",
    "RecoveryFacts",
    "RestoredCompletion",
    "RestoredIdentity",
    "RollbackPolicy",
    "StageFacts",
    "diagnostics_document",
    "evaluate",
    "load_cleanup_facts",
    "load_experiment",
    "load_impact_observations",
    "load_lifecycle_facts",
    "merge_cleanup",
    "result_document",
]
