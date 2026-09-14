"""The dashboard's real-run validation: the capture tool, its readings, and the guide.

Four files have to agree with the dashboard record:

- `tools/inference_dashboard/live.py`, which asks a running Prometheus every panel
  expression and classifies each answer;
- `docs/proof/telemetry/v1-s4-002-pr2-panel-readings.v1alpha1.json`, what one real
  collector returned in nine controlled states;
- `docs/proof/telemetry/v1-s4-002-pr2-dashboard-validation.md`, the record that
  publishes those readings;
- `docs/telemetry/inference-operations-dashboard-operator-guide.md`, the thirty-second
  guide written from them.

The capture tool is tested against a local HTTP stub, never a real Prometheus. The
readings are checked for what they must be to support the published claims: every
panel expression in every state, a reading consistent with its rows, no barred label,
the pod name only where a panel is declared per replica, and counts that reconcile
with the traffic the record says was sent. **None of these tests contacts a cluster.**
Whether the readings are what a collector returned is established by the record's
method, not by this suite.
"""

from __future__ import annotations

import json
import math
import re
import threading
from collections.abc import Iterator, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import parse_qs

import pytest

from tools.inference_dashboard import load_dashboard_record, panel_queries
from tools.inference_dashboard.__main__ import main
from tools.inference_dashboard.live import (
    READINGS,
    CaptureFailed,
    capture,
    classify,
    http_query,
)
from tools.telemetry_correlation import (
    forbidden_metric_labels,
    not_emitted_metric_names,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORD = load_dashboard_record()
PANELS: dict[str, dict[str, Any]] = {
    panel["panelId"]: panel for panel in RECORD["panels"]
}
QUERY_IDS = [query["queryId"] for query in panel_queries(RECORD)]
READINGS_PATH = (
    REPO_ROOT / "docs/proof/telemetry/v1-s4-002-pr2-panel-readings.v1alpha1.json"
)
EVIDENCE = json.loads(READINGS_PATH.read_text(encoding="utf-8"))
STATES: dict[str, dict[str, Any]] = {
    state["stateId"]: state for state in EVIDENCE["states"]
}
VALIDATION = (REPO_ROOT / EVIDENCE["documentRef"]).read_text(encoding="utf-8")
GUIDE_PATH = REPO_ROOT / RECORD["operatorGuideRef"]
GUIDE = GUIDE_PATH.read_text(encoding="utf-8")

SINCE_START_COUNTS = (
    "requests-since-start/A",
    "errors-since-start/A",
    "readiness-checks-failed-since-start/A",
)


def _vector(*samples: tuple[dict[str, str], str]) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": labels, "value": [1789381000.0, value]}
                for labels, value in samples
            ],
        },
    }


def _only_value(state: str, query_id: str) -> float:
    rows = STATES[state]["readings"][query_id]["rows"]
    assert len(rows) == 1, (state, query_id, rows)
    return float(rows[0]["value"])


# --------------------------------------------------------------------------
# Classifying an answer
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("response", "reading"),
    [
        (_vector(), "empty"),
        (_vector(({}, "0"), ({"a": "b"}, "0")), "zero"),
        (_vector(({}, "0"), ({"a": "b"}, "3")), "value"),
        (_vector(({}, "NaN")), "nan"),
        (_vector(({}, "NaN"), ({"a": "b"}, "0")), "nan"),
        (_vector(({}, "NaN"), ({"a": "b"}, "0.5")), "value"),
        (_vector(({}, "0"), ({"a": "b"}, "+Inf")), "value"),
        (
            {"status": "success", "data": {"resultType": "scalar", "result": [1, "2"]}},
            "value",
        ),
    ],
)
def test_an_answer_is_classified_in_the_dashboards_terms(
    response: dict[str, Any], reading: str
) -> None:
    assert classify(response)["reading"] == reading


def test_an_idle_latency_window_is_not_mistaken_for_a_number() -> None:
    """NaN is not a finite non-zero value, and `float('nan') != 0` is true."""
    assert classify(_vector(({}, "NaN")))["reading"] == "nan"
    assert math.isnan(float(classify(_vector(({}, "NaN")))["rows"][0]["value"]))


