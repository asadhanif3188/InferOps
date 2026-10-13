"""The reliability metrics of one experiment run, computed from its stored evidence.

The inputs are files that other tools define and check: the caller record of
the reliability runner, the four timeline streams, and the log of operator
events. A seventh input is the declaration: the observation window, the
expected state, and the signals. This module registers no threshold of a
signal and no expected count. An experiment declares them.

The module computes six metrics. It also states the first caller impact and
the fault that the log records, and a second function gives one figure of
several documents.

*Caller failure episodes.* An episode is a run of failed completed requests
with no successful completed request between them. It starts at the completion
of its first failed request and ends at the completion of the next successful
request. An episode with no such request in the window is open and has no
duration.

*The maximum success gap.* The largest time between two consecutive successful
completions in the window.

*Zero-Ready-endpoint intervals.* The readings of the endpoints stream in which
a Service has no Ready endpoint, as intervals with two durations.

*The detection lag of a signal.* The time from the first caller impact to the
first reading in which the signal states the declared problem.

*The false-healthy and the false-unavailable time of a signal.* The time in
which the caller fails and the signal states healthy, and the time in which
the caller succeeds and the signal states the problem.

*Stabilized recovery.* The first instant at which ten consecutive successful
completions span sixty seconds and each reading of the expected state in that
span holds.

**A caller instant is stated to one millisecond, and a reading is a
sample.** A stream states a
value at a read and states nothing between two reads. So each duration of a
sampled state is two figures. The inner figure is the time between
consecutive reads that both gave the state, and it does not cross a reading
with no value. The outer figure is the time between the nearest reads on each
side that gave another state. No figure says what the value was between two
reads.

**A value that was not read is not a value.** A reading that did not answer, a
count that the reading does not report, and a stream that was not given each
are not read as zero or as a healthy state. A metric that cannot be computed
states a reason, and the document lists each metric with no value.

**The module computes figures. It decides no result.** It states no result
state, no verdict against a bound, no availability percentage, and no
confidence interval.

See docs/testing/reliability-analysis.md and
tests/domain/test_reliability_analysis.py.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import Any, Final

from tools.experiment_events import Log, LogRefused, read_log
from tools.experiment_run import RESULT_STATES
from tools.experiment_timeline import (
    ANSWERED,
    ARGO,
    DEPLOYMENTS,
    ENDPOINTS,
    PODS,
    REPORTED,
    Stream,
    StreamRefused,
    collector_instant,
    format_instant,
    read_stream,
)
from tools.reliability_runner import CallerRecord, RunnerError, read_record
from tools.service_endpoint_state import TIER_OBSERVED, TIERS

__all__ = [
    "AGGREGATE_METRICS",
    "AGGREGATE_RULE",
    "AGGREGATE_SCHEMA",
    "AGGREGATE_STATEMENT",
    "COMPLETION_ORDER",
    "COMPUTED",
    "DECLARATION_SCHEMA",
    "DOES_NOT_ESTABLISH",
    "EVENTS",
    "EXCLUDED_STATES",
    "HEALTHY",
    "INPUTS",
    "LIMITATIONS",
    "MAX_EXCLUSION_REASONS",
    "MAX_SIGNALS",
    "NOT_COMPUTABLE",
    "NOT_OBSERVED",
    "PROBLEM",
    "REASONS",
    "REFUSED_EXIT",
    "REVISION_PRESENT",
    "RULES",
    "SCHEMA",
    "SIGNAL_SOURCES",
    "STABILIZATION_SPAN_MS",
    "STABILIZATION_SUCCESSES",
    "STREAM_INPUTS",
    "SYNCED",
    "AnalysisRefused",
    "RunResult",
    "aggregate",
    "analysis_text",
    "analyze",
    "read_declaration",
]

#: The schema name of an analysis document.
SCHEMA: Final = "inferops.io/reliability-analysis/v1alpha1"

#: The schema name of a declaration.
DECLARATION_SCHEMA: Final = "inferops.io/reliability-analysis-declaration/v1alpha1"

#: The schema name of an aggregate document.
AGGREGATE_SCHEMA: Final = "inferops.io/reliability-aggregate/v1alpha2"

#: The exit status of a command that refused an input.
REFUSED_EXIT: Final = 3

#: The name of the operator events input.
EVENTS: Final = "operator-events"

#: The timeline streams that the analysis reads, by the name of the input.
STREAM_INPUTS: Final = (ENDPOINTS, PODS, DEPLOYMENTS, ARGO)

#: Each input, in the order of the document. The caller record is required.
INPUTS: Final = ("caller", *STREAM_INPUTS, EVENTS)

#: The two states of a metric.
COMPUTED: Final = "computed"
NOT_COMPUTABLE: Final = "not-computable"

#: The three states of a signal at one reading.
HEALTHY: Final = "healthy"
PROBLEM: Final = "problem"
NOT_OBSERVED: Final = "not-observed"

#: The number of consecutive successful completions of a stabilization span.
STABILIZATION_SUCCESSES: Final = 10

#: The least time between the first and the last completion of that span.
STABILIZATION_SPAN_MS: Final = 60_000

#: The sync status with which the delivery controller states that the live state
#: is the state of the revision that it resolved.
SYNCED: Final = "Synced"

#: How two completions with one completion instant are ordered.
COMPLETION_ORDER: Final = (
    "Completed requests are ordered by finishedAt. Two requests with one "
    "finishedAt are ordered by the position of their lines in the record."
)

#: How the analysis reads that the expected revision is present.
REVISION_PRESENT: Final = (
    "A reading of the argo stream holds the expected revision when it reports "
    "a resolvedRevision that is the declared commit and a syncStatus of Synced."
)

#: The most signals that one declaration states.
MAX_SIGNALS: Final = 16

#: The largest count that a declaration states.
_MAX_COUNT: Final = 64

_COUNT_SOURCE: Final = "count"
_VALUE_SOURCE: Final = "value"

#: Each source of a signal: the stream, the form of its declaration, and what
#: the analysis reads. A source of a telemetry stream is not registered.
SIGNAL_SOURCES: Final[Mapping[str, tuple[str, str, str]]] = {
    "endpoints-ready": (
        ENDPOINTS,
        _COUNT_SOURCE,
        "The number of Ready endpoints of the Service of one tier.",
    ),
    "pods-ready": (
        PODS,
        _COUNT_SOURCE,
        "The number of listed pods of one tier whose Ready condition is True.",
    ),
    "deployment-ready-replicas": (
        DEPLOYMENTS,
        _COUNT_SOURCE,
        "The readyReplicas count of the Deployment of one tier.",
    ),
    "deployment-available-replicas": (
        DEPLOYMENTS,
        _COUNT_SOURCE,
        "The availableReplicas count of the Deployment of one tier.",
    ),
    "application-sync-status": (
        ARGO,
        _VALUE_SOURCE,
        "The syncStatus that the delivery controller reported.",
    ),
    "application-health-status": (
        ARGO,
        _VALUE_SOURCE,
        "The healthStatus that the delivery controller reported.",
    ),
}

_APPLICATION_FIELD: Final[Mapping[str, str]] = {
    "application-sync-status": "syncStatus",
    "application-health-status": "healthStatus",
}

_DEPLOYMENT_FIELD: Final[Mapping[str, str]] = {
    "deployment-ready-replicas": "readyReplicas",
    "deployment-available-replicas": "availableReplicas",
}

#: Why a metric has no value.
REASONS: Final[Mapping[str, str]] = {
    "caller-record-does-not-cover-window": (
        "The caller record starts after the window starts, or it ends before "
        "the window ends. The record says nothing about the rest of the window."
    ),
    "no-completion-in-window": (
        "No request completes inside the window. A window with no completion is "
        "not a window with no failure."
    ),
    "episode-open": (
        "A failure episode has no successful completion after it inside the "
        "window, so it has no duration."
    ),
    "episode-starts-before-window": (
        "The last completion before the window is a failed one, so the window "
        "starts inside a failure episode whose start it does not hold."
    ),
    "fewer-than-two-successes": (
        "The window holds fewer than two successful completions, so it holds no "
        "gap between two."
    ),
    "no-count-in-window": (
        "No reading in the window states a Ready endpoint count for the tier."
    ),
    "stream-not-given": "A stream that the metric reads was not given.",
    "no-reading-in-window": "No reading of the stream is inside the window.",
    "readings-out-of-order": (
        "A reading starts before the reading before it finishes. The stream has "
        "no usable order."
    ),
    "signal-never-observed": (
        "No reading in the window states a value for the signal."
    ),
    "caller-not-computable": (
        "The caller metrics have no value, and the metric reads them."
    ),
    "fault-ambiguous": (
        "The log does not hold one fault-injection-started event and one "
        "fault-injection-finished event after it with the same code."
    ),
    "no-caller-impact": (
        "No request failed in the window at or after the fault, so no first "
        "caller impact exists."
    ),
    "never-indicated": (
        "No reading in the window at or after the search start states the "
        "declared problem."
    ),
    "indicated-before-search-start": (
        "The signal already stated the declared problem at the reading before "
        "its first reading at or after the search start, so no first indication "
        "is inside the search."
    ),
    "not-three-counted-runs": (
        "The aggregate does not count three runs, and no rule is registered for "
        "another number."
    ),
    "counted-run-without-value": (
        "A counted run has no value for the figure. The run is not dropped."
    ),
}

RULE_DECLARATION_UNREADABLE: Final = "analysis-declaration-unreadable"
RULE_DECLARATION: Final = "analysis-declaration-unsupported"
RULE_WINDOW: Final = "analysis-window-invalid"
RULE_SIGNAL: Final = "analysis-signal-unsupported"
RULE_INPUT: Final = "analysis-input-refused"
RULE_INPUT_NAME: Final = "analysis-input-misnamed"
RULE_IDENTITY: Final = "analysis-identity-differs"
RULE_AGGREGATE: Final = "analysis-aggregate-unsupported"
RULE_EXCLUSION_REASONS: Final = "analysis-exclusion-reasons-unsupported"
RULE_EXCLUSION: Final = "analysis-exclusion-unregistered"

#: The most exclusion reasons that one freeze record states.
MAX_EXCLUSION_REASONS: Final = 32

#: Each rule that refuses an input, with its statement.
RULES: Final[Mapping[str, str]] = {
    RULE_DECLARATION_UNREADABLE: (
        "A declaration is one JSON object with no member stated twice."
    ),
    RULE_DECLARATION: (
        "A declaration has exactly its members, its schema name, two "
        "identifiers, and an expected state in its form."
    ),
    RULE_WINDOW: (
        "The window states two instants in UTC to one millisecond, and it ends "
        "after it starts. Each recorded abort is after the window starts."
    ),
    RULE_SIGNAL: (
        "Each signal has its own identifier, a registered source, and the "
        "members of that source in their form. A declaration states at most "
        f"{MAX_SIGNALS} signals."
    ),
    RULE_INPUT: (
        "Each input is accepted by the reader of the tool that defines it. The "
        "analysis names the input and the rule of that tool."
    ),
    RULE_INPUT_NAME: "A stream is given under the name that its header states.",
    RULE_IDENTITY: ("The declaration and each input name one experiment and one run."),
    RULE_AGGREGATE: (
        "An aggregate is asked for a registered metric of analysis documents of "
        "one experiment, each of another run, each with a registered result "
        "state."
    ),
    RULE_EXCLUSION_REASONS: (
        "The exclusion reasons of a freeze record are one object with exactly an "
        "experiment identifier and a list of reasons. Each reason has its own "
        "identifier, one of the result states INCONCLUSIVE, REFUSED, and ABORTED, "
        "a reason as text, and, when it is for named runs alone, their run "
        "identifiers. No result state has one reason text twice. A record states "
        f"at most {MAX_EXCLUSION_REASONS} reasons."
    ),
    RULE_EXCLUSION: (
        "A run in the state INCONCLUSIVE, REFUSED, or ABORTED states a reason that "
        "the freeze record of its manifest registers, character for character, "
        "for the experiment, the result state, and the run."
    ),
}

#: The limits of an analysis document. The document states each one.
LIMITATIONS: Final[tuple[str, ...]] = (
    "A caller instant is on the clock of the runner's pod. A reading is on the "
    "clock of the collecting host. An event is on the clock of the recording "
    "host. The difference between the clocks is not measured. Each figure that "
    "compares a caller instant with a reading or an event holds that difference.",
    "A request is counted at its completion. A request that fails after a long "
    "time is counted at the end of that time. The first caller impact is the "
    "completion of the first failed request, and the request started earlier.",
    "A failure episode ends at the first successful completion after it, from "
    "any worker. With two workers, a request that was sent before the failure "
    "can end the episode.",
    "A stream states a value at a read and states nothing between two reads. "
    "The inner figure of an interval holds no change that no read gave. The "
    "outer figure holds each read on both sides. Neither is the exact time.",
    "The stabilization rule needs one reading of each condition inside the "
    "span, and it sets no limit for the time between two readings. A span can "
    "hold a long time with no reading. The document states the longest such "
    "time for each condition.",
    "With no stated fault the search for the first caller impact and for the "
    "stabilized recovery starts at the start of the window. A recovery that is "
    "found then can be a state that no fault disturbed.",
    "A reading whose value was not read is not healthy and is not a problem. "
    "A Deployment count that the API omitted is such a value, and the API "
    "omits a count of zero. So a signal of a Deployment count has no value in "
    "a reading in which the count is zero.",
    "The analysis reads the instant at which the tool recorded an event. It "
    "does not read the second instant that an event can state for another "
    "clock.",
    "The declaration is an input. The analysis does not hold a threshold, an "
    "expected count, or a window to a frozen record of an experiment.",
    "The document does not state the digest of an input, and it does not state "
    "the revision of the code that computed it.",
    "No signal is read from a telemetry stream.",
)

#: What an analysis document does not establish. The document states each one.
DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "The result state of a run. No figure here is compared with a bound.",
    "An availability percentage, an error rate, a percentile, a confidence "
    "interval, or a statistical significance.",
    "A production SLO. The stabilization rule is a definition for an experiment.",
    "The cause of a failure, of a gap, or of a recovery.",
    "An order of two instants from two clocks that are less than one second apart.",
    "That a signal detects a problem in another run, on another topology, or "
    "in another environment.",
    "That the inputs are the evidence of a real run. The analysis reads the "
    "files that it is given.",
)

#: The one registered rule of an aggregate.
AGGREGATE_RULE: Final = "median-of-three"

#: The result states whose runs an aggregate does not count. A run in one of
#: them is left out of the median only for a reason that its exclusion
#: reasons register, and the aggregate states that reason.
EXCLUDED_STATES: Final = ("INCONCLUSIVE", "REFUSED", "ABORTED")

#: What each aggregate document states about itself.
AGGREGATE_STATEMENT: Final = (
    "The median of three runs is the one aggregate. Three observations do not "
    "support a confidence interval or a statistical significance, and the "
    "document states neither. Each run is listed with its own value."
)

#: The figures that an aggregate can be asked for, with the path of each in an
#: analysis document.
AGGREGATE_METRICS: Final[Mapping[str, tuple[str, ...]]] = {
    "caller-failure-episode-ms": (
        "caller",
        "failureEpisodes",
        "callerFailureEpisodeMs",
    ),
    "max-success-gap-ms": ("caller", "maxSuccessGap", "ms"),
    "requests-failed-in-window": ("caller", "requests", "failed"),
    "requests-failed-since-fault": (
        "stabilizedRecovery",
        "requestsFailedSinceFault",
    ),
    "stabilized-since-fault-started-ms": (
        "stabilizedRecovery",
        "sinceFault",
        "fromFaultStartedMs",
    ),
}

_DECLARATION_MEMBERS: Final = frozenset(
    {"schema", "experimentId", "runId", "window", "expected", "signals"}
)
_WINDOW_MEMBERS: Final = frozenset({"from", "to"})
_EXCLUSION_MEMBERS: Final = frozenset({"experimentId", "reasons"})
_REASON_MEMBERS: Final = frozenset({"id", "resultState", "reason"})
_REASON_RUNS: Final = "runIds"
#: The longest statement that a run manifest holds.
_MAX_REASON_LENGTH: Final = 2000
_EXPECTED_MEMBERS: Final = frozenset(
    {"desiredRevision", "readyReplicas", "runtimeReadyEndpoints"}
)
_IDENTIFIER: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,62}")
_SIGNAL_ID: Final = re.compile(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?")
_STATUS_WORD: Final = re.compile(r"[A-Za-z]{1,32}")
_COMMIT_FORM: Final = re.compile(r"[0-9a-f]{40}")
_RUNTIME_TIER: Final = "serving-runtime"
_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)
_MILLISECOND: Final = timedelta(milliseconds=1)

_ZERO: Final = "zero"
_NON_ZERO: Final = "non-zero"
_HELD: Final = "held"
_NOT_HELD: Final = "not-held"


class AnalysisRefused(Exception):
    """An input that the analysis does not read."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(f"{rule}: {message}")
        self.rule = rule
        self.message = message


