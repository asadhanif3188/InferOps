"""Binding-version handling, kept explicit and in one place.

A binding and a WorkloadContract both declare ``inferops.io/v1alpha1`` today, and
that is a coincidence of maturity rather than a shared version. ``apiVersion`` and
``kind`` together name a schema, each contract is versioned on its own, and so the
binding's supported versions are a separate constant from the workload domain's.
A second binding version is an entry here, not a change to the other contract.

The version is refused first, before a single field below it is read: every field
path this package knows is a path in ``v1alpha1``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..context import NO_REQUEST_CONTEXT, RequestContext
from .errors import UnsupportedBindingVersionError

#: The ``kind`` every document this package reads must declare.
ENVIRONMENT_BINDING_KIND: Final = "EnvironmentBinding"

#: Every binding ``apiVersion`` this package implements, in maturity order.
SUPPORTED_BINDING_VERSIONS: Final[tuple[str, ...]] = ("inferops.io/v1alpha1",)


def _supported() -> str:
    return ", ".join(repr(entry) for entry in SUPPORTED_BINDING_VERSIONS)


@dataclass(frozen=True, slots=True)
class BindingVersion:
    """One supported binding ``apiVersion``, split into its group and version."""

    group: str
    version: str

    def __post_init__(self) -> None:
        if str(self) not in SUPPORTED_BINDING_VERSIONS:
            raise UnsupportedBindingVersionError(
                "$.apiVersion",
                "the binding version named here is not one this package "
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
    ) -> BindingVersion:
        """The declared version, or a refusal naming the versions that exist."""
        if not isinstance(value, str) or value not in SUPPORTED_BINDING_VERSIONS:
            raise UnsupportedBindingVersionError(
                "$.apiVersion",
                "the binding version declared here is not one this package "
                f"implements; the supported versions are {_supported()}",
                context=context,
            )
        group, _, version = value.partition("/")
        return cls(group=group, version=version)


def is_supported_binding_version(value: object) -> bool:
    """Whether a declared ``apiVersion`` is a binding version this package reads."""
    return isinstance(value, str) and value in SUPPORTED_BINDING_VERSIONS


__all__ = [
    "ENVIRONMENT_BINDING_KIND",
    "SUPPORTED_BINDING_VERSIONS",
    "BindingVersion",
    "is_supported_binding_version",
]
