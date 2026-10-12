"""The operator events of one experiment run, as one log.

An experiment run has events that no cluster object and no metric holds: the
process that controls the run injects a fault, an operator reviews a detection,
an operator decides a reversal, a reversal is created and accepted, a run is
aborted, and an operator acts by hand. This module writes one log of those
events for one run, and it reads a stored log back.

**One line for each event, and the tool takes the instant.** :func:`record`
appends one event and states ``recordedAt``: the wall clock of the host that
ran the command, in UTC, to one millisecond. The caller cannot state it. So the
process that issues a fault command and records the event beside it states both
on one clock.

**An instant from another clock is a second field.** An event that happened on
another system, such as the acceptance of a commit on a Git host, can state
``occurredAt`` with the clock that it is on. It is normalised to UTC and keeps
the resolution that it was stated with. It does not replace ``recordedAt``.

**A log holds no free text.** Each value of an event is one of a registered
vocabulary or has a fixed form: a kind, an actor, a code, a subject that is a
resource kind and a name, a commit identifier, and an instant. No option takes
a note, a name of a person, a command line, or a request identifier.

**A log is not caller truth, and it is not a detection.** It states what was
recorded and when. :data:`DOES_NOT_ESTABLISH` is part of every log.

See docs/environment/experiment-operator-events.md and
tests/domain/test_experiment_events.py.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from tools.experiment_timeline import (
    REFUSED_EXIT,
    cluster_instant,
    collector_instant,
    format_instant,
)

__all__ = [
    "ACTORS",
    "CLOCKS",
    "CODE_REQUIRED",
    "COMMIT_REQUIRED",
    "DOES_NOT_ESTABLISH",
    "KINDS",
    "LIMITATIONS",
    "MAX_EVENTS",
    "OMITTED",
    "OPERATOR_ONLY",
    "REFUSED_EXIT",
    "ROLE",
    "RULES",
    "SCHEMA",
    "SUBJECT_KINDS",
    "EventRefused",
    "Log",
    "LogRefused",
    "close_log",
    "log_text",
    "open_log",
    "read_log",
    "record",
]

#: The schema name of each line of a log.
SCHEMA: Final = "inferops.io/experiment-operator-events/v1alpha1"

#: The name of the stream. It is a registered raw role of the evidence layout.
ROLE: Final = "operator-events"

#: The largest number of events that one log holds.
MAX_EVENTS: Final = 500

#: The kinds of event, with what each one records.
KINDS: Final[Mapping[str, str]] = {
    "fault-injection-started": (
        "The control of the run is about to issue the command that injects the "
        "fault. Record it before the command."
    ),
    "fault-injection-finished": (
        "The command that injects the fault returned. Record it after the command."
    ),
    "detection-reviewed": (
        "An operator reviewed the signals and judged that the declared problem is "
        "present."
    ),
    "reversal-decided": "An operator decided to reverse the change.",
    "reversal-created": "The commit that reverses the change exists.",
    "reversal-accepted": (
        "The commit that reverses the change was accepted into the branch that "
        "the delivery path follows."
    ),
    "run-aborted": "The run was aborted.",
    "manual-action": (
        "An operator acted on the environment by hand, outside the procedure of "
        "the run."
    ),
}

#: Who recorded an event. ``operator`` is a person. ``control-process`` is the
#: program that controls the run. Neither names a person.
ACTORS: Final = ("operator", "control-process")

#: The kinds that only an operator records. Each is a judgement or an act of a
#: person.
OPERATOR_ONLY: Final = frozenset(
    {"detection-reviewed", "reversal-decided", "manual-action"}
)

#: The kinds that state a code. The code names the fault, the reason of the
#: abort, or the action, as the frozen record of the experiment registers it.
CODE_REQUIRED: Final = frozenset(
    {
        "fault-injection-started",
        "fault-injection-finished",
        "run-aborted",
        "manual-action",
    }
)

#: The kinds that state the commit of the reversal.
COMMIT_REQUIRED: Final = frozenset({"reversal-created", "reversal-accepted"})

#: The clocks that an ``occurredAt`` can be on.
CLOCKS: Final[Mapping[str, str]] = {
    "recording-host": "The host that ran the command, at an earlier instant.",
    "cluster": "A component of the cluster.",
    "git-host": "The host of the Git repository.",
    "other-host": "Another host that the page of the run names.",
}

#: The resource kinds that a subject can name.
SUBJECT_KINDS: Final = ("pod", "deployment", "service", "application")

#: What a log leaves out, on purpose.
OMITTED: Final[tuple[str, ...]] = (
    "The name, the account, and the address of a person. An actor is one of two roles.",
    "Each note and each description. An event states a code and no sentence.",
    "The command line of a fault and the text that a command printed.",
    "Each request identifier and each correlation identifier of a caller.",
    "The address of a repository and the name of a branch.",
)

#: The limits of a log.
LIMITATIONS: Final[tuple[str, ...]] = (
    "The instant recordedAt is the wall clock of the host that ran the record "
    "command, in UTC, to one millisecond. It is the instant at which the event "
    "was recorded. It is not the instant at which the event happened.",
    "A wall clock can be set while a run is in progress. The end line names each "
    "event that was recorded at an earlier instant than the event before it.",
    "A fault is injected between the event fault-injection-started and the event "
    "fault-injection-finished, when the control of the run recorded the first "
    "before the command and the second after it. Nothing checks that order, and "
    "no instant inside that interval is established.",
    "The instant occurredAt is what the person or the program that recorded the "
    "event stated. It is on the clock that the event names, it keeps the "
    "resolution that it was stated with, and nothing compares it with that "
    "clock.",
    "The difference between the clock of the recording host and any other clock "
    "is not measured.",
    "An event of an operator is recorded when the operator runs the command. The "
    "time between a judgement and its record is not measured.",
    "A code and a name are free within their form. The form is not a check for a "
    "secret, and it does not show that the frozen record of an experiment "
    "registers the code.",
    "One process appends to a log. Two processes that append at one time are not "
    "ordered, and the tool does not lock the file.",
    f"A log holds at most {MAX_EVENTS} events.",
)

#: What no log establishes.
DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "That a caller obtained or lost a completion at any instant. An event is a "
    "record of the control of the run or of an operator. It is not a request "
    "that a caller sent and had answered.",
    "That a fault took effect, or when. An event states that a command was about "
    "to be issued and that it returned.",
    "That a detection was correct. The event detection-reviewed states that an "
    "operator recorded a judgement.",
    "That a reversal reached the cluster. The event reversal-accepted states "
    "that an acceptance was recorded, and a commit identifier is what the "
    "recorder stated.",
    "That no other action was taken. A log holds each event that was recorded, "
    "and an action that nobody recorded is in no log.",
    "A detection lag, a decision time, a recovery time, or any other metric of "
    "an experiment. A log is evidence that an analysis reads. This module "
    "computes no metric and gives no verdict.",
)

RULE_UNREADABLE: Final = "events-log-unreadable"
RULE_HEADER: Final = "events-header-unsupported"
RULE_MEMBERS: Final = "events-members-unsupported"
RULE_SEQUENCE: Final = "events-event-out-of-sequence"
RULE_VOCABULARY: Final = "events-vocabulary-unregistered"
RULE_INSTANT: Final = "events-instant-invalid"
RULE_FORM: Final = "events-value-malformed"
RULE_REQUIRED: Final = "events-member-required"
RULE_END: Final = "events-end-missing"
RULE_COUNTS: Final = "events-counts-differ"

#: Each rule that :func:`read_log` holds a log to, with its statement.
RULES: Final[Mapping[str, str]] = {
    RULE_UNREADABLE: (
        "A log is UTF-8 text, and each line ends with a line feed. Each line is "
        "one JSON object with no member stated twice."
    ),
    RULE_HEADER: (
        "The first line is the header. It states the schema, the stream name, an "
        "experiment identifier, a run identifier, and the instant at which the "
        "log was opened, each in its form."
    ),
    RULE_MEMBERS: "Each line has exactly the members of its record.",
    RULE_SEQUENCE: (
        "Each line between the header and the end line is an event, the events "
        f"are numbered from 1 with no gap, and a log holds at most {MAX_EVENTS}."
    ),
    RULE_VOCABULARY: (
        "Each event states a registered kind and a registered actor. A kind that "
        "is a judgement or an act of a person states the actor operator. A "
        "subject states a registered resource kind, and an occurredAt states a "
        "registered clock."
    ),
    RULE_INSTANT: (
        "Each recordedAt, the openedAt, and the closedAt is UTC to one "
        "millisecond in the one registered form. Each occurredAt is UTC with a "
        "resolution of one second or of one millisecond."
    ),
    RULE_FORM: (
        "A code, a name of a subject, and a commit identifier each have their "
        "form. No member holds any other text."
    ),
    RULE_REQUIRED: (
        "An event of a kind that needs a code states one, and an event of a kind "
        "that needs the commit of the reversal states one. An event of another "
        "kind states no commit."
    ),
    RULE_END: (
        "The last line of a closed log is the end line, and no line follows it. "
        "A log with no end line is open, and the check refuses it."
    ),
    RULE_COUNTS: (
        "The end line states the number of events and the number of each kind, "
        "as the log holds them."
    ),
}

_HEADER_MEMBERS: Final = frozenset(
    {
        "record",
        "schema",
        "stream",
        "experimentId",
        "runId",
        "openedAt",
        "clock",
        "kinds",
        "omitted",
        "limitations",
        "doesNotEstablish",
    }
)
_EVENT_MEMBERS: Final = frozenset(
    {
        "record",
        "index",
        "kind",
        "actor",
        "recordedAt",
        "occurredAt",
        "code",
        "subject",
        "commit",
    }
)
_OCCURRED_MEMBERS: Final = frozenset({"value", "resolution", "clock"})
_SUBJECT_MEMBERS: Final = frozenset({"kind", "name"})
_END_MEMBERS: Final = frozenset(
    {"record", "events", "byKind", "closedAt", "instantsOutOfOrder"}
)

_IDENTIFIER: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,62}")
_CODE: Final = re.compile(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?")
_NAME: Final = re.compile(r"[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?")
_COMMIT_FORM: Final = re.compile(r"[0-9a-f]{40}")
_SECOND_INSTANT: Final = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
)


class LogRefused(Exception):
    """A text that is not a log of this module."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(f"{rule}: {message}")
        self.rule = rule
        self.message = message


