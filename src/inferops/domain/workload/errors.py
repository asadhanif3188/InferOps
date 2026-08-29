"""What a workload document is refused with while it is being read.

These are *parse* failures: the document cannot be turned into a typed domain
object at all. They are not the platform's canonical validation result, and this
module deliberately does not assign a canonical error code or a rule identifier
to any of them. That vocabulary — ``contract-invalid``, ``version-unsupported``,
and the rule identifiers beside them — is published in
``docs/contracts/workload-contract.md`` and applied by the validation pipeline in
``V1-S1-001-PR2``. Two modules owning one vocabulary is how the two drift.

What this module does own is the distinction the parse itself has to make, and it
makes it in the type rather than in a string:

- :class:`UnsupportedContractVersionError` — the document is well formed for a
  contract version this package does not implement. Nothing further is read from
  it, because every field path below ``apiVersion`` belongs to a shape this
  package has no claim over.
- :class:`MalformedWorkloadContractError` — the document declares a version this
  package implements and then fails to satisfy it.

**A message never carries a value read out of the document.** It names the field,
and it describes the constraint in the schema's own published vocabulary. The
field most likely to be refused for looking wrong is the field most likely to hold
a secret, and an error is the surface most likely to be logged, pasted into a
ticket, and kept. The permitted values of a closed vocabulary are safe to print
because they come from the schema; the value that failed to be one of them is not.
"""

from __future__ import annotations

from ..context import NO_REQUEST_CONTEXT, RequestContext


class DomainError(Exception):
    """Base class for every failure this domain raises."""


class WorkloadContractError(DomainError):
    """A workload document could not be read as a domain object.

    Carries where the failure is, why, and the request-scoped identifiers a caller
    supplied — ``requestId`` and ``correlationId`` when there was a request, and
    an empty context when there was not. The domain never generates either one.
    """

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

    def as_dict(self) -> dict[str, object]:
        """A safe, structured form: field, reason, and any identifiers supplied."""
        return {"field": self.field, "reason": self.reason, **self.context.as_dict()}


class InvalidValueError(DomainError):
    """A constrained value refused itself at construction.

    It carries the constraint that was not met and no field location, because a
    value object does not know where in a document it came from. The parser
    catches this and re-raises it as a :class:`MalformedWorkloadContractError`
    with the field path and the request context attached, which is the division
    of labour: this module knows the constraints, the parser knows the addresses.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class UnsupportedContractVersionError(WorkloadContractError):
    """``apiVersion`` names a contract version this package does not implement."""


class MalformedWorkloadContractError(WorkloadContractError):
    """The document declares a supported version and does not satisfy it."""


class WorkloadValidationError(WorkloadContractError):
    """A parsed workload contract fails a semantic validation rule.

    Carries the field path, the rule identifier (not just a reason), and the
    request-scoped identifiers from context. The reason describes the constraint
    in the schema's own published vocabulary, never a value read from the document.

    A semantic rule is one that compares two fields, consults a compatibility
    matrix, or judges whether a value is plausible. The parsing layer enforces
    single-field structural constraints; this one applies the cross-field and
    matrix rules that the contract publishes under rule identifiers.
    """

    def __init__(
        self,
        field: str,
        rule_id: str,
        reason: str,
        *,
        context: RequestContext = NO_REQUEST_CONTEXT,
    ) -> None:
        super().__init__(field, reason, context=context)
        self.rule_id = rule_id

    def as_dict(self) -> dict[str, object]:
        """A safe, structured form: field, rule_id, reason, and any identifiers."""
        base = super().as_dict()
        base["ruleId"] = self.rule_id
        return base
