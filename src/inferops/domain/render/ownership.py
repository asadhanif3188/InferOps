"""Who owns every value a renderer may read, and the precedence between owners.

Three layers supply input to a render, and each owns a disjoint set of values:

- **workload intent** - the WorkloadContract, authored by the workload's owner;
- **platform defaults** - :class:`~.defaults.PlatformDefaults`, owned by InferOps
  and versioned;
- **environment binding** - the EnvironmentBinding selected for the contract,
  owned by the platform side of the environment.

:data:`RENDER_FIELD_OWNERSHIP` names every value of the normalized render context,
the one layer that owns it, and where in that layer's document it is read from.
Normalization reads nothing that is not a row of this table, and reads each row
from its owner and from nowhere else, so the table is the code path rather than a
description of it.

**The precedence rule is that there is none.** No layer overrides any other:
:data:`OVERRIDES`, the set of pairs in which one layer may replace a value another
owns, is empty. A value has one owner, a second layer has no field to supply it
from, and so there is no order in which a later value could win. That is the rule
the binding's schema already states in its shape - it has no field for a contract
value - extended to the defaults, and it is what makes "last value wins"
impossible rather than merely discouraged. An input that supplies a value it does
not own anyway is refused, by ``conflicts``, rather than read or ignored: the
answer to "who owns this value" has exactly one entry, and a second answer is a
refusal.

**Names are semantic, not copied paths.** A context field is named for what it
means - ``api.replicas``, ``serving.replicas.minimum`` - rather than for where it
was read, so two layers claiming the same meaning would claim the same name. No
name is another name's prefix, segment by segment, so the namespace has one
reading.

**Fields deliberately left out** are listed with a reason in
:data:`EXCLUDED_SOURCE_FIELDS`: identity that the context's sources record, free
text, and the one extension point the platform may never act on. A test walks
every committed valid document and fails if a field is in neither table.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class Layer(StrEnum):
    """A layer of render input, named for what it is."""

    WORKLOAD_INTENT = "workload-intent"
    PLATFORM_DEFAULTS = "platform-defaults"
    ENVIRONMENT_BINDING = "environment-binding"


@dataclass(frozen=True, slots=True)
class FieldOwnership:
    """One value of the render context: its name, its one owner, and its source.

    ``source`` is a dotted path of member names in the owner's JSON form - the
    WorkloadContract or EnvironmentBinding document, or the platform defaults'
    ``as_document()``. ``required`` is false for a value an owner may leave out:
    an optional member, or a member of a profile block the other profile has not.
    """

    name: str
    layer: Layer
    source: str
    required: bool = True


def _w(name: str, source: str, *, required: bool = True) -> FieldOwnership:
    return FieldOwnership(name, Layer.WORKLOAD_INTENT, source, required)


def _d(name: str, source: str) -> FieldOwnership:
    return FieldOwnership(name, Layer.PLATFORM_DEFAULTS, source)


def _b(name: str, source: str) -> FieldOwnership:
    return FieldOwnership(name, Layer.ENVIRONMENT_BINDING, source)


#: Every value of the render context, in the order the published table lists them.
RENDER_FIELD_OWNERSHIP: Final[tuple[FieldOwnership, ...]] = (
    # Workload intent: the WorkloadContract.
    _w("workload.id", "metadata.name"),
    _w("workload.version", "metadata.version"),
    _w("workload.owner", "metadata.owner"),
    _w("workload.profile", "spec.profile"),
    _w("workload.environment", "spec.environment"),
    _w("model.servingCapability", "spec.model.servingCapability"),
    _w("model.ref", "spec.model.modelRef"),
    _w("model.runtimeProfile", "spec.model.runtimeProfile"),
    _w("resources.cpu", "spec.resources.cpu"),
    _w("resources.memory", "spec.resources.memory"),
    _w("resources.accelerator.type", "spec.resources.accelerator.type"),
    _w("resources.accelerator.count", "spec.resources.accelerator.count"),
    _w("serving.replicas.minimum", "spec.scaling.minimumReplicas"),
    _w("serving.replicas.maximum", "spec.scaling.maximumReplicas"),
    _w(
        "integrations.telemetry.capabilityRef",
        "spec.integrations.telemetry.capabilityRef",
    ),
    _w("integrations.telemetry.required", "spec.integrations.telemetry.required"),
    _w(
        "integrations.modelAccess.capabilityRef",
        "spec.integrations.modelAccess.capabilityRef",
        required=False,
    ),
    _w(
        "integrations.modelAccess.required",
        "spec.integrations.modelAccess.required",
        required=False,
    ),
    _w(
        "integrations.evaluation.capabilityRef",
        "spec.integrations.evaluation.capabilityRef",
        required=False,
    ),
    _w(
        "integrations.evaluation.required",
        "spec.integrations.evaluation.required",
        required=False,
    ),
    _w("security.dataClassification", "spec.security.dataClassification"),
    _w("security.secretRefs", "spec.security.secretRefs"),
    _w("attribution.tenant", "spec.attribution.tenant"),
    _w("attribution.costCenter", "spec.attribution.costCenter"),
    _w("evidence.runbookRef", "spec.evidence.runbookRef"),
    _w("evidence.proofRefs", "spec.evidence.proofRefs", required=False),
    _w(
        "runtime.imageReference",
        "spec.synchronousLlm.runtime.imageReference",
        required=False,
    ),
    _w(
        "model.artifact.repository",
        "spec.synchronousLlm.modelArtifact.repository",
        required=False,
    ),
    _w(
        "model.artifact.revision",
        "spec.synchronousLlm.modelArtifact.revision",
        required=False,
    ),
    _w("model.artifact.file", "spec.synchronousLlm.modelArtifact.file", required=False),
    _w(
        "model.artifact.sizeBytes",
        "spec.synchronousLlm.modelArtifact.sizeBytes",
        required=False,
    ),
    _w(
        "model.artifact.sha256",
        "spec.synchronousLlm.modelArtifact.sha256",
        required=False,
    ),
    _w("mock.ciOnly", "spec.mockLlm.ciOnly", required=False),
    _w("mock.determinism", "spec.mockLlm.determinism", required=False),
    _w("mock.fixtureRef", "spec.mockLlm.fixtureRef", required=False),
    # Platform defaults: owned by InferOps, the same in every environment.
    _d("api.requestTimeoutMs", "api.requestTimeoutMs"),
    _d("api.drainTimeoutMs", "api.drainTimeoutMs"),
    _d("api.maxOutputTokens", "api.maxOutputTokens"),
    _d("api.rollout.maxUnavailable", "api.rollout.maxUnavailable"),
    _d("api.rollout.maxSurge", "api.rollout.maxSurge"),
    # Environment binding: the facts one environment supplies.
    _b("destination.clusterProvider", "spec.destination.clusterProvider"),
    _b("destination.namespace", "spec.destination.namespace"),
    _b("modelCache.class", "spec.modelCache.class"),
    _b("modelCache.claimName", "spec.modelCache.claimName"),
    _b("api.replicas", "spec.platform.apiReplicas"),
    _b("gitops.destinationPath", "spec.gitops.destinationPath"),
)

#: Pairs ``(winner, loser)`` in which ``winner`` may replace a value ``loser``
#: owns. Empty: no layer overrides another, in either direction.
OVERRIDES: Final[frozenset[tuple[Layer, Layer]]] = frozenset()

#: Source fields no context value is read from, by layer, each with its reason.
EXCLUDED_SOURCE_FIELDS: Final[Mapping[Layer, Mapping[str, str]]] = MappingProxyType(
    {
        Layer.WORKLOAD_INTENT: MappingProxyType(
            {
                "apiVersion": "identity of the document; the context's sources "
                "record it with the contract's digest",
                "kind": "identity of the document; fixed for every contract",
                "metadata.description": "free text for a reader, which no render "
                "setting may depend on",
                "metadata.annotations": "the contract's non-normative extension "
                "point; the platform must not change behaviour because of one",
            }
        ),
        Layer.PLATFORM_DEFAULTS: MappingProxyType(
            {
                "version": "the shape of the defaults, refused at construction "
                "when unsupported",
                "revision": "identity of the defaults; the context's sources record it",
            }
        ),
        Layer.ENVIRONMENT_BINDING: MappingProxyType(
            {
                "apiVersion": "identity of the document; the context's sources "
                "record it with the binding's digest",
                "kind": "identity of the document; fixed for every binding",
                "metadata.name": "identity of the binding; the context's sources "
                "record it",
                "metadata.owner": "the team that owns the binding's facts, which "
                "no render setting depends on",
                "spec.environment": "the key a binding is selected by, not a "
                "value: selection guarantees it equals the contract's, and the "
                "context takes the environment from the contract",
            }
        ),
    }
)

_BY_NAME: Final[Mapping[str, FieldOwnership]] = MappingProxyType(
    {entry.name: entry for entry in RENDER_FIELD_OWNERSHIP}
)


def owner_of(name: str) -> Layer:
    """The one layer that owns a render-context value.

    Raises:
        KeyError: no render-context value has that name.
    """
    return _BY_NAME[name].layer


def ownership_of(name: str) -> FieldOwnership:
    """The ownership row for a render-context value.

    Raises:
        KeyError: no render-context value has that name.
    """
    return _BY_NAME[name]


def may_override(winner: Layer, loser: Layer) -> bool:
    """Whether ``winner`` may replace a value ``loser`` owns. Never, today."""
    return (winner, loser) in OVERRIDES


__all__ = [
    "EXCLUDED_SOURCE_FIELDS",
    "OVERRIDES",
    "RENDER_FIELD_OWNERSHIP",
    "FieldOwnership",
    "Layer",
    "may_override",
    "owner_of",
    "ownership_of",
]
