"""The RenderedWorkloadRelease as a platform domain object, and its provenance rules.

A release records where one rendered workload release came from: the workload and
version, the digest of the WorkloadContract and of the EnvironmentBinding it was
rendered from, the revisions of the renderer and of the platform defaults, a
release identifier derived from those, and the file name and digest of the Helm
values it produced. This package reads one into typed objects, defines the
canonical form it is hashed and compared in, computes the digests and the
identifier a release records - and the digest of a generated file, by its bytes -
and applies the rules that decide whether a well-formed release is a true one. It
renders nothing, writes nothing, and reads no file.

Start at :func:`parse_rendered_workload_release` for one document,
:func:`check_rendered_workload_release` for the rules on one release, and
:func:`verify_release_sources` to compare a release with the contract and binding
it names. The digests are in ``canonical``; the objects in ``release``; the values
they are built from in ``values``; the supported versions in ``versions``; every
refusal and published rule in ``errors``.

The published document is ``docs/contracts/rendered-workload-release.md`` and the
schema is ``contracts/release/rendered-workload-release.v1alpha1.schema.json``. The
domain reads neither at run time; a test compares this package's copy of every
pattern, vocabulary, bound, and field list with the schema.
"""

from __future__ import annotations

from .canonical import (
    LARGEST_EXACT_INTEGER,
    binding_digest,
    canonical_json,
    canonical_release,
    canonical_sha256,
    contract_digest,
    derive_release_id,
    output_digest,
    release_identity,
)
from .errors import (
    RELEASE_RULES,
    CanonicalFormError,
    MalformedReleaseError,
    ReleaseError,
    ReleaseRefusal,
    ReleaseRule,
    UnsupportedReleaseVersionError,
)
from .parsing import parse_rendered_workload_release
from .provenance import (
    PART_SEPARATORS,
    check_rendered_workload_release,
    credential_positions,
    is_credential_shaped,
    verify_release_sources,
)
from .release import (
    ContractReference,
    EnvironmentBindingReference,
    HelmValuesReference,
    PlatformDefaultsReference,
    ReleaseMetadata,
    ReleaseOutput,
    ReleaseSource,
    RenderedWorkloadRelease,
    RendererReference,
)
from .values import (
    GitRevision,
    LowercaseSemanticVersion,
    ReleaseId,
    ReleaseWorkloadVersion,
    Sha256Hex,
    ValuesFileName,
    parse_release_workload_version,
)
from .versions import (
    RECORDABLE_BINDING_VERSIONS,
    RECORDABLE_CONTRACT_VERSIONS,
    RENDERED_WORKLOAD_RELEASE_KIND,
    SUPPORTED_RELEASE_VERSIONS,
    ReleaseVersion,
    is_supported_release_version,
)

__all__ = [
    "LARGEST_EXACT_INTEGER",
    "PART_SEPARATORS",
    "RECORDABLE_BINDING_VERSIONS",
    "RECORDABLE_CONTRACT_VERSIONS",
    "RELEASE_RULES",
    "RENDERED_WORKLOAD_RELEASE_KIND",
    "SUPPORTED_RELEASE_VERSIONS",
    "CanonicalFormError",
    "ContractReference",
    "EnvironmentBindingReference",
    "GitRevision",
    "HelmValuesReference",
    "LowercaseSemanticVersion",
    "MalformedReleaseError",
    "PlatformDefaultsReference",
    "ReleaseError",
    "ReleaseId",
    "ReleaseMetadata",
    "ReleaseOutput",
    "ReleaseRefusal",
    "ReleaseRule",
    "ReleaseSource",
    "ReleaseVersion",
    "ReleaseWorkloadVersion",
    "RenderedWorkloadRelease",
    "RendererReference",
    "Sha256Hex",
    "UnsupportedReleaseVersionError",
    "ValuesFileName",
    "binding_digest",
    "canonical_json",
    "canonical_release",
    "canonical_sha256",
    "check_rendered_workload_release",
    "contract_digest",
    "credential_positions",
    "derive_release_id",
    "is_credential_shaped",
    "is_supported_release_version",
    "output_digest",
    "parse_release_workload_version",
    "parse_rendered_workload_release",
    "release_identity",
    "verify_release_sources",
]
