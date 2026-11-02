"""The classification of the V2-E02A runs, held to the rule of revision 4.

The first part applies ``decide`` and ``basis_of`` to synthetic sets. They hold the
cases that the three real runs do not reach: a set that shows no failure, a set with
a zero baseline, and a set with too few counted runs. The real set is eligible with
two figures above zero, so only these tests reach the case with no percentage.

The second part reads the committed record and the committed runs. It holds that the
record is what the runs give, that each run is listed, and that the record states no
percentage and no V1 figure.

The third part holds the adjudicated record: the two readings of E02A-AC2 on the raw
streams, a disputed criterion, counted runs that stay counted and give no percentage,
a refused reuse of the baseline, and the summaries of the current pages.

Every check reads files from this repository and objects of its clone. No test
starts a run, contacts a cluster, or reads the desired state of the working tree.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from tools import comparison_eligibility as eligibility
from tools.analysis_replay import History
from tools.analysis_replay.__main__ import history
from tools.comparison_eligibility import (
    ADJUDICATED_PATH,
    ADJUDICATION_PATH,
    BASELINE_RECORD,
    CONSUMERS,
    CURRENT_PAGES,
    CURRENT_TARGET_RECORD,
    ELIGIBLE,
    NOT_DECIDED,
    NOT_ELIGIBLE,
    RECORD_PATH,
    REPO_ROOT,
    SCANNED_PAGES,
    TARGET_RECORD,
    EligibilityRefused,
    Episode,
    Interval,
    Reading,
    RunFacts,
    basis_of,
    build_adjudicated_record,
    check_adjudicated,
    check_committed,
    check_executing_commits,
    check_surfaces,
    decide,
    judge_episode,
    judge_interval,
    judge_reading,
    reading_of,
    record_text,
    stale_statements,
    usable_baseline,
)
from tools.comparison_eligibility import core as module
from tools.comparison_eligibility.core import instant_ms
from tools.reliability_analysis import AGGREGATE_METRICS, RunResult

pytestmark = pytest.mark.docs

AC2_LIMIT_MS = 10_000
REGISTRY = "docs/proof/experiments/registry.v1alpha1.json"
FAULT = "2026-10-31T13:41:35.149Z"
LATER = "2026-10-31T13:42:05.876Z"
EARLIER = "2026-10-31T13:41:30.000Z"
FIRST_READING = "2026-10-31T13:41:35.531Z"
BOUND_MS = 817


def episode(start: str = LATER, *, is_open: bool = False) -> Episode:
    return Episode(
        start=start, open=is_open, ms=None if is_open else 4276, failed_requests=2
    )


def interval(
    first: str = FIRST_READING, outer: str | None = EARLIER, outer_ms: int = 26813
) -> Interval:
    return Interval(
        first_reading=first, outer_start=outer, inner_ms=17342, outer_ms=outer_ms
    )


def run(
    number: int = 1,
    state: str = "PASSED",
    *,
    episodes: Sequence[Episode] = (),
    intervals: Sequence[Interval] = (),
    bound: int | None = BOUND_MS,
    fault: str | None = FAULT,
) -> RunFacts:
    return RunFacts(
        run_id=f"e02a-{number}",
        state=state,
        fault_started=fault,
        clock_bound_ms=bound,
        episodes=tuple(episodes),
        intervals=tuple(intervals),
    )


def showing(count: int, **shown: Any) -> list[RunFacts]:
    """Three counted runs, of which the first ``count`` show the given figures."""
    return [run(n + 1, **(shown if n < count else {})) for n in range(3)]


# --------------------------------------------------------------------------
# The rule, on sets that the real runs do not reach
# --------------------------------------------------------------------------


@pytest.mark.parametrize("count", [2, 3])
def test_a_failure_episode_in_two_or_three_runs_makes_the_set_eligible(
    count: int,
) -> None:
    decided = decide(showing(count, episodes=[episode()]))
    assert decided["verdict"] == ELIGIBLE
    assert decided["restsOn"] == ["failureEpisode"]
    assert decided["conditions"]["failureEpisode"] == {
        "runsShowing": count,
        "runsNotJudged": 0,
        "held": True,
    }


def test_an_open_episode_counts_as_the_rule_states() -> None:
    assert decide(showing(2, episodes=[episode(is_open=True)]))["verdict"] == ELIGIBLE


def test_an_unexpectedly_resilient_baseline_is_not_eligible() -> None:
    """Three valid runs with no failure stay valid evidence, and the verdict says so."""
    decided = decide(showing(0))
    assert decided["verdict"] == NOT_ELIGIBLE
    assert decided["restsOn"] == []
    assert (
        "not reproducing a caller-visible single-runtime failure"
        in decided["statement"]
    )
    assert "narrowed to topology and endpoints" in decided["statement"]
    assert "No improvement percentage" in decided["statement"]


def test_one_run_in_three_is_not_enough() -> None:
    assert decide(showing(1, episodes=[episode()]))["verdict"] == NOT_ELIGIBLE


def test_an_episode_before_the_fault_does_not_count() -> None:
    decided = decide(showing(3, episodes=[episode(EARLIER)]))
    assert decided["conditions"]["failureEpisode"]["runsShowing"] == 0
    assert decided["verdict"] == NOT_ELIGIBLE


@pytest.mark.parametrize(
    ("start", "order"),
    [
        ("2026-10-31T13:41:35.967Z", "not-judged"),  # 818 ms after: the margin itself
        ("2026-10-31T13:41:35.968Z", "after"),  # 819 ms after
        ("2026-10-31T13:41:34.331Z", "not-judged"),  # 818 ms before
        ("2026-10-31T13:41:34.330Z", "before"),  # 819 ms before
    ],
)
def test_the_start_of_an_episode_is_ordered_outside_the_margin_alone(
    start: str, order: str
) -> None:
    assert judge_episode(episode(start), run()) == order


INSIDE_MARGIN = "2026-10-31T13:41:35.500Z"


def test_a_start_inside_the_margin_is_not_a_negative_result() -> None:
    """A figure that is not judged is neither held nor failed."""
    decided = decide(showing(3, episodes=[episode(INSIDE_MARGIN)]))
    assert decided["verdict"] == NOT_DECIDED
    assert decided["conditions"]["failureEpisode"] == {
        "runsShowing": 0,
        "runsNotJudged": 3,
        "held": False,
    }


def test_one_run_shown_and_one_not_judged_could_reach_two() -> None:
    facts = [
        run(1, episodes=[episode()]),
        run(2, episodes=[episode(INSIDE_MARGIN)]),
        run(3),
    ]
    assert decide(facts)["verdict"] == NOT_DECIDED


def test_one_run_not_judged_cannot_reach_two() -> None:
    facts = [run(1, episodes=[episode(INSIDE_MARGIN)]), run(2), run(3)]
    assert decide(facts)["verdict"] == NOT_ELIGIBLE


def test_no_clock_bound_decides_nothing() -> None:
    decided = decide(showing(3, episodes=[episode()], bound=None))
    assert decided["verdict"] == NOT_DECIDED
    assert decided["conditions"]["failureEpisode"]["runsShowing"] == 0
    assert decided["conditions"]["failureEpisode"]["runsNotJudged"] == 3


def test_no_fault_event_decides_nothing() -> None:
    assert (
        decide(showing(3, episodes=[episode()], fault=None))["verdict"] == NOT_DECIDED
    )
    assert (
        decide(showing(3, intervals=[interval()], fault=None))["verdict"] == NOT_DECIDED
    )


def test_a_later_episode_of_a_run_counts() -> None:
    both = [episode(EARLIER), episode()]
    decided = decide(showing(2, episodes=both))
    assert decided["verdict"] == ELIGIBLE
    assert decided["conditions"]["failureEpisode"]["runsShowing"] == 2


def test_a_later_interval_of_a_run_counts() -> None:
    both = [interval(outer=EARLIER), interval(outer=FIRST_READING)]
    decided = decide(showing(2, intervals=both))
    assert decided["restsOn"] == ["zeroReadyInterval.onTheOuterStart"]
    assert (
        decided["conditions"]["zeroReadyInterval"]["onTheOuterStart"]["runsShowing"]
        == 2
    )


def test_an_episode_after_one_inside_the_margin_shows_the_run() -> None:
    decided = decide(showing(2, episodes=[episode(INSIDE_MARGIN), episode()]))
    assert decided["verdict"] == ELIGIBLE
    assert decided["conditions"]["failureEpisode"]["runsNotJudged"] == 0


def test_no_fault_event_judges_nothing() -> None:
    facts = run(fault=None, episodes=[episode()], intervals=[interval()])
    assert judge_episode(facts.episodes[0], facts) == "not-judged"
    assert judge_interval(facts.intervals[0], facts) == {
        "firstReadingAfterFault": False,
        "outerStartAfterFault": False,
    }


def test_an_interval_with_an_outer_start_after_the_fault_makes_the_set_eligible() -> (
    None
):
    decided = decide(showing(2, intervals=[interval(outer=FIRST_READING)]))
    assert decided["verdict"] == ELIGIBLE
    assert decided["restsOn"] == ["zeroReadyInterval.onTheOuterStart"]


def test_an_interval_on_the_first_reading_alone_is_not_decided() -> None:
    """The record does not state this reading, so it cannot make a set eligible."""
    decided = decide(showing(3, intervals=[interval()]))
    assert decided["verdict"] == NOT_DECIDED
    assert decided["restsOn"] == []
    zero = decided["conditions"]["zeroReadyInterval"]
    assert zero["onTheFirstReading"] == {"runsShowing": 3, "held": True}
    assert zero["onTheOuterStart"] == {"runsShowing": 0, "held": False}


def test_an_interval_with_no_read_before_it_has_no_outer_start() -> None:
    reading = judge_interval(interval(outer=None), run())
    assert reading == {"firstReadingAfterFault": True, "outerStartAfterFault": False}


def test_an_interval_with_an_outer_figure_of_zero_is_on_neither_reading() -> None:
    reading = judge_interval(interval(outer=FIRST_READING, outer_ms=0), run())
    assert reading == {"firstReadingAfterFault": False, "outerStartAfterFault": False}


def test_a_set_with_fewer_than_three_counted_runs_is_not_decided() -> None:
    facts = [
        run(1, episodes=[episode()]),
        run(2, episodes=[episode()]),
        run(3, "INCONCLUSIVE", episodes=[episode()]),
    ]
    decided = decide(facts)
    assert decided["verdict"] == NOT_DECIDED
    assert decided["conditions"]["countedRuns"] == 2
    assert decided["conditions"]["failureEpisode"]["held"] is False


def test_no_condition_is_held_on_fewer_than_three_counted_runs() -> None:
    shown: dict[str, Any] = {
        "episodes": [episode()],
        "intervals": [interval(outer=FIRST_READING)],
    }
    facts = [run(1, **shown), run(2, **shown), run(3, "ABORTED", **shown)]
    conditions = decide(facts)["conditions"]
    assert conditions["failureEpisode"]["held"] is False
    assert conditions["zeroReadyInterval"]["onTheFirstReading"]["held"] is False
    assert conditions["zeroReadyInterval"]["onTheOuterStart"]["held"] is False


def test_a_run_that_is_not_counted_is_not_read() -> None:
    facts = [
        run(1, "ABORTED", episodes=[episode()]),
        run(2, "REFUSED", episodes=[episode()]),
        run(3, episodes=[episode()]),
        run(4),
        run(5),
    ]
    decided = decide(facts)
    assert decided["conditions"]["failureEpisode"]["runsShowing"] == 1
    assert decided["verdict"] == NOT_ELIGIBLE


def test_a_failed_run_is_counted() -> None:
    assert (
        decide(showing(2, state="FAILED", episodes=[episode()]))["verdict"] == ELIGIBLE
    )


def test_a_fourth_counted_run_is_refused() -> None:
    with pytest.raises(EligibilityRefused, match="eligibility-too-many"):
        decide([run(number) for number in range(1, 5)])


@pytest.mark.parametrize("text", ["2026-10-31T13:41:35Z", "soon", None, 12])
def test_an_instant_of_another_form_is_refused(text: object) -> None:
    with pytest.raises(EligibilityRefused, match="eligibility-instant"):
        module.instant_ms(text)


# --------------------------------------------------------------------------
# No percentage is invented
# --------------------------------------------------------------------------


def test_a_zero_baseline_gives_no_percentage() -> None:
    figure = basis_of("requests-failed-since-fault", 0, ELIGIBLE)
    assert figure["basis"] == "zero"
    assert figure["percentageOverThisBasisPossible"] is False
    assert figure["statement"] == "No percentage is computed over a zero baseline."


def test_a_median_that_is_not_stated_gives_no_percentage() -> None:
    figure = basis_of("requests-failed-since-fault", None, ELIGIBLE)
    assert figure["basis"] == "no-value"
    assert figure["median"] is None
    assert figure["percentageOverThisBasisPossible"] is False


@pytest.mark.parametrize("verdict", [NOT_ELIGIBLE, NOT_DECIDED])
def test_a_set_that_is_not_eligible_gives_no_percentage(verdict: str) -> None:
    figure = basis_of("caller-failure-episode-ms", 4065, verdict)
    assert figure["basis"] == "positive"
    assert figure["percentageOverThisBasisPossible"] is False


def test_only_an_eligible_set_with_a_positive_median_can_give_one() -> None:
    figure = basis_of("caller-failure-episode-ms", 4065, ELIGIBLE)
    assert figure["percentageOverThisBasisPossible"] is True


# --------------------------------------------------------------------------
# The inputs
# --------------------------------------------------------------------------


def records() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        json.loads((REPO_ROOT / BASELINE_RECORD).read_text(encoding="utf-8")),
        json.loads((REPO_ROOT / TARGET_RECORD).read_text(encoding="utf-8")),
    )


def test_the_module_states_the_rule_of_revision_4_word_for_word() -> None:
    baseline, target = records()
    module._hold_rules(baseline, target)
    assert baseline["definition"]["setRules"][:2] == [
        module.ELIGIBILITY_RULE,
        module.NOT_ELIGIBLE_RULE,
    ]


@pytest.mark.parametrize(
    "change",
    [
        lambda b, _: b["definition"]["setRules"].__setitem__(
            0, b["definition"]["setRules"][0].replace("at least 2", "at least 1")
        ),
        lambda b, _: b["definition"]["setRules"].__setitem__(1, "Nothing."),
        lambda b, _: b["definition"].__setitem__(
            "repetitionRule",
            b["definition"]["repetitionRule"].replace("At most 6", "At most 9"),
        ),
        lambda _, t: t["definition"].__setitem__("setRules", []),
    ],
)
def test_a_record_with_another_rule_is_refused(
    change: Callable[[dict[str, Any], dict[str, Any]], None],
) -> None:
    baseline, target = records()
    change(baseline, target)
    with pytest.raises(EligibilityRefused, match="eligibility-record"):
        module._hold_rules(baseline, target)


def layout(root: Path, *names: str) -> None:
    for name in names:
        (root / module.RUNS_DIRECTORY / name).mkdir(parents=True)


def test_a_missing_identifier_is_refused(tmp_path: Path) -> None:
    """A gap is a start that the proof tree does not hold."""
    layout(tmp_path, "e02a-1", "e02a-3")
    with pytest.raises(EligibilityRefused, match="eligibility-run-set"):
        module._run_directories(tmp_path)


def test_a_set_that_does_not_start_at_one_is_refused(tmp_path: Path) -> None:
    layout(tmp_path, "e02a-2", "e02a-3")
    with pytest.raises(EligibilityRefused, match="eligibility-run-set"):
        module._run_directories(tmp_path)


def test_an_entry_that_is_not_a_run_is_refused(tmp_path: Path) -> None:
    layout(tmp_path, "e02a-1", "notes")
    with pytest.raises(EligibilityRefused, match="eligibility-run-set"):
        module._run_directories(tmp_path)


def test_no_run_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(EligibilityRefused, match="eligibility-run-set"):
        module._run_directories(tmp_path)


def test_the_runs_are_read_in_the_order_of_their_numbers(tmp_path: Path) -> None:
    layout(tmp_path, *(f"e02a-{number}" for number in (2, 1, 3, 4, 5, 6)))
    names = [path.name for path in module._run_directories(tmp_path)]
    assert names == [f"e02a-{number}" for number in range(1, 7)]


def test_a_seventh_start_is_refused(tmp_path: Path) -> None:
    """The repetition rule allows six starts under one revision."""
    layout(tmp_path, *(f"e02a-{number}" for number in range(1, 8)))
    with pytest.raises(EligibilityRefused, match="more than 6 runs"):
        module._run_directories(tmp_path)


def analysis_document() -> dict[str, Any]:
    """The members that the rule reads, as a run analysis states them."""
    return {
        "runId": "e02a-1",
        "fault": {"notBefore": FAULT},
        "caller": {
            "failureEpisodes": {
                "episodes": [
                    {
                        "start": {"finishedAt": LATER},
                        "open": False,
                        "ms": 4276,
                        "failedRequests": 2,
                    }
                ]
            }
        },
        "zeroReadyEndpoints": {
            "tiers": {
                "serving-runtime": {
                    "intervals": [
                        {
                            "firstReading": {"startedAt": FIRST_READING},
                            "boundedBefore": {"startedAt": EARLIER},
                            "innerMs": 17342,
                            "outerMs": 26813,
                        }
                    ]
                }
            }
        },
    }


def test_a_run_document_gives_the_figures_of_the_rule(tmp_path: Path) -> None:
    facts = module._facts(tmp_path, "PASSED", analysis_document())
    assert facts.fault_started == FAULT
    assert facts.clock_bound_ms is None, "this directory holds no environment.txt"
    assert facts.episodes == (Episode(LATER, False, 4276, 2),)
    assert facts.intervals == (interval(),)


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["fault"].update(notBefore=None),
        lambda d: d["fault"].pop("notBefore"),
        lambda d: d["caller"]["failureEpisodes"]["episodes"][0]["start"].update(
            finishedAt=None
        ),
        lambda d: d["caller"]["failureEpisodes"]["episodes"][0].update(
            failedRequests="2"
        ),
        lambda d: d["zeroReadyEndpoints"]["tiers"]["serving-runtime"]["intervals"][
            0
        ].update(firstReading={"startedAt": None}),
        lambda d: d["zeroReadyEndpoints"]["tiers"]["serving-runtime"]["intervals"][
            0
        ].update(outerMs=None),
        lambda d: d["zeroReadyEndpoints"]["tiers"].pop("serving-runtime"),
    ],
)
def test_a_run_document_with_an_unusable_member_is_refused(
    tmp_path: Path, change: Callable[[dict[str, Any]], Any]
) -> None:
    document = analysis_document()
    change(document)
    with pytest.raises(EligibilityRefused, match=r"eligibility-(document|instant)"):
        module._facts(tmp_path, "PASSED", document)


def test_a_run_that_two_rules_count_differently_is_refused() -> None:
    results = {
        "e02a-1": RunResult(state="PASSED"),
        "e02a-2": RunResult(state="REFUSED"),
    }
    module._hold_counted(
        results, {"e02a-1": {"counted": True}, "e02a-2": {"counted": False}}
    )
    with pytest.raises(EligibilityRefused, match="counted by one rule"):
        module._hold_counted(
            results, {"e02a-1": {"counted": True}, "e02a-2": {"counted": True}}
        )


def test_a_correction_of_another_manifest_is_refused(tmp_path: Path) -> None:
    directory = tmp_path / module.CORRECTIONS_DIRECTORY / "e02a-1"
    directory.mkdir(parents=True)
    (directory / "correction-1.v1alpha1.json").write_text(
        json.dumps({"runId": "e02a-1", "manifestSha256": "b" * 64}), encoding="utf-8"
    )
    with pytest.raises(EligibilityRefused, match="eligibility-run"):
        module._corrections(tmp_path, "e02a-1", "a" * 64)


def test_a_freeze_record_with_another_digest_is_refused(tmp_path: Path) -> None:
    for ref in (BASELINE_RECORD, module.REGISTRY_RECORD):
        path = tmp_path / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((REPO_ROOT / ref).read_bytes())
    path = tmp_path / BASELINE_RECORD
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(EligibilityRefused, match="eligibility-record"):
        module._registered(tmp_path, BASELINE_RECORD)


def test_an_absent_freeze_record_is_refused(tmp_path: Path) -> None:
    with pytest.raises(EligibilityRefused, match="eligibility-record"):
        module._registered(tmp_path, BASELINE_RECORD)


def test_a_clock_bound_that_is_absent_or_repeated_is_no_bound(tmp_path: Path) -> None:
    assert module._clock_bound(tmp_path) is None
    file = tmp_path / "environment.txt"
    file.write_text("no reading\n", encoding="utf-8")
    assert module._clock_bound(tmp_path) is None
    file.write_text("clock bound: 1 ms\nclock bound: 2 ms\n", encoding="utf-8")
    assert module._clock_bound(tmp_path) is None
    file.write_text("clock bound: 817 ms\r\n", encoding="utf-8")
    assert module._clock_bound(tmp_path) == 817


def test_a_missing_committed_record_is_a_finding(tmp_path: Path) -> None:
    assert check_committed(tmp_path) == [f"{RECORD_PATH} is absent"]


# --------------------------------------------------------------------------
# The committed record
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def committed() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(
        (REPO_ROOT / RECORD_PATH).read_text(encoding="utf-8")
    )
    return loaded


def test_each_attempted_run_is_listed_with_its_state(committed: dict[str, Any]) -> None:
    rows = [
        (row["runId"], row["state"], row["exclusion"]) for row in committed["attempts"]
    ]
    assert rows == [
        ("e02a-1", "PASSED", None),
        ("e02a-2", "PASSED", None),
        ("e02a-3", "PASSED", None),
    ]
    assert committed["set"] == {
        "runsStarted": 3,
        "startLimit": 6,
        "countedRuns": 3,
        "requiredCountedRuns": 3,
    }


def test_each_run_stays_bound_to_its_executing_commit_and_revision_4(
    committed: dict[str, Any],
) -> None:
    for row in committed["attempts"]:
        assert row["executingRevision"] == "ff45093b2a9bf2cdbcde5fee453fbc6b64f2e53b"
        assert row["runAnalysis"]["revision"] == row["executingRevision"]
        assert row["freezeRecord"]["freezeRecord"] == BASELINE_RECORD
        assert row["freezeRecord"]["freezeRevision"] == 4
        assert row["corrections"], "each run has its correction"


def test_the_verdict_rests_on_the_failure_episodes(committed: dict[str, Any]) -> None:
    decided = committed["eligibility"]
    assert decided["verdict"] == ELIGIBLE
    assert decided["restsOn"] == ["failureEpisode"]
    assert decided["conditions"]["failureEpisode"] == {
        "runsShowing": 3,
        "runsNotJudged": 0,
        "held": True,
    }


def test_the_zero_ready_condition_is_stated_on_both_readings(
    committed: dict[str, Any],
) -> None:
    zero = committed["eligibility"]["conditions"]["zeroReadyInterval"]
    assert zero == {
        "onTheFirstReading": {"runsShowing": 3, "held": True},
        "onTheOuterStart": {"runsShowing": 0, "held": False},
    }
    assert committed["set"]["countedRuns"] == 3


def test_each_episode_starts_outside_the_margin_of_its_run(
    committed: dict[str, Any],
) -> None:
    for row in committed["attempts"]:
        (start,) = row["failureEpisodes"]
        assert start["orderWithFault"] == "after"
        assert start["fromFaultStartedMs"] > row["marginMs"]


def test_the_figures_of_the_later_comparison_are_the_two_medians(
    committed: dict[str, Any],
) -> None:
    figures = committed["comparisonFigures"]
    assert figures["failures"]["metric"] == "requests-failed-since-fault"
    assert figures["episode"]["metric"] == "caller-failure-episode-ms"
    assert (figures["failures"]["median"], figures["episode"]["median"]) == (2, 4065)
    assert committed["statistics"]["medians"]["caller-failure-episode-ms"] == 4065


def test_only_the_registered_metrics_have_a_median(committed: dict[str, Any]) -> None:
    """The aggregate states no zero-Ready figure, so the record states no median of it."""
    assert set(committed["statistics"]["medians"]) == set(AGGREGATE_METRICS)


def test_the_record_states_no_percentage(committed: dict[str, Any]) -> None:
    assert "%" not in record_text(committed)


V1_RECORDS = (
    "docs/proof/serving/v1-s4-006-pr1-recovery-record.v1alpha1.json",
    "docs/proof/environment/v1-s5-001-pr2-recovery-record.v1alpha1.json",
)


@pytest.mark.parametrize("path", V1_RECORDS)
def test_the_record_states_no_timing_of_a_v1_record(
    committed: dict[str, Any], path: str
) -> None:
    timings = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))["timings"]
    figures = [value for value in timings.values() if type(value) is int]
    assert 2832 in figures or 31960 in figures, "the field of the V1 figure moved"
    text = record_text(committed)
    for figure in figures:
        written = f"{figure:,}"
        for form in (str(figure), written):
            assert re.search(rf"(?<![0-9a-f,]){form}(?![0-9a-f,])", text) is None


def test_the_handoff_names_the_last_run_and_both_desired_states(
    committed: dict[str, Any],
) -> None:
    handoff = committed["handoff"]
    assert handoff["lastRun"]["runId"] == "e02a-3"
    assert (
        handoff["lastRun"]["manifestSha256"]
        == committed["attempts"][-1]["manifestSha256"]
    )
    baseline, target = handoff["baselineDesiredState"], handoff["targetDesiredState"]
    assert (baseline["apiReplicas"], baseline["runtimeReplicas"]) == (2, 1)
    assert (target["apiReplicas"], target["runtimeReplicas"]) == (2, 2)
    assert set(baseline["files"]) == set(target["files"])
    assert not set(baseline["files"].values()) & set(target["files"].values())


def test_the_record_states_what_it_does_not_establish(
    committed: dict[str, Any],
) -> None:
    text = " ".join(committed["doesNotEstablish"])
    assert "No run of V2-E02B exists" in text
    assert "does not authorize a run of V2-E02B" in text
    assert "No V1 figure is a value of V2-E02A" in text
    limits = " ".join(committed["limitations"])
    for phrase in (
        "E02A-AC2",
        "availableReplicas",
        "model file",
        "paged",
        "two digests of the wrong kind",
        "in flight",
        "max-success-gap-ms holds it",
        "2 workers",
    ):
        assert phrase in limits


# --------------------------------------------------------------------------
# The executing commits, which the working tree cannot change
# --------------------------------------------------------------------------


class Commits:
    """A clone that gives each path the content that the test names."""

    def __init__(self, content: dict[str, bytes], *, present: bool = True) -> None:
        self.content = content
        self.present = present

    def history(self) -> History:
        return History(
            commit_present=lambda _: self.present,
            blob=lambda _, path: self.content.get(path),
        )


def small_record() -> dict[str, Any]:
    good = eligibility.core.lf_digest(b"content")
    return {
        "attempts": [{"runId": "e02a-1", "executingRevision": "c" * 40}],
        "governingRecord": {"path": "record.json", "contentSha256": good},
        "handoff": {
            "baselineDesiredState": {"path": "tree", "files": {"values.yaml": good}}
        },
    }


def test_a_commit_that_holds_the_baseline_is_accepted() -> None:
    commits = Commits({"record.json": b"content", "tree/values.yaml": b"content"})
    assert check_executing_commits(small_record(), commits.history()) == ([], [])


def test_a_commit_with_another_desired_state_is_a_finding() -> None:
    commits = Commits({"record.json": b"content", "tree/values.yaml": b"other"})
    findings, missing = check_executing_commits(small_record(), commits.history())
    assert missing == []
    assert findings == [f"e02a-1: tree/values.yaml differs at {'c' * 40}"]


def test_a_commit_with_no_record_is_a_finding() -> None:
    commits = Commits({"tree/values.yaml": b"content"})
    findings, _ = check_executing_commits(small_record(), commits.history())
    assert findings == [f"e02a-1: record.json differs at {'c' * 40}"]


def test_a_commit_that_the_clone_does_not_hold_is_stated_and_not_compared() -> None:
    commits = Commits({}, present=False)
    assert check_executing_commits(small_record(), commits.history()) == (
        [],
        ["c" * 40],
    )


def test_the_real_executing_commit_holds_the_baseline(
    committed: dict[str, Any],
) -> None:
    clone = history()
    revision = committed["attempts"][0]["executingRevision"]
    if not clone.commit_present(revision):  # pragma: no cover - a shallow clone
        pytest.skip("this clone does not hold the executing commit")
    assert check_executing_commits(committed, clone) == ([], [])


def test_no_tool_that_a_run_executes_imports_the_package() -> None:
    """The package is outside each material scope, so it moves no pin of a freeze."""
    own = REPO_ROOT / "tools" / "comparison_eligibility"
    for path in (REPO_ROOT / "tools").rglob("*.py"):
        if own not in path.parents:
            assert "comparison_eligibility" not in path.read_text(encoding="utf-8")


def command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.comparison_eligibility", *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_the_check_passes_on_the_committed_record() -> None:
    done = command("--check")
    assert done.returncode == 0, done.stderr
    assert "PASSED" in done.stdout


def test_an_unusable_argument_exits_two() -> None:
    assert command("--unknown").returncode == 2


# --------------------------------------------------------------------------
# The adjudicated record, which states the current verdict
# --------------------------------------------------------------------------

REASON = "No source settles the criterion."
AT = "2026-10-31T13:41:{:02}.000Z"
AT_MS = "2026-10-31T13:41:{:02}.{:03}Z"


def reading(
    second: int,
    *,
    finished: int | None = None,
    answered: bool = True,
    fault: bool = False,
    null_member: bool = False,
    refused: bool = False,
    counts: Sequence[str] = ("serving-runtime.readyReplicas",),
) -> Reading:
    return Reading(
        started_at=AT.format(second),
        finished_at=AT.format(second if finished is None else finished),
        answered=answered,
        no_fault=not fault,
        no_null_member=not null_member,
        no_refused_tier=not refused,
        counts=frozenset(counts),
    )


def has_ready(item: Reading) -> bool:
    return "serving-runtime.readyReplicas" in item.counts


def by_reading_scope(item: Reading) -> bool:
    return item.answered_cleanly


@pytest.fixture(scope="module")
def adjudicated() -> dict[str, Any]:
    text = (REPO_ROOT / ADJUDICATED_PATH).read_text(encoding="utf-8")
    record: dict[str, Any] = json.loads(text)
    return record


def adjudicated_tree(tmp_path: Path) -> Path:
    """A copy of what the adjudicated record reads, with the raw streams."""
    refs = {
        ADJUDICATION_PATH,
        BASELINE_RECORD,
        RECORD_PATH,
        REGISTRY,
        *(ref for _, ref, _ in CONSUMERS),
        *SCANNED_PAGES,
    }
    for ref in refs:
        copied = tmp_path / ref
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes((REPO_ROOT / ref).read_bytes())
    for number in (1, 2, 3):
        directory = f"{module.RUNS_DIRECTORY}/e02a-{number}"
        (tmp_path / directory).mkdir(parents=True)
        for name in ("declaration.json", *(f"{s}.jsonl" for s in module.STREAMS)):
            shutil.copyfile(REPO_ROOT / directory / name, tmp_path / directory / name)
    return tmp_path


def rewrite(root: Path, ref: str, mutate: Callable[[dict[str, Any]], None]) -> None:
    path = root / ref
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_a_reading_that_omits_a_deployment_count_has_no_value_on_the_field_reading() -> (
    None
):
    """An omitted count is missing and not zero, and it opens a gap on one reading."""
    line = {
        "faults": [],
        "read": {
            "state": "answered",
            "startedAt": AT.format(1),
            "finishedAt": AT.format(2),
        },
        "tiers": [
            {
                "tier": "serving-runtime",
                "state": "observed",
                "readyReplicas": {"state": "missing"},
                "replicas": {"state": "reported", "value": 1},
            }
        ],
    }
    parsed = reading_of(line)
    assert parsed.answered_cleanly
    assert "serving-runtime.replicas" in parsed.counts
    assert "serving-runtime.readyReplicas" not in parsed.counts
    assert not has_ready(parsed)


def test_a_count_of_zero_that_a_reading_reports_has_a_value() -> None:
    line = {
        "faults": [],
        "read": {
            "state": "answered",
            "startedAt": AT.format(1),
            "finishedAt": AT.format(2),
        },
        "tiers": [
            {
                "tier": "serving-runtime",
                "state": "observed",
                "readyReplicas": {"state": "reported", "value": 0},
            }
        ],
    }
    assert has_ready(reading_of(line))


def test_the_two_readings_of_the_criterion_give_two_outcomes() -> None:
    """One stream, with the count omitted in the middle: the shape of the real runs."""
    readings = [
        reading(0),
        reading(5, counts=()),
        reading(10, counts=()),
        reading(15, counts=()),
        reading(20),
    ]
    stream = judge_reading(readings, by_reading_scope)
    field = judge_reading(readings, has_ready)
    assert (stream["held"], stream["largestGapStartToStartMs"]) == (True, 5000)
    assert (field["held"], field["largestGapStartToStartMs"]) == (False, 20000)
    assert stream["readingsWithAValue"] == 5
    assert field["readingsWithAValue"] == 2


def test_a_gap_of_exactly_the_limit_holds_and_one_more_does_not() -> None:
    held = judge_reading([reading(0), reading(10)], by_reading_scope)
    assert held["largestGapStartToStartMs"] == AC2_LIMIT_MS
    assert held["held"]
    over = judge_reading([reading(0), reading(11)], by_reading_scope)
    assert not over["held"]


def test_one_millisecond_over_the_limit_does_not_hold() -> None:
    first = Reading(AT.format(0), AT.format(0), True, True, True, True)
    second = Reading(AT_MS.format(10, 1), AT_MS.format(10, 1), True, True, True, True)
    judged = judge_reading([first, second], by_reading_scope)
    assert judged["largestGapStartToStartMs"] == AC2_LIMIT_MS + 1
    assert not judged["held"]


def test_the_limit_reads_the_start_to_start_gap() -> None:
    """The finish to next start gap is under the limit here, and the other is over."""
    judged = judge_reading(
        [reading(0, finished=5), reading(11, finished=12)], by_reading_scope
    )
    assert judged["largestGapStartToStartMs"] == 11_000
    assert judged["largestGapFinishToNextStartMs"] == 6_000
    assert not judged["held"]


def test_one_reading_with_a_value_has_no_gap_and_holds_nothing() -> None:
    judged = judge_reading([reading(0)], by_reading_scope)
    assert judged["firstAndLastHaveAValue"] is True
    assert judged["largestGapStartToStartMs"] is None
    assert judged["held"] is False


def test_readings_out_of_order_are_refused() -> None:
    """A descending stream would otherwise give a negative gap and hold."""
    with pytest.raises(EligibilityRefused, match="not in order of time"):
        judge_reading([reading(40), reading(20), reading(0)], by_reading_scope)


def test_a_reading_that_finished_before_it_started_is_refused() -> None:
    with pytest.raises(EligibilityRefused, match="finished before it started"):
        judge_reading([reading(5, finished=4)], by_reading_scope)


@pytest.mark.parametrize(
    "first_or_last",
    [
        [reading(0, answered=False), reading(5), reading(10)],
        [reading(0), reading(5), reading(10, answered=False)],
    ],
    ids=["first", "last"],
)
def test_the_first_and_the_last_reading_must_each_have_a_value(
    first_or_last: list[Reading],
) -> None:
    judged = judge_reading(first_or_last, by_reading_scope)
    assert judged["firstAndLastHaveAValue"] is False
    assert judged["held"] is False


@pytest.mark.parametrize(
    "shown",
    [
        {"answered": False},
        {"fault": True},
        {"null_member": True},
        {"refused": True},
    ],
    ids=["unanswered", "a-fault", "a-null-member", "a-refused-tier"],
)
def test_each_variant_of_the_reading_scope_takes_a_value_away(
    shown: dict[str, Any],
) -> None:
    assert not reading(0, **shown).answered_cleanly


def line_of(**changed: Any) -> dict[str, Any]:
    """One clean line of a stream, with the given members replaced."""
    line: dict[str, Any] = {
        "faults": [],
        "read": {
            "state": "answered",
            "startedAt": AT.format(1),
            "finishedAt": AT.format(2),
        },
        "tiers": [{"tier": "serving-runtime", "state": "observed"}],
    }
    line.update(changed)
    return line


def test_a_clean_line_of_a_stream_has_a_value() -> None:
    assert reading_of(line_of()).answered_cleanly


@pytest.mark.parametrize(
    "changed",
    [
        {
            "read": {
                "state": "unanswered",
                "startedAt": AT.format(1),
                "finishedAt": AT.format(2),
            }
        },
        {"faults": ["a reason"]},
        {"extra": {"member": None}},
        {"tiers": [{"tier": "serving-runtime", "state": "refused"}]},
    ],
    ids=["unanswered", "a-fault", "a-null-member", "a-refused-tier"],
)
def test_each_variant_is_read_from_the_line_of_a_stream(
    changed: dict[str, Any],
) -> None:
    assert not reading_of(line_of(**changed)).answered_cleanly


def test_a_stream_with_no_reading_in_the_window_holds_nothing() -> None:
    judged = judge_reading([], by_reading_scope)
    assert judged["held"] is False
    assert judged["largestGapStartToStartMs"] is None


def test_a_disputed_criterion_leaves_a_set_that_shows_the_rule_not_decided() -> None:
    """The conditions hold, and the verdict does not follow from them."""
    runs = showing(3, episodes=[episode()])
    assert decide(runs)["verdict"] == ELIGIBLE
    decided = decide(runs, REASON)
    assert decided["verdict"] == NOT_DECIDED
    assert decided["restsOn"] == []
    assert decided["statement"] == REASON
    assert decided["conditions"]["failureEpisode"]["held"] is True


def test_a_disputed_criterion_does_not_become_a_negative_result() -> None:
    assert decide(showing(0))["verdict"] == NOT_ELIGIBLE
    assert decide(showing(0), REASON)["verdict"] == NOT_DECIDED


@pytest.mark.parametrize("reason", ["", "   ", "\n"])
def test_a_blank_reason_is_refused(reason: str) -> None:
    with pytest.raises(EligibilityRefused, match="eligibility-adjudication"):
        decide(showing(3), reason)


def test_counted_runs_of_a_disputed_criterion_give_no_percentage() -> None:
    """A run that stays counted does not carry a percentage with it."""
    figure = basis_of("requests-failed-since-fault", 2, NOT_DECIDED)
    assert figure["basis"] == "positive"
    assert figure["percentageOverThisBasisPossible"] is False
    assert "not decided" in figure["statement"]
    assert "not eligible" not in figure["statement"]


@pytest.mark.parametrize("consumer", ["V2-E02B", "V2-E03", "V2-E06"])
def test_a_disputed_baseline_is_refused_to_each_consumer(consumer: str) -> None:
    with pytest.raises(EligibilityRefused, match="eligibility-disputed") as refused:
        usable_baseline(consumer)
    assert consumer in str(refused.value)
    assert NOT_DECIDED in str(refused.value)


def test_the_guard_reads_the_adjudicated_record_and_not_the_bound_one(
    tmp_path: Path, committed: dict[str, Any]
) -> None:
    """The bound record says eligible, and it gives no way around the refusal."""
    root = adjudicated_tree(tmp_path)
    assert committed["eligibility"]["verdict"] == ELIGIBLE
    with pytest.raises(EligibilityRefused, match="is absent"):
        usable_baseline("V2-E02B", root)
    shutil.copyfile(REPO_ROOT / ADJUDICATED_PATH, root / ADJUDICATED_PATH)
    with pytest.raises(EligibilityRefused, match="eligibility-disputed"):
        usable_baseline("V2-E02B", root)


def test_an_eligible_verdict_gives_the_figures(tmp_path: Path) -> None:
    """The control of the refusal: a later eligible record would give them."""
    root = adjudicated_tree(tmp_path)
    shutil.copyfile(REPO_ROOT / ADJUDICATED_PATH, root / ADJUDICATED_PATH)
    rewrite(root, ADJUDICATED_PATH, lambda d: d["eligibility"].update(verdict=ELIGIBLE))
    figures = usable_baseline("V2-E02B", root)
    assert set(figures) == {"episode", "failures"}


def test_the_record_states_the_decision_for_each_consumer(
    adjudicated: dict[str, Any],
) -> None:
    """The list is what the owner decided. It is not read from the consumer record."""
    rows = {row["experiment"]: row for row in adjudicated["consumers"]}
    assert {name: row["latestRevision"] for name, row in rows.items()} == {
        "V2-E02B": 3,
        "V2-E03": 5,
        "V2-E06": 4,
    }
    assert all(row["consumesRuns"] == [] for row in rows.values())
    assert all("no tool enforces it" in row["statement"] for row in rows.values())
    assert "E02B-AC2 is settled" in rows["V2-E02B"]["statement"]
    for name in ("V2-E03", "V2-E06"):
        assert "next unused registered revision" in rows[name]["statement"]


@pytest.mark.parametrize("experiment", ["v2-e02b", "v2-e03", "v2-e06"])
def test_no_consumer_has_a_run_yet(experiment: str) -> None:
    """A tripwire: a run of a consumer has to state how it treats the three runs."""
    directory = REPO_ROOT / "docs/proof/experiments" / experiment
    assert not (directory / "runs").exists(), f"{experiment} has a run"


def test_the_adjudicated_record_is_what_its_inputs_give() -> None:
    held = (REPO_ROOT / ADJUDICATED_PATH).read_text(encoding="utf-8")
    assert record_text(build_adjudicated_record()) == held.replace("\r\n", "\n")
    assert check_adjudicated() == []


def test_the_verdict_is_the_existing_string_and_states_the_adjudicated_reason(
    adjudicated: dict[str, Any],
) -> None:
    source = json.loads((REPO_ROOT / ADJUDICATION_PATH).read_text(encoding="utf-8"))
    decided = adjudicated["eligibility"]
    assert decided["verdict"] == NOT_DECIDED == "not-decided"
    assert decided["restsOn"] == []
    assert decided["statement"] == source["reason"]
    assert source["ruling"] == "not-settled"
    assert "verdict" not in source
    assert adjudicated["adjudication"]["contentSha256"] == eligibility.core.lf_digest(
        (REPO_ROOT / ADJUDICATION_PATH).read_bytes()
    )


def test_the_record_states_both_readings_of_the_raw_streams(
    adjudicated: dict[str, Any],
) -> None:
    """The figures that the owner saw, computed again from the raw streams."""
    readings = adjudicated["readingsOfTheCriterion"]
    assert readings["runsHoldingTheReadingScope"] == 3
    assert readings["runsHoldingBothRuntimeCounts"] == 0
    assert "no source selects them for E02A-AC2" in readings["statement"]
    assert readings["limitMs"] == AC2_LIMIT_MS
    rows = {row["runId"]: row for row in readings["runs"]}
    expected = {
        "e02a-1": (166, 160, 26304, 25104),
        "e02a-2": (188, 182, 23488, 22417),
        "e02a-3": (178, 172, 23115, 22043),
    }
    for run_id, (window, valued, start_gap, finish_gap) in expected.items():
        row = rows[run_id]
        for field in ("readyReplicas", "availableReplicas"):
            count = row["selectedRuntimeCounts"][f"serving-runtime.{field}"]
            assert count["readingsInWindow"] == window
            assert count["readingsWithAValue"] == valued
            assert count["largestGapStartToStartMs"] == start_gap
            assert count["largestGapFinishToNextStartMs"] == finish_gap
            assert count["held"] is False
        assert row["everyCount"]["readingsWithAValue"] == 0
        assert row["everyCount"]["held"] is False
        assert row["countsReportedInNoReading"] == ["platform-api.unavailableReplicas"]
        assert len(row["countsReportedInEachReading"]) == 12
        for name in (
            "serving-runtime.readyReplicas",
            "serving-runtime.availableReplicas",
            "serving-runtime.unavailableReplicas",
        ):
            assert name not in row["countsReportedInEachReading"]
        assert set(row["readingScope"]["argo"]) == set(row["readingScope"]["pods"])
        assert "noRefusedTier" not in row["readingScope"]["pods"]
        for stream in row["readingScope"].values():
            assert stream["held"] is True
            assert stream["readingsWithAValue"] == stream["readingsInWindow"]
            assert stream["answered"] == stream["readingsInWindow"]
            assert stream["noNullMember"] == stream["readingsInWindow"]
            assert stream.get("noRefusedTier", window_size(stream)) == window_size(
                stream
            )
    assert (
        max(
            stream["largestGapStartToStartMs"]
            for row in rows.values()
            for stream in row["readingScope"].values()
        )
        == 7057
    )


def test_the_record_names_where_revision_4_reads_the_two_counts(
    adjudicated: dict[str, Any],
) -> None:
    """A source that predates the fault names them, and the statement has to say so."""
    freeze = json.loads((REPO_ROOT / BASELINE_RECORD).read_text(encoding="utf-8"))
    definition = freeze["definition"]
    signals = definition["analysisDeclaration"]["signals"]
    assert "runtime-ready-replicas" in {signal["id"] for signal in signals}
    for member in (
        definition["preparation"],
        definition["stablePreFaultWindow"],
        freeze["fields"]["cleanupProcedure"],
    ):
        assert "readyReplicas" in json.dumps(member)
    measurements = json.dumps(definition["measurements"])
    assert "readyReplicas" in measurements
    assert "availableReplicas" in measurements
    statement = adjudicated["readingsOfTheCriterion"]["statement"]
    for phrase in (
        "runtime-ready-replicas",
        "in P6, in the stable window, and in the cleanup",
        "among its measurements",
        "Those uses name no criterion, and the adjudication cites none of them",
        "The review chose those two after the evidence was read",
    ):
        assert phrase in statement


def window_size(stream: dict[str, Any]) -> int:
    size: int = stream["readingsInWindow"]
    return size


def test_each_attempt_stays_counted_and_no_attempt_has_established_validity(
    adjudicated: dict[str, Any], committed: dict[str, Any]
) -> None:
    for row, attempt in zip(
        adjudicated["attempts"], committed["attempts"], strict=True
    ):
        assert row["runId"] == attempt["runId"]
        assert row["counted"] is attempt["counted"] is True
        assert row["state"] == attempt["state"] == "PASSED"
        assert row["validityEstablished"] is False
        assert row["manifestSha256"] == attempt["manifestSha256"]
    assert "does not establish validity" in adjudicated["attemptsStatement"]


def test_the_record_states_its_own_target_and_the_limit_of_that_target(
    adjudicated: dict[str, Any], committed: dict[str, Any]
) -> None:
    target = adjudicated["targetRecord"]
    assert target["path"] == CURRENT_TARGET_RECORD
    assert TARGET_RECORD.endswith("freeze-r2.v1alpha1.json")
    assert target["revision"] == 3
    assert target["boundVerdict"] == ELIGIBLE
    assert "still says eligible until a successor revision" in target["statement"]
    assert committed["handoff"]["targetDesiredState"]["freezeRecord"]["revision"] == 2


def test_the_record_gives_no_percentage_and_states_its_limits(
    adjudicated: dict[str, Any],
) -> None:
    text = record_text(adjudicated)
    assert "%" not in text
    for figure in adjudicated["comparisonFigures"].values():
        assert figure["percentageOverThisBasisPossible"] is False
    limits = " ".join(adjudicated["limitations"])
    for phrase in (
        "not not-eligible",
        "counted: true",
        "post-result choice",
        "still says eligible",
        "next unused registered revision",
        "no before and after statement is permitted",
    ):
        assert phrase in limits
    assert any("is valid" in item for item in adjudicated["doesNotEstablish"])


@pytest.mark.parametrize("path", V1_RECORDS)
def test_the_adjudicated_record_states_no_timing_of_a_v1_record(
    adjudicated: dict[str, Any], path: str
) -> None:
    timings = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))["timings"]
    text = record_text(adjudicated)
    for figure in (value for value in timings.values() if type(value) is int):
        for form in (str(figure), f"{figure:,}"):
            assert re.search(rf"(?<![0-9a-f,]){form}(?![0-9a-f,])", text) is None


def test_the_built_record_needs_only_its_declared_inputs(tmp_path: Path) -> None:
    """The control of each refusal below: the unedited copy gives the same record."""
    root = adjudicated_tree(tmp_path)
    assert build_adjudicated_record(root) == build_adjudicated_record()


@pytest.mark.parametrize(
    ("mutate", "rule"),
    [
        (lambda d: d.update(ruling="settled"), "eligibility-adjudication"),
        (lambda d: d.update(verdict="eligible"), "eligibility-adjudication"),
        (lambda d: d.pop("reason"), "eligibility-adjudication"),
        (lambda d: d.update(reason="   "), "eligibility-adjudication"),
        (lambda d: d.update(reason=3), "eligibility-adjudication"),
        (lambda d: d.update(criterion="E02A-AC3"), "eligibility-adjudication"),
        (lambda d: d.update(schema="another"), "eligibility-adjudication"),
        (lambda d: d.update(experimentId="V2-E02B"), "eligibility-adjudication"),
        (lambda d: d.update(decidedOn=20261102), "eligibility-adjudication"),
        (lambda d: d.update(decidedOn="after the run"), "eligibility-adjudication"),
        (lambda d: d.update(decidedBy=None), "eligibility-adjudication"),
    ],
    ids=[
        "another-ruling",
        "a-verdict",
        "no-reason",
        "a-blank-reason",
        "a-reason-that-is-not-text",
        "another-criterion",
        "another-schema",
        "another-experiment",
        "a-date-that-is-not-text",
        "a-date-that-is-no-date",
        "no-decider",
    ],
)
def test_an_adjudication_input_that_is_not_the_one_ruling_is_refused(
    tmp_path: Path, mutate: Callable[[dict[str, Any]], Any], rule: str
) -> None:
    root = adjudicated_tree(tmp_path)
    rewrite(root, ADJUDICATION_PATH, mutate)
    with pytest.raises(EligibilityRefused, match=rule):
        build_adjudicated_record(root)


def test_no_adjudication_input_is_refused(tmp_path: Path) -> None:
    root = adjudicated_tree(tmp_path)
    (root / ADJUDICATION_PATH).unlink()
    with pytest.raises(EligibilityRefused, match="eligibility-adjudication"):
        build_adjudicated_record(root)


def test_a_classification_record_with_other_bytes_is_refused(tmp_path: Path) -> None:
    """Revision 3 of V2-E02B binds the bytes, so an edit of the old verdict is refused."""
    root = adjudicated_tree(tmp_path)
    path = root / RECORD_PATH
    text = path.read_text(encoding="utf-8")
    assert text.count('"verdict": "eligible"') == 1
    path.write_text(
        text.replace('"verdict": "eligible"', '"verdict": "not-decided"'),
        encoding="utf-8",
    )
    with pytest.raises(EligibilityRefused, match="eligibility-bound"):
        build_adjudicated_record(root)


def test_an_attempt_that_is_not_counted_is_refused(tmp_path: Path) -> None:
    """The record says that each attempt stays counted, so that has to hold."""
    root = adjudicated_tree(tmp_path)
    path = root / RECORD_PATH
    document = json.loads(path.read_text(encoding="utf-8"))
    document["attempts"][0]["counted"] = False
    path.write_text(record_text(document), encoding="utf-8")
    bound = eligibility.core.lf_digest(path.read_bytes())

    def retarget(record: dict[str, Any]) -> None:
        record["definition"]["g3Provenance"]["classification"]["contentSha256"] = bound

    rewrite(root, CURRENT_TARGET_RECORD, retarget)
    registry = json.loads((root / REGISTRY).read_text(encoding="utf-8"))
    for row in registry["records"]:
        if row["path"] == CURRENT_TARGET_RECORD:
            row["contentSha256"] = eligibility.core.lf_digest(
                (root / CURRENT_TARGET_RECORD).read_bytes()
            )
    (root / REGISTRY).write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(EligibilityRefused, match="an attempt of the record"):
        build_adjudicated_record(root)


def test_a_freeze_record_that_states_another_criterion_is_refused() -> None:
    record = {
        "fields": {
            "acceptanceCriteria": [
                {"value": [{"id": module.AC2_ID, "statement": "Another sentence."}]}
            ]
        }
    }
    with pytest.raises(EligibilityRefused, match="eligibility-criterion"):
        module._hold_criterion(record)


@pytest.mark.parametrize(
    "acceptance",
    [
        [],
        [{"value": []}, {"value": ["text"]}],
        {"value": []},
    ],
    ids=["no-part", "a-row-that-is-text", "not-a-list"],
)
def test_a_freeze_record_with_no_usable_criterion_is_refused(
    acceptance: object,
) -> None:
    record = {"fields": {"acceptanceCriteria": acceptance}}
    with pytest.raises(EligibilityRefused, match="eligibility-criterion"):
        module._hold_criterion(record)


def test_a_stream_with_no_reading_is_refused(tmp_path: Path) -> None:
    root = adjudicated_tree(tmp_path)
    path = root / module.RUNS_DIRECTORY / "e02a-2" / "argo.jsonl"
    path.write_text('{"record":"end"}\n', encoding="utf-8")
    with pytest.raises(EligibilityRefused, match="eligibility-stream"):
        build_adjudicated_record(root)


def run_file(root: Path, name: str) -> Path:
    return root / module.RUNS_DIRECTORY / "e02a-1" / name


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("[1]", "no object"),
        ("5", "no object"),
        ('"text"', "no object"),
        ("null", "no object"),
        (json.dumps({"record": "reading", **line_of(tiers={"a": 1})}), "tier"),
        (json.dumps({"record": "reading", **line_of(tiers="text")}), "tier"),
        (json.dumps({"record": "reading", **line_of(tiers=None)}), "tier"),
        (json.dumps({"record": "reading", **line_of(tiers=["text"])}), "tier"),
        (json.dumps({"record": "reading", **line_of(tiers=[{"state": "x"}])}), "tier"),
        (json.dumps({"record": "reading", **line_of(tiers=[{"tier": 1}])}), "tier"),
        (json.dumps({"record": "reading", **line_of(read="text")}), "eligibility"),
        ("not json", "not readable"),
    ],
    ids=[
        "a-list",
        "a-number",
        "a-string",
        "null",
        "tiers-a-mapping",
        "tiers-a-string",
        "tiers-null",
        "a-tier-that-is-text",
        "a-tier-with-no-name",
        "a-tier-name-that-is-no-text",
        "a-read-that-is-text",
        "no-json",
    ],
)
def test_a_malformed_stream_line_is_refused_and_is_a_finding_of_the_check(
    tmp_path: Path, line: str, message: str
) -> None:
    root = adjudicated_tree(tmp_path)
    shutil.copyfile(REPO_ROOT / ADJUDICATED_PATH, root / ADJUDICATED_PATH)
    with run_file(root, "pods.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(f"{line}\n")
    with pytest.raises(EligibilityRefused, match=message):
        build_adjudicated_record(root)
    assert check_adjudicated(root) != []


@pytest.mark.parametrize(
    "window",
    [[1], "text", {"to": AT.format(1)}, {"from": 1, "to": AT.format(1)}, None],
    ids=["a-list", "a-string", "no-from", "a-number", "null"],
)
def test_a_malformed_window_is_refused(tmp_path: Path, window: object) -> None:
    root = adjudicated_tree(tmp_path)
    path = run_file(root, "declaration.json")
    document = json.loads(path.read_text(encoding="utf-8"))
    document["window"] = window
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(EligibilityRefused, match="eligibility"):
        build_adjudicated_record(root)


def bad_instant(text: str) -> str:
    read = {"state": "answered", "startedAt": text, "finishedAt": text}
    return json.dumps({"record": "reading", **line_of(read=read)})


@pytest.mark.parametrize(
    "text",
    [
        "2026-13-31T13:41:01.000Z",
        "2026-02-30T13:41:01.000Z",
        "2026-10-31T25:41:01.000Z",
        "\u0662\u0660\u0662\u0666-10-31T13:41:01.000Z",
    ],
    ids=["month-13", "30-february", "hour-25", "arabic-digits"],
)
def test_an_instant_that_is_not_a_date_is_refused(tmp_path: Path, text: str) -> None:
    with pytest.raises(EligibilityRefused, match="eligibility-instant"):
        instant_ms(text)
    root = adjudicated_tree(tmp_path)
    shutil.copyfile(REPO_ROOT / ADJUDICATED_PATH, root / ADJUDICATED_PATH)
    with run_file(root, "pods.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(f"{bad_instant(text)}\n")
    with pytest.raises(EligibilityRefused, match="eligibility-instant"):
        build_adjudicated_record(root)
    assert check_adjudicated(root) != []


@pytest.mark.parametrize(
    "records",
    [5, ["text"], None],
    ids=["a-number", "a-row-that-is-text", "null"],
)
def test_a_registry_that_is_not_usable_is_refused(
    tmp_path: Path, records: object
) -> None:
    root = adjudicated_tree(tmp_path)
    (root / REGISTRY).write_text(json.dumps({"records": records}), encoding="utf-8")
    with pytest.raises(EligibilityRefused, match="eligibility-record"):
        build_adjudicated_record(root)


def test_a_committed_record_that_is_not_text_is_a_finding(tmp_path: Path) -> None:
    root = adjudicated_tree(tmp_path)
    (root / ADJUDICATED_PATH).write_bytes(b"\xff\xfe not text")
    assert f"{ADJUDICATED_PATH} is not what is built" in check_adjudicated(root)


def test_a_stream_line_nested_too_deeply_is_refused(tmp_path: Path) -> None:
    root = adjudicated_tree(tmp_path)
    with run_file(root, "pods.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("[" * 200_000 + "\n")
    with pytest.raises(EligibilityRefused, match="not readable"):
        build_adjudicated_record(root)


def test_a_null_member_deep_in_a_line_is_found() -> None:
    nested: Any = None
    for _ in range(5_000):
        nested = [nested]
    assert not reading_of(line_of(extra=nested)).no_null_member


def test_a_stream_that_is_absent_is_refused(tmp_path: Path) -> None:
    root = adjudicated_tree(tmp_path)
    (root / module.RUNS_DIRECTORY / "e02a-3" / "pods.jsonl").unlink()
    with pytest.raises(EligibilityRefused, match="eligibility-stream"):
        build_adjudicated_record(root)


@pytest.mark.parametrize(
    "sentence",
    [
        "The baseline is eligible for the comparison.",
        "The set meets the rule.",
        "The set is eligible.",
        "The baseline is `eligible`.",
        "It says that the baseline is eligible.",
        "That the baseline is eligible is what the record states.",
        "We hold That the baseline is eligible.",
        "No source selects them.",
        "No source selects those two counts.",
        "- That the baseline is eligible and every run is valid today.",
        "It is a fact - That the baseline is eligible.",
        "The baseline was **eligible**.",
        "It says that a run is valid.",
        "It states that the run is valid.",
        "The review judged the seven validity criteria, and each held.",
        "It is separate from the authorization of G1.",
        "The change merges into `main` only with the owner's word.",
        "The seven validity criteria hold in each run.",
        "The seven criteria of the record hold.",
        "Each of the seven criteria held.",
        "The state says that a run is valid.",
        "It says that the run is valid.",
        "The baseline\nis eligible.",
    ],
)
def test_a_summary_that_states_the_withdrawn_verdict_is_found(sentence: str) -> None:
    assert stale_statements(sentence)


@pytest.mark.parametrize(
    "sentence",
    [
        "The current eligibility verdict is `not-decided`.",
        "The classification record states the verdict `eligible`, and that is not the current verdict.",
        "No input can make a set eligible.",
        "No source selects them for E02A-AC2.",
        "No source selects them for `E02A-AC2`.",
        "- That the baseline is eligible for an experiment. The result is a statement.",
    ],
)
def test_a_page_may_state_the_current_verdict(sentence: str) -> None:
    assert stale_statements(sentence) == []


def test_each_current_page_states_the_adjudicated_verdict() -> None:
    assert check_surfaces() == []


def test_the_check_reads_each_page_that_states_the_verdict() -> None:
    for page in ("README.md", "docs/proof/README.md"):
        assert page in CURRENT_PAGES
    for page in CURRENT_PAGES:
        assert page in SCANNED_PAGES
    assert "docs/environment/git-desired-state.md" in SCANNED_PAGES
    assert "docs/proof/dashboard.md" in SCANNED_PAGES
    assert "docs/testing/claim-evidence-matrix.md" in SCANNED_PAGES
    assert "docs/environment/single-runtime-baseline-profile.md" in SCANNED_PAGES


@pytest.mark.parametrize(
    "page",
    [
        "README.md",
        "docs/environment/argocd-application.md",
        "docs/environment/capacity-preflight.md",
        "docs/environment/environment-qualification.md",
        "docs/environment/git-desired-state.md",
        "docs/environment/model-cache-storage.md",
        "docs/environment/runtime-model-cache-observation.md",
        "docs/environment/single-runtime-baseline-profile.md",
        "docs/proof/README.md",
        "docs/proof/experiments/README.md",
        "docs/testing/README.md",
        "docs/testing/comparison-eligibility.md",
        "docs/testing/experiment-e02a-control.md",
    ],
)
def test_a_current_page_that_mentions_a_switch_names_each_merge_and_the_deviation(
    page: str,
) -> None:
    """The owner's limit: a statement about a switch names its merge and its deviation."""
    text = (REPO_ROOT / page).read_text(encoding="utf-8")
    for name in ("ff45093", "a3ed812", "v2-s7-004-pr1-switch-deviations.md"):
        assert name in text, name


