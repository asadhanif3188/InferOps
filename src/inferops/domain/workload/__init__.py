"""The WorkloadContract as a platform domain object.

This package holds the platform's own representation of a workload: what it is,
who owns it, what it serves, what it asks for, what it touches, and where the
evidence for its claims lives. It reads a document; it deploys nothing, serves
nothing, and certifies nothing.

Start at :func:`parse_workload_contract`. What it does and does not enforce is in
``parsing``; the objects it produces are in ``contract``; the values those are
built from, and the schema constraints they carry, are in ``values``; the
supported contract versions are in ``versions``.

The published document behind all of it is ``docs/contracts/workload-contract.md``
and the schema is ``contracts/workload/workload-contract.v1alpha1.schema.json``.
The domain does not read either at runtime — a domain object must be constructible
without a file system — and a test compares this package's copy of every pattern,
vocabulary, and bound against the schema so that the two cannot drift apart.
"""

from __future__ import annotations

from .contract import (
    Accelerator,
    Attribution,
    CapabilityDependency,
    Document,
    EvidenceReferences,
    Integrations,
    MockLlmProfile,
    ModelArtifact,
    ModelReference,
    ResourceRequest,
    RuntimeImage,
    ScalingPolicy,
    SecretReference,
    SecurityPolicy,
    SynchronousLlmProfile,
    WorkloadContract,
    WorkloadMetadata,
    WorkloadSpec,
)
from .errors import (
    DomainError,
    InvalidValueError,
    MalformedWorkloadContractError,
    UnsupportedContractVersionError,
    WorkloadContractError,
)
from .parsing import parse_workload_contract
from .values import (
    AcceleratorType,
    AnnotationKey,
    AnnotationValue,
    ArtifactFile,
    ArtifactRepository,
    ConstrainedString,
    DataClassification,
    Description,
    DnsLabel,
    Environment,
    ImageReference,
    KebabCaseName,
    MockDeterminism,
    Profile,
    RepositoryPath,
    ResourceQuantity,
    RuntimeProfile,
    SecretLocator,
    SecretProvider,
    SecretRotation,
    SemanticVersion,
    ServingCapability,
    Sha256Digest,
    UpstreamRevision,
    WorkloadVersion,
)
from .versions import (
    CONTRACT_GROUP,
    SUPPORTED_CONTRACT_VERSIONS,
    WORKLOAD_CONTRACT_KIND,
    ContractVersion,
    is_supported_contract_version,
)

__all__ = [
    "CONTRACT_GROUP",
    "SUPPORTED_CONTRACT_VERSIONS",
    "WORKLOAD_CONTRACT_KIND",
    "Accelerator",
    "AcceleratorType",
    "AnnotationKey",
    "AnnotationValue",
    "ArtifactFile",
    "ArtifactRepository",
    "Attribution",
    "CapabilityDependency",
    "ConstrainedString",
    "ContractVersion",
    "DataClassification",
    "Description",
    "DnsLabel",
    "Document",
    "DomainError",
    "Environment",
    "EvidenceReferences",
    "ImageReference",
    "Integrations",
    "InvalidValueError",
    "KebabCaseName",
    "MalformedWorkloadContractError",
    "MockDeterminism",
    "MockLlmProfile",
    "ModelArtifact",
    "ModelReference",
    "Profile",
    "RepositoryPath",
    "ResourceQuantity",
    "ResourceRequest",
    "RuntimeImage",
    "RuntimeProfile",
    "ScalingPolicy",
    "SecretLocator",
    "SecretProvider",
    "SecretReference",
    "SecretRotation",
    "SecurityPolicy",
    "SemanticVersion",
    "ServingCapability",
    "Sha256Digest",
    "SynchronousLlmProfile",
    "UnsupportedContractVersionError",
    "UpstreamRevision",
    "WorkloadContract",
    "WorkloadContractError",
    "WorkloadMetadata",
    "WorkloadSpec",
    "WorkloadVersion",
    "is_supported_contract_version",
    "parse_workload_contract",
]
