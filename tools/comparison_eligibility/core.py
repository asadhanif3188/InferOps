"""Classify the V2-E02A runs and apply the comparison eligibility rule.

The record of V2-E02A states the rule in ``definition.setRules``. The aggregate
command states neither figure that the rule reads, so this module reads them from
the run analysis of each run: the start of each failure episode, and each
zero-Ready-endpoint interval of the runtime tier.

**A figure comes from a run analysis that a replay reproduced.** Each run directory
is held to ``tools.analysis_replay`` first, so an edited figure refuses the record.
Each median comes from the aggregate of ``tools.reliability_analysis``, after
``aggregate_runs`` held the whole set, and this module computes none.

**The module is conservative where the record states no reading.** Three cases:

- The clock policy of the record declares no set rule. The start of a failure
  episode is on the node clock and the fault event is on the host clock, so a start
  inside the margin of the policy is not judged, and it does not count.
- The record does not state which instant starts a zero-Ready interval. The module
  states two figures: whether the first reading that gave zero started after the
  event, and whether the outer start of the interval is after it. Only the outer
  start can make a set eligible. A set that the first reading alone would make
  eligible is not decided.
- A set with fewer than three counted runs is not decided.

**A figure that is not judged is neither held nor failed.** A set is ``not-eligible``
only when the rule is shown not to hold. When a run that was not judged could reach
the two runs that the rule asks for, the set is ``not-decided``, so evidence that this
module declined to read does not become a negative result.

**No percentage is computed here, and no record states one.** The figure that a
later comparison reads is stated with its basis: ``positive``, ``zero``, or
``no-value``. A later comparison computes no percentage over a zero or an absent
basis, and none when the set is not eligible.

**The record is a statement about the runs that executed.** It reads no file of the
desired state of the working tree, so a later switch of ``main`` does not change it.
The check of each executing commit reads the objects of the clone.

The module reads files and Git objects. It writes no file, starts no run, and
contacts no cluster. See docs/testing/comparison-eligibility.md.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from tools.analysis_replay import (
    REPLAYED,
    History,
    ReplayRefused,
    aggregate_runs,
    replay_run,
)
from tools.analysis_replay.__main__ import checkout_revision, history
from tools.reliability_analysis import (
    AGGREGATE_METRICS,
    AnalysisRefused,
    RunResult,
    aggregate,
)

__all__ = [
    "BASELINE_RECORD",
    "CORRECTIONS_DIRECTORY",
    "DOES_NOT_ESTABLISH",
    "ELIGIBLE",
    "LIMITATIONS",
    "NOT_DECIDED",
    "NOT_ELIGIBLE",
    "RECORD_PATH",
    "REFUSED_EXIT",
    "REPO_ROOT",
    "RULES",
    "RUNS_DIRECTORY",
    "SCHEMA",
    "TARGET_RECORD",
    "EligibilityRefused",
    "Episode",
    "Interval",
    "RunFacts",
    "basis_of",
    "build_record",
    "check_committed",
    "check_executing_commits",
    "decide",
    "judge_episode",
    "judge_interval",
    "record_text",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

SCHEMA: Final = "inferops.io/comparison-eligibility/v1alpha1"

#: The record that governs each run. These two paths are fixed: a later revision of
#: either experiment does not change what these three runs were held to.
BASELINE_RECORD: Final = "docs/proof/experiments/v2-e02a/freeze-r4.v1alpha1.json"
TARGET_RECORD: Final = "docs/proof/experiments/v2-e02b/freeze-r2.v1alpha1.json"
REGISTRY_RECORD: Final = "docs/proof/experiments/registry.v1alpha1.json"
RUNS_DIRECTORY: Final = "docs/proof/experiments/v2-e02a/runs"
CORRECTIONS_DIRECTORY: Final = "docs/proof/experiments/v2-e02a/corrections"
RECORD_PATH: Final = "docs/proof/experiments/v2-e02a/classification.v1alpha1.json"

#: The two sentences of the rule, word for word, and the phrases of the repetition
#: rule that this module restates as figures. It refuses a record that differs.
ELIGIBILITY_RULE: Final = (
    "Comparison eligibility. The three counted runs of V2-E02A support a quantitative "
    "improvement statement for V2-E02B only when at least 2 of the 3 runs show a "
    "failure episode that starts at or after the fault-injection-started event, open "
    "or closed, or at least 2 of the 3 show a zero-Ready-endpoint interval of the "
    "runtime tier that starts after that event, with an outer figure above 0 ms. Both "
    "are read from the run analysis of each run: the start of each failure episode, "
    "and each interval of zeroReadyEndpoints. The aggregate command states neither "
    "figure."
)
NOT_ELIGIBLE_RULE: Final = (
    "When neither holds, the runs remain valid evidence, the baseline is reported as "
    "not reproducing a caller-visible single-runtime failure strongly enough, and the "
    "V2-E02B claim is narrowed to topology and endpoints. No improvement percentage "
    "is stated."
)
REPETITION_PHRASES: Final = (
    "3 counted runs.",
    "A run is counted when its state is PASSED or FAILED.",
    "At most 6 runs start under one revision.",
)
#: What the record of V2-E02B reads from this baseline, in its own words.
COMPARISON_PHRASES: Final = (
    "B_failures and T_failures are the medians of requests-failed-since-fault",
    "B_episode and T_episode are the medians of caller-failure-episode-ms",
    "No percentage is computed over a zero baseline.",
)

REQUIRED_COUNTED: Final = 3
LEAST_SHOWING: Final = 2
START_LIMIT: Final = 6
COUNTED_STATES: Final = frozenset({"PASSED", "FAILED"})
FAILURES_METRIC: Final = "requests-failed-since-fault"
EPISODE_METRIC: Final = "caller-failure-episode-ms"

#: The coarser resolution of the two sources of each order, in milliseconds. The
#: caller record and the operator event log each state the millisecond.
RESOLUTION_MS: Final = 1

AFTER: Final = "after"
BEFORE: Final = "before"
NOT_JUDGED: Final = "not-judged"

ELIGIBLE: Final = "eligible"
NOT_ELIGIBLE: Final = "not-eligible"
NOT_DECIDED: Final = "not-decided"

REFUSED_EXIT: Final = 5

_INSTANT: Final = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")
_RUN_ID: Final = re.compile(r"e02a-([1-9][0-9]*)")
_CLOCK_BOUND: Final = re.compile(r"^clock bound: ([0-9]+) ms$", re.MULTILINE)

#: Each refusal, by rule.
RULES: Final[Mapping[str, str]] = {
    "eligibility-instant": "An instant is not a UTC instant to the millisecond.",
    "eligibility-too-many": "More than three runs are counted.",
    "eligibility-record": "A freeze record is not the registered one, or differs.",
    "eligibility-run-set": "The run identifiers are not 1 to N, at most 6, with no gap.",
    "eligibility-run": "A run directory does not replay, or it names another record.",
    "eligibility-document": "A run document does not have the member that is read.",
}

LIMITATIONS: Final[tuple[str, ...]] = (
    "Three runs give a median and individual values. This record states no confidence interval and no statistical significance.",
    "The state of each run rests on a reading of E02A-AC2 that the repository owner approved on 2026-10-31, after the evidence was read. The freeze record does not state that reading, and no tool reads the approval. On the readings of the runtime readyReplicas count alone, each run would be INCONCLUSIVE, no run would be counted, and this record would decide nothing. The runtime availableReplicas count has the same gaps. The record does not state which fields a reading has to hold.",
    "The model file of a replacement pod was not compared directly. The procedure read the model verification log of the first runtime pod alone. The evidence for each replacement pod is indirect.",
    "The available physical memory of the host was low in each run, and the host paged. The operator read these figures, and no criterion reads them. This record does not establish whether paging changed a figure of a run.",
    "Each manifest states two digests of the wrong kind: the binding and the contract. The correction of each run states the right values. No check reads either field, and no figure of this record reads them.",
    "The clock policy of revision 4 does not declare the set rules. This record applies the margin of the policy to the start of each failure episode. A start inside the margin does not count.",
    "Revision 4 does not state which instant starts a zero-Ready interval. A reading is at most a few seconds from the next, so the state can change between two readings. This record states the first reading that gave zero and the outer start of the interval. The verdict does not rest on the first reading.",
    "The analysis puts a failure episode at the completion of its first failed request. So the start of an episode is not the time at which the caller was first affected. The failed requests were sent up to about 5 s after the fault, one of them 111 ms before it, and each was in flight for about 26 s to 31 s. No request completed in that time.",
    "caller-failure-episode-ms does not hold that time. It runs from the completion of the first failed request to the next success. max-success-gap-ms holds it, and each run states it. The record of V2-E02B reads the first and not the second.",
    "requests-failed-since-fault is 2 in each run, and the caller profile has 2 workers. This record does not establish that the count can exceed the number of workers, so a later reader does not take the count as a measure of the length of the failure.",
    "This record states no cause of an episode and no cause of an interval.",
    "One provider, one node, one Kubernetes version, one release of each side, one model, and one caller workload. A result is bounded to that execution.",
)

DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "A comparison. No run of V2-E02B exists, and this record states no result of it.",
    "An improvement, a reduction, or a percentage. This record states none.",
    "That the desired state is restored. This record changes no desired state.",
    "An authorization. An eligibility verdict does not authorize a run of V2-E02B, the G3 switch, or a later sprint.",
    "That one runtime replica is or is not acceptable for any service.",
    "Node failure, overload, sustained capacity, or production availability.",
    "The cause of a failure, of a gap, or of a recovery.",
    "Anything about another provider, node, release, or caller workload.",
    "A figure of the V1 pod-loss evidence. No V1 figure is a value of V2-E02A.",
)

_V1_STATEMENT: Final = (
    "The controlled baseline is kept apart from the V1 pod-loss evidence. No V1 figure "
    "is a value of V2-E02A, and this record states no V1 figure. A later comparison "
    "reads the two figures of comparisonFigures and no V1 figure."
)

_HANDOFF_STATEMENTS: Final[tuple[str, ...]] = (
    "The last run of V2-E02A is lastRun. No further run is planned under revision 4: three runs are counted.",
    "Rule G3 of revision 4 restores the two desired-state files to the digests of targetDesiredState, in one change merged into main, before the first V2-E02B run. That change needs the explicit authorization of the repository owner. This record does not give it.",
    "The desired state on main stays at baselineDesiredState until that change merges.",
    "No row of this record changes when main returns to the target. Each run stays bound to its executing commit and to revision 4.",
)


class EligibilityRefused(Exception):
    """A record, a run directory, or a document that this module does not accept."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(f"{rule}: {message}")
        self.rule = rule


