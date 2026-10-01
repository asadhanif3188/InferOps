"""What the render boundary refuses with, under one canonical vocabulary.

Two refusals are the boundary's own.

:class:`WorkloadNotAcceptedError` is raised by
:func:`~.acceptance.validate_for_render` when a parsed WorkloadContract fails a rule
the published contract applies. It carries every finding at once, each a
:class:`~inferops.domain.workload.errors.WorkloadValidationError` with the published
rule identifier it was refused under, in the contract's own vocabulary.

:class:`RenderRefused` is what a render is refused with: every reason, from every
input, at once, each a :class:`RenderFinding` carrying three things kept apart on
purpose, as the contract's canonical error model keeps them apart:

- **a category** - which of the kinds of refusal an operator has to tell apart this
  is: a shape the schema refuses, a semantic rule, an unsupported version or
  profile, a value or a capability the renderer's chart cannot carry, an
  incompatible model and runtime, a missing binding, or two layers claiming one
  value. :class:`RefusalCategory` is the whole list;
- **a canonical code** - the coarse public vocabulary a client switches on, never
  grown by a rule: ``contract-invalid``, ``version-unsupported``, and, for a profile
  no renderer was built for or a value its chart cannot carry,
  ``capability-unavailable``;
- **a rule identifier** - which rule refused it, looked up in :data:`RENDER_RULES`.

**The vocabulary reuses before it adds.** A refusal that another domain already
publishes keeps that domain's rule identifier and code: the semantic pipeline's
seven rules, the three structural rules the profile conditions are refused under,
and the binding domain's five set and selection rules. :data:`RENDER_RULES` gives
each a category and records which vocabulary published it. Ten rules are this
package's own, for what no other domain can see: six the boundary applies - a
renderer that does not support an input's version or profile, and an input that
supplies a value it does not own - and four the Helm values renderer applies - a
value or a capability its chart cannot carry, a value it would write that is shaped
like a credential, and a hand-written values file that sets a value it generates.

**Every render refusal is final.** A document that is invalid, a binding that is
missing, a version a renderer does not take, and a value claimed twice are each
still so on retry.

**A message never carries a value read out of a document**, for the reason every
other domain package gives: the field most likely to be refused for looking wrong
is the field most likely to hold a secret.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..environment.errors import BINDING_RULES, BindingRefusal
from ..workload.errors import DomainError, WorkloadValidationError

_DIGIT_RUN = re.compile(r"([0-9]+)")

#: The canonical codes a render refusal can carry. The first two are the ones the
#: offline contract validator publishes; the third is the canonical code for a
#: capability that was never built, which a renderer that does not take a profile
#: is, and so is a chart with no setting for a value. A test holds all three inside
#: the canonical vocabulary the API serves.
CONTRACT_INVALID: Final = "contract-invalid"
VERSION_UNSUPPORTED: Final = "version-unsupported"
CAPABILITY_UNAVAILABLE: Final = "capability-unavailable"


class RefusalCategory(StrEnum):
    """Which kind of refusal a finding is, in the order a reader should fix them.

    A renderer that cannot take an input at all comes first, then a value or a
    capability its chart cannot carry, then what is wrong with the contract, then
    what is wrong with the environment, then what is wrong between the inputs.
    """

    VERSION_UNSUPPORTED = "version-unsupported"
    PROFILE_UNSUPPORTED = "profile-unsupported"
    VALUE_UNSUPPORTED = "value-unsupported"
    SHAPE_INVALID = "shape-invalid"
    SEMANTIC_INVALID = "semantic-invalid"
    MODEL_RUNTIME_INCOMPATIBLE = "model-runtime-incompatible"
    BINDING_MISSING = "binding-missing"
    OWNERSHIP_CONFLICT = "ownership-conflict"


_CATEGORY_ORDER: Final = MappingProxyType(
    {category: index for index, category in enumerate(RefusalCategory)}
)


class RuleOrigin(StrEnum):
    """The vocabulary that publishes a rule identifier."""

    WORKLOAD_CONTRACT = "workload-contract"
    ENVIRONMENT_BINDING = "environment-binding"
    RENDER = "render"


@dataclass(frozen=True, slots=True)
class RenderRule:
    """One rule a render can be refused under, with its category and code."""

    identifier: str
    category: RefusalCategory
    code: str
    origin: RuleOrigin
    summary: str


def _rule(
    identifier: str,
    category: RefusalCategory,
    origin: RuleOrigin,
    summary: str,
    code: str = CONTRACT_INVALID,
) -> RenderRule:
    return RenderRule(identifier, category, code, origin, summary)


_W = RuleOrigin.WORKLOAD_CONTRACT
_B = RuleOrigin.ENVIRONMENT_BINDING
_R = RuleOrigin.RENDER

#: Every rule a render can be refused under, keyed by identifier, in the order the
#: published refusal matrix lists them. A test fails if the matrix and this
#: disagree, if a reused identifier is not the publishing vocabulary's own with its
#: own code, or if a rule of this package's reuses another vocabulary's identifier.
RENDER_RULES: Final[Mapping[str, RenderRule]] = MappingProxyType(
    {
        rule.identifier: rule
        for rule in (
            _rule(
                "render-contract-version-unsupported",
                RefusalCategory.VERSION_UNSUPPORTED,
                _R,
                "the renderer does not take the contract's version",
                VERSION_UNSUPPORTED,
            ),
            _rule(
                "render-binding-version-unsupported",
                RefusalCategory.VERSION_UNSUPPORTED,
                _R,
                "the renderer does not take the selected binding's version",
                VERSION_UNSUPPORTED,
            ),
            _rule(
                "render-defaults-version-unsupported",
                RefusalCategory.VERSION_UNSUPPORTED,
                _R,
                "the renderer does not take the platform defaults' version",
                VERSION_UNSUPPORTED,
            ),
            _rule(
                "render-profile-unsupported",
                RefusalCategory.PROFILE_UNSUPPORTED,
                _R,
                "the renderer was not built for the contract's profile",
                CAPABILITY_UNAVAILABLE,
            ),
            _rule(
                "render-value-unsupported",
                RefusalCategory.VALUE_UNSUPPORTED,
                _R,
                "an accepted value has no form the renderer's chart accepts",
                CAPABILITY_UNAVAILABLE,
            ),
            _rule(
                "render-capability-unsupported",
                RefusalCategory.VALUE_UNSUPPORTED,
                _R,
                "the contract asks for something the renderer's chart does not provide",
                CAPABILITY_UNAVAILABLE,
            ),
            _rule(
                "field-required",
                RefusalCategory.SHAPE_INVALID,
                _W,
                "a profile's own block is absent",
            ),
            _rule(
                "value-not-permitted",
                RefusalCategory.SHAPE_INVALID,
                _W,
                "a value the schema forbids for the contract's profile",
            ),
            _rule(
                "value-out-of-range",
                RefusalCategory.SHAPE_INVALID,
                _W,
                "a mock citing proof references",
            ),
            _rule(
                "replica-range-inverted",
                RefusalCategory.SEMANTIC_INVALID,
                _W,
                "the minimum replica count exceeds the maximum",
            ),
            _rule(
                "secret-value-in-locator",
                RefusalCategory.SEMANTIC_INVALID,
                _W,
                "a secret reference shaped like a pasted credential",
            ),
            _rule(
                "secret-ref-name-duplicated",
                RefusalCategory.SEMANTIC_INVALID,
                _W,
                "two secret entries declare the same logical name",
            ),
            _rule(
                "mock-secret-ref-declared",
                RefusalCategory.SEMANTIC_INVALID,
                _W,
                "a mock-llm workload declares a secret reference",
            ),
            _rule(
                "binding-identity-duplicated",
                RefusalCategory.SEMANTIC_INVALID,
                _B,
                "two bindings supplied together declare the same environment and name",
            ),
            _rule(
                "binding-destination-overlaps",
                RefusalCategory.SEMANTIC_INVALID,
                _B,
                "two bindings supplied together share a GitOps destination",
            ),
            _rule(
                "render-value-credential-shaped",
                RefusalCategory.SEMANTIC_INVALID,
                _R,
                "a value the renderer would write has a part shaped like a published "
                "credential",
            ),
            _rule(
                "runtime-unregistered",
                RefusalCategory.MODEL_RUNTIME_INCOMPATIBLE,
                _W,
                "the runtime image has no entry in the compatibility matrix",
            ),
            _rule(
                "model-artifact-format-unknown",
                RefusalCategory.MODEL_RUNTIME_INCOMPATIBLE,
                _W,
                "the model artifact is in no format the matrix recognises",
            ),
            _rule(
                "runtime-model-incompatible",
                RefusalCategory.MODEL_RUNTIME_INCOMPATIBLE,
                _W,
                "the pinned runtime does not accept the pinned artifact's format",
            ),
            _rule(
                "binding-not-found",
                RefusalCategory.BINDING_MISSING,
                _B,
                "no binding serves the contract's environment, or none has the "
                "name asked for",
            ),
            _rule(
                "binding-selection-ambiguous",
                RefusalCategory.BINDING_MISSING,
                _B,
                "several bindings serve the contract's environment and none was named",
            ),
            _rule(
                "binding-environment-mismatch",
                RefusalCategory.BINDING_MISSING,
                _B,
                "the binding named serves a different environment",
            ),
            _rule(
                "render-ownership-conflict",
                RefusalCategory.OWNERSHIP_CONFLICT,
                _R,
                "an input supplies a value another layer owns",
            ),
            _rule(
                "render-value-unowned",
                RefusalCategory.OWNERSHIP_CONFLICT,
                _R,
                "an input supplies a value no row of the ownership table assigns to it",
            ),
            _rule(
                "render-manual-value-generated",
                RefusalCategory.OWNERSHIP_CONFLICT,
                _R,
                "a hand-written values file sets a value the renderer generates",
            ),
        )
    }
)


def _field_parts(field: str) -> tuple[object, ...]:
    """A field address, with runs of ASCII digits ordered as numbers rather than text.

    ``split`` with one capturing group alternates text and digit runs, so a position
    always holds the same kind of part and two addresses always compare. A digit run
    is ordered by its length without leading zeros, then its text: the order of the
    number, with no ``int`` conversion that a run of any length or a non-ASCII digit
    could make fail. A field can carry a key read from an input, so the key must not
    be able to turn a refusal into a crash.
    """
    return tuple(
        (len(part.lstrip("0")), part.lstrip("0")) if index % 2 else part
        for index, part in enumerate(_DIGIT_RUN.split(field))
    )


def _sort_key(finding: WorkloadValidationError) -> tuple[object, ...]:
    """Order findings by field, reading list indices as numbers rather than text."""
    return (_field_parts(finding.field), finding.rule_id, finding.reason)


class RenderBoundaryError(DomainError):
    """Base class for every refusal the render boundary itself raises."""


class WorkloadNotAcceptedError(RenderBoundaryError):
    """A parsed WorkloadContract failed a published rule. Carries every finding.

    The findings are sorted by field, then rule, so the same contract is refused
    with the same findings in the same order.
    """

    def __init__(self, findings: tuple[WorkloadValidationError, ...]) -> None:
        if not findings:
            raise ValueError("a refusal needs at least one finding")
        ordered = tuple(sorted(findings, key=_sort_key))
        super().__init__("; ".join(str(finding) for finding in ordered))
        self.findings = ordered

    @property
    def retryable(self) -> bool:
        """A contract that fails a rule does not pass it on retry."""
        return False

    def as_dict(self) -> dict[str, object]:
        """Every finding, in the order a reader should follow them."""
        return {
            "retryable": self.retryable,
            "findings": [finding.as_dict() for finding in self.findings],
        }


@dataclass(frozen=True, slots=True)
class RenderFinding:
    """One reason a render is refused: the rule, where, and why.

    The field names the input by its role - ``contract``, ``bindings[i]`` for the
    i-th binding supplied, ``platformDefaults``, or ``selection`` for the caller's
    own request - and then the path inside it. The category and code are the
    rule's, so a finding cannot carry a pairing the published matrix does not.
    """

    rule_id: str
    field: str
    reason: str
    context: RequestContext = NO_REQUEST_CONTEXT

    def __post_init__(self) -> None:
        # An unpublished identifier is a defect in this package, not a refusal of
        # an input, so it fails loudly here rather than reaching a caller.
        if self.rule_id not in RENDER_RULES:
            raise KeyError(self.rule_id)

    @property
    def rule(self) -> RenderRule:
        return RENDER_RULES[self.rule_id]

    @property
    def category(self) -> RefusalCategory:
        return self.rule.category

    @property
    def code(self) -> str:
        return self.rule.code

    def __str__(self) -> str:
        return f"{self.field}: {self.reason}"

    def as_dict(self) -> dict[str, object]:
        """A safe, structured form: rule, category, code, field, reason, identifiers."""
        return {
            "ruleId": self.rule_id,
            "category": self.category.value,
            "code": self.code,
            "field": self.field,
            "reason": self.reason,
            **self.context.as_dict(),
        }


def _finding_key(finding: RenderFinding) -> tuple[object, ...]:
    return (
        _CATEGORY_ORDER[finding.category],
        _field_parts(finding.field),
        finding.rule_id,
        finding.reason,
    )


class RenderRefused(RenderBoundaryError):
    """A render was refused before any output. Carries every finding at once.

    Findings are sorted by category, in :class:`RefusalCategory` order, then by
    field and rule, so the same inputs are refused with the same findings in the
    same order. The refusal's own code and category are its first finding's: the
    one a reader has to resolve first.
    """

    def __init__(self, findings: Iterable[RenderFinding]) -> None:
        ordered = tuple(sorted(findings, key=_finding_key))
        if not ordered:
            raise ValueError("a refusal needs at least one finding")
        super().__init__("; ".join(str(finding) for finding in ordered))
        self.findings = ordered

    @property
    def code(self) -> str:
        return self.findings[0].code

    @property
    def category(self) -> RefusalCategory:
        return self.findings[0].category

    @property
    def retryable(self) -> bool:
        """No render refusal resolves itself on retry."""
        return False

    def rule_ids(self) -> tuple[str, ...]:
        """Every finding's rule identifier, in order."""
        return tuple(finding.rule_id for finding in self.findings)

    def as_dict(self) -> dict[str, object]:
        """The code, the category, and every finding, in the order to follow them."""
        return {
            "code": self.code,
            "category": self.category.value,
            "retryable": self.retryable,
            "findings": [finding.as_dict() for finding in self.findings],
        }


def from_workload_finding(finding: WorkloadValidationError) -> RenderFinding:
    """A contract's own finding, as a render finding under the same rule."""
    return RenderFinding(
        finding.rule_id,
        f"contract.{finding.field}",
        finding.reason,
        finding.context,
    )


def from_binding_refusal(refusal: BindingRefusal) -> RenderFinding:
    """A binding domain refusal, as a render finding under the same rule.

    The binding domain already names each document by its role, so the field is
    kept as it is.
    """
    if BINDING_RULES[refusal.rule_id].code != RENDER_RULES[refusal.rule_id].code:
        raise AssertionError(f"the code of {refusal.rule_id!r} has drifted")
    return RenderFinding(
        refusal.rule_id, refusal.field, refusal.reason, refusal.context
    )


__all__ = [
    "CAPABILITY_UNAVAILABLE",
    "CONTRACT_INVALID",
    "RENDER_RULES",
    "VERSION_UNSUPPORTED",
    "RefusalCategory",
    "RenderBoundaryError",
    "RenderFinding",
    "RenderRefused",
    "RenderRule",
    "RuleOrigin",
    "WorkloadNotAcceptedError",
    "from_binding_refusal",
    "from_workload_finding",
]