def test_a_current_page_that_cannot_be_read_is_a_finding(tmp_path: Path) -> None:
    root = adjudicated_tree(tmp_path)
    (root / "README.md").write_bytes(b"\xff\xfe not text")
    assert check_surfaces(root) == ["README.md is not readable"]


def test_a_scanned_page_need_not_name_the_record(tmp_path: Path) -> None:
    """A page that does not state the verdict is read for a stale sentence alone."""
    root = adjudicated_tree(tmp_path)
    page = "docs/environment/git-desired-state.md"
    assert page not in CURRENT_PAGES
    (root / page).write_text("No verdict here.\n", encoding="utf-8")
    assert check_surfaces(root) == []
    (root / page).write_text("The baseline is eligible.\n", encoding="utf-8")
    assert check_surfaces(root) == [f"{page}: baseline is eligible"]


def test_a_current_page_with_a_stale_summary_fails_the_check(tmp_path: Path) -> None:
    root = adjudicated_tree(tmp_path)
    assert check_surfaces(root) == []
    page = "README.md"
    with (root / page).open("a", encoding="utf-8") as stream:
        stream.write("\nThe baseline is eligible.\n")
    assert check_surfaces(root) == [f"{page}: baseline is eligible"]


def test_a_current_page_that_loses_the_record_fails_the_check(tmp_path: Path) -> None:
    root = adjudicated_tree(tmp_path)
    page = "docs/testing/comparison-eligibility.md"
    path = root / page
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("eligibility-adjudicated.v1alpha1.json", "other.json"),
        encoding="utf-8",
    )
    assert check_surfaces(root) == [f"{page} does not name the adjudicated record"]


def test_an_edited_adjudicated_record_fails_the_check(tmp_path: Path) -> None:
    root = adjudicated_tree(tmp_path)
    path = root / ADJUDICATED_PATH
    shutil.copyfile(REPO_ROOT / ADJUDICATED_PATH, path)
    assert check_adjudicated(root) == []
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('"not-decided"', '"eligible"'), encoding="utf-8")
    assert check_adjudicated(root) == [f"{ADJUDICATED_PATH} is not what is built"]


def test_the_command_prints_the_adjudicated_record() -> None:
    done = command("--adjudicated")
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["eligibility"]["verdict"] == NOT_DECIDED


def test_the_two_options_exclude_each_other() -> None:
    assert command("--adjudicated", "--check").returncode == 2
