"""Versioned platform defaults: the settings InferOps owns for every workload.

A release takes workload intent from a WorkloadContract and environment facts from
an EnvironmentBinding. A third kind of input belongs to neither: a setting the
platform fixes for every workload in every environment, which no workload owner
should have to restate and no environment should vary. That is a platform default,
and :class:`PlatformDefaults` holds one set of them.

**What a ``v1alpha1`` set carries.** Three settings of the platform API tier: the
upstream request timeout, the drain timeout on shutdown, and the output-token
ceiling the API enforces. Each was chosen for three properties together: the
chart already exposes it, neither the WorkloadContract nor the EnvironmentBinding
has a field for it, and the chart's default is the value every environment the
repository describes runs with. The bounds are the chart's own, and a test reads
the chart's values schema and fails if any of them differs. Nothing else is here
yet, on purpose: a setting enters the defaults when a change needs it rendered,
not in advance.

**Identified by a revision.** A set of defaults is read from a committed file at a
full Git revision, and a release records that revision in
``source.platformDefaults.revision``. No defaults file exists yet, and nothing in
this package reads one: the caller constructs the object with the revision it read
the values at. Where the file lives and how it is read is a later change.

**No default has a default.** Every attribute is required. A defaults object that
filled in a value it was not given would be a fourth, unversioned layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from ..release.values import GitRevision
from ..workload.errors import InvalidValueError

#: The JSON form of a defaults set, or of one object inside it.
Document = dict[str, Any]

#: Every platform-defaults version this package implements, in maturity order.
SUPPORTED_PLATFORM_DEFAULTS_VERSIONS: Final[tuple[str, ...]] = ("v1alpha1",)

#: The chart's bounds for a duration in milliseconds, ``$defs.positiveMilliseconds``.
MILLISECONDS_FLOOR: Final = 1
MILLISECONDS_CEILING: Final = 3_600_000

#: The chart's bounds for ``api.maxOutputTokens``.
OUTPUT_TOKENS_FLOOR: Final = 1
OUTPUT_TOKENS_CEILING: Final = 32_768


def _bounded(value: object, floor: int, ceiling: int, what: str) -> None:
    # `True` is an `int` in Python and is not an integer in JSON.
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidValueError(f"{what} must be an integer")
    if not floor <= value <= ceiling:
        raise InvalidValueError(f"{what} must be between {floor} and {ceiling}")


@dataclass(frozen=True, slots=True)
class ApiDefaults:
    """``api``. Settings of the platform API tier that are the same everywhere.

    The API's replica count is not here: it varies by environment, and the
    EnvironmentBinding's ``spec.platform.apiReplicas`` owns it.
    """

    request_timeout_ms: int
    drain_timeout_ms: int
    max_output_tokens: int

    def __post_init__(self) -> None:
        _bounded(
            self.request_timeout_ms,
            MILLISECONDS_FLOOR,
            MILLISECONDS_CEILING,
            "a request timeout in milliseconds",
        )
        _bounded(
            self.drain_timeout_ms,
            MILLISECONDS_FLOOR,
            MILLISECONDS_CEILING,
            "a drain timeout in milliseconds",
        )
        _bounded(
            self.max_output_tokens,
            OUTPUT_TOKENS_FLOOR,
            OUTPUT_TOKENS_CEILING,
            "an output-token ceiling",
        )

    def as_document(self) -> Document:
        return {
            "requestTimeoutMs": self.request_timeout_ms,
            "drainTimeoutMs": self.drain_timeout_ms,
            "maxOutputTokens": self.max_output_tokens,
        }


@dataclass(frozen=True, slots=True)
class PlatformDefaults:
    """One versioned set of platform defaults, read at one revision."""

    version: str
    revision: GitRevision
    api: ApiDefaults

    def __post_init__(self) -> None:
        if self.version not in SUPPORTED_PLATFORM_DEFAULTS_VERSIONS:
            supported = ", ".join(
                repr(entry) for entry in SUPPORTED_PLATFORM_DEFAULTS_VERSIONS
            )
            raise InvalidValueError(
                "the platform-defaults version named here is not one this package "
                f"implements; the supported versions are {supported}"
            )
        if not isinstance(self.revision, GitRevision):
            raise InvalidValueError(
                "a platform-defaults revision must be a GitRevision"
            )
        if not isinstance(self.api, ApiDefaults):
            raise InvalidValueError("platform API defaults must be ApiDefaults")

    def as_document(self) -> Document:
        return {
            "version": self.version,
            "revision": str(self.revision),
            "api": self.api.as_document(),
        }


__all__ = [
    "MILLISECONDS_CEILING",
    "MILLISECONDS_FLOOR",
    "OUTPUT_TOKENS_CEILING",
    "OUTPUT_TOKENS_FLOOR",
    "SUPPORTED_PLATFORM_DEFAULTS_VERSIONS",
    "ApiDefaults",
    "PlatformDefaults",
]
