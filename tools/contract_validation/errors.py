"""Canonical validation errors for InferOps public contracts.

A contract is rejected with a *canonical error code*, a *stable rule identifier*,
and a *field location*. The three are separate on purpose:

- the **code** is the small, public, cross-surface vocabulary an HTTP client
  switches on. It is deliberately coarse and it does not grow when a rule is
  added;
- the **rule** names which specific rule refused the document. It is stable, it
  is quotable in a review, and it is what a reader looks up in the contract
  document's rejection matrix;
- the **field** says where. Without it, a document with forty fields produces a
  refusal the author has to bisect by hand.

A message may never carry a value read out of the document. That rule exists
because the most likely place for a secret to appear is the field that was
rejected for looking wrong, and an error body is the surface most likely to be
logged, pasted into a ticket, and kept.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: Canonical error codes this validator can emit, with their retryable default.
#: The wider code vocabulary belongs to the runtime surfaces that can produce it;
#: an offline document check can only ever conclude these two.
CANONICAL_ERROR_CODES: Final[dict[str, bool]] = {
    "contract-invalid": False,
    "version-unsupported": False,
}

CONTRACT_INVALID: Final = "contract-invalid"
VERSION_UNSUPPORTED: Final = "version-unsupported"


@dataclass(frozen=True)
class Rule:
    """One reason a contract can be refused."""

    identifier: str
    code: str
    summary: str
    #: True when the rule needs information JSON Schema cannot express and is
    #: therefore applied by this module rather than by the schema.
    semantic: bool


def _rule(identifier: str, code: str, summary: str, *, semantic: bool = False) -> Rule:
    return Rule(identifier=identifier, code=code, summary=summary, semantic=semantic)


#: Every rule this validator can cite, keyed by identifier. The contract document
#: publishes this same set as a table, and a test fails if the two disagree.
RULES: Final[dict[str, Rule]] = {
    rule.identifier: rule
    for rule in (
        # --- structural: derived from a JSON Schema keyword ------------------
        _rule(
            "contract-version-unsupported",
            VERSION_UNSUPPORTED,
            "apiVersion is not a contract version this validator supports",
        ),
        _rule(
            "field-required",
            CONTRACT_INVALID,
            "a required field is absent",
        ),
        _rule(
            "field-unknown",
            CONTRACT_INVALID,
            "a field the contract version does not define is present",
        ),
        _rule(
            "value-not-permitted",
            CONTRACT_INVALID,
            "a value is outside the controlled vocabulary or is forbidden in this position",
        ),
        _rule(
            "value-malformed",
            CONTRACT_INVALID,
            "a value does not match the required format for its field",
        ),
        _rule(
            "value-out-of-range",
            CONTRACT_INVALID,
            "a value is outside the permitted length, bound, or item count",
        ),
        _rule(
            "value-wrong-type",
            CONTRACT_INVALID,
            "a value is of the wrong JSON type",
        ),
        _rule(
            "contract-structure-invalid",
            CONTRACT_INVALID,
            "the document violates a structural constraint with no more specific rule",
        ),
        # --- semantic: cross-field or matrix-driven --------------------------
        _rule(
            "replica-range-inverted",
            CONTRACT_INVALID,
            "minimumReplicas exceeds maximumReplicas",
            semantic=True,
        ),
        _rule(
            "secret-value-in-locator",
            CONTRACT_INVALID,
            "a secret reference looks like a pasted credential rather than a locator",
            semantic=True,
        ),
        _rule(
            "secret-ref-name-duplicated",
            CONTRACT_INVALID,
            "two secret references declare the same logical name",
            semantic=True,
        ),
        _rule(
            "mock-secret-ref-declared",
            CONTRACT_INVALID,
            "a mock-llm workload declares a secret reference",
            semantic=True,
        ),
        _rule(
            "runtime-unregistered",
            CONTRACT_INVALID,
            "the runtime image is not in the published runtime and model compatibility matrix",
            semantic=True,
        ),
        _rule(
            "model-artifact-format-unknown",
            CONTRACT_INVALID,
            "the model artifact filename has no recognised format extension",
            semantic=True,
        ),
        _rule(
            "runtime-model-incompatible",
            CONTRACT_INVALID,
            "the runtime does not accept the model artifact format this workload pins",
            semantic=True,
        ),
    )
}


@dataclass(frozen=True, order=True)
class Finding:
    """One refusal, ordered so that a result set sorts identically everywhere."""

    field: str
    rule: str
    code: str
    message: str

    @property
    def retryable(self) -> bool:
        """An invalid document does not become valid on retry."""
        return CANONICAL_ERROR_CODES[self.code]

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "rule": self.rule,
            "field": self.field,
            "message": self.message,
            "retryable": self.retryable,
        }


def finding(rule_identifier: str, field: str, message: str) -> Finding:
    """Build a finding, refusing an unregistered rule rather than inventing one."""
    rule = RULES[rule_identifier]
    return Finding(field=field, rule=rule.identifier, code=rule.code, message=message)
