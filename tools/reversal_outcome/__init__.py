"""The outcome reference of V2-E04: its selection and outcome rules, from declared inputs.

Revision 3 of the V2-E04 freeze record selects the stabilization span that
E04-AC12 judges by one preregistered rule: the first span that starts after
reversalStart and is then observed complete inside the observation limit, by the
unchanged span rule of tools/reliability_analysis, with each cross-clock order
inside the margin of the clock policy resolved both ways. This package applies
that rule and the outcome rules of the record to inputs that the caller declares,
and returns the verdicts of E04-AC12 and E04-AC5 and the state of the run. It
reads no run directory and runs nothing.

See docs/proof/experiments/README.md, which describes the record, and
tests/testing/test_reversal_outcome.py, which holds the reference to each case
that the record names.
"""

from .core import (
    CALLER_INCOMPLETE,
    CANDIDATE_RESOLUTIONS,
    CLOCK_BOUND_REACHED,
    CLOCK_READING_MISSING,
    EVERY_COMPLETION,
    FAILED,
    HELD,
    INCONCLUSIVE,
    LIMIT_RESOLUTIONS,
    MARGIN_AS_AFTER,
    MARGIN_AS_BEFORE,
    MARGIN_AS_INSIDE,
    MARGIN_AS_OUTSIDE,
    NOT_HELD,
    NOT_JUDGED,
    NOT_ORDERED,
    PASS,
    PASSED,
    POST_RECOVERY_CRITERION,
    RECOVERY_CRITERION,
    REPORTED_RESOLUTION,
    REVERSAL_START_UNCONFIRMED,
    VALIDITY,
    Criterion,
    Resolution,
    ReversalInputs,
    ReversalOutcome,
    Span,
    Verdict,
    reversal_outcome,
)

__all__ = [
    "CALLER_INCOMPLETE",
    "CANDIDATE_RESOLUTIONS",
    "CLOCK_BOUND_REACHED",
    "CLOCK_READING_MISSING",
    "EVERY_COMPLETION",
    "FAILED",
    "HELD",
    "INCONCLUSIVE",
    "LIMIT_RESOLUTIONS",
    "MARGIN_AS_AFTER",
    "MARGIN_AS_BEFORE",
    "MARGIN_AS_INSIDE",
    "MARGIN_AS_OUTSIDE",
    "NOT_HELD",
    "NOT_JUDGED",
    "NOT_ORDERED",
    "PASS",
    "PASSED",
    "POST_RECOVERY_CRITERION",
    "RECOVERY_CRITERION",
    "REPORTED_RESOLUTION",
    "REVERSAL_START_UNCONFIRMED",
    "VALIDITY",
    "Criterion",
    "Resolution",
    "ReversalInputs",
    "ReversalOutcome",
    "Span",
    "Verdict",
    "reversal_outcome",
]
