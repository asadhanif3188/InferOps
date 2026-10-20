"""The outcome reference of V2-E04, held to each case that revision 3 of its record names.

``tools.reversal_outcome`` applies the selection rule and the outcome rules of
revision 3 of the V2-E04 freeze record to declared inputs. Each test below builds
one synthetic run in memory: the caller completions, the three condition series of
the span rule, the instants of the host clock, the clock bound, and the verdict of
every criterion that the reference does not compute. No test reads a run
directory, runs an experiment, or contacts a cluster, and no run of V2-E04 exists.

A test of the first part names the case, the verdict of E04-AC12, and the state.
The second part holds what the reference is: a pure function that reuses the span
rule of ``tools.reliability_analysis`` by import, and that refuses inputs that do
not describe one run.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from tools import reversal_outcome as outcome
from tools.reliability_analysis import core as analysis
from tools.reversal_outcome import (
    CLOCK_BOUND_REACHED,
    CLOCK_READING_MISSING,
    FAILED,
    HELD,
    INCONCLUSIVE,
    MARGIN_AS_AFTER,
    MARGIN_AS_BEFORE,
    NOT_HELD,
    NOT_JUDGED,
    PASS,
    PASSED,
    REVERSAL_START_UNCONFIRMED,
    VALIDITY,
    Criterion,
    ReversalInputs,
    ReversalOutcome,
    Verdict,
    reversal_outcome,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
E04_R3 = "docs/proof/experiments/v2-e04/freeze-r3.v1alpha1.json"

#: The instants of the synthetic run, in milliseconds. The fault finishes at 100 s,
#: reversalStart is at 200.5 s, and the observation limit and the window end at
#: 1,680 s and 1,800 s after the fault, as revision 3 states them.
FAULT_FINISHED = 100_000
REVERSAL_START = 200_500
OBSERVATION_LIMIT_END = FAULT_FINISHED + 1_680_000
WINDOW_END = FAULT_FINISHED + 1_800_000
BOUND = 52_000
#: A clock bound of 40 ms and a resolution of 1 ms give a margin of 41 ms.
CLOCK_BOUND = 40
RESOLUTION = 1
MARGIN = CLOCK_BOUND + RESOLUTION

#: Every criterion of V2-E04 other than E04-AC5 and E04-AC12, with its kind.
OTHER_CRITERIA = {
    "E04-AC1": VALIDITY,
    "E04-AC2": VALIDITY,
    "E04-AC3": VALIDITY,
    "E04-AC4": VALIDITY,
    "E04-AC6": VALIDITY,
    "E04-AC7": VALIDITY,
    "E04-AC8": PASS,
    "E04-AC9": PASS,
    "E04-AC10": PASS,
    "E04-AC11": PASS,
    "E04-AC13": PASS,
}


def completions(*segments: tuple[int, int, bool]) -> list[analysis._Completion]:
    """One completion every second from each start to each end, inclusive."""
    found: list[analysis._Completion] = []
    for start, end, success in segments:
        for finished in range(start, end + 1, 1000):
            found.append(
                analysis._Completion(
                    sequence=len(found) + 1,
                    started=finished - 500,
                    finished=finished,
                    success=success,
                    outcome="success" if success else "http-error",
                )
            )
    return sorted(found, key=lambda c: c.finished)


def series(held_from: int, until: int = WINDOW_END) -> analysis._Series:
    """A reading every 2 s that lasts 50 ms, holding its condition from ``held_from``."""
    observations = []
    for index, started in enumerate(range(0, until - 50, 2000)):
        state = analysis._HELD if started >= held_from else analysis._NOT_HELD
        observations.append(analysis._Observation(index, started, started + 50, state))
    return analysis._Series(None, tuple(observations), 0)


def conditions(synced_from: int = 0) -> dict[str, analysis._Series]:
    """The three conditions: the reversal commit from ``synced_from``, and the
    replicas and the endpoints throughout."""
    return {
        "desiredRevision": series(synced_from),
        "readyReplicas": series(0),
        "runtimeReadyEndpoints": series(0),
    }


def criteria(**verdicts: Verdict) -> list[Criterion]:
    """Every declared criterion held, except those named, by identifier with ``_``."""
    named = {key.replace("_", "-"): verdict for key, verdict in verdicts.items()}
    return [
        Criterion(identifier, kind, named.get(identifier, Verdict(HELD)))
        for identifier, kind in OTHER_CRITERIA.items()
    ]


def run(
    calls: Sequence[analysis._Completion],
    *,
    synced_from: int = 0,
    start: int | None = REVERSAL_START,
    clock_bound: int | None = CLOCK_BOUND,
    declared: list[Criterion] | None = None,
    limit_end: int = OBSERVATION_LIMIT_END,
) -> ReversalOutcome:
    return reversal_outcome(
        ReversalInputs(
            reversal_start_ms=start,
            clock_bound_ms=clock_bound,
            resolution_ms=RESOLUTION,
            completions=calls,
            conditions=conditions(synced_from),
            observation_limit_end_ms=limit_end,
            window_end_ms=WINDOW_END,
            bound_ms=BOUND,
            criteria=criteria() if declared is None else declared,
        )
    )


def every(start: int, step: int, count: int) -> list[analysis._Completion]:
    """``count`` successful completions, ``step`` ms apart, from ``start``."""
    return [
        analysis._Completion(
            k + 1, start + step * k - 500, start + step * k, True, "success"
        )
        for k in range(count)
    ]


def successes_from(start: int, end: int = WINDOW_END - 1000) -> tuple[int, int, bool]:
    return (start, end, True)


def failures(start: int, end: int) -> tuple[int, int, bool]:
    return (start, end, False)


# --------------------------------------------------------------------------
# 1. The cases of revision 3
# --------------------------------------------------------------------------


def test_no_span_that_starts_after_reversal_start_completes_inside_the_limit() -> None:
    """A valid run: every validity criterion holds, reversalStart is established,
    and the callers fail until after the observation limit. E04-AC12 is not met."""
    result = run(
        completions(
            successes_from(0, FAULT_FINISHED),
            failures(FAULT_FINISHED + 1000, OBSERVATION_LIMIT_END),
            successes_from(OBSERVATION_LIMIT_END + 1000),
        )
    )
    assert result.recovery == Verdict(NOT_HELD)
    assert result.state == FAILED
    assert result.reported is None


def test_an_earlier_span_with_no_later_qualifying_span_is_failed() -> None:
    """A span starts before reversalStart and completes. After reversalStart the
    successes last 29 s, and the callers then fail to the end. The earlier span is
    never a reason for a verdict: the run is FAILED, never INCONCLUSIVE."""
    calls = completions(
        successes_from(150_000, 230_000),
        failures(231_000, WINDOW_END - 1000),
    )
    # The span rule over every completion finds the earlier span.
    found, _ = analysis._find_span(calls, conditions())
    assert found is not None and found[0].finished == 150_000
    result = run(calls)
    assert result.recovery == Verdict(NOT_HELD)
    assert result.state == FAILED
    assert result.reasons == ()
    assert all(r.span is None for r in result.resolutions)


@pytest.mark.parametrize(
    ("later_onset", "verdict", "state"),
    [
        pytest.param(REVERSAL_START + 31_500, Verdict(HELD), PASSED, id="inside"),
        pytest.param(REVERSAL_START + 60_500, Verdict(NOT_HELD), FAILED, id="outside"),
        pytest.param(
            REVERSAL_START + BOUND + 20,
            Verdict(NOT_JUDGED, CLOCK_BOUND_REACHED),
            INCONCLUSIVE,
            id="inside-the-margin-of-the-bound",
        ),
    ],
)
def test_a_later_qualifying_span_is_selected_and_judged_against_the_bound(
    later_onset: int, verdict: Verdict, state: str
) -> None:
    """A span before reversalStart, then a failure, then a span that starts after
    reversalStart and completes. The later span is selected, and recoveryMs is
    compared with 52,000 ms only when it differs from it by more than the margin."""
    calls = completions(
        successes_from(150_000, 230_000),
        failures(231_000, later_onset - 1000),
        successes_from(later_onset),
    )
    result = run(calls)
    assert result.reported is not None
    assert result.reported.onset_ms == later_onset
    assert result.reported.recovery_ms == later_onset - REVERSAL_START
    assert result.recovery == verdict
    assert result.state == state
    if state == INCONCLUSIVE:
        assert result.reasons == (CLOCK_BOUND_REACHED,)


def test_a_span_that_continues_across_reversal_start_is_cut_at_it() -> None:
    """The successes start at 150 s and never stop. The part after reversalStart is
    the candidate: its first completion, at 201 s, is the onset."""
    result = run(completions(successes_from(150_000)))
    assert result.reported is not None
    assert result.reported.onset_ms == 201_000
    assert result.reported.stabilized_at_ms == 261_000
    assert result.reported.recovery_ms == 500
    assert result.recovery == Verdict(HELD)
    assert result.state == PASSED


def test_an_interrupted_candidate_span_is_not_selected_and_the_next_one_is() -> None:
    """A candidate span after reversalStart is interrupted by one failure after 40 s.
    It establishes no recovery, and the next completed span is selected."""
    result = run(
        completions(
            failures(FAULT_FINISHED, 200_000),
            successes_from(201_000, 241_000),
            failures(242_000, 242_000),
            successes_from(243_000),
        )
    )
    assert result.reported is not None
    assert result.reported.onset_ms == 243_000
    assert result.reported.stabilized_at_ms == 303_000
    assert result.recovery == Verdict(HELD)
    assert result.state == PASSED


def test_no_completed_span_at_all_with_every_validity_criterion_held() -> None:
    result = run(
        completions(
            successes_from(0, FAULT_FINISHED),
            failures(FAULT_FINISHED + 1000, WINDOW_END - 1000),
        )
    )
    assert result.recovery == Verdict(NOT_HELD)
    assert result.post_recovery == Verdict(HELD)
    assert result.state == FAILED


def test_an_earlier_span_inside_the_limit_and_a_later_one_outside_it() -> None:
    """The span before reversalStart completes inside the observation limit, and the
    first span after reversalStart completes 29 s after it. E04-AC12 is not met."""
    later = OBSERVATION_LIMIT_END - 31_000
    result = run(
        completions(
            successes_from(150_000, 230_000),
            failures(231_000, later - 1000),
            successes_from(later),
        )
    )
    spans = {r.span for r in result.resolutions}
    assert len(spans) == 1
    (span,) = spans
    assert span is not None and span.stabilized_at_ms == later + 60_000
    assert span.stabilized_at_ms > OBSERVATION_LIMIT_END + MARGIN
    assert result.recovery == Verdict(NOT_HELD)
    assert result.reported is None
    assert result.state == FAILED


def test_stabilized_at_inside_the_margin_of_the_limit_end_far_above_the_bound() -> None:
    """stabilizedAt lies 10 ms after the end of the observation limit, inside the
    margin, so the order is resolved both ways. Inside, recoveryMs is far above the
    bound, and outside, recovery is not established: one verdict, not met."""
    onset = OBSERVATION_LIMIT_END + 10 - 60_000
    result = run(
        completions(
            failures(FAULT_FINISHED, onset - 10),
            (onset, onset + 60_000, True),
            successes_from(onset + 61_000),
        )
    )
    assert result.reported is not None
    assert result.reported.stabilized_at_ms == OBSERVATION_LIMIT_END + 10
    assert {r.inside_limit for r in result.resolutions} == {True, False}
    assert {r.verdict for r in result.resolutions} == {Verdict(NOT_HELD)}
    assert result.recovery == Verdict(NOT_HELD)
    assert result.state == FAILED


def test_two_resolutions_select_different_spans_with_one_verdict() -> None:
    """A completion at reversalStart, inside the margin. The resolution that counts it
    as after selects the span from it, and the one that counts only completions
    ordered after selects the span from the next. Both are inside the bound. The
    reported figures and E04-AC5 use the second: its window holds 59 s of successes
    after its stabilizedAt, so E04-AC5 does not hold, where the first span's would."""
    start = 200_000
    result = run(
        completions(
            failures(FAULT_FINISHED, start - 1000),
            successes_from(start, start + 120_000),
            failures(start + 121_000, WINDOW_END - 1000),
        ),
        start=start,
    )
    spans = {r.candidates: r.span for r in result.resolutions}
    assert spans[MARGIN_AS_AFTER] is not None
    assert spans[MARGIN_AS_BEFORE] is not None
    assert spans[MARGIN_AS_AFTER].onset_ms == start
    assert spans[MARGIN_AS_BEFORE].onset_ms == start + 1000
    assert result.recovery == Verdict(HELD)
    assert result.reported == spans[MARGIN_AS_BEFORE]
    assert result.reported.stabilized_at_ms == start + 61_000
    assert result.reported.recovery_ms == 1000
    assert result.post_recovery == Verdict(NOT_HELD, outcome.CALLER_INCOMPLETE)
    assert result.state == INCONCLUSIVE
    assert result.reasons == (outcome.CALLER_INCOMPLETE,)


