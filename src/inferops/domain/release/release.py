"""The RenderedWorkloadRelease as the platform's own objects.

One document, read once, becomes a tree of frozen objects whose every string was
checked against the format the schema publishes for it. A release names its inputs
and its output by identity and digest, and these objects hold exactly those names:
no object in the tree has an attribute for a contract's intent, a binding's facts,
the generated values, a timestamp, or free text, so there is nothing a copy of a
document, a render time, or a credential field could be written into.

**Nothing is defaulted and nothing is optional.** Every member of the schema is
required, and every attribute here is too: a release that left an input out could
not be traced back to it, and one that left its output unpinned could not be
compared with another. A test asserts that no field of any class here has a
default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..environment.versions import BindingVersion
from ..workload.errors import InvalidValueError
from ..workload.values import DnsLabel, Environment
from ..workload.versions import ContractVersion
from .values import (
    GitRevision,
    ReleaseId,
    ReleaseWorkloadVersion,
    Sha256Hex,
    ValuesFileName,
)
from .versions import (
    RECORDABLE_BINDING_VERSIONS,
    RECORDABLE_CONTRACT_VERSIONS,
    RENDERED_WORKLOAD_RELEASE_KIND,
    ReleaseVersion,
)

#: The JSON wire form of a document, or of one object inside it.
Document = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ReleaseMetadata:
    """``metadata``. Which workload this is a release of, and which release."""

    workload_id: DnsLabel
    workload_version: ReleaseWorkloadVersion
    release_id: ReleaseId

    def as_document(self) -> Document:
        return {
            "workloadId": str(self.workload_id),
            "workloadVersion": str(self.workload_version),
            "releaseId": str(self.release_id),
        }


@dataclass(frozen=True, slots=True)
class ContractReference:
    """``source.contract``. The WorkloadContract, by version and digest."""

    api_version: ContractVersion
    sha256: Sha256Hex

    def __post_init__(self) -> None:
        # The workload domain reads more versions than a release may record one
        # day; this is the release's own list, not the contract package's.
        if str(self.api_version) not in RECORDABLE_CONTRACT_VERSIONS:
            raise InvalidValueError(
                "this release version cannot record that contract version"
            )

    def as_document(self) -> Document:
        return {"apiVersion": str(self.api_version), "sha256": str(self.sha256)}


@dataclass(frozen=True, slots=True)
class EnvironmentBindingReference:
    """``source.environmentBinding``. The binding, by identity and digest.

    A binding's identity is its environment and its name together, and a binding
    carries no revision field, so a release records both and a digest.
    """

    api_version: BindingVersion
    environment: Environment
    name: DnsLabel
    sha256: Sha256Hex

    def __post_init__(self) -> None:
        if str(self.api_version) not in RECORDABLE_BINDING_VERSIONS:
            raise InvalidValueError(
                "this release version cannot record that binding version"
            )

    def as_document(self) -> Document:
        return {
            "apiVersion": str(self.api_version),
            "environment": self.environment.value,
            "name": str(self.name),
            "sha256": str(self.sha256),
        }


@dataclass(frozen=True, slots=True)
class RendererReference:
    """``source.renderer``. The renderer, by the full commit it ran from."""

    revision: GitRevision

    def as_document(self) -> Document:
        return {"revision": str(self.revision)}


@dataclass(frozen=True, slots=True)
class PlatformDefaultsReference:
    """``source.platformDefaults``. The defaults, by the full commit they were read at."""

    revision: GitRevision

    def as_document(self) -> Document:
        return {"revision": str(self.revision)}


@dataclass(frozen=True, slots=True)
class ReleaseSource:
    """``source``. Every input a release was rendered from, each by identity."""

    contract: ContractReference
    environment_binding: EnvironmentBindingReference
    renderer: RendererReference
    platform_defaults: PlatformDefaultsReference

    def as_document(self) -> Document:
        return {
            "contract": self.contract.as_document(),
            "environmentBinding": self.environment_binding.as_document(),
            "renderer": self.renderer.as_document(),
            "platformDefaults": self.platform_defaults.as_document(),
        }


@dataclass(frozen=True, slots=True)
class HelmValuesReference:
    """``output.helmValues``. The generated values, by file name and digest."""

    path: ValuesFileName
    sha256: Sha256Hex

    def as_document(self) -> Document:
        return {"path": str(self.path), "sha256": str(self.sha256)}


@dataclass(frozen=True, slots=True)
class ReleaseOutput:
    """``output``. What the release produced, referenced rather than carried."""

    helm_values: HelmValuesReference

    def as_document(self) -> Document:
        return {"helmValues": self.helm_values.as_document()}


@dataclass(frozen=True, slots=True)
class RenderedWorkloadRelease:
    """One RenderedWorkloadRelease document, read into typed objects.

    A value of this type is a document that could be *read*. It is not one the
    platform has accepted: whether its identifier is derived, whether a value is
    shaped like a credential, and whether it agrees with the documents it names
    are ``provenance``'s rules, and they have not run.
    """

    api_version: ReleaseVersion
    kind: str
    metadata: ReleaseMetadata
    source: ReleaseSource
    output: ReleaseOutput

    def __post_init__(self) -> None:
        if self.kind != RENDERED_WORKLOAD_RELEASE_KIND:
            raise InvalidValueError(
                f"a release's kind must be {RENDERED_WORKLOAD_RELEASE_KIND!r}"
            )

    def as_document(self) -> Document:
        """The JSON wire form, exactly as a document that parsed to this would be."""
        return {
            "apiVersion": str(self.api_version),
            "kind": self.kind,
            "metadata": self.metadata.as_document(),
            "source": self.source.as_document(),
            "output": self.output.as_document(),
        }


__all__ = [
    "ContractReference",
    "Document",
    "EnvironmentBindingReference",
    "HelmValuesReference",
    "PlatformDefaultsReference",
    "ReleaseMetadata",
    "ReleaseOutput",
    "ReleaseSource",
    "RenderedWorkloadRelease",
    "RendererReference",
]
