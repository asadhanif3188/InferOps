"""The normalized render context, and the one function that builds it.

:func:`build_render_context` is the render boundary. It takes a contract that
passed :func:`~.acceptance.validate_for_render`, one set of
:class:`~.defaults.PlatformDefaults`, and the parsed EnvironmentBindings supplied
together, selects the binding that serves the contract with the binding domain's
own rules, and returns a :class:`RenderContext`: every value a renderer may read,
each with the one layer that owns it and where it was read from, and the identity
and digest of every input.

**Read from the ownership table, and from nothing else.** Each value is read from
the JSON form of its owner at the path :data:`~.ownership.RENDER_FIELD_OWNERSHIP`
names. A value absent from its owner is absent from the context - an optional
member, or the block of the other profile - and nothing fills it in. No value is
merged, overridden, or defaulted, because no layer is consulted for a value it
does not own.

**Deterministic.** The same inputs give an equal context with the same canonical
form and digest, whatever order the bindings were supplied in, in another process,
under another hash seed. Building one reads no clock, no random source, no file,
no environment variable, and no network, runs nothing, and writes nothing: no Git,
no ``kubectl``, no Helm. The context's canonical form is the release domain's
canonical JSON, so it refuses a value with no single JSON spelling instead of
writing one.

**Refused before anything is returned.** A missing, ambiguous, or conflicting
binding, and an input that supplies a value it does not own, are refused with a
:class:`~.errors.RenderRefused` carrying every finding: the binding domain's
refusals under their own rule identifiers, and the ownership refusals of
:mod:`.conflicts`. Nothing is half-built: a context is either returned whole or not
at all.

**One path refuses everything at once.** :func:`prepare_render` takes a parsed
contract rather than a validated one, and a renderer's
:class:`~.support.RendererSupport`, and gathers every finding of every step - the
renderer's support, the contract's rules, the selection, the ownership check - into
one :class:`~.errors.RenderRefused`, so a caller fixes everything in one pass rather
than one refusal per run. :func:`build_render_context` remains the step that takes
an already validated contract and knows no renderer.

**The guard is against accidents, not intent**, as for the validated contract: a
:class:`RenderContext` is refused without this module's private sentinel.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import InitVar, dataclass, field
from types import MappingProxyType
from typing import Any, Final

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..environment.binding import EnvironmentBinding
from ..environment.errors import BindingSelectionError
from ..environment.selection import select_environment_binding
from ..release.canonical import binding_digest, canonical_sha256, contract_digest
from ..release.release import (
    ContractReference,
    EnvironmentBindingReference,
    PlatformDefaultsReference,
    ReleaseSource,
    RendererReference,
)
from ..release.values import Sha256Hex
from ..workload.contract import WorkloadContract
from ..workload.values import DnsLabel
from .acceptance import ValidatedWorkloadContract, validate_for_render
from .conflicts import ownership_findings
from .defaults import PlatformDefaults
from .errors import (
    RenderFinding,
    RenderRefused,
    WorkloadNotAcceptedError,
    from_binding_refusal,
    from_workload_finding,
)
from .ownership import RENDER_FIELD_OWNERSHIP, FieldOwnership, Layer
from .support import (
    RendererSupport,
    unsupported_binding_findings,
    unsupported_contract_findings,
)

#: Held only by this module. A context constructed without it is refused.
_ISSUED: Final = object()

_ABSENT: Final = object()

#: The JSON form of a value or a document.
Document = dict[str, Any]


def _frozen(value: Any) -> Any:
    """A JSON value with every list a tuple and every object read-only."""
    if isinstance(value, dict):
        return MappingProxyType({key: _frozen(member) for key, member in value.items()})
    if isinstance(value, list):
        return tuple(_frozen(member) for member in value)
    return value


def _thawed(value: Any) -> Any:
    """The JSON value :func:`_frozen` was given, as plain lists and dicts."""
    if isinstance(value, Mapping):
        return {key: _thawed(member) for key, member in value.items()}
    if isinstance(value, tuple):
        return [_thawed(member) for member in value]
    return value


def _lookup(document: Mapping[str, Any], path: str) -> Any:
    node: Any = document
    for step in path.split("."):
        if not isinstance(node, Mapping) or step not in node:
            return _ABSENT
        node = node[step]
    return node


@dataclass(frozen=True, slots=True)
class RenderField:
    """One value of the render context, with its owner and where it came from.

    ``value`` is the JSON form the owner holds, read-only: a string, an integer, a
    boolean, a tuple, or a read-only mapping. It takes no part in the hash, for the
    reason the WorkloadContract's annotations do not: a read-only mapping cannot be
    hashed, and equality still compares it.
    """

    name: str
    layer: Layer
    source: str
    value: Any = field(hash=False)

    def as_document(self) -> Document:
        return {
            "layer": self.layer.value,
            "source": self.source,
            "value": _thawed(self.value),
        }


@dataclass(frozen=True, slots=True)
class RenderSources:
    """The identity of every input, in the form a release records it.

    The renderer is not here: it is the consumer of the context, not an input to
    it, and :meth:`release_source` takes it.
    """

    contract: ContractReference
    environment_binding: EnvironmentBindingReference
    platform_defaults: PlatformDefaultsReference

    def release_source(self, renderer: RendererReference) -> ReleaseSource:
        """The ``source`` block of a release a renderer at ``renderer`` would record."""
        if not isinstance(renderer, RendererReference):
            raise TypeError("renderer must be a RendererReference")
        return ReleaseSource(
            contract=self.contract,
            environment_binding=self.environment_binding,
            renderer=renderer,
            platform_defaults=self.platform_defaults,
        )

    def as_document(self) -> Document:
        return {
            "contract": self.contract.as_document(),
            "environmentBinding": self.environment_binding.as_document(),
            "platformDefaults": self.platform_defaults.as_document(),
        }


@dataclass(frozen=True, slots=True)
class RenderContext:
    """Every value a renderer may read, each with its one owner, and the inputs.

    Constructed only by :func:`build_render_context`. ``fields`` is sorted by name.
    """

    fields: tuple[RenderField, ...]
    sources: RenderSources
    issued: InitVar[object] = None

    def __post_init__(self, issued: object) -> None:
        if issued is not _ISSUED:
            raise TypeError(
                "a RenderContext is produced by build_render_context, never "
                "constructed directly"
            )

    def names(self) -> tuple[str, ...]:
        """Every value's name, sorted."""
        return tuple(entry.name for entry in self.fields)

    def entry(self, name: str) -> RenderField:
        """One value, with its owner and source.

        Raises:
            KeyError: the context holds no value of that name - either no such
                value exists, or its owner left it out.
        """
        for entry in self.fields:
            if entry.name == name:
                return entry
        raise KeyError(name)

    def value(self, name: str) -> Any:
        """One value, read-only. Raises :class:`KeyError` as :meth:`entry` does."""
        return self.entry(name).value

    def owned_by(self, layer: Layer) -> tuple[RenderField, ...]:
        """Every value one layer supplied, sorted by name."""
        return tuple(entry for entry in self.fields if entry.layer is layer)

    def as_document(self) -> Document:
        """The JSON form: every value with its owner and source, and the inputs."""
        return {
            "fields": {entry.name: entry.as_document() for entry in self.fields},
            "sources": self.sources.as_document(),
        }

    def digest(self) -> Sha256Hex:
        """The SHA-256 of the canonical form, as the release domain defines it."""
        return canonical_sha256(self.as_document())


