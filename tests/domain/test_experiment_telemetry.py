"""The telemetry streams of an experiment run, from collections built here.

``tools.experiment_telemetry`` reads the directory that a collector script wrote
and returns two streams: ``telemetry`` and ``resources``. This suite builds each
collection in a temporary directory. It reads no cluster and no telemetry
collector, and it commits no collection.

The suite holds the tool to these properties.

*No series is not zero.* An answer with no series gives a reading with the
result ``no-series`` and no value. A read that did not answer, a release with
no collector, and a sample that was not taken each give a reading with no
result. A value of zero is a value, and it is stated only when the collector
answered zero.

*The queries are registered.* Each query aggregates, each label that it
registers is one that the telemetry catalog permits on a metric, and no query
names a request identifier. A series with any other label leaves its reading
with no series.

*One time basis.* Each reading states the two instants of its read in UTC to
one millisecond. An evaluation instant is on the clock of the collector, and it
keeps each digit that the collector stated.

*A stream holds an allowlist.* No address, no label that is not registered, no
error text, and no value of another form reaches a stream.

*A stream is deterministic and can be read back.* One collection gives one text,
and ``read_stream`` refuses a text that does not have the form.

These tests show what the tool does with a directory. They do not show what a
collector does, and no test here is evidence of telemetry of a real run.
"""

from __future__ import annotations

import ast
import copy
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest

from tools import experiment_telemetry as telemetry
from tools.experiment_evidence import EVIDENCE_SUFFIXES, RAW, ROLES
from tools.experiment_telemetry import core
from tools.experiment_telemetry.__main__ import main
from tools.experiment_timeline import format_instant
from tools.service_endpoint_state import TIERS
from tools.telemetry_collection import emitted_metric_names, forbidden_metric_labels

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE = REPO_ROOT / "docs" / "environment" / "experiment-telemetry.md"
CATALOG = REPO_ROOT / "docs" / "telemetry" / "telemetry-catalog.v1alpha1.json"

NAMESPACE = "inferops-release"
RELEASE = "inferops"
SERVICE = "inferops-inferops-llm-collector"
COMMIT = "a" * 40
T0 = datetime(2026, 10, 12, 8, 0, 0, tzinfo=UTC)
#: The collector's own statement of an instant inside the first read: T0 + 40 ms.
EVALUATED = "1791792000.040"

NAMES = tuple(query.name for query in telemetry.QUERIES)
TELEMETRY_NAMES = tuple(q.name for q in telemetry.queries_of("telemetry"))
RESOURCE_NAMES = tuple(q.name for q in telemetry.queries_of("resources"))

# Values that a stream must never hold. Each is in an answer of the default
# collection, in a member that the allowlist does not read.
HOSTILE = (
    "10.96.44.7",
    "desktop-control-plane",
    "inferops-inferops-llm-7d4f8c7b9-abcde",
    "request-0f8a-not-a-real-identifier",
    "upstream connect error: connection refused by 10.1.0.9",
)


def instant(moment: datetime) -> str:
    return format_instant(moment)


def seconds(moment: datetime) -> str:
    """An instant as the collector states it: seconds, with three decimals."""
    whole = int((moment - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds())
    return f"{whole}.{moment.microsecond // 1000:03d}"


assert seconds(T0 + timedelta(milliseconds=40)) == EVALUATED


def vector(*series: tuple[dict[str, str], Any], at: Any = EVALUATED) -> dict[str, Any]:
    """One answer of the query API: an instant vector."""
    stamp = float(at) if isinstance(at, str) else at
    return {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": dict(labels), "value": [stamp, value]}
                for labels, value in series
            ],
        },
    }


def usual_answers() -> dict[str, Any]:
    """What a release with two API pods and two runtime pods answers.

    The resident memory has no series: no process of the release publishes it.
    """
    return {
        "api-scrape-targets": vector(({}, "2")),
        "api-scrape-targets-up": vector(({}, "2")),
        "api-oldest-scrape": vector(({}, "1791791985.250")),
        "runtime-scrape-targets": vector(({}, "2")),
        "runtime-scrape-targets-up": vector(({}, "1")),
        "runtime-oldest-scrape": vector(({}, "1791791990.5")),
        "api-requests-by-outcome": vector(
            ({"inferops_outcome": "success"}, "120"),
            ({"inferops_outcome": "server-error"}, "3"),
        ),
        "api-errors-by-code": vector(
            ({"inferops_error_code": "capability-unavailable"}, "3")
        ),
        "api-processes-reporting-cpu": vector(({}, "2")),
        "api-cpu-seconds": vector(({}, "12.5")),
        "api-resident-memory-bytes": vector(),
    }


def service_object() -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": SERVICE, "namespace": NAMESPACE},
        "spec": {"clusterIP": HOSTILE[0], "type": "ClusterIP"},
    }


def usual_header(**changes: Any) -> dict[str, Any]:
    header = {
        "schema": telemetry.COLLECTION_SCHEMA,
        "experimentId": "example-experiment",
        "runId": "run-1",
        "provider": "docker-desktop",
        "serverVersion": "v1.34.3",
        "namespace": NAMESPACE,
        "release": RELEASE,
        "collectorService": SERVICE,
        "collectorPort": "http",
        "querySet": telemetry.QUERY_SET,
        "querySetSha256": telemetry.query_set_sha256(),
        "executingCommit": COMMIT,
        "procedureSha256": "1" * 64,
        "librarySha256": "2" * 64,
        "requestedSamples": 1,
        "intervalSeconds": 30,
        "requestTimeoutSeconds": 10,
    }
    header.update(changes)
    return header


UNANSWERED = object()


def write_sample(
    directory: Path,
    index: int,
    *,
    collector: Any = "present",
    answers: dict[str, Any] | None = None,
    start: datetime | None = None,
    meta_changes: dict[str, str | None] | None = None,
) -> None:
    """One sample: the Service read, then one read of 100 ms for each query.

    ``collector`` is ``present``, ``absent``, ``unanswered``, or an object that
    the Service read returned. An answer that is ``UNANSWERED`` writes no file.
    An answer that is text is written as it is.
    """
    stem = directory / f"sample-{index:04d}"
    clock = (T0 + timedelta(seconds=30 * (index - 1))) if start is None else start
    lines = {
        "collectorRead": "unanswered" if collector == "unanswered" else "answered",
        "collectorStartedAt": instant(clock - timedelta(milliseconds=200)),
        "collectorFinishedAt": instant(clock - timedelta(milliseconds=100)),
    }
    if collector == "present":
        Path(f"{stem}.collector.json").write_text(json.dumps(service_object()), "utf-8")
    elif collector == "absent":
        Path(f"{stem}.collector.json").write_text("", "utf-8")
    elif collector != "unanswered":
        Path(f"{stem}.collector.json").write_text(json.dumps(collector), "utf-8")
    stated = usual_answers() if answers is None else {**usual_answers(), **answers}
    for name in NAMES:
        answer = stated[name]
        lines[f"query.{name}.read"] = (
            "unanswered" if answer is UNANSWERED else "answered"
        )
        lines[f"query.{name}.startedAt"] = instant(clock)
        clock += timedelta(milliseconds=100)
        lines[f"query.{name}.finishedAt"] = instant(clock)
        if answer is UNANSWERED:
            continue
        text = answer if isinstance(answer, str) else json.dumps(answer)
        Path(f"{stem}.query.{name}.json").write_text(text, "utf-8")
    for key, value in (meta_changes or {}).items():
        if value is None:
            del lines[key]
        else:
            lines[key] = value
    Path(f"{stem}.meta").write_text(
        "".join(f"{key}={value}\n" for key, value in lines.items()), "utf-8"
    )


