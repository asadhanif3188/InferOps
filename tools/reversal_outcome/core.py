"""The outcome of one V2-E04 run, from declared inputs, as revision 3 of its record states it.

Revision 3 of the V2-E04 freeze record selects the stabilization span that E04-AC12
judges by one preregistered rule, ``definition.reversalTiming.selection``, and
states how the verdicts decide the state of a run. This module applies that rule
and those outcome rules to inputs that the caller declares. It is the reference
that the record pins: the review of each run computes the selection from the
evidence and checks it against this function, or a later revision of the record
pins the code that replaces it.

**The selection.** The candidates are the caller completions after
``reversalStart``. The span rule is the stabilization rule of
``tools.reliability_analysis``, unchanged: this module calls its ``_find_span``
over the candidates and copies none of it. ``stabilizationOnset`` is the
completion of the first request of the first span that the rule finds, and
``stabilizedAt`` that of its last request. The span counts only when it
completes inside the observation limit. A span, or the part of a span, that
starts before ``reversalStart`` is never a candidate, so it is never selected
and never a reason for a verdict.

**Two clocks.** ``reversalStart``, the end of the observation limit, and the end
of the window are host instants. The completions are node instants. An order of
the two inside the margin of the clock policy, the clock bound of the run plus the
coarser resolution of the two sources, is resolved both ways. For
``reversalStart`` the selection is made once over the completions that are not
ordered before it, where a completion inside the margin counts as after it, and
once over the completions that are ordered after it. For the end of the
observation limit, ``stabilizedAt`` inside the margin counts once as inside and
once as outside. When every resolution gives one verdict, that is the verdict.
When they differ, the verdict is not judged, for ``clock-bound-reached``.
``recoveryMs`` is compared with the bound only when it differs from the bound by
more than the margin.

**The reported span.** The instants and figures that a result states, and the
post-recovery window that E04-AC5 judges, use the span of the resolution that
counts only the completions ordered after ``reversalStart``, which does not
understate ``recoveryMs``. When that resolution selects no span, because it finds
none or because its span is ordered after the end of the observation limit, they
use the span of the other one.

**No clock bound.** When the end reading of P8 is unusable, the clock bound is not
computable, and each verdict that orders a node instant and a host instant is not
judged, for ``clock-reading-missing``. No completion can then be ordered before
``reversalStart``, so none is known to be before it, and every completion is a
candidate. When no span completes over them at all, E04-AC12 does not depend on
the bound and is not met. When one does, whether it starts after ``reversalStart``
is not known, so E04-AC12 is not judged: the clock uncertainty, and not a span
known to start before ``reversalStart``, leaves it so. Before the reversal commit is
pushed no reading holds it, so the condition series hold no such span.

**The state.** A verdict that is not judged is neither held nor failed. The state
is computed once with each such verdict taken as held and once with each taken as
failed. When the two agree, that is the state. When they differ, the run is
``INCONCLUSIVE`` for the reason of a verdict that is not judged. So a state that
the judged verdicts decide stands.

**E04-AC2.** E04-AC2 is judged here, from the operator events of the reversal and
the reversal commit, and from nothing that the controller reports. It holds when
detection-reviewed, reversal-decided, reversal-created, and reversal-accepted are
recorded once each, in that order and with instants that do not decrease, and
reversal-created and reversal-accepted each record the reversal commit.
reversal-accepted is recorded only after a read of the remote branch reports the
reversal commit as its head, so it is the record of the accepted reversal; whether
the transcript holds that read decides whether reversalStart is established,
which the caller declares, and this module does not read it. Whether
and when the controller resolves the reversal commit is part of the system recovery
that E04-AC12 judges, as the repository owner decided by change control on
2026-10-20: a controller that never resolves it leaves the condition series with no
reading of the reversal commit, so no span completes and E04-AC12 is not met. No
reason is registered for a run whose operator events do not hold, so the state names
E04-AC2 itself.

**What this does not do.** It reads no file and no run directory, runs nothing,
and computes nothing from evidence: the caller declares every input, including
the operator events of the reversal, the verdict of every criterion other than
E04-AC2, E04-AC5, and E04-AC12, the condition series, and the completions. It judges a run that was neither refused nor
aborted. It imports private names of ``tools.reliability_analysis``: the span rule
``_find_span`` and the types of a completion and of a condition series, so a
change to them moves the pin of each record that pins this module.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from tools.reliability_analysis.core import _Completion, _find_span, _Series

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
    "REVERSAL_EVENTS",
    "REVERSAL_EVENTS_CRITERION",
    "REVERSAL_START_UNCONFIRMED",
    "VALIDITY",
    "Criterion",
    "OperatorEvent",
    "Resolution",
    "ReversalInputs",
    "ReversalOutcome",
    "Span",
    "Verdict",
    "reversal_events",
    "reversal_outcome",
]

#: The verdicts of a criterion.
HELD: Final = "held"
NOT_HELD: Final = "not-held"
NOT_JUDGED: Final = "not-judged"
VERDICTS: Final = frozenset({HELD, NOT_HELD, NOT_JUDGED})

#: The kinds of a criterion.
VALIDITY: Final = "validity"
PASS: Final = "pass"
KINDS: Final = frozenset({VALIDITY, PASS})

#: The states of a run that was neither refused nor aborted.
PASSED: Final = "PASSED"
FAILED: Final = "FAILED"
INCONCLUSIVE: Final = "INCONCLUSIVE"

#: The criterion that judges the recovery, the one that judges the window after
#: it, and the one that judges the operator events of the reversal. This module
#: computes all three. Every other criterion is declared.
RECOVERY_CRITERION: Final = "E04-AC12"
POST_RECOVERY_CRITERION: Final = "E04-AC5"
REVERSAL_EVENTS_CRITERION: Final = "E04-AC2"
COMPUTED: Final = (
    REVERSAL_EVENTS_CRITERION,
    POST_RECOVERY_CRITERION,
    RECOVERY_CRITERION,
)

#: The operator events of the reversal, in the order that E04-AC2 requires. The
#: last two record the reversal commit.
REVERSAL_EVENTS: Final = (
    "detection-reviewed",
    "reversal-decided",
    "reversal-created",
    "reversal-accepted",
)
COMMIT_EVENTS: Final = frozenset({"reversal-created", "reversal-accepted"})

#: The reasons for which this module leaves a verdict not judged.
REVERSAL_START_UNCONFIRMED: Final = "reversal-start-unconfirmed"
CLOCK_BOUND_REACHED: Final = "clock-bound-reached"
CLOCK_READING_MISSING: Final = "clock-reading-missing"

#: The two resolutions of the order of a candidate completion and reversalStart.
#: Under the first, a completion inside the margin counts as after reversalStart,
#: and under the second as before it, so the second counts only the completions
#: ordered after it.
MARGIN_AS_AFTER: Final = "margin-as-after"
MARGIN_AS_BEFORE: Final = "margin-as-before"
CANDIDATE_RESOLUTIONS: Final = (MARGIN_AS_AFTER, MARGIN_AS_BEFORE)

#: The two resolutions of the order of stabilizedAt and the end of the
#: observation limit. Under the first, stabilizedAt inside the margin counts as
#: inside the limit, and under the second as outside it.
MARGIN_AS_INSIDE: Final = "margin-as-inside"
MARGIN_AS_OUTSIDE: Final = "margin-as-outside"
LIMIT_RESOLUTIONS: Final = (MARGIN_AS_INSIDE, MARGIN_AS_OUTSIDE)

#: The resolution whose span the reported instants, figures, and E04-AC5 use.
REPORTED_RESOLUTION: Final = MARGIN_AS_BEFORE

#: The one candidate set when the clock bound is not computable: no completion can
#: be ordered before reversalStart, and no instant before the observation limit.
EVERY_COMPLETION: Final = "every-completion"
NOT_ORDERED: Final = "not-ordered"

#: The exclusion reason of a run whose post-recovery window does not hold.
CALLER_INCOMPLETE: Final = "caller-incomplete"

#: The post-recovery window of E04-AC5: at least this many successful requests
#: complete after stabilizedAt inside the window, and the last of them at least
#: this long after it.
POST_RECOVERY_SUCCESSES: Final = 10
POST_RECOVERY_MS: Final = 60_000


@dataclass(frozen=True)
class Verdict:
    """The verdict of one criterion, and its reason.

    The reason of a verdict that is not judged is the reason for which it is not.
    The reason of a validity criterion that does not hold is the exclusion reason
    of the run. A held verdict has no reason.
    """

    verdict: str
    reason: str | None = None


@dataclass(frozen=True)
class OperatorEvent:
    """One event of the operator event log: its name, its recordedAt instant on the
    host clock in milliseconds since the epoch, and the commit that it records."""

    name: str
    recorded_at_ms: int
    commit: str | None = None


@dataclass(frozen=True)
class Criterion:
    """One declared criterion of the run: its identifier, its kind, and its verdict."""

    identifier: str
    kind: str
    verdict: Verdict


@dataclass(frozen=True)
class ReversalInputs:
    """Everything that the outcome of one run is computed from, as declared.

    ``reversal_start_ms`` is ``None`` when reversalStart is not established, and
    ``clock_bound_ms`` is ``None`` when the end reading of P8 is unusable. Each
    instant is in milliseconds since the epoch. ``completions`` are the caller
    completions of the window in completion order, and ``conditions`` are the
    condition series of the span rule, built with the reversal commit as the
    expected desired revision. ``events`` is the operator event log of the run in
    log order, and ``reversal_commit`` the commit of the reversal: E04-AC2 is judged
    from them. ``criteria`` holds every criterion of the record other than E04-AC2,
    E04-AC5, and E04-AC12, with its kind and its verdict.
    """

    reversal_start_ms: int | None
    clock_bound_ms: int | None
    resolution_ms: int
    completions: Sequence[_Completion]
    conditions: Mapping[str, _Series]
    observation_limit_end_ms: int
    window_end_ms: int
    bound_ms: int
    criteria: Sequence[Criterion]
    events: Sequence[OperatorEvent]
    reversal_commit: str


@dataclass(frozen=True)
class Span:
    """A selected span: the completion of its first and its last request, and the
    recovery interval from reversalStart to its onset."""

    onset_ms: int
    stabilized_at_ms: int
    successes: int
    recovery_ms: int


@dataclass(frozen=True)
class Resolution:
    """One resolution of the two cross-clock orders, and the verdict of E04-AC12
    under it. ``span`` is the first span that the rule finds over its candidates,
    inside the observation limit or not."""

    candidates: str
    limit: str
    span: Span | None
    inside_limit: bool
    verdict: Verdict


@dataclass(frozen=True)
class ReversalOutcome:
    """The verdicts that this module computes, the reported span, and the state.

    ``reported`` is the span that the result states, or ``None`` when no span is
    selected inside the observation limit under any resolution. ``reasons`` are
    the reasons of an ``INCONCLUSIVE`` state, and empty otherwise.
    """

    recovery: Verdict
    post_recovery: Verdict
    reversal_events: Verdict
    reported: Span | None
    resolutions: tuple[Resolution, ...]
    state: str
    reasons: tuple[str, ...]


def _check(inputs: ReversalInputs) -> None:
    """Refuse inputs that do not describe one run as declared."""
    finished = [c.finished for c in inputs.completions]
    if finished != sorted(finished):
        raise ValueError("the completions are not in completion order")
    if inputs.clock_bound_ms is not None and inputs.clock_bound_ms < 0:
        raise ValueError("the clock bound is negative")
    if inputs.resolution_ms < 1:
        raise ValueError("the resolution of a source is at least 1 ms")
    if not inputs.reversal_commit:
        raise ValueError("the reversal commit is not declared")
    seen: set[str] = set()
    for criterion in inputs.criteria:
        if criterion.identifier in COMPUTED:
            raise ValueError(f"{criterion.identifier} is computed here, not declared")
        if criterion.identifier in seen:
            raise ValueError(f"{criterion.identifier} is declared twice")
        seen.add(criterion.identifier)
        if criterion.kind not in KINDS or criterion.verdict.verdict not in VERDICTS:
            raise ValueError(f"{criterion.identifier} has no kind or verdict")


def reversal_events(events: Sequence[OperatorEvent], reversal_commit: str) -> Verdict:
    """E04-AC2: the operator events of the reversal, from the event log alone.

    The events of the reversal are read in log order. They hold when they are the
    four of :data:`REVERSAL_EVENTS`, each once and in that order, with instants that
    do not decrease, and when reversal-created and reversal-accepted each record
    the reversal commit. No reading of the controller is an input.
    """
    reversal = [e for e in events if e.name in REVERSAL_EVENTS]
    instants = [e.recorded_at_ms for e in reversal]
    held = (
        tuple(e.name for e in reversal) == REVERSAL_EVENTS
        and instants == sorted(instants)
        and all(
            e.commit == reversal_commit for e in reversal if e.name in COMMIT_EVENTS
        )
    )
    return Verdict(HELD) if held else Verdict(NOT_HELD)


def _order(node: int, host: int, margin: int) -> int:
    """-1 when the node instant is ordered before the host instant, 1 when after,
    and 0 when their difference is inside the margin."""
    if host - node > margin:
        return -1
    if node - host > margin:
        return 1
    return 0


def _candidates(
    completions: Sequence[_Completion], start: int, margin: int, resolution: str
) -> list[_Completion]:
    """The completions after reversalStart under one resolution of their order."""
    if resolution == MARGIN_AS_AFTER:
        return [c for c in completions if _order(c.finished, start, margin) >= 0]
    return [c for c in completions if _order(c.finished, start, margin) > 0]


def _first_span(
    candidates: Sequence[_Completion],
    conditions: Mapping[str, _Series],
    start: int,
) -> Span | None:
    found, _ = _find_span(candidates, conditions)
    if found is None:
        return None
    first, last, size = found
    return Span(first.finished, last.finished, size, first.finished - start)


def _recovery(span: Span | None, inside: bool, bound: int, margin: int) -> Verdict:
    """The verdict of E04-AC12 under one resolution."""
    if span is None or not inside:
        return Verdict(NOT_HELD)
    if abs(span.recovery_ms - bound) <= margin:
        return Verdict(NOT_JUDGED, CLOCK_BOUND_REACHED)
    return Verdict(HELD if span.recovery_ms <= bound else NOT_HELD)


def _one(verdicts: Sequence[Verdict]) -> Verdict:
    """The one verdict of every resolution, or not judged when they differ."""
    distinct = set(verdicts)
    if len(distinct) == 1:
        return verdicts[0]
    return Verdict(NOT_JUDGED, CLOCK_BOUND_REACHED)


def _post_recovery(
    span: Span, completions: Sequence[_Completion], window_end: int, margin: int
) -> Verdict:
    """E04-AC5 over the window after a selected span, with the window end resolved
    both ways."""
    verdicts = []
    # A completion inside the margin of the window end counts once as outside the
    # window and once as inside it.
    for latest in (-1, 0):
        after = [
            c
            for c in completions
            if c.success
            and c.finished > span.stabilized_at_ms
            and _order(c.finished, window_end, margin) <= latest
        ]
        held = (
            len(after) >= POST_RECOVERY_SUCCESSES
            and after[-1].finished - span.stabilized_at_ms >= POST_RECOVERY_MS
        )
        verdicts.append(Verdict(HELD) if held else Verdict(NOT_HELD, CALLER_INCOMPLETE))
    return _one(verdicts)


def _limit_resolutions(order: int) -> list[tuple[str, bool]]:
    """Whether a span is inside the observation limit under each resolution."""
    return [
        (MARGIN_AS_INSIDE, order <= 0),
        (MARGIN_AS_OUTSIDE, order < 0),
    ]


def _state_of(kinds_and_verdicts: Sequence[tuple[str, str]]) -> str:
    if any(k == VALIDITY and v != HELD for k, v in kinds_and_verdicts):
        return INCONCLUSIVE
    if any(k == PASS and v != HELD for k, v in kinds_and_verdicts):
        return FAILED
    return PASSED


def _state(criteria: Sequence[Criterion]) -> tuple[str, tuple[str, ...]]:
    """The state of the run, and the reasons of an INCONCLUSIVE one."""
    as_held = [
        (c.kind, HELD if c.verdict.verdict == NOT_JUDGED else c.verdict.verdict)
        for c in criteria
    ]
    as_failed = [
        (c.kind, NOT_HELD if c.verdict.verdict == NOT_JUDGED else c.verdict.verdict)
        for c in criteria
    ]
    held, failed = _state_of(as_held), _state_of(as_failed)
    if held == failed:
        if held != INCONCLUSIVE:
            return held, ()
        reasons = {
            c.verdict.reason or c.identifier
            for c in criteria
            if c.kind == VALIDITY and c.verdict.verdict == NOT_HELD
        }
        return INCONCLUSIVE, tuple(sorted(reasons))
    reasons = {
        c.verdict.reason or c.identifier
        for c in criteria
        if c.verdict.verdict == NOT_JUDGED
    }
    return INCONCLUSIVE, tuple(sorted(reasons))


def _without_bound(
    inputs: ReversalInputs,
) -> tuple[Verdict, Verdict, tuple[Resolution, ...]]:
    """E04-AC12 and E04-AC5 when the end reading of P8 is unusable."""
    assert inputs.reversal_start_ms is not None
    span = _first_span(inputs.completions, inputs.conditions, inputs.reversal_start_ms)
    if span is None:
        verdict = Verdict(NOT_HELD)
        resolution = Resolution(EVERY_COMPLETION, NOT_ORDERED, None, False, verdict)
        return verdict, Verdict(HELD), (resolution,)
    missing = Verdict(NOT_JUDGED, CLOCK_READING_MISSING)
    resolution = Resolution(EVERY_COMPLETION, NOT_ORDERED, span, False, missing)
    return missing, missing, (resolution,)


def reversal_outcome(inputs: ReversalInputs) -> ReversalOutcome:
    """The verdicts of E04-AC12, E04-AC5, and E04-AC2, the reported span, and the
    state.

    Raises:
        ValueError: the inputs do not describe one run as declared.
    """
    _check(inputs)
    start = inputs.reversal_start_ms
    reported: Span | None = None
    resolutions: tuple[Resolution, ...] = ()
    if start is None:
        recovery = Verdict(NOT_JUDGED, REVERSAL_START_UNCONFIRMED)
        post_recovery = Verdict(HELD)
    elif inputs.clock_bound_ms is None:
        recovery, post_recovery, resolutions = _without_bound(inputs)
    else:
        margin = inputs.clock_bound_ms + inputs.resolution_ms
        spans = {
            name: _first_span(
                _candidates(inputs.completions, start, margin, name),
                inputs.conditions,
                start,
            )
            for name in CANDIDATE_RESOLUTIONS
        }
        found: list[Resolution] = []
        for name in CANDIDATE_RESOLUTIONS:
            span = spans[name]
            order = (
                0
                if span is None
                else _order(
                    span.stabilized_at_ms, inputs.observation_limit_end_ms, margin
                )
            )
            for limit, inside in _limit_resolutions(order):
                inside = span is not None and inside
                verdict = _recovery(span, inside, inputs.bound_ms, margin)
                found.append(Resolution(name, limit, span, inside, verdict))
        resolutions = tuple(found)
        recovery = _one([r.verdict for r in resolutions])
        # The reported span is that of margin-as-before when it selects a span, one
        # that is not ordered after the end of the observation limit, and otherwise
        # that of margin-as-after. A span that completes after the limit is not
        # selected, so it never hides the span of the other resolution.
        chosen = next(
            (
                span
                for span in (spans[REPORTED_RESOLUTION], spans[MARGIN_AS_AFTER])
                if span is not None
                and _order(
                    span.stabilized_at_ms, inputs.observation_limit_end_ms, margin
                )
                <= 0
            ),
            None,
        )
        post_recovery = Verdict(HELD)
        if chosen is not None:
            order = _order(
                chosen.stabilized_at_ms, inputs.observation_limit_end_ms, margin
            )
            judged = _post_recovery(
                chosen, inputs.completions, inputs.window_end_ms, margin
            )
            if order < 0:
                reported, post_recovery = chosen, judged
            elif order == 0:
                reported = chosen
                post_recovery = _one([judged, Verdict(HELD)])
    events = reversal_events(inputs.events, inputs.reversal_commit)
    criteria = [
        *inputs.criteria,
        Criterion(REVERSAL_EVENTS_CRITERION, VALIDITY, events),
        Criterion(POST_RECOVERY_CRITERION, VALIDITY, post_recovery),
        Criterion(RECOVERY_CRITERION, PASS, recovery),
    ]
    state, reasons = _state(criteria)
    return ReversalOutcome(
        recovery=recovery,
        post_recovery=post_recovery,
        reversal_events=events,
        reported=reported,
        resolutions=resolutions,
        state=state,
        reasons=reasons,
    )
