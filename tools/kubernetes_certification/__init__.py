"""Certify the real Kubernetes inference path for the installed InferOps release.

The committed descriptor is the authority for what a Kubernetes `C2` run checks,
and loading it performs no I/O beyond reading committed files. It is cross-checked
against the runtime package, the runtime profile, the local composition, and the
selected model's source record, so a drift between any of them is a refusal rather
than a surprise while a release is installed.

Nothing here operates a cluster. `scripts/environment/kubernetes-certification.sh`
owns every kubectl, helm, and terraform invocation, because the guard that
establishes which cluster is being acted on already lives beside those wrappers
and a second implementation of it in another language would be a second guard.
What lives here is the descriptor, the assertions over what the release answered,
and the machine-readable record — labelled `local real Kubernetes`, and never
written from an answer carrying mock identity or mock capability metadata.
"""

from __future__ import annotations

from .core import (
    Certification,
    CertificationError,
    CertificationFailed,
    ClusterFacts,
    Diagnostics,
    EvidenceDirectory,
    EvidenceUnwritable,
    KubernetesCertificationResult,
    PrerequisiteUnmet,
    certify,
    diagnostics_document,
    load_certification,
    load_cluster_facts,
    result_document,
)

__all__ = [
    "Certification",
    "CertificationError",
    "CertificationFailed",
    "ClusterFacts",
    "Diagnostics",
    "EvidenceDirectory",
    "EvidenceUnwritable",
    "KubernetesCertificationResult",
    "PrerequisiteUnmet",
    "certify",
    "diagnostics_document",
    "load_certification",
    "load_cluster_facts",
    "result_document",
]