def collection(
    tmp_path: Path,
    *samples: dict[str, Any],
    header: dict[str, Any] | None = None,
    end: str | None = "",
) -> Path:
    """A collection of one sample for each keyword set, or of one usual sample."""
    directory = tmp_path / "collection"
    directory.mkdir(parents=True)
    specs = samples or ({},)
    stated = usual_header(requestedSamples=len(specs)) if header is None else header
    (directory / "collection.json").write_text(json.dumps(stated), "utf-8")
    for index, spec in enumerate(specs, start=1):
        if spec.get("taken", True):
            write_sample(
                directory, index, **{k: v for k, v in spec.items() if k != "taken"}
            )
    if end is not None:
        (directory / "collection.end").write_text(
            end or f"completedSamples={len(specs)}\n", "utf-8"
        )
    return directory


def readings(directory: Path, stream: str = "telemetry") -> dict[str, dict[str, Any]]:
    """The readings of the first sample of one stream, by the name of the query."""
    lines = telemetry.build_streams(directory)[stream]
    return {line["query"]: line for line in lines[1:-1] if line["sample"] == 1}


def one(tmp_path: Path, name: str, answer: Any, **spec: Any) -> dict[str, Any]:
    """The reading of one query of a collection whose answer for it is ``answer``."""
    directory = collection(tmp_path, {"answers": {name: answer}, **spec})
    stream = next(q.stream for q in telemetry.QUERIES if q.name == name)
    return readings(directory, stream)[name]


def text_of(directory: Path) -> str:
    built = telemetry.build_streams(directory)
    return "".join(telemetry.stream_text(built[name]) for name in telemetry.STREAMS)


# --------------------------------------------------------------------------
# The registered queries
# --------------------------------------------------------------------------


def test_the_queries_are_a_closed_set_with_one_name_each() -> None:
    assert len(set(NAMES)) == len(NAMES) == 11
    assert len(TELEMETRY_NAMES) == 8
    assert len(RESOURCE_NAMES) == 3
    for query in telemetry.QUERIES:
        assert re.fullmatch(r"[a-z][a-z0-9-]{0,62}", query.name), query.name
        assert query.stream in telemetry.STREAMS
        assert query.kind in telemetry.KINDS
        assert query.states.endswith(".")


def test_each_query_aggregates_so_no_series_keeps_a_label_it_does_not_register() -> (
    None
):
    """``sum``, ``count``, and ``min`` drop each label that ``by`` does not name."""
    form = re.compile(r"(sum|count|min)(?: by \(([a-z_, ]+)\))? ?\((.+)\)")
    for query in telemetry.QUERIES:
        match = form.fullmatch(query.expression)
        assert match is not None, query.expression
        kept = tuple(filter(None, (match.group(2) or "").replace(" ", "").split(",")))
        assert kept == query.labels, query.name


def test_each_registered_label_is_one_the_catalog_permits_on_a_metric() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    permitted = {
        attribute["name"].replace(".", "_")
        for attribute in catalog["attributes"]
        if "metric-label" in attribute["placements"]
    }
    barred = forbidden_metric_labels()
    assert "inferops_request_id" in barred
    assert "inferops_correlation_id" in barred
    registered = {label for query in telemetry.QUERIES for label in query.labels}
    assert registered == {"inferops_outcome", "inferops_error_code"}
    assert registered <= permitted
    assert not registered & barred
    for query in telemetry.QUERIES:
        for label in barred:
            # `timestamp` is a barred label and also a function. A name that an
            # opening bracket follows is the function.
            used = re.search(rf"(?<![a-z_]){label}(?![a-z_(])", query.expression)
            assert used is None, (query.name, label)
        assert "request_id" not in query.expression
        assert "pod" not in query.expression
        assert "instance" not in query.expression


def test_each_query_reads_a_metric_of_the_catalog_or_the_scrape_state() -> None:
    names = emitted_metric_names()
    read = set()
    for query in telemetry.QUERIES:
        found = set(re.findall(r"inferops_[a-z_]+(?=[)\s{]|$)", query.expression))
        found -= set(query.labels)
        assert found <= names, query.name
        assert found or "up{" in query.expression, query.name
        read |= found
    assert read == {
        "inferops_inference_requests_total",
        "inferops_inference_errors_total",
        "inferops_process_cpu_seconds_total",
        "inferops_process_resident_memory_bytes",
    }
    components = set(
        re.findall(
            r'k8s_component="([^"]+)"',
            " ".join(q.expression for q in telemetry.QUERIES),
        )
    )
    assert components == set(TIERS)


def test_the_catalog_records_which_of_the_read_metrics_a_process_publishes() -> None:
    """The page says that the resident memory has no series today. This is why."""
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    emission = {metric["name"]: metric["emission"] for metric in catalog["metrics"]}
    assert emission["inferops_process_resident_memory_bytes"] == "not-emitted"
    for name in (
        "inferops_inference_requests_total",
        "inferops_inference_errors_total",
        "inferops_process_cpu_seconds_total",
    ):
        assert emission[name] == "emitted", name
    page = " ".join(PAGE.read_text(encoding="utf-8").split())
    assert (
        "The telemetry catalog records `inferops_process_resident_memory_bytes` as "
        "not emitted"
    ) in page


def test_the_digest_of_the_set_follows_each_member_of_a_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usual = telemetry.query_set_sha256()
    assert re.fullmatch(r"[0-9a-f]{64}", usual)
    assert telemetry.query_set_sha256() == usual
    first = telemetry.QUERIES[0]
    for change in (
        {"expression": 'count(up{k8s_component="other"})'},
        {"labels": ("inferops_outcome",)},
        {"kind": "number"},
        {"stream": "resources"},
        {"name": "another-name"},
    ):
        changed = telemetry.Query(**{**first.__dict__, **change})
        monkeypatch.setattr(core, "QUERIES", (changed, *telemetry.QUERIES[1:]))
        assert telemetry.query_set_sha256() != usual, change
    # The sentence that describes a query is not part of the digest.
    described = telemetry.Query(**{**first.__dict__, "states": "Other words."})
    monkeypatch.setattr(core, "QUERIES", (described, *telemetry.QUERIES[1:]))
    assert telemetry.query_set_sha256() == usual


def test_the_requests_are_one_line_for_the_set_and_one_for_each_query() -> None:
    lines = telemetry.requests_text().splitlines()
    assert lines[0] == (
        f"query-set {telemetry.QUERY_SET} {telemetry.query_set_sha256()}"
    )
    assert len(lines) == 1 + len(telemetry.QUERIES)
    for line, query in zip(lines[1:], telemetry.QUERIES, strict=True):
        kind, name, path = line.split(" ")
        assert (kind, name) == ("query", query.name)
        # The form that the collector script holds a request to.
        assert re.fullmatch(r"api/v1/query\?query=[A-Za-z0-9%._~-]{1,492}", path)
        assert unquote(path.split("=", 1)[1]) == query.expression