def test_the_other_span_is_reported_when_the_first_completes_after_the_limit() -> None:
    """Found by the review of the first commit. A completion every 7 s from 20 ms
    before reversalStart, inside the margin. margin-as-after selects the span from it,
    which completes inside the observation limit; margin-as-before selects the span
    from the next one, which completes after it and so is not selected. The reported
    span, and the post-recovery window that E04-AC5 judges, are then those of
    margin-as-after. The first commit reported no span and held E04-AC5 trivially."""
    start = 200_500
    calls = every(start - 20, 7000, 21)
    result = run(calls, start=start, limit_end=267_000)
    spans = {r.candidates: r.span for r in result.resolutions}
    assert spans[MARGIN_AS_BEFORE] is not None
    assert spans[MARGIN_AS_BEFORE].stabilized_at_ms == start - 20 + 70_000
    assert spans[MARGIN_AS_AFTER] is not None
    assert result.reported == spans[MARGIN_AS_AFTER]
    assert result.reported.onset_ms == start - 20
    assert result.reported.stabilized_at_ms == start - 20 + 63_000
    # The resolutions give different verdicts: held after, not met before.
    assert result.recovery == Verdict(NOT_JUDGED, CLOCK_BOUND_REACHED)
    assert result.post_recovery == Verdict(HELD)
    # Without successes after the reported span, E04-AC5 of that span fails.
    short = run(calls[:11], start=start, limit_end=267_000)
    assert short.reported == spans[MARGIN_AS_AFTER]
    assert short.post_recovery == Verdict(NOT_HELD, outcome.CALLER_INCOMPLETE)


