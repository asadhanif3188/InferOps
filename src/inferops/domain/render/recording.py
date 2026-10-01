"""The provenance input-trust policy, and the one path that records a release.

A RenderedWorkloadRelease names where a render came from. What it may name is a
policy, and this module is where that policy is written down and applied:

- :data:`RELEASE_PROVENANCE` classifies **every field a release has** - every leaf
  of the published schema - and says where its value comes from. A field is either
  a public-safe identity or reference, or a derived immutable digest or revision.
  No field of a release is anything else.
- :data:`CONTEXT_FIELD_TRUST` classifies **every value a render context holds**.
  Two are public-safe identities a release records: the workload's name and its
  version. The other forty-two are excluded - the secret references, the owner
  and the people who pay for the workload, every render setting, every
  environment fact - and each says why. A field the render context does not hold
  at all, such as a contract's description or annotations, cannot be read here.
- :func:`record_release` is **the supported construction path**. It takes a
  :class:`~.normalization.RenderContext`, which only a validated contract, typed
  defaults, and a selected binding produce, and two typed references - the
  renderer's revision and the generated values' file name and digest - and reads
  each release field from the source its row in :data:`RELEASE_PROVENANCE` names,
  refusing to read a context value that is not classified a public-safe identity.
  It accepts no raw document and copies no member of one. The release it builds
  is then judged by the release domain's single-release rules, so a value shaped
  like a published credential is refused here, before anything is returned.

**What this establishes, and what it cannot.** On this path, the only text a
release carries is two values a validated contract declares as its identity, the
identity of the selected binding, a values file name a caller supplies in a typed
form, constants, and hexadecimal digests and revisions. Nothing classified
excluded - a secret reference, free text, an environment variable, a prompt or a
response, any other document member - has a way in. What the policy cannot do is
decide what an author meant: a secret deliberately written as a workload name that
is otherwise a valid DNS label has exactly the shape of a name, and no rule over
syntax can tell the two apart. That is an input-trust assumption - identities are
public - and it is stated as one, not claimed away. Repository secret scanning is a
separate control over committed files and is not part of this guarantee.

Offline and deterministic like the rest of the package: no clock, no random
source, no environment variable, no file.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..release.canonical import derive_release_id
from ..release.errors import CONTRACT_INVALID, MalformedReleaseError, ReleaseError
from ..release.provenance import check_rendered_workload_release
from ..release.release import (
    HelmValuesReference,
    ReleaseMetadata,
    ReleaseOutput,
    RenderedWorkloadRelease,
    RendererReference,
)
from ..release.values import (
    GitRevision,
    Sha256Hex,
    ValuesFileName,
    parse_release_workload_version,
)
from ..release.versions import (
    RENDERED_WORKLOAD_RELEASE_KIND,
    SUPPORTED_RELEASE_VERSIONS,
    ReleaseVersion,
)
from ..workload.errors import DomainError, InvalidValueError
from ..workload.values import DnsLabel
from .normalization import RenderContext


class ProvenanceTrust(StrEnum):
    """What a value is, for the purpose of recording it in provenance. Closed."""

    #: A name or a reference that identifies an input or an output and is public
    #: by policy: a workload name, a version, a binding name, a file name.
    PUBLIC_IDENTITY = "public-identity"
    #: A digest or a full commit revision: fixed-length hexadecimal, computed or
    #: pinned, never prose.
    DERIVED_DIGEST = "derived-digest"
    #: Never recorded. Sensitive, free text, untrusted, or simply not an identity.
    EXCLUDED = "excluded"


class ProvenanceOrigin(StrEnum):
    """Where :func:`record_release` reads a release field's value from."""

    #: The release version this module records, and its kind.
    RELEASE = "release"
    #: A value of the render context, by its context name.
    CONTEXT_VALUE = "context-value"
    #: The render context's sources, by their path in the release's ``source``.
    CONTEXT_SOURCE = "context-source"
    #: The ``renderer`` argument: a typed revision.
    RENDERER = "renderer"
    #: The ``helm_values`` argument: a typed file name and digest.
    HELM_VALUES = "helm-values"
    #: Computed from the other fields by the release identity rule.
    DERIVATION = "derivation"


