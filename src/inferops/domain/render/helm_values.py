"""The Helm values renderer: one render context in, the ``inferops-llm`` chart's values out.

:class:`HelmValuesRenderer` is the first :class:`~.renderer.Renderer`. It takes a
:class:`~.normalization.RenderContext` for a ``synchronous-llm`` workload and returns
:class:`GeneratedHelmValues`: the values of the existing chart that the contract, the
platform defaults, and the selected binding decide, and nothing else. It extends the
chart's values contract rather than defining a release format beside it: every value it
writes is a value ``charts/inferops-llm/values.schema.json`` already defines, and every
value it does not write keeps the chart's own default or comes from a hand-written file.

**Every context value is accounted for.** :data:`HELM_VALUE_DISPOSITIONS` names each of
the context's values once, and says what the renderer does with it:

- **rendered** - written to the chart values it names. Twenty-four values, written to
  twenty-five chart values: the runtime image reference is split into its repository
  and its digest, as the chart pins them;
- **constrained** - not written, because the chart has no setting for it, and refused
  unless it asks for what the chart already does: a fixed replica count, no
  accelerator, the one runtime sizing the chart configures, and no integration but
  the platform's telemetry. Eight values;
- **not rendered** - not written, and no chart setting depends on it: identity the
  release records elsewhere, documentation references, the mock profile's block, and
  environment facts that are install arguments rather than values. Twelve values.

**What it refuses, and why.** A context reaches the renderer only after the boundary
accepted it, so every refusal here is about the chart, not the input:

- ``render-capability-unsupported`` - the contract asks for something the chart does
  not provide: a replica range, an accelerator, another runtime sizing, a model-access
  or evaluation integration, a telemetry capability other than the platform's, or a
  secret reference. A secret reference is refused because the chart binds a named
  Kubernetes Secret key to an environment variable, a contract names a provider and a
  locator, and no accepted rule maps one to the other; inventing one here would render
  a binding nobody decided;
- ``render-value-unsupported`` - an accepted value has no form the chart's schema
  accepts. :data:`CHART_VALUE_CONSTRAINTS` holds the schema's constraint for every
  value written, and a test reads the schema and fails if one differs, so a contract
  value wider than the chart - a ``staging`` environment, a pre-release version, a
  ``Pi`` quantity - is refused here rather than by Helm. A CPU or memory limit below
  the chart's own runtime request is refused too, because Kubernetes refuses a
  container whose request exceeds its limit;
- ``render-value-credential-shaped`` - a string the renderer would write has a part that
  begins with a published credential prefix. Generated values are written to Git, so
  this is what generated output may carry: names, references, and digests, never a
  value shaped like a credential, whichever layer supplied it;
- ``render-profile-unsupported`` and the two version rules - the renderer was not built
  for the context's profile or input versions. :func:`~.renderer.render_with` refuses
  those before calling the renderer; ``render`` refuses them again for a context built
  without that check.

**Resources mean limits.** The contract's ``cpu`` and ``memory`` are the ceiling the
workload runs under, and render to the runtime's limits. The runtime's requests are the
chart's: they reserve what a local cluster can schedule - one CPU and two gibibytes -
and a request equal to the contract's six CPUs would not schedule on a host the
environment scripts accept. That is the V1 release's own split, and it is kept.

**Hand-written values.** A release is installed with the generated values and, beside
them, a hand-written file for what no input owns - the API image a contributor built,
the model's alias, licence, and download URL. :func:`manual_value_findings` refuses a
hand-written file that sets, replaces, or removes a value the renderer generates, so a
value the contract owns cannot be written a second time by hand.

**Pure.** Rendering reads no clock, file, environment variable, or network, and writes
nothing; equal contexts give equal values and the same canonical YAML. The renderer's
revision names the commit it runs from and takes no part in the values.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..release.provenance import is_credential_shaped
from ..release.values import GitRevision
from ..workload.values import Profile
from .errors import RenderFinding, RenderRefused
from .normalization import RenderContext, RenderField, _frozen, _thawed
from .ownership import Layer
from .support import RendererSupport
from .values_yaml import canonical_yaml

#: The chart the values are for, and the version they were written against. A test
#: compares both with ``charts/inferops-llm/Chart.yaml``, so a chart change fails the
#: build until somebody reads this mapping against it.
CHART_NAME: Final = "inferops-llm"
CHART_VERSION: Final = "0.3.0"

#: What the renderer takes: today's input versions and the synchronous profile only.
HELM_VALUES_SUPPORT: Final = RendererSupport(
    contract_versions=frozenset({"inferops.io/v1alpha1"}),
    binding_versions=frozenset({"inferops.io/v1alpha1"}),
    platform_defaults_versions=frozenset({"v1alpha1"}),
    profiles=frozenset({Profile.SYNCHRONOUS_LLM}),
)

#: The chart's ``profile`` for the one workload profile the renderer takes.
CHART_PROFILE: Final = "real"

#: The one telemetry capability the chart provides.
PLATFORM_TELEMETRY: Final = "platform-telemetry"

#: The runtime sizing the chart configures: one CPU runtime, one slot.
CHART_RUNTIME_PROFILE: Final = "resource-conscious"

#: The chart's own runtime requests, which a rendered limit may not fall below. A
#: test compares them with ``runtime.resources.requests`` in the chart's values.
CHART_RUNTIME_REQUESTS: Final[Mapping[str, str]] = MappingProxyType(
    {"cpu": "1", "memory": "2Gi"}
)

#: Comment lines written above the generated values. Constant: no revision, no date.
VALUES_HEADER: Final[tuple[str, ...]] = (
    f"Generated Helm values for the {CHART_NAME} chart, version {CHART_VERSION}.",
    "Do not edit by hand: change the WorkloadContract, the EnvironmentBinding, or",
    "the platform defaults they were rendered from, and render them again.",
)


class Disposition(StrEnum):
    """What the renderer does with one render-context value. Closed."""

    #: Written to the chart values the row names.
    RENDERED = "rendered"
    #: Not written; refused unless it asks for what the chart already does.
    CONSTRAINED = "constrained"
    #: Not written, and no chart setting depends on it.
    NOT_RENDERED = "not-rendered"


@dataclass(frozen=True, slots=True)
class ValueDisposition:
    """One context value: what happens to it, the chart values it reaches, and why."""

    disposition: Disposition
    targets: tuple[str, ...]
    reason: str


def _rendered(*targets: str, reason: str) -> ValueDisposition:
    return ValueDisposition(Disposition.RENDERED, targets, reason)


def _constrained(reason: str) -> ValueDisposition:
    return ValueDisposition(Disposition.CONSTRAINED, (), reason)


def _not_rendered(reason: str) -> ValueDisposition:
    return ValueDisposition(Disposition.NOT_RENDERED, (), reason)


_SAME = "the chart value of the same meaning"
_MOCK = (
    "the mock profile's block; the renderer takes the synchronous profile only, so "
    "no context it renders holds one"
)
_INTEGRATION = (
    "the chart wires no model-access or evaluation capability, so declaring one is "
    "refused rather than dropped"
)

#: Every value of the render context, in the ownership table's order, with what the
#: renderer does with it. A test fails if the context gains a value this table does
#: not name.
HELM_VALUE_DISPOSITIONS: Final[Mapping[str, ValueDisposition]] = MappingProxyType(
    {
        "workload.id": _rendered("ownership.workloadId", reason=_SAME),
        "workload.version": _rendered("ownership.workloadVersion", reason=_SAME),
        "workload.owner": _rendered("ownership.owner", reason=_SAME),
        "workload.profile": _rendered(
            "profile",
            reason="synchronous-llm is the chart's real profile; the chart derives "
            "the serving capability and the adapter from it",
        ),
        "workload.environment": _rendered(
            "telemetry.deploymentEnvironment",
            reason="the environment every emitted record carries",
        ),
        "model.servingCapability": _not_rendered(
            "the chart derives the capability from its profile, and the boundary "
            "already requires the native capability for this profile"
        ),
        "model.ref": _rendered(
            "model.identifier",
            reason="the platform identifier a caller's model member is checked against",
        ),
        "model.runtimeProfile": _constrained(
            "the chart configures one runtime sizing, so only that sizing is accepted"
        ),
        "resources.cpu": _rendered(
            "runtime.resources.limits.cpu",
            reason="the ceiling the runtime runs under; the request stays the chart's",
        ),
        "resources.memory": _rendered(
            "runtime.resources.limits.memory",
            reason="the ceiling the runtime runs under; the request stays the chart's",
        ),
        "resources.accelerator.type": _constrained(
            "the chart requests no accelerator, so only none is accepted"
        ),
        "resources.accelerator.count": _constrained(
            "the chart requests no accelerator, so only a count of zero is accepted"
        ),
        "serving.replicas.minimum": _rendered(
            "runtime.replicaCount",
            reason="the chart runs a fixed replica count, so the range must be one "
            "number",
        ),
        "serving.replicas.maximum": _constrained(
            "the chart has no autoscaler, so the maximum must equal the minimum"
        ),
        "integrations.telemetry.capabilityRef": _rendered(
            "telemetry.enabled",
            reason="the platform's telemetry is the chart's own, so declaring it "
            "enables it; another capability is refused",
        ),
        "integrations.telemetry.required": _not_rendered(
            "telemetry is enabled for every workload, which satisfies either answer"
        ),
        "integrations.modelAccess.capabilityRef": _constrained(_INTEGRATION),
        "integrations.modelAccess.required": _constrained(_INTEGRATION),
        "integrations.evaluation.capabilityRef": _constrained(_INTEGRATION),
        "integrations.evaluation.required": _constrained(_INTEGRATION),
        "security.dataClassification": _not_rendered(
            "no chart setting acts on a classification, and no policy engine reads one"
        ),
        "security.secretRefs": _rendered(
            "security.secretRefs",
            reason="rendered empty; a declared reference is refused, because no "
            "accepted rule maps a contract locator to the chart's secret binding",
        ),
        "attribution.tenant": _rendered("ownership.tenant", reason=_SAME),
        "attribution.costCenter": _rendered("ownership.costCenter", reason=_SAME),
        "evidence.runbookRef": _not_rendered(
            "a documentation reference; no chart setting reads it"
        ),
        "evidence.proofRefs": _not_rendered(
            "documentation references; no chart setting reads them"
        ),
        "runtime.imageReference": _rendered(
            "runtime.image.repository",
            "runtime.image.digest",
            reason="split at its digest, because the chart pins the repository and "
            "the digest as two values",
        ),
        "model.artifact.repository": _rendered(
            "model.artifact.repository", reason=_SAME
        ),
        "model.artifact.revision": _rendered(
            "model.revision",
            reason="the chart derives the in-claim directory from it",
        ),
        "model.artifact.file": _rendered("model.artifact.fileName", reason=_SAME),
        "model.artifact.sizeBytes": _rendered("model.artifact.sizeBytes", reason=_SAME),
        "model.artifact.sha256": _rendered("model.artifact.sha256", reason=_SAME),
        "mock.ciOnly": _not_rendered(_MOCK),
        "mock.determinism": _not_rendered(_MOCK),
        "mock.fixtureRef": _not_rendered(_MOCK),
        "api.requestTimeoutMs": _rendered("api.requestTimeoutMs", reason=_SAME),
        "api.drainTimeoutMs": _rendered("api.drainTimeoutMs", reason=_SAME),
        "api.maxOutputTokens": _rendered("api.maxOutputTokens", reason=_SAME),
        "destination.clusterProvider": _not_rendered(
            "selects the cluster a release is installed into; not a chart value"
        ),
        "destination.namespace": _not_rendered(
            "the release namespace is an install argument, not a value, and the "
            "chart checks its prefix itself"
        ),
        "modelCache.class": _not_rendered(
            "the chart mounts an existing claim, the one class this binding version has"
        ),
        "modelCache.claimName": _rendered(
            "model.cache.claimName", reason="the existing claim the runtime mounts"
        ),
        "api.replicas": _rendered("api.replicaCount", reason=_SAME),
        "gitops.destinationPath": _not_rendered(
            "where a release is written, not something a release reads"
        ),
    }
)


@dataclass(frozen=True, slots=True)
class ChartValueConstraint:
    """The chart schema's constraint on one value the renderer writes.

    ``kind`` is the JSON type. A member left ``None`` is a keyword the schema does not
    apply to that value.
    """

    kind: str
    pattern: str | None = None
    max_length: int | None = None
    enum: tuple[str, ...] | None = None
    minimum: int | None = None
    maximum: int | None = None
    max_items: int | None = None


def _string(
    pattern: str | None = None,
    *,
    max_length: int | None = None,
    enum: tuple[str, ...] | None = None,
) -> ChartValueConstraint:
    return ChartValueConstraint(
        "string", pattern=pattern, max_length=max_length, enum=enum
    )


def _integer(minimum: int, maximum: int | None = None) -> ChartValueConstraint:
    return ChartValueConstraint("integer", minimum=minimum, maximum=maximum)


_DNS_SAFE_OR_EMPTY = "^$|^[a-z0-9]([a-z0-9-]*[a-z0-9])?$"
_SHA256 = "^$|^sha256:[0-9a-f]{64}$"

#: Every value the renderer writes, with the constraint the chart's values schema
#: applies to it, copied from the schema and held to it by a test.
CHART_VALUE_CONSTRAINTS: Final[Mapping[str, ChartValueConstraint]] = MappingProxyType(
    {
        "api.drainTimeoutMs": _integer(1, 3_600_000),
        "api.maxOutputTokens": _integer(1, 32_768),
        "api.replicaCount": _integer(1, 16),
        "api.requestTimeoutMs": _integer(1, 3_600_000),
        "model.artifact.fileName": _string(
            "^$|^[A-Za-z0-9][A-Za-z0-9._-]*$", max_length=253
        ),
        "model.artifact.repository": _string(
            "^$|^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$",
            max_length=253,
        ),
        "model.artifact.sha256": _string(_SHA256),
        "model.artifact.sizeBytes": _integer(0),
        "model.cache.claimName": _string(
            "^$|^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$", max_length=253
        ),
        "model.identifier": _string(_DNS_SAFE_OR_EMPTY, max_length=63),
        "model.revision": _string("^$|^[0-9a-f]{40}$"),
        "ownership.costCenter": _string(max_length=63),
        "ownership.owner": _string(_DNS_SAFE_OR_EMPTY, max_length=63),
        "ownership.tenant": _string(max_length=63),
        "ownership.workloadId": _string(_DNS_SAFE_OR_EMPTY, max_length=63),
        "ownership.workloadVersion": _string("^$|^[0-9]+\\.[0-9]+\\.[0-9]+$"),
        "profile": _string(enum=("", "mock", "real")),
        "runtime.image.digest": _string(_SHA256),
        "runtime.image.repository": _string(
            "^$|^[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[0-9]+)?"
            "(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*$",
            max_length=255,
        ),
        "runtime.replicaCount": _integer(1, 16),
        "runtime.resources.limits.cpu": _string("^[0-9]+(\\.[0-9]+)?m?$"),
        "runtime.resources.limits.memory": _string(
            "^[0-9]+(\\.[0-9]+)?(Ki|Mi|Gi|Ti|k|M|G|T)?$"
        ),
        "security.secretRefs": ChartValueConstraint("array", max_items=16),
        "telemetry.deploymentEnvironment": _string(enum=("dev", "ci", "local", "test")),
        "telemetry.enabled": ChartValueConstraint("boolean"),
    }
)

#: Every value the renderer writes, as a path of member names. A successful render
#: writes all of them; a hand-written values file may set none of them.
GENERATED_VALUE_PATHS: Final[frozenset[tuple[str, ...]]] = frozenset(
    tuple(path.split(".")) for path in CHART_VALUE_CONSTRAINTS
)

#: Every character a written string may hold, as the canonical YAML form requires.
_PRINTABLE: Final = re.compile(r"[\x20-\x7e]*", re.ASCII)

#: What one unit of each suffix the chart's quantity patterns admit is worth, as a
#: numerator and a denominator.
_UNITS: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        "": (1, 1),
        "m": (1, 1000),
        "k": (10**3, 1),
        "M": (10**6, 1),
        "G": (10**9, 1),
        "T": (10**12, 1),
        "Ki": (2**10, 1),
        "Mi": (2**20, 1),
        "Gi": (2**30, 1),
        "Ti": (2**40, 1),
    }
)
_QUANTITY: Final = re.compile(r"([0-9]+)(?:\.([0-9]+))?([A-Za-z]*)", re.ASCII)

_ROLES: Final[Mapping[Layer, str]] = MappingProxyType(
    {
        Layer.WORKLOAD_INTENT: "contract",
        Layer.PLATFORM_DEFAULTS: "platformDefaults",
        Layer.ENVIRONMENT_BINDING: "binding",
    }
)


def _field(entry: RenderField) -> str:
    """Where a context value came from: its input's role, then its source path."""
    return f"{_ROLES[entry.layer]}.{entry.source}"