def test_a_refused_query_keeps_prometheus_s_reason() -> None:
    result = classify(
        {"status": "error", "errorType": "bad_data", "error": "parse error at char 3"}
    )
    assert result == {
        "reading": "refused",
        "errorType": "bad_data",
        "error": "parse error at char 3",
        "rows": [],
    }


def test_an_unsupported_result_type_is_not_silently_empty() -> None:
    with pytest.raises(ValueError, match="matrix"):
        classify({"status": "success", "data": {"resultType": "matrix", "result": []}})


def test_rows_are_ordered_so_a_capture_diffs_cleanly() -> None:
    result = classify(_vector(({"b": "2", "a": "1"}, "1"), ({"a": "0"}, "1")))
    assert [row["labels"] for row in result["rows"]] == [
        {"a": "0"},
        {"a": "1", "b": "2"},
    ]
    assert list(result["rows"][1]["labels"]) == ["a", "b"]


def test_a_capture_asks_every_panel_expression_once_whatever_its_profile() -> None:
    asked: list[str] = []

    def ask(expression: str) -> Mapping[str, Any]:
        asked.append(expression)
        return _vector()

    readings = capture(RECORD, ask)
    assert list(readings) == QUERY_IDS
    assert sorted(asked) == sorted(query["expr"] for query in panel_queries(RECORD))
    assert all(entry["reading"] == "empty" for entry in readings.values())


# --------------------------------------------------------------------------
# Asking over HTTP, against a stub
# --------------------------------------------------------------------------


class _Stub(BaseHTTPRequestHandler):
    received: ClassVar[list[dict[str, list[str]]]] = []

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        form = parse_qs(self.rfile.read(length).decode("ascii"))
        type(self).received.append(form)
        query = form["query"][0]
        if query == "proxy page":
            self._send(502, b"<html>Bad Gateway</html>", "text/html")
            return
        if query == "redirect":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/api/v1/query")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if query == "not a query(":
            body, status = (
                {"status": "error", "errorType": "bad_data", "error": "x"},
                400,
            )
        else:
            body, status = _vector(({"k8s_component": "platform-api"}, "1")), 200
        self._send(status, json.dumps(body).encode("utf-8"), "application/json")

    def _send(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_: object) -> None:
        return


@pytest.fixture
def prometheus_stub() -> Iterator[str]:
    _Stub.received = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()


def test_http_query_pins_every_expression_to_one_instant(prometheus_stub: str) -> None:
    ask = http_query(prometheus_stub, at=1789381000.25)
    assert classify(ask("up"))["reading"] == "value"
    assert _Stub.received == [{"query": ["up"], "time": ["1789381000.250"]}]


def test_http_query_reads_a_400_as_a_refusal_rather_than_raising(
    prometheus_stub: str,
) -> None:
    assert classify(http_query(prometheus_stub)("not a query("))["reading"] == "refused"
    assert "time" not in _Stub.received[0]


def test_the_command_prints_one_reading_per_panel_expression(
    prometheus_stub: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--capture", prometheus_stub, "--at", "1789381000"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["at"] == 1789381000
    assert list(printed["readings"]) == QUERY_IDS
    assert {entry["time"][0] for entry in _Stub.received} == {"1789381000.000"}


def test_a_proxy_error_page_stops_the_capture_rather_than_becoming_a_reading(
    prometheus_stub: str,
) -> None:
    with pytest.raises(CaptureFailed, match="HTTP 502"):
        http_query(prometheus_stub)("proxy page")


def test_a_redirect_is_refused_rather_than_followed(prometheus_stub: str) -> None:
    with pytest.raises(CaptureFailed, match="HTTP 302"):
        http_query(prometheus_stub)("redirect")


def test_an_unreachable_collector_stops_the_capture() -> None:
    with pytest.raises(CaptureFailed, match="could not reach"):
        http_query("http://127.0.0.1:1")("up")


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "ftp://127.0.0.1/", "127.0.0.1:9090"]
)
def test_only_an_http_url_is_asked(url: str) -> None:
    with pytest.raises(CaptureFailed, match="use http or https"):
        http_query(url)


def test_the_command_reports_an_unreachable_collector_and_prints_no_readings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--capture", "http://127.0.0.1:1"]) == 1
    printed = capsys.readouterr()
    assert printed.out == ""
    assert "REFUSED  no capture" in printed.err


def test_the_command_refuses_an_empty_capture_url() -> None:
    with pytest.raises(SystemExit) as refused:
        main(["--capture", ""])
    assert refused.value.code == 2