def test_stabilized_at_inside_the_margin_of_the_limit_with_two_verdicts() -> None:
    """stabilizedAt 10 ms after the end of the observation limit, and recoveryMs well
    inside the bound: inside the limit E04-AC12 holds, outside it is not met, so it
    is not judged. E04-AC5 applies under one resolution and holds under both."""
    calls = completions(successes_from(201_000))
    result = run(calls, limit_end=261_000 - 10)
    assert result.reported is not None
    assert result.reported.stabilized_at_ms == 261_000
    assert {r.verdict for r in result.resolutions} == {
        Verdict(HELD),
        Verdict(NOT_HELD),
    }
    assert result.recovery == Verdict(NOT_JUDGED, CLOCK_BOUND_REACHED)
    assert result.post_recovery == Verdict(HELD)
    assert result.state == INCONCLUSIVE


def test_e04_ac5_inside_the_margin_of_the_limit_with_two_verdicts() -> None:
    """The same span, with no successful request after it: E04-AC5 fails when the span
    counts as inside the limit and holds when it does not, so it is not judged."""
    calls = completions(successes_from(201_000, 261_000), failures(262_000, 400_000))
    result = run(calls, limit_end=261_000 - 10)
    assert result.post_recovery == Verdict(NOT_JUDGED, CLOCK_BOUND_REACHED)
    assert result.state == INCONCLUSIVE


