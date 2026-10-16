"""Q2, the runtime startup characterization, as one record.

Q2 measures how long a serving runtime pod of the qualified release takes from
its creation to its first Ready condition, when the Deployment controller
replaces it in a controlled restart. It runs three restarts, one at a time, in
the environment that the Q1 qualification ``q1-1`` selected. Every replacement
pod is one observation. ``S`` is the maximum of the observations. The result is
``CHARACTERIZED``, ``INCONCLUSIVE``, or ``REFUSED``.

A frozen driver prepares the release with the phase ``up`` of the Q1 driver,
requests each restart, writes what the cluster and the procedures answered into
one directory, and runs this module. This module reads that directory and returns
one record. It contacts no cluster, and it runs no procedure.

**A restart is not a fault.** A restart is one ``kubectl rollout restart`` of the
runtime Deployment. The Deployment controller then replaces each runtime pod
under the rollout bounds of the chart. No pod is deleted by name, and no caller
runs. A restart is not the fault of a reliability experiment.

**Ready is the Ready condition of the pod.** The kubelet sets it from the
readiness probe of the runtime container, which asks ``/health``. The runtime
answers 503 to ``/health`` while it loads the model. The driver also sends one
completion to each replacement after its restart, and a rule holds that each
answered. The completion is not a part of the measured interval.

**A precondition that is not held refuses.** The phase ``up`` completed, the
working tree was clean, the frozen inputs are at their pins, the delivery paths
equal the desired revision, and the environment, the release, and the images are
the ones that ``q1-1`` states. When one of these is not held, the result is
``REFUSED``, and the driver requests no restart. When each is held and a rule of
the measurement is not held, the result is ``INCONCLUSIVE``. A record states
``S`` only when the result is ``CHARACTERIZED``.

**A read that was not made is not a value.** An absent source gives the state
``not-observed`` to each rule that reads it, and a source of another form gives
``not-held``.

**The record is not a startup benchmark.** It states the start-to-Ready interval
of six replacement pods on one node, at a resolution of one second, with no
caller traffic. It states no average, no percentile, and no rate.

See docs/environment/runtime-startup-characterization.md, which describes the
directory, each rule, the measurement, and the limits of a record, and
tests/domain/test_runtime_startup.py, which gives the module each refusal.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from tools.environment_qualification.core import (
    UP_REFUSALS,
    Source,
    Sources,
    environment_digest,
    environment_identity,
)

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: The schema name of a record.
RECORD_SCHEMA: Final = "inferops.io/runtime-startup-characterization/v1alpha1"

#: The schema name that the driver writes into the header of a directory.
COLLECTION_SCHEMA: Final = "inferops.io/runtime-startup-collection/v1alpha1"

#: The schema name of the file that the driver writes for each restart.
RESTART_SCHEMA: Final = "inferops.io/runtime-startup-restart/v1alpha1"

#: The characterization that a record states.
CHARACTERIZATION: Final = "Q2"

#: The experiment identifier of the freeze record.
EXPERIMENT_ID: Final = "v2-q2-runtime-startup-characterization"

#: The freeze record that governs the driver and this module. Revision 2
#: supersedes revision 1, under which no characterization ran: revision 1 held the
#: API image to the digest that q1-1 states, and a build of unchanged inputs
#: reports another digest.
FREEZE_RECORD: Final = "docs/proof/experiments/v2-q2/freeze-r2.v1alpha1.json"

#: The freeze record of Q1, whose phase up prepares the release.
QUALIFICATION_FREEZE_RECORD: Final = (
    "docs/proof/experiments/v2-q1/freeze-r1.v1alpha1.json"
)

#: The qualification that selected the environment, and its committed record.
#: Q2 holds the environment, the release, and the images to that record.
QUALIFICATION_ID: Final = "q1-1"
QUALIFICATION_RECORD: Final = (
    "docs/proof/experiments/v2-q1/runs/q1-1/record.v1alpha1.json"
)

#: The schema name of a Q1 record.
QUALIFICATION_SCHEMA: Final = "inferops.io/environment-qualification/v1alpha1"

#: Where committed characterization directories are found.
RUNS_PATTERN: Final = "docs/proof/experiments/v2-q2/runs/*"

#: The target of Q2: the release that q1-1 qualified. No option changes it.
TARGET_RELEASE_KEY: Final = "local-docker-desktop/support-assistant"
TARGET_API_REPLICAS: Final = 2
TARGET_RUNTIME_REPLICAS: Final = 2
SELECTED_PROVIDER: Final = "docker-desktop"

#: The labels and the container names of the release.
RELEASE_INSTANCE: Final = "inferops"
API_COMPONENT: Final = "platform-api"
RUNTIME_COMPONENT: Final = "serving-runtime"
API_CONTAINER: Final = "api"
RUNTIME_CONTAINER: Final = "runtime"
VERIFY_CONTAINER: Final = "verify-model"

#: The restarts of one characterization, in the order the driver requests them.
RESTARTS: Final = ("r1", "r2", "r3")

#: The replacement pods of one restart: one for each runtime replica.
REPLACEMENTS_PER_RESTART: Final = TARGET_RUNTIME_REPLICAS

#: The resolution of a cluster timestamp, which states whole seconds.
RESOLUTION_MS: Final = 1000

#: The files of a directory. The driver restates each name.
HEADER_FILE: Final = "run.json"
CAPACITY_RECORD: Final = "capacity/record.v1alpha1.json"
PROVENANCE_FILE: Final = "provenance.json"
DEPLOYMENTS_FILE: Final = "deployments.json"
RESTARTS_DIRECTORY: Final = "restarts"
RESTART_FILE: Final = "restart.json"
BEFORE_DEPLOYMENT_FILE: Final = "before.deployment.json"
BEFORE_PODS_FILE: Final = "before.pods.json"
WATCH_FILE: Final = "watch.jsonl"
AFTER_PODS_FILE: Final = "after.pods.json"
COMPLETION_PREFIX: Final = "completion."
RECORD_FILE: Final = "record.v1alpha1.json"

#: The files of one restart directory that a record reads, in order.
RESTART_FILES: Final = (
    RESTART_FILE,
    BEFORE_DEPLOYMENT_FILE,
    BEFORE_PODS_FILE,
    WATCH_FILE,
    AFTER_PODS_FILE,
)

#: The schema names of the source records. Each is written by its own tool.
CAPACITY_SCHEMA: Final = "inferops.io/capacity-preflight/v1alpha1"
PROVENANCE_SCHEMA: Final = "inferops.io/desired-state-provenance/v1alpha1"

#: The exit status of the command for each result that is not CHARACTERIZED.
REFUSED_EXIT: Final = 5
INCONCLUSIVE_EXIT: Final = 6

CHARACTERIZED: Final = "CHARACTERIZED"
INCONCLUSIVE: Final = "INCONCLUSIVE"
REFUSED: Final = "REFUSED"

#: Every result that a record can state.
RESULT_STATES: Final = (CHARACTERIZED, INCONCLUSIVE, REFUSED)

HELD: Final = "held"
NOT_HELD: Final = "not-held"
NOT_OBSERVED: Final = "not-observed"

#: Every state of a rule.
RULE_STATES: Final = (HELD, NOT_HELD, NOT_OBSERVED)

#: The categories, in the order a record states them.
PREPARATION: Final = "preparation"
DESIRED_STATE: Final = "desired-state"
ENVIRONMENT: Final = "environment"
RELEASE_IDENTITY: Final = "release-identity"
TOPOLOGY: Final = "topology"
MEASUREMENT: Final = "measurement"
READINESS: Final = "readiness"
EVIDENCE: Final = "evidence"

CATEGORIES: Final = (
    PREPARATION,
    DESIRED_STATE,
    ENVIRONMENT,
    RELEASE_IDENTITY,
    TOPOLOGY,
    MEASUREMENT,
    READINESS,
    EVIDENCE,
)

WORKING_TREE_STATES: Final = ("clean", "dirty", "unread")
DESIRED_STATE_DIFF_STATES: Final = ("none", "differs", "unread")
FREEZE_CHANGE_STATES: Final = ("none", "listed", "unread")

#: The event types of a watch stream. An ERROR event refuses its stream.
EVENT_TYPES: Final = ("ADDED", "MODIFIED", "DELETED", "ERROR")


@dataclass(frozen=True)
class Rule:
    """One rule of a record: the criterion of the freeze record that it decides."""

    rule_id: str
    criterion: str
    category: str
    statement: str


#: Every rule, in the order a record states them. Each one is one acceptance
#: criterion of the freeze record, with the same statement.
RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "preparation-completed",
        "Q2-AC1",
        PREPARATION,
        "The phase up of the Q1 driver completed: it states no refusal, the target "
        "check refused nothing, and it ran at the executing commit of the "
        "characterization.",
    ),
    Rule(
        "working-tree-clean",
        "Q2-AC2",
        DESIRED_STATE,
        "The working tree was clean when the characterization started.",
    ),
    Rule(
        "procedure-frozen",
        "Q2-AC3",
        DESIRED_STATE,
        "The driver names the Q2 freeze record, the record has the content that the "
        "checkout holds, and the freeze tool listed no changed material file of the "
        "Q2 record or of the Q1 record when the characterization started.",
    ),
    Rule(
        "desired-revision-known",
        "Q2-AC4",
        DESIRED_STATE,
        "The desired revision is one full commit identifier, and the chart, the "
        "desired-state tree, and the controller manifests of the executing commit "
        "equal those of that revision.",
    ),
    Rule(
        "environment-qualified",
        "Q2-AC5",
        ENVIRONMENT,
        "The qualification q1-1 is QUALIFIED, the capacity gate accepted the target "
        "release key with 2 API replicas and 2 runtime replicas before the release "
        "was applied, and the environment identity of that capacity record has the "
        "digest that q1-1 states.",
    ),
    Rule(
        "release-qualified",
        "Q2-AC6",
        RELEASE_IDENTITY,
        "The provenance record resolves the target release key at the desired "
        "revision to the release identifier that q1-1 states, the API Deployment "
        "runs the API image digest that the phase up declared, and the runtime "
        "Deployment runs the runtime image that q1-1 states.",
    ),
    Rule(
        "topology-ready",
        "Q2-AC7",
        TOPOLOGY,
        "Before the first restart, the API Deployment and the runtime Deployment "
        "each state 2 replicas and report 2 replicas, 2 Ready, 2 available, and 2 "
        "updated at their current generation.",
    ),
    Rule(
        "three-restarts",
        "Q2-AC8",
        MEASUREMENT,
        "The directory holds the restarts r1, r2, and r3 and no other, the rollout "
        "restart of each exited 0, and the rollout of each completed within its "
        "bound.",
    ),
    Rule(
        "stable-before-each-restart",
        "Q2-AC9",
        TOPOLOGY,
        "Before each restart, the runtime Deployment states 2 replicas and reports "
        "2 replicas, 2 Ready, 2 available, and 2 updated at its current generation, "
        "and exactly 2 runtime pods exist, each Ready and none deleted.",
    ),
    Rule(
        "stream-complete",
        "Q2-AC10",
        EVIDENCE,
        "The watch stream of each restart is a sequence of pod events of the "
        "runtime tier with no ERROR event, it opens with one ADDED event for each "
        "pod of the reading before the restart, and the watch stopped after the "
        "rollout completed.",
    ),
    Rule(
        "two-replacements",
        "Q2-AC11",
        MEASUREMENT,
        "Each restart created exactly 2 runtime pods that the reading before it "
        "does not list, each with a creation instant, each became Ready in the "
        "stream no earlier than its creation, and the reading after the restart "
        "lists exactly those 2 pods, each Ready.",
    ),
    Rule(
        "one-at-a-time",
        "Q2-AC12",
        MEASUREMENT,
        "In each restart, the second replacement was created no earlier than the "
        "first replacement became Ready.",
    ),
    Rule(
        "ready-held",
        "Q2-AC13",
        READINESS,
        "Each replacement stayed Ready in the stream from the event in which it "
        "first became Ready to the end of the stream, and the reading after the "
        "restart states no restart of its init container or of its runtime "
        "container.",
    ),
    Rule(
        "model-verified",
        "Q2-AC14",
        READINESS,
        "In the reading after the restart, the verify-model init container of each "
        "replacement terminated with exit code 0, and its runtime container runs "
        "the runtime image that q1-1 states.",
    ),
    Rule(
        "ready-serves",
        "Q2-AC15",
        READINESS,
        "Each replacement answered one completion through a port-forward to that "
        "pod after the rollout of its restart completed, with HTTP status 200, a "
        "finish reason, and at least one completion token.",
    ),
    Rule(
        "readings-in-order",
        "Q2-AC16",
        EVIDENCE,
        "The phase up started before the characterization, each restart was "
        "requested after the characterization started and after the rollout of "
        "the restart before it completed, and each rollout completed after its "
        "request and before the characterization finished.",
    ),
)

#: The rules whose failure refuses: they decide whether the characterization may
#: run in the qualified environment. The driver requests no restart unless each
#: is held.
PRECONDITION_RULES: Final = (
    "preparation-completed",
    "working-tree-clean",
    "procedure-frozen",
    "desired-revision-known",
    "environment-qualified",
    "release-qualified",
    "topology-ready",
)

#: What no record establishes. Part of every record.
DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "A record does not establish a startup benchmark, an average start time, a "
    "percentile, or a rate. It states six intervals and their maximum.",
    "A record does not establish the start time of a pod that replaces a deleted "
    "pod, a pod that starts under caller traffic, or a pod that starts on a cold "
    "image cache or a cold model cache.",
    "A record does not establish a recovery time, an availability, a service "
    "level, or the reliability of the caller path. No caller ran.",
    "A record does not establish an interval shorter than its resolution. A "
    "cluster timestamp states whole seconds, so each interval can be up to one "
    "second shorter or longer than the time that passed.",
    "A record does not establish that the readiness probe answered at the instant "
    "of the Ready condition. The kubelet sets the condition after the probe.",
    "A record does not establish that a source record is what its collection "
    "gives. The module reads the stored source records and does not build them "
    "again.",
    "A record does not establish a result of a reliability experiment, or a bound "
    "that later work derives from S.",
    "A record does not establish production availability, high availability, or "
    "resilience to the loss of a node, a zone, or a region.",
    "A record does not establish anything about another provider, another node, "
    "another Kubernetes version, another release, or another model.",
)

_REVISION: Final = re.compile(r"[0-9a-f]{40}")
_DIGEST: Final = re.compile(r"sha256:[0-9a-f]{64}")
_HEX64: Final = re.compile(r"[0-9a-f]{64}")
_CHARACTERIZATION_ID: Final = re.compile(r"q2-[1-9][0-9]?")
_CATEGORY: Final = re.compile(r"[a-z][a-z-]{0,62}[a-z]")
_NAME: Final = re.compile(r"[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?")
_KEY: Final = re.compile(r"[a-z0-9][a-z0-9-]{0,62}/[a-z0-9][a-z0-9-]{0,62}")
_UID: Final = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_SECONDS_INSTANT: Final = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
)
_INSTANT: Final = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{3})?Z"
)
_IMAGE: Final = re.compile(r"[a-z0-9][a-z0-9._/:-]{0,199}@sha256:[0-9a-f]{64}")


def _text(value: object, pattern: re.Pattern[str]) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _optional(pattern: re.Pattern[str]) -> Callable[[object], bool]:
    return lambda value: value is None or _text(value, pattern)


#: The members of a header, and the test of each value.
_HEADER: Final[dict[str, Callable[[object], bool]]] = {
    "schema": lambda value: value == COLLECTION_SCHEMA,
    "characterizationId": lambda value: _text(value, _CHARACTERIZATION_ID),
    "provider": lambda value: _text(value, _CATEGORY),
    "releaseKey": lambda value: _text(value, _KEY),
    "executingCommit": lambda value: _text(value, _REVISION),
    "upExecutingCommit": _optional(_REVISION),
    "desiredRevision": _optional(_REVISION),
    "workingTree": lambda value: value in WORKING_TREE_STATES,
    "desiredStateDiff": lambda value: value in DESIRED_STATE_DIFF_STATES,
    "freezeRecord": lambda value: (
        isinstance(value, str)
        and re.fullmatch(r"[a-z0-9][a-z0-9./-]{0,199}\.json", value) is not None
    ),
    "freezeRecordSha256": _optional(_HEX64),
    "freezeChanges": lambda value: value in FREEZE_CHANGE_STATES,
    "qualificationFreezeChanges": lambda value: value in FREEZE_CHANGE_STATES,
    "apiImageDigest": _optional(_DIGEST),
    "targetRefusal": _optional(_CATEGORY),
    "upRefusal": lambda value: value is None or value in UP_REFUSALS,
    "upStartedAt": _optional(_INSTANT),
    "startedAt": lambda value: _text(value, _INSTANT),
    "finishedAt": lambda value: _text(value, _INSTANT),
}

#: The members of the file of one restart, and the test of each value. An exit
#: status is null when the command did not run.
_RESTART: Final[dict[str, Callable[[object], bool]]] = {
    "schema": lambda value: value == RESTART_SCHEMA,
    "restart": lambda value: value in RESTARTS,
    "requestedAt": lambda value: _text(value, _INSTANT),
    "restartExit": lambda value: value is None or _count(value) is not None,
    "rolloutExit": lambda value: value is None or _count(value) is not None,
    "rolledOutAt": _optional(_INSTANT),
    "watchStoppedAt": _optional(_INSTANT),
}


class CollectionRefused(ValueError):
    """The directory is not a characterization directory, so no record exists."""


def _count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return ()


def _dig(document: object, *path: str) -> Any:
    for member in path:
        if not isinstance(document, Mapping):
            return None
        document = document.get(member)
    return document


def lf_digest(data: bytes) -> str:
    """The SHA-256 of a file's bytes with CRLF read as LF, as hexadecimal."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _instant(value: object) -> datetime | None:
    if not _text(value, _INSTANT):
        return None
    text = str(value)
    pattern = "%Y-%m-%dT%H:%M:%S.%fZ" if "." in text else "%Y-%m-%dT%H:%M:%SZ"
    try:
        return datetime.strptime(text, pattern).replace(tzinfo=UTC)
    except ValueError:
        return None