@dataclass(frozen=True, slots=True)
class ProvenanceField:
    """One field of a release: its trust class, and where its value comes from."""

    field: str
    trust: ProvenanceTrust
    origin: ProvenanceOrigin
    source: str


@dataclass(frozen=True, slots=True)
class ContextFieldTrust:
    """One value of the render context, classified, with the reason."""

    trust: ProvenanceTrust
    reason: str


def _p(field: str, origin: ProvenanceOrigin, source: str) -> ProvenanceField:
    return ProvenanceField(field, ProvenanceTrust.PUBLIC_IDENTITY, origin, source)


def _d(field: str, origin: ProvenanceOrigin, source: str) -> ProvenanceField:
    return ProvenanceField(field, ProvenanceTrust.DERIVED_DIGEST, origin, source)


_O = ProvenanceOrigin

#: Every field of a release, in the published schema's order. A test holds the
#: field list to the schema's leaves and every row to the value it produces.
RELEASE_PROVENANCE: Final[tuple[ProvenanceField, ...]] = (
    _p("apiVersion", _O.RELEASE, "apiVersion"),
    _p("kind", _O.RELEASE, "kind"),
    _p("metadata.workloadId", _O.CONTEXT_VALUE, "workload.id"),
    _p("metadata.workloadVersion", _O.CONTEXT_VALUE, "workload.version"),
    _d("metadata.releaseId", _O.DERIVATION, "releaseId"),
    _p("source.contract.apiVersion", _O.CONTEXT_SOURCE, "contract.apiVersion"),
    _d("source.contract.sha256", _O.CONTEXT_SOURCE, "contract.sha256"),
    _p(
        "source.environmentBinding.apiVersion",
        _O.CONTEXT_SOURCE,
        "environmentBinding.apiVersion",
    ),
    _p(
        "source.environmentBinding.environment",
        _O.CONTEXT_SOURCE,
        "environmentBinding.environment",
    ),
    _p("source.environmentBinding.name", _O.CONTEXT_SOURCE, "environmentBinding.name"),
    _d(
        "source.environmentBinding.sha256",
        _O.CONTEXT_SOURCE,
        "environmentBinding.sha256",
    ),
    _d("source.renderer.revision", _O.RENDERER, "revision"),
    _d(
        "source.platformDefaults.revision",
        _O.CONTEXT_SOURCE,
        "platformDefaults.revision",
    ),
    _p("output.helmValues.path", _O.HELM_VALUES, "path"),
    _d("output.helmValues.sha256", _O.HELM_VALUES, "sha256"),
)

_IDENTITY = "the workload's identity, which a release records: public by policy"
_SENSITIVE = (
    "sensitive: names the secrets the workload reads; a reference is not a value, "
    "and provenance carries neither"
)
_PEOPLE = (
    "who owns or pays for the workload; it identifies an organisation, not a "
    "release, and the contract digest covers it"
)
_INTENT = (
    "a render setting the contract declares, not an identity; the contract digest "
    "covers it"
)
_REFERENCE = (
    "a reference to another artifact the contract cites, not an identity of this "
    "release; the contract digest covers it"
)
_DEFAULT = (
    "a platform default, not an identity; the platform-defaults revision covers it"
)
_FACT = (
    "a fact of one environment, not an identity; the binding digest covers it, and "
    "the binding is recorded by name"
)


def _public(reason: str) -> ContextFieldTrust:
    return ContextFieldTrust(ProvenanceTrust.PUBLIC_IDENTITY, reason)


def _excluded(reason: str) -> ContextFieldTrust:
    return ContextFieldTrust(ProvenanceTrust.EXCLUDED, reason)


