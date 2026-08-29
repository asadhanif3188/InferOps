"""The typed values a workload contract is built out of.

Every constraint in this module is a *single-field structural* constraint that the
published schema already declares: a controlled vocabulary, a format, a length, or
a bound. None of it is a cross-field or matrix rule — no comparison of two
siblings, no compatibility lookup, no judgement about whether a locator looks like
a pasted credential. Those are the semantic layer's, and the pipeline that applies
them is ``V1-S1-001-PR2``.

**This duplicates the schema on purpose, and the duplication is checked.** The
domain cannot import a JSON Schema validator: ``jsonschema`` is a development
dependency, the distribution declares no runtime dependency at all, and a domain
that needed one to construct an object would have made validation a prerequisite
for having a value. So the patterns, vocabularies, and bounds are written here in
Python — and ``tests/domain/test_workload_schema_agreement.py`` reads
``contracts/workload/workload-contract.v1alpha1.schema.json`` and fails if a single
one of them differs from what the schema publishes. Drift is a test failure rather
than a discovery.

A constrained value refuses itself at construction: an object of one of these
types is one whose format was checked, so no consumer has to ask. The refusal
carries the constraint, never the value that failed it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from .errors import InvalidValueError

# --------------------------------------------------------------------------
# Controlled vocabularies
# --------------------------------------------------------------------------


class Profile(StrEnum):
    """``spec.profile``. The kind of workload, and which profile block applies."""

    SYNCHRONOUS_LLM = "synchronous-llm"
    MOCK_LLM = "mock-llm"


class Environment(StrEnum):
    """``spec.environment``. Where the workload is declared to run."""

    CI = "ci"
    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class ServingCapability(StrEnum):
    """``spec.model.servingCapability``. Which serving capability is bound."""

    NATIVE = "inferops-native-serving"
    MOCK = "inferops-mock-serving"


class RuntimeProfile(StrEnum):
    """``spec.model.runtimeProfile``. Sizing intent, not a measured capability."""

    RESOURCE_CONSCIOUS = "resource-conscious"
    BALANCED = "balanced"
    THROUGHPUT_ORIENTED = "throughput-oriented"


class AcceleratorType(StrEnum):
    """``spec.resources.accelerator.type``."""

    NONE = "none"
    INTEGRATED_GPU = "integrated-gpu"
    NVIDIA_GPU = "nvidia-gpu"
    AMD_GPU = "amd-gpu"


class DataClassification(StrEnum):
    """``spec.security.dataClassification``. A closed vocabulary."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class SecretProvider(StrEnum):
    """``spec.security.secretRefs[].provider``. Where a secret is held."""

    KUBERNETES_SECRET = "kubernetes-secret"
    EXTERNAL_SECRET = "external-secret"
    FILE_MOUNT = "file-mount"


class SecretRotation(StrEnum):
    """``spec.security.secretRefs[].rotation``. Who is responsible for rotating."""

    PLATFORM_MANAGED = "platform-managed"
    OWNER_MANAGED = "owner-managed"
    EXTERNAL_MANAGED = "external-managed"


class MockDeterminism(StrEnum):
    """``spec.mockLlm.determinism``. One value: a mock that varies is unassertable."""

    FIXED_FIXTURE = "fixed-fixture"


# --------------------------------------------------------------------------
# Constrained strings
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ConstrainedString:
    """A string whose format was checked when it was constructed.

    Subclasses supply the published constraint. The class attributes are named
    after what the schema calls them so that the drift test reads as a comparison
    rather than as a translation.
    """

    value: str

    #: What the constraint is called in a refusal, in a reader's words.
    NAME: ClassVar[str] = "value"
    #: The published pattern, or None where the schema declares none.
    PATTERN: ClassVar[re.Pattern[str] | None] = None
    MINIMUM_LENGTH: ClassVar[int] = 1
    MAXIMUM_LENGTH: ClassVar[int] = 0
    #: A published ``not``/``pattern`` exclusion, and why it exists.
    FORBIDDEN: ClassVar[re.Pattern[str] | None] = None
    FORBIDDEN_REASON: ClassVar[str] = ""

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidValueError(f"{self.NAME} must be a string")
        length = len(self.value)
        if length < self.MINIMUM_LENGTH or length > self.MAXIMUM_LENGTH:
            raise InvalidValueError(
                f"{self.NAME} must be between {self.MINIMUM_LENGTH} and "
                f"{self.MAXIMUM_LENGTH} characters"
            )
        if self.PATTERN is not None and self.PATTERN.fullmatch(self.value) is None:
            raise InvalidValueError(
                f"{self.NAME} must match the published format {self.PATTERN.pattern}"
            )
        if self.FORBIDDEN is not None and self.FORBIDDEN.search(self.value) is not None:
            raise InvalidValueError(f"{self.NAME} {self.FORBIDDEN_REASON}")

    def __str__(self) -> str:
        return self.value