def _satisfies(constraint: ChartValueConstraint, value: object) -> bool:
    """Whether the chart's schema accepts ``value`` under ``constraint``."""
    if constraint.kind == "boolean":
        return isinstance(value, bool)
    if constraint.kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return False
        return (constraint.minimum is None or value >= constraint.minimum) and (
            constraint.maximum is None or value <= constraint.maximum
        )
    if constraint.kind == "array":
        return isinstance(value, list) and (
            constraint.max_items is None or len(value) <= constraint.max_items
        )
    if not isinstance(value, str) or _PRINTABLE.fullmatch(value) is None:
        return False
    if constraint.max_length is not None and len(value) > constraint.max_length:
        return False
    if constraint.enum is not None and value not in constraint.enum:
        return False
    return constraint.pattern is None or (
        re.search(constraint.pattern, value, re.ASCII) is not None
    )


def _quantity(text: str) -> tuple[int, int]:
    """A quantity the chart's pattern accepts, as an exact numerator and denominator."""
    match = _QUANTITY.fullmatch(text)
    if match is None or match.group(3) not in _UNITS:
        raise AssertionError("a quantity that passed the chart's pattern did not parse")
    whole, fraction, suffix = match.groups()
    fraction = fraction or ""
    numerator, denominator = _UNITS[suffix]
    return int(whole + fraction) * numerator, 10 ** len(fraction) * denominator