#: Every value of the render context, classified. A test fails if the render
#: context gains a value this table does not name, or if one is named twice.
CONTEXT_FIELD_TRUST: Final[Mapping[str, ContextFieldTrust]] = MappingProxyType(
    {
        name: classified
        for name, classified in (
            ("workload.id", _public(_IDENTITY)),
            ("workload.version", _public(_IDENTITY)),
            ("workload.owner", _excluded(_PEOPLE)),
            ("workload.profile", _excluded(_INTENT)),
            ("workload.environment", _excluded(_INTENT)),
            ("model.servingCapability", _excluded(_INTENT)),
            ("model.ref", _excluded(_REFERENCE)),
            ("model.runtimeProfile", _excluded(_INTENT)),
            ("resources.cpu", _excluded(_INTENT)),
            ("resources.memory", _excluded(_INTENT)),
            ("resources.accelerator.type", _excluded(_INTENT)),
            ("resources.accelerator.count", _excluded(_INTENT)),
            ("serving.replicas.minimum", _excluded(_INTENT)),
            ("serving.replicas.maximum", _excluded(_INTENT)),
            ("integrations.telemetry.capabilityRef", _excluded(_REFERENCE)),
            ("integrations.telemetry.required", _excluded(_INTENT)),
            ("integrations.modelAccess.capabilityRef", _excluded(_REFERENCE)),
            ("integrations.modelAccess.required", _excluded(_INTENT)),
            ("integrations.evaluation.capabilityRef", _excluded(_REFERENCE)),
            ("integrations.evaluation.required", _excluded(_INTENT)),
            ("security.dataClassification", _excluded(_INTENT)),
            ("security.secretRefs", _excluded(_SENSITIVE)),
            ("attribution.tenant", _excluded(_PEOPLE)),
            ("attribution.costCenter", _excluded(_PEOPLE)),
            ("evidence.runbookRef", _excluded(_REFERENCE)),
            ("evidence.proofRefs", _excluded(_REFERENCE)),
            ("runtime.imageReference", _excluded(_REFERENCE)),
            ("model.artifact.repository", _excluded(_REFERENCE)),
            ("model.artifact.revision", _excluded(_REFERENCE)),
            ("model.artifact.file", _excluded(_REFERENCE)),
            ("model.artifact.sizeBytes", _excluded(_INTENT)),
            ("model.artifact.sha256", _excluded(_REFERENCE)),
            ("mock.ciOnly", _excluded(_INTENT)),
            ("mock.determinism", _excluded(_INTENT)),
            ("mock.fixtureRef", _excluded(_REFERENCE)),
            ("api.requestTimeoutMs", _excluded(_DEFAULT)),
            ("api.drainTimeoutMs", _excluded(_DEFAULT)),
            ("api.maxOutputTokens", _excluded(_DEFAULT)),
            ("destination.clusterProvider", _excluded(_FACT)),
            ("destination.namespace", _excluded(_FACT)),
            ("modelCache.class", _excluded(_FACT)),
            ("modelCache.claimName", _excluded(_FACT)),
            ("api.replicas", _excluded(_FACT)),
            ("gitops.destinationPath", _excluded(_FACT)),
        )
    }
)

#: The release version a release is recorded at: the newest this package reads.
RECORDED_RELEASE_VERSION: Final = SUPPORTED_RELEASE_VERSIONS[-1]


class ReleaseNotRecordedError(DomainError):
    """A release could not be recorded from this render context. Carries every reason.

    Each refusal is a :class:`~inferops.domain.release.errors.ReleaseError`: a
    single-release rule under its published identifier, or a value the release
    version cannot hold. None repeats a value; none resolves itself on retry.
    """

    code: str = CONTRACT_INVALID

    def __init__(self, refusals: Sequence[ReleaseError]) -> None:
        self.refusals: tuple[ReleaseError, ...] = tuple(refusals)
        super().__init__(
            "no release was recorded: "
            + "; ".join(f"{entry.field}: {entry.reason}" for entry in self.refusals)
        )

    @property
    def retryable(self) -> bool:
        return False

    def as_dict(self) -> dict[str, object]:
        """A safe, structured form: code, and every refusal's own form."""
        return {
            "code": self.code,
            "retryable": self.retryable,
            "refusals": [entry.as_dict() for entry in self.refusals],
        }


def provenance_field(field: str) -> ProvenanceField:
    """The row of :data:`RELEASE_PROVENANCE` for one release field.

    Raises:
        KeyError: a release has no field of that path.
    """
    for row in RELEASE_PROVENANCE:
        if row.field == field:
            return row
    raise KeyError(field)


