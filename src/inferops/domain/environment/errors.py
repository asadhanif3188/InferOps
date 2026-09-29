"""What an EnvironmentBinding is refused with, and the rules that refuse it.

Two kinds of failure, kept apart the way the workload domain keeps them apart.

**Reading one document.** :class:`UnsupportedBindingVersionError` and
:class:`MalformedEnvironmentBindingError` are parse failures: the document cannot
be turned into a typed binding at all. They carry a field, a reason, and the
canonical code their type maps to - ``version-unsupported`` and
``contract-invalid`` - and no rule identifier: every one of them is a structural
refusal the published schema already makes, and the offline validator is what
names the structural rule. The workload domain's parse errors carry no code; the
binding's do, because the code is fixed by the type and a caller should not have
to know that mapping to report one.

**Comparing documents.** A binding that is well formed alone can still conflict
with another binding, or fail to serve a WorkloadContract. Those refusals need
more than one document, the schema cannot express them, and each is published
under a rule identifier in :data:`BINDING_RULES` with the canonical code it maps
to. No canonical code was added for them: every one is ``contract-invalid``, the
code an offline check concludes when the documents it was given cannot be used
as given, and none of them becomes valid on retry.

**A message never carries a value read out of a document.** A binding's name, a
path, a namespace are author-supplied text; a refusal names where the problem is
and which rule refused it, and leaves the value in the document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..workload.errors import DomainError

#: The canonical codes a binding refusal can carry. The same two the offline
#: contract validator publishes; a test holds this set inside that vocabulary.
CONTRACT_INVALID: Final = "contract-invalid"
VERSION_UNSUPPORTED: Final = "version-unsupported"


@dataclass(frozen=True, slots=True)
class BindingRule:
    """One published reason a set of bindings, or a selection, is refused."""

    identifier: str
    code: str
    summary: str


def _rule(identifier: str, summary: str) -> BindingRule:
    return BindingRule(identifier=identifier, code=CONTRACT_INVALID, summary=summary)


#: Every rule the binding domain can cite, keyed by identifier. The binding's
#: contract document publishes the same set as a table, and a test fails if the
#: two disagree or if an identifier here is one the offline validator also uses.
BINDING_RULES: Final[dict[str, BindingRule]] = {
    rule.identifier: rule
    for rule in (
        _rule(
            "binding-identity-duplicated",
            "two bindings declare the same environment and name",
        ),
        _rule(
            "binding-destination-overlaps",
            "two bindings declare the same GitOps destination, or one inside the other",
        ),
        _rule(
            "binding-not-found",
            "no binding serves the contract's environment, or none has the name asked for",
        ),
        _rule(
            "binding-selection-ambiguous",
            "more than one binding serves the contract's environment and none was named",
        ),
        _rule(
            "binding-environment-mismatch",
            "the binding named for a contract serves a different environment",
        ),
    )
}


class EnvironmentBindingError(DomainError):
    """A binding could not be read, or could not be used as given.

    Carries where the failure is, why, the canonical code, and the request-scoped
    identifiers a caller supplied. The domain never generates either identifier.
    """

    #: The canonical code this refusal maps to. Every binding refusal is final:
    #: a document that is malformed or in conflict does not change on retry.
    code: str = CONTRACT_INVALID

    def __init__(
        self,
        field: str,
        reason: str,
        *,
        context: RequestContext = NO_REQUEST_CONTEXT,
    ) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason
        self.context = context

    @property
    def retryable(self) -> bool:
        """A binding refusal does not resolve itself on retry."""
        return False

    def as_dict(self) -> dict[str, object]:
        """A safe, structured form: code, field, reason, and any identifiers."""
        return {
            "code": self.code,
            "retryable": self.retryable,
            "field": self.field,
            "reason": self.reason,
            **self.context.as_dict(),
        }


class UnsupportedBindingVersionError(EnvironmentBindingError):
    """``apiVersion`` names a binding version this package does not implement."""

    code = VERSION_UNSUPPORTED


class MalformedEnvironmentBindingError(EnvironmentBindingError):
    """The document declares a supported version and does not satisfy it."""


class BindingRefusal(EnvironmentBindingError):
    """One published rule refused a set of bindings or a selection among them.

    The field names the document by its role - ``contract``, ``bindings[i]`` for
    the i-th binding supplied, or ``selection`` for the caller's own request - and
    then the path inside it.
    """

    def __init__(
        self,
        field: str,
        rule_id: str,
        reason: str,
        *,
        context: RequestContext = NO_REQUEST_CONTEXT,
    ) -> None:
        # An unpublished identifier is a defect in this package, not a refusal of
        # a document, so it fails loudly here rather than reaching a caller.
        rule = BINDING_RULES[rule_id]
        super().__init__(field, reason, context=context)
        self.rule_id = rule.identifier
        self.code = rule.code

    def as_dict(self) -> dict[str, object]:
        """A safe, structured form: code, rule, field, reason, and identifiers."""
        return {"ruleId": self.rule_id, **super().as_dict()}


class BindingSelectionError(DomainError):
    """No binding could be selected for a contract. Carries every reason at once.

    A selection over a set of bindings that conflict with each other is not
    attempted, so the refusals are either the set's conflicts or the selection's
    own reasons, never a mixture that would report one cause twice.
    """

    def __init__(self, refusals: tuple[BindingRefusal, ...]) -> None:
        if not refusals:
            raise ValueError("a selection error needs at least one refusal")
        super().__init__("; ".join(str(refusal) for refusal in refusals))
        self.refusals = refusals

    def as_dict(self) -> dict[str, object]:
        """Every refusal, in the order a reader should follow them."""
        return {"refusals": [refusal.as_dict() for refusal in self.refusals]}


__all__ = [
    "BINDING_RULES",
    "CONTRACT_INVALID",
    "VERSION_UNSUPPORTED",
    "BindingRefusal",
    "BindingRule",
    "BindingSelectionError",
    "EnvironmentBindingError",
    "MalformedEnvironmentBindingError",
    "UnsupportedBindingVersionError",
]