def _below(value: str, floor: str) -> bool:
    (a, b), (c, d) = _quantity(value), _quantity(floor)
    return a * d < c * b


@dataclass(frozen=True, slots=True)
class _Leaf:
    """One chart value the renderer would write, and the context value it came from."""

    path: str
    value: Any
    source: RenderField


def _present(context: RenderContext, name: str) -> RenderField | None:
    try:
        return context.entry(name)
    except KeyError:
        return None


def _support_findings(
    context: RenderContext, request: RequestContext
) -> list[RenderFinding]:
    """The support checks ``render_with`` makes, made again on the context alone."""
    support = HELM_VALUES_SUPPORT
    findings: list[RenderFinding] = []
    if context.value("workload.profile") not in {str(p) for p in support.profiles}:
        findings.append(
            RenderFinding(
                "render-profile-unsupported",
                "contract.spec.profile",
                "the renderer was not built for this profile",
                request,
            )
        )
    if str(context.sources.contract.api_version) not in support.contract_versions:
        findings.append(
            RenderFinding(
                "render-contract-version-unsupported",
                "contract.apiVersion",
                "the renderer does not take this contract version",
                request,
            )
        )
    binding = context.sources.environment_binding
    if str(binding.api_version) not in support.binding_versions:
        findings.append(
            RenderFinding(
                "render-binding-version-unsupported",
                "binding.apiVersion",
                "the renderer does not take this binding version",
                request,
            )
        )
    return findings