# --------------------------------------------------------------------------
# A collection, as two streams
# --------------------------------------------------------------------------


def test_one_sample_gives_one_reading_for_each_query_of_each_stream(
    tmp_path: Path,
) -> None:
    built = telemetry.build_streams(collection(tmp_path))
    assert set(built) == {"telemetry", "resources"}
    for name, names in (("telemetry", TELEMETRY_NAMES), ("resources", RESOURCE_NAMES)):
        header, *lines, end = built[name]
        assert header["record"] == "header"
        assert header["stream"] == name
        assert header["schema"] == telemetry.STREAM_SCHEMA
        assert header["collection"]["complete"] is True
        assert header["clock"]["skew"] == "not-measured"
        assert [query["name"] for query in header["queries"]] == list(names)
        assert tuple(line["query"] for line in lines) == names
        assert [line["index"] for line in lines] == list(range(1, len(names) + 1))
        assert {line["sample"] for line in lines} == {1}
        assert {line["collector"] for line in lines} == {"present"}
        assert end["readings"] == len(names)
        assert end["byReadState"]["answered"] == len(names)
    first = built["telemetry"][1]
    assert first == {
        "record": "reading",
        "index": 1,
        "sample": 1,
        "query": "api-scrape-targets",
        "read": {
            "state": "answered",
            "startedAt": "2026-10-12T08:00:00.000Z",
            "finishedAt": "2026-10-12T08:00:00.100Z",
        },
        "collector": "present",
        "result": "series",
        "evaluatedAt": {
            "state": "reported",
            "value": "2026-10-12T08:00:00.040Z",
            "resolution": "millisecond",
        },
        "series": [{"labels": {}, "value": {"state": "reported", "value": 2}}],
        "faults": [],
    }


def test_a_grouped_query_states_one_series_for_each_value_of_its_label(
    tmp_path: Path,
) -> None:
    found = readings(collection(tmp_path))
    assert found["api-requests-by-outcome"]["series"] == [
        {
            "labels": {"inferops_outcome": "server-error"},
            "value": {"state": "reported", "value": 3.0},
        },
        {
            "labels": {"inferops_outcome": "success"},
            "value": {"state": "reported", "value": 120.0},
        },
    ]
    assert found["api-errors-by-code"]["series"] == [
        {
            "labels": {"inferops_error_code": "capability-unavailable"},
            "value": {"state": "reported", "value": 3.0},
        }
    ]


def test_an_answer_with_no_series_is_not_a_value_of_zero(tmp_path: Path) -> None:
    """The resident memory: no process of the release publishes the metric."""
    directory = collection(tmp_path)
    reading = readings(directory, "resources")["api-resident-memory-bytes"]
    assert reading["read"]["state"] == "answered"
    assert reading["result"] == "no-series"
    assert reading["series"] == []
    assert reading["evaluatedAt"] == {"state": "missing"}
    assert reading["faults"] == []
    end = telemetry.build_streams(directory)["resources"][-1]
    assert end["byResult"] == {"series": 2, "no-series": 1}
    assert end["byReadState"]["answered"] == 3
    # No member of the reading states a number.
    assert not re.search(r"[0-9]", json.dumps(reading["series"]))


def test_a_value_of_zero_is_a_value_and_differs_from_no_series(tmp_path: Path) -> None:
    zero = one(tmp_path, "runtime-scrape-targets-up", vector(({}, "0")))
    assert zero["result"] == "series"
    assert zero["series"] == [
        {"labels": {}, "value": {"state": "reported", "value": 0}}
    ]
    none = one(tmp_path / "b", "runtime-scrape-targets-up", vector())
    assert none["result"] == "no-series"
    assert none["series"] == []
    assert zero["series"] != none["series"]


def test_a_query_that_did_not_answer_gives_no_result(tmp_path: Path) -> None:
    directory = collection(tmp_path, {"answers": {"api-errors-by-code": UNANSWERED}})
    found = readings(directory)
    reading = found["api-errors-by-code"]
    assert reading["read"] == {
        "state": "unanswered",
        "startedAt": "2026-10-12T08:00:00.700Z",
        "finishedAt": "2026-10-12T08:00:00.800Z",
    }
    assert reading["collector"] == "present"
    assert (reading["result"], reading["evaluatedAt"], reading["series"]) == (
        None,
        None,
        None,
    )
    # The other reads of the same sample are as they were.
    assert found["api-requests-by-outcome"]["result"] == "series"
    end = telemetry.build_streams(directory)["telemetry"][-1]
    assert end["byReadState"] == {
        "answered": 7,
        "absent": 0,
        "unanswered": 1,
        "unreadable": 0,
        "not-taken": 0,
    }
    assert end["byResult"] == {"series": 7, "no-series": 0}


def test_a_release_with_no_collector_states_each_read_as_absent(tmp_path: Path) -> None:
    """The Service read answered with no object, and no query answered."""
    directory = collection(
        tmp_path,
        {"collector": "absent", "answers": dict.fromkeys(NAMES, UNANSWERED)},
    )
    for stream in telemetry.STREAMS:
        _, *lines, end = telemetry.build_streams(directory)[stream]
        assert {line["read"]["state"] for line in lines} == {"absent"}
        assert {line["collector"] for line in lines} == {"absent"}
        assert all(line["result"] is None for line in lines)
        assert all(line["series"] is None for line in lines)
        assert end["byReadState"]["absent"] == len(lines)
        assert end["byResult"] == {"series": 0, "no-series": 0}
        assert end["evaluationOffset"] == {
            "readings": 0,
            "notBelowMilliseconds": None,
            "notAboveMilliseconds": None,
        }


def test_a_service_read_that_did_not_answer_does_not_make_a_query_absent(
    tmp_path: Path,
) -> None:
    directory = collection(
        tmp_path,
        {"collector": "unanswered", "answers": {"api-cpu-seconds": UNANSWERED}},
    )
    reading = readings(directory, "resources")["api-cpu-seconds"]
    assert reading["read"]["state"] == "unanswered"
    assert reading["collector"] == "not-read"
    # A query that answered is an answer, whatever the Service read showed.
    assert readings(directory)["api-scrape-targets"]["read"]["state"] == "answered"


@pytest.mark.parametrize(
    "answer",
    [
        {"kind": "Service", "metadata": {"name": "other", "namespace": NAMESPACE}},
        {"kind": "Service", "metadata": {"name": SERVICE, "namespace": "other"}},
        {"kind": "Pod", "metadata": {"name": SERVICE, "namespace": NAMESPACE}},
        {"kind": "Service"},
        ["not", "an", "object"],
    ],
)
def test_a_service_answer_that_is_another_object_is_not_read(
    tmp_path: Path, answer: Any
) -> None:
    directory = collection(
        tmp_path, {"collector": answer, "answers": {"api-cpu-seconds": UNANSWERED}}
    )
    reading = readings(directory, "resources")["api-cpu-seconds"]
    assert reading["collector"] == "not-read"
    assert reading["read"]["state"] == "unanswered"