def _read(row: FieldOwnership, owners: Mapping[Layer, Document]) -> RenderField | None:
    value = _lookup(owners[row.layer], row.source)
    if value is _ABSENT:
        if row.required:
            # A validated contract, a parsed binding, and a constructed defaults set
            # always carry a required member, so reaching this is a defect in the
            # ownership table, not a refusal of a document.
            raise AssertionError(
                f"the required render value {row.name!r} is missing from its owner"
            )
        return None
    return RenderField(row.name, row.layer, row.source, _frozen(value))


def _binding_index(
    bindings: Sequence[EnvironmentBinding], binding: EnvironmentBinding
) -> int:
    """The position of the selected binding, which selection returns unchanged."""
    return next(index for index, entry in enumerate(bindings) if entry is binding)


def _owners(
    workload: WorkloadContract,
    platform_defaults: PlatformDefaults,
    binding: EnvironmentBinding,
) -> dict[Layer, Document]:
    return {
        Layer.WORKLOAD_INTENT: workload.as_document(),
        Layer.PLATFORM_DEFAULTS: platform_defaults.as_document(),
        Layer.ENVIRONMENT_BINDING: binding.as_document(),
    }


def _roles(index: int) -> dict[Layer, str]:
    return {
        Layer.WORKLOAD_INTENT: "contract",
        Layer.PLATFORM_DEFAULTS: "platformDefaults",
        Layer.ENVIRONMENT_BINDING: f"bindings[{index}]",
    }


def _select(
    workload: WorkloadContract,
    bindings: Sequence[EnvironmentBinding],
    binding_name: DnsLabel | None,
    context: RequestContext,
) -> tuple[EnvironmentBinding | None, list[RenderFinding]]:
    try:
        binding = select_environment_binding(
            workload, bindings, binding_name=binding_name, context=context
        )
    except BindingSelectionError as error:
        return None, [from_binding_refusal(refusal) for refusal in error.refusals]
    return binding, []


