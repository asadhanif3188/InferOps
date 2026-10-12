"""The infrastructure timelines of one experiment run, as four streams.

A collector reads one cluster a bounded number of times and writes what each
read returned into one directory. This module reads that directory. It reads no
cluster. It returns four streams, and each stream holds one reading for each
sample:

- ``endpoints``: the Ready endpoints of the API Service and of the serving
  runtime Service;
- ``pods``: each pod of the two tiers, with its UID, its revision, its Ready
  condition, its restart counts, and its deletion timestamp;
- ``deployments``: the replica counts and the revision of the Deployment of
  each tier;
- ``argo``: what the delivery controller reported about one Application.

**A value that was not read is not a value.** Each field of a reading has one
of three states. ``reported`` carries the value. ``missing`` means that the
object was read and did not hold the field. ``malformed`` means that the field
held a value of another type or of another form. Only ``reported`` carries a
value, and no function here replaces an absent value with zero, with false, or
with a healthy state. A read that did not answer gives a reading with no value
at all.

**One time basis.** The collector states two instants for each read: when the
read started and when it finished, on the wall clock of the collecting host, in
UTC, to one millisecond. They are the time basis of every stream. An instant
that a cluster component wrote is normalised to UTC and keeps the resolution it
was written with. The two kinds of instant are not on one clock, and
:data:`LIMITATIONS` says what follows from that.

**What a stream holds is an allowlist.** Each text value of a reading has a
fixed form, and a value of another form is ``malformed`` and is not copied. A
stream holds no address, no node name, no image, no environment variable, no
message, and no kubeconfig context.

**A stream is not caller truth.** It states what the cluster published and what
the delivery controller reported. It is not a request that a caller sent and had
answered. :data:`DOES_NOT_ESTABLISH` is part of every stream.

:func:`changes` compares each reading with the next one and returns each value
that differs, with the interval that the two reads bound. What happened between
two readings was not observed.

See docs/environment/experiment-timelines.md and
tests/domain/test_experiment_timeline.py.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

from tools.service_endpoint_state import TIER_OBSERVED, TIERS
from tools.service_endpoint_state import observe as observe_endpoints
from tools.service_endpoint_state.core import (
    COMPONENT_LABEL,
    INSTANCE_LABEL,
    _shape_faults,
)

#: The schema name of each line of a stream.
STREAM_SCHEMA: Final = "inferops.io/experiment-timeline/v1alpha1"

#: The schema name that the collector writes into the header of a collection.
COLLECTION_SCHEMA: Final = "inferops.io/experiment-timeline-collection/v1alpha1"

#: The schema name of the document that :func:`changes` returns.
CHANGES_SCHEMA: Final = "inferops.io/experiment-timeline-changes/v1alpha1"

ENDPOINTS: Final = "endpoints"
PODS: Final = "pods"
DEPLOYMENTS: Final = "deployments"
ARGO: Final = "argo"

#: The four streams. Each name is a registered raw role of the evidence layout.
STREAMS: Final = (ENDPOINTS, PODS, DEPLOYMENTS, ARGO)

#: The file of each stream.
STREAM_FILES: Final[Mapping[str, str]] = {name: f"{name}.jsonl" for name in STREAMS}

#: The files of a collection. The collector restates each name.
HEADER_FILE: Final = "collection.json"
END_FILE: Final = "collection.end"
SAMPLE_STEM: Final = "sample-{index:04d}"
META_SUFFIX: Final = ".meta"
WORKLOAD_SUFFIX: Final = ".workload.json"
APPLICATION_SUFFIX: Final = ".application.json"

#: The bounds of one collection. The collector restates each one.
MAX_SAMPLES: Final = 1800
MAX_INTERVAL_SECONDS: Final = 30
MAX_READ_TIMEOUT_SECONDS: Final = 60

#: The largest number of pods of the two tiers that a reading states. It is
#: twice the bound of the endpoint-state record for one Service.
MAX_PODS: Final = 64

#: The largest number of containers that a reading states for one pod.
MAX_CONTAINERS: Final = 8

#: The exit status of the command when a collection or a stream is refused.
REFUSED_EXIT: Final = 3

REPORTED: Final = "reported"
MISSING: Final = "missing"
MALFORMED: Final = "malformed"

#: The states of one field of one reading. Only ``reported`` carries a value.
FIELD_STATES: Final = (REPORTED, MISSING, MALFORMED)

ANSWERED: Final = "answered"
ABSENT: Final = "absent"
UNANSWERED: Final = "unanswered"
UNREADABLE: Final = "unreadable"
NOT_TAKEN: Final = "not-taken"

#: The states of one read. ``answered`` is the one state that gives values.
#: ``absent`` is an answer that held no object, and only the Application read
#: has it. ``unanswered`` is a read that failed or timed out. ``unreadable`` is
#: an answer that this module cannot use. ``not-taken`` is a sample that the
#: collection was asked for and did not write.
READ_STATES: Final = (ANSWERED, ABSENT, UNANSWERED, UNREADABLE, NOT_TAKEN)

#: The kinds of the workload read. The collector asks for these five in one call.
WORKLOAD_KINDS: Final = ("Service", "EndpointSlice", "Pod", "ReplicaSet", "Deployment")

REVISION_ANNOTATION: Final = "deployment.kubernetes.io/revision"
TEMPLATE_HASH_LABEL: Final = "pod-template-hash"

#: The phases of a pod, as Kubernetes documents them.
POD_PHASES: Final = ("Pending", "Running", "Succeeded", "Failed", "Unknown")

#: The values of the status of a condition, as Kubernetes documents them.
CONDITION_STATUSES: Final = ("True", "False", "Unknown")

#: The two conditions of a Deployment that a reading states.
DEPLOYMENT_CONDITIONS: Final = ("Available", "Progressing")

#: The counts of a Deployment that a reading states, with the path of each.
DEPLOYMENT_COUNTS: Final[Mapping[str, tuple[str, ...]]] = {
    "generation": ("metadata", "generation"),
    "observedGeneration": ("status", "observedGeneration"),
    "specReplicas": ("spec", "replicas"),
    "replicas": ("status", "replicas"),
    "updatedReplicas": ("status", "updatedReplicas"),
    "readyReplicas": ("status", "readyReplicas"),
    "availableReplicas": ("status", "availableReplicas"),
    "unavailableReplicas": ("status", "unavailableReplicas"),
}

_WORD: Final = "word"
_COMMIT: Final = "commit"
_REF: Final = "ref"
_INSTANT: Final = "instant"
_COUNT: Final = "count"

#: The fields of the Application that a reading states, with the path and the
#: form of each. The names are those of the reconciliation record.
APPLICATION_FIELDS: Final[Mapping[str, tuple[tuple[str, ...], str]]] = {
    "followedRevision": (("spec", "source", "targetRevision"), _REF),
    "syncStatus": (("status", "sync", "status"), _WORD),
    "resolvedRevision": (("status", "sync", "revision"), _COMMIT),
    "healthStatus": (("status", "health", "status"), _WORD),
    "operationPhase": (("status", "operationState", "phase"), _WORD),
    "operationRevision": (
        ("status", "operationState", "syncResult", "revision"),
        _COMMIT,
    ),
    "operationStartedAt": (("status", "operationState", "startedAt"), _INSTANT),
    "operationFinishedAt": (("status", "operationState", "finishedAt"), _INSTANT),
    "reconciledAt": (("status", "reconciledAt"), _INSTANT),
    "deletionTimestamp": (("metadata", "deletionTimestamp"), _INSTANT),
}

#: Fields of the last entry of the history of the Application.
APPLICATION_HISTORY_FIELDS: Final[Mapping[str, tuple[str, str]]] = {
    "historyId": ("id", _COUNT),
    "historyRevision": ("revision", _COMMIT),
    "historyDeployedAt": ("deployedAt", _INSTANT),
}

#: What a stream leaves out of each object, on purpose.
OMITTED: Final[tuple[str, ...]] = (
    "The addresses of an endpoint and of a pod.",
    "The node name, the zone, and the hostname of an endpoint and of a pod.",
    "The images, the commands, the environment variables, and the volumes of a pod.",
    "Each message of a condition, of a container state, and of an operation.",
    "The repository address of the Application.",
    "The name of the kubeconfig context. A context name can hold an account identifier.",
    "Every pod of the namespace that is not a pod of one of the two tiers. A "
    "reading states their number and nothing else.",
)

#: The limits of a stream.
LIMITATIONS: Final[tuple[str, ...]] = (
    "The instants read.startedAt and read.finishedAt are the wall clock of the "
    "host that ran the collector, in UTC, to one millisecond. A wall clock can "
    "be set while a collection runs. The end line names each reading whose "
    "start is before the finish of the reading before it.",
    "A reading is the state at an instant that is not known. The instant is not "
    "before read.startedAt and not after read.finishedAt, when the API server "
    "answered from its present state. The workload read is one command that "
    "makes one request for each kind, so its kinds are not one atomic reading.",
    "An instant that a cluster component wrote is on the clock of that "
    "component. It is normalised to UTC and keeps its resolution, which is one "
    "second for each instant that Kubernetes writes into the fields read here. "
    "It is not on the clock of the collecting host.",
    "The difference between the clock of the collecting host and a clock of the "
    "cluster was not measured. The end line counts the cluster instants, other "
    "than a deletion timestamp, that are later than the finish of the read that "
    "returned them. A count above zero shows that the two clocks differ. A "
    "count of zero does not bound the difference.",
    "The deletion timestamp of a pod is the instant at which its grace period "
    "ends. It is not the instant of the request to delete the pod, and it can be "
    "later than the read that returned it.",
    "No order between two events is established when the events are less than "
    "one second apart and one of them is a cluster instant, or when both are in "
    "the interval of one read.",
    "A state that began and ended between two readings is in no reading.",
    "The Kubernetes API omits a status count of a Deployment that is zero, and "
    "it omits a count that the controller did not write yet. A reading states "
    "each omitted count as missing. It does not state zero.",
    "An identity is a name and a UID. It is valid for the life of that object "
    "on that cluster. It is not a stable identity of a replica.",
    "A pod that left the read and a pod that entered it are two facts. No "
    "reading states that one pod replaced another.",
    "The revision of a pod is the revision annotation of the ReplicaSet that "
    "owns it, in the same read. It is missing when that ReplicaSet is not in "
    "the read.",
    f"A reading with more than {MAX_PODS} pods of the two tiers states no pod.",
    "The collection names the commit of the working tree that ran the "
    "collector, and the SHA-256 of the collector script and of its library. It "
    "does not state whether the tree had a change that was not committed.",
)

#: What no stream establishes.
DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "That a caller obtained a completion at any instant. A Ready endpoint, a "
    "Ready pod, a replica count, a sync state, and a health state are what the "
    "cluster and the delivery controller published. None of them is a request "
    "that a caller sent and had answered.",
    "That a field with a state other than reported had any value. A field that "
    "was not reported is not zero, not Ready, not synced, and not healthy.",
    "The state of the cluster at a sample whose read is not answered. A read "
    "that did not answer is not an empty namespace.",
    "The instant of a change. A change is bounded by two reads, and the "
    "interval between them is the smallest interval that a stream supports.",
    "That a request reached a Ready endpoint, or that a pod behind a Ready "
    "endpoint could serve inference.",
    "That the delivery controller applied the commit it reported, or that an "
    "object of the release was rendered at that commit.",
    "The cause of a change. A stream holds no event, no log, and no message.",
    "A result of an experiment. A stream is evidence that an analysis reads. "
    "This module computes no metric and gives no verdict.",
)

RULE_UNREADABLE: Final = "timeline-stream-unreadable"
RULE_HEADER: Final = "timeline-header-unsupported"
RULE_MEMBERS: Final = "timeline-members-unsupported"
RULE_SEQUENCE: Final = "timeline-reading-out-of-sequence"
RULE_READ: Final = "timeline-read-state-unsupported"
RULE_INSTANT: Final = "timeline-instant-invalid"
RULE_END: Final = "timeline-end-missing"
RULE_COUNTS: Final = "timeline-counts-differ"

#: Each rule that :func:`read_stream` holds a stream to, with its statement.
RULES: Final[Mapping[str, str]] = {
    RULE_UNREADABLE: (
        "A stream is UTF-8 text. Each line is one JSON object with no member "
        "stated twice."
    ),
    RULE_HEADER: (
        "The first line is the header. It states the stream schema, one of the "
        "four stream names, an experiment identifier, and a run identifier, "
        "each in its form."
    ),
    RULE_MEMBERS: (
        "Each line has exactly the members of its record and of its stream."
    ),
    RULE_SEQUENCE: (
        "The readings are numbered from 1 with no gap, and no line follows the "
        "end line."
    ),
    RULE_READ: "Each reading states one of the registered read states.",
    RULE_INSTANT: (
        "Each instant of a read is absent or is UTC to one millisecond in the "
        "one registered form, and a read does not finish before it starts."
    ),
    RULE_END: "The last line is the end line.",
    RULE_COUNTS: (
        "The end line states the number of readings and the number of readings "
        "in each read state, as the stream holds them."
    ),
}

_HEADER_MEMBERS: Final = frozenset(
    {
        "schema",
        "experimentId",
        "runId",
        "provider",
        "serverVersion",
        "namespace",
        "release",
        "application",
        "applicationNamespace",
        "executingCommit",
        "procedureSha256",
        "librarySha256",
        "requestedSamples",
        "intervalSeconds",
        "readTimeoutSeconds",
    }
)
_STREAM_HEADER_MEMBERS: Final = frozenset(
    {
        "record",
        "schema",
        "stream",
        "experimentId",
        "runId",
        "collection",
        "clock",
        "bounds",
        "omitted",
        "limitations",
        "doesNotEstablish",
    }
)
_READING_MEMBERS: Final[Mapping[str, frozenset[str]]] = {
    ENDPOINTS: frozenset({"record", "index", "read", "tiers", "faults"}),
    PODS: frozenset({"record", "index", "read", "pods", "otherPods", "faults"}),
    DEPLOYMENTS: frozenset({"record", "index", "read", "tiers", "faults"}),
    ARGO: frozenset({"record", "index", "read", "application", "faults"}),
}
_READ_MEMBERS: Final = frozenset({"state", "startedAt", "finishedAt"})
_END_MEMBERS: Final = frozenset(
    {
        "record",
        "readings",
        "byReadState",
        "clusterInstantsAfterRead",
        "instantsOutOfOrder",
    }
)

_IDENTIFIER: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,62}")
_LABEL: Final = re.compile(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?")
_NAME: Final = re.compile(r"[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?")
_UID: Final = re.compile(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}")
_COMMIT_FORM: Final = re.compile(r"[0-9a-f]{40}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_VERSION: Final = re.compile(r"v[0-9][0-9A-Za-z.+-]{0,62}")
_WORD_FORM: Final = re.compile(r"[A-Za-z][A-Za-z0-9]{0,63}")
_REF_FORM: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}")
_HASH_FORM: Final = re.compile(r"[a-z0-9]{1,16}")
_DIGITS: Final = re.compile(r"[0-9]{1,9}")
_COLLECTOR_INSTANT: Final = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z"
)
_CLUSTER_INSTANT: Final = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt]([0-9]{2}):([0-9]{2}):([0-9]{2})"
    r"(?:\.([0-9]{1,9}))?([Zz]|[+-][0-9]{2}:[0-9]{2})"
)
_SAMPLE_META: Final = re.compile(r"sample-([0-9]{4})\.meta")
_UNSAFE: Final = re.compile(r"[^A-Za-z0-9 .,:;_/'()-]")

_MAX_COUNT: Final = 999_999_999
_FAULT_LENGTH: Final = 240
_FAULT_LIMIT: Final = 10


class CollectionRefused(Exception):
    """The directory is not one collection, so no stream can be built from it."""


class StreamRefused(Exception):
    """A text that is not a stream of this module."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(f"{rule}: {message}")
        self.rule = rule
        self.message = message