class _Repeated(ValueError):
    """One JSON object states one member twice."""


def _no_repeat(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for name, value in pairs:
        if name in document:
            raise _Repeated(name)
        document[name] = value
    return document


# --------------------------------------------------------------------------
# Instants and intervals
# --------------------------------------------------------------------------


def _ms(value: object) -> int | None:
    """An instant in the one stored form, as milliseconds, or None."""
    instant = collector_instant(value)
    if instant is None:
        return None
    return (instant - _EPOCH) // _MILLISECOND


def _instant(milliseconds: int) -> str:
    return format_instant(_EPOCH + milliseconds * _MILLISECOND)


_Interval = tuple[int, int]


def _length(interval: _Interval) -> int:
    return interval[1] - interval[0]


def _union(intervals: Sequence[_Interval]) -> list[_Interval]:
    """The same time as disjoint intervals in order. An empty interval is dropped."""
    merged: list[_Interval] = []
    for start, end in sorted(i for i in intervals if i[1] > i[0]):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _measure(intervals: Sequence[_Interval]) -> int:
    return sum(_length(interval) for interval in _union(intervals))


def _overlap(left: Sequence[_Interval], right: Sequence[_Interval]) -> int:
    """The time that is in an interval of each of the two lists."""
    total = 0
    others = _union(right)
    for start, end in _union(left):
        for other_start, other_end in others:
            low, high = max(start, other_start), min(end, other_end)
            if high > low:
                total += high - low
    return total


# --------------------------------------------------------------------------
# The declaration
# --------------------------------------------------------------------------


def _is_count(value: object, minimum: int) -> bool:
    return type(value) is int and minimum <= value <= _MAX_COUNT


def _signal(entry: object, seen: set[str]) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise AnalysisRefused(RULE_SIGNAL, "a signal is not an object")
    identifier, source = entry.get("id"), entry.get("source")
    if (
        not isinstance(identifier, str)
        or _SIGNAL_ID.fullmatch(identifier) is None
        or identifier in seen
    ):
        raise AnalysisRefused(
            RULE_SIGNAL, "a signal states no identifier of its own in its form"
        )
    if not isinstance(source, str) or source not in SIGNAL_SOURCES:
        raise AnalysisRefused(
            RULE_SIGNAL, f"the signal {identifier} states an unregistered source"
        )
    seen.add(identifier)
    if SIGNAL_SOURCES[source][1] == _COUNT_SOURCE:
        if (
            set(entry) != {"id", "source", "tier", "problemBelow"}
            or not isinstance(entry["tier"], str)
            or entry["tier"] not in TIERS
            or not _is_count(entry["problemBelow"], 1)
        ):
            raise AnalysisRefused(
                RULE_SIGNAL,
                f"the signal {identifier} does not state a registered tier and a "
                "problemBelow count",
            )
        return dict(entry)
    values = entry.get("healthyValues")
    if (
        set(entry) != {"id", "source", "healthyValues"}
        or not isinstance(values, list)
        or not 1 <= len(values) <= 8
        or not all(
            isinstance(value, str) and _STATUS_WORD.fullmatch(value) is not None
            for value in values
        )
        or len(set(values)) != len(values)
    ):
        raise AnalysisRefused(
            RULE_SIGNAL,
            f"the signal {identifier} does not state its healthyValues as one to "
            "eight words",
        )
    return dict(entry)


def read_declaration(text: str) -> dict[str, Any]:
    """A declaration, held to its form.

    Raises:
        AnalysisRefused: a rule of :data:`RULES` is not held.
    """
    try:
        document = json.loads(text, object_pairs_hook=_no_repeat)
    except (ValueError, RecursionError) as fault:
        raise AnalysisRefused(
            RULE_DECLARATION_UNREADABLE, "the declaration is not one JSON object"
        ) from fault
    if not isinstance(document, dict):
        raise AnalysisRefused(
            RULE_DECLARATION_UNREADABLE, "the declaration is not one JSON object"
        )
    if set(document) != _DECLARATION_MEMBERS:
        raise AnalysisRefused(
            RULE_DECLARATION, "the declaration does not have its members"
        )
    if document["schema"] != DECLARATION_SCHEMA:
        raise AnalysisRefused(RULE_DECLARATION, "the declaration states another schema")
    for name in ("experimentId", "runId"):
        value = document[name]
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise AnalysisRefused(
                RULE_DECLARATION, f"the declaration states no usable {name}"
            )
    window = document["window"]
    if not isinstance(window, dict) or set(window) != _WINDOW_MEMBERS:
        raise AnalysisRefused(RULE_WINDOW, "the window does not have its members")
    start, end = _ms(window["from"]), _ms(window["to"])
    if start is None or end is None or end <= start:
        raise AnalysisRefused(
            RULE_WINDOW,
            "the window does not state two instants in UTC to one millisecond, or "
            "it does not end after it starts",
        )
    expected = document["expected"]
    if not isinstance(expected, dict) or set(expected) != _EXPECTED_MEMBERS:
        raise AnalysisRefused(
            RULE_DECLARATION, "the expected state does not have its members"
        )
    revision, replicas = expected["desiredRevision"], expected["readyReplicas"]
    if (
        not isinstance(revision, str)
        or _COMMIT_FORM.fullmatch(revision) is None
        or not isinstance(replicas, dict)
        or set(replicas) != set(TIERS)
        or not all(_is_count(count, 1) for count in replicas.values())
        or not _is_count(expected["runtimeReadyEndpoints"], 1)
    ):
        raise AnalysisRefused(
            RULE_DECLARATION,
            "the expected state does not state a full commit identifier, a Ready "
            "replica count for each tier, and a Ready endpoint count",
        )
    signals = document["signals"]
    if not isinstance(signals, list) or len(signals) > MAX_SIGNALS:
        raise AnalysisRefused(
            RULE_SIGNAL, f"signals is not a list of at most {MAX_SIGNALS} signals"
        )
    seen: set[str] = set()
    document["signals"] = [_signal(entry, seen) for entry in signals]
    return document


# --------------------------------------------------------------------------
# The inputs
# --------------------------------------------------------------------------


def _read_inputs(
    declaration: Mapping[str, Any], texts: Mapping[str, str | None]
) -> tuple[CallerRecord, dict[str, Stream], Log | None]:
    """Each given input, read by the tool that defines it.

    A refusal names the input and the rule of that tool. It does not repeat the
    detail of that tool, which can quote a value of the file.
    """
    if set(texts) - set(INPUTS):
        raise AnalysisRefused(RULE_INPUT_NAME, "an input has an unregistered name")
    caller_text = texts.get("caller")
    if caller_text is None:
        raise AnalysisRefused(RULE_INPUT, "caller: no caller record was given")
    try:
        caller = read_record(caller_text)
    except RunnerError as refused:
        raise AnalysisRefused(RULE_INPUT, f"caller: {refused.rule}") from refused
    named = [("caller", caller.header["experimentId"], caller.header["runId"])]
    streams: dict[str, Stream] = {}
    for name in STREAM_INPUTS:
        text = texts.get(name)
        if text is None:
            continue
        try:
            stream = read_stream(text)
        except StreamRefused as refused:
            raise AnalysisRefused(RULE_INPUT, f"{name}: {refused.rule}") from refused
        if stream.name != name:
            raise AnalysisRefused(
                RULE_INPUT_NAME,
                f"the file given as {name} is the stream {stream.name}",
            )
        streams[name] = stream
        named.append((name, stream.header["experimentId"], stream.header["runId"]))
    log: Log | None = None
    events_text = texts.get(EVENTS)
    if events_text is not None:
        try:
            log = read_log(events_text)
        except LogRefused as refused:
            raise AnalysisRefused(RULE_INPUT, f"{EVENTS}: {refused.rule}") from refused
        named.append((EVENTS, log.header["experimentId"], log.header["runId"]))
    wanted = (declaration["experimentId"], declaration["runId"])
    for name, experiment, run in named:
        if (experiment, run) != wanted:
            raise AnalysisRefused(
                RULE_IDENTITY,
                f"{name} names another experiment or another run than the declaration",
            )
    return caller, streams, log


# --------------------------------------------------------------------------
# The operator events
# --------------------------------------------------------------------------


def _event_point(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "index": event["index"],
        "recordedAt": event["recordedAt"],
        "code": event["code"],
    }


def _fault(log: Log | None) -> dict[str, Any]:
    """The interval of the fault injection, when the log states exactly one."""
    empty = {"notBefore": None, "notAfter": None, "code": None}
    if log is None:
        return {"state": "not-given", **empty}
    started = [e for e in log.events if e["kind"] == "fault-injection-started"]
    finished = [e for e in log.events if e["kind"] == "fault-injection-finished"]
    if not started and not finished:
        return {"state": "not-recorded", **empty}
    if (
        len(started) != 1
        or len(finished) != 1
        or finished[0]["index"] < started[0]["index"]
        or finished[0]["code"] != started[0]["code"]
        or finished[0]["recordedAt"] < started[0]["recordedAt"]
    ):
        return {"state": "ambiguous", **empty}
    return {
        "state": "stated",
        "notBefore": started[0]["recordedAt"],
        "notAfter": finished[0]["recordedAt"],
        "code": started[0]["code"],
    }


def _of_kind(log: Log | None, kind: str) -> list[dict[str, Any]]:
    if log is None:
        return []
    return [_event_point(event) for event in log.events if event["kind"] == kind]


# --------------------------------------------------------------------------
# The caller metrics
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Completion:
    sequence: int
    started: int
    finished: int
    success: bool
    outcome: str

    def point(self) -> dict[str, Any]:
        return {"sequence": self.sequence, "finishedAt": _instant(self.finished)}


def _completions(caller: CallerRecord) -> list[_Completion]:
    """Each request of the record, in the order of :data:`COMPLETION_ORDER`."""
    listed = []
    for request in caller.requests:
        started, finished = _ms(request["startedAt"]), _ms(request["finishedAt"])
        # The reader of the record accepted both instants.
        assert started is not None and finished is not None
        listed.append(
            _Completion(
                sequence=request["sequence"],
                started=started,
                finished=finished,
                success=request["success"] is True,
                outcome=request["outcome"],
            )
        )
    # The sort is stable, so two requests with one instant keep their line order.
    return sorted(listed, key=lambda completion: completion.finished)


def _tied(ordered: Sequence[_Completion], position: int) -> bool:
    """Whether a completion of the other outcome has the same completion instant."""
    own = ordered[position]
    return any(
        other.finished == own.finished and other.success is not own.success
        for other in ordered
    )


def _episodes(ordered: Sequence[_Completion]) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    start: int | None = None
    failed = 0
    for position, completion in enumerate(ordered):
        if not completion.success:
            if start is None:
                start, failed = position, 0
            failed += 1
            continue
        if start is None:
            continue
        first = ordered[start]
        episodes.append(
            {
                "index": len(episodes) + 1,
                "open": False,
                "start": {**first.point(), "tied": _tied(ordered, start)},
                "end": {**completion.point(), "tied": _tied(ordered, position)},
                "ms": completion.finished - first.finished,
                "failedRequests": failed,
            }
        )
        start = None
    if start is not None:
        first = ordered[start]
        episodes.append(
            {
                "index": len(episodes) + 1,
                "open": True,
                "start": {**first.point(), "tied": _tied(ordered, start)},
                "end": None,
                "ms": None,
                "failedRequests": failed,
            }
        )
    return episodes


def _max_success_gap(ordered: Sequence[_Completion]) -> dict[str, Any]:
    successes = [completion for completion in ordered if completion.success]
    if len(successes) < 2:
        return {
            "state": NOT_COMPUTABLE,
            "reason": "fewer-than-two-successes",
            "successes": len(successes),
            "ms": None,
            "from": None,
            "to": None,
        }
    # The first of the largest gaps is the one that is stated.
    earlier, later = max(
        pairwise(successes), key=lambda pair: pair[1].finished - pair[0].finished
    )
    return {
        "state": COMPUTED,
        "reason": None,
        "successes": len(successes),
        "ms": later.finished - earlier.finished,
        "from": earlier.point(),
        "to": later.point(),
    }


def _caller(
    caller: CallerRecord,
    window: tuple[int, int],
    fault_from: int | None,
) -> tuple[dict[str, Any], list[_Completion]]:
    """The caller metrics, and the completions of the window in order."""
    start, end = window
    everything = _completions(caller)
    ordered = [c for c in everything if start <= c.finished <= end]
    record_start = _ms(caller.header["startedAt"])
    record_end = _ms(caller.end["finishedAt"])
    assert record_start is not None and record_end is not None
    covers = record_start <= start and record_end >= end
    instants = Counter(completion.finished for completion in ordered)
    reason = None
    if not covers:
        reason = "caller-record-does-not-cover-window"
    elif not ordered:
        reason = "no-completion-in-window"
    document: dict[str, Any] = {
        "state": COMPUTED if reason is None else NOT_COMPUTABLE,
        "reason": reason,
        "record": {
            "mode": caller.header["mode"],
            "startedAt": caller.header["startedAt"],
            "finishedAt": caller.end["finishedAt"],
            "endState": caller.end["endState"],
            "requests": len(everything),
            "coversWindow": covers,
        },
        "order": {
            "rule": COMPLETION_ORDER,
            "completionsSharingAnInstant": sum(
                count for count in instants.values() if count > 1
            ),
        },
        "requests": None,
        "failureEpisodes": None,
        "maxSuccessGap": None,
        "firstImpact": None,
    }
    if reason is not None:
        return document, []
    episodes = _episodes(ordered)
    open_count = sum(1 for episode in episodes if episode["open"])
    before = [c for c in everything if c.finished < start]
    after = [c for c in everything if c.finished > end]
    # The window starts inside an episode when the completion before it failed.
    cut = bool(before) and not before[-1].success
    later = next((c for c in after if c.success), None)
    for episode in episodes:
        # The record can hold the success that ends an open episode. It is
        # after the window, so it is stated and it does not close the episode.
        episode["successAfterWindow"] = (
            later.point() if episode["open"] and later is not None else None
        )
    edges = [start, *(c.finished for c in ordered), end]
    document["requests"] = {
        "completed": len(ordered),
        "successful": sum(1 for c in ordered if c.success),
        "failed": sum(1 for c in ordered if not c.success),
        "outsideWindow": len(everything) - len(ordered),
        # The edges of the window count as ends, so a caller that completes
        # nothing for a time is visible here.
        "largestTimeWithNoCompletionMs": max(
            later_edge - earlier_edge for earlier_edge, later_edge in pairwise(edges)
        ),
    }
    figure_reason = None
    if cut:
        figure_reason = "episode-starts-before-window"
    elif open_count:
        figure_reason = "episode-open"
    document["failureEpisodes"] = {
        "count": len(episodes),
        "open": open_count,
        "startsBeforeWindow": cut,
        "episodes": episodes,
        # No failed request gives 0. An open episode, and a window that starts
        # inside an episode, give no figure.
        "callerFailureEpisodeMs": (
            max((episode["ms"] for episode in episodes), default=0)
            if figure_reason is None
            else None
        ),
        "reason": figure_reason,
    }
    document["maxSuccessGap"] = _max_success_gap(ordered)
    search = start if fault_from is None else max(start, fault_from)
    impact = next((c for c in ordered if not c.success and c.finished >= search), None)
    document["firstImpact"] = {
        "state": "none" if impact is None else "observed",
        "searchedFrom": _instant(search),
        "sequence": None if impact is None else impact.sequence,
        "startedAt": None if impact is None else _instant(impact.started),
        "finishedAt": None if impact is None else _instant(impact.finished),
        "outcome": None if impact is None else impact.outcome,
    }
    return document, ordered


# --------------------------------------------------------------------------
# A sampled series
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Observation:
    """What one reading states about one subject.

    ``state`` is the reduced state. A reading that is not observed states no
    instant here, because it places no value in time.
    """

    index: int
    started: int | None
    finished: int | None
    state: str

    def point(self) -> dict[str, Any]:
        assert self.started is not None and self.finished is not None
        return {
            "index": self.index,
            "startedAt": _instant(self.started),
            "finishedAt": _instant(self.finished),
        }


@dataclass(frozen=True)
class _Series:
    """The observations of the window, or the reason that the window has none."""

    reason: str | None
    observations: tuple[_Observation, ...]
    outside: int


def _answered(reading: Mapping[str, Any]) -> bool:
    read = reading["read"]
    return bool(
        read["state"] == ANSWERED
        and read["startedAt"] is not None
        and read["finishedAt"] is not None
    )


def _series(
    stream: Stream | None,
    window: tuple[int, int],
    reduce: Callable[[Mapping[str, Any]], str],
) -> _Series:
    """The readings of one stream that are inside the window, each reduced.

    A reading is inside the window when its read starts and finishes inside it.
    A reading with no instants between two such readings is kept as not
    observed. ``reduce`` gives the state of an answered reading, and it gives
    :data:`NOT_OBSERVED` when the reading does not report the value.
    """
    if stream is None:
        return _Series("stream-not-given", (), 0)
    start, end = window
    placed = [
        (
            reading,
            _ms(reading["read"]["startedAt"]),
            _ms(reading["read"]["finishedAt"]),
        )
        for reading in stream.readings
    ]
    inside = [
        position
        for position, (_, started, finished) in enumerate(placed)
        if started is not None
        and finished is not None
        and started >= start
        and finished <= end
    ]
    if not inside:
        return _Series("no-reading-in-window", (), len(placed))
    observations: list[_Observation] = []
    previous: int | None = None
    for position in range(inside[0], inside[-1] + 1):
        reading, started, finished = placed[position]
        if started is not None and finished is not None:
            if started < start or finished > end:
                return _Series("readings-out-of-order", (), len(placed))
            if previous is not None and started < previous:
                return _Series("readings-out-of-order", (), len(placed))
            previous = finished
        state = reduce(reading) if _answered(reading) else NOT_OBSERVED
        observed = state != NOT_OBSERVED
        observations.append(
            _Observation(
                index=reading["index"],
                started=started if observed else None,
                finished=finished if observed else None,
                state=state,
            )
        )
    return _Series(None, tuple(observations), len(placed) - len(observations))


@dataclass(frozen=True)
class _Span:
    """Consecutive readings that gave one state, and the readings that bound them."""

    first: _Observation
    last: _Observation
    readings: int
    not_observed_inside: int
    before: _Observation | None
    after: _Observation | None
    #: The first and the last reading of each part of the run that holds no
    #: reading without a value.
    parts: tuple[tuple[_Observation, _Observation], ...]

    def inner(self) -> list[_Interval]:
        """The time between consecutive reads that both gave the state.

        A reading with no value inside the run divides it. The time across such
        a reading is in no part, because no read gave the state there.
        """
        intervals: list[_Interval] = []
        for first, last in self.parts:
            assert first.finished is not None and last.started is not None
            intervals.append((first.finished, max(first.finished, last.started)))
        return intervals

    def outer(self, window: tuple[int, int]) -> _Interval:
        low = window[0] if self.before is None else self.before.started
        high = window[1] if self.after is None else self.after.finished
        assert low is not None and high is not None
        return (low, high)

    def document(self, window: tuple[int, int]) -> dict[str, Any]:
        return {
            "firstReading": self.first.point(),
            "lastReading": self.last.point(),
            "readings": self.readings,
            "notObservedReadingsInside": self.not_observed_inside,
            "boundedBefore": None if self.before is None else self.before.point(),
            "boundedAfter": None if self.after is None else self.after.point(),
            "innerMs": _measure(self.inner()),
            "outerMs": _length(self.outer(window)),
        }


def _spans(observations: Sequence[_Observation], state: str) -> list[_Span]:
    """Each run of readings that gave ``state`` with no reading of another state.

    A reading that is not observed does not end a run and is not a reading of
    the state. It divides the run into parts, and the inner figure is the sum of
    the parts. The reading that bounds a run on a side is the nearest reading
    on that side that gave another state.
    """
    spans: list[_Span] = []
    position, total = 0, len(observations)
    while position < total:
        if observations[position].state != state:
            position += 1
            continue
        first = last = part = position
        readings, inside, pending = 1, 0, 0
        parts: list[tuple[_Observation, _Observation]] = []
        cursor = position + 1
        while cursor < total and observations[cursor].state in (state, NOT_OBSERVED):
            if observations[cursor].state == state:
                if pending:
                    parts.append((observations[part], observations[last]))
                    part = cursor
                last, readings = cursor, readings + 1
                inside, pending = inside + pending, 0
            else:
                pending += 1
            cursor += 1
        parts.append((observations[part], observations[last]))
        back = first - 1
        while back >= 0 and observations[back].state == NOT_OBSERVED:
            back -= 1
        spans.append(
            _Span(
                first=observations[first],
                last=observations[last],
                readings=readings,
                not_observed_inside=inside,
                before=observations[back] if back >= 0 else None,
                after=observations[cursor] if cursor < total else None,
                parts=tuple(parts),
            )
        )
        position = cursor
    return spans


def _unread(
    observations: Sequence[_Observation], window: tuple[int, int]
) -> list[_Interval]:
    """The time of the window in which no read gave a value.

    It is the time before the first reading with a value, the time after the
    last one, and each time between two such readings that holds a reading
    with no value.
    """
    seen = [o for o in observations if o.state != NOT_OBSERVED]
    if not seen:
        return [window]
    first, last = seen[0], seen[-1]
    assert first.started is not None and last.finished is not None
    intervals: list[_Interval] = [
        (window[0], first.started),
        (last.finished, window[1]),
    ]
    previous: _Observation | None = None
    gap = False
    for observation in observations:
        if observation.state == NOT_OBSERVED:
            gap = previous is not None
            continue
        if gap and previous is not None:
            assert previous.finished is not None and observation.started is not None
            intervals.append((previous.finished, observation.started))
        previous, gap = observation, False
    return intervals


def _reading_counts(series: _Series) -> dict[str, Any]:
    states = [observation.state for observation in series.observations]
    seen = [o for o in series.observations if o.state != NOT_OBSERVED]
    between = [
        later.started - earlier.finished
        for earlier, later in pairwise(seen)
        if later.started is not None and earlier.finished is not None
    ]
    return {
        "inWindow": len(states),
        "withValue": len(seen),
        "withoutValue": states.count(NOT_OBSERVED),
        "outsideWindow": series.outside,
        "largestTimeBetweenReadsMs": max(between, default=None),
    }


# --------------------------------------------------------------------------
# The reductions of a reading
# --------------------------------------------------------------------------


def _endpoint_count(reading: Mapping[str, Any], tier: str) -> int | None:
    tiers = reading["tiers"]
    if tiers is None:
        return None
    found = [entry for entry in tiers if entry["tier"] == tier]
    if len(found) != 1 or found[0]["state"] != TIER_OBSERVED:
        return None
    return int(found[0]["endpoints"]["ready"])


def _deployment_count(reading: Mapping[str, Any], tier: str, name: str) -> int | None:
    tiers = reading["tiers"]
    if tiers is None:
        return None
    found = [entry for entry in tiers if entry["tier"] == tier]
    if len(found) != 1 or found[0]["state"] != TIER_OBSERVED:
        return None
    field = found[0][name]
    if field["state"] != REPORTED or type(field["value"]) is not int:
        return None
    return int(field["value"])


def _ready_pods(reading: Mapping[str, Any], tier: str) -> int | None:
    pods = reading["pods"]
    if pods is None:
        return None
    count = 0
    for pod in pods:
        if pod["tier"] != tier:
            continue
        ready = pod["ready"]
        if ready["state"] != REPORTED:
            # A pod with no Ready condition is not counted as not Ready.
            return None
        count += ready["value"] == "True"
    return count


def _application_value(reading: Mapping[str, Any], name: str) -> str | None:
    application = reading["application"]
    if application is None:
        return None
    field = application[name]
    if field["state"] != REPORTED or not isinstance(field["value"], str):
        return None
    return str(field["value"])


def _signal_state(signal: Mapping[str, Any], reading: Mapping[str, Any]) -> str:
    source = signal["source"]
    if source in _APPLICATION_FIELD:
        value = _application_value(reading, _APPLICATION_FIELD[source])
        if value is None:
            return NOT_OBSERVED
        return HEALTHY if value in signal["healthyValues"] else PROBLEM
    tier = signal["tier"]
    if source == "endpoints-ready":
        count = _endpoint_count(reading, tier)
    elif source == "pods-ready":
        count = _ready_pods(reading, tier)
    else:
        count = _deployment_count(reading, tier, _DEPLOYMENT_FIELD[source])
    if count is None:
        return NOT_OBSERVED
    return PROBLEM if count < signal["problemBelow"] else HEALTHY


# --------------------------------------------------------------------------
# Zero Ready endpoints
# --------------------------------------------------------------------------


def _zero_ready_tier(
    stream: Stream | None, window: tuple[int, int], tier: str
) -> tuple[str | None, dict[str, Any] | None]:
    def reduce(reading: Mapping[str, Any]) -> str:
        count = _endpoint_count(reading, tier)
        if count is None:
            return NOT_OBSERVED
        return _ZERO if count == 0 else _NON_ZERO

    series = _series(stream, window, reduce)
    if series.reason is not None:
        return series.reason, None
    counts = _reading_counts(series)
    document: dict[str, Any] = {
        "state": NOT_OBSERVED,
        "reason": "no-count-in-window",
        "readings": counts,
        "notObservedMs": _measure(_unread(series.observations, window)),
        "count": None,
        "intervals": [],
        "totalInnerMs": None,
        "maxInnerMs": None,
        "totalOuterMs": None,
        "maxOuterMs": None,
    }
    if counts["withValue"] == 0:
        # No reading states a count, so the tier has no interval and no zero.
        return None, document
    spans = _spans(series.observations, _ZERO)
    inner = [_measure(span.inner()) for span in spans]
    outer = [span.outer(window) for span in spans]
    document.update(
        state="observed",
        reason=None,
        count=len(spans),
        intervals=[span.document(window) for span in spans],
        totalInnerMs=sum(inner),
        maxInnerMs=max(inner, default=0),
        totalOuterMs=_measure(outer),
        maxOuterMs=max((_length(interval) for interval in outer), default=0),
    )
    return None, document


def _zero_ready(stream: Stream | None, window: tuple[int, int]) -> dict[str, Any]:
    tiers: dict[str, Any] = {}
    for tier in TIERS:
        reason, document = _zero_ready_tier(stream, window, tier)
        if reason is not None:
            return {"state": NOT_COMPUTABLE, "reason": reason, "tiers": None}
        tiers[tier] = document
    return {"state": COMPUTED, "reason": None, "tiers": tiers}


# --------------------------------------------------------------------------
# The signals
# --------------------------------------------------------------------------


def _disagreement(
    caller_intervals: Sequence[_Interval],
    observations: Sequence[_Observation],
    state: str,
    window: tuple[int, int],
) -> dict[str, Any]:
    """The time in the caller intervals in which the signal gave ``state``."""
    spans = _spans(observations, state)
    return {
        "callerMs": _measure(caller_intervals),
        "innerMs": _overlap(
            caller_intervals, [part for span in spans for part in span.inner()]
        ),
        "outerMs": _overlap(caller_intervals, [span.outer(window) for span in spans]),
        "signalNotObservedMs": _overlap(
            caller_intervals, _unread(observations, window)
        ),
    }


def _detection_lag(
    observations: Sequence[_Observation],
    impact: int | None,
    search: int,
) -> dict[str, Any]:
    empty = {
        "firstIndication": None,
        "notBefore": None,
        "notAfter": None,
        "lagNotBelowMs": None,
        "lagNotAboveMs": None,
        "order": None,
    }
    position = next(
        (
            p
            for p, o in enumerate(observations)
            if o.state == PROBLEM and o.finished is not None and o.finished >= search
        ),
        None,
    )
    if position is None:
        return {"state": NOT_COMPUTABLE, "reason": "never-indicated", **empty}
    first = observations[position]
    back = position - 1
    while back >= 0 and observations[back].state == NOT_OBSERVED:
        back -= 1
    before = observations[back] if back >= 0 else None
    if before is not None and before.state == PROBLEM:
        return {
            "state": NOT_COMPUTABLE,
            "reason": "indicated-before-search-start",
            **empty,
            "firstIndication": first.point(),
        }
    assert first.finished is not None
    not_before = None if before is None else before.started
    stated = {
        "firstIndication": first.point(),
        # The signal did not state the problem at the read before, so it
        # changed after that read started. With no read before, no instant
        # bounds the change from below.
        "notBefore": None if not_before is None else _instant(not_before),
        "notAfter": _instant(first.finished),
    }
    if impact is None:
        return {
            "state": NOT_COMPUTABLE,
            "reason": "no-caller-impact",
            **empty,
            **stated,
        }
    below = None if not_before is None else not_before - impact
    above = first.finished - impact
    if above < 0:
        order = "signal-first"
    elif below is not None and below > 0:
        order = "caller-first"
    else:
        order = "not-established"
    return {
        "state": COMPUTED,
        "reason": None,
        **stated,
        "lagNotBelowMs": below,
        "lagNotAboveMs": above,
        # The order of the recorded instants. The two clocks are not compared.
        "order": order,
    }


def _caller_intervals(
    caller: Mapping[str, Any], ordered: Sequence[_Completion], end: int
) -> tuple[list[_Interval], list[_Interval]]:
    """The time in which the caller fails, and the time in which it succeeds.

    The caller fails from the start of an episode to its end, and an open
    episode lasts to the end of the window. The caller succeeds between two
    consecutive completions that are both successful. The time from a
    successful completion to the failed one after it is in neither.
    """
    by_sequence = {completion.sequence: completion for completion in ordered}
    failing = [
        (
            by_sequence[episode["start"]["sequence"]].finished,
            end
            if episode["open"]
            else by_sequence[episode["end"]["sequence"]].finished,
        )
        for episode in caller["failureEpisodes"]["episodes"]
    ]
    succeeding = [
        (earlier.finished, later.finished)
        for earlier, later in pairwise(ordered)
        if earlier.success and later.success
    ]
    return failing, succeeding


def _signal_document(
    signal: Mapping[str, Any],
    stream: Stream | None,
    window: tuple[int, int],
    caller: Mapping[str, Any],
    ordered: Sequence[_Completion],
    fault: Mapping[str, Any],
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "id": signal["id"],
        "source": signal["source"],
        "stream": SIGNAL_SOURCES[signal["source"]][0],
        "declared": {
            name: value
            for name, value in signal.items()
            if name not in ("id", "source")
        },
        "state": COMPUTED,
        "reason": None,
        "readings": None,
        "byState": None,
        "changed": None,
        "detectionLag": None,
        "falseHealthy": None,
        "falseUnavailable": None,
    }
    series = _series(stream, window, lambda reading: _signal_state(signal, reading))
    if series.reason is not None:
        document.update(state=NOT_COMPUTABLE, reason=series.reason)
        return document
    observations = series.observations
    states = [observation.state for observation in observations]
    document["readings"] = _reading_counts(series)
    document["byState"] = {
        state: states.count(state) for state in (HEALTHY, PROBLEM, NOT_OBSERVED)
    }
    if HEALTHY not in states and PROBLEM not in states:
        document.update(state=NOT_COMPUTABLE, reason="signal-never-observed")
        return document
    document["changed"] = HEALTHY in states and PROBLEM in states
    if caller["state"] != COMPUTED:
        for name in ("detectionLag", "falseHealthy", "falseUnavailable"):
            document[name] = {
                "state": NOT_COMPUTABLE,
                "reason": "caller-not-computable",
            }
        return document
    failing, succeeding = _caller_intervals(caller, ordered, window[1])
    document["falseHealthy"] = {
        "state": COMPUTED,
        "reason": None,
        **_disagreement(failing, observations, HEALTHY, window),
    }
    document["falseUnavailable"] = {
        "state": COMPUTED,
        "reason": None,
        **_disagreement(succeeding, observations, PROBLEM, window),
    }
    if fault["state"] == "ambiguous":
        document["detectionLag"] = {
            "state": NOT_COMPUTABLE,
            "reason": "fault-ambiguous",
        }
        return document
    impact = _ms(caller["firstImpact"]["finishedAt"])
    fault_from = _ms(fault["notBefore"])
    search = window[0] if fault_from is None else max(window[0], fault_from)
    document["detectionLag"] = _detection_lag(observations, impact, search)
    return document


# --------------------------------------------------------------------------
# Stabilized recovery
# --------------------------------------------------------------------------


def _conditions(
    declaration: Mapping[str, Any],
    streams: Mapping[str, Stream],
    window: tuple[int, int],
) -> dict[str, _Series]:
    """The three conditions of the expected state, each as a series."""
    expected = declaration["expected"]

    def revision(reading: Mapping[str, Any]) -> str:
        resolved = _application_value(reading, "resolvedRevision")
        sync = _application_value(reading, "syncStatus")
        if resolved is None or sync is None:
            return NOT_OBSERVED
        held = resolved == expected["desiredRevision"] and sync == SYNCED
        return _HELD if held else _NOT_HELD

    def replicas(reading: Mapping[str, Any]) -> str:
        counts = [_deployment_count(reading, tier, "readyReplicas") for tier in TIERS]
        if any(count is None for count in counts):
            return NOT_OBSERVED
        wanted = [expected["readyReplicas"][tier] for tier in TIERS]
        return _HELD if counts == wanted else _NOT_HELD

    def endpoints(reading: Mapping[str, Any]) -> str:
        count = _endpoint_count(reading, _RUNTIME_TIER)
        if count is None:
            return NOT_OBSERVED
        return _HELD if count == expected["runtimeReadyEndpoints"] else _NOT_HELD

    return {
        "desiredRevision": _series(streams.get(ARGO), window, revision),
        "readyReplicas": _series(streams.get(DEPLOYMENTS), window, replicas),
        "runtimeReadyEndpoints": _series(streams.get(ENDPOINTS), window, endpoints),
    }


def _blocked_until(series: _Series, until: int) -> int | None:
    """The latest instant, for a span that ends at ``until``, with no held value.

    A reading that does not hold blocks until its read finishes. A reading with
    no value blocks from the read with a value before it to the read with a
    value after it, because the stream states no value for that time. With no
    read after it, the time with no value does not end.
    """
    latest: int | None = None
    observations = series.observations
    for position, observation in enumerate(observations):
        if observation.state == _HELD:
            continue
        if observation.state == _NOT_HELD:
            assert observation.started is not None and observation.finished is not None
            if observation.started <= until:
                latest = max(latest or 0, observation.finished)
            continue
        earlier = next(
            (o for o in reversed(observations[:position]) if o.finished is not None),
            None,
        )
        later = next(
            (o for o in observations[position + 1 :] if o.started is not None), None
        )
        if (
            earlier is not None
            and earlier.finished is not None
            and earlier.finished > until
        ):
            continue
        high = until if later is None or later.started is None else later.started
        latest = max(latest or 0, high)
    return latest


def _inside(series: _Series, low: int, high: int) -> list[_Observation]:
    return [
        o
        for o in series.observations
        if o.started is not None
        and o.finished is not None
        and o.started >= low
        and o.finished <= high
    ]


def _largest_silence(inside: Sequence[_Observation], low: int, high: int) -> int:
    """The longest time from ``low`` to ``high`` in which no read was in progress."""
    longest, reached = 0, low
    for observation in inside:
        assert observation.started is not None and observation.finished is not None
        longest = max(longest, observation.started - reached)
        reached = max(reached, observation.finished)
    return max(longest, high - reached)


def _find_span(
    candidates: Sequence[_Completion], conditions: Mapping[str, _Series]
) -> tuple[tuple[_Completion, _Completion, int] | None, tuple[int, int]]:
    """The first stabilization span, and the longest run of successes.

    A span is consecutive successful completions. It holds at least
    :data:`STABILIZATION_SUCCESSES` of them over at least
    :data:`STABILIZATION_SPAN_MS`. It starts after the last instant at which a
    condition has no held value, and it holds at least one reading of each
    condition.
    """
    run_start = 0
    longest = (0, 0)
    for position, completion in enumerate(candidates):
        if not completion.success:
            run_start = position + 1
            continue
        run = candidates[run_start : position + 1]
        longest = max(longest, (len(run), completion.finished - run[0].finished))
        blocked = [
            _blocked_until(series, completion.finished)
            for series in conditions.values()
        ]
        after = max((b for b in blocked if b is not None), default=None)
        usable = [c for c in run if after is None or c.finished > after]
        if (
            len(usable) < STABILIZATION_SUCCESSES
            or completion.finished - usable[0].finished < STABILIZATION_SPAN_MS
        ):
            continue
        low, high = usable[0].finished, completion.finished
        if all(_inside(series, low, high) for series in conditions.values()):
            return (usable[0], completion, len(usable)), longest
    return None, longest


def _stabilized(
    declaration: Mapping[str, Any],
    streams: Mapping[str, Stream],
    window: tuple[int, int],
    caller: Mapping[str, Any],
    ordered: Sequence[_Completion],
    fault: Mapping[str, Any],
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "state": NOT_COMPUTABLE,
        "reason": None,
        "rule": {
            "consecutiveSuccesses": STABILIZATION_SUCCESSES,
            "spanMs": STABILIZATION_SPAN_MS,
            "revisionPresent": REVISION_PRESENT,
        },
        "conditions": None,
        "searchedFrom": None,
        "stabilized": None,
        "stabilizedAt": None,
        "span": None,
        "sinceFault": None,
        "requestsFailedSinceFault": None,
        "longestSuccessRun": None,
    }
    if caller["state"] != COMPUTED:
        document["reason"] = "caller-not-computable"
        return document
    if fault["state"] == "ambiguous":
        document["reason"] = "fault-ambiguous"
        return document
    conditions = _conditions(declaration, streams, window)
    document["conditions"] = {
        name: {
            "state": series.reason or "read",
            "readings": None if series.reason else _reading_counts(series),
            "held": None
            if series.reason
            else sum(1 for o in series.observations if o.state == _HELD),
            "notHeld": None
            if series.reason
            else sum(1 for o in series.observations if o.state == _NOT_HELD),
        }
        for name, series in conditions.items()
    }
    reasons = sorted({s.reason for s in conditions.values() if s.reason is not None})
    if reasons:
        document["reason"] = reasons[0]
        return document
    fault_from, fault_to = _ms(fault["notBefore"]), _ms(fault["notAfter"])
    search = window[0] if fault_to is None else max(window[0], fault_to)
    found, longest = _find_span(
        [c for c in ordered if c.finished >= search], conditions
    )
    document.update(
        state=COMPUTED,
        searchedFrom=_instant(search),
        stabilized=found is not None,
        longestSuccessRun={"successes": longest[0], "spanMs": longest[1]},
    )
    if found is None:
        return document
    first, last, size = found
    document["stabilizedAt"] = _instant(last.finished)
    document["span"] = {
        "first": first.point(),
        "last": last.point(),
        "successes": size,
        "ms": last.finished - first.finished,
        "readingsInside": {
            name: len(_inside(series, first.finished, last.finished))
            for name, series in conditions.items()
        },
        # The longest time of the span with no read of a condition, with the
        # two ends of the span as ends. The rule sets no limit for it.
        "largestTimeWithNoReadingMs": {
            name: _largest_silence(
                _inside(series, first.finished, last.finished),
                first.finished,
                last.finished,
            )
            for name, series in conditions.items()
        },
    }
    if fault_from is not None and fault_to is not None:
        document["sinceFault"] = {
            "faultStartedAt": fault["notBefore"],
            "faultFinishedAt": fault["notAfter"],
            "fromFaultStartedMs": last.finished - fault_from,
            "fromFaultFinishedMs": last.finished - fault_to,
        }
        document["requestsFailedSinceFault"] = sum(
            1
            for c in ordered
            if not c.success and fault_from <= c.finished <= last.finished
        )
    return document


# --------------------------------------------------------------------------
# The analysis
# --------------------------------------------------------------------------


def _without_value(
    caller: Mapping[str, Any],
    zero: Mapping[str, Any],
    signals: Sequence[Mapping[str, Any]],
    stabilized: Mapping[str, Any],
) -> list[str]:
    """Each metric of the document that has no value, by its path."""
    names: list[str] = []
    if caller["state"] != COMPUTED:
        names.append("caller")
    else:
        if caller["failureEpisodes"]["reason"] is not None:
            names.append("caller.failureEpisodes.callerFailureEpisodeMs")
        if caller["maxSuccessGap"]["state"] != COMPUTED:
            names.append("caller.maxSuccessGap")
    if zero["state"] != COMPUTED:
        names.append("zeroReadyEndpoints")
    else:
        names.extend(
            f"zeroReadyEndpoints.tiers.{tier}"
            for tier, entry in zero["tiers"].items()
            if entry["state"] != "observed"
        )
    for signal in signals:
        if signal["state"] != COMPUTED:
            names.append(f"signals.{signal['id']}")
            continue
        names.extend(
            f"signals.{signal['id']}.{name}"
            for name in ("detectionLag", "falseHealthy", "falseUnavailable")
            if signal[name]["state"] != COMPUTED
        )
    if stabilized["state"] != COMPUTED:
        names.append("stabilizedRecovery")
    return names


def analyze(declaration_text: str, texts: Mapping[str, str | None]) -> dict[str, Any]:
    """The analysis document of one run.

    ``texts`` gives the text of each input by its name in :data:`INPUTS`. The
    caller record is required. An input that is None was not given, and each
    metric that reads it then has no value.

    Raises:
        AnalysisRefused: a rule of :data:`RULES` is not held.
    """
    declaration = read_declaration(declaration_text)
    caller_record, streams, log = _read_inputs(declaration, texts)
    start, end = _ms(declaration["window"]["from"]), _ms(declaration["window"]["to"])
    assert start is not None and end is not None
    aborts = _of_kind(log, "run-aborted")
    ended_by = "declared"
    if aborts:
        # A log can hold events whose instants are not in the order of its
        # lines, so the earliest instant is taken and not the first line.
        aborted = min(_ms(abort["recordedAt"]) or 0 for abort in aborts)
        if aborted <= start:
            raise AnalysisRefused(
                RULE_WINDOW, "the run was aborted at or before the window start"
            )
        if aborted < end:
            end, ended_by = aborted, "run-aborted"
    window = (start, end)
    fault = _fault(log)
    caller, ordered = _caller(caller_record, window, _ms(fault["notBefore"]))
    zero = _zero_ready(streams.get(ENDPOINTS), window)
    signals = [
        _signal_document(
            signal,
            streams.get(SIGNAL_SOURCES[signal["source"]][0]),
            window,
            caller,
            ordered,
            fault,
        )
        for signal in declaration["signals"]
    ]
    stabilized = _stabilized(declaration, streams, window, caller, ordered, fault)
    given = {"caller", *streams, *((EVENTS,) if log is not None else ())}
    return {
        "schema": SCHEMA,
        "experimentId": declaration["experimentId"],
        "runId": declaration["runId"],
        "inputs": {name: "read" if name in given else "not-given" for name in INPUTS},
        "window": {
            "from": declaration["window"]["from"],
            "to": declaration["window"]["to"],
            "effectiveTo": _instant(end),
            "endedBy": ended_by,
        },
        "expected": declaration["expected"],
        "fault": fault,
        "aborts": aborts,
        "manualActions": _of_kind(log, "manual-action"),
        "caller": caller,
        "zeroReadyEndpoints": zero,
        "signals": signals,
        "stabilizedRecovery": stabilized,
        "withoutValue": _without_value(caller, zero, signals, stabilized),
        "clocks": {
            "caller": "the clock of the pod of the reliability runner",
            "readings": "the clock of the host that ran the timeline collector",
            "events": "the clock of the host that recorded each event",
            "skew": "not-measured",
        },
        "limitations": list(LIMITATIONS),
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def analysis_text(document: Mapping[str, Any]) -> str:
    """A document as the text that is stored: sorted members, and one line feed last."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


# --------------------------------------------------------------------------
# The aggregate of three runs
# --------------------------------------------------------------------------


def _figure(document: Mapping[str, Any], path: Sequence[str]) -> int | None:
    value: Any = document
    for name in path:
        if not isinstance(value, dict) or name not in value:
            return None
        value = value[name]
    return value if type(value) is int else None


@dataclass(frozen=True)
class RunResult:
    """The result of one run, as its manifest states it, for an aggregate.

    ``state`` and ``reason`` are the two members of the result of the manifest.
    ``exclusion_reasons`` is the ``exclusionReasons`` member of the freeze
    record that the manifest names, or None when that record has none.
    ``preregistration`` is how the manifest names that record: its path, its
    revision, and its content digest. The replay tool adds the executing
    revision that it read the record at. It is a mapping or None. The
    aggregate repeats it and does not read it.

    The caller reads the manifest and the freeze record. This module reads no
    file, so it does not check that the three are those of one run directory.
    """

    state: str
    reason: object = None
    exclusion_reasons: object = None
    preregistration: Mapping[str, Any] | None = None


def _identifier(value: object) -> bool:
    return type(value) is str and _IDENTIFIER.fullmatch(value) is not None


def _reasons_problem(policy: object) -> str | None:
    """Why the exclusion reasons of a freeze record do not have their form."""
    if not isinstance(policy, dict) or set(policy) != _EXCLUSION_MEMBERS:
        return "the exclusion reasons do not have exactly their two members"
    if not _identifier(policy["experimentId"]):
        return "the exclusion reasons state no usable experiment identifier"
    reasons = policy["reasons"]
    if not isinstance(reasons, list) or len(reasons) > MAX_EXCLUSION_REASONS:
        return f"the reasons are not a list of at most {MAX_EXCLUSION_REASONS}"
    identifiers: set[str] = set()
    stated: set[tuple[str, str]] = set()
    for entry in reasons:
        if (
            not isinstance(entry, dict)
            or not set(entry) >= _REASON_MEMBERS
            or set(entry) - _REASON_MEMBERS - {_REASON_RUNS}
        ):
            return "a reason does not have exactly its members"
        identifier, state, reason = entry["id"], entry["resultState"], entry["reason"]
        if not _identifier(identifier) or identifier in identifiers:
            return "a reason has no identifier of its own"
        identifiers.add(identifier)
        if type(state) is not str or state not in EXCLUDED_STATES:
            return "a reason is registered for a result state that is counted"
        if (
            type(reason) is not str
            or not reason
            or reason != reason.strip()
            or len(reason) > _MAX_REASON_LENGTH
        ):
            return (
                "a reason is not text of 1 to 2000 characters with no white space "
                "at its ends"
            )
        if (state, reason) in stated:
            return "one result state has one reason text twice"
        stated.add((state, reason))
        if _REASON_RUNS in entry:
            runs = entry[_REASON_RUNS]
            if (
                not isinstance(runs, list)
                or not runs
                or not all(_identifier(run) for run in runs)
                or len(set(runs)) != len(runs)
            ):
                return "the runs of a reason are not run identifiers, each once"
    return None


def _exclusion(experiment: str, run: str, result: RunResult) -> dict[str, Any]:
    """The registered reason for which one run is not counted.

    The reason of the manifest is compared as text, character for character,
    with each reason that the freeze record registers for the result state. A
    message names the run and repeats no text of a manifest or of a record.

    Raises:
        AnalysisRefused: the exclusion reasons do not have their form, or they
            do not register the reason for the experiment, the state, and the
            run.
    """
    policy = result.exclusion_reasons
    if policy is None:
        raise AnalysisRefused(
            RULE_EXCLUSION,
            f"the run {run} is in the state {result.state}, and no exclusion reason "
            "is registered for it",
        )
    problem = _reasons_problem(policy)
    if problem is not None:
        raise AnalysisRefused(RULE_EXCLUSION_REASONS, f"the run {run}: {problem}")
    assert isinstance(policy, dict)
    if policy["experimentId"] != experiment:
        raise AnalysisRefused(
            RULE_EXCLUSION,
            f"the run {run}: the exclusion reasons are registered for another "
            "experiment",
        )
    reason = result.reason
    if type(reason) is not str or not reason:
        raise AnalysisRefused(
            RULE_EXCLUSION, f"the run {run} is not counted and states no reason"
        )
    entries = [entry for entry in policy["reasons"] if entry["reason"] == reason]
    for entry in entries:
        if entry["resultState"] != result.state:
            continue
        if _REASON_RUNS in entry and run not in entry[_REASON_RUNS]:
            raise AnalysisRefused(
                RULE_EXCLUSION,
                f"the run {run}: its reason is registered for other runs",
            )
        return {
            "reasonId": entry["id"],
            "reason": reason,
            "preregistration": None
            if result.preregistration is None
            else dict(result.preregistration),
        }
    raise AnalysisRefused(
        RULE_EXCLUSION,
        f"the run {run}: its reason is registered for another result state"
        if entries
        else f"the run {run}: its reason is not a registered exclusion reason",
    )


def aggregate(
    metric: str, runs: Sequence[tuple[Mapping[str, Any], str | RunResult]]
) -> dict[str, Any]:
    """One figure of several analysis documents, with the median of three runs.

    ``runs`` gives each analysis document with the result of its run: a
    :class:`RunResult`, or the result state alone. A run in the state PASSED or
    FAILED is counted, whatever else its result states. A run in one of
    :data:`EXCLUDED_STATES` is not counted only when its reason is one that its
    exclusion reasons register for the experiment, the state, and the run. The
    aggregate then lists the run with that reason. A run in one of those states
    with the state alone has no registered reason, and it refuses the
    aggregate.

    A counted run with no figure leaves the aggregate with no median: the run
    is not dropped. The median is stated only for three counted runs.

    Raises:
        AnalysisRefused: the rule of an aggregate is not held, or a run that is
            not counted has no registered reason.
    """
    if metric not in AGGREGATE_METRICS:
        raise AnalysisRefused(RULE_AGGREGATE, "the metric is not registered")
    if not runs:
        raise AnalysisRefused(RULE_AGGREGATE, "no analysis document was given")
    listed: list[dict[str, Any]] = []
    results: list[RunResult] = []
    experiments: set[str] = set()
    for document, given in runs:
        result = given if isinstance(given, RunResult) else RunResult(given)
        state = result.state
        if not isinstance(document, dict) or document.get("schema") != SCHEMA:
            raise AnalysisRefused(
                RULE_AGGREGATE, "a document is not an analysis document"
            )
        experiment, run = document.get("experimentId"), document.get("runId")
        if (
            not isinstance(experiment, str)
            or not isinstance(run, str)
            or _IDENTIFIER.fullmatch(experiment) is None
            or _IDENTIFIER.fullmatch(run) is None
        ):
            raise AnalysisRefused(
                RULE_AGGREGATE, "a document states no usable identifiers"
            )
        if type(state) is not str or state not in RESULT_STATES:
            raise AnalysisRefused(
                RULE_AGGREGATE, f"the run {run} has an unregistered result state"
            )
        if result.preregistration is not None and not isinstance(
            result.preregistration, Mapping
        ):
            raise AnalysisRefused(
                RULE_AGGREGATE,
                f"the run {run} names its freeze record in another form",
            )
        if any(entry["runId"] == run for entry in listed):
            raise AnalysisRefused(RULE_AGGREGATE, f"the run {run} is given twice")
        experiments.add(experiment)
        results.append(result)
        listed.append(
            {
                "runId": run,
                "resultState": state,
                "counted": state not in EXCLUDED_STATES,
                "exclusion": None,
                "value": _figure(document, AGGREGATE_METRICS[metric]),
            }
        )
    if len(experiments) != 1:
        raise AnalysisRefused(
            RULE_AGGREGATE, "the documents name more than one experiment"
        )
    (experiment,) = experiments
    # A state alone does not leave a run out. Each run that is not counted is
    # held to a reason that its freeze record registers.
    for entry, result in zip(listed, results, strict=True):
        if not entry["counted"]:
            entry["exclusion"] = _exclusion(experiment, entry["runId"], result)
    values: list[int | None] = [e["value"] for e in listed if e["counted"]]
    present = sorted(value for value in values if value is not None)
    median: int | None = None
    reason: str | None = None
    if len(values) != 3:
        reason = "not-three-counted-runs"
    elif len(present) != 3:
        reason = "counted-run-without-value"
    else:
        median = present[1]
    return {
        "schema": AGGREGATE_SCHEMA,
        "experimentId": experiment,
        "metric": metric,
        "path": list(AGGREGATE_METRICS[metric]),
        "rule": AGGREGATE_RULE,
        "runs": sorted(listed, key=lambda entry: str(entry["runId"])),
        "countedRuns": len(values),
        "state": COMPUTED if reason is None else NOT_COMPUTABLE,
        "reason": reason,
        "median": median,
        "statement": AGGREGATE_STATEMENT,
    }
