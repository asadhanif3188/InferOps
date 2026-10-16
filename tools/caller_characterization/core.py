"""Q3, the stable caller characterization, as one record.

Q3 measures what the caller sees when the topology of the qualified release is
healthy and no fault is injected. It runs the RP-1 caller runner once, for at least five minutes,
against the API Service of the release that the Q1 qualification ``q1-1``
qualified, in the environment that ``q1-1`` selected. It records the successful
requests, the latency distribution, the gaps between successive successes, and
the canonical errors. ``G`` is the p99 of the gaps between successive successes.
When fewer than 100 requests succeeded, ``G`` is the maximum gap, and the record
says that the p99 is not meaningful. The result is ``CHARACTERIZED``,
``INCONCLUSIVE``, or ``REFUSED``.

A frozen driver prepares the release with the phase ``up`` of the Q1 driver,
starts the caller runner, watches the pods of the release while it runs, writes
what the cluster and the runner answered into one directory, and runs this
module. This module reads that directory and returns one record. It contacts no
cluster, and it runs no procedure.

**Healthy is a state of the topology, not of the caller.** Before the caller
starts, both Deployments are at 2 Ready replicas and exactly 2 API pods and 2
runtime pods exist, each Ready. While it runs, the watch shows no pod added, no
pod deleted, and no pod that is not Ready, and afterwards the same pods are Ready
with no container restart. A request that does not succeed is a caller result:
it is recorded, and it is not a reason to refuse the run.

**A precondition that is not held refuses.** The phase ``up`` completed, the
working tree was clean, the frozen inputs are at their pins, the delivery paths
equal the desired revision, the environment, the release, and the images are the
ones that ``q1-1`` states, and the topology is Ready. When one of these is not
held, the result is ``REFUSED``, and the driver starts no caller. When each is
held and a rule of the measurement is not held, the result is ``INCONCLUSIVE``.
A record states ``G`` only when the result is ``CHARACTERIZED``.

**A read that was not made is not a value.** An absent source gives the state
``not-observed`` to each rule that reads it, and a source of another form gives
``not-held``.

**The record is not a throughput benchmark.** It states no rate. Its latency
figures describe one closed-loop workload of two callers on one node, and no
figure of it is a capacity figure or a service level.

See docs/environment/stable-caller-characterization.md, which describes the
directory, each rule, the measurement, and the limits of a record, and
tests/domain/test_caller_characterization.py, which gives the module each
refusal.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

from tools.environment_qualification.core import (
    UP_REFUSALS,
    Source,
    Sources,
    environment_digest,
    environment_identity,
)
from tools.reliability_runner.core import CallerRecord, RunnerError, read_record
from tools.runtime_startup.core import Event, Stream, read_stream

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: The schema name of a record.
RECORD_SCHEMA: Final = "inferops.io/caller-characterization/v1alpha1"

#: The schema name that the driver writes into the header of a directory.
COLLECTION_SCHEMA: Final = "inferops.io/caller-characterization-collection/v1alpha1"

#: The schema name of the file in which the driver states the caller run.
CALLER_RUN_SCHEMA: Final = "inferops.io/caller-characterization-run/v1alpha1"

#: The characterization that a record states.
CHARACTERIZATION: Final = "Q3"

#: The experiment identifier of the freeze record. The driver gives it to the
#: caller runner.
EXPERIMENT_ID: Final = "v2-q3-stable-caller-characterization"

#: The freeze record that governs the driver and this module.
FREEZE_RECORD: Final = "docs/proof/experiments/v2-q3/freeze-r1.v1alpha1.json"

#: Every revision of the Q3 freeze record that a header may name. A record is
#: built again under the revision that its header names, so a later revision
#: that adds itself here leaves the records of earlier revisions as they were.
FREEZE_RECORDS: Final = (FREEZE_RECORD,)

#: The freeze record of Q1, whose phase up prepares the release.
QUALIFICATION_FREEZE_RECORD: Final = (
    "docs/proof/experiments/v2-q1/freeze-r1.v1alpha1.json"
)

#: The qualification that selected the environment, and its committed record.
#: Q3 holds the environment, the release, and the images to that record.
QUALIFICATION_ID: Final = "q1-1"
QUALIFICATION_RECORD: Final = (
    "docs/proof/experiments/v2-q1/runs/q1-1/record.v1alpha1.json"
)

#: The schema name of a Q1 record.
QUALIFICATION_SCHEMA: Final = "inferops.io/environment-qualification/v1alpha1"

#: Where committed characterization directories are found.
RUNS_PATTERN: Final = "docs/proof/experiments/v2-q3/runs/*"

#: The target of Q3: the release that q1-1 qualified. No option changes it.
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

#: The two tiers whose pods the driver reads and watches, with their replicas.
TIERS: Final = (
    (API_COMPONENT, TARGET_API_REPLICAS),
    (RUNTIME_COMPONENT, TARGET_RUNTIME_REPLICAS),
)

#: The bounds that the driver gives the caller runner. A plan with other bounds
#: is not a plan of Q3.
CALLER_DURATION_SECONDS: Final = 360
CALLER_REQUEST_CEILING: Final = 2000

#: The least run length of a characterization: five minutes.
MINIMUM_RUN_MS: Final = 300_000

#: The percentile of the gaps that G is, and the least number of successes for
#: which it is stated. With fewer successes, G is the maximum gap.
PERCENTILE: Final = 99
MINIMUM_SUCCESSES_FOR_PERCENTILE: Final = 100

#: The end state of a caller record that Q3 reads as a run of its full duration.
DURATION_END_STATE: Final = "duration"

#: The states of the Job of the caller run, as the driver read them.
JOB_STATES: Final = ("succeeded", "failed", "unfinished", "not-started")

#: The files of a directory. The driver restates each name.
HEADER_FILE: Final = "run.json"
CAPACITY_RECORD: Final = "capacity/record.v1alpha1.json"
PROVENANCE_FILE: Final = "provenance.json"
DEPLOYMENTS_FILE: Final = "deployments.json"
BEFORE_PODS_FILE: Final = "before.pods.json"
WATCH_FILE: Final = "watch.jsonl"
CALLER_RUN_FILE: Final = "caller-run.json"
PLAN_FILE: Final = "plan.json"
CALLER_FILE: Final = "caller.jsonl"
CALLER_REFUSED_FILE: Final = "caller.refused.jsonl"
AFTER_DEPLOYMENTS_FILE: Final = "after.deployments.json"
AFTER_PODS_FILE: Final = "after.pods.json"
RECORD_FILE: Final = "record.v1alpha1.json"

#: The files of a directory that a record reads, in order.
SOURCE_FILES: Final = (
    HEADER_FILE,
    CAPACITY_RECORD,
    PROVENANCE_FILE,
    DEPLOYMENTS_FILE,
    BEFORE_PODS_FILE,
    WATCH_FILE,
    CALLER_RUN_FILE,
    PLAN_FILE,
    CALLER_FILE,
    CALLER_REFUSED_FILE,
    AFTER_DEPLOYMENTS_FILE,
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
CALLER: Final = "caller"
MEASUREMENT: Final = "measurement"
EVIDENCE: Final = "evidence"

CATEGORIES: Final = (
    PREPARATION,
    DESIRED_STATE,
    ENVIRONMENT,
    RELEASE_IDENTITY,
    TOPOLOGY,
    CALLER,
    MEASUREMENT,
    EVIDENCE,
)

WORKING_TREE_STATES: Final = ("clean", "dirty", "unread")
DESIRED_STATE_DIFF_STATES: Final = ("none", "differs", "unread")
FREEZE_CHANGE_STATES: Final = ("none", "listed", "unread")


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
        "Q3-AC1",
        PREPARATION,
        "The phase up of the Q1 driver completed: it states no refusal, the target "
        "check refused nothing, and it ran at the executing commit of the "
        "characterization.",
    ),
    Rule(
        "working-tree-clean",
        "Q3-AC2",
        DESIRED_STATE,
        "The working tree was clean when the characterization started.",
    ),
    Rule(
        "procedure-frozen",
        "Q3-AC3",
        DESIRED_STATE,
        "The driver names a registered revision of the Q3 freeze record, that "
        "revision has the content that the checkout holds, and the freeze tool "
        "listed no changed material file of it or of the Q1 record when the "
        "characterization started.",
    ),
    Rule(
        "desired-revision-known",
        "Q3-AC4",
        DESIRED_STATE,
        "The desired revision is one full commit identifier, and the chart, the "
        "desired-state tree, and the controller manifests of the executing commit "
        "equal those of that revision.",
    ),
    Rule(
        "environment-qualified",
        "Q3-AC5",
        ENVIRONMENT,
        "The qualification q1-1 is QUALIFIED, the capacity gate accepted the target "
        "release key with 2 API replicas and 2 runtime replicas, and the "
        "environment identity of that capacity record has the digest that q1-1 "
        "states.",
    ),
    Rule(
        "release-qualified",
        "Q3-AC6",
        RELEASE_IDENTITY,
        "The provenance record resolves the target release key at the desired "
        "revision to the release identifier that q1-1 states, the API Deployment "
        "runs the API image digest that the phase up declared, and the runtime "
        "Deployment runs the runtime image that q1-1 states.",
    ),
    Rule(
        "topology-ready",
        "Q3-AC7",
        TOPOLOGY,
        "Before the caller started, the API Deployment and the runtime Deployment "
        "each state 2 replicas and report 2 replicas, 2 Ready, 2 available, and 2 "
        "updated at their current generation, and exactly 2 API pods and 2 runtime "
        "pods exist, each Ready and none being deleted.",
    ),
    Rule(
        "caller-run-completed",
        "Q3-AC8",
        CALLER,
        "The start of the caller run exited 0, its Job succeeded within the wait "
        "bound, the runner script collected its record, and the cleanup exited 0.",
    ),
    Rule(
        "caller-record-accepted",
        "Q3-AC9",
        CALLER,
        "The runner's reader accepts the caller record with its plan, in the mode "
        "in-cluster, for the Q3 experiment and the characterization identifier, "
        "with the release identifier of the provenance record declared, a duration "
        "of 360 s, and a request ceiling of 2000.",
    ),
    Rule(
        "five-minutes-run",
        "Q3-AC10",
        MEASUREMENT,
        "The caller run ended at its duration of 360 s, not at its ceiling or at a "
        "stop request, and it lasted at least 300,000 ms.",
    ),
    Rule(
        "gaps-observed",
        "Q3-AC11",
        MEASUREMENT,
        "The caller record holds at least 2 successful requests, so at least one "
        "gap between successive successes.",
    ),
    Rule(
        "stream-complete",
        "Q3-AC12",
        EVIDENCE,
        "The watch stream is a sequence of pod events of the API tier and the "
        "runtime tier with no ERROR event, it opens with one ADDED event for each "
        "pod of the reading before the caller, and the watch was started before the "
        "caller run was requested and stopped after the driver saw its Job end.",
    ),
    Rule(
        "topology-held",
        "Q3-AC13",
        TOPOLOGY,
        "While the caller ran, the watch stream shows no pod that the reading "
        "before does not list, no deleted pod, and no pod that is not Ready or is "
        "being deleted; after it, the same 4 pods are Ready with the restart count "
        "of each container that they had before, and both Deployments report 2 "
        "Ready replicas at the generation that they stated before.",
    ),
    Rule(
        "readings-in-order",
        "Q3-AC14",
        EVIDENCE,
        "The phase up started before the characterization, the caller run was "
        "requested after the characterization started, and the driver saw its Job "
        "end after it was requested and before the characterization finished.",
    ),
)

#: The rules whose failure refuses: they decide whether the characterization may
#: run in the qualified environment. The driver starts no caller unless each is
#: held.
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
    "A record does not establish a throughput, a rate, a capacity figure, or a "
    "benchmark. It states one closed-loop workload of two callers, sent for six "
    "minutes on one node.",
    "A record does not establish a service level, an availability, or a latency "
    "that a caller can expect. Its latency figures describe the requests of one "
    "run.",
    "A record does not establish what a caller sees while something fails or "
    "recovers. By the rules of the record, no API pod or runtime pod was added, "
    "deleted, not Ready, or restarted while the caller ran; the Service endpoints, "
    "the path from the API to the runtime, and the node were not read.",
    "A record does not establish that a percentile of fewer than 100 successes is "
    "meaningful. With fewer, G is the maximum gap.",
    "A record does not establish that the clock of the runner pod agrees with "
    "another clock. The gaps are differences of the instants of that one clock.",
    "A record does not establish that a source record is what its collection "
    "gives. The module reads the stored source records and does not build them "
    "again.",
    "A record does not establish a result of a reliability experiment. The bounds "
    "derived from G are stated by another record.",
    "A record does not establish production availability, high availability, or "
    "resilience to the loss of a node, a zone, or a region.",
    "A record does not establish anything about another provider, another node, "
    "another Kubernetes version, another release, another model, or another "
    "caller workload.",
)

_REVISION: Final = re.compile(r"[0-9a-f]{40}")
_DIGEST: Final = re.compile(r"sha256:[0-9a-f]{64}")
_HEX64: Final = re.compile(r"[0-9a-f]{64}")
_CHARACTERIZATION_ID: Final = re.compile(r"q3-[1-9][0-9]?")
_CATEGORY: Final = re.compile(r"[a-z][a-z-]{0,62}[a-z]")
_KEY: Final = re.compile(r"[a-z0-9][a-z0-9-]{0,62}/[a-z0-9][a-z0-9-]{0,62}")
_UID: Final = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_INSTANT: Final = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{3})?Z"
)
_IMAGE: Final = re.compile(r"[a-z0-9][a-z0-9._/:-]{0,199}@sha256:[0-9a-f]{64}")


def _text(value: object, pattern: re.Pattern[str]) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _optional(pattern: re.Pattern[str]) -> Callable[[object], bool]:
    return lambda value: value is None or _text(value, pattern)


def _count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _exit(value: object) -> bool:
    return value is None or _count(value) is not None


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

#: The members of the file of the caller run, and the test of each value. An exit
#: status is null when the command did not run, and an instant is null when it
#: was not reached.
_CALLER_RUN: Final[dict[str, Callable[[object], bool]]] = {
    "schema": lambda value: value == CALLER_RUN_SCHEMA,
    "requestedAt": lambda value: _text(value, _INSTANT),
    "startExit": _exit,
    "jobState": lambda value: value in JOB_STATES,
    "jobEndedAt": _optional(_INSTANT),
    "collectExit": _exit,
    "cleanupExit": _exit,
    "watchStartedAt": lambda value: _text(value, _INSTANT),
    "watchStoppedAt": _optional(_INSTANT),
}


class CollectionRefused(ValueError):
    """The directory is not a characterization directory, so no record exists."""


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


def _text_source(directory: Path, name: str) -> Source:
    data = _read_bytes(directory, name)
    if data is None:
        return Source(name, problem=ABSENT)
    try:
        return Source(name, value=data.decode("utf-8"))
    except UnicodeError:
        return Source(name, problem=UNREADABLE)


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
class Characterization:
    """Every source of one directory, read once."""

    header: Mapping[str, Any]
    capacity: Source
    provenance: Source
    deployments: Source
    before_pods: Source
    stream: Stream
    caller_run: Source
    plan: Source
    caller: Source
    caller_refused: bool
    after_deployments: Source
    after_pods: Source
    qualification: Source
    root: Path
    directory: Path


def read_characterization(directory: Path, root: Path = REPO_ROOT) -> Characterization:
    """Read the header and every source of a directory."""
    header = read_header(directory)
    return Characterization(
        header=header,
        capacity=_json_source(directory, CAPACITY_RECORD, CAPACITY_SCHEMA),
        provenance=_json_source(directory, PROVENANCE_FILE),
        deployments=_json_source(directory, DEPLOYMENTS_FILE),
        before_pods=_json_source(directory, BEFORE_PODS_FILE),
        stream=read_stream(_read_bytes(directory, WATCH_FILE)),
        caller_run=_json_source(directory, CALLER_RUN_FILE, CALLER_RUN_SCHEMA),
        plan=_text_source(directory, PLAN_FILE),
        caller=_text_source(directory, CALLER_FILE),
        caller_refused=(directory / CALLER_REFUSED_FILE).exists(),
        after_deployments=_json_source(directory, AFTER_DEPLOYMENTS_FILE),
        after_pods=_json_source(directory, AFTER_PODS_FILE),
        qualification=_json_source(root, QUALIFICATION_RECORD, QUALIFICATION_SCHEMA),
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


def _tier(item: Mapping[str, Any]) -> str | None:
    """The tier of a pod or a Deployment of the release, or nothing."""
    for component, _ in TIERS:
        if _labelled(item, component):
            return component
    return None


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


def _uid(pod: Mapping[str, Any]) -> str | None:
    """The identifier of a pod, or nothing when it is not one."""
    value = _dig(pod, "metadata", "uid")
    return value if _text(value, _UID) else None


def _restart_counts(pod: Mapping[str, Any]) -> dict[str, int] | None:
    """The restart count of each container and init container of a pod.

    Nothing is stated when a container states no count.
    """
    counts: dict[str, int] = {}
    for member in ("initContainerStatuses", "containerStatuses"):
        for status in _sequence(_dig(pod, "status", member)):
            name = _dig(status, "name")
            restarts = _count(_dig(status, "restartCount"))
            if not isinstance(name, str) or restarts is None:
                return None
            counts[f"{member}/{name}"] = restarts
    return counts or None


def caller_record(sources: Characterization) -> CallerRecord | None:
    """The caller record that the runner's reader accepts with its plan, or nothing."""
    if sources.caller_refused or not sources.caller.read or not sources.plan.read:
        return None
    try:
        return read_record(str(sources.caller.value), plan=str(sources.plan.value))
    except RunnerError:
        return None


