"""The EnvironmentBinding as the platform's own objects.

One document, read once, becomes a tree of frozen objects whose every string was
checked against the format the schema publishes for it. Nothing here knows what a
namespace object, a volume claim, a Helm value, or an Argo application is: a
binding names a provider, a namespace, a claim, a count, and a path, and these
objects hold those names as values. What they point at is verified by the local
cluster provider contract at run time, and by nothing in this package.

**The boundary with the WorkloadContract is in the shape.** No object in this
tree has an attribute for a value a WorkloadContract owns - no profile, model,
resources, scaling, integrations, security, attribution, evidence, or profile
block - so a binding has nowhere to hold one and nothing to override one with.
The one member the two share is ``spec.environment``, and it is the contract's own
:class:`~inferops.domain.workload.values.Environment` type: the key a binding is
matched on, not a second copy of a contract value. A test compares the attribute
names of both trees and fails if any other name appears in both.

**Nothing is defaulted and nothing is optional.** Every member of the schema is
required, so every attribute here is too. A fact a binding left out would be a
fact something else supplies silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..workload.errors import InvalidValueError
from ..workload.values import DnsLabel, Environment
from .values import (
    API_REPLICAS_CEILING,
    API_REPLICAS_FLOOR,
    ClusterProvider,
    GitOpsPath,
    ModelCacheClass,
    ReleaseNamespace,
)
from .versions import ENVIRONMENT_BINDING_KIND, BindingVersion

#: The JSON wire form of a document, or of one object inside it.
Document = dict[str, Any]


@dataclass(frozen=True, slots=True)
class BindingIdentity:
    """What identifies one binding: the environment it serves and its name.

    Two bindings may serve one environment; two with the same environment and the
    same name are one identity claimed twice, which the set rules refuse.
    """

    environment: Environment
    name: DnsLabel


@dataclass(frozen=True, slots=True)
class BindingMetadata:
    """``metadata``. The binding's name and the team that owns its facts."""

    name: DnsLabel
    #: The platform side of the boundary, not the workload's owner.
    owner: DnsLabel

    def as_document(self) -> Document:
        return {"name": str(self.name), "owner": str(self.owner)}


@dataclass(frozen=True, slots=True)
class Destination:
    """``spec.destination``. Where a release goes; a selection, not a verification."""

    cluster_provider: ClusterProvider
    namespace: ReleaseNamespace

    def as_document(self) -> Document:
        return {
            "clusterProvider": self.cluster_provider.value,
            "namespace": str(self.namespace),
        }


@dataclass(frozen=True, slots=True)
class ModelCache:
    """``spec.modelCache``. The cache a release mounts; referenced, never created."""

    cache_class: ModelCacheClass
    claim_name: DnsLabel

    def as_document(self) -> Document:
        return {"class": self.cache_class.value, "claimName": str(self.claim_name)}


@dataclass(frozen=True, slots=True)
class PlatformSettings:
    """``spec.platform``. Settings for platform-owned components only.

    The serving runtime's replica count is not here: it is workload intent, and
    the WorkloadContract's ``spec.scaling`` owns it.
    """

    api_replicas: int

    def __post_init__(self) -> None:
        # Checked here as well as by the parser, so that an object constructed
        # directly cannot hold a count the chart would refuse. `True` is an `int`
        # in Python and is not an integer in JSON.
        if isinstance(self.api_replicas, bool) or not isinstance(
            self.api_replicas, int
        ):
            raise InvalidValueError("an API replica count must be an integer")
        if not API_REPLICAS_FLOOR <= self.api_replicas <= API_REPLICAS_CEILING:
            raise InvalidValueError(
                f"an API replica count must be between {API_REPLICAS_FLOOR} and "
                f"{API_REPLICAS_CEILING}"
            )

    def as_document(self) -> Document:
        return {"apiReplicas": self.api_replicas}


@dataclass(frozen=True, slots=True)
class GitOpsDestination:
    """``spec.gitops``. Where generated desired state is to be written.

    A declared location. Nothing in this package writes there, and nothing
    reconciles it.
    """

    destination_path: GitOpsPath

    def as_document(self) -> Document:
        return {"destinationPath": str(self.destination_path)}


@dataclass(frozen=True, slots=True)
class BindingSpec:
    """``spec``. Environment facts, and only environment facts."""

    environment: Environment
    destination: Destination
    model_cache: ModelCache
    platform: PlatformSettings
    gitops: GitOpsDestination

    def as_document(self) -> Document:
        return {
            "environment": self.environment.value,
            "destination": self.destination.as_document(),
            "modelCache": self.model_cache.as_document(),
            "platform": self.platform.as_document(),
            "gitops": self.gitops.as_document(),
        }


@dataclass(frozen=True, slots=True)
class EnvironmentBinding:
    """One EnvironmentBinding document, read into typed objects."""

    api_version: BindingVersion
    kind: str
    metadata: BindingMetadata
    spec: BindingSpec

    def __post_init__(self) -> None:
        if self.kind != ENVIRONMENT_BINDING_KIND:
            raise InvalidValueError(
                f"a binding's kind must be {ENVIRONMENT_BINDING_KIND!r}"
            )

    @property
    def identity(self) -> BindingIdentity:
        """The environment this binding serves, and its name."""
        return BindingIdentity(
            environment=self.spec.environment, name=self.metadata.name
        )

    def as_document(self) -> Document:
        """The JSON wire form, exactly as a document that parsed to this would be."""
        return {
            "apiVersion": str(self.api_version),
            "kind": self.kind,
            "metadata": self.metadata.as_document(),
            "spec": self.spec.as_document(),
        }


__all__ = [
    "BindingIdentity",
    "BindingMetadata",
    "BindingSpec",
    "Destination",
    "Document",
    "EnvironmentBinding",
    "GitOpsDestination",
    "ModelCache",
    "PlatformSettings",
]