# --------------------------------------------------------------------------
# Instants
# --------------------------------------------------------------------------


def format_instant(instant: datetime) -> str:
    """An instant in UTC to one millisecond, in the one form a stream uses."""
    instant = instant.astimezone(UTC)
    return f"{instant:%Y-%m-%dT%H:%M:%S}.{instant.microsecond // 1000:03d}Z"


def collector_instant(value: object) -> datetime | None:
    """An instant that the collector wrote, or None when it is not usable.

    The collector writes one form: UTC to one millisecond. A text of another
    form is not read as an instant, and neither is a date that does not exist.
    """
    if not isinstance(value, str) or _COLLECTOR_INSTANT.fullmatch(value) is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _parse_cluster_instant(value: str) -> tuple[datetime, bool] | None:
    """A cluster instant in UTC, and whether it stated a fraction of a second."""
    match = _CLUSTER_INSTANT.fullmatch(value)
    if match is None:
        return None
    year, month, day, hour, minute, second = (int(match.group(n)) for n in range(1, 7))
    fraction, zone = match.group(7), match.group(8)
    if zone in ("Z", "z"):
        offset = timedelta(0)
    else:
        sign = -1 if zone[0] == "-" else 1
        hours, minutes = int(zone[1:3]), int(zone[4:6])
        if hours > 23 or minutes > 59:
            return None
        offset = sign * timedelta(hours=hours, minutes=minutes)
    microsecond = int((fraction or "0").ljust(6, "0")[:6])
    try:
        local = datetime(
            year, month, day, hour, minute, second, microsecond, timezone(offset)
        )
        return local.astimezone(UTC), fraction is not None
    except (ValueError, OverflowError):
        return None


