"""Refusing an input that supplies a value it does not own.

The ownership table gives every render value one owner, and normalization reads
each value from its owner alone. That makes "last value wins" impossible *inside*
the context, but on its own it would let a value somewhere else pass in silence:
an input carrying a value it does not own would simply not be read, and its author
would believe it had taken effect. This module refuses that instead.

**What is checked.** Every leaf of each input's JSON form - the contract, the
platform defaults, and the selected binding - must be a value the table assigns to
that input, or a field the table leaves out of it with a reason. A leaf that is
neither is refused, and the refusal names the layer that owns it where one does:

- ``render-ownership-conflict`` - the leaf is a value another layer owns: its path
  is that layer's source path for it, or the value's own name. A binding carrying
  ``spec.scaling.minimumReplicas`` claims the workload's replica range; defaults
  carrying ``api.replicas`` claim the binding's API replica count. Neither value
  is chosen: the render is refused.
- ``render-value-unowned`` - the leaf is a value no layer owns, or an input's own
  value at a path the table does not read it from. Rendering without it would
  drop a value somebody wrote.

A leaf is any value that is not an object, an empty object, or an object the table
names as a whole - the contract's annotations, which are left out as the contract's
non-normative extension point.

**What reaches it today.** Nothing a parser produces: each parser refuses a field
its schema does not define, so a binding that writes a contract field is refused
as ``field-unknown`` before it is a binding at all, and a test walks every
committed valid input and finds no leaf this module refuses. It is what keeps the
rule when an input's document gains a field nobody assigned an owner - a new
version, a new defaults setting, a subclass - and the tests reach it with inputs
whose documents carry one more value.

**The path is the input's meaning.** A path an input's own table rows or
exclusions name means what that input says it means, even where another input uses
the same path for something else: a binding's ``metadata.name`` is the binding's
name, never the workload's, and its ``spec.environment`` is the selection key,
which selection has already required to equal the contract's.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import Any, Final

from ..context import NO_REQUEST_CONTEXT, RequestContext
from .errors import RenderFinding
from .ownership import (
    EXCLUDED_SOURCE_FIELDS,
    RENDER_FIELD_OWNERSHIP,
    FieldOwnership,
    Layer,
)


def _known_paths(layer: Layer) -> frozenset[str]:
    """Every path a layer's own document may hold a value at."""
    return frozenset(
        {row.source for row in RENDER_FIELD_OWNERSHIP if row.layer is layer}
        | set(EXCLUDED_SOURCE_FIELDS[layer])
    )


_KNOWN: Final[Mapping[Layer, frozenset[str]]] = MappingProxyType(
    {layer: _known_paths(layer) for layer in Layer}
)


def _claimable() -> Mapping[str, FieldOwnership]:
    """Each path that names a render value: the value's name and its source path.

    A name and a source are both ways of saying which value is meant. No path may
    name two values, and a test holds that.
    """
    found: dict[str, FieldOwnership] = {}
    for row in RENDER_FIELD_OWNERSHIP:
        for path in (row.name, row.source):
            if found.get(path, row) is not row:
                raise AssertionError(f"the path {path!r} names two render values")
            found[path] = row
    return MappingProxyType(found)


_CLAIMABLE: Final = _claimable()


def _leaves(document: Mapping[str, Any], known: frozenset[str]) -> Iterator[str]:
    """Every leaf path of a document, stopping at a path the layer itself names."""
    pending: list[tuple[str, Any]] = [
        (str(key), value) for key, value in document.items()
    ]
    while pending:
        path, value = pending.pop()
        if path in known or not isinstance(value, Mapping) or not value:
            yield path
            continue
        pending.extend((f"{path}.{key}", member) for key, member in value.items())


def ownership_findings(
    owners: Mapping[Layer, Mapping[str, Any]],
    roles: Mapping[Layer, str],
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> list[RenderFinding]:
    """Every value an input supplies without owning it. Empty when there is none.

    Args:
        owners: each layer's JSON form, as normalization reads it.
        roles: how a refusal names each input - ``contract``, ``platformDefaults``,
            ``bindings[i]``.
        context: request-scoped identifiers, attached to every finding.
    """
    findings: list[RenderFinding] = []
    for layer in Layer:
        known = _KNOWN[layer]
        for path in _leaves(owners[layer], known):
            if path in known:
                continue
            field = f"{roles[layer]}.{path}"
            claimed = _CLAIMABLE.get(path)
            if claimed is not None and claimed.layer is not layer:
                findings.append(
                    RenderFinding(
                        "render-ownership-conflict",
                        field,
                        f"the {layer.value} input supplies '{claimed.name}', which "
                        f"{claimed.layer.value} owns; no layer overrides another, so "
                        "neither value is chosen",
                        context,
                    )
                )
            else:
                findings.append(
                    RenderFinding(
                        "render-value-unowned",
                        field,
                        f"the {layer.value} input supplies a value the ownership "
                        "table does not assign to it here, and a value with no "
                        "owner is refused rather than dropped",
                        context,
                    )
                )
    return findings


__all__ = ["ownership_findings"]
