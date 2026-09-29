"""The rules that need more than one document: bindings together, and a contract.

A single binding is refused by its parser. What a parser cannot see is whether a
binding that is well formed on its own can be used: whether it conflicts with the
other bindings it is supplied beside, and whether exactly one of them serves the
WorkloadContract a release is for. This module applies those rules, and it is the
only place they are applied.

**Two set rules.** Across every binding supplied together:

- ``binding-identity-duplicated`` - two bindings declare the same environment and
  name. Which one a selection by name returns would be decided by list order.
- ``binding-destination-overlaps`` - two bindings declare the same GitOps
  destination, or one inside the other. Generated desired state for one would
  overwrite, or sit inside, the other's, whatever their environments.

**The selection rule.** A WorkloadContract's ``spec.environment`` selects a
binding. When exactly one binding serves that environment, it is the one. When
more than one does, the caller must name one, because the contract has no field
to name it with and this package will not choose: "the first", "the last", and
"the one that happens to match" are each a silent precedence rule, which is what
the binding exists to rule out. A named binding must serve the contract's
environment; a name that exists only under another environment is refused rather
than followed. A second binding added to an environment later turns a selection
that used to succeed without a name into a refusal, which is the intended effect:
the choice is surfaced, not made.

**Selection merges nothing.** It returns one of the bindings it was given, as the
same object, and reads exactly one member of the contract: ``spec.environment``.
The contract's own fields - scaling, resources, model, and the rest - are neither
read nor copied, and the binding has no attribute that could hold one. Combining a
contract with a binding into release input is the renderer's, and no renderer
exists.

Everything here is offline and deterministic: no file system, network, cluster,
clock, or randomness. Refusals are returned sorted, so the same input produces the
same refusals in the same order.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..workload.contract import WorkloadContract
from ..workload.values import DnsLabel
from .binding import EnvironmentBinding
from .errors import BindingRefusal, BindingSelectionError

_DIGIT_RUN = re.compile(r"(\d+)")


def _sort_key(refusal: BindingRefusal) -> tuple[object, ...]:
    """Order refusals by field, reading list indices as numbers rather than text."""
    parts = tuple(
        int(part) if part.isdigit() else part
        for part in _DIGIT_RUN.split(refusal.field)
    )
    return (parts, refusal.rule_id, refusal.reason)


def _require_bindings(bindings: object) -> None:
    """Refuse a raw document where a parsed binding belongs.

    This is a programming error rather than a refusal of a document, and it is
    raised as one: a mapping that was never parsed has had none of its fields
    checked, and a rule applied to it would be applied to an unknown shape.
    """
    if isinstance(bindings, (str, bytes)) or not isinstance(bindings, Sequence):
        raise TypeError("bindings must be a sequence of parsed EnvironmentBinding")
    for binding in bindings:
        if not isinstance(binding, EnvironmentBinding):
            raise TypeError(
                "every binding must be an EnvironmentBinding produced by "
                "parse_environment_binding, not a raw document"
            )


def _overlaps(first: tuple[str, ...], second: tuple[str, ...]) -> bool:
    """Whether one directory is the other, or contains it, segment by segment."""
    shorter = min(len(first), len(second))
    return first[:shorter] == second[:shorter]


def validate_environment_bindings(
    bindings: Sequence[EnvironmentBinding],
    *,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> list[BindingRefusal]:
    """Apply the set rules to bindings supplied together. Returns every refusal.

    A refusal names the later binding of a conflicting pair, by its position in
    ``bindings``, and says which earlier position it conflicts with. The value both
    share is not repeated.
    """
    _require_bindings(bindings)
    refusals: list[BindingRefusal] = []

    first_with_identity: dict[object, int] = {}
    for index, binding in enumerate(bindings):
        identity = binding.identity
        if identity in first_with_identity:
            refusals.append(
                BindingRefusal(
                    f"bindings[{index}].metadata.name",
                    "binding-identity-duplicated",
                    "this binding declares the same environment and name as the "
                    f"binding at position {first_with_identity[identity]}, so a "
                    "selection by name could not tell the two apart",
                    context=context,
                )
            )
        else:
            first_with_identity[identity] = index

    for later, binding in enumerate(bindings):
        segments = binding.spec.gitops.destination_path.segments
        for earlier in range(later):
            other = bindings[earlier].spec.gitops.destination_path.segments
            if _overlaps(segments, other):
                refusals.append(
                    BindingRefusal(
                        f"bindings[{later}].spec.gitops.destinationPath",
                        "binding-destination-overlaps",
                        "this binding's GitOps destination is the destination of "
                        f"the binding at position {earlier}, or one of the two "
                        "contains the other, so desired state generated for one "
                        "would be written over or inside the other's",
                        context=context,
                    )
                )
    return sorted(refusals, key=_sort_key)


def _selection_refusals(
    contract: WorkloadContract,
    bindings: Sequence[EnvironmentBinding],
    binding_name: DnsLabel | None,
    context: RequestContext,
) -> tuple[EnvironmentBinding | None, list[BindingRefusal]]:
    environment = contract.spec.environment

    if binding_name is None:
        serving = [b for b in bindings if b.spec.environment is environment]
        if len(serving) == 1:
            return serving[0], []
        if not serving:
            return None, [
                BindingRefusal(
                    "contract.spec.environment",
                    "binding-not-found",
                    "no binding supplied serves this contract's environment, and a "
                    "release has no environment facts to take without one",
                    context=context,
                )
            ]
        return None, [
            BindingRefusal(
                "contract.spec.environment",
                "binding-selection-ambiguous",
                f"{len(serving)} bindings supplied serve this contract's "
                "environment and none was named; name the binding to use, "
                "because none is chosen by order or by default",
                context=context,
            )
        ]

    named = [
        (index, binding)
        for index, binding in enumerate(bindings)
        if binding.metadata.name == binding_name
    ]
    for _, binding in named:
        if binding.spec.environment is environment:
            return binding, []
    if not named:
        return None, [
            BindingRefusal(
                "selection.bindingName",
                "binding-not-found",
                "no binding supplied has the name asked for",
                context=context,
            )
        ]
    return None, [
        BindingRefusal(
            f"bindings[{index}].spec.environment",
            "binding-environment-mismatch",
            "the binding with the name asked for serves a different environment "
            "from this contract's, and a binding is never applied across "
            "environments",
            context=context,
        )
        for index, _ in named
    ]


def select_environment_binding(
    contract: WorkloadContract,
    bindings: Sequence[EnvironmentBinding],
    *,
    binding_name: DnsLabel | None = None,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> EnvironmentBinding:
    """The one binding that serves ``contract``, or every reason there is none.

    Args:
        contract: a parsed WorkloadContract. Only ``spec.environment`` is read.
        bindings: parsed bindings supplied together. The set rules are applied to
            all of them first, and a set that conflicts is not selected from.
        binding_name: the binding to use, when more than one serves the contract's
            environment. Optional when exactly one does.
        context: request-scoped identifiers, attached to every refusal.

    Returns:
        One of ``bindings``, unchanged and not copied.

    Raises:
        BindingSelectionError: carrying every refusal, sorted.
        TypeError: an argument is not the parsed object this function reads.
    """
    if not isinstance(contract, WorkloadContract):
        raise TypeError("contract must be a WorkloadContract, not a raw document")
    if binding_name is not None and not isinstance(binding_name, DnsLabel):
        raise TypeError("binding_name must be a DnsLabel or None")

    conflicts = validate_environment_bindings(bindings, context=context)
    if conflicts:
        raise BindingSelectionError(tuple(conflicts))

    selected, refusals = _selection_refusals(contract, bindings, binding_name, context)
    if selected is None:
        raise BindingSelectionError(tuple(sorted(refusals, key=_sort_key)))
    return selected


__all__ = ["select_environment_binding", "validate_environment_bindings"]