def test_a_query_that_answered_while_the_service_read_showed_none_is_an_answer(
    tmp_path: Path,
) -> None:
    found = readings(collection(tmp_path, {"collector": "absent"}))
    assert found["api-scrape-targets"]["read"]["state"] == "answered"
    assert found["api-scrape-targets"]["collector"] == "absent"
    assert found["api-scrape-targets"]["result"] == "series"


def test_a_sample_that_was_not_taken_is_a_reading_with_no_instant(
    tmp_path: Path,
) -> None:
    directory = collection(tmp_path, {}, {"taken": False}, end=None)
    header, *lines, end = telemetry.build_streams(directory)["telemetry"]
    assert header["collection"]["complete"] is False
    assert header["collection"]["completedSamples"] == {"state": "missing"}
    later = [line for line in lines if line["sample"] == 2]
    assert len(later) == 8
    for line in later:
        assert line["read"] == {
            "state": "not-taken",
            "startedAt": None,
            "finishedAt": None,
        }
        assert line["collector"] == "not-read"
        assert line["result"] is None
    assert end["byReadState"]["not-taken"] == 8
    assert end["readings"] == 16


@pytest.mark.parametrize(
    "end,completed",
    [
        ("completedSamples=1\n", {"state": "reported", "value": 1}),
        ("completedSamples=many\n", {"state": "malformed"}),
        ("other=1\n", {"state": "missing"}),
    ],
)
def test_a_collection_is_complete_only_when_its_end_states_each_sample(
    tmp_path: Path, end: str, completed: dict[str, Any]
) -> None:
    directory = collection(tmp_path, {}, {}, end=end)
    header = telemetry.build_streams(directory)["resources"][0]
    assert header["collection"]["completedSamples"] == completed
    assert header["collection"]["complete"] is False


@pytest.mark.parametrize(
    "changes,detail",
    [
        (
            {"query.api-cpu-seconds.startedAt": "2026-10-12 08:00:00"},
            "no usable instants",
        ),
        ({"query.api-cpu-seconds.finishedAt": None}, "no usable instants"),
        (
            {"query.api-cpu-seconds.finishedAt": "2026-10-12T07:00:00.000Z"},
            "no usable instants",
        ),
        ({"query.api-cpu-seconds.read": None}, "does not state whether"),
        ({"query.api-cpu-seconds.read": "maybe"}, "does not state whether"),
    ],
)
def test_a_read_that_the_sample_does_not_state_in_form_is_unreadable(
    tmp_path: Path, changes: dict[str, str | None], detail: str
) -> None:
    directory = collection(tmp_path, {"meta_changes": changes})
    reading = readings(directory, "resources")["api-cpu-seconds"]
    assert reading["read"]["state"] == "unreadable"
    assert reading["result"] is None
    assert detail in reading["faults"][0]
    if "instants" in detail:
        assert reading["read"]["startedAt"] is None


def test_an_answer_the_sample_states_and_the_directory_lacks_is_unreadable(
    tmp_path: Path,
) -> None:
    directory = collection(tmp_path)
    (directory / "sample-0001.query.api-cpu-seconds.json").unlink()
    reading = readings(directory, "resources")["api-cpu-seconds"]
    assert reading["read"]["state"] == "unreadable"
    assert "holds no file" in reading["faults"][0]
    (directory / "sample-0001.query.api-cpu-seconds.json").mkdir()
    reading = readings(directory, "resources")["api-cpu-seconds"]
    assert reading["read"]["state"] == "unreadable"


@pytest.mark.parametrize(
    "answer,fault",
    [
        ("", "not one JSON object"),
        ("not json", "not one JSON object"),
        ("[1, 2]", "not one JSON object"),
        pytest.param("[" * 100_000, "not one JSON object", id="deeply-nested"),
        ({"status": "error", "errorType": "bad_data", "error": HOSTILE[4]}, "success"),
        ({"status": "success"}, "success"),
        ({"status": "success", "data": []}, "success"),
        (
            {"status": "success", "data": {"resultType": "matrix", "result": []}},
            "instant vector",
        ),
        (
            {"status": "success", "data": {"resultType": "vector", "result": {}}},
            "instant vector",
        ),
    ],
)
def test_an_answer_that_is_not_an_instant_vector_is_not_counted_as_answered(
    tmp_path: Path, answer: Any, fault: str
) -> None:
    reading = one(tmp_path, "api-cpu-seconds", answer)
    assert reading["read"]["state"] == "unreadable"
    assert reading["read"]["startedAt"] is not None
    assert (reading["result"], reading["series"]) == (None, None)
    assert fault in reading["faults"][0]
    assert HOSTILE[4] not in json.dumps(reading)


# --------------------------------------------------------------------------
# Labels: what a series may state
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "labels",
    [
        {"inferops_outcome": "success", "inferops_request_id": HOSTILE[3]},
        {"inferops_request_id": HOSTILE[3]},
        {"instance": HOSTILE[2]},
        {"__name__": "inferops_inference_requests_total"},
        {"inferops_error_code": "capability-unavailable"},
    ],
)
def test_a_series_with_a_label_that_is_not_registered_leaves_no_series(
    tmp_path: Path, labels: dict[str, str]
) -> None:
    answer = vector(({"inferops_outcome": "success"}, "120"), (labels, "7"))
    reading = one(tmp_path, "api-requests-by-outcome", answer)
    assert reading["read"]["state"] == "answered"
    assert (reading["result"], reading["evaluatedAt"], reading["series"]) == (
        None,
        None,
        None,
    )
    assert reading["faults"] == [
        "a series states a label that the query does not register"
    ]
    # Neither the name of the label nor its value is copied.
    stored = json.dumps(reading)
    for text in (*labels, *labels.values()):
        if text != "inferops_outcome" and text != "success":
            assert text not in stored, text


@pytest.mark.parametrize(
    "value",
    [
        "",
        "has space",
        "user@example.invalid",
        "/" + "home/someone/file",
        "a" * 64,
        "line\nbreak",
        "-leading",
        7,
        None,
    ],
)
def test_a_label_value_of_another_form_leaves_no_series(
    tmp_path: Path, value: Any
) -> None:
    answer = vector(({"inferops_outcome": value}, "1"))
    reading = one(tmp_path, "api-requests-by-outcome", answer)
    assert reading["series"] is None
    assert reading["result"] is None
    assert reading["faults"] == [
        "a value of a label does not have the form of a label value"
    ]
    if isinstance(value, str) and value:
        assert json.dumps(value)[1:-1] not in json.dumps(reading)


def test_two_series_with_the_same_labels_leave_no_series(tmp_path: Path) -> None:
    answer = vector(
        ({"inferops_outcome": "success"}, "1"), ({"inferops_outcome": "success"}, "2")
    )
    reading = one(tmp_path, "api-requests-by-outcome", answer)
    assert reading["series"] is None
    assert reading["faults"] == ["two series state the same labels"]


def test_a_reading_with_more_series_than_the_bound_states_none(tmp_path: Path) -> None:
    def series(count: int) -> dict[str, Any]:
        return vector(
            *(({"inferops_outcome": f"outcome-{n}"}, "1") for n in range(count))
        )

    most = one(tmp_path, "api-requests-by-outcome", series(telemetry.MAX_SERIES))
    assert len(most["series"]) == telemetry.MAX_SERIES == 32
    over = one(
        tmp_path / "b", "api-requests-by-outcome", series(telemetry.MAX_SERIES + 1)
    )
    assert over["read"]["state"] == "answered"
    assert over["series"] is None
    assert over["faults"] == [
        "the answer holds more than 32 series, and the reading states none"
    ]