@dataclass(frozen=True)
class Episode:
    """One failure episode of a run analysis.

    ``start`` is the completion instant of its first failed request, on the node
    clock.
    """

    start: str
    open: bool
    ms: int | None
    failed_requests: int


@dataclass(frozen=True)
class Interval:
    """One zero-Ready-endpoint interval of the runtime tier.

    ``first_reading`` is the start of the first read that gave zero. ``outer_start``
    is the start of the read before it, which the outer figure measures from, or
    None when no read came before. Both are on the host clock.
    """

    first_reading: str
    outer_start: str | None
    inner_ms: int
    outer_ms: int


@dataclass(frozen=True)
class RunFacts:
    """What the rule reads from one run."""

    run_id: str
    state: str
    fault_started: str | None
    clock_bound_ms: int | None
    episodes: tuple[Episode, ...] = ()
    intervals: tuple[Interval, ...] = ()


def instant_ms(text: object) -> int:
    """A UTC instant to the millisecond, as milliseconds since the epoch."""
    if not isinstance(text, str) or _INSTANT.fullmatch(text) is None:
        raise EligibilityRefused(
            "eligibility-instant", "an instant is not a UTC instant to the millisecond"
        )
    moment = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    return round(moment.timestamp() * 1000)


def judge_episode(episode: Episode, run: RunFacts) -> str:
    """The order of the start of an episode and the fault-injection-started event.

    The two instants are on two clocks. Inside the margin no order is stated. With
    no clock bound, or with no fault event, nothing is judged.
    """
    if run.fault_started is None or run.clock_bound_ms is None:
        return NOT_JUDGED
    margin = run.clock_bound_ms + RESOLUTION_MS
    difference = instant_ms(episode.start) - instant_ms(run.fault_started)
    if difference > margin:
        return AFTER
    return BEFORE if difference < -margin else NOT_JUDGED