def cluster_instant(value: object) -> dict[str, Any]:
    """An instant that a cluster component wrote, as a field in UTC.

    An instant with no fraction of a second keeps a resolution of one second.
    An instant with a fraction is cut to one millisecond. It is not rounded.
    """
    if value is None:
        return {"state": MISSING}
    parsed = _parse_cluster_instant(value) if isinstance(value, str) else None
    if parsed is None:
        return {"state": MALFORMED}
    instant, fractional = parsed
    if fractional:
        return {
            "state": REPORTED,
            "value": format_instant(instant),
            "resolution": "millisecond",
        }
    return {
        "state": REPORTED,
        "value": f"{instant:%Y-%m-%dT%H:%M:%SZ}",
        "resolution": "second",
    }


# --------------------------------------------------------------------------
# Fields
# --------------------------------------------------------------------------


def _at(document: object, path: Sequence[str]) -> tuple[str, Any]:
    """The value at ``path``. An absent key and a null are both ``missing``."""
    current: Any = document
    for key in path:
        if not isinstance(current, Mapping):
            return MALFORMED, None
        if key not in current or current[key] is None:
            return MISSING, None
        current = current[key]
    return REPORTED, current


def _field(state: str, value: Any = None) -> dict[str, Any]:
    return (
        {"state": REPORTED, "value": value} if state == REPORTED else {"state": state}
    )


def _text(
    document: object, path: Sequence[str], form: re.Pattern[str]
) -> dict[str, Any]:
    state, value = _at(document, path)
    if state != REPORTED:
        return _field(state)
    if not isinstance(value, str) or form.fullmatch(value) is None:
        return _field(MALFORMED)
    return _field(REPORTED, value)


def _choice(
    document: object, path: Sequence[str], choices: Sequence[str]
) -> dict[str, Any]:
    state, value = _at(document, path)
    if state != REPORTED:
        return _field(state)
    return _field(REPORTED, value) if value in choices else _field(MALFORMED)


def _is_count(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= _MAX_COUNT
    )


def _count(document: object, path: Sequence[str]) -> dict[str, Any]:
    state, value = _at(document, path)
    if state != REPORTED:
        return _field(state)
    return _field(REPORTED, value) if _is_count(value) else _field(MALFORMED)


def _flag(document: object, path: Sequence[str]) -> dict[str, Any]:
    state, value = _at(document, path)
    if state != REPORTED:
        return _field(state)
    return _field(REPORTED, value) if isinstance(value, bool) else _field(MALFORMED)


def _instant_at(document: object, path: Sequence[str]) -> dict[str, Any]:
    state, value = _at(document, path)
    return cluster_instant(value) if state == REPORTED else _field(state)


def _annotated_count(item: Mapping[str, Any], annotation: str) -> dict[str, Any]:
    """A count that an annotation states as text, such as a revision."""
    state, value = _at(item, ("metadata", "annotations", annotation))
    if state != REPORTED:
        return _field(state)
    if not isinstance(value, str) or _DIGITS.fullmatch(value) is None:
        return _field(MALFORMED)
    return _field(REPORTED, int(value))