@pytest.mark.parametrize(
    "item",
    [
        "text",
        {"metric": {}},
        {"value": [1791792000.04, "1"]},
        {"metric": [], "value": [1791792000.04, "1"]},
        {"metric": {}, "value": "1"},
        {"metric": {}, "value": [1791792000.04]},
        {"metric": {}, "value": [1791792000.04, "1", "2"]},
    ],
)
def test_a_series_that_does_not_hold_its_labels_and_one_sample_leaves_none(
    tmp_path: Path, item: Any
) -> None:
    answer = vector(({}, "2"))
    answer["data"]["result"].append(item)
    reading = one(tmp_path, "api-cpu-seconds", answer)
    assert reading["series"] is None
    assert reading["faults"] == ["a series does not hold its labels and one sample"]


def test_the_faults_of_a_reading_are_bounded_and_are_texts_of_the_tool(
    tmp_path: Path,
) -> None:
    faults = [f"fault {n}" for n in range(14)]
    assert core._bounded(faults) == [*faults[:10], "4 more fault(s) are not listed"]
    assert core._bounded(faults[:10]) == faults[:10]
    # One answer with each kind of fault states each kind once.
    answer = vector(
        ({"instance": HOSTILE[2]}, "1"),
        ({"instance": HOSTILE[1]}, "1"),
        ({"inferops_outcome": "has space"}, "1"),
    )
    answer["data"]["result"].append("text")
    reading = one(tmp_path, "api-requests-by-outcome", answer)
    assert reading["faults"] == [
        "a series states a label that the query does not register",
        "a value of a label does not have the form of a label value",
        "a series does not hold its labels and one sample",
    ]


# --------------------------------------------------------------------------
# Values and instants
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,stated,field",
    [
        ("api-scrape-targets", "2", {"state": "reported", "value": 2}),
        ("api-scrape-targets", "2e0", {"state": "reported", "value": 2}),
        ("api-scrape-targets", "2.0", {"state": "reported", "value": 2}),
        ("api-scrape-targets", "1.5", {"state": "malformed"}),
        ("api-scrape-targets", "-1", {"state": "malformed"}),
        ("api-scrape-targets", "1000000000", {"state": "malformed"}),
        ("api-scrape-targets", "NaN", {"state": "malformed"}),
        ("api-scrape-targets", 2, {"state": "malformed"}),
        ("api-scrape-targets", True, {"state": "malformed"}),
        ("api-scrape-targets", None, {"state": "malformed"}),
        ("api-cpu-seconds", "12.5", {"state": "reported", "value": 12.5}),
        ("api-cpu-seconds", "0", {"state": "reported", "value": 0.0}),
        ("api-cpu-seconds", "1e3", {"state": "reported", "value": 1000.0}),
        ("api-cpu-seconds", "-2.5", {"state": "reported", "value": -2.5}),
        ("api-cpu-seconds", "NaN", {"state": "malformed"}),
        ("api-cpu-seconds", "+Inf", {"state": "malformed"}),
        ("api-cpu-seconds", "-Inf", {"state": "malformed"}),
        ("api-cpu-seconds", "1e999", {"state": "malformed"}),
        ("api-cpu-seconds", "12,5", {"state": "malformed"}),
        ("api-cpu-seconds", "١٢", {"state": "malformed"}),
        ("api-cpu-seconds", "", {"state": "malformed"}),
        ("api-cpu-seconds", 12.5, {"state": "malformed"}),
        (
            "api-oldest-scrape",
            "1791791985.250",
            {
                "state": "reported",
                "value": "2026-10-12T07:59:45.250Z",
                "resolution": "millisecond",
            },
        ),
        (
            "api-oldest-scrape",
            "1791791985",
            {
                "state": "reported",
                "value": "2026-10-12T07:59:45.000Z",
                "resolution": "millisecond",
            },
        ),
        (
            "api-oldest-scrape",
            "1791791985.9999",
            {
                "state": "reported",
                "value": "2026-10-12T07:59:45.999Z",
                "resolution": "millisecond",
            },
        ),
        ("api-oldest-scrape", "-1", {"state": "malformed"}),
        ("api-oldest-scrape", "253402300800", {"state": "malformed"}),
        ("api-oldest-scrape", "NaN", {"state": "malformed"}),
    ],
)
def test_a_value_is_reported_only_in_the_form_of_the_kind_of_its_query(
    tmp_path: Path, name: str, stated: Any, field: dict[str, Any]
) -> None:
    reading = one(tmp_path, name, vector(({}, stated)))
    assert reading["read"]["state"] == "answered"
    assert reading["result"] == "series"
    assert reading["series"] == [{"labels": {}, "value": field}]
    kind = next(q.kind for q in telemetry.QUERIES if q.name == name)
    expected = (
        []
        if field["state"] == "reported"
        else [f"1 value(s) do not have the form of the kind {kind}"]
    )
    assert reading["faults"] == expected


def test_an_evaluation_instant_is_cut_to_one_millisecond_and_is_not_rounded(
    tmp_path: Path,
) -> None:
    for number, (stated, expected) in enumerate(
        [
            ("1791792000.123", "2026-10-12T08:00:00.123Z"),
            ("1791792000.1239", "2026-10-12T08:00:00.123Z"),
            ("1791792000.9996", "2026-10-12T08:00:00.999Z"),
            ("1791792000", "2026-10-12T08:00:00.000Z"),
        ]
    ):
        text = json.dumps(vector(({}, "1"))).replace("1791792000.04", stated)
        assert stated in text
        reading = one(tmp_path / str(number), "api-cpu-seconds", text)
        assert reading["evaluatedAt"] == {
            "state": "reported",
            "value": expected,
            "resolution": "millisecond",
        }


@pytest.mark.parametrize(
    "stamps",
    [
        (1791792000.04, 1791792000.05),
        ("1791792000.04",),
        (None,),
        (True,),
        (-5,),
        (253402300800,),
    ],
)
def test_series_that_do_not_state_one_usable_evaluation_instant_state_none(
    tmp_path: Path, stamps: tuple[Any, ...]
) -> None:
    answer = vector(
        *(({"inferops_outcome": f"outcome-{n}"}, "1") for n in range(len(stamps)))
    )
    for item, stamp in zip(answer["data"]["result"], stamps, strict=True):
        item["value"][0] = stamp
    reading = one(tmp_path, "api-requests-by-outcome", answer)
    assert reading["evaluatedAt"] == {"state": "malformed"}
    assert reading["result"] == "series"
    assert reading["faults"] == [
        "the series do not state one usable evaluation instant"
    ]