def nearest_rank(values: Sequence[int], percentile: int) -> int | None:
    """The nearest-rank percentile: the value at rank ceil(percentile/100 * n).

    The values are read in ascending order. Nothing is stated for no value.
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = (percentile * len(ordered) + 99) // 100
    return ordered[max(rank, 1) - 1]


def success_instants(record: CallerRecord) -> list[datetime]:
    """The completion instants of the successful requests, in their order.

    Two completions of one instant are ordered by their sequence numbers. The
    instants are those of the runner pod's clock, to one millisecond.
    """
    rows = []
    for request in record.requests:
        if request["success"] is not True:
            continue
        finished = _instant(request["finishedAt"])
        if finished is not None:
            rows.append((finished, int(request["sequence"])))
    return [finished for finished, _ in sorted(rows)]


def success_gaps(record: CallerRecord) -> list[int]:
    """The gap between each two successive successes, in milliseconds.

    A gap is the time from the completion of one successful request to the
    completion of the next. The time before the first success and after the last
    is not a gap.
    """
    instants = success_instants(record)
    return [_milliseconds(earlier, later) for earlier, later in pairwise(instants)]


def _distribution(values: Sequence[int]) -> dict[str, int | None]:
    return {
        "count": len(values),
        "minMs": min(values) if values else None,
        "p50Ms": nearest_rank(values, 50),
        "p90Ms": nearest_rank(values, 90),
        "p99Ms": nearest_rank(values, 99),
        "maxMs": max(values) if values else None,
    }


def caller_summary(record: CallerRecord | None) -> dict[str, Any] | None:
    """What the caller saw: counts, latencies, gaps, and canonical errors.

    Nothing is stated when the caller record is not accepted. The figures are of
    this one run. They are not a rate, a capacity, or a service level.
    """
    if record is None:
        return None
    successes = [r for r in record.requests if r["success"] is True]
    instants = success_instants(record)
    errors = Counter(
        str(r["errorCode"])
        for r in record.requests
        if r["outcome"] != "success" and r["errorCode"] is not None
    )
    return {
        "startedAt": record.header["startedAt"],
        "finishedAt": record.end["finishedAt"],
        "endState": record.end["endState"],
        "elapsedMs": record.end["elapsedMs"],
        "requests": len(record.requests),
        "successes": len(successes),
        "outcomes": dict(sorted(record.end["outcomes"].items())),
        "canonicalErrors": dict(sorted(errors.items())),
        "successLatency": _distribution([int(r["latencyMs"]) for r in successes]),
        "gaps": _distribution(success_gaps(record)),
        "firstSuccessAt": None
        if not instants
        else instants[0].strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "lastSuccessAt": None
        if not instants
        else instants[-1].strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    }


def bound_of(result: str, record: CallerRecord | None) -> dict[str, Any]:
    """G: the p99 gap between successive successes, or the maximum gap when fewer
    than 100 requests succeeded. It has a value only when the result is
    CHARACTERIZED."""
    gaps = success_gaps(record) if record is not None else []
    successes = (
        sum(1 for r in record.requests if r["success"] is True)
        if record is not None
        else None
    )
    stated = result == CHARACTERIZED and successes is not None and bool(gaps)
    meaningful = (
        None
        if not stated or successes is None
        else successes >= MINIMUM_SUCCESSES_FOR_PERCENTILE
    )
    if not stated:
        value = None
        rule = None
    elif meaningful:
        value = nearest_rank(gaps, PERCENTILE)
        rule = "p99"
    else:
        value = max(gaps)
        rule = "maximum"
    return {
        "symbol": "G",
        "rule": rule,
        "valueMs": value,
        "percentile": PERCENTILE,
        "method": (
            "The nearest-rank p99 of the gaps between successive successes: the gap "
            "at rank ceil(0.99 * n) of the n gaps in ascending order. With fewer "
            "than 100 successes, the maximum gap."
        ),
        "minimumSuccessesForPercentile": MINIMUM_SUCCESSES_FOR_PERCENTILE,
        "percentileMeaningful": meaningful,
        "successes": successes if stated else None,
        "gaps": len(gaps) if stated else None,
    }


def identities(sources: Characterization) -> dict[str, Any]:
    """The immutable identities of the characterization. Unread ones are null."""
    header = sources.header
    environment = _environment(sources)
    freeze_path = (
        header["freezeRecord"] if header["freezeRecord"] in FREEZE_RECORDS else None
    )
    freeze = None if freeze_path is None else _read_bytes(sources.root, freeze_path)
    qualification = _read_bytes(sources.root, QUALIFICATION_RECORD)
    record = caller_record(sources)
    return {
        "executingCommit": header["executingCommit"],
        "desiredRevision": header["desiredRevision"],
        "releaseKey": header["releaseKey"],
        "releaseId": _release_id(sources),
        "apiImageDigest": header["apiImageDigest"],
        "runtimeImage": _dig(
            _qualified(sources), "identities", "runtimeImage", "reference"
        ),
        "provider": header["provider"],
        "kubernetesServerVersion": None
        if environment is None
        else environment["kubernetesServerVersion"],
        "environmentSha256": None
        if environment is None
        else environment_digest(environment),
        "callerProfile": None if record is None else dict(record.header["profile"]),
        "runnerSha256": None if record is None else record.header["runnerSha256"],
        "planSha256": None if record is None else record.header["planSha256"],
        "qualification": {
            "qualificationId": QUALIFICATION_ID,
            "path": QUALIFICATION_RECORD,
            "contentSha256": None
            if qualification is None
            else lf_digest(qualification),
        },
        "freezeRecord": {
            "path": freeze_path,
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
    if header["freezeRecord"] not in FREEZE_RECORDS:
        return NOT_HELD, f"the driver names {header['freezeRecord']}"
    data = _read_bytes(sources.root, header["freezeRecord"])
    if data is None:
        return NOT_OBSERVED, "the checkout holds no such Q3 freeze record"
    if header["freezeRecordSha256"] != lf_digest(data):
        return NOT_HELD, "the freeze record has other content than the checkout holds"
    for member, record in (
        ("freezeChanges", "Q3"),
        ("qualificationFreezeChanges", "Q1"),
    ):
        if header[member] == "unread":
            return NOT_OBSERVED, f"the changes of the {record} record were not read"
        if header[member] != "none":
            return NOT_HELD, f"the freeze tool listed a changed {record} material file"
    return HELD, "the Q3 and the Q1 freeze records list no changed material file"


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
    # The API image is held to the digest that the phase up declared, and not to
    # the one of q1-1: a build of the same inputs reports another manifest-list
    # digest. The inputs of the build are pinned by the Q1 record, which
    # procedure-frozen holds unchanged.
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
    return (
        HELD,
        f"release {release_id}, the declared API image, and the runtime image of "
        f"{QUALIFICATION_ID}",
    )


def _deployment_problem(
    deployment: Mapping[str, Any], replicas: int, generation: object = None
) -> str | None:
    """Why a Deployment is not settled at ``replicas``, or nothing when it is.

    When ``generation`` is given, the Deployment must state it.
    """
    status = _mapping(deployment.get("status"))
    if _dig(deployment, "spec", "replicas") != replicas:
        return f"states {_dig(deployment, 'spec', 'replicas')} replicas"
    for member in ("replicas", "readyReplicas", "availableReplicas", "updatedReplicas"):
        if status.get(member) != replicas:
            return f"reports {member} {status.get(member)}"
    current = _dig(deployment, "metadata", "generation")
    if _count(current) is None or status.get("observedGeneration") != current:
        return "reports a generation that is not its current one"
    if generation is not None and current != generation:
        return f"is at generation {current}, not {generation}"
    return None


def _pods_problem(source: Source, when: str) -> Outcome | None:
    """Why a reading of the pods is not 2 Ready pods of each tier, or nothing."""
    pods = _items(source)
    if pods is None:
        if not source.read:
            return _missing(source)
        return NOT_HELD, f"{source.name} is not a list of pods"
    for component, replicas in TIERS:
        found = [pod for pod in pods if _labelled(pod, component)]
        if len(found) != replicas:
            return NOT_HELD, f"{len(found)} {component} pods {when}, not {replicas}"
    if len(pods) != sum(replicas for _, replicas in TIERS):
        return NOT_HELD, f"a pod of the reading {when} is of another tier"
    for pod in pods:
        if _uid(pod) is None:
            return NOT_HELD, f"a pod of the reading {when} states no identifier"
        if _dig(pod, "metadata", "deletionTimestamp") is not None:
            return NOT_HELD, f"a pod was being deleted {when}"
        if not _is_ready(pod):
            return NOT_HELD, f"a pod was not Ready {when}"
    return None


def _topology_ready(sources: Characterization) -> Outcome:
    if not sources.deployments.read:
        return _missing(sources.deployments)
    items = _items(sources.deployments)
    if items is None:
        return NOT_HELD, f"{DEPLOYMENTS_FILE} is not a list of Deployments"
    for component, replicas in TIERS:
        found = _deployments(items, component)
        if len(found) != 1:
            return NOT_HELD, f"{len(found)} {component} Deployments, not 1"
        problem = _deployment_problem(found[0], replicas)
        if problem is not None:
            return NOT_HELD, f"the {component} Deployment {problem}"
    pods = _pods_problem(sources.before_pods, "before the caller")
    if pods is not None:
        return pods
    return HELD, "each Deployment at 2 Ready replicas, and 2 Ready pods of each tier"


def _caller_run_value(sources: Characterization, member: str) -> Any:
    return _dig(sources.caller_run.value, member)


def _caller_run_problem(sources: Characterization) -> Outcome | None:
    """Why the file of the caller run is not usable, or nothing when it is."""
    if not sources.caller_run.read:
        return _missing(sources.caller_run)
    value = _mapping(sources.caller_run.value)
    if set(value) != set(_CALLER_RUN):
        return NOT_HELD, f"{CALLER_RUN_FILE} states other members"
    if not all(test(value[name]) for name, test in _CALLER_RUN.items()):
        return NOT_HELD, f"{CALLER_RUN_FILE} states an unusable value"
    return None


def _caller_run_completed(sources: Characterization) -> Outcome:
    problem = _caller_run_problem(sources)
    if problem is not None:
        return problem
    if _caller_run_value(sources, "startExit") != 0:
        return NOT_HELD, "the start of the caller run did not exit 0"
    state = _caller_run_value(sources, "jobState")
    if state != "succeeded" or _caller_run_value(sources, "jobEndedAt") is None:
        return NOT_HELD, f"the Job of the caller run is {state}"
    if _caller_run_value(sources, "collectExit") != 0:
        return NOT_HELD, "the runner script did not collect the record"
    if _caller_run_value(sources, "cleanupExit") != 0:
        return NOT_HELD, "the cleanup of the caller run did not exit 0"
    return HELD, "the caller run started, succeeded, was collected, and was removed"


def _caller_record_accepted(sources: Characterization) -> Outcome:
    if sources.caller_refused:
        return NOT_HELD, "the runner script kept the caller record as refused"
    if not sources.caller.read:
        return _missing(sources.caller)
    if not sources.plan.read:
        return _missing(sources.plan)
    try:
        record = read_record(str(sources.caller.value), plan=str(sources.plan.value))
    except RunnerError as error:
        return NOT_HELD, f"the runner's reader refused the record: {error.rule}"
    header = record.header
    if header["mode"] != "in-cluster":
        return NOT_HELD, f"the record is of the mode {header['mode']}"
    if header["experimentId"] != EXPERIMENT_ID:
        return NOT_HELD, f"the record is of the experiment {header['experimentId']}"
    if header["runId"] != sources.header["characterizationId"]:
        return NOT_HELD, "the record is of another run identifier"
    bounds = _mapping(header["bounds"])
    if (bounds.get("durationSeconds"), bounds.get("requestCeiling")) != (
        CALLER_DURATION_SECONDS,
        CALLER_REQUEST_CEILING,
    ):
        return NOT_HELD, "the plan states another duration or request ceiling"
    release_id = _release_id(sources)
    if release_id is None:
        return NOT_OBSERVED, "no provenance release to compare"
    if (
        _dig(header, "release", "source") != "declared"
        or _dig(header, "release", "releaseId") != release_id
    ):
        return NOT_HELD, "the record declares another release"
    return HELD, f"the record of {len(record.requests)} requests is accepted"


def _five_minutes_run(sources: Characterization) -> Outcome:
    record = caller_record(sources)
    if record is None:
        return NOT_OBSERVED, "no accepted caller record was read"
    if record.end["endState"] != DURATION_END_STATE:
        return NOT_HELD, f"the run ended with {record.end['endState']}"
    if record.end["elapsedMs"] < MINIMUM_RUN_MS:
        return NOT_HELD, f"the run lasted {record.end['elapsedMs']} ms"
    return HELD, f"the run lasted {record.end['elapsedMs']} ms, to its duration"


def _gaps_observed(sources: Characterization) -> Outcome:
    record = caller_record(sources)
    if record is None:
        return NOT_OBSERVED, "no accepted caller record was read"
    successes = len(success_instants(record))
    if successes < 2:
        return NOT_HELD, f"{successes} successful requests, so no gap"
    return HELD, f"{successes} successful requests, {successes - 1} gaps"


def _before_uids(sources: Characterization) -> list[str] | None:
    items = _items(sources.before_pods)
    if items is None:
        return None
    uids = [_uid(item) for item in items]
    return None if None in uids else [uid for uid in uids if uid is not None]


def _stream_complete(sources: Characterization) -> Outcome:
    stream = sources.stream
    if stream.problem == ABSENT:
        return NOT_OBSERVED, f"{WATCH_FILE} was not read"
    if stream.problem is not None:
        return NOT_HELD, f"{WATCH_FILE}: {stream.problem}"
    for event in stream.events:
        if event.kind == "ERROR":
            return NOT_HELD, "the stream holds an ERROR event"
        if _dig(event.pod, "kind") not in (None, "Pod") or _tier(event.pod) is None:
            return NOT_HELD, "the stream holds another object"
        if _uid(event.pod) is None:
            return NOT_HELD, "an event names no pod identifier"
    before = _before_uids(sources)
    if before is None:
        return NOT_OBSERVED, "the reading before the caller was not read"
    opening = stream.events[: len(before)]
    if sorted(str(_uid(event.pod)) for event in opening) != sorted(before) or any(
        event.kind != "ADDED" for event in opening
    ):
        return NOT_HELD, "the stream does not open with the pods of the reading before"
    problem = _caller_run_problem(sources)
    if problem is not None:
        return problem
    started = _instant(_caller_run_value(sources, "watchStartedAt"))
    stopped = _instant(_caller_run_value(sources, "watchStoppedAt"))
    requested = _instant(_caller_run_value(sources, "requestedAt"))
    ended = _instant(_caller_run_value(sources, "jobEndedAt"))
    if started is None or stopped is None or requested is None or ended is None:
        return NOT_OBSERVED, "the watch or the caller run has no end"
    if started > requested:
        return NOT_HELD, "the watch started after the caller run was requested"
    if stopped < ended:
        return NOT_HELD, "the watch stopped before the Job of the caller run ended"
    return HELD, "the stream opens with the pods before and outlasts the caller run"


def _events_problem(events: Sequence[Event], before: Sequence[str]) -> str | None:
    for event in events:
        uid = _uid(event.pod)
        if uid not in before:
            return "the stream shows a pod that the reading before does not list"
        if event.kind == "DELETED":
            return "the stream shows a deleted pod"
        if _dig(event.pod, "metadata", "deletionTimestamp") is not None:
            return "the stream shows a pod that was being deleted"
        if not _is_ready(event.pod):
            return "the stream shows a pod that was not Ready"
    return None


def _topology_held(sources: Characterization) -> Outcome:
    if sources.stream.problem is not None:
        if sources.stream.problem == ABSENT:
            return NOT_OBSERVED, f"{WATCH_FILE} was not read"
        return NOT_HELD, f"{WATCH_FILE}: {sources.stream.problem}"
    before = _before_uids(sources)
    if before is None:
        return NOT_OBSERVED, "the reading before the caller was not read"
    problem = _events_problem(sources.stream.events, before)
    if problem is not None:
        return NOT_HELD, problem
    pods = _pods_problem(sources.after_pods, "after the caller")
    if pods is not None:
        return pods
    after = {_uid(pod): pod for pod in _items(sources.after_pods) or []}
    if sorted(str(uid) for uid in after) != sorted(before):
        return NOT_HELD, "the reading after lists other pods than the reading before"
    earlier = {_uid(pod): pod for pod in _items(sources.before_pods) or []}
    for uid, pod in after.items():
        counts = _restart_counts(pod)
        if counts is None or counts != _restart_counts(earlier[uid]):
            return NOT_HELD, "a container of a pod restarted, or states no count"
    if not sources.after_deployments.read:
        return _missing(sources.after_deployments)
    items = _items(sources.after_deployments)
    previous = _items(sources.deployments)
    if items is None or previous is None:
        return NOT_HELD, f"{AFTER_DEPLOYMENTS_FILE} is not a list of Deployments"
    for component, replicas in TIERS:
        found = _deployments(items, component)
        stated = _deployments(previous, component)
        if len(found) != 1 or len(stated) != 1:
            return NOT_HELD, f"not one {component} Deployment after the caller"
        problem = _deployment_problem(
            found[0], replicas, _dig(stated[0], "metadata", "generation")
        )
        if problem is not None:
            return NOT_HELD, f"after the caller, the {component} Deployment {problem}"
    return HELD, "the same 4 pods stayed Ready, and no container restarted"


def _readings_in_order(sources: Characterization) -> Outcome:
    header = sources.header
    up = _instant(header["upStartedAt"])
    started = _instant(header["startedAt"])
    finished = _instant(header["finishedAt"])
    if up is None or started is None or finished is None:
        return NOT_OBSERVED, "the phase up or the characterization has no instant"
    if not up < started <= finished:
        return NOT_HELD, "the phase up did not start before the characterization"
    problem = _caller_run_problem(sources)
    if problem is not None:
        return problem
    requested = _instant(_caller_run_value(sources, "requestedAt"))
    ended = _instant(_caller_run_value(sources, "jobEndedAt"))
    if requested is None or ended is None:
        return NOT_OBSERVED, "the caller run has no request or end instant"
    if requested < started:
        return NOT_HELD, "the caller run was requested before the characterization"
    if not requested < ended <= finished:
        return NOT_HELD, "the caller run is out of order"
    return HELD, "the phase up, then the caller run, inside the characterization"


_EVALUATORS: Final[dict[str, Callable[[Characterization], Outcome]]] = {
    "preparation-completed": _preparation_completed,
    "working-tree-clean": _working_tree_clean,
    "procedure-frozen": _procedure_frozen,
    "desired-revision-known": _desired_revision_known,
    "environment-qualified": _environment_qualified,
    "release-qualified": _release_qualified,
    "topology-ready": _topology_ready,
    "caller-run-completed": _caller_run_completed,
    "caller-record-accepted": _caller_record_accepted,
    "five-minutes-run": _five_minutes_run,
    "gaps-observed": _gaps_observed,
    "stream-complete": _stream_complete,
    "topology-held": _topology_held,
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
    files = []
    for name in SOURCE_FILES:
        data = _read_bytes(sources.directory, name)
        if data is not None:
            files.append({"name": name, "sha256": lf_digest(data)})
    return files


def build_record(directory: Path, root: Path = REPO_ROOT) -> dict[str, Any]:
    """The record of one characterization directory."""
    sources = read_characterization(directory, root)
    findings = evaluate(sources)
    result = result_of(findings)
    unheld = [item for item in findings if item["state"] != HELD]
    record = caller_record(sources)
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
            "callerDurationSeconds": CALLER_DURATION_SECONDS,
            "callerRequestCeiling": CALLER_REQUEST_CEILING,
            "minimumRunMs": MINIMUM_RUN_MS,
        },
        "identities": identities(sources),
        "environment": _environment(sources),
        "measurement": {
            "gap": "From the completion instant of one successful request to the "
            "completion instant of the next successful request, in the order of "
            "their completions.",
            "clock": "The wall clock of the runner pod, to one millisecond: the "
            "finishedAt instant of each request line.",
            "latency": "The latencyMs of each successful request, from the "
            "monotonic clock of the runner pod.",
            "percentiles": "Nearest rank: the value at rank ceil(p/100 * n) of the "
            "n values in ascending order.",
        },
        "caller": caller_summary(record),
        "bound": bound_of(result, record),
        "files": _files(sources),
        "findings": findings,
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def preconditions(directory: Path, root: Path = REPO_ROOT) -> list[dict[str, str]]:
    """The state of each precondition rule of a directory.

    The driver asks this before it starts the caller. It reads the header, the
    capacity record, the provenance, the Deployments, the pods, and the record of
    q1-1.
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