def test_the_command_refuses_an_instant_without_a_capture() -> None:
    with pytest.raises(SystemExit) as refused:
        main(["--at", "1789381000"])
    assert refused.value.code == 2


# --------------------------------------------------------------------------
# The committed readings
# --------------------------------------------------------------------------


def test_the_readings_record_names_its_class_provider_and_references() -> None:
    assert EVIDENCE["contractVersion"] == "inferops.io/v1alpha1"
    assert EVIDENCE["evidenceClass"] == "local-real-cpu"
    assert EVIDENCE["provider"] == "docker-desktop"
    assert "none is a measurement" in EVIDENCE["statement"].lower()
    assert REPO_ROOT / EVIDENCE["dashboardRecordRef"] == REPO_ROOT / (
        "docs/telemetry/inference-operations-dashboard.v1alpha1.json"
    )
    for state in EVIDENCE["states"]:
        if state["screenshotRef"] is not None:
            shot = REPO_ROOT / state["screenshotRef"]
            assert shot.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", shot


def test_every_state_reads_every_panel_expression() -> None:
    assert len(STATES) == len(EVIDENCE["states"]) == 9
    for state_id, state in STATES.items():
        assert list(state["readings"]) == QUERY_IDS, state_id


def test_every_reading_agrees_with_the_rows_it_carries() -> None:
    for state_id, state in STATES.items():
        for query_id, entry in state["readings"].items():
            assert entry["reading"] in READINGS, (state_id, query_id)
            assert entry["reading"] != "refused", (state_id, query_id, entry)
            rebuilt = _vector(*((row["labels"], row["value"]) for row in entry["rows"]))
            assert classify(rebuilt) == entry, (state_id, query_id)


def test_no_reading_carries_a_barred_label() -> None:
    barred = forbidden_metric_labels()
    for state_id, state in STATES.items():
        for query_id, entry in state["readings"].items():
            for row in entry["rows"]:
                assert not barred & set(row["labels"]), (state_id, query_id, row)


def test_the_pod_name_appears_only_where_a_panel_is_declared_per_replica() -> None:
    for state_id, state in STATES.items():
        for query_id, entry in state["readings"].items():
            panel = PANELS[query_id.split("/")[0]]
            if any("instance" in row["labels"] for row in entry["rows"]):
                assert panel["perReplica"], (state_id, query_id)


def test_a_not_emitted_metric_read_nothing_in_any_state() -> None:
    silent = not_emitted_metric_names()
    for panel in RECORD["panels"]:
        if panel["signal"] != "not-emitted":
            continue
        for query in panel["queries"]:
            key = f"{panel['panelId']}/{query['refId']}"
            reads_silent = any(name in query["expr"] for name in silent)
            for state_id, state in STATES.items():
                entry = state["readings"][key]
                if reads_silent:
                    assert entry["reading"] == "empty", (state_id, key)
                else:
                    assert entry["reading"] == "value", (state_id, key)
                    assert [row["value"] for row in entry["rows"]] == ["1"]


def test_zero_and_missing_came_apart_on_the_real_collector() -> None:
    idle = STATES["idle"]["readings"]
    gone = STATES["api-scaled-to-zero"]["readings"]
    for key in ("requests-since-start/A", "errors-since-start/A"):
        assert idle[key]["reading"] == "zero", key
    for key in SINCE_START_COUNTS:
        assert gone[key]["reading"] == "empty", key
    assert idle["api-identity-not-published/A"]["reading"] == "empty"
    assert gone["api-identity-not-published/A"]["reading"] == "value"
    assert gone["scrape-jobs-that-discovered-no-pod/A"]["reading"] == "value"
    runtime_gone = STATES["serving-runtime-scaled-to-zero"]["readings"]
    assert runtime_gone["scrape-jobs-that-discovered-no-pod/B"]["reading"] == "value"
    assert runtime_gone["runtime-operating-identity/A"]["reading"] == "empty"