def _cluster_instant(value: object) -> datetime | None:
    """A cluster timestamp, which states whole seconds, or nothing."""
    return _instant(value) if _text(value, _SECONDS_INSTANT) else None


def _milliseconds(start: datetime, end: datetime) -> int:
    return round((end - start).total_seconds() * 1000)


# --------------------------------------------------------------------------
# Reading a directory
# --------------------------------------------------------------------------

ABSENT: Final = "absent"
UNREADABLE: Final = "unreadable"


def _read_bytes(directory: Path, name: str) -> bytes | None:
    path = directory / name
    if not path.is_file():
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def _json_source(directory: Path, name: str, schema: str | None = None) -> Source:
    data = _read_bytes(directory, name)
    if data is None:
        return Source(name, problem=ABSENT)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError):
        return Source(name, problem=UNREADABLE)
    if schema is not None and _dig(value, "schema") != schema:
        return Source(name, problem=f"not of the schema {schema}")
    return Source(name, value=value)


def read_header(directory: Path) -> dict[str, Any]:
    """The header of a directory. Raise when the directory is not one."""
    data = _read_bytes(directory, HEADER_FILE)
    if data is None:
        raise CollectionRefused(f"{HEADER_FILE} is absent or unreadable")
    try:
        header = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise CollectionRefused(f"{HEADER_FILE} is not JSON") from error
    if not isinstance(header, dict):
        raise CollectionRefused(f"{HEADER_FILE} is not an object")
    if set(header) != set(_HEADER):
        raise CollectionRefused(
            f"{HEADER_FILE} must state exactly the members {sorted(_HEADER)}"
        )
    wrong = sorted(name for name, test in _HEADER.items() if not test(header[name]))
    if wrong:
        raise CollectionRefused(f"{HEADER_FILE} states unusable values for {wrong}")
    return header