def test_the_end_line_bounds_the_difference_of_the_two_clocks(tmp_path: Path) -> None:
    """Each read is 100 ms. The collector states T0 + 40 ms for each query.

    The first read is open from T0 to T0 + 100 ms, so the collector's clock is
    between 60 ms behind and 40 ms ahead. The last read of the stream starts at
    T0 + 700 ms, so it is between 760 ms and 660 ms behind. The two bounds are
    the largest lower bound and the smallest upper bound, and here they do not
    agree: the collection states one evaluation instant for reads at eight
    different instants.
    """
    end = telemetry.build_streams(collection(tmp_path))["telemetry"][-1]
    assert end["evaluationOffset"] == {
        "readings": 8,
        "notBelowMilliseconds": -60,
        "notAboveMilliseconds": -660,
    }
    # One reading with a series: the two bounds are its two differences.
    answers: dict[str, Any] = dict.fromkeys(NAMES, vector())
    answers["api-scrape-targets"] = vector(
        ({}, "2"), at=seconds(T0 + timedelta(milliseconds=350))
    )
    end = telemetry.build_streams(collection(tmp_path / "b", {"answers": answers}))[
        "telemetry"
    ][-1]
    assert end["evaluationOffset"] == {
        "readings": 1,
        "notBelowMilliseconds": 250,
        "notAboveMilliseconds": 350,
    }
    assert end["byResult"] == {"series": 1, "no-series": 7}


def test_the_end_line_names_each_reading_that_starts_before_the_one_before_finished(
    tmp_path: Path,
) -> None:
    directory = collection(tmp_path, {}, {"start": T0 - timedelta(seconds=5)})
    end = telemetry.build_streams(directory)["telemetry"][-1]
    assert end["instantsOutOfOrder"] == [9]
    assert (
        telemetry.build_streams(collection(tmp_path / "b", {}, {}))["telemetry"][-1][
            "instantsOutOfOrder"
        ]
        == []
    )


# --------------------------------------------------------------------------
# What a stream leaves out
# --------------------------------------------------------------------------


def test_no_stream_holds_a_value_that_the_allowlist_does_not_read(
    tmp_path: Path,
) -> None:
    hostile = vector(({"instance": HOSTILE[2], "node": HOSTILE[1]}, "1"))
    hostile["warnings"] = [HOSTILE[4]]
    directory = collection(
        tmp_path,
        {
            "answers": {
                "api-scrape-targets": hostile,
                "api-cpu-seconds": {"status": "error", "error": HOSTILE[4]},
                "api-errors-by-code": vector(
                    ({"inferops_request_id": HOSTILE[3]}, "1")
                ),
            }
        },
    )
    raw = "".join(
        path.read_text("utf-8") for path in directory.iterdir() if path.is_file()
    )
    stored = text_of(directory)
    for value in HOSTILE:
        assert value in raw, value
        assert value not in stored, value
    assert "clusterIP" not in stored
    assert "inferops_request_id" not in stored


def test_the_tool_reads_no_caller_record_and_names_no_request_identifier() -> None:
    """The caller record has another source, and no stream is derived from it."""
    package = REPO_ROOT / "tools" / "experiment_telemetry"
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for name in imported:
            assert "reliability_runner" not in name, path.name
            assert "llm_load" not in name, path.name
            assert not name.startswith(("urllib.request", "http", "socket")), path.name
        assert "request_id" not in path.read_text(encoding="utf-8"), path.name


# --------------------------------------------------------------------------
# A collection that is refused
# --------------------------------------------------------------------------


def _without(header: dict[str, Any], name: str) -> dict[str, Any]:
    return {key: value for key, value in header.items() if key != name}


@pytest.mark.parametrize(
    "header,message",
    [
        (_without(usual_header(), "querySet"), "members of a collection"),
        ({**usual_header(), "note": "x"}, "members of a collection"),
        (usual_header(schema="inferops.io/other/v1"), "another schema"),
        (usual_header(experimentId="has space"), "experimentId"),
        (usual_header(runId="../run"), "runId"),
        (usual_header(provider="Docker Desktop"), "provider"),
        (usual_header(namespace=7), "namespace"),
        (usual_header(collectorService="svc/other"), "collectorService"),
        (usual_header(collectorPort="9090/x"), "collectorPort"),
        (usual_header(executingCommit="abc"), "executingCommit"),
        (usual_header(procedureSha256="1" * 63), "procedureSha256"),
        (usual_header(querySet="another-set"), "does not state the query set"),
        (usual_header(querySetSha256="0" * 64), "does not state the query set"),
        (usual_header(requestedSamples=0), "requestedSamples"),
        (usual_header(requestedSamples=721), "requestedSamples"),
        (usual_header(requestedSamples=True), "requestedSamples"),
        (usual_header(requestedSamples=1.0), "requestedSamples"),
        (usual_header(intervalSeconds=4), "intervalSeconds"),
        (usual_header(intervalSeconds=121), "intervalSeconds"),
        (usual_header(requestTimeoutSeconds=61), "requestTimeoutSeconds"),
        (usual_header(serverVersion=None), "serverVersion"),
    ],
)
def test_a_header_that_does_not_have_the_form_is_refused(
    tmp_path: Path, header: dict[str, Any], message: str
) -> None:
    directory = collection(tmp_path, header=header)
    with pytest.raises(telemetry.CollectionRefused, match=message):
        telemetry.build_streams(directory)


def test_a_collection_of_another_query_set_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The digest in the header is the tool's, so a changed query refuses."""
    directory = collection(tmp_path)
    telemetry.build_streams(directory)
    first = telemetry.QUERIES[0]
    changed = telemetry.Query(**{**first.__dict__, "expression": "count(up)"})
    monkeypatch.setattr(core, "QUERIES", (changed, *telemetry.QUERIES[1:]))
    with pytest.raises(telemetry.CollectionRefused, match="another set of queries"):
        telemetry.build_streams(directory)


@pytest.mark.parametrize(
    "version,field",
    [
        ("", {"state": "missing"}),
        ("1.34", {"state": "malformed"}),
        ("v1.34.3", {"state": "reported", "value": "v1.34.3"}),
    ],
)
def test_a_server_version_that_was_not_read_is_kept_as_a_field(
    tmp_path: Path, version: str, field: dict[str, Any]
) -> None:
    directory = collection(tmp_path, header=usual_header(serverVersion=version))
    header = telemetry.build_streams(directory)["telemetry"][0]
    assert header["collection"]["serverVersion"] == field


def test_a_directory_that_is_not_a_collection_is_refused(tmp_path: Path) -> None:
    with pytest.raises(telemetry.CollectionRefused, match="not a directory"):
        telemetry.build_streams(tmp_path / "none")
    with pytest.raises(telemetry.CollectionRefused, match=r"holds no collection\.json"):
        telemetry.build_streams(tmp_path)
    (tmp_path / "collection.json").write_text("[]", "utf-8")
    with pytest.raises(telemetry.CollectionRefused, match="not one JSON object"):
        telemetry.build_streams(tmp_path)


def test_a_sample_that_the_header_did_not_ask_for_is_refused(tmp_path: Path) -> None:
    directory = collection(tmp_path)
    write_sample(directory, 2)
    with pytest.raises(telemetry.CollectionRefused, match=r"sample-0002\.meta"):
        telemetry.build_streams(directory)


# --------------------------------------------------------------------------
# A stored stream, read back
# --------------------------------------------------------------------------


def test_one_collection_gives_one_text(tmp_path: Path) -> None:
    directory = collection(tmp_path, {}, {"collector": "absent"})
    first = text_of(directory)
    assert text_of(directory) == first
    assert first.endswith("\n")
    assert "\r" not in first
    for line in first.splitlines():
        document = json.loads(line)
        assert list(document) == sorted(document)


