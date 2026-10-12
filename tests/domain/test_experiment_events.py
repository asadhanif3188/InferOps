"""The log of the operator events of an experiment run, written and read back here.

``tools.experiment_events`` appends one line for each event to one log and holds
a stored log to its form. This suite writes each log in a temporary directory.
It contacts no cluster and no Git host.

The suite holds the tool to these properties.

*The tool takes the instant.* ``recordedAt`` is the clock of the host that ran
the command, in UTC, to one millisecond. No argument states it. An instant from
another clock is a second field that names its clock and keeps its resolution.

*A log holds no free text.* Each value is one of a registered vocabulary or has
a fixed form. A note, a name of a person, an address, a path, and a request
identifier are each refused, and nothing is written for an event that is
refused.

*A log is appended to and is not rewritten.* An event leaves each earlier byte
as it was. A closed log takes no event, and an existing file is not opened
again.

*A stored log can be read back.* ``read_log`` refuses a text that does not have
the form, and a log that is open.

*The caller record stays independent.* The tool imports no caller tool and
takes no request identifier.

These tests show what the tool does with a file. They do not show that an event
happened, and no test here is evidence of a real run.
"""

from __future__ import annotations

import ast
import copy
import inspect
import json
import re
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tools import experiment_events as events
from tools.experiment_events import core
from tools.experiment_events.__main__ import main
from tools.experiment_evidence import EVIDENCE_SUFFIXES, RAW, ROLES

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE = REPO_ROOT / "docs" / "environment" / "experiment-operator-events.md"
T0 = datetime(2026, 10, 12, 8, 0, 0, tzinfo=UTC)
COMMIT = "c" * 40
INSTANT = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z"


def ticking(start: datetime = T0, step: float = 1.5) -> Callable[[], datetime]:
    """A clock that states ``start`` and then moves by ``step`` seconds each call."""
    moments: Iterator[datetime] = (
        start + timedelta(seconds=step * n) for n in range(10_000)
    )
    return lambda: next(moments)


def opened(tmp_path: Path, clock: Callable[[], datetime] | None = None) -> Path:
    path = tmp_path / "operator-events.jsonl"
    events.open_log(path, "example-experiment", "run-1", now=clock or ticking())
    return path


def a_run(tmp_path: Path) -> Path:
    """A closed log with one event of each kind."""
    clock = ticking()
    path = opened(tmp_path, clock)
    for kind, actor, extra in USUAL_EVENTS:
        events.record(path, kind, actor, now=clock, **extra)
    events.close_log(path, now=clock)
    return path


USUAL_EVENTS: list[tuple[str, str, dict[str, Any]]] = [
    (
        "fault-injection-started",
        "control-process",
        {"code": "delete-runtime-pod", "subject": "pod/inferops-runtime-5d4f8-abcde"},
    ),
    ("fault-injection-finished", "control-process", {"code": "delete-runtime-pod"}),
    ("detection-reviewed", "operator", {}),
    ("reversal-decided", "operator", {}),
    ("reversal-created", "operator", {"commit": COMMIT}),
    (
        "reversal-accepted",
        "operator",
        {
            "commit": COMMIT,
            "occurred_at": "2026-10-12T10:00:07+02:00",
            "clock": "git-host",
        },
    ),
    ("manual-action", "operator", {"code": "restart-port-forward"}),
    ("run-aborted", "control-process", {"code": "caller-stream-lost"}),
]