@dataclass(frozen=True)
class Event:
    """One event of a watch stream: its type and the pod it carries."""

    kind: str
    pod: Mapping[str, Any]

    @property
    def uid(self) -> object:
        return _dig(self.pod, "metadata", "uid")


@dataclass(frozen=True)
class Stream:
    """A watch stream, or why it is not one."""

    events: tuple[Event, ...] = ()
    problem: str | None = None


def read_stream(data: bytes | None) -> Stream:
    """Read a watch stream: one JSON event on each line, in the order received."""
    if data is None:
        return Stream(problem=ABSENT)
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        return Stream(problem=UNREADABLE)
    events = []
    for number, line in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            return Stream(problem=f"line {number} is not JSON")
        kind = _dig(event, "type")
        pod = _dig(event, "object")
        if kind not in EVENT_TYPES or not isinstance(pod, Mapping):
            return Stream(problem=f"line {number} is not a watch event")
        events.append(Event(str(kind), pod))
    if not events:
        return Stream(problem="the stream holds no event")
    return Stream(tuple(events))


@dataclass(frozen=True)
class Restart:
    """Every file of one restart directory, read once."""

    name: str
    present: bool
    restart: Source
    before_deployment: Source
    before_pods: Source
    stream: Stream
    after_pods: Source
    completions: Mapping[str, Source] = field(default_factory=dict)


@dataclass(frozen=True)
class Characterization:
    """Every source of one directory, read once."""

    header: Mapping[str, Any]
    capacity: Source
    provenance: Source
    deployments: Source
    qualification: Source
    restarts: tuple[Restart, ...]
    others: tuple[str, ...]
    root: Path
    directory: Path