def test_a_first_request_inside_the_margin_with_one_verdict_both_ways() -> None:
    start = 200_000
    result = run(
        completions(failures(FAULT_FINISHED, start - 1000), successes_from(start)),
        start=start,
    )
    assert {r.span.onset_ms for r in result.resolutions if r.span} == {
        start,
        start + 1000,
    }
    assert result.recovery == Verdict(HELD)
    assert result.state == PASSED


def test_a_first_request_inside_the_margin_with_two_verdicts_is_not_judged() -> None:
    """Counted as after reversalStart, the completion at it starts a span of exactly
    60 s that completes. Counted as before it, the 59 s that remain are no span, a
    failure follows, and the next span starts 100 s later, outside the bound. The
    verdicts differ, so E04-AC12 is not judged, and notJudged decides the state."""
    start = 200_000
    result = run(
        completions(
            failures(FAULT_FINISHED, start - 1000),
            (start, start + 60_000, True),
            failures(start + 61_000, start + 99_000),
            successes_from(start + 100_000),
        ),
        start=start,
    )
    verdicts = {r.candidates: r.verdict for r in result.resolutions}
    assert verdicts[MARGIN_AS_AFTER] == Verdict(HELD)
    assert verdicts[MARGIN_AS_BEFORE] == Verdict(NOT_HELD)
    assert result.recovery == Verdict(NOT_JUDGED, CLOCK_BOUND_REACHED)
    assert result.state == INCONCLUSIVE
    assert result.reasons == (CLOCK_BOUND_REACHED,)