def _assemble(
    workload: WorkloadContract,
    platform_defaults: PlatformDefaults,
    binding: EnvironmentBinding,
    owners: Mapping[Layer, Document],
) -> RenderContext:
    fields = [
        entry
        for row in RENDER_FIELD_OWNERSHIP
        if (entry := _read(row, owners)) is not None
    ]
    sources = RenderSources(
        contract=ContractReference(
            api_version=workload.api_version, sha256=contract_digest(workload)
        ),
        environment_binding=EnvironmentBindingReference(
            api_version=binding.api_version,
            environment=binding.spec.environment,
            name=binding.metadata.name,
            sha256=binding_digest(binding),
        ),
        platform_defaults=PlatformDefaultsReference(
            revision=platform_defaults.revision
        ),
    )
    return RenderContext(
        tuple(sorted(fields, key=lambda entry: entry.name)), sources, _ISSUED
    )


def _require_defaults(platform_defaults: object) -> None:
    if not isinstance(platform_defaults, PlatformDefaults):
        raise TypeError(
            "platform_defaults must be PlatformDefaults, not a raw document"
        )


def build_render_context(
    contract: ValidatedWorkloadContract,
    platform_defaults: PlatformDefaults,
    bindings: Sequence[EnvironmentBinding],
    *,
    binding_name: DnsLabel | None = None,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> RenderContext:
    """The normalized render context for one contract, or the reason there is none.

    Args:
        contract: a contract :func:`~.acceptance.validate_for_render` accepted.
        platform_defaults: the platform defaults to render with.
        bindings: parsed bindings supplied together. The binding domain's set
            rules and selection choose the one that serves ``contract``.
        binding_name: the binding to use when more than one serves the contract's
            environment, exactly as for selection.
        context: request-scoped identifiers, attached to every refusal.

    Raises:
        RenderRefused: no binding could be selected, or an input supplies a value
            it does not own; every finding at once.
        TypeError: an argument is not the validated or parsed object this reads -
            a raw document, or a WorkloadContract that has not been validated.
    """
    if not isinstance(contract, ValidatedWorkloadContract):
        raise TypeError(
            "contract must be a ValidatedWorkloadContract produced by "
            "validate_for_render; a parsed or raw contract cannot be rendered"
        )
    _require_defaults(platform_defaults)

    workload = contract.contract
    binding, findings = _select(workload, bindings, binding_name, context)
    if binding is None:
        raise RenderRefused(findings)
    owners = _owners(workload, platform_defaults, binding)
    conflicts = ownership_findings(
        owners, _roles(_binding_index(bindings, binding)), context
    )
    if conflicts:
        raise RenderRefused(conflicts)
    return _assemble(workload, platform_defaults, binding, owners)


def prepare_render(
    contract: WorkloadContract,
    platform_defaults: PlatformDefaults,
    bindings: Sequence[EnvironmentBinding],
    *,
    support: RendererSupport,
    binding_name: DnsLabel | None = None,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> RenderContext:
    """The render context for a renderer of ``support``, or every reason there is none.

    The canonical path: it validates the parsed contract itself, and gathers every
    finding of every step into one refusal - the renderer's support for the
    contract's version and profile, the defaults' version, and the selected
    binding's version; the contract's semantic rules and profile conditions; the
    selection; and the ownership check. A step that needs the selected binding
    runs only once there is one.

    Raises:
        RenderRefused: every finding, sorted by category, field, and rule.
        TypeError: an argument is a raw document, or ``support`` is not a
            :class:`~.support.RendererSupport`.
        ValueError: a ``synchronous-llm`` contract was given and no compatibility
            matrix was supplied to the workload package's loader.
    """
    if not isinstance(contract, WorkloadContract):
        raise TypeError(
            "contract must be a WorkloadContract produced by parse_workload_contract, "
            "not a raw document"
        )
    _require_defaults(platform_defaults)
    if not isinstance(support, RendererSupport):
        raise TypeError("support must be a RendererSupport")

    findings = unsupported_contract_findings(
        support, contract, platform_defaults, context
    )
    validated: ValidatedWorkloadContract | None = None
    try:
        validated = validate_for_render(contract, context=context)
    except WorkloadNotAcceptedError as error:
        findings.extend(from_workload_finding(finding) for finding in error.findings)

    binding, refusals = _select(contract, bindings, binding_name, context)
    findings.extend(refusals)
    owners: dict[Layer, Document] = {}
    if binding is not None:
        index = _binding_index(bindings, binding)
        findings.extend(unsupported_binding_findings(support, binding, index, context))
        owners = _owners(contract, platform_defaults, binding)
        findings.extend(ownership_findings(owners, _roles(index), context))

    if findings:
        raise RenderRefused(findings)
    if validated is None or binding is None:
        # No finding means validation and selection both returned. Reaching this
        # is a defect in this function, not a refusal of an input.
        raise AssertionError("a render with no finding has no contract or binding")
    return _assemble(validated.contract, platform_defaults, binding, owners)


__all__ = [
    "RenderContext",
    "RenderField",
    "RenderSources",
    "build_render_context",
    "prepare_render",
]