def test_the_order_of_the_series_in_an_answer_does_not_change_a_stream(
    tmp_path: Path,
) -> None:
    usual = usual_answers()["api-requests-by-outcome"]
    turned = copy.deepcopy(usual)
    turned["data"]["result"].reverse()
    first = text_of(collection(tmp_path))
    second = text_of(
        collection(tmp_path / "b", {"answers": {"api-requests-by-outcome": turned}})
    )
    assert first == second


def test_each_built_stream_is_read_back(tmp_path: Path) -> None:
    directory = collection(
        tmp_path,
        {},
        {"collector": "absent", "answers": dict.fromkeys(NAMES, UNANSWERED)},
        {"answers": {"api-cpu-seconds": "not json", "api-errors-by-code": UNANSWERED}},
        {"taken": False},
        end=None,
    )
    built = telemetry.build_streams(directory)
    for name in telemetry.STREAMS:
        stream = telemetry.read_stream(telemetry.stream_text(built[name]))
        assert stream.name == name
        assert stream.header == built[name][0]
        assert list(stream.readings) == built[name][1:-1]
        assert stream.end == built[name][-1]
    stream = telemetry.read_stream(telemetry.stream_text(built["telemetry"]))
    assert stream.summary() == (
        "telemetry: 32 reading(s): 15 answered, 8 absent, 1 unanswered, "
        "8 not-taken; 15 with series, 0 with no series"
    )
    stream = telemetry.read_stream(telemetry.stream_text(built["resources"]))
    assert stream.summary() == (
        "resources: 12 reading(s): 5 answered, 3 absent, 1 unreadable, "
        "3 not-taken; 3 with series, 2 with no series"
    )


def _lines(tmp_path: Path, stream: str = "telemetry") -> list[dict[str, Any]]:
    built = telemetry.build_streams(collection(tmp_path, {}, {}))
    return copy.deepcopy(built[stream])


Change = Callable[[list[dict[str, Any]]], Any]


def _set(index: int, *path: Any, value: Any) -> Change:
    def change(lines: list[dict[str, Any]]) -> None:
        target: Any = lines[index]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def _drop(index: int, *path: Any) -> Change:
    def change(lines: list[dict[str, Any]]) -> None:
        target: Any = lines[index]
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return change


# Line 7 is the reading of api-requests-by-outcome of the first sample.
STORED_CASES: list[tuple[str, Change, str]] = [
    ("header-missing", lambda lines: lines.pop(0), core.RULE_HEADER),
    ("other-schema", _set(0, "schema", value="x"), core.RULE_HEADER),
    ("other-stream", _set(0, "stream", value="pods"), core.RULE_HEADER),
    ("bad-run", _set(0, "runId", value="a b"), core.RULE_HEADER),
    ("header-extra", _set(0, "note", value="x"), core.RULE_MEMBERS),
    ("reading-extra", _set(1, "note", value="x"), core.RULE_MEMBERS),
    ("reading-short", _drop(1, "collector"), core.RULE_MEMBERS),
    ("read-extra", _set(1, "read", "note", value="x"), core.RULE_MEMBERS),
    ("end-extra", _set(-1, "note", value="x"), core.RULE_MEMBERS),
    (
        "queries-changed",
        _set(0, "queries", 0, "expression", value="count(up)"),
        core.RULE_QUERIES,
    ),
    ("queries-short", lambda lines: lines[0]["queries"].pop(), core.RULE_QUERIES),
    (
        "other-set",
        _set(0, "collection", "querySetSha256", value="0" * 64),
        core.RULE_QUERIES,
    ),
    ("collection-not-object", _set(0, "collection", value=[]), core.RULE_QUERIES),
    ("not-a-reading", _set(2, "record", value="event"), core.RULE_SEQUENCE),
    ("index-gap", _set(2, "index", value=5), core.RULE_SEQUENCE),
    ("index-float", _set(2, "index", value=2.0), core.RULE_SEQUENCE),
    ("index-true", _set(1, "index", value=True), core.RULE_SEQUENCE),
    ("other-sample", _set(2, "sample", value=2), core.RULE_SEQUENCE),
    ("other-query", _set(2, "query", value="api-cpu-seconds"), core.RULE_SEQUENCE),
    ("half-sample", lambda lines: lines.pop(-2), core.RULE_SEQUENCE),
    ("read-state", _set(1, "read", "state", value="healthy"), core.RULE_READ),
    ("collector-state", _set(1, "collector", value="up"), core.RULE_READ),
    (
        "instant-form",
        _set(1, "read", "startedAt", value="2026-10-12T08:00:00Z"),
        core.RULE_INSTANT,
    ),
    ("one-instant", _set(1, "read", "finishedAt", value=None), core.RULE_INSTANT),
    (
        "finishes-first",
        _set(1, "read", "finishedAt", value="2026-10-12T07:00:00.000Z"),
        core.RULE_INSTANT,
    ),
    ("faults-text", _set(1, "faults", value="none"), core.RULE_READING),
    ("faults-items", _set(1, "faults", value=[1]), core.RULE_READING),
    (
        "result-unanswered",
        _set(1, "read", "state", value="unanswered"),
        core.RULE_READING,
    ),
    ("result-other", _set(1, "result", value="zero"), core.RULE_READING),
    ("result-none-series", _set(1, "result", value=None), core.RULE_READING),
    ("series-result-empty", _set(1, "series", value=[]), core.RULE_READING),
    ("no-series-with-one", _set(1, "result", value="no-series"), core.RULE_READING),
    ("series-not-list", _set(1, "series", value={}), core.RULE_READING),
    ("evaluated-not-field", _set(1, "evaluatedAt", value="now"), core.RULE_READING),
    (
        "evaluated-state",
        _set(1, "evaluatedAt", value={"state": "healthy"}),
        core.RULE_READING,
    ),
    (
        "value-not-field",
        _set(1, "series", 0, "value", value=2),
        core.RULE_READING,
    ),
    (
        "value-missing-with-value",
        _set(1, "series", 0, "value", value={"state": "missing", "value": 0}),
        core.RULE_READING,
    ),
    ("series-extra", _set(1, "series", 0, "note", value="x"), core.RULE_READING),
    (
        "too-many-series",
        _set(
            7,
            "series",
            value=[
                {
                    "labels": {"inferops_outcome": f"outcome-{n}"},
                    "value": {"state": "reported", "value": 1.0},
                }
                for n in range(33)
            ],
        ),
        core.RULE_READING,
    ),
    (
        "label-unregistered",
        _set(7, "series", 0, "labels", value={"inferops_request_id": "r-1"}),
        core.RULE_LABEL,
    ),
    (
        "label-on-plain-query",
        _set(1, "series", 0, "labels", value={"inferops_outcome": "success"}),
        core.RULE_LABEL,
    ),
    (
        "label-value-form",
        _set(7, "series", 0, "labels", value={"inferops_outcome": "a b"}),
        core.RULE_LABEL,
    ),
    (
        "label-value-type",
        _set(7, "series", 0, "labels", value={"inferops_outcome": 7}),
        core.RULE_LABEL,
    ),
    ("labels-not-object", _set(7, "series", 0, "labels", value=[]), core.RULE_LABEL),
    (
        "labels-twice",
        _set(7, "series", 1, "labels", value={"inferops_outcome": "server-error"}),
        core.RULE_LABEL,
    ),
    ("end-missing", lambda lines: lines.pop(), core.RULE_END),
    ("line-after-end", lambda lines: lines.append(dict(lines[1])), core.RULE_END),
    ("count-readings", _set(-1, "readings", value=15), core.RULE_COUNTS),
    ("count-float", _set(-1, "readings", value=16.0), core.RULE_COUNTS),
    ("count-states", _set(-1, "byReadState", "answered", value=15), core.RULE_COUNTS),
    ("count-states-list", _set(-1, "byReadState", value=[]), core.RULE_COUNTS),
    ("count-results", _set(-1, "byResult", "series", value=0), core.RULE_COUNTS),
    (
        "count-true",
        lambda lines: lines[-1]["byResult"].update({"no-series": False}),
        core.RULE_COUNTS,
    ),
]