def judge_interval(interval: Interval, run: RunFacts) -> dict[str, bool]:
    """Whether an interval starts after the fault event, on each of the two readings.

    Both instants are on the host clock, so they are ordered directly. An interval
    with an outer figure of 0 ms is on neither reading, and neither is an interval
    of a run with no fault event. An interval with no read before it has no outer
    start, so it is not after the event on that reading.
    """
    if run.fault_started is None or interval.outer_ms <= 0:
        return {"firstReadingAfterFault": False, "outerStartAfterFault": False}
    fault = instant_ms(run.fault_started)
    return {
        "firstReadingAfterFault": instant_ms(interval.first_reading) > fault,
        "outerStartAfterFault": interval.outer_start is not None
        and instant_ms(interval.outer_start) > fault,
    }


def _shows_episode(run: RunFacts) -> bool:
    return any(judge_episode(episode, run) == AFTER for episode in run.episodes)


def _not_judged(run: RunFacts) -> bool:
    """Whether a run that shows no failure episode has a figure that was not judged.

    A start inside the margin, a run with no clock bound, and a run with no fault
    event each leave a figure with no stated order.
    """
    if _shows_episode(run):
        return False
    return any(
        judge_episode(episode, run) == NOT_JUDGED for episode in run.episodes
    ) or (run.fault_started is None and bool(run.intervals))