def _read_restart(directory: Path, name: str) -> Restart:
    base = directory / RESTARTS_DIRECTORY / name
    completions = {}
    if base.is_dir():
        for path in sorted(base.iterdir()):
            if (
                path.is_file()
                and path.name.startswith(COMPLETION_PREFIX)
                and path.name.endswith(".json")
            ):
                pod = path.name[len(COMPLETION_PREFIX) : -len(".json")]
                completions[pod] = _json_source(base, path.name)
    return Restart(
        name=name,
        present=base.is_dir(),
        restart=_json_source(base, RESTART_FILE, RESTART_SCHEMA),
        before_deployment=_json_source(base, BEFORE_DEPLOYMENT_FILE),
        before_pods=_json_source(base, BEFORE_PODS_FILE),
        stream=read_stream(_read_bytes(base, WATCH_FILE)),
        after_pods=_json_source(base, AFTER_PODS_FILE),
        completions=completions,
    )


def read_characterization(directory: Path, root: Path = REPO_ROOT) -> Characterization:
    """Read the header and every source of a directory."""
    header = read_header(directory)
    restarts_dir = directory / RESTARTS_DIRECTORY
    names = (
        sorted(path.name for path in restarts_dir.iterdir())
        if restarts_dir.is_dir()
        else []
    )
    return Characterization(
        header=header,
        capacity=_json_source(directory, CAPACITY_RECORD, CAPACITY_SCHEMA),
        provenance=_json_source(directory, PROVENANCE_FILE),
        deployments=_json_source(directory, DEPLOYMENTS_FILE),
        qualification=_json_source(root, QUALIFICATION_RECORD, QUALIFICATION_SCHEMA),
        restarts=tuple(_read_restart(directory, name) for name in RESTARTS),
        others=tuple(name for name in names if name not in RESTARTS),
        root=root,
        directory=directory,
    )


# --------------------------------------------------------------------------
# The derived parts of a record
# --------------------------------------------------------------------------


def _environment(sources: Characterization) -> dict[str, Any] | None:
    """The environment identity of the capacity record, as Q1 computes it."""
    absent = Source("", problem=ABSENT)
    qualification = Sources(
        header={},
        capacity=sources.capacity,
        provenance=absent,
        reconciliation=absent,
        deployments=absent,
        endpoints=absent,
        model_cache=absent,
        plan=absent,
        caller_text=None,
        caller_refused=False,
        root=sources.root,
        directory=sources.directory,
    )
    return environment_identity(qualification)


def _qualified(sources: Characterization) -> Mapping[str, Any]:
    """The identities that the record of q1-1 states, or nothing."""
    record = _mapping(sources.qualification.value)
    if record.get("result") != "QUALIFIED":
        return {}
    if _dig(record, "collection", "qualificationId") != QUALIFICATION_ID:
        return {}
    return record


def _qualified_value(sources: Characterization, *path: str) -> Any:
    return _dig(_qualified(sources), *path)


def _provenance_record(sources: Characterization) -> Mapping[str, Any] | None:
    if not sources.provenance.read:
        return None
    records = _sequence(sources.provenance.value)
    if len(records) != 1 or _dig(records[0], "schema") != PROVENANCE_SCHEMA:
        return None
    return _mapping(records[0])


def _release_id(sources: Characterization) -> str | None:
    value = _dig(_provenance_record(sources), "release", "releaseId")
    return value if _text(value, _HEX64) else None


def _items(source: Source) -> list[Mapping[str, Any]] | None:
    """The items of a list read, or nothing when it is not one."""
    if not source.read:
        return None
    items = _dig(source.value, "items")
    if not isinstance(items, list) or not all(isinstance(i, Mapping) for i in items):
        return None
    return items


def _labelled(item: Mapping[str, Any], component: str) -> bool:
    labels = _mapping(_dig(item, "metadata", "labels"))
    return (
        labels.get("app.kubernetes.io/instance") == RELEASE_INSTANCE
        and labels.get("app.kubernetes.io/component") == component
    )


def _deployments(
    items: Sequence[Mapping[str, Any]], component: str
) -> list[Mapping[str, Any]]:
    return [
        item
        for item in items
        if _dig(item, "kind") in (None, "Deployment") and _labelled(item, component)
    ]


def _container_image(deployment: Mapping[str, Any], name: str) -> list[object]:
    containers = _sequence(_dig(deployment, "spec", "template", "spec", "containers"))
    return [_dig(item, "image") for item in containers if _dig(item, "name") == name]


def _condition(pod: Mapping[str, Any], kind: str) -> Mapping[str, Any]:
    for condition in _sequence(_dig(pod, "status", "conditions")):
        if _dig(condition, "type") == kind:
            return _mapping(condition)
    return {}


def _is_ready(pod: Mapping[str, Any]) -> bool:
    return _condition(pod, "Ready").get("status") == "True"


def _container_status(
    pod: Mapping[str, Any], member: str, name: str
) -> Mapping[str, Any]:
    for status in _sequence(_dig(pod, "status", member)):
        if _dig(status, "name") == name:
            return _mapping(status)
    return {}


@dataclass(frozen=True)
class Replacement:
    """One replacement pod of one restart, as its stream gives it."""

    uid: str
    name: object
    created: datetime | None
    events: tuple[Event, ...]
    ready_index: int | None

    @property
    def first_ready(self) -> Event | None:
        """The first event in which the pod is Ready, or nothing."""
        return None if self.ready_index is None else self.events[self.ready_index]

    @property
    def ready(self) -> datetime | None:
        if self.first_ready is None:
            return None
        return _cluster_instant(
            _condition(self.first_ready.pod, "Ready").get("lastTransitionTime")
        )


def _before_uids(restart: Restart) -> list[object] | None:
    items = _items(restart.before_pods)
    if items is None:
        return None
    return [_dig(item, "metadata", "uid") for item in items]


def replacements(restart: Restart) -> list[Replacement] | None:
    """The pods that a restart created, in the order of their creation.

    A replacement is a pod of the stream that the reading before the restart does
    not list. Nothing is stated when the stream or that reading is not readable.
    """
    before = _before_uids(restart)
    if before is None or restart.stream.problem is not None:
        return None
    grouped: dict[str, list[Event]] = {}
    for event in restart.stream.events:
        uid = event.uid
        if isinstance(uid, str) and uid not in before:
            grouped.setdefault(uid, []).append(event)
    found = []
    for uid, events in grouped.items():
        first = events[0].pod
        ready = next(
            (
                index
                for index, event in enumerate(events)
                if event.kind != "DELETED" and _is_ready(event.pod)
            ),
            None,
        )
        found.append(
            Replacement(
                uid=uid,
                name=_dig(first, "metadata", "name"),
                created=_cluster_instant(_dig(first, "metadata", "creationTimestamp")),
                events=tuple(events),
                ready_index=ready,
            )
        )
    epoch = datetime.min.replace(tzinfo=UTC)
    return sorted(found, key=lambda item: item.created or epoch)


def _phase_instant(event: Event | None, kind: str) -> datetime | None:
    if event is None:
        return None
    condition = _condition(event.pod, kind)
    if condition.get("status") != "True":
        return None
    return _cluster_instant(condition.get("lastTransitionTime"))


def _runtime_started(event: Event | None) -> datetime | None:
    if event is None:
        return None
    status = _container_status(event.pod, "containerStatuses", RUNTIME_CONTAINER)
    return _cluster_instant(_dig(status, "state", "running", "startedAt"))