def _capability_findings(
    context: RenderContext, request: RequestContext
) -> list[RenderFinding]:
    """Every constrained value that asks for something the chart does not provide."""

    def refuse(entry: RenderField, reason: str) -> RenderFinding:
        return RenderFinding(
            "render-capability-unsupported", _field(entry), reason, request
        )

    findings: list[RenderFinding] = []
    minimum = context.entry("serving.replicas.minimum")
    maximum = context.entry("serving.replicas.maximum")
    if maximum.value != minimum.value:
        findings.append(
            refuse(
                maximum,
                "the chart runs a fixed replica count and has no autoscaler, so the "
                "maximum must equal the minimum",
            )
        )
    accelerator = context.entry("resources.accelerator.type")
    if accelerator.value != "none":
        findings.append(refuse(accelerator, "the chart requests no accelerator"))
    count = context.entry("resources.accelerator.count")
    if count.value != 0:
        findings.append(refuse(count, "the chart requests no accelerator"))
    sizing = context.entry("model.runtimeProfile")
    if sizing.value != CHART_RUNTIME_PROFILE:
        findings.append(
            refuse(sizing, "the chart configures one runtime sizing, and not this one")
        )
    telemetry = context.entry("integrations.telemetry.capabilityRef")
    if telemetry.value != PLATFORM_TELEMETRY:
        findings.append(
            refuse(
                telemetry, "the chart provides the platform's telemetry and no other"
            )
        )
    for name in ("modelAccess", "evaluation"):
        declared = _present(context, f"integrations.{name}.capabilityRef")
        if declared is not None:
            findings.append(refuse(declared, f"the chart wires no {name} capability"))
    secrets = context.entry("security.secretRefs")
    if secrets.value:
        findings.append(
            refuse(
                secrets,
                "no accepted rule maps a contract secret reference to the chart's "
                "secret binding, so a declared reference cannot be rendered",
            )
        )
    return findings