def lines_of(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


# --------------------------------------------------------------------------
# The vocabulary
# --------------------------------------------------------------------------


def test_the_kinds_are_the_events_that_a_run_records() -> None:
    assert tuple(events.KINDS) == (
        "fault-injection-started",
        "fault-injection-finished",
        "detection-reviewed",
        "reversal-decided",
        "reversal-created",
        "reversal-accepted",
        "run-aborted",
        "manual-action",
    )
    assert events.ACTORS == ("operator", "control-process")
    operator_only, code_required = events.OPERATOR_ONLY, events.CODE_REQUIRED
    commit_required = events.COMMIT_REQUIRED
    assert operator_only == {
        "detection-reviewed",
        "reversal-decided",
        "manual-action",
    }
    assert code_required == {
        "fault-injection-started",
        "fault-injection-finished",
        "run-aborted",
        "manual-action",
    }
    assert commit_required == {"reversal-created", "reversal-accepted"}
    for group in (events.OPERATOR_ONLY, events.CODE_REQUIRED, events.COMMIT_REQUIRED):
        assert group <= set(events.KINDS)
    assert tuple(events.CLOCKS) == (
        "recording-host",
        "cluster",
        "git-host",
        "other-host",
    )
    assert events.SUBJECT_KINDS == ("pod", "deployment", "service", "application")
    assert {kind for kind, _, _ in USUAL_EVENTS} == set(events.KINDS)


# --------------------------------------------------------------------------
# A log, written
# --------------------------------------------------------------------------


def test_a_new_log_is_one_header_and_is_open(tmp_path: Path) -> None:
    path = opened(tmp_path)
    [header] = lines_of(path)
    assert header == {
        "record": "header",
        "schema": events.SCHEMA,
        "stream": "operator-events",
        "experimentId": "example-experiment",
        "runId": "run-1",
        "openedAt": "2026-10-12T08:00:00.000Z",
        "clock": header["clock"],
        "kinds": dict(events.KINDS),
        "omitted": list(events.OMITTED),
        "limitations": list(events.LIMITATIONS),
        "doesNotEstablish": list(events.DOES_NOT_ESTABLISH),
    }
    assert header["clock"]["skew"] == "not-measured"
    assert header["clock"]["recordedAt"]["resolution"] == "millisecond"
    log = events.read_log(path.read_text("utf-8"), allow_open=True)
    assert log.closed is False
    assert log.events == ()
    with pytest.raises(events.LogRefused) as refused:
        events.read_log(path.read_text("utf-8"))
    assert refused.value.rule == core.RULE_END


def test_an_event_states_the_instant_that_the_tool_took(tmp_path: Path) -> None:
    clock = ticking()
    path = opened(tmp_path, clock)
    event = events.record(
        path,
        "fault-injection-started",
        "control-process",
        code="delete-runtime-pod",
        subject="pod/inferops-runtime-5d4f8-abcde",
        now=clock,
    )
    assert event == {
        "record": "event",
        "index": 1,
        "kind": "fault-injection-started",
        "actor": "control-process",
        "recordedAt": "2026-10-12T08:00:01.500Z",
        "occurredAt": None,
        "code": "delete-runtime-pod",
        "subject": {"kind": "pod", "name": "inferops-runtime-5d4f8-abcde"},
        "commit": None,
    }
    assert lines_of(path)[1] == event


def test_the_default_clock_is_the_host_clock_in_utc_to_one_millisecond(
    tmp_path: Path,
) -> None:
    path = tmp_path / "log.jsonl"
    before = datetime.now(UTC) - timedelta(milliseconds=1)
    events.open_log(path, "e", "r")
    event = events.record(path, "reversal-decided", "operator")
    end = events.close_log(path)
    after = datetime.now(UTC)
    header = lines_of(path)[0]
    for stated in (header["openedAt"], event["recordedAt"], end["closedAt"]):
        assert re.fullmatch(INSTANT, stated, re.A), stated
        moment = datetime.strptime(stated, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
        assert before <= moment <= after


def test_no_argument_states_the_instant_of_the_record() -> None:
    """The command has no option for ``recordedAt``, and the function has no
    parameter of that name. The function does take a clock, ``now``."""
    parameters = inspect.signature(events.record).parameters
    assert "recorded_at" not in parameters
    assert set(parameters) == {
        "path",
        "kind",
        "actor",
        "code",
        "subject",
        "commit",
        "occurred_at",
        "clock",
        "now",
    }
    source = (REPO_ROOT / "tools/experiment_events/__main__.py").read_text("utf-8")
    options = set(re.findall(r'add_argument\(\s*"(--[a-z-]+)"', source))
    assert options == {
        "--experiment",
        "--run",
        "--kind",
        "--actor",
        "--code",
        "--subject",
        "--commit",
        "--occurred-at",
        "--clock",
    }


@pytest.mark.parametrize(
    "stated,value,resolution",
    [
        ("2026-10-12T08:00:07Z", "2026-10-12T08:00:07Z", "second"),
        ("2026-10-12T10:00:07+02:00", "2026-10-12T08:00:07Z", "second"),
        ("2026-10-12T08:00:07.250Z", "2026-10-12T08:00:07.250Z", "millisecond"),
        ("2026-10-12T08:00:07.2509Z", "2026-10-12T08:00:07.250Z", "millisecond"),
        ("2026-10-12T03:30:07.5-04:30", "2026-10-12T08:00:07.500Z", "millisecond"),
    ],
)
def test_an_instant_of_another_clock_is_normalised_and_keeps_its_resolution(
    tmp_path: Path, stated: str, value: str, resolution: str
) -> None:
    path = opened(tmp_path)
    event = events.record(
        path,
        "reversal-accepted",
        "operator",
        commit=COMMIT,
        occurred_at=stated,
        clock="git-host",
        now=ticking(),
    )
    assert event["occurredAt"] == {
        "value": value,
        "resolution": resolution,
        "clock": "git-host",
    }
    # It does not replace the instant of the record.
    assert event["recordedAt"] == "2026-10-12T08:00:00.000Z"
    events.close_log(path, now=ticking())
    events.read_log(path.read_text("utf-8"))


def test_each_event_leaves_each_earlier_byte_as_it_was(tmp_path: Path) -> None:
    clock = ticking()
    path = opened(tmp_path, clock)
    earlier = path.read_bytes()
    for kind, actor, extra in USUAL_EVENTS:
        events.record(path, kind, actor, now=clock, **extra)
        now = path.read_bytes()
        assert now.startswith(earlier)
        assert now.count(b"\n") == earlier.count(b"\n") + 1
        earlier = now
    events.close_log(path, now=clock)
    final = path.read_bytes()
    assert final.startswith(earlier)
    assert b"\r" not in final
    for line in final.decode("utf-8").splitlines():
        document = json.loads(line)
        assert list(document) == sorted(document)


def test_a_closed_log_states_its_counts_and_is_read_back(tmp_path: Path) -> None:
    path = a_run(tmp_path)
    log = events.read_log(path.read_text("utf-8"))
    assert log.closed is True
    assert [event["index"] for event in log.events] == list(range(1, 9))
    assert log.end == {
        "record": "end",
        "events": 8,
        "byKind": dict.fromkeys(events.KINDS, 1),
        "closedAt": "2026-10-12T08:00:13.500Z",
        "instantsOutOfOrder": [],
    }
    assert log.summary() == (
        "operator-events: 8 event(s): 1 fault-injection-started, "
        "1 fault-injection-finished, 1 detection-reviewed, 1 reversal-decided, "
        "1 reversal-created, 1 reversal-accepted, 1 run-aborted, 1 manual-action"
    )
    accepted = log.events[5]
    assert accepted["occurredAt"] == {
        "value": "2026-10-12T08:00:07Z",
        "resolution": "second",
        "clock": "git-host",
    }


def test_a_closed_log_takes_no_event_and_is_not_closed_twice(tmp_path: Path) -> None:
    path = a_run(tmp_path)
    before = path.read_bytes()
    with pytest.raises(events.EventRefused, match="closed") as refused:
        events.record(path, "reversal-decided", "operator")
    assert refused.value.rule == core.RULE_END
    with pytest.raises(events.EventRefused, match="closed"):
        events.close_log(path)
    assert path.read_bytes() == before


def test_an_existing_file_is_not_opened_again(tmp_path: Path) -> None:
    path = opened(tmp_path)
    before = path.read_bytes()
    with pytest.raises(events.EventRefused, match="the file exists") as refused:
        events.open_log(path, "example-experiment", "run-2")
    assert refused.value.rule == core.RULE_HEADER
    assert path.read_bytes() == before
    with pytest.raises(events.EventRefused, match="cannot be written"):
        events.open_log(tmp_path / "none" / "log.jsonl", "e", "r")


@pytest.mark.parametrize("identifier", ["", "has space", "../run", "a" * 64, "-x", 7])
def test_an_identifier_of_another_form_opens_no_log(
    tmp_path: Path, identifier: Any
) -> None:
    path = tmp_path / "log.jsonl"
    with pytest.raises(events.EventRefused):
        events.open_log(path, identifier, "run-1")
    with pytest.raises(events.EventRefused):
        events.open_log(path, "example-experiment", identifier)
    assert not path.exists()


def test_a_clock_that_was_set_back_is_named_in_the_end_line(tmp_path: Path) -> None:
    path = opened(tmp_path)
    for offset in (10, 20, 5, 6, 1):
        events.record(
            path,
            "reversal-decided",
            "operator",
            now=ticking(T0 + timedelta(seconds=offset)),
        )
    end = events.close_log(path, now=ticking())
    assert end["instantsOutOfOrder"] == [3, 5]
    events.read_log(path.read_text("utf-8"))


def test_a_full_log_takes_no_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(core, "MAX_EVENTS", 2)
    path = opened(tmp_path)
    events.record(path, "reversal-decided", "operator")
    events.record(path, "reversal-decided", "operator")
    before = path.read_bytes()
    with pytest.raises(events.EventRefused, match="takes no more") as refused:
        events.record(path, "reversal-decided", "operator")
    assert refused.value.rule == core.RULE_SEQUENCE
    assert path.read_bytes() == before
    assert events.MAX_EVENTS == 500


# --------------------------------------------------------------------------
# An event that is refused
# --------------------------------------------------------------------------

REFUSED_EVENTS: list[tuple[str, str, str, dict[str, Any], str]] = [
    ("kind", "pod-deleted", "operator", {}, core.RULE_VOCABULARY),
    ("actor", "reversal-decided", "someone", {}, core.RULE_VOCABULARY),
    (
        "review-by-process",
        "detection-reviewed",
        "control-process",
        {},
        core.RULE_VOCABULARY,
    ),
    (
        "decision-by-process",
        "reversal-decided",
        "control-process",
        {},
        core.RULE_VOCABULARY,
    ),
    (
        "manual-by-process",
        "manual-action",
        "control-process",
        {"code": "x"},
        core.RULE_VOCABULARY,
    ),
    (
        "fault-no-code",
        "fault-injection-started",
        "control-process",
        {},
        core.RULE_REQUIRED,
    ),
    (
        "finished-no-code",
        "fault-injection-finished",
        "operator",
        {},
        core.RULE_REQUIRED,
    ),
    ("abort-no-code", "run-aborted", "operator", {}, core.RULE_REQUIRED),
    ("manual-no-code", "manual-action", "operator", {}, core.RULE_REQUIRED),
    ("created-no-commit", "reversal-created", "operator", {}, core.RULE_REQUIRED),
    ("accepted-no-commit", "reversal-accepted", "operator", {}, core.RULE_REQUIRED),
    (
        "commit-on-decision",
        "reversal-decided",
        "operator",
        {"commit": COMMIT},
        core.RULE_REQUIRED,
    ),
    (
        "short-commit",
        "reversal-created",
        "operator",
        {"commit": "c0ffee1"},
        core.RULE_FORM,
    ),
    (
        "upper-commit",
        "reversal-created",
        "operator",
        {"commit": "C" * 40},
        core.RULE_FORM,
    ),
    (
        "code-sentence",
        "manual-action",
        "operator",
        {"code": "restarted the port forward by hand"},
        core.RULE_FORM,
    ),
    ("code-upper", "run-aborted", "operator", {"code": "Abort"}, core.RULE_FORM),
    ("code-long", "run-aborted", "operator", {"code": "a" * 64}, core.RULE_FORM),
    ("code-empty", "run-aborted", "operator", {"code": ""}, core.RULE_FORM),
    (
        "code-email",
        "manual-action",
        "operator",
        {"code": "someone@example.invalid"},
        core.RULE_FORM,
    ),
    (
        "code-path",
        "manual-action",
        "operator",
        {"code": "/" + "home/someone/notes"},
        core.RULE_FORM,
    ),
    (
        "code-line-break",
        "manual-action",
        "operator",
        {"code": "restart\nforged-line"},
        core.RULE_FORM,
    ),
    (
        "subject-no-kind",
        "reversal-decided",
        "operator",
        {"subject": "inferops-runtime"},
        core.RULE_VOCABULARY,
    ),
    (
        "subject-kind",
        "reversal-decided",
        "operator",
        {"subject": "secret/token"},
        core.RULE_VOCABULARY,
    ),
    (
        "subject-node",
        "reversal-decided",
        "operator",
        {"subject": "node/desktop-control-plane"},
        core.RULE_VOCABULARY,
    ),
    (
        "subject-name",
        "reversal-decided",
        "operator",
        {"subject": "pod/Has Space"},
        core.RULE_FORM,
    ),
    (
        "subject-address",
        "reversal-decided",
        "operator",
        {"subject": "service/https://user:secret@example.invalid"},
        core.RULE_FORM,
    ),
    (
        "subject-empty",
        "reversal-decided",
        "operator",
        {"subject": "pod/"},
        core.RULE_FORM,
    ),
    (
        "instant-no-clock",
        "reversal-decided",
        "operator",
        {"occurred_at": "2026-10-12T08:00:07Z"},
        core.RULE_INSTANT,
    ),
    (
        "clock-no-instant",
        "reversal-decided",
        "operator",
        {"clock": "git-host"},
        core.RULE_INSTANT,
    ),
    (
        "clock-other",
        "reversal-decided",
        "operator",
        {"occurred_at": "2026-10-12T08:00:07Z", "clock": "my-watch"},
        core.RULE_VOCABULARY,
    ),
    (
        "instant-no-zone",
        "reversal-decided",
        "operator",
        {"occurred_at": "2026-10-12T08:00:07", "clock": "git-host"},
        core.RULE_INSTANT,
    ),
    (
        "instant-words",
        "reversal-decided",
        "operator",
        {"occurred_at": "about ten past eight", "clock": "git-host"},
        core.RULE_INSTANT,
    ),
    (
        "instant-no-date",
        "reversal-decided",
        "operator",
        {"occurred_at": "2026-02-30T08:00:07Z", "clock": "git-host"},
        core.RULE_INSTANT,
    ),
]


@pytest.mark.parametrize(
    "kind,actor,extra,rule",
    [case[1:] for case in REFUSED_EVENTS],
    ids=[case[0] for case in REFUSED_EVENTS],
)
def test_an_event_that_does_not_hold_a_rule_is_refused_and_nothing_is_written(
    tmp_path: Path, kind: str, actor: str, extra: dict[str, Any], rule: str
) -> None:
    path = opened(tmp_path)
    before = path.read_bytes()
    with pytest.raises(events.EventRefused) as refused:
        events.record(path, kind, actor, **extra)
    assert refused.value.rule == rule
    assert path.read_bytes() == before
    # The refusal repeats no value that the caller gave.
    for value in extra.values():
        if len(value) > 12:
            assert value not in str(refused.value)


def test_a_file_that_is_not_an_open_log_takes_no_event(tmp_path: Path) -> None:
    missing = tmp_path / "none.jsonl"
    with pytest.raises(events.EventRefused) as refused:
        events.record(missing, "reversal-decided", "operator")
    assert refused.value.rule == core.RULE_UNREADABLE
    assert not missing.exists()
    other = tmp_path / "other.jsonl"
    other.write_text('{"record":"reading"}\n', "utf-8")
    with pytest.raises(events.EventRefused) as refused:
        events.record(other, "reversal-decided", "operator")
    assert refused.value.rule == core.RULE_HEADER
    assert other.read_text("utf-8") == '{"record":"reading"}\n'
    # A last line that was not written whole is not appended to.
    torn = opened_in(tmp_path / "torn")
    torn.write_bytes(torn.read_bytes() + b'{"record":"event","index":1')
    before = torn.read_bytes()
    with pytest.raises(events.EventRefused) as refused:
        events.record(torn, "reversal-decided", "operator")
    assert refused.value.rule == core.RULE_UNREADABLE
    assert torn.read_bytes() == before


def opened_in(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return opened(directory)


# --------------------------------------------------------------------------
# A stored log, read back
# --------------------------------------------------------------------------

Change = Callable[[list[dict[str, Any]]], Any]


def _set(index: int, *path: Any, value: Any) -> Change:
    def change(lines: list[dict[str, Any]]) -> None:
        target: Any = lines[index]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def _drop(index: int, name: str) -> Change:
    return lambda lines: lines[index].pop(name)


# Line 1 is fault-injection-started, line 3 is detection-reviewed, line 5 is
# reversal-created, and line 6 is reversal-accepted with an occurredAt.
STORED_CASES: list[tuple[str, Change, str]] = [
    ("header-missing", lambda lines: lines.pop(0), core.RULE_HEADER),
    ("other-schema", _set(0, "schema", value="x"), core.RULE_HEADER),
    ("other-stream", _set(0, "stream", value="telemetry"), core.RULE_HEADER),
    ("bad-experiment", _set(0, "experimentId", value="a b"), core.RULE_HEADER),
    ("bad-run", _set(0, "runId", value=7), core.RULE_HEADER),
    ("header-extra", _set(0, "operator", value="a person"), core.RULE_MEMBERS),
    ("header-short", _drop(0, "limitations"), core.RULE_MEMBERS),
    ("event-note", _set(1, "note", value="free text"), core.RULE_MEMBERS),
    ("event-request", _set(1, "requestId", value="r-1"), core.RULE_MEMBERS),
    ("event-short", _drop(1, "commit"), core.RULE_MEMBERS),
    ("end-extra", _set(-1, "note", value="x"), core.RULE_MEMBERS),
    (
        "occurred-extra",
        _set(6, "occurredAt", "note", value="x"),
        core.RULE_MEMBERS,
    ),
    ("occurred-text", _set(6, "occurredAt", value="08:00"), core.RULE_MEMBERS),
    (
        "subject-extra",
        _set(1, "subject", "namespace", value="inferops-release"),
        core.RULE_MEMBERS,
    ),
    ("subject-text", _set(1, "subject", value="pod/x"), core.RULE_MEMBERS),
    ("not-an-event", _set(2, "record", value="reading"), core.RULE_SEQUENCE),
    ("index-gap", _set(2, "index", value=5), core.RULE_SEQUENCE),
    ("index-float", _set(2, "index", value=2.0), core.RULE_SEQUENCE),
    ("index-true", _set(1, "index", value=True), core.RULE_SEQUENCE),
    ("line-after-end", lambda lines: lines.append(dict(lines[1])), core.RULE_END),
    ("kind", _set(3, "kind", value="pod-deleted"), core.RULE_VOCABULARY),
    ("kind-list", _set(3, "kind", value=["detection-reviewed"]), core.RULE_VOCABULARY),
    ("actor", _set(3, "actor", value="someone"), core.RULE_VOCABULARY),
    (
        "review-by-process",
        _set(3, "actor", value="control-process"),
        core.RULE_VOCABULARY,
    ),
    ("subject-kind", _set(1, "subject", "kind", value="secret"), core.RULE_VOCABULARY),
    ("clock", _set(6, "occurredAt", "clock", value="my-watch"), core.RULE_VOCABULARY),
    (
        "recorded-form",
        _set(1, "recordedAt", value="2026-10-12T08:00:01Z"),
        core.RULE_INSTANT,
    ),
    ("recorded-none", _set(1, "recordedAt", value=None), core.RULE_INSTANT),
    ("opened-form", _set(0, "openedAt", value="today"), core.RULE_INSTANT),
    ("closed-form", _set(-1, "closedAt", value=1791792000), core.RULE_INSTANT),
    (
        "occurred-offset",
        _set(6, "occurredAt", "value", value="2026-10-12T10:00:07+02:00"),
        core.RULE_INSTANT,
    ),
    (
        "occurred-resolution",
        _set(6, "occurredAt", "resolution", value="millisecond"),
        core.RULE_INSTANT,
    ),
    (
        "occurred-no-date",
        _set(6, "occurredAt", "value", value="2026-02-30T08:00:07Z"),
        core.RULE_INSTANT,
    ),
    ("code-sentence", _set(1, "code", value="deleted one pod"), core.RULE_FORM),
    ("code-number", _set(1, "code", value=7), core.RULE_FORM),
    ("subject-name", _set(1, "subject", "name", value="Pod One"), core.RULE_FORM),
    ("commit-short", _set(5, "commit", value="c0ffee1"), core.RULE_FORM),
    ("fault-no-code", _set(1, "code", value=None), core.RULE_REQUIRED),
    ("created-no-commit", _set(5, "commit", value=None), core.RULE_REQUIRED),
    ("commit-on-review", _set(3, "commit", value=COMMIT), core.RULE_REQUIRED),
    ("end-missing", lambda lines: lines.pop(), core.RULE_END),
    ("end-in-the-middle", _set(4, "record", value="end"), core.RULE_SEQUENCE),
    (
        "clock-list",
        _set(6, "occurredAt", "clock", value=["git-host"]),
        core.RULE_VOCABULARY,
    ),
    ("count-events", _set(-1, "events", value=7), core.RULE_COUNTS),
    ("count-float", _set(-1, "events", value=8.0), core.RULE_COUNTS),
    ("count-kind", _set(-1, "byKind", "run-aborted", value=2), core.RULE_COUNTS),
    ("count-list", _set(-1, "byKind", value=[]), core.RULE_COUNTS),
    ("count-true", _set(-1, "byKind", "run-aborted", value=True), core.RULE_COUNTS),
    ("out-of-order", _set(-1, "instantsOutOfOrder", value=[2]), core.RULE_COUNTS),
    (
        "set-back-unstated",
        _set(2, "recordedAt", value="2026-10-12T07:00:00.000Z"),
        core.RULE_COUNTS,
    ),
]


@pytest.mark.parametrize(
    "change,rule", [case[1:] for case in STORED_CASES], ids=[c[0] for c in STORED_CASES]
)
def test_a_text_that_does_not_have_the_form_of_a_log_is_refused(
    tmp_path: Path, change: Change, rule: str
) -> None:
    lines = copy.deepcopy(lines_of(a_run(tmp_path)))
    assert [lines[n]["kind"] for n in (1, 3, 5, 6)] == [
        "fault-injection-started",
        "detection-reviewed",
        "reversal-created",
        "reversal-accepted",
    ]
    events.read_log(events.log_text(lines))
    change(lines)
    with pytest.raises(events.LogRefused) as refused:
        events.read_log(events.log_text(lines))
    assert refused.value.rule == rule


@pytest.mark.parametrize(
    "text",
    [
        "not json\n",
        "[]\n",
        "7\n",
        '{"record":"header","record":"header"}\n',
        '{"record":"header"}',
        "\n",
        "[" * 100_000 + "\n",
    ],
    ids=["text", "list", "number", "twice", "no-line-feed", "empty-line", "deep"],
)
def test_a_text_that_is_not_lines_of_objects_is_refused(text: str) -> None:
    with pytest.raises(events.LogRefused) as refused:
        events.read_log(text)
    assert refused.value.rule == core.RULE_UNREADABLE


def test_an_empty_text_is_not_a_log() -> None:
    with pytest.raises(events.LogRefused) as refused:
        events.read_log("")
    assert refused.value.rule == core.RULE_HEADER


def test_each_rule_has_a_case_that_refuses_by_it() -> None:
    covered = {rule for _, _, rule in STORED_CASES} | {core.RULE_UNREADABLE}
    assert covered == set(events.RULES)
    assert len(events.RULES) == 10
    for rule in events.RULES:
        assert rule.startswith("events-"), rule


def test_a_stored_log_with_more_events_than_the_bound_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = a_run(tmp_path).read_text("utf-8")
    monkeypatch.setattr(core, "MAX_EVENTS", 7)
    with pytest.raises(events.LogRefused) as refused:
        events.read_log(text)
    assert refused.value.rule == core.RULE_SEQUENCE


def test_a_log_with_carriage_returns_is_read(tmp_path: Path) -> None:
    """A checkout that converts line ends does not make a log another log."""
    text = a_run(tmp_path).read_text("utf-8")
    log = events.read_log(text.replace("\n", "\r\n"))
    assert len(log.events) == 8


# --------------------------------------------------------------------------
# What a log leaves out
# --------------------------------------------------------------------------


def test_no_member_of_an_event_takes_free_text(tmp_path: Path) -> None:
    """Each text value of each event has a registered value or a fixed form."""
    forms = {
        "kind": re.compile("|".join(events.KINDS)),
        "actor": re.compile("|".join(events.ACTORS)),
        "recordedAt": re.compile(INSTANT, re.A),
        "code": re.compile(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?"),
        "commit": re.compile(r"[0-9a-f]{40}"),
        "subject.kind": re.compile("|".join(events.SUBJECT_KINDS)),
        "subject.name": re.compile(r"[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?"),
        "occurredAt.value": re.compile(r"[0-9T:.Z-]{20,24}"),
        "occurredAt.resolution": re.compile("second|millisecond"),
        "occurredAt.clock": re.compile("|".join(events.CLOCKS)),
        "record": re.compile("event"),
    }
    seen = set()
    for event in events.read_log(a_run(tmp_path).read_text("utf-8")).events:
        for name, value in event.items():
            members = value.items() if isinstance(value, dict) else [(None, value)]
            for inner, stated in members:
                key = name if inner is None else f"{name}.{inner}"
                if isinstance(stated, str):
                    assert forms[key].fullmatch(stated), (key, stated)
                    seen.add(key)
                else:
                    assert stated is None or type(stated) is int, key
    assert seen == set(forms)


def test_the_tool_reads_no_caller_record_and_takes_no_request_identifier() -> None:
    """The caller record has another source, and no event is derived from it."""
    package = REPO_ROOT / "tools" / "experiment_events"
    for path in sorted(package.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        imported = set()
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                imported |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for name in imported:
            assert "reliability_runner" not in name, path.name
            assert "llm_load" not in name, path.name
            assert not name.startswith(("urllib", "http", "socket", "subprocess")), (
                path.name
            )
        assert "request_id" not in text, path.name
        assert "requestId" not in text, path.name


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_command_opens_records_closes_and_checks(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "operator-events.jsonl"
    assert main(["open", str(path), "--experiment", "example", "--run", "run-1"]) == 0
    assert re.fullmatch(
        rf"OPENED   operator-events\.jsonl at {INSTANT}\n", capfd.readouterr().out, re.A
    )
    assert main(["check", str(path)]) == 3
    assert "events-end-missing" in capfd.readouterr().err
    assert (
        main(
            [
                "record",
                str(path),
                "--kind",
                "fault-injection-started",
                "--actor",
                "control-process",
                "--code",
                "delete-runtime-pod",
                "--subject",
                "pod/inferops-runtime-5d4f8-abcde",
            ]
        )
        == 0
    )
    printed = json.loads(capfd.readouterr().out)
    assert printed == lines_of(path)[1]
    assert printed["subject"] == {"kind": "pod", "name": "inferops-runtime-5d4f8-abcde"}
    assert (
        main(
            [
                "record",
                str(path),
                "--kind",
                "reversal-accepted",
                "--actor",
                "operator",
                "--commit",
                COMMIT,
                "--occurred-at",
                "2026-10-12T10:00:07+02:00",
                "--clock",
                "git-host",
            ]
        )
        == 0
    )
    assert json.loads(capfd.readouterr().out)["occurredAt"]["value"] == (
        "2026-10-12T08:00:07Z"
    )
    assert main(["close", str(path)]) == 0
    assert json.loads(capfd.readouterr().out)["events"] == 2
    assert main(["check", str(path)]) == 0
    assert capfd.readouterr().out == (
        "READ     operator-events: 2 event(s): 1 fault-injection-started, "
        "1 reversal-accepted\n"
    )
    assert b"\r" not in path.read_bytes()


def test_the_command_refuses_with_exit_3_and_writes_nothing(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "log.jsonl"
    assert (
        main(["record", str(path), "--kind", "run-aborted", "--actor", "operator"]) == 3
    )
    assert "REFUSED  events-log-unreadable" in capfd.readouterr().err
    assert not path.exists()
    assert main(["open", str(path), "--experiment", "e", "--run", "r"]) == 0
    before = path.read_bytes()
    assert main(["open", str(path), "--experiment", "e", "--run", "r"]) == 3
    assert (
        main(["record", str(path), "--kind", "run-aborted", "--actor", "operator"]) == 3
    )
    assert "events-member-required" in capfd.readouterr().err
    assert (
        main(
            [
                "record",
                str(path),
                "--kind",
                "manual-action",
                "--actor",
                "operator",
                "--code",
                "I restarted the forward",
            ]
        )
        == 3
    )
    captured = capfd.readouterr()
    assert "events-value-malformed" in captured.err
    assert "restarted" not in captured.err
    assert path.read_bytes() == before
    binary = tmp_path / "binary.jsonl"
    binary.write_bytes(b"\xff\xfe")
    assert main(["check", str(binary), str(tmp_path / "none")]) == 3
    captured = capfd.readouterr()
    assert "REFUSED  binary.jsonl: events-log-unreadable" in captured.err
    assert "REFUSED  none: events-log-unreadable" in captured.err


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["open"],
        ["open", "x"],
        ["record", "x"],
        ["record", "x", "--kind", "pod-deleted", "--actor", "operator"],
        ["record", "x", "--kind", "run-aborted", "--actor", "someone"],
        ["record", "x", "--kind", "run-aborted", "--actor", "operator", "--note", "n"],
        [
            "record",
            "x",
            "--kind",
            "run-aborted",
            "--actor",
            "operator",
            "--recorded-at",
            "2026-10-12T08:00:00.000Z",
        ],
        [
            "record",
            "x",
            "--kind",
            "run-aborted",
            "--actor",
            "operator",
            "--clock",
            "sun",
        ],
        ["check"],
        ["close"],
    ],
)
def test_arguments_that_are_not_usable_exit_2(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(arguments)
    assert stopped.value.code == 2


# --------------------------------------------------------------------------
# The evidence layout and the page
# --------------------------------------------------------------------------


def test_the_log_is_a_registered_raw_role_with_a_hashed_suffix() -> None:
    assert events.ROLE == "operator-events"
    assert ROLES[events.ROLE].kind == RAW
    assert ".jsonl" in EVIDENCE_SUFFIXES


def _flat(text: str) -> str:
    return " ".join(text.replace("`", "").split())


def test_the_page_publishes_each_kind_rule_limit_and_boundary_of_the_tool() -> None:
    page = _flat(PAGE.read_text(encoding="utf-8"))
    for rule, statement in events.RULES.items():
        assert rule in page, rule
        assert _flat(statement) in page, rule
    for statement in (
        *events.LIMITATIONS,
        *events.DOES_NOT_ESTABLISH,
        *events.OMITTED,
        *events.KINDS.values(),
        *events.CLOCKS.values(),
    ):
        assert _flat(statement) in page, statement
    for name in (
        *events.KINDS,
        *events.ACTORS,
        *events.CLOCKS,
        *events.SUBJECT_KINDS,
        events.ROLE,
        events.SCHEMA,
    ):
        assert re.search(
            rf"(?<![A-Za-z0-9-]){re.escape(name)}(?![A-Za-z0-9-])", page
        ), name
    assert str(events.MAX_EVENTS) in page


# --------------------------------------------------------------------------
# What the independent reviews found
# --------------------------------------------------------------------------

HEADER_CASES: list[tuple[str, Change]] = [
    ("clock-text", _set(0, "clock", value="whatever text")),
    ("clock-skew", _set(0, "clock", "skew", value="measured")),
    ("kinds-sentence", _set(0, "kinds", value={"x": "a free sentence"})),
    ("kinds-changed", _set(0, "kinds", "run-aborted", value="Another meaning.")),
    ("omitted-note", _set(0, "omitted", value=["A note that names a person."])),
    ("limitations-short", lambda lines: lines[0]["limitations"].pop()),
    ("boundaries-empty", _set(0, "doesNotEstablish", value=[])),
    ("boundaries-number", _set(0, "doesNotEstablish", value=5)),
]


@pytest.mark.parametrize(
    "change", [case[1] for case in HEADER_CASES], ids=[case[0] for case in HEADER_CASES]
)
def test_a_stored_header_with_a_text_that_is_not_the_tools_is_refused(
    tmp_path: Path, change: Change
) -> None:
    """The first commit read the names of these five members and not their text."""
    lines = copy.deepcopy(lines_of(a_run(tmp_path)))
    change(lines)
    with pytest.raises(events.LogRefused) as refused:
        events.read_log(events.log_text(lines))
    assert refused.value.rule == core.RULE_HEADER
    assert "person" not in str(refused.value)


def test_a_log_with_such_a_header_takes_no_event(tmp_path: Path) -> None:
    path = opened(tmp_path)
    [header] = lines_of(path)
    header["omitted"] = ["A note that names a person."]
    path.write_bytes(events.log_text([header]).encode("utf-8"))
    before = path.read_bytes()
    with pytest.raises(events.EventRefused) as refused:
        events.record(path, "reversal-decided", "operator")
    assert refused.value.rule == core.RULE_HEADER
    assert path.read_bytes() == before


def test_an_out_of_order_list_with_a_number_of_another_type_is_refused(
    tmp_path: Path,
) -> None:
    """The first commit read 2.0 as 2."""
    path = opened(tmp_path)
    for offset in (10, 5):
        events.record(
            path,
            "reversal-decided",
            "operator",
            now=ticking(T0 + timedelta(seconds=offset)),
        )
    events.close_log(path, now=ticking())
    lines = lines_of(path)
    assert lines[-1]["instantsOutOfOrder"] == [2]
    lines[-1]["instantsOutOfOrder"] = [2.0]
    with pytest.raises(events.LogRefused) as refused:
        events.read_log(events.log_text(lines))
    assert refused.value.rule == core.RULE_COUNTS


def test_a_file_that_cannot_be_written_to_refuses_and_does_not_raise(
    tmp_path: Path, capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first commit raised from the write, and the command exited 1."""
    path = opened(tmp_path)
    before = path.read_bytes()
    original = Path.open

    def refuse_append(self: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if "a" in mode:
            raise PermissionError(13, "Permission denied")
        return original(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", refuse_append)
    with pytest.raises(events.EventRefused) as refused:
        events.record(path, "reversal-decided", "operator")
    assert refused.value.rule == core.RULE_UNREADABLE
    with pytest.raises(events.EventRefused):
        events.close_log(path)
    for arguments in (
        ["record", str(path), "--kind", "reversal-decided", "--actor", "operator"],
        ["close", str(path)],
    ):
        assert main(arguments) == 3
        assert "cannot be written to" in capfd.readouterr().err
    assert path.read_bytes() == before


def test_the_function_takes_a_clock_and_the_command_passes_none(tmp_path: Path) -> None:
    """What "the tool takes the instant" holds for, exactly.

    The function has a parameter for a clock, and a caller of the function can
    state any instant with it. The command has no option for it, and it calls
    the function with no clock.
    """
    path = opened(tmp_path)
    stated = events.record(
        path,
        "reversal-decided",
        "operator",
        now=lambda: datetime(1999, 1, 1, tzinfo=UTC),
    )
    assert stated["recordedAt"] == "1999-01-01T00:00:00.000Z"
    source = (REPO_ROOT / "tools/experiment_events/__main__.py").read_text("utf-8")
    assert "now=" not in source
    assert "now" in inspect.signature(events.record).parameters


@pytest.mark.parametrize(
    "extra",
    [
        {"subject": 5},
        {"subject": ["pod", "x"]},
        {"subject": b"pod/x"},
        {"clock": [], "occurred_at": "2026-10-12T08:00:07Z"},
        {"clock": {}, "occurred_at": "2026-10-12T08:00:07Z"},
        {"clock": "git-host", "occurred_at": 7},
        {"code": 7, "kind": "run-aborted"},
        {"commit": ["c"], "kind": "reversal-created"},
    ],
)
def test_an_argument_of_another_type_is_refused_and_does_not_raise(
    tmp_path: Path, extra: dict[str, Any]
) -> None:
    path = opened(tmp_path)
    before = path.read_bytes()
    kind = extra.pop("kind", "reversal-decided")
    with pytest.raises(events.EventRefused):
        events.record(path, kind, "operator", **extra)
    assert path.read_bytes() == before