def _stamp(value: datetime | None) -> str | None:
    return None if value is None else value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _between(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None or end < start:
        return None
    return _milliseconds(start, end)


def observations(sources: Characterization) -> list[dict[str, Any]]:
    """Every replacement of every restart, with its instants and intervals.

    ``startToReadyMs`` is the interval from the creation of the pod to the first
    Ready condition that the stream shows. The two parts, to the Initialized
    condition and from it to Ready, are stated beside it. A value that was not
    read is null.
    """
    rows = []
    for restart in sources.restarts:
        for order, item in enumerate(replacements(restart) or [], start=1):
            ready_event = item.first_ready
            scheduled = _phase_instant(ready_event, "PodScheduled")
            initialized = _phase_instant(ready_event, "Initialized")
            rows.append(
                {
                    "restart": restart.name,
                    "order": order,
                    "pod": item.name if _text(item.name, _NAME) else None,
                    "createdAt": _stamp(item.created),
                    "scheduledAt": _stamp(scheduled),
                    "initializedAt": _stamp(initialized),
                    "runtimeStartedAt": _stamp(_runtime_started(ready_event)),
                    "readyAt": _stamp(item.ready),
                    "startToReadyMs": _between(item.created, item.ready),
                    "createdToInitializedMs": _between(item.created, initialized),
                    "initializedToReadyMs": _between(initialized, item.ready),
                }
            )
    return rows


def identities(sources: Characterization) -> dict[str, Any]:
    """The immutable identities of the characterization. Unread ones are null."""
    header = sources.header
    environment = _environment(sources)
    freeze = _read_bytes(sources.root, FREEZE_RECORD)
    qualification = _read_bytes(sources.root, QUALIFICATION_RECORD)
    return {
        "executingCommit": header["executingCommit"],
        "desiredRevision": header["desiredRevision"],
        "releaseKey": header["releaseKey"],
        "releaseId": _release_id(sources),
        "apiImageDigest": header["apiImageDigest"],
        "runtimeImage": _qualified_value(
            sources, "identities", "runtimeImage", "reference"
        ),
        "provider": header["provider"],
        "kubernetesServerVersion": None
        if environment is None
        else environment["kubernetesServerVersion"],
        "environmentSha256": None
        if environment is None
        else environment_digest(environment),
        "qualification": {
            "qualificationId": QUALIFICATION_ID,
            "path": QUALIFICATION_RECORD,
            "contentSha256": None
            if qualification is None
            else lf_digest(qualification),
        },
        "freezeRecord": {
            "path": FREEZE_RECORD,
            "contentSha256": None if freeze is None else lf_digest(freeze),
        },
    }


# --------------------------------------------------------------------------
# The rules
# --------------------------------------------------------------------------

Outcome = tuple[str, str]


def _missing(source: Source) -> Outcome:
    if source.problem == ABSENT:
        return NOT_OBSERVED, f"{source.name} was not read"
    return NOT_HELD, f"{source.name} is {source.problem}"


def _preparation_completed(sources: Characterization) -> Outcome:
    header = sources.header
    if header["upRefusal"] is not None:
        return NOT_HELD, f"the phase up refused: {header['upRefusal']}"
    if header["targetRefusal"] is not None:
        return NOT_HELD, f"the target check refused: {header['targetRefusal']}"
    if header["upExecutingCommit"] is None or header["upStartedAt"] is None:
        return NOT_OBSERVED, "the phase up states no executing commit or start time"
    if header["upExecutingCommit"] != header["executingCommit"]:
        return NOT_HELD, "the phase up ran at another commit"
    return HELD, "the phase up completed at the executing commit"


def _working_tree_clean(sources: Characterization) -> Outcome:
    state = sources.header["workingTree"]
    if state == "unread":
        return NOT_OBSERVED, "the working tree was not read"
    if state != "clean":
        return NOT_HELD, "the working tree was not clean"
    return HELD, "the working tree was clean"


def _procedure_frozen(sources: Characterization) -> Outcome:
    header = sources.header
    if header["freezeRecord"] != FREEZE_RECORD:
        return NOT_HELD, f"the driver names {header['freezeRecord']}"
    data = _read_bytes(sources.root, FREEZE_RECORD)
    if data is None:
        return NOT_OBSERVED, "the checkout holds no Q2 freeze record"
    if header["freezeRecordSha256"] != lf_digest(data):
        return NOT_HELD, "the freeze record has other content than the checkout holds"
    for member, record in (
        ("freezeChanges", "Q2"),
        ("qualificationFreezeChanges", "Q1"),
    ):
        if header[member] == "unread":
            return NOT_OBSERVED, f"the changes of the {record} record were not read"
        if header[member] != "none":
            return NOT_HELD, f"the freeze tool listed a changed {record} material file"
    return HELD, "the Q2 and the Q1 freeze records list no changed material file"


def _desired_revision_known(sources: Characterization) -> Outcome:
    header = sources.header
    if header["desiredRevision"] is None:
        return NOT_OBSERVED, "the desired revision was not read"
    if header["desiredStateDiff"] == "unread":
        return NOT_OBSERVED, "the delivery paths were not compared"
    if header["desiredStateDiff"] != "none":
        return NOT_HELD, "the delivery paths differ from the desired revision"
    return HELD, "the delivery paths equal the desired revision"


def _environment_qualified(sources: Characterization) -> Outcome:
    if not sources.qualification.read:
        return _missing(sources.qualification)
    qualified = _qualified(sources)
    if not qualified:
        return NOT_HELD, f"the record of {QUALIFICATION_ID} is not QUALIFIED"
    if not sources.capacity.read:
        return _missing(sources.capacity)
    record = sources.capacity.value
    if _dig(record, "collection", "releaseKey") != TARGET_RELEASE_KEY:
        return NOT_HELD, f"the capacity record is not of {TARGET_RELEASE_KEY}"
    topology = _mapping(_dig(record, "footprint", "topology"))
    if (topology.get("apiReplicas"), topology.get("runtimeReplicas")) != (
        TARGET_API_REPLICAS,
        TARGET_RUNTIME_REPLICAS,
    ):
        return NOT_HELD, "the capacity footprint is not of 2 API and 2 runtime replicas"
    if _dig(record, "result") != "ACCEPTED":
        return NOT_HELD, f"the capacity gate result is {_dig(record, 'result')}"
    environment = _environment(sources)
    if environment is None:
        return NOT_HELD, "the capacity record states no readable environment identity"
    if environment["provider"] != SELECTED_PROVIDER:
        return NOT_HELD, f"the provider is not {SELECTED_PROVIDER}"
    digest = environment_digest(environment)
    if digest != qualified.get("environmentSha256"):
        return (
            NOT_HELD,
            f"the environment {digest} is not the one {QUALIFICATION_ID} states",
        )
    return HELD, f"the environment {digest} of {QUALIFICATION_ID}"


def _release_qualified(sources: Characterization) -> Outcome:
    qualified = _qualified(sources)
    if not qualified:
        return NOT_OBSERVED, f"no QUALIFIED record of {QUALIFICATION_ID} was read"
    if not sources.provenance.read:
        return _missing(sources.provenance)
    record = _provenance_record(sources)
    if record is None:
        return NOT_HELD, f"{PROVENANCE_FILE} is not a list of one provenance record"
    header = sources.header
    if header["desiredRevision"] is None:
        return NOT_OBSERVED, "the desired revision was not read"
    if _dig(record, "git", "revision") != header["desiredRevision"]:
        return NOT_HELD, "the provenance record resolves another revision"
    if (
        _dig(record, "desiredState", "key") != TARGET_RELEASE_KEY
        or header["releaseKey"] != TARGET_RELEASE_KEY
    ):
        return NOT_HELD, f"the release key is not {TARGET_RELEASE_KEY}"
    release_id = _release_id(sources)
    if release_id is None or release_id != _dig(qualified, "identities", "releaseId"):
        return NOT_HELD, f"the release is not the one {QUALIFICATION_ID} states"
    # The API image is held to the digest that the phase up declared, and not
    # to the one of q1-1: a build of the same inputs reports another digest. The
    # inputs of the build are pinned by the Q1 record, which procedure-frozen
    # holds unchanged.
    digest = header["apiImageDigest"]
    if digest is None:
        return NOT_OBSERVED, "the phase up declared no API image digest"
    if not sources.deployments.read:
        return _missing(sources.deployments)
    items = _items(sources.deployments)
    if items is None:
        return NOT_HELD, f"{DEPLOYMENTS_FILE} is not a list of Deployments"
    api = _deployments(items, API_COMPONENT)
    runtime = _deployments(items, RUNTIME_COMPONENT)
    if len(api) != 1 or len(runtime) != 1:
        return NOT_HELD, "the release does not hold one API and one runtime Deployment"
    api_images = _container_image(api[0], API_CONTAINER)
    if len(api_images) != 1 or not _text(api_images[0], _IMAGE):
        return NOT_HELD, "the API Deployment does not run one api container by digest"
    if not str(api_images[0]).endswith("@" + str(digest)):
        return NOT_HELD, "the api container runs another digest than the declared one"
    runtime_image = _dig(qualified, "identities", "runtimeImage", "reference")
    if _container_image(runtime[0], RUNTIME_CONTAINER) != [runtime_image]:
        return (
            NOT_HELD,
            f"the runtime container runs another image than {QUALIFICATION_ID}",
        )
    return HELD, f"release {release_id} with the images of {QUALIFICATION_ID}"


def _topology_ready(sources: Characterization) -> Outcome:
    if not sources.deployments.read:
        return _missing(sources.deployments)
    items = _items(sources.deployments)
    if items is None:
        return NOT_HELD, f"{DEPLOYMENTS_FILE} is not a list of Deployments"
    for component, replicas in (
        (API_COMPONENT, TARGET_API_REPLICAS),
        (RUNTIME_COMPONENT, TARGET_RUNTIME_REPLICAS),
    ):
        found = _deployments(items, component)
        if len(found) != 1:
            return NOT_HELD, f"{len(found)} {component} Deployments, not 1"
        problem = _deployment_problem(found[0], replicas)
        if problem is not None:
            return NOT_HELD, f"the {component} Deployment {problem}"
    return HELD, "each Deployment states and reports 2 Ready replicas"


def _restart_value(restart: Restart, member: str) -> Any:
    return _dig(restart.restart.value, member)


def _restart_problem(restart: Restart) -> Outcome | None:
    """Why the file of one restart is not usable, or nothing when it is."""
    if not restart.restart.read:
        return _missing(restart.restart)
    value = _mapping(restart.restart.value)
    if set(value) != set(_RESTART):
        return NOT_HELD, f"{restart.name}/{RESTART_FILE} states other members"
    if not all(test(value[name]) for name, test in _RESTART.items()):
        return NOT_HELD, f"{restart.name}/{RESTART_FILE} states an unusable value"
    if value["restart"] != restart.name:
        return NOT_HELD, f"{restart.name}/{RESTART_FILE} names another restart"
    return None


def _three_restarts(sources: Characterization) -> Outcome:
    if sources.others:
        return NOT_HELD, f"the directory holds other restarts: {list(sources.others)}"
    for restart in sources.restarts:
        if not restart.present:
            return NOT_OBSERVED, f"the restart {restart.name} was not made"
        problem = _restart_problem(restart)
        if problem is not None:
            return problem
        if _restart_value(restart, "restartExit") != 0:
            return NOT_HELD, f"the rollout restart {restart.name} did not exit 0"
        if (
            _restart_value(restart, "rolloutExit") != 0
            or _restart_value(restart, "rolledOutAt") is None
        ):
            return (
                NOT_HELD,
                f"the rollout of {restart.name} did not complete in its bound",
            )
    return HELD, "three restarts, each rolled out"


def _deployment_problem(deployment: Mapping[str, Any], replicas: int) -> str | None:
    status = _mapping(deployment.get("status"))
    if _dig(deployment, "spec", "replicas") != replicas:
        return f"states {_dig(deployment, 'spec', 'replicas')} replicas"
    for member in ("replicas", "readyReplicas", "availableReplicas", "updatedReplicas"):
        if status.get(member) != replicas:
            return f"reports {member} {status.get(member)}"
    generation = _dig(deployment, "metadata", "generation")
    if _count(generation) is None or status.get("observedGeneration") != generation:
        return "reports a generation that is not its current one"
    return None


def _stable_before_each_restart(sources: Characterization) -> Outcome:
    for restart in sources.restarts:
        if not restart.present:
            return NOT_OBSERVED, f"the restart {restart.name} was not made"
        if not restart.before_deployment.read:
            return _missing(restart.before_deployment)
        deployment = _mapping(restart.before_deployment.value)
        if _dig(deployment, "kind") not in (None, "Deployment") or not _labelled(
            deployment, RUNTIME_COMPONENT
        ):
            return (
                NOT_HELD,
                f"{restart.name}: the reading is not the runtime Deployment",
            )
        problem = _deployment_problem(deployment, TARGET_RUNTIME_REPLICAS)
        if problem is not None:
            return NOT_HELD, f"{restart.name}: the runtime Deployment {problem}"
        pods = _items(restart.before_pods)
        if pods is None:
            if not restart.before_pods.read:
                return _missing(restart.before_pods)
            return NOT_HELD, f"{restart.name}: {BEFORE_PODS_FILE} is not a list of pods"
        if len(pods) != TARGET_RUNTIME_REPLICAS:
            return (
                NOT_HELD,
                f"{restart.name}: {len(pods)} runtime pods before the restart",
            )
        for pod in pods:
            if not _labelled(pod, RUNTIME_COMPONENT) or not _text(
                _dig(pod, "metadata", "uid"), _UID
            ):
                return (
                    NOT_HELD,
                    f"{restart.name}: a pod of the reading is not a runtime pod",
                )
            if _dig(pod, "metadata", "deletionTimestamp") is not None:
                return NOT_HELD, f"{restart.name}: a runtime pod was being deleted"
            if not _is_ready(pod):
                return NOT_HELD, f"{restart.name}: a runtime pod was not Ready"
    return HELD, "2 Ready runtime pods and a settled Deployment before each restart"


def _stream_complete(sources: Characterization) -> Outcome:
    for restart in sources.restarts:
        if not restart.present:
            return NOT_OBSERVED, f"the restart {restart.name} was not made"
        stream = restart.stream
        if stream.problem == ABSENT:
            return NOT_OBSERVED, f"{restart.name}/{WATCH_FILE} was not read"
        if stream.problem is not None:
            return NOT_HELD, f"{restart.name}/{WATCH_FILE}: {stream.problem}"
        for event in stream.events:
            if event.kind == "ERROR":
                return NOT_HELD, f"{restart.name}: the stream holds an ERROR event"
            if _dig(event.pod, "kind") not in (None, "Pod") or not _labelled(
                event.pod, RUNTIME_COMPONENT
            ):
                return NOT_HELD, f"{restart.name}: the stream holds another object"
            if not _text(event.uid, _UID):
                return NOT_HELD, f"{restart.name}: an event names no pod identifier"
        before = _before_uids(restart)
        if before is None:
            return NOT_OBSERVED, f"{restart.name}: the reading before was not read"
        opening = stream.events[: len(before)]
        if sorted(str(event.uid) for event in opening) != sorted(
            str(uid) for uid in before
        ) or any(event.kind != "ADDED" for event in opening):
            return NOT_HELD, (
                f"{restart.name}: the stream does not open with the pods of the "
                "reading before"
            )
        problem = _restart_problem(restart)
        if problem is not None:
            return problem
        rolled = _instant(_restart_value(restart, "rolledOutAt"))
        stopped = _instant(_restart_value(restart, "watchStoppedAt"))
        if rolled is None or stopped is None:
            return NOT_OBSERVED, f"{restart.name}: the rollout or the watch has no end"
        if stopped < rolled:
            return (
                NOT_HELD,
                f"{restart.name}: the watch stopped before the rollout completed",
            )
    return HELD, "each stream opens with the pods before and outlasts its rollout"


def _uids(source: Source) -> list[object] | None:
    items = _items(source)
    if items is None:
        return None
    return [_dig(item, "metadata", "uid") for item in items]


def _two_replacements(sources: Characterization) -> Outcome:
    for restart in sources.restarts:
        found = replacements(restart)
        if found is None:
            return (
                NOT_OBSERVED,
                f"{restart.name}: the stream or the reading before was not read",
            )
        if len(found) != REPLACEMENTS_PER_RESTART:
            return NOT_HELD, f"{restart.name}: {len(found)} replacements, not 2"
        for item in found:
            if item.created is None:
                return (
                    NOT_HELD,
                    f"{restart.name}: a replacement states no creation instant",
                )
            if item.ready is None:
                return NOT_HELD, f"{restart.name}: a replacement did not become Ready"
            if item.ready < item.created:
                return (
                    NOT_HELD,
                    f"{restart.name}: a replacement was Ready before its creation",
                )
            if not _text(item.name, _NAME):
                return NOT_HELD, f"{restart.name}: a replacement states no usable name"
        after = _items(restart.after_pods)
        if after is None:
            if not restart.after_pods.read:
                return _missing(restart.after_pods)
            return NOT_HELD, f"{restart.name}: {AFTER_PODS_FILE} is not a list of pods"
        listed = sorted(str(_dig(pod, "metadata", "uid")) for pod in after)
        if listed != sorted(item.uid for item in found):
            return NOT_HELD, f"{restart.name}: the reading after lists other pods"
        if not all(_is_ready(pod) for pod in after):
            return (
                NOT_HELD,
                f"{restart.name}: a replacement is not Ready in the reading after",
            )
    return HELD, "two replacements in each restart, each Ready"


def _one_at_a_time(sources: Characterization) -> Outcome:
    for restart in sources.restarts:
        found = replacements(restart)
        if found is None or len(found) != REPLACEMENTS_PER_RESTART:
            return NOT_OBSERVED, f"{restart.name}: the two replacements were not read"
        first, second = found
        if first.ready is None or second.created is None:
            return (
                NOT_OBSERVED,
                f"{restart.name}: an instant of a replacement was not read",
            )
        if second.created < first.ready:
            return NOT_HELD, (
                f"{restart.name}: the second replacement was created before the "
                "first was Ready"
            )
    return HELD, "in each restart the second replacement followed the first Ready"


def _ready_held(sources: Characterization) -> Outcome:
    for restart in sources.restarts:
        found = replacements(restart)
        if found is None:
            return (
                NOT_OBSERVED,
                f"{restart.name}: the stream or the reading before was not read",
            )
        after = {
            _dig(pod, "metadata", "uid"): pod
            for pod in _items(restart.after_pods) or []
        }
        for item in found:
            if item.ready_index is None:
                return NOT_HELD, f"{restart.name}: a replacement did not become Ready"
            for event in item.events[item.ready_index :]:
                if event.kind == "DELETED" or not _is_ready(event.pod):
                    return (
                        NOT_HELD,
                        f"{restart.name}: a replacement left Ready in the stream",
                    )
            pod = after.get(item.uid)
            if pod is None:
                return (
                    NOT_OBSERVED,
                    f"{restart.name}: a replacement is not in the reading after",
                )
            for member, name in (
                ("initContainerStatuses", VERIFY_CONTAINER),
                ("containerStatuses", RUNTIME_CONTAINER),
            ):
                restarts = _count(
                    _container_status(pod, member, name).get("restartCount")
                )
                if restarts is None:
                    return (
                        NOT_HELD,
                        f"{restart.name}: the {name} container states no restart count",
                    )
                if restarts != 0:
                    return NOT_HELD, f"{restart.name}: the {name} container restarted"
    return HELD, "each replacement stayed Ready, and no container restarted"


def _model_verified(sources: Characterization) -> Outcome:
    image = _qualified_value(sources, "identities", "runtimeImage", "reference")
    if not _text(image, _IMAGE):
        return NOT_OBSERVED, f"no runtime image of {QUALIFICATION_ID} was read"
    digest = str(image).rsplit("@", 1)[1]
    for restart in sources.restarts:
        found = replacements(restart)
        after = _items(restart.after_pods)
        if found is None or after is None:
            return NOT_OBSERVED, f"{restart.name}: the replacements were not read"
        by_uid = {_dig(pod, "metadata", "uid"): pod for pod in after}
        for item in found:
            pod = by_uid.get(item.uid)
            if pod is None:
                return (
                    NOT_OBSERVED,
                    f"{restart.name}: a replacement is not in the reading after",
                )
            verify = _container_status(pod, "initContainerStatuses", VERIFY_CONTAINER)
            exit_code = _dig(verify, "state", "terminated", "exitCode")
            if isinstance(exit_code, bool) or exit_code != 0:
                return (
                    NOT_HELD,
                    f"{restart.name}: the {VERIFY_CONTAINER} container did not exit 0",
                )
            containers = _sequence(_dig(pod, "spec", "containers"))
            images = [
                _dig(c, "image")
                for c in containers
                if _dig(c, "name") == RUNTIME_CONTAINER
            ]
            status = _container_status(pod, "containerStatuses", RUNTIME_CONTAINER)
            image_id = status.get("imageID")
            if images != [image] or not (
                isinstance(image_id, str) and image_id.endswith("@" + digest)
            ):
                return (
                    NOT_HELD,
                    f"{restart.name}: a runtime container runs another image",
                )
    return (
        HELD,
        f"each replacement verified the model and runs the image of {QUALIFICATION_ID}",
    )


def _ready_serves(sources: Characterization) -> Outcome:
    for restart in sources.restarts:
        found = replacements(restart)
        if found is None:
            return NOT_OBSERVED, f"{restart.name}: the replacements were not read"
        names = {str(item.name) for item in found}
        extra = sorted(set(restart.completions) - names)
        if extra:
            return (
                NOT_HELD,
                f"{restart.name}: a completion of a pod that is not a replacement",
            )
        for item in found:
            source = restart.completions.get(str(item.name))
            if source is None:
                return NOT_OBSERVED, f"{restart.name}: no completion of a replacement"
            if not source.read:
                return _missing(source)
            value = _mapping(source.value)
            tokens = _count(value.get("completionTokens"))
            reason = value.get("finishReason")
            if value.get("httpStatus") != 200 or isinstance(
                value.get("httpStatus"), bool
            ):
                return (
                    NOT_HELD,
                    f"{restart.name}: a completion answered {value.get('httpStatus')}",
                )
            if not (isinstance(reason, str) and reason) or tokens is None or tokens < 1:
                return (
                    NOT_HELD,
                    f"{restart.name}: a completion states no finish reason or token",
                )
    return HELD, "each replacement answered one completion"


def _readings_in_order(sources: Characterization) -> Outcome:
    header = sources.header
    up = _instant(header["upStartedAt"])
    started = _instant(header["startedAt"])
    finished = _instant(header["finishedAt"])
    if up is None or started is None or finished is None:
        return NOT_OBSERVED, "the phase up or the characterization has no instant"
    if not up < started <= finished:
        return NOT_HELD, "the phase up did not start before the characterization"
    previous = started
    for restart in sources.restarts:
        if not restart.present:
            return NOT_OBSERVED, f"the restart {restart.name} was not made"
        problem = _restart_problem(restart)
        if problem is not None:
            return problem
        requested = _instant(_restart_value(restart, "requestedAt"))
        rolled = _instant(_restart_value(restart, "rolledOutAt"))
        if requested is None or rolled is None:
            return (
                NOT_OBSERVED,
                f"{restart.name}: the request or the rollout has no instant",
            )
        if requested < previous:
            return (
                NOT_HELD,
                f"{restart.name} was requested before the step before it ended",
            )
        if not requested < rolled <= finished:
            return NOT_HELD, f"{restart.name}: the rollout is out of order"
        previous = rolled
    return HELD, "the phase up, then three restarts in order"


_EVALUATORS: Final[dict[str, Callable[[Characterization], Outcome]]] = {
    "preparation-completed": _preparation_completed,
    "working-tree-clean": _working_tree_clean,
    "procedure-frozen": _procedure_frozen,
    "desired-revision-known": _desired_revision_known,
    "environment-qualified": _environment_qualified,
    "release-qualified": _release_qualified,
    "topology-ready": _topology_ready,
    "three-restarts": _three_restarts,
    "stable-before-each-restart": _stable_before_each_restart,
    "stream-complete": _stream_complete,
    "two-replacements": _two_replacements,
    "one-at-a-time": _one_at_a_time,
    "ready-held": _ready_held,
    "model-verified": _model_verified,
    "ready-serves": _ready_serves,
    "readings-in-order": _readings_in_order,
}


def evaluate(
    sources: Characterization, rule_ids: Sequence[str] | None = None
) -> list[dict[str, str]]:
    """The state of each rule, in the order of :data:`RULES`."""
    findings = []
    for rule in RULES:
        if rule_ids is not None and rule.rule_id not in rule_ids:
            continue
        state, detail = _EVALUATORS[rule.rule_id](sources)
        findings.append(
            {
                "ruleId": rule.rule_id,
                "criterion": rule.criterion,
                "category": rule.category,
                "state": state,
                "detail": detail,
            }
        )
    return findings


def result_of(findings: Sequence[Mapping[str, str]]) -> str:
    """REFUSED when a precondition is not held, INCONCLUSIVE when another rule is
    not held, and CHARACTERIZED when each is held."""
    if any(
        item["state"] != HELD and item["ruleId"] in PRECONDITION_RULES
        for item in findings
    ):
        return REFUSED
    if any(item["state"] != HELD for item in findings):
        return INCONCLUSIVE
    return CHARACTERIZED


def _files(sources: Characterization) -> list[dict[str, str]]:
    names = [HEADER_FILE, CAPACITY_RECORD, PROVENANCE_FILE, DEPLOYMENTS_FILE]
    for restart in sources.restarts:
        base = f"{RESTARTS_DIRECTORY}/{restart.name}"
        names.extend(f"{base}/{name}" for name in RESTART_FILES)
        names.extend(
            f"{base}/{COMPLETION_PREFIX}{pod}.json"
            for pod in sorted(restart.completions)
        )
    files = []
    for name in names:
        data = _read_bytes(sources.directory, name)
        if data is not None:
            files.append({"name": name, "sha256": lf_digest(data)})
    return files


def bound_of(result: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """S: the maximum start-to-Ready interval. It has a value only when the
    result is CHARACTERIZED."""
    values = [
        row["startToReadyMs"] for row in rows if row["startToReadyMs"] is not None
    ]
    value = max(values) if result == CHARACTERIZED and values else None
    at = next(
        (
            {"restart": row["restart"], "pod": row["pod"]}
            for row in rows
            if value is not None and row["startToReadyMs"] == value
        ),
        None,
    )
    return {
        "symbol": "S",
        "rule": "the maximum startToReadyMs of every observation",
        "valueMs": value,
        "observations": len(rows) if value is not None else None,
        "firstObservedAt": at,
    }


def build_record(directory: Path, root: Path = REPO_ROOT) -> dict[str, Any]:
    """The record of one characterization directory."""
    sources = read_characterization(directory, root)
    findings = evaluate(sources)
    result = result_of(findings)
    unheld = [item for item in findings if item["state"] != HELD]
    environment = _environment(sources)
    rows = observations(sources)
    return {
        "schema": RECORD_SCHEMA,
        "characterization": CHARACTERIZATION,
        "result": result,
        "notHeld": {
            "categories": [
                category
                for category in CATEGORIES
                if any(item["category"] == category for item in unheld)
            ],
            "rules": [item["ruleId"] for item in unheld],
        },
        "collection": dict(sources.header),
        "target": {
            "releaseKey": TARGET_RELEASE_KEY,
            "apiReplicas": TARGET_API_REPLICAS,
            "runtimeReplicas": TARGET_RUNTIME_REPLICAS,
            "provider": SELECTED_PROVIDER,
            "restarts": len(RESTARTS),
            "replacementsPerRestart": REPLACEMENTS_PER_RESTART,
        },
        "identities": identities(sources),
        "environment": environment,
        "measurement": {
            "interval": "From the creation of a replacement pod to its first Ready "
            "condition in the watch stream.",
            "clock": "The cluster's timestamps: the creation instant of the pod and "
            "the transition instant of its Ready condition.",
            "resolutionMs": RESOLUTION_MS,
        },
        "observations": rows,
        "bound": bound_of(result, rows),
        "files": _files(sources),
        "findings": findings,
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def preconditions(directory: Path, root: Path = REPO_ROOT) -> list[dict[str, str]]:
    """The state of each precondition rule of a directory.

    The driver asks this before it requests a restart. It reads the header, the
    capacity record, the provenance, the Deployments, and the record of q1-1.
    """
    return evaluate(read_characterization(directory, root), PRECONDITION_RULES)


def record_text(record: Mapping[str, Any]) -> str:
    """The text of a record: indented JSON with sorted members and one final LF."""
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def committed_runs(root: Path = REPO_ROOT) -> list[Path]:
    """Every committed characterization directory."""
    return sorted(path for path in root.glob(RUNS_PATTERN) if path.is_dir())


def check_committed(root: Path = REPO_ROOT) -> list[str]:
    """Build the record of each committed directory again. Return each difference."""
    findings = []
    for directory in committed_runs(root):
        name = directory.relative_to(root).as_posix()
        stored = _read_bytes(directory, RECORD_FILE)
        if stored is None:
            findings.append(f"{name}: no {RECORD_FILE}")
            continue
        try:
            built = record_text(build_record(directory, root))
        except CollectionRefused as refused:
            findings.append(f"{name}: not a collection: {refused}")
            continue
        if stored.replace(b"\r\n", b"\n").decode("utf-8") != built:
            findings.append(f"{name}: {RECORD_FILE} is not what the directory gives")
    return findings