def _leaves(context: RenderContext) -> Iterator[_Leaf]:
    """Every chart value a render of ``context`` would write, with its source."""
    for name, row in HELM_VALUE_DISPOSITIONS.items():
        if row.disposition is not Disposition.RENDERED:
            continue
        entry = context.entry(name)
        if name == "workload.profile":
            values: tuple[Any, ...] = (CHART_PROFILE,)
        elif name == "integrations.telemetry.capabilityRef":
            values = (True,)
        elif name == "runtime.imageReference":
            repository, _, digest = str(entry.value).rpartition("@")
            values = (repository, digest)
        else:
            values = (_thawed(entry.value),)
        for path, value in zip(row.targets, values, strict=True):
            yield _Leaf(path, value, entry)


def _value_findings(
    leaves: tuple[_Leaf, ...], request: RequestContext
) -> list[RenderFinding]:
    findings: list[RenderFinding] = []
    for leaf in leaves:
        resource = leaf.path.rpartition(".")[2]
        if not _satisfies(CHART_VALUE_CONSTRAINTS[leaf.path], leaf.value):
            findings.append(
                RenderFinding(
                    "render-value-unsupported",
                    _field(leaf.source),
                    f"the chart's {leaf.path} accepts no form of this value",
                    request,
                )
            )
        elif leaf.path.startswith("runtime.resources.limits.") and _below(
            leaf.value, CHART_RUNTIME_REQUESTS[resource]
        ):
            findings.append(
                RenderFinding(
                    "render-value-unsupported",
                    _field(leaf.source),
                    f"this limit is below the chart's runtime {resource} request, "
                    "and Kubernetes refuses a request above its limit",
                    request,
                )
            )
        if isinstance(leaf.value, str) and is_credential_shaped(leaf.value):
            findings.append(
                RenderFinding(
                    "render-value-credential-shaped",
                    _field(leaf.source),
                    "a part of this value begins with the published prefix of a "
                    "credential format; generated values are written to Git and "
                    "never carry one",
                    request,
                )
            )
    return findings


