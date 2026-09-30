"""The typed values a RenderedWorkloadRelease is built out of.

Every constraint here is a *single-field structural* constraint the published
release schema already declares: a format, a length, or a vocabulary. The rules
that judge a release the schema accepts - whether its identifier is derived,
whether a value is shaped like a credential, whether it agrees with the documents
it names - are in ``provenance``.

Two values are not redefined here, on purpose. The workload identifier and the
binding name are the WorkloadContract's own
:class:`~inferops.domain.workload.values.DnsLabel`, and the environment is its own
:class:`~inferops.domain.workload.values.Environment`, so a release cannot hold a
spelling of either that the documents it names could not. A digest-pinned
workload version is the contract's own
:class:`~inferops.domain.workload.values.ImageReference`.

The patterns and bounds are written in Python for the reason the workload domain
gives: the domain cannot import a JSON Schema validator. A test reads
``contracts/release/rendered-workload-release.v1alpha1.schema.json`` and fails if
any of them differs from what the schema publishes.
"""

from __future__ import annotations

import re
from typing import Final

from ..workload.errors import InvalidValueError
from ..workload.values import ConstrainedString, ImageReference

# The schema's own patterns, character for character, compared by a test.
SHA256_HEX_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
GIT_REVISION_PATTERN: Final = re.compile(r"^[0-9a-f]{40}$")
LOWERCASE_SEMANTIC_VERSION_PATTERN: Final = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-z-][0-9a-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-z-][0-9a-z-]*))*))?"
    r"(?:\+([0-9a-z-]+(?:\.[0-9a-z-]+)*))?$"
)
VALUES_FILE_NAME_PATTERN: Final = re.compile(
    r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*\.yaml$"
)


class Sha256Hex(ConstrainedString):
    """A SHA-256 digest as 64 lowercase hexadecimal characters, with no prefix.

    One digest has one spelling, so two releases can be compared as text. The
    WorkloadContract's :class:`~inferops.domain.workload.values.Sha256Digest` is a
    different form - it carries a ``sha256:`` prefix - and is not this type.
    """

    NAME = "a SHA-256 digest in lowercase hexadecimal"
    PATTERN = SHA256_HEX_PATTERN
    # The schema declares no length bound here; the pattern fixes the length. The
    # agreement test reads the bound out of the pattern.
    MINIMUM_LENGTH = 64
    MAXIMUM_LENGTH = 64


class ReleaseId(Sha256Hex):
    """``metadata.releaseId``: the digest its own workload identity and source derive.

    The form is checked here. That the value is the derived one is a rule, not a
    format, and ``provenance`` applies it.
    """

    NAME = "a release identifier"


class GitRevision(ConstrainedString):
    """A full Git commit identifier. A branch, a tag, or an abbreviation can move."""

    NAME = "a full Git revision"
    PATTERN = GIT_REVISION_PATTERN
    MINIMUM_LENGTH = 40
    MAXIMUM_LENGTH = 40


class LowercaseSemanticVersion(ConstrainedString):
    """A semantic version whose pre-release and build identifiers are lowercase.

    The WorkloadContract's semantic version with uppercase removed, so it is
    narrower than what a contract accepts: ``1.0.0-RC.1`` is a valid contract
    version and cannot be recorded by this version of the release.
    """

    NAME = "a lowercase semantic version"
    PATTERN = LOWERCASE_SEMANTIC_VERSION_PATTERN
    MAXIMUM_LENGTH = 128


class ValuesFileName(ConstrainedString):
    """The name of a file beside the release, lowercase, ending in ``.yaml``.

    It has no directory part, so it cannot point outside the release's own
    directory, at another release's values, or at a file on somebody's machine.
    """

    NAME = "a values file name"
    PATTERN = VALUES_FILE_NAME_PATTERN
    MAXIMUM_LENGTH = 255


#: ``metadata.workloadVersion``: one of the two forms, kept as the form it is.
ReleaseWorkloadVersion = LowercaseSemanticVersion | ImageReference


def parse_release_workload_version(value: str) -> ReleaseWorkloadVersion:
    """Read whichever of the two accepted forms the value is, or refuse it."""
    if (
        LOWERCASE_SEMANTIC_VERSION_PATTERN.fullmatch(value) is not None
        and len(value) <= LowercaseSemanticVersion.MAXIMUM_LENGTH
    ):
        return LowercaseSemanticVersion(value)
    try:
        return ImageReference(value)
    except InvalidValueError:
        # A value that is neither form is refused with both forms named, the
        # way the schema's `oneOf` refuses it, and without the value.
        raise InvalidValueError(
            "a workload version must be a lowercase semantic version of at most "
            f"{LowercaseSemanticVersion.MAXIMUM_LENGTH} characters or an image "
            "reference pinned by digest"
        ) from None


__all__ = [
    "GIT_REVISION_PATTERN",
    "LOWERCASE_SEMANTIC_VERSION_PATTERN",
    "SHA256_HEX_PATTERN",
    "VALUES_FILE_NAME_PATTERN",
    "GitRevision",
    "LowercaseSemanticVersion",
    "ReleaseId",
    "ReleaseWorkloadVersion",
    "Sha256Hex",
    "ValuesFileName",
    "parse_release_workload_version",
]
