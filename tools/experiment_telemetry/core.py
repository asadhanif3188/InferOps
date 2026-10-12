"""The telemetry readings of one experiment run, as two streams.

A collector script asks the telemetry collector of the release a registered
set of instant queries, a bounded number of times, and writes what each read
returned into one directory. This module reads that directory. It contacts no cluster and
no collector. It returns two streams, and each stream holds one reading for each
query of each sample:

- ``telemetry``: the scrape targets of each tier, the instant of the oldest
  scrape of each tier, the request counter by outcome, and the error counter by
  error code;
- ``resources``: what the API process publishes about its own processor time
  and its own memory.

**The queries are registered, and the set is closed.** :data:`QUERIES` is every
query that a collection can hold. Each query aggregates, and it registers each
label that a series of its answer can state. A collection that was made with
another set is refused, and so is a stored stream that states a label that its
query does not register.

**No series is not zero.** A read has one of five states, and only ``answered``
gives a result. An answered read has one of two results: ``series`` or
``no-series``. A reading with the result ``no-series`` states no value. No
function here replaces it with zero.

**One time basis.** The collector script states two instants for each read, on
the wall clock of the collecting host, in UTC, to one millisecond. They are the
time basis of both streams, and they have the form that the timeline streams
use. An evaluation instant and an instant of a scrape are on the clock of the
telemetry collector. :data:`LIMITATIONS` says what follows from that.

**A stream is not caller truth.** It states what the telemetry collector
stored. It reads no caller record, and it holds no request identifier.
:data:`DOES_NOT_ESTABLISH` is part of every stream.

See docs/environment/experiment-telemetry.md and
tests/domain/test_experiment_telemetry.py.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote

from tools.experiment_timeline import (
    ABSENT,
    ANSWERED,
    FIELD_STATES,
    MALFORMED,
    MISSING,
    NOT_TAKEN,
    READ_STATES,
    REFUSED_EXIT,
    REPORTED,
    UNANSWERED,
    UNREADABLE,
    collector_instant,
    format_instant,
)

__all__ = [
    "ABSENT",
    "ANSWERED",
    "COLLECTION_SCHEMA",
    "COLLECTOR_STATES",
    "COLLECTOR_SUFFIX",
    "DOES_NOT_ESTABLISH",
    "END_FILE",
    "FIELD_STATES",
    "HEADER_FILE",
    "KINDS",
    "LIMITATIONS",
    "MALFORMED",
    "MAX_INTERVAL_SECONDS",
    "MAX_REQUEST_TIMEOUT_SECONDS",
    "MAX_SAMPLES",
    "MAX_SERIES",
    "META_SUFFIX",
    "MIN_INTERVAL_SECONDS",
    "MISSING",
    "NOT_TAKEN",
    "NO_SERIES",
    "OMITTED",
    "QUERIES",
    "QUERY_SET",
    "QUERY_SUFFIX",
    "READ_STATES",
    "REFUSED_EXIT",
    "REPORTED",
    "RESOURCES",
    "RESULTS",
    "RULES",
    "SAMPLE_STEM",
    "SERIES",
    "STREAMS",
    "STREAM_FILES",
    "STREAM_SCHEMA",
    "TELEMETRY",
    "UNANSWERED",
    "UNREADABLE",
    "Collection",
    "CollectionRefused",
    "Query",
    "Read",
    "Sample",
    "Stream",
    "StreamRefused",
    "build_streams",
    "queries_of",
    "query_set_sha256",
    "read_collection",
    "read_stream",
    "request_path",
    "requests_text",
    "stream_text",
]

#: The schema name of each line of a stream.
STREAM_SCHEMA: Final = "inferops.io/experiment-telemetry/v1alpha1"

#: The schema name that the collector script writes into the header of a collection.
COLLECTION_SCHEMA: Final = "inferops.io/experiment-telemetry-collection/v1alpha1"

TELEMETRY: Final = "telemetry"
RESOURCES: Final = "resources"

#: The two streams. Each name is a registered raw role of the evidence layout.
STREAMS: Final = (TELEMETRY, RESOURCES)

#: The file of each stream.
STREAM_FILES: Final[Mapping[str, str]] = {name: f"{name}.jsonl" for name in STREAMS}

#: The files of a collection. The collector script restates each name.
HEADER_FILE: Final = "collection.json"
END_FILE: Final = "collection.end"
SAMPLE_STEM: Final = "sample-{index:04d}"
META_SUFFIX: Final = ".meta"
COLLECTOR_SUFFIX: Final = ".collector.json"
QUERY_SUFFIX: Final = ".query.{name}.json"

#: The bounds of one collection. The collector script restates the first three.
#: The fourth is the largest request timeout that a header may state, and the
#: script states one value inside it.
MAX_SAMPLES: Final = 720
MIN_INTERVAL_SECONDS: Final = 5
MAX_INTERVAL_SECONDS: Final = 120
MAX_REQUEST_TIMEOUT_SECONDS: Final = 60

#: The largest number of series that one reading states.
MAX_SERIES: Final = 32

SERIES: Final = "series"
NO_SERIES: Final = "no-series"

#: The results of an answered read. ``no-series`` is an answer that held no
#: sample. It is not a value, and it is not zero.
RESULTS: Final = (SERIES, NO_SERIES)

COLLECTOR_PRESENT: Final = "present"
COLLECTOR_ABSENT: Final = "absent"
COLLECTOR_NOT_READ: Final = "not-read"

#: What the read of the collector's Service showed for one sample.
COLLECTOR_STATES: Final = (COLLECTOR_PRESENT, COLLECTOR_ABSENT, COLLECTOR_NOT_READ)

KIND_COUNT: Final = "count"
KIND_NUMBER: Final = "number"
KIND_INSTANT: Final = "instant"

#: The kinds of value. ``count`` is a whole number that is not negative.
#: ``number`` is a finite number. ``instant`` is an instant that the collector
#: states in seconds, and a reading states it in UTC to one millisecond.
KINDS: Final = (KIND_COUNT, KIND_NUMBER, KIND_INSTANT)


@dataclass(frozen=True)
class Query:
    """One registered instant query.

    ``labels`` is each label that a series of the answer can state. The
    expression aggregates over every other label.
    """

    name: str
    stream: str
    expression: str
    labels: tuple[str, ...]
    kind: str
    states: str

    def as_document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "expression": self.expression,
            "labels": list(self.labels),
            "kind": self.kind,
            "states": self.states,
        }


#: The name of the registered set. A change to a query changes the digest of the
#: set, and it takes another name: a test pins the digest of this name.
QUERY_SET: Final = "experiment-run-queries-r1"

#: Every query that a collection can hold, in the order of the reads.
QUERIES: Final[tuple[Query, ...]] = (
    Query(
        "api-scrape-targets",
        TELEMETRY,
        'count(up{k8s_component="platform-api"})',
        (),
        KIND_COUNT,
        "The number of scrape targets of the API tier that the collector holds.",
    ),
    Query(
        "api-scrape-targets-up",
        TELEMETRY,
        'sum(up{k8s_component="platform-api"})',
        (),
        KIND_COUNT,
        "The number of those targets whose last scrape succeeded.",
    ),
    Query(
        "api-oldest-scrape",
        TELEMETRY,
        'min(timestamp(up{k8s_component="platform-api"}))',
        (),
        KIND_INSTANT,
        "The instant of the oldest last scrape among the targets of the API tier.",
    ),
    Query(
        "runtime-scrape-targets",
        TELEMETRY,
        'count(up{k8s_component="serving-runtime"})',
        (),
        KIND_COUNT,
        "The number of scrape targets of the serving runtime tier that the "
        "collector holds.",
    ),
    Query(
        "runtime-scrape-targets-up",
        TELEMETRY,
        'sum(up{k8s_component="serving-runtime"})',
        (),
        KIND_COUNT,
        "The number of those targets whose last scrape succeeded.",
    ),
    Query(
        "runtime-oldest-scrape",
        TELEMETRY,
        'min(timestamp(up{k8s_component="serving-runtime"}))',
        (),
        KIND_INSTANT,
        "The instant of the oldest last scrape among the targets of the serving "
        "runtime tier.",
    ),
    Query(
        "api-requests-by-outcome",
        TELEMETRY,
        "sum by (inferops_outcome) (inferops_inference_requests_total)",
        ("inferops_outcome",),
        KIND_NUMBER,
        "The request counter of the API, summed over its processes, for each outcome.",
    ),
    Query(
        "api-errors-by-code",
        TELEMETRY,
        "sum by (inferops_error_code) (inferops_inference_errors_total)",
        ("inferops_error_code",),
        KIND_NUMBER,
        "The error counter of the API, summed over its processes, for each "
        "canonical error code.",
    ),
    Query(
        "api-processes-reporting-cpu",
        RESOURCES,
        "count(inferops_process_cpu_seconds_total)",
        (),
        KIND_COUNT,
        "The number of API processes whose processor time the collector holds.",
    ),
    Query(
        "api-cpu-seconds",
        RESOURCES,
        "sum(inferops_process_cpu_seconds_total)",
        (),
        KIND_NUMBER,
        "The processor time of the API processes, in seconds, summed.",
    ),
    Query(
        "api-resident-memory-bytes",
        RESOURCES,
        "sum(inferops_process_resident_memory_bytes)",
        (),
        KIND_NUMBER,
        "The resident memory of the API processes, in bytes, summed.",
    ),
)

#: What a stream leaves out, on purpose.
OMITTED: Final[tuple[str, ...]] = (
    "Each label of a series that the query does not register. Each registered "
    "query aggregates over every other label.",
    "The name of a pod, of a scrape target, and of a scrape job, and the "
    "address of a target.",
    "Each request identifier, correlation identifier, trace identifier, and "
    "tenant identifier. The telemetry catalog bars each from a metric label, "
    "and no registered query groups by one.",
    "The text of an error that the collector or the API server returned.",
    "The name of the kubeconfig context. A context name can hold an account identifier.",
    "The Service object of the collector. The tool reads whether it is present "
    "and nothing else.",
)

#: The limits of a stream.
LIMITATIONS: Final[tuple[str, ...]] = (
    "The instants read.startedAt and read.finishedAt are the wall clock of the "
    "host that ran the collector script, in UTC, to one millisecond. A wall "
    "clock can be set while a collection runs. The end line names each reading "
    "whose start is before the finish of the reading before it.",
    "A value is the answer of the telemetry collector to one instant query. It "
    "is not a reading of the process that published the metric. The collector "
    "answers from the last sample that it stored. That sample can be older "
    "than the read by the scrape interval. When the collector stored no newer "
    "sample and no mark that the series ended, the sample can be older by up "
    "to the lookback of the collector, which the chart leaves at the default "
    "of the collector. No run observed either.",
    "The instant evaluatedAt and the value of a query of the kind instant are "
    "on the clock of the telemetry collector, to one millisecond. They are not "
    "on the clock of the collecting host.",
    "The difference between the two clocks is not measured. The end line states "
    "two bounds that the evaluation instants give. The bounds hold when the "
    "collector took each evaluation instant while its read was open, and when "
    "the difference did not change during the collection. Each instant is cut "
    "to one millisecond, so each bound is to about one millisecond. No run "
    "observed when a collector takes the instant.",
    "A reading with the result no-series states that the collector held no "
    "sample for the query at the evaluation instant. It does not state why. A "
    "metric that no process publishes, a target that the collector did not "
    "discover, and a sample that went stale each give no series.",
    "A value of a counter is the sum over the processes that the collector "
    "scraped. The sum falls when a process starts again and when a target "
    "leaves. A stream computes no rate and corrects no reset.",
    "The queries of one sample are separate reads at separate instants. They "
    "are not one atomic reading.",
    "A state that began and ended between two scrapes is in no sample of the "
    "collector. A state that began and ended between two readings is in no "
    "reading.",
    "Each kubectl call of a read states a request timeout, and kubectl applies "
    "it to each request that the call makes. The call of the Service read can "
    "make more than one request. No run observed how long a read takes. A "
    "query that the collector refused and a query that the API server could "
    "not pass to the collector are both unanswered.",
    "A read reaches the collector through the Service proxy of the API server. "
    "The network policy of the chart selects the pod of the collector and "
    "admits no connection to its port. Whether a cluster applies that policy to "
    "a connection from the API server is a property of its network plugin. No "
    "run observed it.",
    "The series of the collector are in a volume that goes when its pod goes. A "
    "stream holds only what was read while the collection ran.",
    "The resources stream reads what the API process publishes about itself. No "
    "query reads the resource use of the serving runtime, of a container, or "
    "of a node, because the release has no source for them.",
    "The chart renders the scrape job of the serving runtime only under the "
    "profile real. Under another profile the three queries of the serving "
    "runtime tier have no series.",
    "A value of a registered label is free within the form of a label value. "
    "The form is not a check for a secret, and it does not show that the value "
    "is a registered outcome or a canonical error code.",
    "A value of the kind number is stored as a binary number of 64 bits. A "
    "counter above 9007199254740992 loses its last digits.",
    f"A reading whose answer holds more than {MAX_SERIES} series states no series.",
    "The collection names the commit of the working tree that ran the collector "
    "script, and the SHA-256 of the script and of its library. It does not "
    "state whether the tree had a change that was not committed.",
)

#: What no stream establishes.
DOES_NOT_ESTABLISH: Final[tuple[str, ...]] = (
    "That a caller obtained a completion at any instant. A scrape that "
    "succeeded, a request counter, and an error counter are what the telemetry "
    "collector stored. None of them is a request that a caller sent and had "
    "answered.",
    "That a reading with the result no-series is a value of zero. No series is "
    "not zero, not healthy, and not failed.",
    "That the telemetry collector existed or answered at a sample whose read "
    "state is not answered. A read that did not answer is not a result with no "
    "series.",
    "That a metric means what its name says. A scrape that succeeded does not "
    "show that a counter agrees with what callers observed.",
    "The instant of a change. A change is bounded by two scrapes of the "
    "collector and by two readings.",
    "The resource use of the serving runtime, of a container, or of a node.",
    "A rate, a ratio, a detection lag, or any other metric of an experiment. A "
    "stream is evidence that an analysis reads. This module computes no metric "
    "and gives no verdict.",
)

RULE_UNREADABLE: Final = "telemetry-stream-unreadable"
RULE_HEADER: Final = "telemetry-header-unsupported"
RULE_MEMBERS: Final = "telemetry-members-unsupported"
RULE_QUERIES: Final = "telemetry-query-unregistered"
RULE_SEQUENCE: Final = "telemetry-reading-out-of-sequence"
RULE_READ: Final = "telemetry-read-state-unsupported"
RULE_INSTANT: Final = "telemetry-instant-invalid"
RULE_READING: Final = "telemetry-reading-unsupported"
RULE_LABEL: Final = "telemetry-label-unregistered"
RULE_END: Final = "telemetry-end-missing"
RULE_COUNTS: Final = "telemetry-counts-differ"

#: Each rule that :func:`read_stream` holds a stream to, with its statement.
RULES: Final[Mapping[str, str]] = {
    RULE_UNREADABLE: (
        "A stream is UTF-8 text, and each line ends with a line feed. Each line "
        "is one JSON object with no member stated twice."
    ),
    RULE_HEADER: (
        "The first line is the header. It states the stream schema, one of the "
        "two stream names, an experiment identifier, and a run identifier, each "
        "in its form. Its collection has exactly the members of a collection, "
        "each in its form. Its clocks, its bounds, what it leaves out, its "
        "limitations, and what it does not establish are the texts of this tool."
    ),
    RULE_MEMBERS: (
        "Each line has exactly the members of its record, and each read has "
        "exactly its three members."
    ),
    RULE_QUERIES: (
        "The header states the registered queries of its stream, as this tool "
        "registers them, and it names the registered set."
    ),
    RULE_SEQUENCE: (
        "Each line between the header and the end line is a reading. The "
        "readings are numbered from 1 with no gap, and each sample holds the "
        "queries of the stream in the registered order."
    ),
    RULE_READ: (
        "Each reading states one of the registered read states and one of the "
        "registered states of the collector."
    ),
    RULE_INSTANT: (
        "Each instant of a read is absent or is UTC to one millisecond in the "
        "one registered form. A read states both instants or neither, and it "
        "does not finish before it starts."
    ),
    RULE_READING: (
        "Each fault of a reading is a text of this tool. A reading states a "
        "result, a series, and an evaluation instant only when its read "
        "answered. A reading with the result series states at least one series "
        f"and at most {MAX_SERIES}, and a reading with the result no-series states "
        "none. Each series has its labels and one value. Each value and each "
        "evaluation instant is a field with the form of its kind. A read that "
        "was not taken states no instant, each other read except an unreadable "
        "one states its instants, and an absent read states an absent "
        "collector."
    ),
    RULE_LABEL: (
        "Each series states only labels that its query registers, each value of "
        "a label has the form of a label value, and no two series of one "
        "reading state the same labels."
    ),
    RULE_END: "The last line is the end line, and no line follows it.",
    RULE_COUNTS: (
        "The end line states the number of readings, the number in each read "
        "state, the number with each result, the two bounds of the clock "
        "difference, and each reading that starts before the one before it "
        "finished, as this tool computes them from the readings."
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
        "collectorService",
        "collectorPort",
        "querySet",
        "querySetSha256",
        "executingCommit",
        "procedureSha256",
        "librarySha256",
        "requestedSamples",
        "intervalSeconds",
        "requestTimeoutSeconds",
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
        "queries",
        "clock",
        "bounds",
        "omitted",
        "limitations",
        "doesNotEstablish",
    }
)
_READING_MEMBERS: Final = frozenset(
    {
        "record",
        "index",
        "sample",
        "query",
        "read",
        "collector",
        "result",
        "evaluatedAt",
        "series",
        "faults",
    }
)
_READ_MEMBERS: Final = frozenset({"state", "startedAt", "finishedAt"})
_SERIES_MEMBERS: Final = frozenset({"labels", "value"})
_END_MEMBERS: Final = frozenset(
    {
        "record",
        "readings",
        "byReadState",
        "byResult",
        "evaluationOffset",
        "instantsOutOfOrder",
    }
)

_IDENTIFIER: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,62}")
_LABEL: Final = re.compile(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?")
_COMMIT_FORM: Final = re.compile(r"[0-9a-f]{40}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_VERSION: Final = re.compile(r"v[0-9][0-9A-Za-z.+-]{0,62}")
_DIGITS: Final = re.compile(r"[0-9]{1,9}")
_SAMPLE_META: Final = re.compile(r"sample-([0-9]{4})\.meta")
#: A sample value, as the collector writes a finite number.
_NUMBER: Final = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
)
#: A value of a label. It is the form of an identifier, which holds each
#: registered outcome and each canonical error code.
_LABEL_VALUE: Final = _IDENTIFIER

_MAX_COUNT: Final = 999_999_999
_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)
_LAST_MILLISECOND: Final = 253_402_300_799_999
#: The most digits of a number that is read as an instant.
_MAX_DIGITS: Final = 40
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
# The registered queries
# --------------------------------------------------------------------------


def queries_of(stream: str) -> tuple[Query, ...]:
    """The registered queries of one stream, in the order of the reads."""
    return tuple(query for query in QUERIES if query.stream == stream)


def query_set_sha256() -> str:
    """The SHA-256 of the registered set: each name, stream, expression, label, and kind.

    A collection states this digest, and a stream is built only from a
    collection that states the digest of this module.
    """
    canonical = json.dumps(
        {
            "querySet": QUERY_SET,
            "queries": [
                {
                    "name": query.name,
                    "stream": query.stream,
                    "expression": query.expression,
                    "labels": list(query.labels),
                    "kind": query.kind,
                }
                for query in QUERIES
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def request_path(query: Query) -> str:
    """The path and the query string of one instant query, below the proxy path.

    Each character of the expression that is not a letter, a digit, ``-``,
    ``.``, ``_``, or ``~`` is percent-encoded, so the text holds no character
    that a shell or a URL reads.
    """
    return f"api/v1/query?query={quote(query.expression, safe='')}"


def requests_text() -> str:
    """What the collector script reads: the set, and one line for each query."""
    lines = [f"query-set {QUERY_SET} {query_set_sha256()}"]
    lines.extend(f"query {query.name} {request_path(query)}" for query in QUERIES)
    return "".join(f"{line}\n" for line in lines)


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
    """One sample: what the read of the Service showed, and one read for each query."""

    index: int
    collector: str
    queries: Mapping[str, Read]


@dataclass(frozen=True)
class Collection:
    """What one run of the collector script wrote: its header and its samples."""

    header: Mapping[str, Any]
    completed: dict[str, Any]
    samples: tuple[Sample, ...]

    @property
    def complete(self) -> bool:
        """Every sample that was asked for was taken, and the script said so."""
        return (
            self.completed.get("state") == REPORTED
            and self.completed.get("value") == self.header["requestedSamples"]
            and all(
                read.state != NOT_TAKEN
                for sample in self.samples
                for read in sample.queries.values()
            )
        )


def _pairs(path: Path) -> dict[str, str]:
    """The ``key=value`` lines of one file that the collector script wrote."""
    found: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return found
    for line in lines:
        key, separator, value = line.strip().partition("=")
        if separator and key:
            found[key] = value
    return found


def _load(path: Path) -> tuple[bool, Any]:
    """Whether a file holds one JSON value, and that value.

    A number with a fraction is read as a decimal, so an instant that the
    collector states to one millisecond keeps each digit. A file that states a
    member twice, and a file with a number that the decimal reader refuses, do
    not hold one JSON value.
    """
    try:
        text = path.read_bytes().decode("utf-8")
        return True, json.loads(text, parse_float=Decimal, object_pairs_hook=_no_repeat)
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        RecursionError,
        ArithmeticError,
    ):
        return False, None


def _is_count(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= _MAX_COUNT
    )


def _header(directory: Path) -> dict[str, Any]:
    """The header that the collector script wrote, held to its members and their form."""
    path = directory / HEADER_FILE
    if not path.is_file():
        raise CollectionRefused(f"the directory holds no {HEADER_FILE}")
    readable, header = _load(path)
    if not readable or not isinstance(header, dict):
        raise CollectionRefused(f"{HEADER_FILE} is not one JSON object")
    if set(header) != _HEADER_MEMBERS:
        raise CollectionRefused(
            f"{HEADER_FILE} does not hold the members of a collection, which are "
            f"{sorted(_HEADER_MEMBERS)}"
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
        "collectorService": _LABEL,
        "collectorPort": _LABEL,
        "executingCommit": _COMMIT_FORM,
        "procedureSha256": _SHA256,
        "librarySha256": _SHA256,
    }
    for name, form in forms.items():
        value = header[name]
        if not isinstance(value, str) or form.fullmatch(value) is None:
            raise CollectionRefused(f"{HEADER_FILE} states no usable {name}")
    if header["querySet"] != QUERY_SET or header["querySetSha256"] != (
        query_set_sha256()
    ):
        raise CollectionRefused(
            f"{HEADER_FILE} does not state the query set {QUERY_SET} with the "
            "digest that this tool gives. The collection was made with another "
            "set of queries, and this tool does not read it"
        )
    bounds = {
        "requestedSamples": (1, MAX_SAMPLES),
        "intervalSeconds": (MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS),
        "requestTimeoutSeconds": (1, MAX_REQUEST_TIMEOUT_SECONDS),
    }
    for name, (minimum, maximum) in bounds.items():
        value = header[name]
        if not _is_count(value) or not minimum <= value <= maximum:
            raise CollectionRefused(
                f"{HEADER_FILE} does not state {name} as a whole number from "
                f"{minimum} to {maximum}"
            )
    # A server version that the script could not read is an empty text. It is
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


def _collector_state(
    meta: Mapping[str, str], path: Path, service: str, namespace: str
) -> str:
    """What the read of the collector's Service showed.

    ``absent`` needs an answer that holds no object. A read that did not answer,
    and an answer that is another object, are ``not-read``.
    """
    if meta.get("collectorRead") != ANSWERED or not path.is_file():
        return COLLECTOR_NOT_READ
    try:
        if not path.read_bytes().strip():
            return COLLECTOR_ABSENT
    except OSError:
        return COLLECTOR_NOT_READ
    readable, document = _load(path)
    if not readable or not isinstance(document, dict):
        return COLLECTOR_NOT_READ
    metadata = document.get("metadata")
    if (
        document.get("kind") == "Service"
        and isinstance(metadata, dict)
        and metadata.get("name") == service
        and metadata.get("namespace") == namespace
    ):
        return COLLECTOR_PRESENT
    return COLLECTOR_NOT_READ


def _query_read(
    meta: Mapping[str, str], query: Query, path: Path, collector: str
) -> Read:
    """One read of one query, from the status file and the file of the answer."""
    key = f"query.{query.name}"
    started = collector_instant(meta.get(f"{key}.startedAt"))
    finished = collector_instant(meta.get(f"{key}.finishedAt"))
    stated = meta.get(f"{key}.read")
    if started is None or finished is None or finished < started:
        # A reading with no usable instants has no place on a timeline.
        return Read(
            UNREADABLE, detail="the sample states no usable instants for this read"
        )
    if stated == UNANSWERED:
        # The Service was read and is not there, so no collector could answer.
        state = ABSENT if collector == COLLECTOR_ABSENT else UNANSWERED
        return Read(state, started, finished)
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
    readable, document = _load(path)
    if not readable or not isinstance(document, dict):
        return Read(
            UNREADABLE, started, finished, detail="the answer is not one JSON object"
        )
    return Read(ANSWERED, started, finished, document)


def _sample(directory: Path, index: int, header: Mapping[str, Any]) -> Sample:
    stem = SAMPLE_STEM.format(index=index)
    meta_path = directory / f"{stem}{META_SUFFIX}"
    if not meta_path.is_file():
        return Sample(
            index,
            COLLECTOR_NOT_READ,
            {query.name: Read(NOT_TAKEN) for query in QUERIES},
        )
    meta = _pairs(meta_path)
    collector = _collector_state(
        meta,
        directory / f"{stem}{COLLECTOR_SUFFIX}",
        header["collectorService"],
        header["namespace"],
    )
    return Sample(
        index,
        collector,
        {
            query.name: _query_read(
                meta,
                query,
                directory / f"{stem}{QUERY_SUFFIX.format(name=query.name)}",
                collector,
            )
            for query in QUERIES
        },
    )


def read_collection(directory: Path) -> Collection:
    """What one run of the collector script wrote: its header and each sample.

    A sample that the collection was asked for and did not write is returned
    with the read state ``not-taken`` for each query.

    Raises:
        CollectionRefused: the directory holds no usable header, it states
            another query set, or it holds a sample that the header did not ask
            for.
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
    samples = tuple(
        _sample(directory, index, header) for index in range(1, requested + 1)
    )
    return Collection(header, completed, samples)