# Every pattern below is the schema's own, character for character. The schema is
# the published artifact; this is a copy of it that Python can apply, and the copy
# is compared to the original by a test rather than by a reader's eye.
DNS_LABEL_PATTERN: Final = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
KEBAB_CASE_NAME_PATTERN: Final = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
SEMANTIC_VERSION_PATTERN: Final = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
DIGEST_PINNED_IMAGE_REFERENCE_PATTERN: Final = re.compile(
    r"^[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[0-9]+)?"
    r"(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)+@sha256:[0-9a-f]{64}$"
)
SHA256_DIGEST_PATTERN: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA256_HEX_PATTERN: Final = re.compile(r"^[0-9a-f]{40,64}$")
REPOSITORY_PATH_PATTERN: Final = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$")
REPOSITORY_PATH_FORBIDDEN_PATTERN: Final = re.compile(r"(^|/)\.\.(/|$)")
KUBERNETES_QUANTITY_PATTERN: Final = re.compile(
    r"^[0-9]+(\.[0-9]+)?(m|k|M|G|T|P|E|Ki|Mi|Gi|Ti|Pi|Ei)?$"
)
ANNOTATION_KEY_PATTERN: Final = re.compile(
    r"^[a-z0-9]([-a-z0-9.]*[a-z0-9])?/[a-z0-9]([-a-z0-9._]*[a-z0-9])?$"
)
SECRET_LOCATOR_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]*$")
ARTIFACT_REPOSITORY_PATTERN: Final = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)+$"
)
ARTIFACT_FILE_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class DnsLabel(ConstrainedString):
    """A DNS-safe stable identifier: ``workload_id``, ``owner_id``, ``tenant_id``."""

    NAME = "a DNS-safe identifier"
    PATTERN = DNS_LABEL_PATTERN
    MAXIMUM_LENGTH = 63


class KebabCaseName(ConstrainedString):
    """A chosen name: ``modelRef``, ``capabilityRef``, ``costCenter``, secret name."""

    NAME = "a kebab-case name"
    PATTERN = KEBAB_CASE_NAME_PATTERN
    MAXIMUM_LENGTH = 63


class SemanticVersion(ConstrainedString):
    """A semantic version, one of the two forms ``workload_version`` may take."""

    NAME = "a semantic version"
    PATTERN = SEMANTIC_VERSION_PATTERN
    # The schema declares no length bound on this one; the pattern is the
    # constraint. The bound here is a memory guard, not a published rule, and the
    # drift test knows the difference.
    MAXIMUM_LENGTH = 256


class ImageReference(ConstrainedString):
    """An OCI image reference pinned by digest. A tag alone is a movable label."""

    NAME = "a digest-pinned image reference"
    PATTERN = DIGEST_PINNED_IMAGE_REFERENCE_PATTERN
    MAXIMUM_LENGTH = 512


class Sha256Digest(ConstrainedString):
    """A ``sha256:``-prefixed content digest."""

    NAME = "a sha256 digest"
    PATTERN = SHA256_DIGEST_PATTERN
    MAXIMUM_LENGTH = 71


class UpstreamRevision(ConstrainedString):
    """A publisher's revision identifier, as a hexadecimal commit-like string."""

    NAME = "an upstream revision"
    PATTERN = SHA256_HEX_PATTERN
    MAXIMUM_LENGTH = 64


class RepositoryPath(ConstrainedString):
    """A path relative to the repository root.

    Absolute paths, parent traversal, and drive letters are excluded by the
    schema so that a contract cannot carry a personal filesystem path. That is
    the same rule the repository applies to its own diffs, applied to a document.
    """

    NAME = "a repository-relative path"
    PATTERN = REPOSITORY_PATH_PATTERN
    MAXIMUM_LENGTH = 255
    FORBIDDEN = REPOSITORY_PATH_FORBIDDEN_PATTERN
    FORBIDDEN_REASON = "must not traverse out of the repository with '..'"