def _nested(leaves: tuple[_Leaf, ...]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for leaf in leaves:
        *parents, last = leaf.path.split(".")
        node = document
        for part in parents:
            node = node.setdefault(part, {})
        node[last] = leaf.value
    return document


def _leaf_paths(document: Mapping[str, Any], prefix: str = "") -> Iterator[str]:
    for key, value in document.items():
        path = f"{prefix}{key}"
        if isinstance(value, Mapping) and value:
            yield from _leaf_paths(value, f"{path}.")
        else:
            yield path


@dataclass(frozen=True, slots=True)
class GeneratedHelmValues:
    """The chart values one render wrote. Read-only; produced by the renderer.

    ``values`` is the values document, with every list a tuple and every object a
    read-only mapping. It takes no part in the hash, as a render value does not.
    """

    values: Mapping[str, Any] = field(hash=False)

    def as_document(self) -> dict[str, Any]:
        """The values as plain JSON-form dictionaries and lists."""
        document: dict[str, Any] = _thawed(self.values)
        return document

    def paths(self) -> tuple[str, ...]:
        """Every value written, as a dotted path, sorted."""
        return tuple(sorted(_leaf_paths(self.values)))

    def to_yaml(self) -> str:
        """The canonical YAML text: the fixed header, then the values, keys sorted."""
        return canonical_yaml(self.as_document(), header=VALUES_HEADER)


@dataclass(frozen=True, slots=True)
class HelmValuesRenderer:
    """Renders a ``synchronous-llm`` context into the ``inferops-llm`` chart's values.

    ``revision`` is the full commit the renderer runs from. A release records it; the
    values do not depend on it.
    """

    revision: GitRevision

    def __post_init__(self) -> None:
        if not isinstance(self.revision, GitRevision):
            raise TypeError("a renderer revision must be a GitRevision")

    @property
    def support(self) -> RendererSupport:
        return HELM_VALUES_SUPPORT

    def render(
        self,
        context: RenderContext,
        *,
        request: RequestContext = NO_REQUEST_CONTEXT,
    ) -> GeneratedHelmValues:
        """The chart values for ``context``: the same values for an equal context.

        Raises:
            RenderRefused: the context is outside the renderer's support, or asks
                for a value or a capability the chart cannot carry; every finding
                at once, none quoting a value.
            TypeError: ``context`` is not a :class:`~.normalization.RenderContext`.
        """
        if not isinstance(context, RenderContext):
            raise TypeError(
                "context must be a RenderContext produced by build_render_context "
                "or prepare_render, not a raw document"
            )
        unsupported = _support_findings(context, request)
        if unsupported:
            raise RenderRefused(unsupported)
        leaves = tuple(_leaves(context))
        findings = _capability_findings(context, request)
        findings.extend(_value_findings(leaves, request))
        if findings:
            raise RenderRefused(findings)
        return GeneratedHelmValues(_frozen(_nested(leaves)))


def _manual_leaves(
    document: Mapping[Any, Any], prefix: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], bool]]:
    """Every value a values file sets, with whether it is an empty mapping.

    An empty mapping merges nothing into what it lands on; anything else - a scalar,
    a list, or a null, which Helm reads as a removal - replaces it.
    """
    for key, value in document.items():
        path = (*prefix, str(key))
        if isinstance(value, Mapping) and value:
            yield from _manual_leaves(value, path)
        else:
            yield path, isinstance(value, Mapping)