def test_the_counts_reconcile_with_the_traffic_the_record_says_was_sent() -> None:
    """A count that does not match what was sent is a panel, or a record, that lies."""
    sent = errors = 0
    reconciled = 0
    for state in EVIDENCE["states"]:
        for traffic in state["traffic"]:
            sent += traffic["requests"]
            errors += sum(
                count
                for status, count in traffic["byStatus"].items()
                if not status.startswith("200 ")
            )
        if state["stateId"] in (
            "traffic",
            "error",
            "serving-runtime-scaled-to-zero",
            "serving-runtime-restored",
        ):
            assert _only_value(state["stateId"], "requests-since-start/A") == sent
            assert _only_value(state["stateId"], "errors-since-start/A") == errors
            ratio = _only_value(state["stateId"], "unsuccessful-request-ratio/A")
            assert ratio == pytest.approx(errors / sent)
            reconciled += 1
    assert reconciled == 4


def test_the_rate_panels_missed_failures_the_counts_saw() -> None:
    """The finding the fixtures could not produce, kept so it cannot be edited away."""
    before = _only_value("error", "errors-since-start/A")
    after = _only_value("serving-runtime-scaled-to-zero", "errors-since-start/A")
    assert after - before == 10
    rows = STATES["serving-runtime-scaled-to-zero"]["readings"]["errors-by-code/A"][
        "rows"
    ]
    unavailable = [
        row
        for row in rows
        if row["labels"]["inferops_error_code"] == "capability-unavailable"
    ]
    assert [row["value"] for row in unavailable] == ["0"]


def test_the_in_flight_reading_matches_the_concurrency_sent() -> None:
    state = STATES["traffic-in-flight"]
    concurrency = max(traffic["concurrency"] for traffic in state["traffic"])
    assert _only_value("traffic-in-flight", "api-in-flight-by-replica/A") == concurrency


def test_a_replaced_api_process_is_counted_until_its_series_go_stale() -> None:
    readings = "api-processes-publishing-identity/A"
    assert _only_value("api-pod-replaced-transition", readings) == 2
    assert _only_value("api-pod-replaced-settled", readings) == 1
    for key in SINCE_START_COUNTS:
        assert STATES["api-pod-replaced-settled"]["readings"][key]["reading"] == "zero"


# --------------------------------------------------------------------------
# The validation record and the dashboard record
# --------------------------------------------------------------------------


def test_the_dashboard_record_claims_the_run_this_evidence_records() -> None:
    status = RECORD["verificationStatus"]
    assert (
        REPO_ROOT / RECORD["realRunEvidenceRef"] == REPO_ROOT / EVIDENCE["documentRef"]
    )
    assert status["importedIntoGrafana"] is True
    assert status["evaluatedByPrometheus"] is True
    assert status["evidenceClass"] == EVIDENCE["evidenceClass"]
    assert "docker-desktop" in status["note"]


def test_the_validation_record_publishes_the_counts_the_readings_have() -> None:
    flat = " ".join(VALIDATION.split())
    total = sum(len(state["readings"]) for state in EVIDENCE["states"])
    tally = {reading: 0 for reading in READINGS}
    for state in EVIDENCE["states"]:
        for entry in state["readings"].values():
            tally[entry["reading"]] += 1
    assert (
        f"nine states, {len(QUERY_IDS)} expressions in each, {total} readings" in flat
    )
    assert (
        f"Of {total} readings, {tally['value']} were a value, {tally['empty']} empty, "
        f"{tally['zero']} zero, and none NaN or refused." in flat
    )
    assert tally["nan"] == tally["refused"] == 0
    assert f"all {len(QUERY_IDS)}** panel expressions" in flat
    assert f"all {len(RECORD['panels'])} panels" in flat


def test_the_validation_record_lists_every_state_in_order_at_its_capture_time() -> None:
    table = VALIDATION.split("### The states, in order", 1)[1].split("\n\n**", 1)[0]
    listed = re.findall(
        r"^\| `([a-z0-9-]+)` \| (\d\d:\d\d:\d\d) \|", table, re.MULTILINE
    )
    assert listed == [
        (state["stateId"], state["capturedAt"][11:19]) for state in EVIDENCE["states"]
    ]


def _relative_links(document: str) -> list[str]:
    return [
        target
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", document)
        if "://" not in target
    ]


@pytest.mark.parametrize(
    "path",
    [
        REPO_ROOT / EVIDENCE["documentRef"],
        GUIDE_PATH,
    ],
    ids=["validation-record", "operator-guide"],
)
def test_every_relative_link_resolves(path: Path) -> None:
    for target in _relative_links(path.read_text(encoding="utf-8")):
        assert (path.parent / target).resolve().exists(), (path.name, target)