def decide(runs: Sequence[RunFacts]) -> dict[str, Any]:
    """Apply the rule to one set of runs.

    Only a counted run is read. A set that has more than three counted runs is
    refused, and one that has fewer is not decided. A run that was not judged can
    keep a set from being decided, and it does not make a set not eligible.

    Raises:
        EligibilityRefused: more than three runs are counted.
    """
    counted = [run for run in runs if run.state in COUNTED_STATES]
    if len(counted) > REQUIRED_COUNTED:
        raise EligibilityRefused(
            "eligibility-too-many", f"{len(counted)} runs are counted"
        )
    episodes = sum(_shows_episode(run) for run in counted)
    not_judged = sum(_not_judged(run) for run in counted)
    readings = [
        [judge_interval(interval, run) for interval in run.intervals] for run in counted
    ]
    first = sum(any(r["firstReadingAfterFault"] for r in row) for row in readings)
    outer = sum(any(r["outerStartAfterFault"] for r in row) for row in readings)
    complete = len(counted) == REQUIRED_COUNTED
    conditions: dict[str, Any] = {
        "countedRuns": len(counted),
        "leastRunsShowing": LEAST_SHOWING,
        "failureEpisode": {
            "runsShowing": episodes,
            "runsNotJudged": not_judged,
            "held": complete and episodes >= LEAST_SHOWING,
        },
        "zeroReadyInterval": {
            "onTheFirstReading": {
                "runsShowing": first,
                "held": complete and first >= LEAST_SHOWING,
            },
            "onTheOuterStart": {
                "runsShowing": outer,
                "held": complete and outer >= LEAST_SHOWING,
            },
        },
    }
    if not complete:
        verdict, rests_on, statement = (
            NOT_DECIDED,
            [],
            f"The set has {len(counted)} counted runs, and the rule reads three.",
        )
    elif conditions["failureEpisode"]["held"]:
        verdict, rests_on, statement = (
            ELIGIBLE,
            ["failureEpisode"],
            f"{episodes} of the 3 counted runs show a failure episode that starts after the fault-injection-started event, by more than the margin. The rule asks for 2.",
        )
    elif outer >= LEAST_SHOWING:
        verdict, rests_on, statement = (
            ELIGIBLE,
            ["zeroReadyInterval.onTheOuterStart"],
            f"{outer} of the 3 counted runs show a zero-Ready interval of the runtime tier whose outer start is after the fault-injection-started event. The rule asks for 2.",
        )
    elif first >= LEAST_SHOWING:
        verdict, rests_on, statement = (
            NOT_DECIDED,
            [],
            "The zero-Ready condition holds on the first reading alone. The record does not state that reading, so a person decides it.",
        )
    elif episodes + not_judged >= LEAST_SHOWING:
        verdict, rests_on, statement = (
            NOT_DECIDED,
            [],
            f"{not_judged} of the 3 counted runs have a figure that was not judged, and it could reach the 2 runs that the rule asks for. A figure that is not judged is neither held nor failed.",
        )
    else:
        verdict, rests_on, statement = NOT_ELIGIBLE, [], NOT_ELIGIBLE_RULE
    return {
        "verdict": verdict,
        "restsOn": rests_on,
        "conditions": conditions,
        "statement": statement,
    }


