"""What the render boundary refuses a workload with, before anything is rendered.

One refusal is the boundary's own: :class:`WorkloadNotAcceptedError`, raised when a
parsed WorkloadContract fails a rule the published contract applies. It carries
every finding at once, each a
:class:`~inferops.domain.workload.errors.WorkloadValidationError` with the
published rule identifier it was refused under, and it assigns no code of its own.

**No render refusal vocabulary is defined here.** A missing or ambiguous binding is
refused by the binding domain's selection rules, which raise
:class:`~inferops.domain.environment.errors.BindingSelectionError` with their own
published identifiers, and the boundary lets that through unchanged. Platform
defaults of a version this package does not implement refuse themselves at
construction. Which canonical code each of these, and an ownership conflict,
becomes when a renderer reports it is a later change; inventing the codes before
the refusals that need them would be a vocabulary with no consumer.

**A message never carries a value read out of a document**, for the reason every
other domain package gives: the field most likely to be refused for looking wrong
is the field most likely to hold a secret.
"""

from __future__ import annotations

import re

from ..workload.errors import DomainError, WorkloadValidationError

_DIGIT_RUN = re.compile(r"(\d+)")


def _sort_key(finding: WorkloadValidationError) -> tuple[object, ...]:
    """Order findings by field, reading list indices as numbers rather than text."""
    parts = tuple(
        int(part) if part.isdigit() else part
        for part in _DIGIT_RUN.split(finding.field)
    )
    return (parts, finding.rule_id, finding.reason)


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


__all__ = ["RenderBoundaryError", "WorkloadNotAcceptedError"]