def _safe(text: str) -> str:
    """One fault as one bounded line of a fixed set of characters."""
    text = _UNSAFE.sub("?", " ".join(text.split()))
    return text if len(text) <= _FAULT_LENGTH else text[: _FAULT_LENGTH - 3] + "..."


def _bounded(faults: Sequence[str]) -> list[str]:
    """At most a fixed number of faults, and the number of the others."""
    kept = [_safe(fault) for fault in faults[:_FAULT_LIMIT]]
    if len(faults) > _FAULT_LIMIT:
        kept.append(f"{len(faults) - _FAULT_LIMIT} more fault(s) are not listed")
    return kept


# --------------------------------------------------------------------------
# One directory, as samples
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Read:
    """One read of one sample: its state, its two instants, and its answer."""

    state: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    document: Any = None
    detail: str | None = None

    def as_document(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "startedAt": None
            if self.started_at is None
            else format_instant(self.started_at),
            "finishedAt": None
            if self.finished_at is None
            else format_instant(self.finished_at),
        }


@dataclass(frozen=True)
class Sample:
    """One sample: the workload read and the Application read."""

    index: int
    workload: Read
    application: Read


@dataclass(frozen=True)
class Collection:
    """What one collector run wrote: its header and its samples."""

    header: Mapping[str, Any]
    completed: dict[str, Any]
    samples: tuple[Sample, ...]

    @property
    def complete(self) -> bool:
        """Every sample that was asked for was taken, and the collector said so."""
        return (
            self.completed.get("state") == REPORTED
            and self.completed.get("value") == self.header["requestedSamples"]
            and all(
                sample.workload.state != NOT_TAKEN
                and sample.application.state != NOT_TAKEN
                for sample in self.samples
            )
        )


def _pairs(path: Path) -> dict[str, str]:
    """The ``key=value`` lines of one file that the collector wrote."""
    found: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key:
            found[key] = value
    return found


def _load(path: Path) -> tuple[bool, Any]:
    """Whether a file holds one JSON value, and that value."""
    try:
        return True, json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return False, None


def _header(directory: Path) -> dict[str, Any]:
    """The header that the collector wrote, held to its members and their form."""
    path = directory / HEADER_FILE
    if not path.is_file():
        raise CollectionRefused(f"the directory holds no {HEADER_FILE}")
    readable, header = _load(path)
    if not readable or not isinstance(header, dict):
        raise CollectionRefused(f"{HEADER_FILE} is not one JSON object")
    if set(header) != _HEADER_MEMBERS:
        raise CollectionRefused(
            f"{HEADER_FILE} holds the members {sorted(header)}, and a collection "
            f"holds {sorted(_HEADER_MEMBERS)}"
        )
    if header["schema"] != COLLECTION_SCHEMA:
        raise CollectionRefused(
            f"{HEADER_FILE} states another schema than {COLLECTION_SCHEMA}"
        )
    forms = {
        "experimentId": _IDENTIFIER,
        "runId": _IDENTIFIER,
        "provider": _LABEL,
        "namespace": _LABEL,
        "release": _LABEL,
        "application": _LABEL,
        "applicationNamespace": _LABEL,
        "executingCommit": _COMMIT_FORM,
        "procedureSha256": _SHA256,
        "librarySha256": _SHA256,
    }
    for name, form in forms.items():
        value = header[name]
        if not isinstance(value, str) or form.fullmatch(value) is None:
            raise CollectionRefused(f"{HEADER_FILE} states no usable {name}")
    bounds = {
        "requestedSamples": MAX_SAMPLES,
        "intervalSeconds": MAX_INTERVAL_SECONDS,
        "readTimeoutSeconds": MAX_READ_TIMEOUT_SECONDS,
    }
    for name, maximum in bounds.items():
        value = header[name]
        if not _is_count(value) or not 1 <= value <= maximum:
            raise CollectionRefused(
                f"{HEADER_FILE} does not state {name} as a whole number from 1 "
                f"to {maximum}"
            )
    # A server version that the collector could not read is an empty text. It is
    # kept as a field that is missing, and it is not a reason to refuse.
    version = header["serverVersion"]
    if not isinstance(version, str):
        raise CollectionRefused(f"{HEADER_FILE} states no usable serverVersion")
    header = dict(header)
    if not version:
        header["serverVersion"] = {"state": MISSING}
    elif _VERSION.fullmatch(version) is None:
        header["serverVersion"] = {"state": MALFORMED}
    else:
        header["serverVersion"] = {"state": REPORTED, "value": version}
    return header


def _read(
    meta: Mapping[str, str], name: str, path: Path, *, may_be_absent: bool
) -> Read:
    """One read of one sample, from the status file and the file of the answer."""
    started = collector_instant(meta.get(f"{name}StartedAt"))
    finished = collector_instant(meta.get(f"{name}FinishedAt"))
    stated = meta.get(f"{name}Read")
    if started is None or finished is None or finished < started:
        # A reading with no usable instants has no place on a timeline.
        return Read(
            UNREADABLE, detail="the sample states no usable instants for this read"
        )
    if stated == UNANSWERED:
        return Read(UNANSWERED, started, finished)
    if stated != ANSWERED:
        return Read(
            UNREADABLE,
            started,
            finished,
            detail="the sample does not state whether this read answered",
        )
    if not path.is_file():
        return Read(
            UNREADABLE,
            started,
            finished,
            detail="the sample states an answer, and the directory holds no file of it",
        )
    if may_be_absent and not path.read_bytes().strip():
        return Read(ABSENT, started, finished)
    readable, document = _load(path)
    if not readable or not isinstance(document, dict):
        return Read(
            UNREADABLE, started, finished, detail="the answer is not one JSON object"
        )
    return Read(ANSWERED, started, finished, document)


def _sample(directory: Path, index: int) -> Sample:
    stem = SAMPLE_STEM.format(index=index)
    meta_path = directory / f"{stem}{META_SUFFIX}"
    if not meta_path.is_file():
        return Sample(index, Read(NOT_TAKEN), Read(NOT_TAKEN))
    meta = _pairs(meta_path)
    return Sample(
        index,
        _read(
            meta,
            "workload",
            directory / f"{stem}{WORKLOAD_SUFFIX}",
            may_be_absent=False,
        ),
        _read(
            meta,
            "application",
            directory / f"{stem}{APPLICATION_SUFFIX}",
            may_be_absent=True,
        ),
    )


def read_collection(directory: Path) -> Collection:
    """What one collector run wrote: its header and each sample it was asked for.

    A sample that the collection was asked for and did not write is returned
    with the read state ``not-taken``.

    Raises:
        CollectionRefused: the directory holds no usable header, or it holds a
            sample that the header did not ask for.
    """
    if not directory.is_dir():
        raise CollectionRefused("the path is not a directory")
    header = _header(directory)
    requested = header["requestedSamples"]
    for entry in sorted(directory.iterdir()):
        match = _SAMPLE_META.fullmatch(entry.name)
        if match is not None and not 1 <= int(match.group(1)) <= requested:
            raise CollectionRefused(
                f"the directory holds {entry.name}, and the header asked for "
                f"{requested} sample(s)"
            )
    end_path = directory / END_FILE
    stated = _pairs(end_path).get("completedSamples") if end_path.is_file() else None
    if stated is None:
        completed: dict[str, Any] = {"state": MISSING}
    elif stated.isascii() and _DIGITS.fullmatch(stated) is not None:
        completed = {"state": REPORTED, "value": int(stated)}
    else:
        completed = {"state": MALFORMED}
    samples = tuple(_sample(directory, index) for index in range(1, requested + 1))
    return Collection(header, completed, samples)


