"""The classification of the V2-E02A runs, held to the rule of revision 4.

The first part applies ``decide`` and ``basis_of`` to synthetic sets. They hold the
cases that the three real runs do not reach: a set that shows no failure, a set with
a zero baseline, and a set with too few counted runs. The real set is eligible with
two figures above zero, so only these tests reach the case with no percentage.

The second part reads the committed record and the committed runs. It holds that the
record is what the runs give, that each run is listed, and that the record states no
percentage and no V1 figure.

Every check reads files from this repository and objects of its clone. No test
starts a run, contacts a cluster, or reads the desired state of the working tree.
"""

from __future__ import annotations

import json
import re
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
    BASELINE_RECORD,
    ELIGIBLE,
    NOT_DECIDED,
    NOT_ELIGIBLE,
    RECORD_PATH,
    REPO_ROOT,
    TARGET_RECORD,
    EligibilityRefused,
    Episode,
    Interval,
    RunFacts,
    basis_of,
    check_committed,
    check_executing_commits,
    decide,
    judge_episode,
    judge_interval,
    record_text,
)
from tools.comparison_eligibility import core as module
from tools.reliability_analysis import AGGREGATE_METRICS

pytestmark = pytest.mark.docs

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