def basis_of(metric: str, median: int | None, verdict: str) -> dict[str, Any]:
    """The figure that a later comparison reads, with its basis.

    A percentage needs an eligible set and a basis above zero. A median that is zero
    or that the aggregate does not state gives none, and this function invents none.
    """
    if median is None:
        basis, statement = (
            "no-value",
            "The aggregate states no median, so the improvement is not computed.",
        )
    elif median == 0:
        basis, statement = "zero", "No percentage is computed over a zero baseline."
    elif verdict != ELIGIBLE:
        basis, statement = (
            "positive",
            "The set is not eligible, so no improvement percentage is stated.",
        )
    else:
        basis, statement = "positive", "The median is above zero."
    return {
        "metric": metric,
        "median": median,
        "basis": basis,
        "percentageOverThisBasisPossible": basis == "positive" and verdict == ELIGIBLE,
        "statement": statement,
    }


def lf_digest(data: bytes) -> str:
    """The SHA-256 of the bytes with every CRLF replaced by LF."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _dig(document: object, *path: str) -> Any:
    for name in path:
        if not isinstance(document, dict) or name not in document:
            raise EligibilityRefused(
                "eligibility-document", f"no member {'.'.join(path)}"
            )
        document = document[name]
    return document


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise EligibilityRefused(
            "eligibility-document", f"{path.name} is not readable"
        ) from error


def _registered(root: Path, ref: str) -> tuple[dict[str, Any], str]:
    """A freeze record, held to the digest that the registry pins for it."""
    path = root / ref
    if not path.is_file():
        raise EligibilityRefused("eligibility-record", f"{ref} is absent")
    digest = lf_digest(path.read_bytes())
    rows = _dig(_json(root / REGISTRY_RECORD), "records")
    pinned = [row.get("contentSha256") for row in rows if row.get("path") == ref]
    if pinned != [digest]:
        raise EligibilityRefused(
            "eligibility-record", f"{ref} does not have its registered digest"
        )
    return _json(path), digest


def _topology(record: Mapping[str, Any]) -> dict[str, Any]:
    (row,) = _dig(record, "fields", "topology")
    value: dict[str, Any] = _dig(row, "value")
    return value


def _hold_rules(baseline: Mapping[str, Any], target: Mapping[str, Any]) -> None:
    rules = _dig(baseline, "definition", "setRules")
    if ELIGIBILITY_RULE not in rules or NOT_ELIGIBLE_RULE not in rules:
        raise EligibilityRefused(
            "eligibility-record", "the record does not state the rule of this module"
        )
    repetition = _dig(baseline, "definition", "repetitionRule")
    if not all(phrase in repetition for phrase in REPETITION_PHRASES):
        raise EligibilityRefused(
            "eligibility-record", "the record does not state the repetition rule"
        )
    comparison = " ".join(_dig(target, "definition", "setRules"))
    if not all(phrase in comparison for phrase in COMPARISON_PHRASES):
        raise EligibilityRefused(
            "eligibility-record", "the target record reads other figures"
        )


def _run_directories(root: Path) -> list[Path]:
    """The run directories, in order, with no identifier missing.

    The driver spends one identifier for each start, so a gap is a run that the
    proof tree does not hold.
    """
    runs = root / RUNS_DIRECTORY
    found: dict[int, Path] = {}
    for path in runs.iterdir() if runs.is_dir() else ():
        match = _RUN_ID.fullmatch(path.name)
        if match is None or not path.is_dir():
            raise EligibilityRefused("eligibility-run-set", "an entry is not a run")
        found[int(match.group(1))] = path
    if not found or sorted(found) != list(range(1, len(found) + 1)):
        raise EligibilityRefused("eligibility-run-set", "an identifier is missing")
    if len(found) > START_LIMIT:
        raise EligibilityRefused(
            "eligibility-run-set", f"more than {START_LIMIT} runs started"
        )
    return [found[number] for number in sorted(found)]


def _corrections(root: Path, run_id: str, manifest_sha256: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted((root / CORRECTIONS_DIRECTORY / run_id).glob("correction-*")):
        correction = _json(path)
        if (
            correction.get("runId") != run_id
            or correction.get("manifestSha256") != manifest_sha256
        ):
            raise EligibilityRefused(
                "eligibility-run", f"{path.name} does not name {run_id}"
            )
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": lf_digest(path.read_bytes()),
            }
        )
    return rows


def _clock_bound(run_dir: Path) -> int | None:
    try:
        text = (run_dir / "environment.txt").read_text(encoding="utf-8")
    except OSError:
        return None
    bounds = _CLOCK_BOUND.findall(text.replace("\r\n", "\n"))
    return int(bounds[0]) if len(bounds) == 1 else None


def _instant(document: object, *path: str) -> str:
    """An instant of a run document, refused unless it is a UTC instant."""
    text: str = _dig(document, *path)
    instant_ms(text)
    return text


def _whole(document: object, *path: str) -> int:
    """A count of a run document, refused unless it is a whole number."""
    value = _dig(document, *path)
    if type(value) is not int:
        raise EligibilityRefused(
            "eligibility-document", f"{'.'.join(path)} is not a whole number"
        )
    return value


def _facts(run_dir: Path, state: str, analysis: Mapping[str, Any]) -> RunFacts:
    """The figures that the rule reads, from one reproduced run analysis.

    A run analysis with no fault instant is refused here: it has no event to
    order an episode with, and a counted run has one.
    """
    fault = _instant(analysis, "fault", "notBefore")
    episodes = tuple(
        Episode(
            start=_instant(episode, "start", "finishedAt"),
            open=_dig(episode, "open"),
            ms=_dig(episode, "ms"),
            failed_requests=_whole(episode, "failedRequests"),
        )
        for episode in _dig(analysis, "caller", "failureEpisodes", "episodes")
    )
    tier = _dig(analysis, "zeroReadyEndpoints", "tiers", "serving-runtime")
    intervals = tuple(
        Interval(
            first_reading=_instant(interval, "firstReading", "startedAt"),
            outer_start=None
            if interval.get("boundedBefore") is None
            else _instant(interval, "boundedBefore", "startedAt"),
            inner_ms=_whole(interval, "innerMs"),
            outer_ms=_whole(interval, "outerMs"),
        )
        for interval in _dig(tier, "intervals")
    )
    return RunFacts(
        run_id=_dig(analysis, "runId"),
        state=state,
        fault_started=fault,
        clock_bound_ms=_clock_bound(run_dir),
        episodes=episodes,
        intervals=intervals,
    )


def _episode_row(episode: Episode, run: RunFacts) -> dict[str, Any]:
    assert run.fault_started is not None
    return {
        "startedAt": episode.start,
        "open": episode.open,
        "ms": episode.ms,
        "failedRequests": episode.failed_requests,
        "fromFaultStartedMs": instant_ms(episode.start) - instant_ms(run.fault_started),
        "orderWithFault": judge_episode(episode, run),
    }


def _interval_row(interval: Interval, run: RunFacts) -> dict[str, Any]:
    return {
        "firstReadingStartedAt": interval.first_reading,
        "outerStartedAt": interval.outer_start,
        "innerMs": interval.inner_ms,
        "outerMs": interval.outer_ms,
        **judge_interval(interval, run),
    }


def _analysis(run_dir: Path, root: Path) -> Mapping[str, Any]:
    """The analysis of one run, after a replay reproduced its run analysis."""
    replay = replay_run(run_dir, root)
    if replay.status != REPLAYED or len(replay.analyses) != 1:
        raise EligibilityRefused(
            "eligibility-run", f"{run_dir.name} has no reproduced run analysis"
        )
    analysis: Mapping[str, Any] = _dig(replay.analyses[0].document, "analysis")
    return analysis


def _attempt(
    run_dir: Path,
    root: Path,
    analysis: Mapping[str, Any],
    row: Mapping[str, Any],
    figures: Mapping[str, Any],
) -> dict[str, Any]:
    facts = _facts(run_dir, row["state"], analysis)
    if facts.run_id != run_dir.name:
        raise EligibilityRefused(
            "eligibility-run", f"{run_dir.name} states another run identifier"
        )
    margin = None if facts.clock_bound_ms is None else facts.clock_bound_ms + 1
    return {
        "runId": facts.run_id,
        "directory": row["directory"],
        "state": facts.state,
        "counted": row["counted"],
        "exclusion": row["exclusion"],
        "executingRevision": row["executingRevision"],
        "freezeRecord": row["freezeRecord"],
        "manifestSha256": row["manifestSha256"],
        "rawEvidenceSha256": row["rawEvidenceSha256"],
        "runAnalysis": row["runAnalysis"],
        "corrections": _corrections(root, facts.run_id, row["manifestSha256"]),
        "startedAt": row["startedAt"],
        "finishedAt": row["finishedAt"],
        "faultStartedAt": facts.fault_started,
        "clockBoundMs": facts.clock_bound_ms,
        "marginMs": margin,
        "failureEpisodes": [_episode_row(e, facts) for e in facts.episodes],
        "runtimeZeroReadyIntervals": [_interval_row(i, facts) for i in facts.intervals],
        "figures": dict(figures),
    }


def _runs_of(
    root: Path,
    directories: Sequence[Path],
    revision: str,
    baseline: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Each attempted run, and the median of each registered metric.

    ``aggregate_runs`` holds the whole set once: the layout, the replay, and that no
    run of the experiment is left out. Each metric then reads the analyses that a
    replay reproduced, so a run is replayed twice and not once for each metric.
    """
    whole = aggregate_runs(FAILURES_METRIC, directories, revision, root, history(root))
    rows = {row["runId"]: row for row in whole["runs"]}
    manifests = {path.name: _json(path / "run.v1alpha1.json") for path in directories}
    analyses = {path.name: _analysis(path, root) for path in directories}
    results: dict[str, RunResult] = {}
    for run_id, manifest in manifests.items():
        spec = _dig(manifest, "metadata", "spec")
        if spec.get("freezeRecord") != BASELINE_RECORD:
            raise EligibilityRefused(
                "eligibility-run", f"{run_id} names another record"
            )
        results[run_id] = RunResult(
            state=_dig(manifest, "result", "state"),
            reason=_dig(manifest, "result").get("reason"),
            exclusion_reasons=_dig(baseline, "exclusionReasons"),
            preregistration=spec,
        )
    pairs = [(analyses[path.name], results[path.name]) for path in directories]
    try:
        aggregates = {
            metric: aggregate(metric, pairs) for metric in sorted(AGGREGATE_METRICS)
        }
    except AnalysisRefused as refused:
        raise EligibilityRefused("eligibility-run", str(refused)) from refused
    values = {
        metric: {row["runId"]: row for row in document["runs"]}
        for metric, document in aggregates.items()
    }
    for run_id, result in results.items():
        if values[FAILURES_METRIC][run_id]["counted"] != (
            result.state in COUNTED_STATES
        ):
            raise EligibilityRefused(
                "eligibility-run", f"{run_id} is counted by one rule and not another"
            )
    attempts = []
    for run_dir in directories:
        run_id = run_dir.name
        row = rows[run_id]
        listed = values[FAILURES_METRIC][run_id]
        metadata = _dig(manifests[run_id], "metadata")
        attempts.append(
            _attempt(
                run_dir,
                root,
                analyses[run_id],
                {
                    "directory": row["runDirectory"],
                    "state": results[run_id].state,
                    "counted": listed["counted"],
                    "exclusion": listed["exclusion"],
                    "executingRevision": row["executingRevision"],
                    "freezeRecord": dict(_dig(metadata, "spec")),
                    "manifestSha256": row["manifestSha256"],
                    "rawEvidenceSha256": row["rawEvidenceSha256"],
                    "runAnalysis": {
                        name: row["runAnalysis"][name]
                        for name in ("path", "sha256", "revision", "sourceSha256")
                    },
                    "startedAt": _dig(metadata, "startedAt"),
                    "finishedAt": _dig(metadata, "finishedAt"),
                },
                {metric: values[metric][run_id]["value"] for metric in values},
            )
        )
    return attempts, {
        "rule": "median-of-three",
        "medians": {
            metric: document["median"] for metric, document in aggregates.items()
        },
        "notAggregated": "The zero-Ready intervals. The aggregate command does not state them, so each run states its own.",
        "statement": aggregates[FAILURES_METRIC]["statement"],
    }