def test_an_unusable_end_reading_with_a_candidate_span() -> None:
    """With no clock bound, each verdict that orders a node and a host instant is not
    judged, for clock-reading-missing, and notJudged decides the state."""
    result = run(completions(successes_from(150_000)), clock_bound=None)
    assert result.recovery == Verdict(NOT_JUDGED, CLOCK_READING_MISSING)
    assert result.post_recovery == Verdict(NOT_JUDGED, CLOCK_READING_MISSING)
    assert result.state == INCONCLUSIVE
    assert result.reasons == (CLOCK_READING_MISSING,)


def test_an_unusable_end_reading_with_no_span_that_completes() -> None:
    """No span completes over any completion, so E04-AC12 does not depend on the
    clock bound, and it is not met. With no bound, no completion can be ordered
    before reversalStart, so every completion of the window is a candidate: the
    successes before the fault are no span only because no reading holds the
    reversal commit before it is pushed."""
    calls = completions(
        successes_from(0, FAULT_FINISHED),
        failures(FAULT_FINISHED + 1000, WINDOW_END - 1000),
    )
    assert run(calls, clock_bound=None).recovery == Verdict(
        NOT_JUDGED, CLOCK_READING_MISSING
    )
    result = run(calls, synced_from=REVERSAL_START, clock_bound=None)
    assert result.recovery == Verdict(NOT_HELD)
    assert result.post_recovery == Verdict(HELD)
    assert result.state == FAILED


def test_the_controller_never_resolves_the_reversal_commit_inside_the_limit() -> None:
    """The callers succeed, but no reading holds the reversal commit before the end of
    the window, so no span completes. E04-AC2, a validity criterion inherited from
    revision 1, does not hold, because no argo reading reports the reversal commit
    inside the observation limit: the run is INCONCLUSIVE, not FAILED. Revision 3
    does not change E04-AC2, and its validation record lists this path. No
    registered exclusion reason names this cause, so the criterion is the reason."""
    result = run(
        completions(successes_from(0)),
        synced_from=WINDOW_END,
        declared=criteria(E04_AC2=Verdict(NOT_HELD)),
    )
    assert result.recovery == Verdict(NOT_HELD)
    assert result.state == INCONCLUSIVE
    assert result.reasons == ("E04-AC2",)


def test_reversal_start_not_established() -> None:
    result = run(completions(successes_from(150_000)), start=None)
    assert result.recovery == Verdict(NOT_JUDGED, REVERSAL_START_UNCONFIRMED)
    assert result.resolutions == ()
    assert result.state == INCONCLUSIVE
    assert result.reasons == (REVERSAL_START_UNCONFIRMED,)


@pytest.mark.parametrize("reason", ["stream-incomplete", "caller-incomplete"])
def test_a_validity_criterion_that_does_not_hold(reason: str) -> None:
    declared = criteria(
        E04_AC3=Verdict(NOT_HELD, reason)
        if reason == "stream-incomplete"
        else Verdict(HELD),
        E04_AC4=Verdict(NOT_HELD, reason)
        if reason == "caller-incomplete"
        else Verdict(HELD),
    )
    result = run(completions(successes_from(150_000)), declared=declared)
    assert result.recovery == Verdict(HELD)
    assert result.state == INCONCLUSIVE
    assert result.reasons == (reason,)


@pytest.mark.parametrize("criterion", ["E04_AC10", "E04_AC11"])
def test_another_pass_criterion_not_met_with_e04_ac12_not_judged(
    criterion: str,
) -> None:
    """E04-AC12 is not judged because reversalStart is not established, and a judged
    pass criterion is not met. The judged verdicts decide FAILED, and it stands."""
    result = run(
        completions(successes_from(150_000)),
        start=None,
        declared=criteria(**{criterion: Verdict(NOT_HELD)}),
    )
    assert result.recovery == Verdict(NOT_JUDGED, REVERSAL_START_UNCONFIRMED)
    assert result.state == FAILED
    assert result.reasons == ()