# --------------------------------------------------------------------------
# One answer, as series
# --------------------------------------------------------------------------


def _decimal(value: object) -> Decimal | None:
    """A finite number that a sample states, or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | Decimal):
        number = Decimal(value)
    elif isinstance(value, str) and value.isascii() and _NUMBER.fullmatch(value):
        try:
            number = Decimal(value)
        except InvalidOperation:
            return None
    else:
        return None
    return number if number.is_finite() else None


def _instant(seconds: Decimal | None) -> dict[str, Any]:
    """An instant that the collector states in seconds, in UTC to one millisecond.

    A finer fraction is cut. It is not rounded.
    """
    if (
        seconds is None
        or seconds < 0
        or seconds.adjusted() > 12
        or len(seconds.as_tuple().digits) > _MAX_DIGITS
    ):
        return {"state": MALFORMED}
    # The product is exact: the context holds more digits than the number has.
    with localcontext() as context:
        context.prec = _MAX_DIGITS + 8
        milliseconds = int((seconds * 1000).to_integral_value(rounding=ROUND_FLOOR))
    if not 0 <= milliseconds <= _LAST_MILLISECOND:
        return {"state": MALFORMED}
    return {
        "state": REPORTED,
        "value": format_instant(_EPOCH + timedelta(milliseconds=milliseconds)),
        "resolution": "millisecond",
    }


def _value(kind: str, stated: object) -> dict[str, Any]:
    """The value of one series, as a field of the kind of its query."""
    # A sample value is text in the answer of the collector. A JSON number in
    # its place is another form, and it is not read as a value.
    number = _decimal(stated) if isinstance(stated, str) else None
    if number is None:
        return {"state": MALFORMED}
    if kind == KIND_INSTANT:
        return _instant(number)
    if kind == KIND_COUNT:
        if number != number.to_integral_value() or not 0 <= number <= _MAX_COUNT:
            return {"state": MALFORMED}
        return {"state": REPORTED, "value": int(number)}
    as_float = float(number)
    # A number that a binary number of 64 bits cannot hold is not a value: an
    # overflow is not an infinity, and an underflow is not zero.
    if not math.isfinite(as_float) or (as_float == 0.0 and number != 0):
        return {"state": MALFORMED}
    return {"state": REPORTED, "value": as_float}


def _bounded(faults: Sequence[str]) -> list[str]:
    """At most a fixed number of faults, and the number of the others."""
    kept = list(faults[:_FAULT_LIMIT])
    if len(faults) > _FAULT_LIMIT:
        kept.append(f"{len(faults) - _FAULT_LIMIT} more fault(s) are not listed")
    return kept


@dataclass(frozen=True)
class _Reduced:
    state: str
    result: str | None = None
    evaluated_at: dict[str, Any] | None = None
    series: list[dict[str, Any]] | None = None
    faults: tuple[str, ...] = ()


def _reduce(query: Query, document: Mapping[str, Any]) -> _Reduced:
    """One answer of the collector, reduced to the series that the query registers.

    Each fault is a text of this module. It quotes no text of the answer: a
    label name, a label value, and an error text of the collector are not
    copied.
    """
    data = document.get("data")
    if document.get("status") != "success" or not isinstance(data, dict):
        return _Reduced(
            UNREADABLE, faults=("the answer does not state success and a result",)
        )
    result = data.get("result")
    if data.get("resultType") != "vector" or not isinstance(result, list):
        return _Reduced(UNREADABLE, faults=("the answer is not an instant vector",))
    if len(result) > MAX_SERIES:
        return _Reduced(
            ANSWERED,
            faults=(
                f"the answer holds more than {MAX_SERIES} series, and the reading "
                "states none",
            ),
        )
    series: list[tuple[tuple[tuple[str, str], ...], dict[str, Any]]] = []
    evaluated: set[Decimal | None] = set()
    faults: list[str] = []
    value_faults = 0
    for item in result:
        metric = item.get("metric") if isinstance(item, dict) else None
        sample = item.get("value") if isinstance(item, dict) else None
        if (
            not isinstance(metric, dict)
            or not isinstance(sample, list)
            or len(sample) != 2
        ):
            faults.append("a series does not hold its labels and one sample")
            continue
        if not set(metric) <= set(query.labels):
            faults.append("a series states a label that the query does not register")
            continue
        if not all(
            isinstance(value, str) and _LABEL_VALUE.fullmatch(value) is not None
            for value in metric.values()
        ):
            faults.append("a value of a label does not have the form of a label value")
            continue
        evaluated.add(_decimal(sample[0]) if not isinstance(sample[0], str) else None)
        value = _value(query.kind, sample[1])
        if value["state"] != REPORTED:
            value_faults += 1
        series.append((tuple(sorted(metric.items())), value))
    keys = [key for key, _ in series]
    if len(set(keys)) != len(keys):
        faults.append("two series state the same labels")
    if faults:
        # A series that cannot be named without a guess leaves the reading with
        # no series. The other series are not kept: a part of an answer is not
        # the answer.
        return _Reduced(ANSWERED, faults=tuple(dict.fromkeys(faults)))
    if not series:
        return _Reduced(ANSWERED, NO_SERIES, {"state": MISSING}, [])
    notes = []
    if value_faults:
        notes.append(
            f"{value_faults} value(s) do not have the form of the kind {query.kind}"
        )
    if len(evaluated) != 1 or None in evaluated:
        evaluated_at = {"state": MALFORMED}
        notes.append("the series do not state one usable evaluation instant")
    else:
        evaluated_at = _instant(next(iter(evaluated)))
        if evaluated_at["state"] != REPORTED:
            notes.append("the series do not state one usable evaluation instant")
    return _Reduced(
        ANSWERED,
        SERIES,
        evaluated_at,
        [{"labels": dict(key), "value": value} for key, value in sorted(series)],
        tuple(notes),
    )


# --------------------------------------------------------------------------
# The streams
# --------------------------------------------------------------------------


def _reading(sample: Sample, query: Query) -> dict[str, Any]:
    read = sample.queries[query.name]
    reading: dict[str, Any] = {
        "record": "reading",
        "sample": sample.index,
        "query": query.name,
        "read": read.as_document(),
        "collector": sample.collector,
        "result": None,
        "evaluatedAt": None,
        "series": None,
        "faults": [] if read.detail is None else [read.detail],
    }
    if read.state != ANSWERED:
        return reading
    reduced = _reduce(query, read.document)
    reading["read"] = {**read.as_document(), "state": reduced.state}
    reading["result"] = reduced.result
    reading["evaluatedAt"] = reduced.evaluated_at
    reading["series"] = reduced.series
    reading["faults"] = _bounded(reduced.faults)
    return reading


def _milliseconds(later: datetime, earlier: datetime) -> int:
    return (later - earlier) // timedelta(milliseconds=1)


def _end(readings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The end line of one stream: its counts and its two clock observations."""
    states = [reading["read"]["state"] for reading in readings]
    results = [reading["result"] for reading in readings]
    not_below: list[int] = []
    not_above: list[int] = []
    out_of_order: list[int] = []
    previous: datetime | None = None
    for reading in readings:
        started = collector_instant(reading["read"]["startedAt"])
        finished = collector_instant(reading["read"]["finishedAt"])
        if started is None or finished is None:
            continue
        if previous is not None and started < previous:
            out_of_order.append(reading["index"])
        previous = finished
        evaluated = reading["evaluatedAt"]
        instant = (
            collector_instant(evaluated.get("value"))
            if isinstance(evaluated, dict) and evaluated.get("state") == REPORTED
            else None
        )
        if instant is not None:
            # The collector took the instant while the read was open. So its
            # clock minus the host clock is between these two differences.
            not_below.append(_milliseconds(instant, finished))
            not_above.append(_milliseconds(instant, started))
    return {
        "record": "end",
        "readings": len(readings),
        "byReadState": {state: states.count(state) for state in READ_STATES},
        "byResult": {result: results.count(result) for result in RESULTS},
        "evaluationOffset": {
            "readings": len(not_below),
            "notBelowMilliseconds": max(not_below) if not_below else None,
            "notAboveMilliseconds": min(not_above) if not_above else None,
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
        "queries": [query.as_document() for query in queries_of(stream)],
        **_fixed_header(),
    }


def _fixed_header() -> dict[str, Any]:
    """The members of a header that are texts and bounds of this tool."""
    return {
        "clock": {
            "read": {
                "members": ["read.startedAt", "read.finishedAt"],
                "source": "the wall clock of the host that ran the collector script",
                "zone": "UTC",
                "resolution": "millisecond",
            },
            "collector": {
                "members": "evaluatedAt, and each value of a query of the kind instant",
                "source": "the clock of the telemetry collector",
                "zone": "UTC, after normalisation",
                "resolution": "millisecond",
            },
            "skew": "not-measured",
        },
        "bounds": {
            "maxSamples": MAX_SAMPLES,
            "minIntervalSeconds": MIN_INTERVAL_SECONDS,
            "maxIntervalSeconds": MAX_INTERVAL_SECONDS,
            "maxSeries": MAX_SERIES,
        },
        "omitted": list(OMITTED),
        "limitations": list(LIMITATIONS),
        "doesNotEstablish": list(DOES_NOT_ESTABLISH),
    }


def build_streams(directory: Path) -> dict[str, list[dict[str, Any]]]:
    """The two streams of one collection, each as its lines in order.

    Raises:
        CollectionRefused: the directory is not a collection of this query set.
    """
    collection = read_collection(directory)
    streams: dict[str, list[dict[str, Any]]] = {}
    for name in STREAMS:
        readings = [
            _reading(sample, query)
            for sample in collection.samples
            for query in queries_of(name)
        ]
        for index, reading in enumerate(readings, start=1):
            reading["index"] = index
        streams[name] = [_stream_header(name, collection), *readings, _end(readings)]
    return streams


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
        results = self.end["byResult"]
        return (
            f"{self.name}: {len(self.readings)} reading(s): {stated or 'none'}; "
            f"{results[SERIES]} with series, {results[NO_SERIES]} with no series"
        )


def _no_repeat(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for key, value in pairs:
        if key in found:
            raise ValueError("a member is stated twice")
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


def _is_field(value: object, kind: str) -> bool:
    """Whether a value is a field of one kind: a state, and a value in its form.

    Only a reported field carries a value. A count is a whole number, a number
    is a finite number with a fraction part in its text, and an instant is UTC
    to one millisecond with that resolution.
    """
    if not isinstance(value, dict):
        return False
    state = value.get("state")
    if not isinstance(state, str) or state not in FIELD_STATES:
        return False
    if state != REPORTED:
        return set(value) == {"state"}
    stated = value.get("value")
    if kind == KIND_INSTANT:
        return (
            set(value) == {"state", "value", "resolution"}
            and value["resolution"] == "millisecond"
            and collector_instant(stated) is not None
        )
    if set(value) != {"state", "value"}:
        return False
    if kind == KIND_COUNT:
        return _is_count(stated)
    return type(stated) is float and math.isfinite(stated)


#: Each fault that a reading can state, as this module writes it.
_FAULTS: Final = frozenset(
    {
        "the sample states no usable instants for this read",
        "the sample does not state whether this read answered",
        "the sample states an answer, and the directory holds no file of it",
        "the answer is not one JSON object",
        "the answer does not state success and a result",
        "the answer is not an instant vector",
        f"the answer holds more than {MAX_SERIES} series, and the reading states none",
        "a series does not hold its labels and one sample",
        "a series states a label that the query does not register",
        "a value of a label does not have the form of a label value",
        "two series state the same labels",
        "the series do not state one usable evaluation instant",
    }
)
_COUNTED_FAULT: Final = re.compile(
    r"[1-9][0-9]{0,8} (?:value\(s\) do not have the form of the kind "
    r"(?:count|number|instant)|more fault\(s\) are not listed)"
)


def _is_fault(text: object) -> bool:
    return isinstance(text, str) and (
        text in _FAULTS
        or (text.isascii() and _COUNTED_FAULT.fullmatch(text) is not None)
    )


def _collection_fault(collection: object) -> str | None:
    """Why the collection of a header does not have its form, or None."""
    members = (_HEADER_MEMBERS - {"schema", "experimentId", "runId"}) | {
        "completedSamples",
        "complete",
    }
    if not isinstance(collection, dict) or set(collection) != members:
        return "the collection does not have its members"
    forms = {
        "provider": _LABEL,
        "namespace": _LABEL,
        "release": _LABEL,
        "collectorService": _LABEL,
        "collectorPort": _LABEL,
        "executingCommit": _COMMIT_FORM,
        "procedureSha256": _SHA256,
        "librarySha256": _SHA256,
    }
    for name, form in forms.items():
        value = collection[name]
        if not isinstance(value, str) or form.fullmatch(value) is None:
            return f"the collection states no usable {name}"
    bounds = {
        "requestedSamples": (1, MAX_SAMPLES),
        "intervalSeconds": (MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS),
        "requestTimeoutSeconds": (1, MAX_REQUEST_TIMEOUT_SECONDS),
    }
    for name, (minimum, maximum) in bounds.items():
        value = collection[name]
        if not _is_count(value) or not minimum <= value <= maximum:
            return f"the collection states no usable {name}"
    version = collection["serverVersion"]
    if (
        not isinstance(version, dict)
        or version.get("state") not in FIELD_STATES
        or set(version) != ({"state", "value"} if "value" in version else {"state"})
        or ("value" in version) != (version["state"] == REPORTED)
        or (
            "value" in version
            and (
                not isinstance(version["value"], str)
                or _VERSION.fullmatch(version["value"]) is None
            )
        )
    ):
        return "the collection states no usable serverVersion"
    if not _is_field(collection["completedSamples"], KIND_COUNT):
        return "the collection states no usable completedSamples"
    if type(collection["complete"]) is not bool:
        return "the collection does not state complete as true or false"
    return None


def _reading_fault(query: Query, reading: Mapping[str, Any]) -> str | None:
    """Why a reading does not have the form of its read state, or None."""
    faults = reading["faults"]
    if not isinstance(faults, list) or not all(_is_fault(fault) for fault in faults):
        return "a fault is not a text of this tool"
    read = reading["read"]
    state, collector = read["state"], reading["collector"]
    stated = read["startedAt"] is not None
    if state == NOT_TAKEN and (stated or collector != COLLECTOR_NOT_READ):
        return "a read that was not taken states an instant or a read collector"
    if state in (ANSWERED, ABSENT, UNANSWERED) and not stated:
        return f"the read is {state}, and it states no instant"
    if state == ABSENT and collector != COLLECTOR_ABSENT:
        return "the read is absent, and the collector is not"
    result, series = reading["result"], reading["series"]
    evaluated = reading["evaluatedAt"]
    if result is None:
        if series is not None or evaluated is not None:
            return "a reading with no result states a series or an evaluation instant"
        return None
    if state != ANSWERED:
        return f"the reading states a result, and its read is {state}"
    if result not in RESULTS:
        return "the result is not a registered result"
    if not isinstance(series, list) or not all(isinstance(s, dict) for s in series):
        return "series is not a list of objects"
    if (result == SERIES) != bool(series):
        return "the result does not agree with the number of series"
    if not _is_field(evaluated, KIND_INSTANT):
        return "evaluatedAt is not a field of the kind instant"
    if len(series) > MAX_SERIES:
        return f"the reading states more than {MAX_SERIES} series"
    for entry in series:
        if set(entry) != _SERIES_MEMBERS or not _is_field(entry["value"], query.kind):
            return (
                "a series does not state its labels and a value that is a field "
                f"of the kind {query.kind}"
            )
    return None


def _label_fault(query: Query, reading: Mapping[str, Any]) -> str | None:
    """Why a series states a label that its query does not register, or None."""
    seen: set[tuple[tuple[str, str], ...]] = set()
    for entry in reading["series"] or ():
        labels = entry["labels"]
        if not isinstance(labels, dict) or not set(labels) <= set(query.labels):
            return "a series states a label that its query does not register"
        if not all(
            isinstance(value, str) and _LABEL_VALUE.fullmatch(value) is not None
            for value in labels.values()
        ):
            return "a value of a label does not have the form of a label value"
        key = tuple(sorted(labels.items()))
        if key in seen:
            return "two series state the same labels"
        seen.add(key)
    return None


def read_stream(text: str) -> Stream:
    """A stored stream, held to its form.

    This reads the form of a stream: the header and its collection, the texts
    of this tool that a header repeats, the registered queries, the sequence,
    the members of each line, the states, the instants of each read, the faults,
    the labels and the value of each series, and the end line. It does not show
    that a stream is what a collection gives, and it does not show that a value
    is what a collector answered.

    Raises:
        StreamRefused: a rule of :data:`RULES` is not held.
    """
    if text and not text.endswith("\n"):
        raise StreamRefused(
            RULE_UNREADABLE, "the last line does not end with a line feed"
        )
    lines: list[dict[str, Any]] = []
    for number, line in enumerate(text.split("\n")[:-1], start=1):
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
    stream = header["stream"]
    if (
        header["schema"] != STREAM_SCHEMA
        or not isinstance(stream, str)
        or stream not in STREAMS
    ):
        raise StreamRefused(
            RULE_HEADER, "the header states another schema or an unregistered stream"
        )
    for name in ("experimentId", "runId"):
        value = header[name]
        if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
            raise StreamRefused(RULE_HEADER, f"the header states no usable {name}")
    queries = queries_of(stream)
    collection = header["collection"]
    if (
        header["queries"] != [query.as_document() for query in queries]
        or not isinstance(collection, dict)
        or collection.get("querySet") != QUERY_SET
        or collection.get("querySetSha256") != query_set_sha256()
    ):
        raise StreamRefused(
            RULE_QUERIES,
            "the header does not state the registered queries of its stream and "
            f"the set {QUERY_SET}",
        )
    reason = _collection_fault(collection)
    if reason is not None:
        raise StreamRefused(RULE_HEADER, reason)
    fixed = _fixed_header()
    if stream_text([{name: header[name] for name in fixed}]) != stream_text([fixed]):
        raise StreamRefused(
            RULE_HEADER,
            "the clocks, the bounds, or the statements of the header are not the "
            "texts of this tool",
        )
    if len(lines) < 2 or lines[-1].get("record") != "end":
        raise StreamRefused(RULE_END, "the last line is not an end line")
    end = lines[-1]
    if set(end) != _END_MEMBERS:
        raise StreamRefused(RULE_MEMBERS, "the end line does not have its members")
    readings = lines[1:-1]
    for position, reading in enumerate(readings, start=1):
        where = f"line {position + 1}"
        if reading.get("record") != "reading":
            raise StreamRefused(RULE_SEQUENCE, f"{where} is not a reading")
        if set(reading) != _READING_MEMBERS:
            raise StreamRefused(RULE_MEMBERS, f"{where} does not have its members")
        if type(reading["index"]) is not int or reading["index"] != position:
            raise StreamRefused(RULE_SEQUENCE, f"{where} is not reading {position}")
        sample, place = divmod(position - 1, len(queries))
        query = queries[place]
        if type(reading["sample"]) is not int or reading["sample"] != sample + 1:
            raise StreamRefused(
                RULE_SEQUENCE, f"{where} is not a reading of sample {sample + 1}"
            )
        if reading["query"] != query.name:
            raise StreamRefused(
                RULE_SEQUENCE,
                f"{where} is not the reading of the query {query.name}",
            )
        read = reading["read"]
        if not isinstance(read, dict) or set(read) != _READ_MEMBERS:
            raise StreamRefused(
                RULE_MEMBERS, f"{where}: read does not have its members"
            )
        if not isinstance(read["state"], str) or read["state"] not in READ_STATES:
            raise StreamRefused(RULE_READ, f"{where} states an unregistered read state")
        if (
            not isinstance(reading["collector"], str)
            or reading["collector"] not in COLLECTOR_STATES
        ):
            raise StreamRefused(
                RULE_READ, f"{where} states an unregistered state of the collector"
            )
        started = _stored_instant(read["startedAt"], f"{where}: read.startedAt")
        finished = _stored_instant(read["finishedAt"], f"{where}: read.finishedAt")
        if (started is None) != (finished is None):
            raise StreamRefused(RULE_INSTANT, f"{where} states one instant of two")
        if started is not None and finished is not None and finished < started:
            raise StreamRefused(RULE_INSTANT, f"{where} finishes before it starts")
        reason = _reading_fault(query, reading)
        if reason is not None:
            raise StreamRefused(RULE_READING, f"{where}: {reason}")
        reason = _label_fault(query, reading)
        if reason is not None:
            raise StreamRefused(RULE_LABEL, f"{where}: {reason}")
    if len(readings) % len(queries):
        raise StreamRefused(
            RULE_SEQUENCE, "the last sample does not hold each query of the stream"
        )
    # The end line is compared as text, so a count that is true or 16.0 is not
    # read as 1 or 16.
    if stream_text([end]) != stream_text([_end(readings)]):
        raise StreamRefused(
            RULE_COUNTS,
            "the end line does not state what this tool computes from the readings",
        )
    return Stream(header, tuple(readings), end)
