"""Versioned platform defaults: the settings InferOps owns for every workload.

A release takes workload intent from a WorkloadContract and environment facts from
an EnvironmentBinding. A third kind of input belongs to neither: a setting the
platform fixes for every workload in every environment, which no workload owner
should have to restate and no environment should vary. That is a platform default,
and :class:`PlatformDefaults` holds one set of them.

**What a ``v1alpha1`` set carries.** Seven settings. Five are the platform API
tier's: the upstream request timeout, the drain timeout on shutdown, the
output-token ceiling the API enforces, and the two bounds of the API's rolling
update. Two are the serving runtime tier's: the two bounds of its rolling update.
Each was chosen for three properties together: the chart exposes it, neither the
WorkloadContract nor the EnvironmentBinding has a field for it, and the chart's
default is the value every values file the repository renders with uses. The
bounds are the chart's own, and a test reads the chart's values schema and fails
if any of them differs. Nothing else is here yet, on purpose: a setting enters
the defaults when a change needs it rendered, not in advance.

**The rollout bounds were added in place.** The first ``v1alpha1`` sets carried
three settings. The API tier's two bounds joined them, and then the runtime
tier's two. No defaults file is committed at any revision, so no stored document
changed its meaning either time; a caller that constructs a set states every
bound, or construction fails. The bounds are a rollout policy. They establish
nothing about what a caller observes during a rollout, a pod deletion, or an
eviction.

**The runtime's replica count is not a default.** The workload owner declares it
in the WorkloadContract's ``spec.scaling``. The platform owns how a rollout of
those replicas proceeds, and does not own how many there are.

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

#: The chart's bounds for each rolling-update bound, ``$defs.rollout``: whole pods.
ROLLOUT_PODS_FLOOR: Final = 0
ROLLOUT_PODS_CEILING: Final = 16


def _bounded(value: object, floor: int, ceiling: int, what: str) -> None:
    # `True` is an `int` in Python and is not an integer in JSON.
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidValueError(f"{what} must be an integer")
    if not floor <= value <= ceiling:
        raise InvalidValueError(f"{what} must be between {floor} and {ceiling}")


def _rollout_bounds(max_unavailable: object, max_surge: object) -> None:
    """The checks every tier's rollout bounds pass: whole pods, and not two zeros."""
    _bounded(
        max_unavailable,
        ROLLOUT_PODS_FLOOR,
        ROLLOUT_PODS_CEILING,
        "a rollout's unavailable-pod bound",
    )
    _bounded(
        max_surge,
        ROLLOUT_PODS_FLOOR,
        ROLLOUT_PODS_CEILING,
        "a rollout's surge-pod bound",
    )
    if max_unavailable == 0 and max_surge == 0:
        raise InvalidValueError(
            "a rollout's unavailable-pod bound and surge-pod bound must not both be 0"
        )


@dataclass(frozen=True, slots=True)
class ApiRolloutDefaults:
    """``api.rollout``. The two bounds of the API tier's rolling update, in whole pods.

    ``max_unavailable`` is how many API pods a rollout may take away before their
    replacements are Ready. ``max_surge`` is how many it may add above the replica
    count. Two zeros are refused: Kubernetes refuses a rolling update that may
    neither remove a pod nor add one.
    """

    max_unavailable: int
    max_surge: int

    def __post_init__(self) -> None:
        _rollout_bounds(self.max_unavailable, self.max_surge)

    def as_document(self) -> Document:
        return {
            "maxUnavailable": self.max_unavailable,
            "maxSurge": self.max_surge,
        }


@dataclass(frozen=True, slots=True)
class RuntimeRolloutDefaults:
    """``runtime.rollout``. The two bounds of the runtime tier's rolling update.

    The bounds are whole pods, and mean what :class:`ApiRolloutDefaults` says. This
    is a type of its own so that one tier's bounds cannot be passed as the other's:
    the two tiers hold opposite policies. Two zeros are refused here too.
    """

    max_unavailable: int
    max_surge: int

    def __post_init__(self) -> None:
        _rollout_bounds(self.max_unavailable, self.max_surge)

    def as_document(self) -> Document:
        return {
            "maxUnavailable": self.max_unavailable,
            "maxSurge": self.max_surge,
        }


@dataclass(frozen=True, slots=True)
class ApiDefaults:
    """``api``. Settings of the platform API tier that are the same everywhere.

    The API's replica count is not here: it varies by environment, and the
    EnvironmentBinding's ``spec.platform.apiReplicas`` owns it.
    """

    request_timeout_ms: int
    drain_timeout_ms: int
    max_output_tokens: int
    rollout: ApiRolloutDefaults

    def __post_init__(self) -> None:
        if not isinstance(self.rollout, ApiRolloutDefaults):
            raise InvalidValueError(
                "platform API rollout defaults must be ApiRolloutDefaults"
            )
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
            "rollout": self.rollout.as_document(),
        }


@dataclass(frozen=True, slots=True)
class RuntimeDefaults:
    """``runtime``. Settings of the serving runtime tier that are the same everywhere.

    The runtime's replica count is not here: it is workload intent, and the
    WorkloadContract's ``spec.scaling`` owns it. Its image, its model, and its CPU
    and memory limits are the contract's too.
    """

    rollout: RuntimeRolloutDefaults

    def __post_init__(self) -> None:
        if not isinstance(self.rollout, RuntimeRolloutDefaults):
            raise InvalidValueError(
                "platform runtime rollout defaults must be RuntimeRolloutDefaults"
            )

    def as_document(self) -> Document:
        return {"rollout": self.rollout.as_document()}


@dataclass(frozen=True, slots=True)
class PlatformDefaults:
    """One versioned set of platform defaults, read at one revision."""

    version: str
    revision: GitRevision
    api: ApiDefaults
    runtime: RuntimeDefaults

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
        if not isinstance(self.runtime, RuntimeDefaults):
            raise InvalidValueError("platform runtime defaults must be RuntimeDefaults")

    def as_document(self) -> Document:
        return {
            "version": self.version,
            "revision": str(self.revision),
            "api": self.api.as_document(),
            "runtime": self.runtime.as_document(),
        }


__all__ = [
    "MILLISECONDS_CEILING",
    "MILLISECONDS_FLOOR",
    "OUTPUT_TOKENS_CEILING",
    "OUTPUT_TOKENS_FLOOR",
    "ROLLOUT_PODS_CEILING",
    "ROLLOUT_PODS_FLOOR",
    "SUPPORTED_PLATFORM_DEFAULTS_VERSIONS",
    "ApiDefaults",
    "ApiRolloutDefaults",
    "PlatformDefaults",
    "RuntimeDefaults",
    "RuntimeRolloutDefaults",
]