# --------------------------------------------------------------------------
# The workload read, by kind
# --------------------------------------------------------------------------


def _by_kind(document: Mapping[str, Any]) -> tuple[dict[str, list[Any]], list[str]]:
    """The items of one workload read, by kind, and each fault of the list."""
    found: dict[str, list[Any]] = {kind: [] for kind in WORKLOAD_KINDS}
    faults: list[str] = []
    items = document.get("items")
    if document.get("kind") != "List" or not isinstance(items, list):
        return found, ["the answer is not a list of objects"]
    for index, item in enumerate(items):
        kind = item.get("kind") if isinstance(item, dict) else None
        if kind not in found:
            faults.append(f"item {index} is not an object of a kind that was asked for")
            continue
        found[kind].append(item)
    return found, faults


def _object_faults(
    items: Sequence[Any], kind: str, namespace: str, faults: list[str]
) -> None:
    """The members that each stream reads of every object of one kind."""
    names: list[str] = []
    uids: list[str] = []
    for index, item in enumerate(items):
        label = f"{kind} {index}"
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            faults.append(f"{label}: metadata is not an object")
            continue
        name, uid = metadata.get("name"), metadata.get("uid")
        if not isinstance(name, str) or _NAME.fullmatch(name) is None:
            faults.append(f"{label}: metadata.name is not a name")
        else:
            names.append(name)
        if not isinstance(uid, str) or _UID.fullmatch(uid) is None:
            faults.append(f"{label}: metadata.uid is not a UID")
        else:
            uids.append(uid)
        if metadata.get("namespace") != namespace:
            faults.append(f"{label}: the object is not in the namespace {namespace}")
        for member in ("labels", "annotations"):
            held = metadata.get(member)
            if held is None:
                continue
            if not isinstance(held, dict) or not all(
                isinstance(value, str) for value in held.values()
            ):
                faults.append(f"{label}: metadata.{member} is not an object of text")
    for what, values in (("name", names), ("UID", uids)):
        repeated = {value for value in values if values.count(value) > 1}
        if repeated:
            faults.append(
                f"{len(repeated)} {what}(s) are stated by more than one {kind}"
            )


def _label(item: Mapping[str, Any], name: str) -> str | None:
    labels = item["metadata"].get("labels") or {}
    value = labels.get(name)
    return value if isinstance(value, str) else None


def _tier_of(item: Mapping[str, Any], release: str) -> str | None:
    """The tier that an object of the release belongs to, or None."""
    if _label(item, INSTANCE_LABEL) != release:
        return None
    tier = _label(item, COMPONENT_LABEL)
    return tier if tier in TIERS else None


# --------------------------------------------------------------------------
# The four readings of one sample
# --------------------------------------------------------------------------


def _endpoints(
    kinds: Mapping[str, list[Any]], release: str, namespace: str
) -> tuple[list[dict[str, Any]] | None, list[str]]:
    """The Ready endpoint state of each tier, by the rules of the endpoint record."""
    faults: list[str] = []
    services, slices = kinds["Service"], kinds["EndpointSlice"]
    _shape_faults(services, slices, namespace, faults)
    if faults:
        return None, faults
    tiers, broken = observe_endpoints(
        services, slices, release=release, namespace=namespace
    )
    return tiers, [
        f"{rule_id}: {detail}"
        for rule_id, details in broken.items()
        for detail in details
    ]


def _owner(pod: Mapping[str, Any]) -> tuple[dict[str, Any], str | None]:
    """The controller that owns a pod, as a field, and its UID when it has one."""
    state, references = _at(pod, ("metadata", "ownerReferences"))
    if state != REPORTED:
        return _field(state), None
    if not isinstance(references, list):
        return _field(MALFORMED), None
    controllers = [
        entry
        for entry in references
        if isinstance(entry, dict) and entry.get("controller") is True
    ]
    if not controllers:
        return _field(MISSING), None
    if len(controllers) > 1:
        return _field(MALFORMED), None
    kind, name, uid = (controllers[0].get(key) for key in ("kind", "name", "uid"))
    if (
        not isinstance(kind, str)
        or _WORD_FORM.fullmatch(kind) is None
        or not isinstance(name, str)
        or _NAME.fullmatch(name) is None
    ):
        return _field(MALFORMED), None
    usable = isinstance(uid, str) and _UID.fullmatch(uid) is not None
    return _field(REPORTED, {"kind": kind, "name": name}), uid if usable else None