class EventRefused(Exception):
    """An event that cannot be recorded, or a log that cannot be written to."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(f"{rule}: {message}")
        self.rule = rule
        self.message = message


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------
# A stored log, read back
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Log:
    """One stored log that :func:`read_log` accepted.

    ``end`` is None for a log that is open.
    """

    header: Mapping[str, Any]
    events: tuple[Mapping[str, Any], ...]
    end: Mapping[str, Any] | None

    @property
    def closed(self) -> bool:
        return self.end is not None

    def summary(self) -> str:
        kinds = [event["kind"] for event in self.events]
        stated = ", ".join(
            f"{kinds.count(kind)} {kind}" for kind in KINDS if kinds.count(kind)
        )
        return f"{ROLE}: {len(self.events)} event(s): {stated or 'none'}"


def _no_repeat(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for key, value in pairs:
        if key in found:
            raise ValueError("a member is stated twice")
        found[key] = value
    return found


def _recorded(value: object, where: str) -> datetime:
    instant = collector_instant(value)
    if instant is None:
        raise LogRefused(
            RULE_INSTANT,
            f"{where} is not UTC to one millisecond in the registered form",
        )
    return instant


def _occurred_fault(value: object) -> tuple[str, str] | None:
    """The rule that an ``occurredAt`` does not hold, and why, or None."""
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != _OCCURRED_MEMBERS:
        return RULE_MEMBERS, "occurredAt does not have its members"
    if not isinstance(value["clock"], str) or value["clock"] not in CLOCKS:
        return RULE_VOCABULARY, "occurredAt states an unregistered clock"
    stated, resolution = value["value"], value["resolution"]
    usable = isinstance(stated, str) and (
        (resolution == "millisecond" and collector_instant(stated) is not None)
        or (
            resolution == "second"
            and _SECOND_INSTANT.fullmatch(stated) is not None
            and cluster_instant(stated).get("value") == stated
        )
    )
    if not usable:
        return RULE_INSTANT, "occurredAt is not UTC with its resolution"
    return None


def _event_fault(event: Mapping[str, Any]) -> tuple[str, str] | None:
    """The first rule that one event does not hold, and why, or None."""
    kind, actor = event["kind"], event["actor"]
    if not isinstance(kind, str) or kind not in KINDS:
        return RULE_VOCABULARY, "the event states an unregistered kind"
    if not isinstance(actor, str) or actor not in ACTORS:
        return RULE_VOCABULARY, "the event states an unregistered actor"
    if kind in OPERATOR_ONLY and actor != "operator":
        return RULE_VOCABULARY, f"an event of the kind {kind} states the actor operator"
    fault = _occurred_fault(event["occurredAt"])
    if fault is not None:
        return fault
    code, subject, commit = event["code"], event["subject"], event["commit"]
    if code is not None and (
        not isinstance(code, str) or _CODE.fullmatch(code) is None
    ):
        return RULE_FORM, "the code does not have the form of a code"
    if subject is not None:
        if not isinstance(subject, dict) or set(subject) != _SUBJECT_MEMBERS:
            return RULE_MEMBERS, "the subject does not have its members"
        if subject["kind"] not in SUBJECT_KINDS:
            return RULE_VOCABULARY, "the subject states an unregistered resource kind"
        name = subject["name"]
        if not isinstance(name, str) or _NAME.fullmatch(name) is None:
            return RULE_FORM, "the name of the subject does not have its form"
    if commit is not None and (
        not isinstance(commit, str) or _COMMIT_FORM.fullmatch(commit) is None
    ):
        return RULE_FORM, "the commit is not a full commit identifier"
    if kind in CODE_REQUIRED and code is None:
        return RULE_REQUIRED, f"an event of the kind {kind} states a code"
    if (kind in COMMIT_REQUIRED) != (commit is not None):
        if commit is None:
            return RULE_REQUIRED, f"an event of the kind {kind} states a commit"
        return RULE_REQUIRED, f"an event of the kind {kind} states no commit"
    return None


def _out_of_order(events: Sequence[Mapping[str, Any]]) -> list[int]:
    """Each event that was recorded at an earlier instant than the one before it."""
    found = []
    previous: datetime | None = None
    for event in events:
        instant = collector_instant(event["recordedAt"])
        if instant is None:
            continue
        if previous is not None and instant < previous:
            found.append(event["index"])
        previous = instant
    return found


def read_log(text: str, *, allow_open: bool = False) -> Log:
    """A stored log, held to its form.

    This reads the form of a log: the header, the sequence, the members and the
    vocabulary of each event, the form of each value, the instants, and the
    counts of the end line. It does not show that an event happened, and it
    does not show that a code is one that an experiment registers.

    Raises:
        LogRefused: a rule of :data:`RULES` is not held. A log with no end line
            is refused unless ``allow_open`` is set.
    """
    if text and not text.endswith("\n"):
        raise LogRefused(RULE_UNREADABLE, "the last line does not end with a line feed")
    lines: list[dict[str, Any]] = []
    for number, line in enumerate(text.split("\n")[:-1], start=1):
        try:
            document = json.loads(line, object_pairs_hook=_no_repeat)
        except (ValueError, RecursionError) as fault:
            raise LogRefused(
                RULE_UNREADABLE, f"line {number} is not one JSON object"
            ) from fault
        if not isinstance(document, dict):
            raise LogRefused(RULE_UNREADABLE, f"line {number} is not one JSON object")
        lines.append(document)
    if not lines or lines[0].get("record") != "header":
        raise LogRefused(RULE_HEADER, "the first line is not a header")
    header = lines[0]
    if set(header) != _HEADER_MEMBERS:
        raise LogRefused(RULE_MEMBERS, "the header does not have its members")
    if header["schema"] != SCHEMA or header["stream"] != ROLE:
        raise LogRefused(
            RULE_HEADER, "the header states another schema or another stream"
        )
    for name in ("experimentId", "runId"):
        value = header[name]
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise LogRefused(RULE_HEADER, f"the header states no usable {name}")
    _recorded(header["openedAt"], "openedAt")
    end: dict[str, Any] | None = None
    events = lines[1:]
    if events and events[-1].get("record") == "end":
        end = events.pop()
    elif not allow_open:
        raise LogRefused(RULE_END, "the last line is not an end line: the log is open")
    if len(events) > MAX_EVENTS:
        raise LogRefused(RULE_SEQUENCE, f"the log holds more than {MAX_EVENTS} events")
    for position, event in enumerate(events, start=1):
        where = f"line {position + 1}"
        if event.get("record") != "event":
            raise LogRefused(RULE_SEQUENCE, f"{where} is not an event")
        if set(event) != _EVENT_MEMBERS:
            raise LogRefused(RULE_MEMBERS, f"{where} does not have its members")
        if type(event["index"]) is not int or event["index"] != position:
            raise LogRefused(RULE_SEQUENCE, f"{where} is not event {position}")
        _recorded(event["recordedAt"], f"{where}: recordedAt")
        broken = _event_fault(event)
        if broken is not None:
            raise LogRefused(broken[0], f"{where}: {broken[1]}")
    if end is not None:
        if set(end) != _END_MEMBERS:
            raise LogRefused(RULE_MEMBERS, "the end line does not have its members")
        _recorded(end["closedAt"], "closedAt")
        kinds = [event["kind"] for event in events]
        counts = end["byKind"]
        if (
            type(end["events"]) is not int
            or end["events"] != len(events)
            or counts != {kind: kinds.count(kind) for kind in KINDS}
            or any(type(count) is not int for count in counts.values())
            or end["instantsOutOfOrder"] != _out_of_order(events)
        ):
            raise LogRefused(
                RULE_COUNTS,
                "the end line does not state the events that the log holds",
            )
    return Log(header, tuple(events), end)


# --------------------------------------------------------------------------
# A log, written
# --------------------------------------------------------------------------


def log_text(lines: Sequence[Mapping[str, Any]]) -> str:
    """Lines of a log as the text that is stored: sorted members, one line each."""
    return "".join(
        json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n" for line in lines
    )


def _stored(path: Path) -> Log:
    """The open log at ``path``, or a refusal to write to it."""
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as fault:
        raise EventRefused(RULE_UNREADABLE, "the file is not a readable log") from fault
    try:
        log = read_log(text, allow_open=True)
    except LogRefused as refused:
        raise EventRefused(refused.rule, refused.message) from refused
    if log.closed:
        raise EventRefused(
            RULE_END, "the log is closed, and a closed log takes no event"
        )
    return log


def _append(path: Path, line: Mapping[str, Any]) -> None:
    with path.open("ab") as handle:
        handle.write(log_text([line]).encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())


def open_log(
    path: Path,
    experiment_id: str,
    run_id: str,
    *,
    now: Callable[[], datetime] = _now,
) -> dict[str, Any]:
    """Write the header of a new log, and return it.

    Raises:
        EventRefused: an identifier does not have its form, or the file exists.
            A log is one run, and the tool does not write into an earlier one.
    """
    for name, value in (("experiment", experiment_id), ("run", run_id)):
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise EventRefused(
                RULE_HEADER,
                f"the {name} identifier is not 1 to 63 letters, digits, '.', '_', "
                "and '-', with a letter or a digit first",
            )
    header = {
        "record": "header",
        "schema": SCHEMA,
        "stream": ROLE,
        "experimentId": experiment_id,
        "runId": run_id,
        "openedAt": format_instant(now()),
        "clock": {
            "recordedAt": {
                "source": "the wall clock of the host that ran the record command",
                "zone": "UTC",
                "resolution": "millisecond",
            },
            "occurredAt": {
                "source": "the clock that the event names",
                "zone": "UTC, after normalisation",
                "resolution": "as each event states it",
            },
            "skew": "not-measured",
        },
        "kinds": dict(KINDS),
        "omitted": list(OMITTED),
        "limitations": list(LIMITATIONS),
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }
    try:
        with path.open("xb") as handle:
            handle.write(log_text([header]).encode("utf-8"))
    except FileExistsError as fault:
        raise EventRefused(
            RULE_HEADER,
            "the file exists. A log is one run, and the tool does not write into "
            "an earlier one",
        ) from fault
    except OSError as fault:
        raise EventRefused(RULE_UNREADABLE, "the file cannot be written") from fault
    return header


def _occurred(stated: str | None, clock: str | None) -> dict[str, Any] | None:
    if stated is None and clock is None:
        return None
    if stated is None or clock is None:
        raise EventRefused(
            RULE_INSTANT, "an occurredAt states an instant and the clock that it is on"
        )
    if clock not in CLOCKS:
        raise EventRefused(RULE_VOCABULARY, "the clock is not a registered clock")
    field = cluster_instant(stated)
    if field.get("state") != "reported":
        raise EventRefused(
            RULE_INSTANT,
            "the instant is not a date and a time with a zone, such as "
            "2026-10-12T08:00:00Z or 2026-10-12T10:00:00.250+02:00",
        )
    return {"value": field["value"], "resolution": field["resolution"], "clock": clock}


def _subject(stated: str | None) -> dict[str, str] | None:
    if stated is None:
        return None
    kind, separator, name = stated.partition("/")
    if not separator or kind not in SUBJECT_KINDS:
        raise EventRefused(
            RULE_VOCABULARY,
            "a subject is a registered resource kind, '/', and a name",
        )
    return {"kind": kind, "name": name}


def record(
    path: Path,
    kind: str,
    actor: str,
    *,
    code: str | None = None,
    subject: str | None = None,
    commit: str | None = None,
    occurred_at: str | None = None,
    clock: str | None = None,
    now: Callable[[], datetime] = _now,
) -> dict[str, Any]:
    """Append one event to an open log, and return it.

    The instant ``recordedAt`` is taken here, after the log was read and before
    the line is written. The caller does not state it.

    Raises:
        EventRefused: the file is not an open log, the log is full, or the
            event does not hold a rule. Nothing is written.
    """
    log = _stored(path)
    if len(log.events) >= MAX_EVENTS:
        raise EventRefused(
            RULE_SEQUENCE, f"the log holds {MAX_EVENTS} events, and it takes no more"
        )
    event = {
        "record": "event",
        "index": len(log.events) + 1,
        "kind": kind,
        "actor": actor,
        "recordedAt": None,
        "occurredAt": _occurred(occurred_at, clock),
        "code": code,
        "subject": _subject(subject),
        "commit": commit,
    }
    fault = _event_fault(event)
    if fault is not None:
        raise EventRefused(*fault)
    event["recordedAt"] = format_instant(now())
    _append(path, event)
    return event


def close_log(path: Path, *, now: Callable[[], datetime] = _now) -> dict[str, Any]:
    """Append the end line to an open log, and return it.

    Raises:
        EventRefused: the file is not an open log.
    """
    log = _stored(path)
    kinds = [event["kind"] for event in log.events]
    end = {
        "record": "end",
        "events": len(log.events),
        "byKind": {kind: kinds.count(kind) for kind in KINDS},
        "closedAt": format_instant(now()),
        "instantsOutOfOrder": _out_of_order(log.events),
    }
    _append(path, end)
    return end