def _desired_state(record: Mapping[str, Any], ref: str, digest: str) -> dict[str, Any]:
    topology = _topology(record)
    release = _dig(topology, "release")
    return {
        "freezeRecord": {
            "path": ref,
            "revision": _dig(record, "metadata", "revision"),
            "contentSha256": digest,
        },
        "path": _dig(topology, "desiredStatePath"),
        "apiReplicas": _dig(topology, "apiReplicas"),
        "runtimeReplicas": _dig(topology, "runtimeReplicas"),
        "releaseId": _dig(release, "releaseId"),
        "files": dict(_dig(release, "desiredStateFiles")),
    }


def _handoff(
    attempts: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    baseline_sha256: str,
    target: Mapping[str, Any],
    target_sha256: str,
) -> dict[str, Any]:
    last = attempts[-1]
    return {
        "lastRun": {
            name: last[name]
            for name in (
                "runId",
                "state",
                "finishedAt",
                "executingRevision",
                "manifestSha256",
                "rawEvidenceSha256",
                "runAnalysis",
            )
        },
        "baselineDesiredState": _desired_state(
            baseline, BASELINE_RECORD, baseline_sha256
        ),
        "targetDesiredState": _desired_state(target, TARGET_RECORD, target_sha256),
        "statements": list(_HANDOFF_STATEMENTS),
    }