def _containers(pod: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Each container of a pod as it reported, and the sum of the restart counts.

    The sum is reported only when each container reports its count. A pod with
    no container status has a sum that is missing. It does not have a sum of
    zero.
    """
    state, statuses = _at(pod, ("status", "containerStatuses"))
    if state != REPORTED:
        return _field(state), _field(state)
    if (
        not isinstance(statuses, list)
        or not statuses
        or len(statuses) > MAX_CONTAINERS
        or not all(isinstance(entry, dict) for entry in statuses)
    ):
        return _field(MALFORMED), _field(MALFORMED)
    listed = [
        {
            "name": _text(entry, ("name",), _LABEL),
            "ready": _flag(entry, ("ready",)),
            "started": _flag(entry, ("started",)),
            "restartCount": _count(entry, ("restartCount",)),
        }
        for entry in statuses
    ]
    counts = [entry["restartCount"] for entry in listed]
    if all(count["state"] == REPORTED for count in counts):
        total = _field(REPORTED, sum(count["value"] for count in counts))
    else:
        total = _field(MALFORMED)
    return _field(REPORTED, listed), total


def _ready_condition(pod: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """The status of the Ready condition of a pod, and when it last changed.

    A pod with no Ready condition has a status that is missing. It is not read
    as not Ready. ``Unknown`` is a value of its own.
    """
    state, conditions = _at(pod, ("status", "conditions"))
    if state != REPORTED:
        return _field(state), _field(state)
    if not isinstance(conditions, list):
        return _field(MALFORMED), _field(MALFORMED)
    ready = [
        entry
        for entry in conditions
        if isinstance(entry, dict) and entry.get("type") == "Ready"
    ]
    if not ready:
        return _field(MISSING), _field(MISSING)
    if len(ready) > 1:
        return _field(MALFORMED), _field(MALFORMED)
    return (
        _choice(ready[0], ("status",), CONDITION_STATUSES),
        _instant_at(ready[0], ("lastTransitionTime",)),
    )


def _pods(
    kinds: Mapping[str, list[Any]], release: str, namespace: str
) -> tuple[list[dict[str, Any]] | None, int | None, list[str]]:
    """Each pod of the two tiers, and the number of the other pods."""
    faults: list[str] = []
    _object_faults(kinds["Pod"], "Pod", namespace, faults)
    _object_faults(kinds["ReplicaSet"], "ReplicaSet", namespace, faults)
    if faults:
        return None, None, faults
    own = [(pod, _tier_of(pod, release)) for pod in kinds["Pod"]]
    of_tiers = [(pod, tier) for pod, tier in own if tier is not None]
    if len(of_tiers) > MAX_PODS:
        return (
            None,
            None,
            [f"the read holds {len(of_tiers)} pods of the two tiers"],
        )
    sets = {item["metadata"]["uid"]: item for item in kinds["ReplicaSet"]}
    listed = []
    for pod, tier in of_tiers:
        owner, owner_uid = _owner(pod)
        owning_set = (
            sets.get(owner_uid)
            if owner_uid is not None
            and owner["state"] == REPORTED
            and owner["value"]["kind"] == "ReplicaSet"
            else None
        )
        ready, ready_since = _ready_condition(pod)
        containers, restarts = _containers(pod)
        listed.append(
            {
                "name": pod["metadata"]["name"],
                "uid": pod["metadata"]["uid"],
                "tier": tier,
                "templateHash": _text(
                    pod, ("metadata", "labels", TEMPLATE_HASH_LABEL), _HASH_FORM
                ),
                "owner": owner,
                "revision": _annotated_count(owning_set, REVISION_ANNOTATION)
                if owning_set is not None
                else _field(MISSING),
                "phase": _choice(pod, ("status", "phase"), POD_PHASES),
                "ready": ready,
                "readyTransitionAt": ready_since,
                "containers": containers,
                "restartCount": restarts,
                "createdAt": _instant_at(pod, ("metadata", "creationTimestamp")),
                "deletionTimestamp": _instant_at(
                    pod, ("metadata", "deletionTimestamp")
                ),
                "deletionGracePeriodSeconds": _count(
                    pod, ("metadata", "deletionGracePeriodSeconds")
                ),
            }
        )
    listed.sort(key=lambda entry: (entry["tier"], entry["name"], entry["uid"]))
    return listed, len(own) - len(of_tiers), []


def _deployment_condition(item: Mapping[str, Any], kind: str) -> dict[str, Any]:
    state, conditions = _at(item, ("status", "conditions"))
    if state != REPORTED:
        return _field(state)
    if not isinstance(conditions, list):
        return _field(MALFORMED)
    found = [
        entry
        for entry in conditions
        if isinstance(entry, dict) and entry.get("type") == kind
    ]
    if not found:
        return _field(MISSING)
    if len(found) > 1:
        return _field(MALFORMED)
    return _field(
        REPORTED,
        {
            "status": _choice(found[0], ("status",), CONDITION_STATUSES),
            "reason": _text(found[0], ("reason",), _WORD_FORM),
            "lastTransitionTime": _instant_at(found[0], ("lastTransitionTime",)),
            "lastUpdateTime": _instant_at(found[0], ("lastUpdateTime",)),
        },
    )


def _deployments(
    kinds: Mapping[str, list[Any]], release: str, namespace: str
) -> tuple[list[dict[str, Any]] | None, list[str]]:
    """The Deployment of each tier: its counts, its revision, its conditions."""
    faults: list[str] = []
    _object_faults(kinds["Deployment"], "Deployment", namespace, faults)
    if faults:
        return None, faults
    tiers = []
    for tier in TIERS:
        own = [item for item in kinds["Deployment"] if _tier_of(item, release) == tier]
        if len(own) != 1:
            found = f"{len(own)} Deployments" if own else "no Deployment"
            faults.append(
                f"{tier}: {found} of the release {release} carry this component label"
            )
            tiers.append({"tier": tier, "state": "refused"})
            continue
        [item] = own
        document: dict[str, Any] = {
            "tier": tier,
            "state": TIER_OBSERVED,
            "name": item["metadata"]["name"],
            "uid": item["metadata"]["uid"],
            "revision": _annotated_count(item, REVISION_ANNOTATION),
        }
        for name, path in DEPLOYMENT_COUNTS.items():
            document[name] = _count(item, path)
        document["conditions"] = {
            kind: _deployment_condition(item, kind) for kind in DEPLOYMENT_CONDITIONS
        }
        tiers.append(document)
    return tiers, faults


def application_fields(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Every allowlisted field of one Application object, each with its state."""

    def typed(source: object, path: Sequence[str], form: str) -> dict[str, Any]:
        if form == _WORD:
            return _text(source, path, _WORD_FORM)
        if form == _COMMIT:
            return _text(source, path, _COMMIT_FORM)
        if form == _REF:
            return _text(source, path, _REF_FORM)
        if form == _COUNT:
            return _count(source, path)
        return _instant_at(source, path)

    fields = {
        name: typed(document, path, form)
        for name, (path, form) in APPLICATION_FIELDS.items()
    }
    state, history = _at(document, ("status", "history"))
    last: Any = None
    if state == REPORTED:
        if not isinstance(history, list):
            state = MALFORMED
        elif not history:
            state = MISSING
        elif not isinstance(history[-1], Mapping):
            state = MALFORMED
        else:
            last = history[-1]
    for name, (key, form) in APPLICATION_HISTORY_FIELDS.items():
        fields[name] = typed(last, (key,), form) if state == REPORTED else _field(state)
    return fields


def _application(
    read: Read, name: str, namespace: str
) -> tuple[dict[str, Any] | None, list[str]]:
    """What the delivery controller reported, or None with the reason."""
    document = read.document
    metadata = document.get("metadata")
    if (
        document.get("kind") != "Application"
        or not isinstance(metadata, dict)
        or metadata.get("name") != name
        or metadata.get("namespace") != namespace
    ):
        return None, ["the answer is not the Application that the collection names"]
    return application_fields(document), []


# --------------------------------------------------------------------------
# The streams
# --------------------------------------------------------------------------


def _instants_of(value: object) -> Iterator[datetime]:
    """Each cluster instant that a reading reports as a time that passed.

    A deletion timestamp is left out. Kubernetes sets it to the end of the grace
    period, so it can be later than the read on one clock.
    """
    if isinstance(value, dict):
        if value.get("state") == REPORTED and "resolution" in value:
            parsed = _parse_cluster_instant(value["value"])
            if parsed is not None:
                yield parsed[0]
            return
        for name, member in value.items():
            if name != "deletionTimestamp":
                yield from _instants_of(member)
    elif isinstance(value, list):
        for member in value:
            yield from _instants_of(member)


def _end(readings: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The end line of one stream: its counts and its two clock observations."""
    states = [reading["read"]["state"] for reading in readings]
    later = []
    for reading in readings:
        finished = collector_instant(reading["read"]["finishedAt"])
        if finished is None:
            continue
        for instant in _instants_of(
            {k: v for k, v in reading.items() if k not in ("read", "faults")}
        ):
            if instant > finished:
                later.append((instant - finished) // timedelta(milliseconds=1))
    out_of_order = []
    previous: datetime | None = None
    for reading in readings:
        started = collector_instant(reading["read"]["startedAt"])
        finished = collector_instant(reading["read"]["finishedAt"])
        if started is None or finished is None:
            continue
        if previous is not None and started < previous:
            out_of_order.append(reading["index"])
        previous = finished
    return {
        "record": "end",
        "readings": len(readings),
        "byReadState": {state: states.count(state) for state in READ_STATES},
        "clusterInstantsAfterRead": {
            "count": len(later),
            "largestMilliseconds": max(later) if later else None,
        },
        "instantsOutOfOrder": out_of_order,
    }


def _stream_header(stream: str, collection: Collection) -> dict[str, Any]:
    header = collection.header
    return {
        "record": "header",
        "schema": STREAM_SCHEMA,
        "stream": stream,
        "experimentId": header["experimentId"],
        "runId": header["runId"],
        "collection": {
            **{
                name: header[name]
                for name in sorted(
                    _HEADER_MEMBERS - {"schema", "experimentId", "runId"}
                )
            },
            "completedSamples": collection.completed,
            "complete": collection.complete,
        },
        "clock": {
            "read": {
                "members": ["read.startedAt", "read.finishedAt"],
                "source": "the wall clock of the host that ran the collector",
                "zone": "UTC",
                "resolution": "millisecond",
            },
            "cluster": {
                "members": "each field that states a resolution",
                "source": "the clock of the cluster component that wrote the value",
                "zone": "UTC, after normalisation",
                "resolution": "as each field states it",
            },
            "skew": "not-measured",
        },
        "bounds": {
            "tiers": list(TIERS),
            "maxSamples": MAX_SAMPLES,
            "maxIntervalSeconds": MAX_INTERVAL_SECONDS,
            "maxPods": MAX_PODS,
            "maxContainersPerPod": MAX_CONTAINERS,
        },
        "omitted": list(OMITTED),
        "limitations": list(LIMITATIONS),
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def _workload_readings(
    collection: Collection, sample: Sample
) -> dict[str, dict[str, Any]]:
    """The three readings that the workload read of one sample gives."""
    release = collection.header["release"]
    namespace = collection.header["namespace"]
    read = sample.workload
    base = {"record": "reading", "index": sample.index, "read": read.as_document()}
    empty: dict[str, dict[str, Any]] = {
        ENDPOINTS: {**base, "tiers": None, "faults": []},
        PODS: {**base, "pods": None, "otherPods": None, "faults": []},
        DEPLOYMENTS: {**base, "tiers": None, "faults": []},
    }
    if read.state != ANSWERED:
        if read.detail is not None:
            for reading in empty.values():
                reading["faults"] = [read.detail]
        return empty
    kinds, list_faults = _by_kind(read.document)
    if list_faults:
        for reading in empty.values():
            reading["faults"] = _bounded(list_faults)
        return empty
    endpoint_tiers, endpoint_faults = _endpoints(kinds, release, namespace)
    pods, others, pod_faults = _pods(kinds, release, namespace)
    deployment_tiers, deployment_faults = _deployments(kinds, release, namespace)
    return {
        ENDPOINTS: {
            **base,
            "tiers": endpoint_tiers,
            "faults": _bounded(endpoint_faults),
        },
        PODS: {
            **base,
            "pods": pods,
            "otherPods": others,
            "faults": _bounded(pod_faults),
        },
        DEPLOYMENTS: {
            **base,
            "tiers": deployment_tiers,
            "faults": _bounded(deployment_faults),
        },
    }


def _application_reading(collection: Collection, sample: Sample) -> dict[str, Any]:
    read = sample.application
    reading: dict[str, Any] = {
        "record": "reading",
        "index": sample.index,
        "read": read.as_document(),
        "application": None,
        "faults": [] if read.detail is None else [read.detail],
    }
    if read.state == ANSWERED:
        fields, faults = _application(
            read,
            collection.header["application"],
            collection.header["applicationNamespace"],
        )
        reading["application"] = fields
        reading["faults"] = _bounded(faults)
    return reading


def build_streams(directory: Path) -> dict[str, list[dict[str, Any]]]:
    """The four streams of one collection, each as its lines in order.

    Raises:
        CollectionRefused: the directory is not a collection.
    """
    collection = read_collection(directory)
    readings: dict[str, list[dict[str, Any]]] = {name: [] for name in STREAMS}
    for sample in collection.samples:
        for name, reading in _workload_readings(collection, sample).items():
            readings[name].append(reading)
        readings[ARGO].append(_application_reading(collection, sample))
    return {
        name: [_stream_header(name, collection), *readings[name], _end(readings[name])]
        for name in STREAMS
    }


def stream_text(lines: Sequence[Mapping[str, Any]]) -> str:
    """A stream as the text that is stored: one line for each record, sorted members."""
    return "".join(
        json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n" for line in lines
    )


# --------------------------------------------------------------------------
# A stored stream, read back
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Stream:
    """One stored stream that :func:`read_stream` accepted."""

    header: Mapping[str, Any]
    readings: tuple[Mapping[str, Any], ...]
    end: Mapping[str, Any]

    @property
    def name(self) -> str:
        return str(self.header["stream"])

    def summary(self) -> str:
        counts = self.end["byReadState"]
        stated = ", ".join(
            f"{counts[state]} {state}" for state in READ_STATES if counts[state]
        )
        return f"{self.name}: {len(self.readings)} reading(s): {stated or 'none'}"


def _no_repeat(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for key, value in pairs:
        if key in found:
            raise ValueError(f"the member {key!r} is stated twice")
        found[key] = value
    return found


def _stored_instant(value: object, where: str) -> datetime | None:
    if value is None:
        return None
    instant = collector_instant(value)
    if instant is None:
        raise StreamRefused(
            RULE_INSTANT,
            f"{where} is not UTC to one millisecond in the registered form",
        )
    return instant


def read_stream(text: str) -> Stream:
    """A stored stream, held to its form.

    This reads the form of a stream: the header, the sequence, the members of
    each line, the read states, the instants of each read, and the counts of
    the end line. It does not read the fields of a reading for their form, and
    it does not show that a stream is what a collection gives.

    Raises:
        StreamRefused: a rule of :data:`RULES` is not held.
    """
    lines: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        try:
            document = json.loads(line, object_pairs_hook=_no_repeat)
        except (ValueError, RecursionError) as fault:
            raise StreamRefused(
                RULE_UNREADABLE, f"line {number} is not one JSON object"
            ) from fault
        if not isinstance(document, dict):
            raise StreamRefused(
                RULE_UNREADABLE, f"line {number} is not one JSON object"
            )
        lines.append(document)
    if not lines or lines[0].get("record") != "header":
        raise StreamRefused(RULE_HEADER, "the first line is not a header")
    header = lines[0]
    if set(header) != _STREAM_HEADER_MEMBERS:
        raise StreamRefused(RULE_MEMBERS, "the header does not have its members")
    if header["schema"] != STREAM_SCHEMA or header["stream"] not in STREAMS:
        raise StreamRefused(
            RULE_HEADER, "the header states another schema or an unregistered stream"
        )
    for name in ("experimentId", "runId"):
        value = header[name]
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise StreamRefused(RULE_HEADER, f"the header states no usable {name}")
    if len(lines) < 2 or lines[-1].get("record") != "end":
        raise StreamRefused(RULE_END, "the last line is not an end line")
    end = lines[-1]
    if set(end) != _END_MEMBERS:
        raise StreamRefused(RULE_MEMBERS, "the end line does not have its members")
    members = _READING_MEMBERS[header["stream"]]
    readings = lines[1:-1]
    for position, reading in enumerate(readings, start=1):
        where = f"line {position + 1}"
        if reading.get("record") != "reading":
            raise StreamRefused(RULE_SEQUENCE, f"{where} is not a reading")
        if set(reading) != members:
            raise StreamRefused(RULE_MEMBERS, f"{where} does not have its members")
        if reading["index"] != position or isinstance(reading["index"], bool):
            raise StreamRefused(RULE_SEQUENCE, f"{where} is not reading {position}")
        read = reading["read"]
        if not isinstance(read, dict) or set(read) != _READ_MEMBERS:
            raise StreamRefused(
                RULE_MEMBERS, f"{where}: read does not have its members"
            )
        if read["state"] not in READ_STATES:
            raise StreamRefused(RULE_READ, f"{where} states an unregistered read state")
        started = _stored_instant(read["startedAt"], f"{where}: read.startedAt")
        finished = _stored_instant(read["finishedAt"], f"{where}: read.finishedAt")
        if (started is None) != (finished is None):
            raise StreamRefused(RULE_INSTANT, f"{where} states one instant of two")
        if started is not None and finished is not None and finished < started:
            raise StreamRefused(RULE_INSTANT, f"{where} finishes before it starts")
    states = [reading["read"]["state"] for reading in readings]
    if end["readings"] != len(readings) or end["byReadState"] != {
        state: states.count(state) for state in READ_STATES
    }:
        raise StreamRefused(
            RULE_COUNTS,
            "the end line does not state the readings that the stream holds",
        )
    return Stream(header, tuple(readings), end)


# --------------------------------------------------------------------------
# Changes between consecutive readings
# --------------------------------------------------------------------------

NOT_COLLECTED: Final = "not-collected"
REFUSED: Final = "refused"
PRESENT: Final = "present"

#: The fields of a pod whose changes :func:`changes` reports.
POD_CHANGE_FIELDS: Final = (
    "ready",
    "phase",
    "restartCount",
    "revision",
    "deletionTimestamp",
)

#: The fields of a Deployment whose changes :func:`changes` reports.
DEPLOYMENT_CHANGE_FIELDS: Final = ("revision", *DEPLOYMENT_COUNTS)

_Values = dict[tuple[str, str], dict[str, Any]]


def _values(stream: str, reading: Mapping[str, Any]) -> _Values | str:
    """Each tracked value of one reading, or the one state of the whole reading."""
    state = reading["read"]["state"]
    if state == ABSENT:
        return {("application", PRESENT): _field(REPORTED, False)}
    if state != ANSWERED:
        return NOT_COLLECTED
    found: _Values = {}
    if stream == ARGO:
        if reading["application"] is None:
            return REFUSED
        found["application", PRESENT] = _field(REPORTED, True)
        for name, field in reading["application"].items():
            found["application", name] = field
        return found
    if stream == PODS:
        if reading["pods"] is None:
            return REFUSED
        for pod in reading["pods"]:
            found[pod["uid"], PRESENT] = _field(
                REPORTED, {"name": pod["name"], "tier": pod["tier"]}
            )
            for name in POD_CHANGE_FIELDS:
                found[pod["uid"], name] = pod[name]
        return found
    if reading["tiers"] is None:
        return REFUSED
    for tier in reading["tiers"]:
        name = tier["tier"]
        observed = tier["state"] == TIER_OBSERVED
        found[name, "state"] = _field(REPORTED, tier["state"])
        if stream == ENDPOINTS:
            figures = tier["endpoints"] if observed else None
            for member in ("total", "ready", "notReady", "serving", "terminating"):
                found[name, member] = (
                    _field(REPORTED, figures[member])
                    if figures is not None
                    else {"state": REFUSED}
                )
            found[name, "readyPods"] = (
                _field(REPORTED, sorted(pod["podUid"] for pod in tier["ready"]))
                if observed
                else {"state": REFUSED}
            )
        else:
            for member in DEPLOYMENT_CHANGE_FIELDS:
                found[name, member] = tier[member] if observed else {"state": REFUSED}
    return found


def changes(stream: Stream) -> dict[str, Any]:
    """Each tracked value that differs between two consecutive readings.

    A change states the two readings and the interval that their reads bound:
    not before the start of the earlier read, and not after the finish of the
    later read. A value that was reported and is then not reported is a change
    to that state. No value is carried across a reading that did not report it.

    An object that is in one reading and not in the next gives one change of
    ``present``. It gives no change for each of its fields.
    """
    found = []
    for before, after in pairwise(stream.readings):
        old, new = _values(stream.name, before), _values(stream.name, after)
        if isinstance(old, str) and isinstance(new, str):
            continue
        keys = sorted(
            set(old if isinstance(old, dict) else ())
            | set(new if isinstance(new, dict) else ())
        )
        for key in keys:
            subject, name = key
            was = old.get(key) if isinstance(old, dict) else {"state": old}
            now = new.get(key) if isinstance(new, dict) else {"state": new}
            if was is None or now is None:
                # The object is in one of the two readings only.
                if name != PRESENT:
                    continue
                was = was or {"state": ABSENT}
                now = now or {"state": ABSENT}
            if was == now:
                continue
            found.append(
                {
                    "subject": subject,
                    "field": name,
                    "fromReading": before["index"],
                    "toReading": after["index"],
                    "notBefore": before["read"]["startedAt"],
                    "notAfter": after["read"]["finishedAt"],
                    "from": was,
                    "to": now,
                }
            )
    return {
        "schema": CHANGES_SCHEMA,
        "stream": stream.name,
        "experimentId": stream.header["experimentId"],
        "runId": stream.header["runId"],
        "readings": len(stream.readings),
        "changes": found,
        "limitations": [
            "A change is a difference between two consecutive readings. What "
            "happened between two readings was not observed.",
            "The interval of a change is on the clock of the collecting host. A "
            "bound that is null is a read with no usable instant.",
            "A change from or to not-collected, refused, or absent states that a "
            "reading gave no value. It does not state a value.",
        ],
    }


def changes_text(document: Mapping[str, Any]) -> str:
    """A changes document as text: sorted members, one trailing newline."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"