def _overrides(path: tuple[str, ...], empty_mapping: bool) -> bool:
    """Whether a hand-written value at ``path`` sets, replaces, or removes a generated one."""
    for generated in GENERATED_VALUE_PATHS:
        if path[: len(generated)] == generated:
            # At a generated value, or beneath one, which replaces it with a mapping.
            return True
        if generated[: len(path)] == path and not empty_mapping:
            # Above a generated value: a scalar, a list, or a null replaces the lot.
            return True
    return False


def manual_value_findings(
    manual_values: Mapping[str, Any],
    *,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> list[RenderFinding]:
    """Every value a hand-written values file sets that the renderer generates.

    Helm merges values files in order, and whichever comes last wins, so a
    hand-written file installed beside the generated one could replace a value the
    contract owns - or remove it with a null - and nothing would say so. This finds
    each such value, wherever the file would be placed, and names it by its path.

    Raises:
        TypeError: ``manual_values`` is not a mapping.
    """
    if not isinstance(manual_values, Mapping):
        raise TypeError("manual values must be a mapping, as a values file is")
    return [
        RenderFinding(
            "render-manual-value-generated",
            "manualValues." + ".".join(path),
            "the renderer generates this value from the contract, the binding, or "
            "the platform defaults; a hand-written values file may not set, "
            "replace, or remove it",
            context,
        )
        for path, empty_mapping in sorted(_manual_leaves(manual_values))
        if _overrides(path, empty_mapping)
    ]


__all__ = [
    "CHART_NAME",
    "CHART_PROFILE",
    "CHART_RUNTIME_PROFILE",
    "CHART_RUNTIME_REQUESTS",
    "CHART_VALUE_CONSTRAINTS",
    "CHART_VERSION",
    "GENERATED_VALUE_PATHS",
    "HELM_VALUES_SUPPORT",
    "HELM_VALUE_DISPOSITIONS",
    "PLATFORM_TELEMETRY",
    "VALUES_HEADER",
    "ChartValueConstraint",
    "Disposition",
    "GeneratedHelmValues",
    "HelmValuesRenderer",
    "ValueDisposition",
    "manual_value_findings",
]
