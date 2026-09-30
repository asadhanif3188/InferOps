"""Release-version handling, and the source versions a release can record.

A release, a WorkloadContract, and an EnvironmentBinding all declare
``inferops.io/v1alpha1`` today. That is a coincidence of maturity, not a shared
version: ``apiVersion`` and ``kind`` together name a schema, and each is versioned
on its own. So the release's supported versions are a constant of their own, and
so are the contract and binding versions a release of this version can *record* -
which is a different question from which versions the other two packages read.

The version is refused first, before a single field below it is read: every field
path this package knows is a path in ``v1alpha1``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..context import NO_REQUEST_CONTEXT, RequestContext
from .errors import UnsupportedReleaseVersionError

#: The ``kind`` every document this package reads must declare.
RENDERED_WORKLOAD_RELEASE_KIND: Final = "RenderedWorkloadRelease"

#: Every release ``apiVersion`` this package implements, in maturity order.
SUPPORTED_RELEASE_VERSIONS: Final[tuple[str, ...]] = ("inferops.io/v1alpha1",)

#: The WorkloadContract versions a ``v1alpha1`` release can record in
#: ``source.contract.apiVersion``. A test holds it to the schema's enum.
RECORDABLE_CONTRACT_VERSIONS: Final[tuple[str, ...]] = ("inferops.io/v1alpha1",)

#: The EnvironmentBinding versions a ``v1alpha1`` release can record in
#: ``source.environmentBinding.apiVersion``. A test holds it to the schema's enum.
RECORDABLE_BINDING_VERSIONS: Final[tuple[str, ...]] = ("inferops.io/v1alpha1",)


def _supported() -> str:
    return ", ".join(repr(entry) for entry in SUPPORTED_RELEASE_VERSIONS)


@dataclass(frozen=True, slots=True)
class ReleaseVersion:
    """One supported release ``apiVersion``, split into its group and version."""

    group: str
    version: str

    def __post_init__(self) -> None:
        if str(self) not in SUPPORTED_RELEASE_VERSIONS:
            raise UnsupportedReleaseVersionError(
                "$.apiVersion",
                "the release version named here is not one this package "
                f"implements; the supported versions are {_supported()}",
            )

    def __str__(self) -> str:
        return f"{self.group}/{self.version}"

    @classmethod
    def parse(
        cls,
        value: object,
        *,
        context: RequestContext = NO_REQUEST_CONTEXT,
    ) -> ReleaseVersion:
        """The declared version, or a refusal naming the versions that exist."""
        if not isinstance(value, str) or value not in SUPPORTED_RELEASE_VERSIONS:
            raise UnsupportedReleaseVersionError(
                "$.apiVersion",
                "the release version declared here is not one this package "
                f"implements; the supported versions are {_supported()}",
                context=context,
            )
        group, _, version = value.partition("/")
        return cls(group=group, version=version)


def is_supported_release_version(value: object) -> bool:
    """Whether a declared ``apiVersion`` is a release version this package reads."""
    return isinstance(value, str) and value in SUPPORTED_RELEASE_VERSIONS


__all__ = [
    "RECORDABLE_BINDING_VERSIONS",
    "RECORDABLE_CONTRACT_VERSIONS",
    "RENDERED_WORKLOAD_RELEASE_KIND",
    "SUPPORTED_RELEASE_VERSIONS",
    "ReleaseVersion",
    "is_supported_release_version",
]