class ResourceQuantity(ConstrainedString):
    """A resource quantity in documented Kubernetes units, held as written.

    It is deliberately not converted into a number. Two quantities are not
    compared, added, or resolved against a node anywhere in this domain: the unit
    grammar is Kubernetes', and a domain that reimplemented its arithmetic would
    be making a claim about scheduling that nothing here has tested.
    """

    NAME = "a resource quantity"
    PATTERN = KUBERNETES_QUANTITY_PATTERN
    MAXIMUM_LENGTH = 32


class AnnotationKey(ConstrainedString):
    """A namespaced annotation key: ``<dns-domain>/<name>``."""

    NAME = "a namespaced annotation key"
    PATTERN = ANNOTATION_KEY_PATTERN
    MAXIMUM_LENGTH = 253


class AnnotationValue(ConstrainedString):
    """A non-normative annotation value. The schema sets no pattern and no floor."""

    NAME = "an annotation value"
    MINIMUM_LENGTH = 0
    MAXIMUM_LENGTH = 1024


class Description(ConstrainedString):
    """``metadata.description``. Free text, bounded, with no published format."""

    NAME = "a description"
    MAXIMUM_LENGTH = 500


class SecretLocator(ConstrainedString):
    """Where a secret lives. Never the secret.

    The character set excludes whitespace, quotes, and assignment characters. The
    contract document measures what that does and does not catch, and the check
    that closes part of the gap is semantic and belongs to the validation
    pipeline, not to this type.
    """

    NAME = "a secret locator"
    PATTERN = SECRET_LOCATOR_PATTERN
    MAXIMUM_LENGTH = 253


class ArtifactRepository(ConstrainedString):
    """The upstream repository a model artifact is published in."""

    NAME = "an artifact repository"
    PATTERN = ARTIFACT_REPOSITORY_PATTERN
    MAXIMUM_LENGTH = 253


class ArtifactFile(ConstrainedString):
    """The file within that repository. A name, never a path."""

    NAME = "an artifact filename"
    PATTERN = ARTIFACT_FILE_PATTERN
    MAXIMUM_LENGTH = 255


# --------------------------------------------------------------------------
# Published numeric bounds
# --------------------------------------------------------------------------

MINIMUM_REPLICAS_FLOOR: Final = 0
MINIMUM_REPLICAS_CEILING: Final = 100
MAXIMUM_REPLICAS_FLOOR: Final = 1
MAXIMUM_REPLICAS_CEILING: Final = 100
ACCELERATOR_COUNT_FLOOR: Final = 0
ACCELERATOR_COUNT_CEILING: Final = 64
ARTIFACT_SIZE_BYTES_FLOOR: Final = 1
MAXIMUM_SECRET_REFERENCES: Final = 32
MAXIMUM_PROOF_REFERENCES: Final = 16


@dataclass(frozen=True, slots=True)
class WorkloadVersion:
    """``workload_version``: an immutable release identity, in one of two forms.

    The schema accepts a semantic version **or** an image reference pinned by
    digest, and which one an author chose is information a later component may
    need — a digest is already resolved, a semantic version is not. Collapsing
    both into a string would throw that away, so the form is kept.
    """

    semantic_version: SemanticVersion | None = None
    image_reference: ImageReference | None = None

    def __post_init__(self) -> None:
        supplied = [self.semantic_version, self.image_reference]
        if sum(entry is not None for entry in supplied) != 1:
            raise InvalidValueError(
                "a workload version is either a semantic version or an image "
                "reference pinned by digest, and is exactly one of the two"
            )

    @classmethod
    def parse(cls, value: str) -> WorkloadVersion:
        """Read whichever of the two published forms the value is."""
        if SEMANTIC_VERSION_PATTERN.fullmatch(value) is not None:
            return cls(semantic_version=SemanticVersion(value))
        if DIGEST_PINNED_IMAGE_REFERENCE_PATTERN.fullmatch(value) is not None:
            return cls(image_reference=ImageReference(value))
        raise InvalidValueError(
            "a workload version must be a semantic version or an image reference "
            "pinned by digest; a tag alone is a movable label and is not accepted"
        )

    @property
    def is_digest_pinned(self) -> bool:
        """True when the release identity is already resolved to exact bytes."""
        return self.image_reference is not None

    def __str__(self) -> str:
        return str(self.semantic_version or self.image_reference)