def test_no_committed_validation_file_carries_host_state() -> None:
    host_state = re.compile(
        r"\b[A-Za-z]:\\|(?<![A-Za-z])[A-Za-z]:/(?!/)|/Users/|/home/|AppData"
        r"|\.kube/config|kubeconfig:"
    )
    for text in (READINGS_PATH.read_text(encoding="utf-8"), VALIDATION, GUIDE):
        assert not host_state.search(text), host_state.search(text)


# --------------------------------------------------------------------------
# The operator guide
# --------------------------------------------------------------------------


def _guide_rows() -> dict[str, list[str]]:
    table = GUIDE.split("## Every panel:", 1)[1].split("\n## ", 1)[0]
    rows: dict[str, list[str]] = {}
    for line in table.splitlines():
        match = re.match(r"^\| `([a-z0-9-]+)` \|(.*)\|$", line)
        if match:
            assert match.group(1) not in rows, match.group(1)
            rows[match.group(1)] = [
                cell.strip() for cell in match.group(2).split(" | ")
            ]
    return rows


def test_the_guide_covers_every_panel_once_and_no_other() -> None:
    assert set(_guide_rows()) == set(PANELS)


def test_the_guide_names_an_unsafe_conclusion_for_every_panel() -> None:
    for panel_id, (answers, unsafe) in _guide_rows().items():
        assert answers, panel_id
        assert len(unsafe) > 20, panel_id


def test_the_guide_says_nothing_answers_a_panel_that_answers_nothing() -> None:
    for panel_id, (answers, _) in _guide_rows().items():
        silent = PANELS[panel_id]["signal"] in ("not-emitted", "not-answerable")
        assert answers.startswith("Nothing.") is silent, panel_id


def test_the_guide_links_every_committed_screenshot() -> None:
    for state in EVIDENCE["states"]:
        if state["screenshotRef"] is not None:
            assert Path(state["screenshotRef"]).name in GUIDE, state["stateId"]


def test_the_bucket_comparison_is_the_committed_one() -> None:
    """The first commit's comparison added durations nobody logged; this pins the logged."""
    flat = " ".join(VALIDATION.split())
    logged = [
        traffic
        for state in EVIDENCE["states"]
        for traffic in state["traffic"]
        if state["stateId"] in ("traffic-in-flight", "traffic")
        and traffic["clientSecondsAtOrUnder"] is not None
    ]
    count = sum(traffic["requests"] for traffic in logged)
    under = {
        le: sum(traffic["clientSecondsAtOrUnder"][le] for traffic in logged)
        for le in ("0.5", "1", "2.5")
    }
    assert f"Clients logged {count} durations" in flat
    assert f"`{under['0.5']}` at or under 0.5 s, `{under['1']}` at or under 1 s" in flat
    assert under["2.5"] == count
    reads = {entry["readId"]: entry for entry in EVIDENCE["directReads"]}
    collector = reads["request-duration-buckets-at-traffic"]
    assert collector["readAt"] == STATES["traffic"]["capturedAt"]
    assert (
        f"were `{collector['values']['0.5']}` and `{collector['values']['1']}`" in flat
    )
    assert collector["values"]["+Inf"] == str(
        int(_only_value("traffic", "requests-since-start/A"))
    )


def test_the_token_figures_are_committed_direct_reads() -> None:
    reads = {entry["readId"]: entry for entry in EVIDENCE["directReads"]}[
        "token-counters-after-traffic"
    ]["values"]
    api = reads["sum by (inferops_token_direction) (inferops_inference_tokens_total)"]
    sent = [traffic for state in EVIDENCE["states"][:3] for traffic in state["traffic"]]
    assert int(api["input"]) == sum(traffic["promptTokens"] for traffic in sent)
    assert int(api["output"]) == sum(traffic["completionTokens"] for traffic in sent)
    assert reads["llamacpp:tokens_predicted_total"] == api["output"]
    assert int(reads["llamacpp:prompt_tokens_total"]) + int(
        reads["llamacpp:prompt_tokens_cached_total"]
    ) == int(api["input"])
    for text in (VALIDATION, GUIDE):
        assert reads["llamacpp:prompt_tokens_cached_total"] in text
