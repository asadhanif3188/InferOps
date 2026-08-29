"""The workload contract as the platform's own objects.

One document, read once, becomes a tree of frozen objects whose every string has
already been checked against the format the schema publishes for it. Nothing here
knows what a Deployment is, what Helm renders, or what a serving runtime accepts.
That is the point: the architecture's dependency rule exists so that this layer is
testable with no cluster, no model, and no network, and these objects are what the
rest of the platform is written against.

Three properties are worth stating because each was a decision.

**Absence is preserved.** ``metadata.description`` absent and
``metadata.description`` present-and-empty are different documents, and so are an
absent ``proofRefs`` and a declared empty one. A later component renders what the
author wrote; adding a field they did not write is how a document starts meaning
something they did not say. So every optional field is ``None`` when it was
absent, and :meth:`WorkloadContract.as_document` puts back exactly what was there.

**Nothing is defaulted.** The contract's own design bias is refuse rather than
guess — no default resources, no implicit owner, no inferred environment — and a
domain object that filled one in would undo that bias one field at a time.

**The profile block is not paired here.** A ``synchronous-llm`` document carries
``spec.synchronousLlm``, and a ``mock-llm`` document carries ``spec.mockLlm``. That
pairing is a cross-field rule; both blocks are optional on this object, and the
rule that exactly the right one is present belongs to the validation pipeline in
``V1-S1-001-PR2``. Encoding it here would mean this module and that one both own
it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .values import (
    AcceleratorType,
    ArtifactFile,
    ArtifactRepository,
    DataClassification,
    Description,
    DnsLabel,
    Environment,
    ImageReference,
    KebabCaseName,
    MockDeterminism,
    Profile,
    RepositoryPath,
    ResourceQuantity,
    RuntimeProfile,
    SecretLocator,
    SecretProvider,
    SecretRotation,
    ServingCapability,
    Sha256Digest,
    UpstreamRevision,
    WorkloadVersion,
)
from .versions import ContractVersion

#: The JSON wire form of a document, or of one object inside it.
Document = dict[str, Any]


def _without_absent(members: Document) -> Document:
    """Drop members that were absent, and keep every member that was present.

    ``None`` means absent. It never means false, empty, or zero: a ``required``
    of ``false``, an ``accelerator.count`` of ``0``, and a declared empty
    ``secretRefs`` are all values an author wrote, and all three survive this.
    """
    return {key: value for key, value in members.items() if value is not None}


@dataclass(frozen=True, slots=True)
class WorkloadMetadata:
    """``metadata``. Who the workload is, who owns it, and what release it is."""

    name: DnsLabel
    version: WorkloadVersion
    owner: DnsLabel
    description: Description | None = None
    #: The contract's one extension point, and a non-normative one: the platform
    #: must not change behaviour because of an annotation. Keys and values were
    #: checked at parse time against the published key format and length bound.
    #:
    #: Excluded from the hash, and only from the hash. A frozen dataclass is
    #: hashable, a mapping is not, and without this a contract that used the
    #: extension point would be unhashable while one that did not would be
    #: hashable - a difference nobody would find until something put a workload in
    #: a set. Two metadata objects differing only in their annotations therefore
    #: collide in a hash bucket and are still distinguished by ``==``, which is
    #: what a hash is allowed to do.
    annotations: Mapping[str, str] | None = field(default=None, hash=False)

    def as_document(self) -> Document:
        return _without_absent(
            {
                "name": str(self.name),
                "version": str(self.version),
                "owner": str(self.owner),
                "description": (
                    None if self.description is None else str(self.description)
                ),
                "annotations": (
                    None if self.annotations is None else dict(self.annotations)
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class ModelReference:
    """``spec.model``. The common model and runtime reference.

    Everything specific to one profile lives in that profile's own block. The
    bytes behind ``model_ref`` are pinned there, not here: this names a registered
    model identity in the platform catalogue, and no catalogue exists yet.
    """

    serving_capability: ServingCapability
    model_ref: KebabCaseName
    runtime_profile: RuntimeProfile

    def as_document(self) -> Document:
        return {
            "servingCapability": self.serving_capability.value,
            "modelRef": str(self.model_ref),
            "runtimeProfile": self.runtime_profile.value,
        }


@dataclass(frozen=True, slots=True)
class Accelerator:
    """``spec.resources.accelerator``. A declared request, not a measured device."""

    type: AcceleratorType
    count: int

    def as_document(self) -> Document:
        return {"type": self.type.value, "count": self.count}


@dataclass(frozen=True, slots=True)
class ResourceRequest:
    """``spec.resources``. Explicit in every environment; there is no default."""

    cpu: ResourceQuantity
    memory: ResourceQuantity
    accelerator: Accelerator

    def as_document(self) -> Document:
        return {
            "cpu": str(self.cpu),
            "memory": str(self.memory),
            "accelerator": self.accelerator.as_document(),
        }


@dataclass(frozen=True, slots=True)
class ScalingPolicy:
    """``spec.scaling``. The declared replica range, held as declared.

    Whether the range is non-empty is a comparison between two fields, and this
    object does not make it. ``replica-range-inverted`` is a published semantic
    rule and the pipeline in ``PR2`` is what applies it.
    """

    minimum_replicas: int
    maximum_replicas: int

    def as_document(self) -> Document:
        return {
            "minimumReplicas": self.minimum_replicas,
            "maximumReplicas": self.maximum_replicas,
        }


@dataclass(frozen=True, slots=True)
class CapabilityDependency:
    """One entry under ``spec.integrations``: a capability, and how hard it is.

    ``required`` is true when the workload cannot perform its declared function
    without the capability. Declaring one is not evidence that a provider exists;
    no capability registry exists to resolve ``capability_ref`` against.
    """

    capability_ref: KebabCaseName
    required: bool

    def as_document(self) -> Document:
        return {"capabilityRef": str(self.capability_ref), "required": self.required}


@dataclass(frozen=True, slots=True)
class Integrations:
    """``spec.integrations``. Telemetry is required; the other two are optional.

    A workload the platform cannot observe is a workload it cannot operate, which
    is why the telemetry dependency has no ``None`` case here.
    """

    telemetry: CapabilityDependency
    model_access: CapabilityDependency | None = None
    evaluation: CapabilityDependency | None = None

    def as_document(self) -> Document:
        return _without_absent(
            {
                "modelAccess": (
                    None
                    if self.model_access is None
                    else self.model_access.as_document()
                ),
                "telemetry": self.telemetry.as_document(),
                "evaluation": (
                    None if self.evaluation is None else self.evaluation.as_document()
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class SecretReference:
    """One entry under ``spec.security.secretRefs``: a locator, never a secret.

    There is no field on this object a secret value could be assigned to, for the
    same reason there is none in the schema. Whether a locator is in fact a pasted
    credential is a judgement, it is published as the semantic rule
    ``secret-value-in-locator``, and it is not made here.
    """

    name: KebabCaseName
    provider: SecretProvider
    reference: SecretLocator
    owner: DnsLabel
    rotation: SecretRotation

    def as_document(self) -> Document:
        return {
            "name": str(self.name),
            "provider": self.provider.value,
            "reference": str(self.reference),
            "owner": str(self.owner),
            "rotation": self.rotation.value,
        }


@dataclass(frozen=True, slots=True)
class SecurityPolicy:
    """``spec.security``. A classification, and the secrets the workload names."""

    data_classification: DataClassification
    secret_refs: tuple[SecretReference, ...]

    def as_document(self) -> Document:
        return {
            "dataClassification": self.data_classification.value,
            "secretRefs": [entry.as_document() for entry in self.secret_refs],
        }


@dataclass(frozen=True, slots=True)
class Attribution:
    """``spec.attribution``. Who is billed, and on whose behalf.

    ``tenant`` is a **request**, not an assertion. It is declared in the document
    and must be validated against the owning team's entitlement by a trusted
    component before it is used for isolation, attribution, or authorisation.
    Nothing in this domain performs that check, and nothing here should be read as
    having performed it.
    """

    tenant: DnsLabel
    cost_center: KebabCaseName

    def as_document(self) -> Document:
        return {"tenant": str(self.tenant), "costCenter": str(self.cost_center)}


@dataclass(frozen=True, slots=True)
class EvidenceReferences:
    """``spec.evidence``. Where the procedure is, and what proof is cited.

    ``proof_refs`` is ``None`` when the author cited none and an empty tuple when
    they declared an empty list. The difference is preserved because a mock
    workload is capped at zero entries by the schema, and "declared none" and
    "declared empty" are two ways of complying that a rendered document should not
    silently merge.
    """

    runbook_ref: RepositoryPath
    proof_refs: tuple[RepositoryPath, ...] | None = None

    def as_document(self) -> Document:
        return _without_absent(
            {
                "runbookRef": str(self.runbook_ref),
                "proofRefs": (
                    None
                    if self.proof_refs is None
                    else [str(entry) for entry in self.proof_refs]
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeImage:
    """``spec.synchronousLlm.runtime``. The runtime, pinned by digest."""

    image_reference: ImageReference

    def as_document(self) -> Document:
        return {"imageReference": str(self.image_reference)}


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    """``spec.synchronousLlm.modelArtifact``. The exact bytes to be served.

    Both pins are required and neither substitutes for the other: a revision names
    what a publisher said it published, and a hash names what actually arrived.
    Holding both is not the same as having verified either, and nothing in this
    domain fetches or hashes anything.
    """

    repository: ArtifactRepository
    revision: UpstreamRevision
    file: ArtifactFile
    size_bytes: int
    sha256: Sha256Digest

    def as_document(self) -> Document:
        return {
            "repository": str(self.repository),
            "revision": str(self.revision),
            "file": str(self.file),
            "sizeBytes": self.size_bytes,
            "sha256": str(self.sha256),
        }


@dataclass(frozen=True, slots=True)
class SynchronousLlmProfile:
    """``spec.synchronousLlm``. Present for the real profile, and only for it."""

    runtime: RuntimeImage
    model_artifact: ModelArtifact

    def as_document(self) -> Document:
        return {
            "runtime": self.runtime.as_document(),
            "modelArtifact": self.model_artifact.as_document(),
        }


@dataclass(frozen=True, slots=True)
class MockLlmProfile:
    """``spec.mockLlm``. Self-labelling, so the label survives being copied.

    ``ci_only`` is always ``true`` and ``determinism`` is always
    ``fixed-fixture``. Both are constants in the schema rather than choices, and
    they are carried here rather than assumed so that an object read from a
    document still says what it is.
    """

    ci_only: bool
    determinism: MockDeterminism
    fixture_ref: RepositoryPath

    def as_document(self) -> Document:
        return {
            "ciOnly": self.ci_only,
            "determinism": self.determinism.value,
            "fixtureRef": str(self.fixture_ref),
        }


@dataclass(frozen=True, slots=True)
class WorkloadSpec:
    """``spec``. Everything the platform is entitled to act on."""

    profile: Profile
    environment: Environment
    model: ModelReference
    resources: ResourceRequest
    scaling: ScalingPolicy
    integrations: Integrations
    security: SecurityPolicy
    attribution: Attribution
    evidence: EvidenceReferences
    synchronous_llm: SynchronousLlmProfile | None = None
    mock_llm: MockLlmProfile | None = None

    def as_document(self) -> Document:
        return _without_absent(
            {
                "profile": self.profile.value,
                "environment": self.environment.value,
                "model": self.model.as_document(),
                "resources": self.resources.as_document(),
                "scaling": self.scaling.as_document(),
                "integrations": self.integrations.as_document(),
                "security": self.security.as_document(),
                "attribution": self.attribution.as_document(),
                "evidence": self.evidence.as_document(),
                "synchronousLlm": (
                    None
                    if self.synchronous_llm is None
                    else self.synchronous_llm.as_document()
                ),
                "mockLlm": (
                    None if self.mock_llm is None else self.mock_llm.as_document()
                ),
            }
        )


@dataclass(frozen=True, slots=True)
class WorkloadContract:
    """One WorkloadContract document, as the platform's own object.

    A value of this type is a document that could be *read*. It is not a document
    the platform has accepted: the cross-field and matrix rules that decide that
    are the validation pipeline's, and they have not run.
    """

    api_version: ContractVersion
    kind: str
    metadata: WorkloadMetadata
    spec: WorkloadSpec

    @property
    def workload_id(self) -> DnsLabel:
        """``workload_id``: stable, DNS-safe, unique within an environment."""
        return self.metadata.name

    @property
    def owner_id(self) -> DnsLabel:
        """``owner_id``: a workload without an owner has nobody to page."""
        return self.metadata.owner

    @property
    def tenant_id(self) -> DnsLabel:
        """``tenant_id``, as **declared**. See :class:`Attribution`."""
        return self.spec.attribution.tenant

    @property
    def is_mock(self) -> bool:
        """True for a ``mock-llm`` workload, which can certify nothing real."""
        return self.spec.profile is Profile.MOCK_LLM

    def as_document(self) -> Document:
        """The JSON wire form this object was read from, rebuilt.

        Exact, for a document this package accepted: no field is added, dropped,
        reordered in meaning, or given a default it did not carry. A test asserts
        that over every committed valid fixture, which is what makes "the domain
        object loses nothing" a checked property rather than a claim.
        """
        return {
            "apiVersion": str(self.api_version),
            "kind": self.kind,
            "metadata": self.metadata.as_document(),
            "spec": self.spec.as_document(),
        }


__all__ = [
    "Accelerator",
    "Attribution",
    "CapabilityDependency",
    "Document",
    "EvidenceReferences",
    "Integrations",
    "MockLlmProfile",
    "ModelArtifact",
    "ModelReference",
    "ResourceRequest",
    "RuntimeImage",
    "ScalingPolicy",
    "SecretReference",
    "SecurityPolicy",
    "SynchronousLlmProfile",
    "WorkloadContract",
    "WorkloadMetadata",
    "WorkloadSpec",
]