def _public_context_value(render_context: RenderContext, field: str) -> str:
    """A release field read from the context value its row names, if that is public.

    Both tables are read at call time, so neither can be edited to open a path
    without this refusing it. Reaching a refusal here is a defect in the policy
    tables, not a refusal of an input.
    """
    row = provenance_field(field)
    if row.origin is not ProvenanceOrigin.CONTEXT_VALUE:
        raise AssertionError(f"the release field {field!r} is not read from a value")
    if row.trust is not ProvenanceTrust.PUBLIC_IDENTITY:
        raise AssertionError(
            f"the release field {field!r} is not classified a public identity"
        )
    classified = CONTEXT_FIELD_TRUST.get(row.source)
    if classified is None or classified.trust is not ProvenanceTrust.PUBLIC_IDENTITY:
        raise AssertionError(
            f"the render value {row.source!r} is not classified a public identity, "
            "so no release field may be read from it"
        )
    value = render_context.value(row.source)
    if not isinstance(value, str):
        raise AssertionError(f"the render value {row.source!r} is not a string")
    return value


def record_release(
    render_context: RenderContext,
    *,
    renderer: RendererReference,
    helm_values: HelmValuesReference,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> RenderedWorkloadRelease:
    """The release a renderer at ``renderer`` records for ``render_context``.

    Every field is read from the source :data:`RELEASE_PROVENANCE` names; the
    release identifier is derived, never supplied. The release is judged by the
    release domain's single-release rules before it is returned, so the identifier
    is derived and no value in it begins, or has a part that begins, with a
    published credential prefix. The release agrees with the contract and binding
    the context was built from by construction; ``verify_release_sources`` confirms
    that for a caller holding both.

    Args:
        render_context: a context :func:`~.normalization.build_render_context` or
            :func:`~.normalization.prepare_render` returned.
        renderer: the full commit the renderer ran from.
        helm_values: the generated values file's name and digest.
        context: request-scoped identifiers, attached to every refusal.

    Raises:
        ReleaseNotRecordedError: the release would be refused; every reason at
            once, none quoting a value.
        TypeError: an argument is not the typed object this reads - a raw
            document, a dictionary, a bare string, or a reference built around
            bare strings instead of its constrained types.
    """
    if not isinstance(render_context, RenderContext):
        raise TypeError(
            "render_context must be a RenderContext produced by build_render_context "
            "or prepare_render, not a raw document"
        )
    # The references are dataclasses and check nothing themselves, so each member
    # must be the constrained type that refused a malformed value when it was made.
    if not isinstance(renderer, RendererReference) or not isinstance(
        renderer.revision, GitRevision
    ):
        raise TypeError("renderer must be a RendererReference holding a GitRevision")
    if (
        not isinstance(helm_values, HelmValuesReference)
        or not isinstance(helm_values.path, ValuesFileName)
        or not isinstance(helm_values.sha256, Sha256Hex)
    ):
        raise TypeError(
            "helm_values must be a HelmValuesReference holding a ValuesFileName "
            "and a Sha256Hex"
        )

    workload_id = DnsLabel(_public_context_value(render_context, "metadata.workloadId"))
    try:
        workload_version = parse_release_workload_version(
            _public_context_value(render_context, "metadata.workloadVersion")
        )
    except InvalidValueError:
        raise ReleaseNotRecordedError(
            [
                MalformedReleaseError(
                    "release.metadata.workloadVersion",
                    "the contract's version is neither a lowercase semantic "
                    "version nor an image reference pinned by digest, so this "
                    "release version cannot record it",
                    context=context,
                )
            ]
        ) from None

    source = render_context.sources.release_source(renderer)
    release = RenderedWorkloadRelease(
        api_version=ReleaseVersion.parse(RECORDED_RELEASE_VERSION, context=context),
        kind=RENDERED_WORKLOAD_RELEASE_KIND,
        metadata=ReleaseMetadata(
            workload_id=workload_id,
            workload_version=workload_version,
            release_id=derive_release_id(workload_id, workload_version, source),
        ),
        source=source,
        output=ReleaseOutput(helm_values=helm_values),
    )
    refusals = check_rendered_workload_release(release, context=context)
    if refusals:
        raise ReleaseNotRecordedError(refusals)
    return release


__all__ = [
    "CONTEXT_FIELD_TRUST",
    "RECORDED_RELEASE_VERSION",
    "RELEASE_PROVENANCE",
    "ContextFieldTrust",
    "ProvenanceField",
    "ProvenanceOrigin",
    "ProvenanceTrust",
    "ReleaseNotRecordedError",
    "provenance_field",
    "record_release",
]