def build_record(root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build the classification record from the files of ``root``.

    Raises:
        EligibilityRefused: a rule of :data:`RULES` is not held.
        ReplayRefused: the replay refused a run directory.
    """
    baseline, baseline_sha256 = _registered(root, BASELINE_RECORD)
    target, target_sha256 = _registered(root, TARGET_RECORD)
    _hold_rules(baseline, target)
    directories = _run_directories(root)
    attempts, statistics = _runs_of(
        root, directories, checkout_revision(root), baseline
    )
    decided = decide(
        [
            RunFacts(
                run_id=row["runId"],
                state=row["state"],
                fault_started=row["faultStartedAt"],
                clock_bound_ms=row["clockBoundMs"],
                episodes=tuple(
                    Episode(e["startedAt"], e["open"], e["ms"], e["failedRequests"])
                    for e in row["failureEpisodes"]
                ),
                intervals=tuple(
                    Interval(
                        i["firstReadingStartedAt"],
                        i["outerStartedAt"],
                        i["innerMs"],
                        i["outerMs"],
                    )
                    for i in row["runtimeZeroReadyIntervals"]
                ),
            )
            for row in attempts
        ]
    )
    medians = statistics["medians"]
    verdict = decided["verdict"]
    return {
        "schema": SCHEMA,
        "experimentId": "V2-E02A",
        "governingRecord": {
            "path": BASELINE_RECORD,
            "revision": _dig(baseline, "metadata", "revision"),
            "contentSha256": baseline_sha256,
        },
        "set": {
            "runsStarted": len(attempts),
            "startLimit": START_LIMIT,
            "countedRuns": decided["conditions"]["countedRuns"],
            "requiredCountedRuns": REQUIRED_COUNTED,
        },
        "evidenceLevel": "C2",
        "attempts": attempts,
        "statistics": statistics,
        "eligibility": decided,
        "comparisonFigures": {
            "failures": basis_of(FAILURES_METRIC, medians[FAILURES_METRIC], verdict),
            "episode": basis_of(EPISODE_METRIC, medians[EPISODE_METRIC], verdict),
        },
        "v1Evidence": _V1_STATEMENT,
        "handoff": _handoff(attempts, baseline, baseline_sha256, target, target_sha256),
        "limitations": list(LIMITATIONS),
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def record_text(record: Mapping[str, Any]) -> str:
    """The canonical text of a record."""
    return json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def check_committed(root: Path = REPO_ROOT) -> list[str]:
    """Build the record again and compare it with the committed file."""
    path = root / RECORD_PATH
    if not path.is_file():
        return [f"{RECORD_PATH} is absent"]
    try:
        built = record_text(build_record(root))
    except (EligibilityRefused, ReplayRefused) as refused:
        return [str(refused)]
    held = path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
    return [] if held == built else [f"{RECORD_PATH} is not what the runs give"]


def check_executing_commits(
    record: Mapping[str, Any], history: History
) -> tuple[list[str], list[str]]:
    """Hold each run to the desired state and the record of its executing commit.

    The objects of the clone are read. The working tree is not, so this check holds
    after ``main`` leaves the baseline. It returns the findings, and each commit
    that the clone does not hold: a shallow clone holds none of them.
    """
    findings: list[str] = []
    missing: list[str] = []
    desired = _dig(record, "handoff", "baselineDesiredState")
    governing = _dig(record, "governingRecord")
    for attempt in _dig(record, "attempts"):
        run_id, revision = attempt["runId"], attempt["executingRevision"]
        if not history.commit_present(revision):
            missing.append(revision)
            continue
        expected = {governing["path"]: governing["contentSha256"]}
        for name, digest in desired["files"].items():
            expected[f"{desired['path']}/{name}"] = digest
        for path, digest in expected.items():
            held = history.blob(revision, path)
            if held is None or lf_digest(held) != digest:
                findings.append(f"{run_id}: {path} differs at {revision}")
    return findings, sorted(set(missing))