def test_a_failed_containment_stands_inside_the_margin_of_the_bound() -> None:
    """The same rule for a verdict inside the clock margin: E04-AC12 is not judged,
    for clock-bound-reached, and a judged pass criterion is not met."""
    onset = REVERSAL_START + BOUND + 20
    result = run(
        completions(failures(FAULT_FINISHED, onset - 1000), successes_from(onset)),
        declared=criteria(E04_AC9=Verdict(NOT_HELD)),
    )
    assert result.recovery == Verdict(NOT_JUDGED, CLOCK_BOUND_REACHED)
    assert result.state == FAILED


def test_a_span_can_start_up_to_one_reading_before_the_reversal_commit_holds() -> None:
    """The limitation that revision 3 states: a reading that does not hold blocks a
    span only until it finishes, so the span starts after the last such reading and
    before the next reading, which holds the commit. recoveryMs can be understated
    by up to one reading interval, 2 s here."""
    synced = 250_000
    result = run(completions(successes_from(150_000)), synced_from=synced)
    assert result.reported is not None
    last_not_held = synced - 2000 + 50
    assert last_not_held < result.reported.onset_ms < synced
    assert result.reported.onset_ms == 249_000


# --------------------------------------------------------------------------
# 2. What the reference is
# --------------------------------------------------------------------------

SOURCE = REPO_ROOT / "tools" / "reversal_outcome" / "core.py"


def test_the_span_rule_is_imported_and_not_copied() -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert not defined & {"_find_span", "_blocked_until", "_inside", "_spans"}
    assert vars(outcome.core)["_find_span"] is analysis._find_span
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported |= {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    # No module that reads a file, a process, or the network.
    assert imported == {
        "__future__",
        "collections.abc",
        "dataclasses",
        "typing",
        "tools.reliability_analysis.core",
    }


def test_the_kinds_of_the_declared_criteria_are_those_of_revision_3() -> None:
    document: Any = json.loads((REPO_ROOT / E04_R3).read_text(encoding="utf-8"))
    (entry,) = document["fields"]["acceptanceCriteria"]
    kinds = {c["id"]: c["kind"] for c in entry["value"]}
    assert kinds.pop("E04-AC5") == VALIDITY
    assert kinds.pop("E04-AC12") == PASS
    assert kinds == OTHER_CRITERIA


def test_revision_3_pins_the_reference() -> None:
    document: Any = json.loads((REPO_ROOT / E04_R3).read_text(encoding="utf-8"))
    pinned = {p["path"] for p in document["pinnedInputs"]}
    assert {
        "tools/reversal_outcome/__init__.py",
        "tools/reversal_outcome/core.py",
        "tools/reliability_analysis/core.py",
    } <= pinned
    assert "tools.reversal_outcome.core" in document["materialScope"]["entryModules"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        pytest.param(
            {"completions": completions((2000, 2000, True), (1000, 1000, True))[::-1]},
            "completion order",
            id="completions-out-of-order",
        ),
        pytest.param({"clock_bound_ms": -1}, "negative", id="negative-bound"),
        pytest.param({"resolution_ms": 0}, "resolution", id="zero-resolution"),
        pytest.param(
            {"criteria": [Criterion("E04-AC12", PASS, Verdict(HELD))]},
            "computed here",
            id="recovery-declared",
        ),
        pytest.param(
            {"criteria": [Criterion("E04-AC5", VALIDITY, Verdict(HELD))]},
            "computed here",
            id="post-recovery-declared",
        ),
        pytest.param(
            {"criteria": [Criterion("E04-AC1", VALIDITY, Verdict(HELD))] * 2},
            "twice",
            id="declared-twice",
        ),
        pytest.param(
            {"criteria": [Criterion("E04-AC1", "other", Verdict(HELD))]},
            "no kind",
            id="unknown-kind",
        ),
        pytest.param(
            {"criteria": [Criterion("E04-AC1", VALIDITY, Verdict("maybe"))]},
            "no kind",
            id="unknown-verdict",
        ),
    ],
)
def test_inputs_that_do_not_describe_one_run_are_refused(
    change: dict[str, Any], message: str
) -> None:
    values: dict[str, Any] = {
        "reversal_start_ms": REVERSAL_START,
        "clock_bound_ms": CLOCK_BOUND,
        "resolution_ms": RESOLUTION,
        "completions": completions(successes_from(150_000)),
        "conditions": conditions(),
        "observation_limit_end_ms": OBSERVATION_LIMIT_END,
        "window_end_ms": WINDOW_END,
        "bound_ms": BOUND,
        "criteria": criteria(),
        **change,
    }
    with pytest.raises(ValueError, match=message):
        reversal_outcome(ReversalInputs(**values))