@pytest.mark.parametrize(
    "change,rule", [case[1:] for case in STORED_CASES], ids=[c[0] for c in STORED_CASES]
)
def test_a_text_that_does_not_have_the_form_of_a_stream_is_refused(
    tmp_path: Path, change: Change, rule: str
) -> None:
    lines = _lines(tmp_path)
    assert lines[7]["query"] == "api-requests-by-outcome"
    telemetry.read_stream(telemetry.stream_text(lines))
    change(lines)
    with pytest.raises(telemetry.StreamRefused) as refused:
        telemetry.read_stream(telemetry.stream_text(lines))
    assert refused.value.rule == rule


@pytest.mark.parametrize(
    "text",
    ["", "not json\n", "[]\n", '{"record":"header","record":"header"}\n', "7\n"],
)
def test_a_text_that_is_not_lines_of_objects_is_refused(text: str) -> None:
    with pytest.raises(telemetry.StreamRefused) as refused:
        telemetry.read_stream(text)
    assert refused.value.rule in (core.RULE_UNREADABLE, core.RULE_HEADER)
    if text:
        assert refused.value.rule == core.RULE_UNREADABLE


def test_each_rule_has_a_case_that_refuses_by_it() -> None:
    covered = {rule for _, _, rule in STORED_CASES} | {core.RULE_UNREADABLE}
    assert covered == set(telemetry.RULES)
    assert len(telemetry.RULES) == 11
    for rule in telemetry.RULES:
        assert rule.startswith("telemetry-"), rule


def test_a_stored_stream_with_a_request_identifier_label_is_refused(
    tmp_path: Path,
) -> None:
    """The check holds a stored file to the registered labels, not only the builder."""
    lines = _lines(tmp_path)
    lines[7]["series"][0]["labels"]["inferops_request_id"] = "r-1"
    with pytest.raises(telemetry.StreamRefused) as refused:
        telemetry.read_stream(telemetry.stream_text(lines))
    assert refused.value.rule == core.RULE_LABEL
    assert "r-1" not in str(refused.value)


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_command_prints_the_registered_requests(
    capfdbinary: pytest.CaptureFixture[bytes],
) -> None:
    assert main(["requests"]) == 0
    assert capfdbinary.readouterr().out == telemetry.requests_text().encode("utf-8")


def test_the_command_prints_one_stream_in_lf_bytes(
    tmp_path: Path, capfdbinary: pytest.CaptureFixture[bytes]
) -> None:
    directory = collection(tmp_path)
    for name in telemetry.STREAMS:
        assert main(["stream", str(directory), name]) == 0
        printed = capfdbinary.readouterr().out
        built = telemetry.build_streams(directory)[name]
        assert printed == telemetry.stream_text(built).encode("utf-8")
        assert b"\r" not in printed


def test_the_command_refuses_a_directory_that_is_not_a_collection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["stream", str(tmp_path), "telemetry"]) == telemetry.REFUSED_EXIT == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "REFUSED  not-a-collection" in captured.err


def test_the_command_checks_stored_streams(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    built = telemetry.build_streams(collection(tmp_path))
    good = tmp_path / "telemetry.jsonl"
    good.write_bytes(telemetry.stream_text(built["telemetry"]).encode("utf-8"))
    bad = tmp_path / "resources.jsonl"
    bad.write_bytes(telemetry.stream_text(built["resources"][:-1]).encode("utf-8"))
    binary = tmp_path / "binary.jsonl"
    binary.write_bytes(b"\xff\xfe")
    assert main(["check", str(good)]) == 0
    assert capsys.readouterr().out == (
        "READ     telemetry: 8 reading(s): 8 answered; 8 with series, "
        "0 with no series\n"
    )
    assert main(["check", str(good), str(bad), str(binary), str(tmp_path / "x")]) == 3
    captured = capsys.readouterr()
    assert "READ     telemetry" in captured.out
    assert "REFUSED  resources.jsonl: telemetry-end-missing" in captured.err
    assert "REFUSED  binary.jsonl: telemetry-stream-unreadable" in captured.err
    assert "REFUSED  x: telemetry-stream-unreadable" in captured.err


@pytest.mark.parametrize(
    "arguments",
    [[], ["stream"], ["stream", "."], ["stream", ".", "pods"], ["check"], ["changes"]],
)
def test_arguments_that_are_not_usable_exit_2(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(arguments)
    assert stopped.value.code == 2


# --------------------------------------------------------------------------
# The evidence layout and the page
# --------------------------------------------------------------------------


def test_each_stream_is_a_registered_raw_role_with_a_hashed_suffix() -> None:
    """A run directory can name each stream file under a role of the same name."""
    for name in telemetry.STREAMS:
        assert ROLES[name].kind == RAW, name
        assert Path(telemetry.STREAM_FILES[name]).suffix in EVIDENCE_SUFFIXES


def _flat(text: str) -> str:
    return " ".join(text.replace("`", "").split())


def test_the_page_publishes_each_query_rule_limit_and_boundary_of_the_tool() -> None:
    page = _flat(PAGE.read_text(encoding="utf-8"))
    for rule, statement in telemetry.RULES.items():
        assert rule in page, rule
        assert _flat(statement) in page, rule
    for statement in (
        *telemetry.LIMITATIONS,
        *telemetry.DOES_NOT_ESTABLISH,
        *telemetry.OMITTED,
    ):
        assert _flat(statement) in page, statement
    for query in telemetry.QUERIES:
        assert query.name in page, query.name
        assert _flat(query.expression) in page, query.name
        assert _flat(query.states) in page, query.name
    for name in (
        *telemetry.STREAMS,
        *telemetry.READ_STATES,
        *telemetry.RESULTS,
        *telemetry.COLLECTOR_STATES,
        *telemetry.KINDS,
        *telemetry.FIELD_STATES,
        telemetry.QUERY_SET,
    ):
        assert re.search(
            rf"(?<![A-Za-z0-9-]){re.escape(name)}(?![A-Za-z0-9-])", page
        ), name
    for bound in (
        telemetry.MAX_SAMPLES,
        telemetry.MIN_INTERVAL_SECONDS,
        telemetry.MAX_INTERVAL_SECONDS,
        telemetry.MAX_SERIES,
    ):
        assert str(bound) in page, bound
