"""The RP-1 reliability runner: its plan, its loop, its Job, and its caller record.

Nothing here sends a request to a model, and nothing here contacts a cluster. Each
request is answered by an injected transport function or by a loopback server inside
this process. No Job is applied. No latency here describes serving.

The suite does five things:

- **plan** -- it holds the plan against the RP-1 profile, and it gives the plan one
  unusable value at a time;
- **origin** -- it compares the classification and the transport of the runner file
  with the V1 load harness, case by case, because the runner file restates both and
  imports neither;
- **loop** -- it runs the loop against scripted answers: the two workers, the two
  bounds, the stop signal, the wait after a request that is not a success, and what
  each request sends;
- **record** -- it gives the record checker one defect at a time, and it requires the
  rule that names that defect;
- **Job and script** -- it reads the manifest and the script as data and as text. It
  does not apply the manifest, and it does not execute the script.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import http.server
import io
import json
import os
import re
import signal
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.llm_load import core as source_core
from tools.reliability_profile import BOUNDARY_STATEMENT, load_profile
from tools.reliability_runner import __main__ as cli
from tools.reliability_runner import core, incluster
from tools.reliability_runner.core import RULES, RunnerError

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE_PATH = REPO_ROOT / "docs/serving/reliability-runner.md"
SCRIPT_PATH = REPO_ROOT / "scripts/environment/reliability-runner.sh"
LIB_PATH = REPO_ROOT / "scripts/environment/lib.sh"
RENDER_PATH = REPO_ROOT / "charts/inferops-llm/ci/rendered/real.expected.yaml"
SAMPLE_PATH = REPO_ROOT / "docs/proof/serving/v2-s5-001-pr2-rehearsal-caller.jsonl"

PROFILE = load_profile()
SOURCE = source_core.load_profile()
PROMPT = PROFILE.request_body["messages"][0]["content"]
IMAGE = "localhost/inferops-api@sha256:" + "a" * 64
RELEASE_ID = "b" * 64


def plan(**changes: Any) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "experiment_id": "EXP-A",
        "run_id": "run-1",
        "duration_seconds": 60,
        "request_ceiling": 8,
        "release_id": RELEASE_ID,
    }
    arguments.update(changes)
    return core.build_plan(**arguments)


def completion(adapter: str = "real", **changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "COMPLETION-TEXT-MARKER"},
            }
        ],
        "usage": {"prompt_tokens": 30, "completion_tokens": 40},
        "x_inferops": {"adapterKind": adapter, "modelRef": "qwen3-1-7b-q8-0"},
    }
    body.update(changes)
    return body


ERROR_BODY: dict[str, Any] = {
    "code": "adapter-unavailable",
    "message": "ERROR-MESSAGE-MARKER",
    "details": {
        "adapterKind": "real",
        "modelRef": "qwen3-1-7b-q8-0",
        "conditionId": "runtime-unreachable",
    },
}


class Harness:
    """One run of the loop against scripted answers and a clock that a test moves."""

    def __init__(
        self,
        answers: Callable[[int], Any],
        *,
        step: float = 1.0,
        **changes: Any,
    ) -> None:
        self.plan = plan(**changes)
        self.text = core.plan_text(self.plan)
        self.calls: list[tuple[str, str, Any, dict[str, str], float]] = []
        self.sleeps: list[float] = []
        self.out = io.StringIO()
        self._answers = answers
        self._step = step
        self._lock = threading.Lock()
        self._now = 0.0
        self._ticks = 0
        self.run = incluster.Run(
            self.plan,
            out=self.out,
            runner_sha256=core.runner_digest(),
            plan_sha256=core.plan_digest(self.text),
            transport=self._transport,
            clock=self._clock,
            wall=self._wall,
            sleep=self._sleep,
        )

    def _transport(
        self,
        method: str,
        url: str,
        body: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> tuple[int, object | None]:
        with self._lock:
            self.calls.append((method, url, body, dict(headers), timeout_seconds))
            self._now += self._step
        sequence = int(headers["X-InferOps-Request-ID"].rsplit("-", 1)[1])
        answer = self._answers(sequence)
        if isinstance(answer, BaseException):
            raise answer
        status, body_out = answer
        return status, body_out

    def _clock(self) -> float:
        with self._lock:
            return self._now

    def _wall(self) -> datetime:
        with self._lock:
            self._ticks += 1
            return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(
                milliseconds=self._ticks
            )

    def _sleep(self, seconds: float) -> None:
        with self._lock:
            self.sleeps.append(seconds)

    def execute(self) -> int:
        return self.run.execute()

    @property
    def lines(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.out.getvalue().splitlines()]

    @property
    def requests(self) -> list[dict[str, Any]]:
        return sorted(
            (line for line in self.lines if line["record"] == "request"),
            key=lambda line: line["sequence"],
        )

    def record(self) -> core.CallerRecord:
        return core.read_record(self.out.getvalue(), plan=self.text)


def always(answer: Any) -> Callable[[int], Any]:
    return lambda _: answer


# --------------------------------------------------------------------------
# The plan
# --------------------------------------------------------------------------


def test_the_plan_sends_the_request_of_the_profile_and_no_argument_changes_it() -> None:
    document = plan()
    assert document["request"] == {
        "method": PROFILE.request_method,
        "path": PROFILE.request_path,
        "contentType": PROFILE.request_content_type,
        "requestIdHeader": PROFILE.request_id_header,
        "correlationIdHeader": PROFILE.correlation_id_header,
        "body": PROFILE.body(),
    }
    assert document["caller"] == {"concurrency": 2}
    assert document["timeouts"] == {"requestTimeoutMs": PROFILE.request_timeout_ms}
    assert document["success"] == {
        "requiredStatus": PROFILE.required_status,
        "requiredAdapterKind": PROFILE.required_adapter_kind,
        "requiredModelRef": PROFILE.required_model_ref,
        "requireUsage": PROFILE.require_usage,
        "requireChoice": True,
    }
    assert document["profile"] == {
        "profileId": "RP-1",
        "profileRevision": PROFILE.profile_revision,
        "profileSha256": PROFILE.profile_sha256,
    }
    assert document["boundary"] == BOUNDARY_STATEMENT
    # The builder takes no argument for the request, the workers, the deadline, or
    # the success rule.
    assert set(core.build_plan.__kwdefaults__ or {}) | {
        "experiment_id",
        "run_id",
        "duration_seconds",
    } == {
        "experiment_id",
        "run_id",
        "duration_seconds",
        "request_ceiling",
        "release_id",
        "service",
        "namespace",
        "port",
        "mode",
        "profile",
    }


def test_the_plan_targets_the_api_service_by_its_cluster_dns_name() -> None:
    assert plan()["target"] == {
        "kind": "api-service",
        "service": "inferops-inferops-llm",
        "namespace": "inferops-release",
        "port": 8090,
        "baseUrl": "http://inferops-inferops-llm.inferops-release.svc:8090",
    }


def test_the_service_name_and_port_are_those_of_the_committed_render() -> None:
    services = [
        document
        for document in yaml.safe_load_all(RENDER_PATH.read_text(encoding="utf-8"))
        if document
        and document["kind"] == "Service"
        and document["metadata"]["labels"]["app.kubernetes.io/component"]
        == "platform-api"
    ]
    assert len(services) == 1
    assert services[0]["metadata"]["name"] == core.API_SERVICE
    assert [port["port"] for port in services[0]["spec"]["ports"]] == [
        core.API_SERVICE_PORT
    ]
    assert services[0]["spec"]["type"] == "ClusterIP"
    assert f'readonly INFEROPS_RELEASE_NAMESPACE="{core.RELEASE_NAMESPACE}"' in (
        LIB_PATH.read_text(encoding="utf-8")
    )


def test_a_release_identifier_is_declared_or_stated_as_not_declared() -> None:
    assert plan()["release"] == {"releaseId": RELEASE_ID, "source": "declared"}
    assert plan(release_id=None)["release"] == {
        "releaseId": None,
        "source": "not-declared",
    }


@pytest.mark.parametrize(
    ("changes", "rule"),
    [
        ({"run_id": "Run-1"}, core.RULE_IDENTIFIER),
        ({"run_id": "run_1"}, core.RULE_IDENTIFIER),
        ({"run_id": "-run"}, core.RULE_IDENTIFIER),
        ({"run_id": "r" * 41}, core.RULE_IDENTIFIER),
        ({"run_id": "run-1\n"}, core.RULE_IDENTIFIER),
        ({"experiment_id": "EXP A"}, core.RULE_IDENTIFIER),
        ({"experiment_id": "e" * 64}, core.RULE_IDENTIFIER),
        ({"experiment_id": ""}, core.RULE_IDENTIFIER),
        ({"duration_seconds": 0}, core.RULE_PLAN),
        ({"duration_seconds": 3601}, core.RULE_PLAN),
        ({"duration_seconds": True}, core.RULE_PLAN),
        ({"duration_seconds": 60.0}, core.RULE_PLAN),
        ({"request_ceiling": 0}, core.RULE_PLAN),
        ({"request_ceiling": 10_001}, core.RULE_PLAN),
        ({"release_id": "b5457f49"}, core.RULE_PLAN),
        ({"release_id": "B" * 64}, core.RULE_PLAN),
        ({"port": 0}, core.RULE_PLAN),
        ({"port": 65536}, core.RULE_PLAN),
        ({"service": "127.0.0.1"}, core.RULE_PLAN),
        ({"service": "10-1-2-3.inferops-release.pod"}, core.RULE_PLAN),
        ({"service": "api-0.inferops-inferops-llm"}, core.RULE_PLAN),
        ({"service": "localhost:8090/x"}, core.RULE_PLAN),
        ({"service": "Inferops"}, core.RULE_PLAN),
        ({"namespace": "inferops-release.svc.cluster.local"}, core.RULE_PLAN),
        ({"mode": "host"}, core.RULE_PLAN),
    ],
)
def test_a_plan_with_one_unusable_value_is_refused(
    changes: dict[str, Any], rule: str
) -> None:
    with pytest.raises(RunnerError) as refused:
        plan(**changes)
    assert refused.value.rule == rule


@pytest.mark.parametrize(
    "base_url",
    [
        "http://127.0.0.1:8090",
        "http://localhost:8090",
        "http://10.1.2.3:8090",
        "https://inferops-inferops-llm.inferops-release.svc:8090",
        "http://inferops-inferops-llm.inferops-release.svc:8091",
        "http://inferops-inferops-llm.inferops-release.svc.cluster.local:8090",
        "http://inferops-inferops-llm.inferops-release.svc:8090/",
        "http://user@inferops-inferops-llm.inferops-release.svc:8090",
    ],
)
def test_the_runner_refuses_a_base_url_that_is_not_the_service_it_names(
    base_url: str,
) -> None:
    document = plan()
    document["target"]["baseUrl"] = base_url
    with pytest.raises(incluster.PlanRefused):
        incluster.check_plan(document)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(extra=1),
        lambda d: d.pop("bounds"),
        lambda d: d["request"].update(method="GET"),
        lambda d: d["request"].update(path="v1/chat/completions"),
        lambda d: d["request"].update(body=[]),
        lambda d: d["request"].update(readinessPath="/health/ready"),
        lambda d: d["caller"].update(concurrency=9),
        lambda d: d["caller"].update(concurrency=0),
        lambda d: d["timeouts"].update(requestTimeoutMs=300_001),
        lambda d: d["success"].update(requireChoice=False),
        lambda d: d["success"].update(requiredAdapterKind="Real Adapter"),
        lambda d: d["bounds"].update(pauseAfterNonSuccessMs=-1),
        lambda d: d["bounds"].update(pauseAfterNonSuccessMs=10_001),
        lambda d: d["release"].update(source="observed"),
        lambda d: d["release"].update(releaseId=None),
        lambda d: d["target"].update(kind="pod"),
        lambda d: d.update(schemaVersion="inferops.io/v1"),
        lambda d: d.update(boundary=""),
        lambda d: d["answerMembers"].update(extension=""),
    ],
)
def test_the_runner_refuses_a_plan_with_one_unsupported_member(
    mutate: Callable[[dict[str, Any]], Any],
) -> None:
    document = plan()
    incluster.check_plan(copy.deepcopy(document))
    mutate(document)
    with pytest.raises(incluster.PlanRefused):
        incluster.check_plan(document)


def test_the_text_of_a_plan_is_one_text_with_lf() -> None:
    first = core.plan_text(plan())
    assert first == core.plan_text(json.loads(first))
    assert "\r" not in first and first.endswith("}\n")
    assert core.plan_digest(first) == core.plan_digest(first.replace("\n", "\r\n"))


# --------------------------------------------------------------------------
# Origin: the classification and the transport are those of the V1 harness
# --------------------------------------------------------------------------

BODIES: list[object | None] = [
    None,
    [],
    "text",
    {},
    completion(),
    completion("mock"),
    completion("REAL"),
    completion(choices=[]),
    completion(choices=None),
    completion(choices=["text"]),
    completion(usage=None),
    completion(usage={"prompt_tokens": 1}),
    completion(usage={"prompt_tokens": True, "completion_tokens": 1}),
    completion(usage={"prompt_tokens": -1, "completion_tokens": 1}),
    completion(x_inferops={"adapterKind": "real", "modelRef": "another-model"}),
    completion(x_inferops={"adapterKind": "real"}),
    completion(x_inferops={"modelRef": "qwen3-1-7b-q8-0"}),
    completion(x_inferops="text"),
    completion(choices=[{"finish_reason": "A Reason With Spaces"}]),
    completion(choices=[{}]),
    ERROR_BODY,
    {**ERROR_BODY, "code": "Not A Token"},
    {**ERROR_BODY, "code": 7},
    {**ERROR_BODY, "details": {"conditionId": "x" * 65}},
    {**ERROR_BODY, "details": "text"},
    {"code": "internal-error"},
    {"details": {"adapterKind": "mock"}},
    # An extension and details in one body: the extension is read.
    completion("real", details={"adapterKind": "mock"}),
]
#: Each answer case: a status, a body, and a latency. And the two cases with no
#: answer, once each: the classification reads no status and no body of them.
ANSWER_CASES = [
    (None, status, body, latency)
    for status in (200, 503, 404)
    for body in BODIES
    for latency in (1, PROFILE.request_timeout_ms, PROFILE.request_timeout_ms + 1)
]
CASES = [*ANSWER_CASES, ("timeout", 0, None, 1), ("transport-error", 0, None, 1)]


@pytest.mark.parametrize("require_usage", [True, False])
def test_the_runner_classifies_each_case_as_the_v1_harness_does(
    require_usage: bool,
) -> None:
    document = plan()
    document["success"]["requireUsage"] = require_usage
    source = replace(SOURCE, require_usage=require_usage)
    outcomes = set()
    for failure, status, body, latency in CASES:
        expected = source_core.classify(
            source,
            answer=None if failure else source_core.HttpAnswer(status, body),
            failure=failure,
            latency_ms=latency,
        )
        result = incluster.classify(
            document,
            status=None if failure else status,
            body=body,
            failure=failure,
            latency_ms=latency,
        )
        case = (failure, status, body, latency)
        # The V1 record writes status 0 for a request with no answer. This record
        # writes null.
        assert result == {
            "outcome": expected.outcome,
            "httpStatus": expected.status or None,
            "errorCode": expected.error_code,
            "errorCondition": expected.error_condition,
            "finishReason": expected.finish_reason,
            "inputTokens": expected.input_tokens,
            "outputTokens": expected.output_tokens,
            "adapterKind": expected.adapter_kind,
            "modelRef": expected.model_ref,
        }, case
        outcomes.add(expected.outcome)
    assert len(BODIES) == 28
    assert len(ANSWER_CASES) == 3 * 28 * 3 == 252
    assert len(CASES) == 254
    assert outcomes == set(source_core.OUTCOMES) == set(incluster.OUTCOMES)
    assert incluster.OUTCOMES == source_core.OUTCOMES


def test_the_transport_differs_from_the_v1_transport_in_one_parse_case() -> None:
    # A number of too many digits is not a decode error. The V1 parser raises on
    # it. The parser of the runner file returns no parsed body.
    data = b"1" * 5000
    assert incluster._parse_body(data) is None
    with pytest.raises(ValueError):
        source_core._parse_body(data)
    for same in (b"{}", b"not json", b"\xff", b'{"a": [1, 2]}'):
        assert incluster._parse_body(same) == source_core._parse_body(same)


def test_the_runner_restates_the_limits_of_the_v1_harness() -> None:
    assert incluster.MAXIMUM_RESPONSE_BYTES == source_core.MAXIMUM_RESPONSE_BYTES
    assert incluster.SAFE_TOKEN.pattern == source_core.SAFE_TOKEN.pattern
    assert incluster.UNRECOGNIZED == source_core.UNRECOGNIZED
    assert incluster.MAXIMUM_CONCURRENCY == source_core.MAXIMUM_CONCURRENCY
    assert (
        incluster.MAXIMUM_REQUEST_TIMEOUT_MS == source_core.MAXIMUM_REQUEST_TIMEOUT_MS
    )
    assert incluster.MAXIMUM_DURATION_SECONDS == source_core.MAXIMUM_RUN_SECONDS


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        server: Any = self.server
        length = int(self.headers.get("Content-Length", "0"))
        server.requests.append(
            {
                "path": self.path,
                "connection": self.headers.get("Connection"),
                "contentType": self.headers.get("Content-Type"),
                "requestId": self.headers.get("X-InferOps-Request-ID"),
                "correlationId": self.headers.get("X-InferOps-Correlation-ID"),
                "body": json.loads(self.rfile.read(length)),
            }
        )
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/ok")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/slow":
            server.release.wait(10)
        status = 503 if self.path == "/busy" else 200
        payload = {
            "/busy": json.dumps(ERROR_BODY).encode(),
            "/text": b"not json",
            "/large": b'"' + b"a" * incluster.MAXIMUM_RESPONSE_BYTES + b'"',
        }.get(self.path, json.dumps(completion()).encode())
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        return


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.requests: list[dict[str, Any]] = []
        self.release = threading.Event()

    def url(self, path: str = "") -> str:
        return f"http://127.0.0.1:{self.server_address[1]}{path}"


@pytest.fixture
def loopback() -> Iterator[_Server]:
    server = _Server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("path", ["/ok", "/busy", "/text", "/large", "/redirect"])
def test_the_runner_transport_returns_what_the_v1_transport_returns(
    loopback: _Server, path: str
) -> None:
    headers = {"Content-Type": "application/json"}
    status, body = incluster.http_transport(
        "POST", loopback.url(path), {"a": 1}, headers, 5
    )
    expected = source_core.http_transport("POST", loopback.url(path), {"a": 1}, {}, 5)
    assert (status, body) == (expected.status, expected.body)
    first, second = loopback.requests
    # One request each, on a new connection, as JSON, and no request to /ok after
    # the redirect.
    assert first == second
    assert first["path"] == path
    assert first["connection"] == "close"
    assert first["contentType"] == "application/json"
    assert first["body"] == {"a": 1}


def test_the_runner_transport_raises_a_timeout_and_a_failure_as_the_v1_does(
    loopback: _Server,
) -> None:
    with pytest.raises(incluster.TransportTimeout):
        incluster.http_transport("POST", loopback.url("/slow"), {}, {}, 0.3)
    with pytest.raises(source_core.TransportTimeout):
        source_core.http_transport("POST", loopback.url("/slow"), {}, {}, 0.3)
    loopback.release.set()
    closed = _Server()
    address = closed.url("/ok")
    closed.server_close()
    with pytest.raises((incluster.TransportFailure, incluster.TransportTimeout)):
        incluster.http_transport("POST", address, {}, {}, 5)


def test_the_runner_transport_reads_no_proxy_variable(loopback: _Server) -> None:
    # The opener is built when the file is imported, so each request here is sent by
    # a new interpreter that starts with the variable set. The first interpreter is
    # the control: the default opener reads the variable, and its request does not
    # arrive.
    proxied = {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
    environment = {
        name: value for name, value in os.environ.items() if name.lower() not in proxied
    }
    environment["HTTP_PROXY"] = "http://127.0.0.1:9"
    environment["ALL_PROXY"] = "http://127.0.0.1:9"

    def child(script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-c", script, loopback.url("/ok")],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    control = child(
        "import sys, urllib.request\n"
        "request = urllib.request.Request(sys.argv[1], data=b'{}', method='POST')\n"
        "print(urllib.request.build_opener().open(request, timeout=20).status)\n"
    )
    assert control.returncode != 0
    assert loopback.requests == []
    sent = child(
        "import sys\n"
        "from tools.reliability_runner import incluster\n"
        "print(incluster.http_transport('POST', sys.argv[1], {'a': 1}, {}, 20)[0])\n"
    )
    assert sent.stdout.strip() == "200", sent.stderr
    assert [request["path"] for request in loopback.requests] == ["/ok"]


def test_a_run_over_loopback_http_sends_what_the_v1_harness_sends(
    loopback: _Server,
) -> None:
    # The plan names the Service. The transport of this test sends each request to
    # the loopback server in its place, and changes nothing else.
    base = plan()["target"]["baseUrl"]

    def transport(
        method: str, url: str, body: Mapping[str, Any], headers: Any, timeout: float
    ) -> tuple[int, object | None]:
        assert url.startswith(base)
        return incluster.http_transport(
            method, loopback.url() + url[len(base) :], body, headers, timeout
        )

    out = io.StringIO()
    document = plan(request_ceiling=3)
    text = core.plan_text(document)
    status = incluster.Run(
        document,
        out=out,
        runner_sha256=core.runner_digest(),
        plan_sha256=core.plan_digest(text),
        transport=transport,
    ).execute()
    assert status == 0
    record = core.read_record(out.getvalue(), plan=text)
    assert [request["outcome"] for request in record.requests] == ["success"] * 3
    assert sorted(request["requestId"] for request in loopback.requests) == [
        "run-1-00001",
        "run-1-00002",
        "run-1-00003",
    ]
    for request in loopback.requests:
        assert request["path"] == SOURCE.fixture.request_path
        assert request["body"] == SOURCE.fixture.body()
        assert request["correlationId"] == "run-1"
        assert request["contentType"] == "application/json"
        assert request["connection"] == "close"

    sent: list[Mapping[str, str]] = []

    def keep(*arguments: Any) -> source_core.HttpAnswer:
        sent.append(arguments[3])
        return source_core.HttpAnswer(200, None)

    source_core.send_one(
        SOURCE,
        "http://127.0.0.1:1",
        run_id="run-1",
        sequence=1,
        phase=source_core.PHASE_MEASURED,
        level_id="c2",
        concurrency=2,
        worker=0,
        dispatch_offset_ms=0,
        transport=keep,
        clock=lambda: 0.0,
    )
    # The same request identifier form and the same correlation identifier.
    assert sent[0][PROFILE.request_id_header] == "run-1-00001"
    assert sent[0][PROFILE.correlation_id_header] == "run-1"


# --------------------------------------------------------------------------
# The loop
# --------------------------------------------------------------------------


def test_each_request_is_one_post_of_the_profile_to_the_service() -> None:
    harness = Harness(always((200, completion())))
    assert harness.execute() == 0
    assert len(harness.calls) == 8
    for method, url, body, headers, timeout in harness.calls:
        assert method == "POST"
        assert url == (
            "http://inferops-inferops-llm.inferops-release.svc:8090/v1/chat/completions"
        )
        assert body == PROFILE.body()
        assert set(headers) == {
            "Content-Type",
            "X-InferOps-Request-ID",
            "X-InferOps-Correlation-ID",
        }
        assert headers["X-InferOps-Correlation-ID"] == "run-1"
        assert timeout == PROFILE.request_timeout_ms / 1000
    assert sorted(call[3]["X-InferOps-Request-ID"] for call in harness.calls) == [
        f"run-1-{number:05d}" for number in range(1, 9)
    ]


def test_the_first_call_of_a_run_is_a_request_and_not_a_probe() -> None:
    # The target answers nothing at first. The run sends the request anyway, and
    # it records what came back. It reads no readiness answer and no model list.
    harness = Harness(
        lambda sequence: (
            incluster.TransportFailure() if sequence <= 4 else (200, completion())
        )
    )
    assert harness.execute() == 0
    assert {call[1].rsplit("/", 1)[1] for call in harness.calls} == {"completions"}
    assert [request["outcome"] for request in harness.requests] == [
        "transport-error"
    ] * 4 + ["success"] * 4
    assert harness.requests[0]["sequence"] == 1


def test_two_workers_send_and_two_requests_are_in_flight_at_one_time() -> None:
    barrier = threading.Barrier(2, timeout=10)

    def answer(sequence: int) -> Any:
        if sequence <= 2:
            barrier.wait()
        return (200, completion())

    harness = Harness(answer)
    assert harness.execute() == 0
    assert not barrier.broken
    assert {request["worker"] for request in harness.requests} == {0, 1}
    assert harness.lines[0]["concurrency"] == 2


def test_a_run_ends_at_its_request_ceiling() -> None:
    harness = Harness(always((200, completion())), request_ceiling=5)
    assert harness.execute() == 0
    end = harness.lines[-1]
    assert end["endState"] == "request-ceiling"
    assert end["dispatched"] == end["recorded"] == 5 == len(harness.calls)


def test_a_run_ends_at_its_duration_and_a_request_in_flight_is_recorded() -> None:
    # Each call moves the clock 25 seconds. The duration is 60 seconds.
    harness = Harness(
        always((200, completion())),
        step=25.0,
        request_ceiling=1000,
        duration_seconds=60,
    )
    assert harness.execute() == 0
    end = harness.lines[-1]
    assert end["endState"] == "duration"
    assert 3 <= end["dispatched"] <= 4
    assert end["recorded"] == end["dispatched"] == len(harness.calls)
    harness.record()


def test_a_stop_request_ends_a_run_and_the_request_in_flight_is_recorded() -> None:
    # The test calls `stop`, which is what the signal handler calls. No signal is
    # delivered to a process here.
    harness: Harness

    def answer(sequence: int) -> Any:
        if sequence == 3:
            harness.run.stop()
        return (200, completion())

    harness = Harness(answer, request_ceiling=1000)
    assert harness.execute() == incluster.EXIT_INTERRUPTED
    end = harness.lines[-1]
    assert end["endState"] == "interrupted"
    # The other worker can dispatch while the third request is in flight, so the
    # count is not fixed. It is far below the ceiling.
    assert 3 <= end["dispatched"] < 1000
    assert end["recorded"] == end["dispatched"]
    assert 3 in [request["sequence"] for request in harness.requests]
    harness.record()


def test_a_run_in_which_each_request_fails_exits_0() -> None:
    harness = Harness(always((503, ERROR_BODY)))
    assert harness.execute() == incluster.EXIT_OK
    assert harness.lines[-1]["outcomes"]["http-error"] == 8
    assert harness.lines[-1]["outcomes"]["success"] == 0
    assert all(request["success"] is False for request in harness.requests)


@pytest.mark.parametrize(
    ("answer", "outcome"),
    [
        ((503, ERROR_BODY), "http-error"),
        ((200, completion(choices=[])), "invalid-response"),
        ((200, completion("mock")), "identity-refused"),
        (incluster.TransportFailure(), "transport-error"),
        (incluster.TransportTimeout(), "timeout"),
    ],
)
def test_a_worker_waits_after_a_request_that_is_not_a_success(
    answer: Any, outcome: str
) -> None:
    harness = Harness(always(answer), request_ceiling=4)
    assert harness.execute() == 0
    assert {request["outcome"] for request in harness.requests} == {outcome}
    # A wait occurs. Its length is held by the next test: a worker that reaches
    # the ceiling ends the wait of the other worker early.
    assert harness.sleeps and max(harness.sleeps) <= incluster.POLL_SECONDS
    assert len(harness.calls) == 4


def test_the_wait_is_one_second_in_steps_and_a_stop_request_ends_it() -> None:
    harness = Harness(always((200, completion())))
    assert harness.plan["bounds"]["pauseAfterNonSuccessMs"] == 1000
    assert core.PAUSE_AFTER_NON_SUCCESS_MS == 1000
    harness.run._pause(1.0)
    assert sum(harness.sleeps) == pytest.approx(1.0)
    assert len(harness.sleeps) == 10
    harness.run.stop()
    harness.run._pause(1.0)
    assert len(harness.sleeps) == 10


def test_a_worker_that_fails_gives_the_end_state_failed_and_exit_4() -> None:
    # The fourth request raises an error that no outcome names. The other worker
    # can reach the ceiling first: the failure still decides the end state.
    def answer(sequence: int) -> Any:
        if sequence == 4:
            return ValueError("FAILURE-MESSAGE-MARKER")
        return (200, completion())

    harness = Harness(answer, request_ceiling=4)
    assert harness.execute() == incluster.EXIT_FAILED == 4
    end = harness.lines[-1]
    assert end["endState"] == "failed"
    assert (end["dispatched"], end["recorded"]) == (4, 3)
    assert "FAILURE-MESSAGE-MARKER" not in harness.out.getvalue()
    with pytest.raises(RunnerError) as refused:
        harness.record()
    assert refused.value.rule in (core.RULE_SEQUENCE, core.RULE_COUNTS)


def test_a_worker_does_not_wait_after_a_success_and_no_outcome_ends_a_run() -> None:
    harness = Harness(always((200, completion())))
    harness.execute()
    assert harness.sleeps == []
    # The V1 harness ends a run on an answer of another adapter and after five
    # transport errors in a row. This runner ends at its bounds only.
    for answer in ((200, completion("mock")), incluster.TransportFailure()):
        harness = Harness(always(answer), request_ceiling=12)
        assert harness.execute() == 0
        assert harness.lines[-1]["endState"] == "request-ceiling"
        assert harness.lines[-1]["dispatched"] == 12
    assert source_core.MAXIMUM_CONSECUTIVE_TRANSPORT_ERRORS < 12


def test_a_caller_record_holds_no_prompt_no_completion_and_no_error_message() -> None:
    answers = [(200, completion()), (503, ERROR_BODY), (200, completion("mock"))]
    harness = Harness(lambda sequence: answers[sequence % 3])
    harness.execute()
    text = harness.out.getvalue()
    assert PROMPT not in text
    assert "COMPLETION-TEXT-MARKER" not in text
    assert "ERROR-MESSAGE-MARKER" not in text
    assert "messages" not in text
    header = harness.lines[0]
    assert header["promptText"] is False and header["completionText"] is False
    assert "request" not in header and "answerMembers" not in header


def test_a_request_line_states_the_identities_the_times_and_the_outcome() -> None:
    harness = Harness(
        lambda sequence: (200, completion()) if sequence % 2 else (503, ERROR_BODY),
        step=0.25,
        request_ceiling=2,
    )
    harness.execute()
    first, second = harness.requests
    assert set(first) == set(core._REQUEST_MEMBERS)
    assert {
        name: first[name]
        for name in (
            "requestId",
            "experimentId",
            "runId",
            "releaseId",
            "httpStatus",
            "success",
            "outcome",
            "errorCode",
            "errorCondition",
            "inputTokens",
            "outputTokens",
            "finishReason",
            "adapterKind",
            "modelRef",
        )
    } == {
        "requestId": "run-1-00001",
        "experimentId": "EXP-A",
        "runId": "run-1",
        "releaseId": RELEASE_ID,
        "httpStatus": 200,
        "success": True,
        "outcome": "success",
        "errorCode": None,
        "errorCondition": None,
        "inputTokens": 30,
        "outputTokens": 40,
        "finishReason": "stop",
        "adapterKind": "real",
        "modelRef": "qwen3-1-7b-q8-0",
    }
    assert (second["httpStatus"], second["success"], second["errorCode"]) == (
        503,
        False,
        "adapter-unavailable",
    )
    assert second["errorCondition"] == "runtime-unreachable"
    assert second["inputTokens"] is None and second["finishReason"] is None
    for request in (first, second):
        assert core.TIME.fullmatch(request["startedAt"])
        assert core.TIME.fullmatch(request["finishedAt"])
        assert request["startedAt"] < request["finishedAt"]
        assert request["latencyMs"] >= 250


def test_a_request_with_no_answer_has_a_null_status_and_not_zero() -> None:
    harness = Harness(always(incluster.TransportFailure()), request_ceiling=1)
    harness.execute()
    assert harness.requests[0]["httpStatus"] is None
    assert harness.requests[0]["success"] is False


def test_the_utc_text_is_to_one_millisecond() -> None:
    moment = datetime(2026, 3, 4, 5, 6, 7, 89_999, tzinfo=UTC)
    assert incluster.utc_text(moment) == "2026-03-04T05:06:07.089Z"
    other = moment.astimezone(tz=None)
    assert incluster.utc_text(other) == "2026-03-04T05:06:07.089Z"


# --------------------------------------------------------------------------
# The entry point of the runner file
# --------------------------------------------------------------------------

#: The modules of the standard library that the runner file imports. A pod holds an
#: interpreter and this file, so an import of another module fails in the pod.
RUNNER_IMPORTS = {
    "__future__",
    "collections.abc",
    "datetime",
    "hashlib",
    "http.client",
    "json",
    "re",
    "signal",
    "sys",
    "threading",
    "time",
    "typing",
    "urllib.error",
    "urllib.request",
}


def test_the_runner_file_imports_the_standard_library_only() -> None:
    tree = ast.parse(core.runner_source())
    imported: set[str | None] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            imported.add(node.module)
    assert imported == RUNNER_IMPORTS
    assert imported - {"__future__"} <= set(sys.stdlib_module_names) | {
        "collections.abc",
        "http.client",
        "urllib.error",
        "urllib.request",
    }


def test_the_runner_file_names_no_platform_signal() -> None:
    code = "\n".join(
        line
        for line in core.runner_source().splitlines()
        if not line.lstrip().startswith("#")
    )
    code = re.sub(r'""".*?"""', "", code, flags=re.DOTALL)
    for word in (
        "kubectl",
        "subprocess",
        "/health",
        "/v1/models",
        "KUBERNETES_SERVICE",
        "serviceaccount",
        "os.environ",
        "socket",
        "GET",
    ):
        assert word not in code, word


def isolated(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", *arguments],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_the_runner_file_runs_alone_and_refuses_a_plan_it_does_not_execute(
    tmp_path: Path,
) -> None:
    # A copy outside the repository, started in isolated mode, as a pod starts it.
    runner = tmp_path / "incluster.py"
    runner.write_text(core.runner_source(), encoding="utf-8", newline="\n")
    cases = {
        "rehearsal": core.plan_text(plan(mode="rehearsal")),
        "loopback": core.plan_text(plan()).replace(
            "http://inferops-inferops-llm.inferops-release.svc:8090",
            "http://127.0.0.1:8090",
        ),
        "not-json": "{",
        "list": "[]",
    }
    for name, text in cases.items():
        path = tmp_path / f"{name}.json"
        path.write_text(text, encoding="utf-8", newline="\n")
        result = isolated(str(runner), str(path))
        assert result.returncode == incluster.EXIT_REFUSED, (name, result.stderr)
        assert result.stdout == ""
        assert result.stderr.startswith("REFUSED  ")
        assert "Traceback" not in result.stderr
    assert isolated(str(runner)).returncode == incluster.EXIT_REFUSED
    assert isolated(str(runner), str(tmp_path / "absent.json")).returncode == 3


def test_the_entry_point_states_the_digest_of_the_file_and_of_the_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    text = core.plan_text(plan(request_ceiling=2))
    path = tmp_path / "plan.json"
    path.write_text(text, encoding="utf-8", newline="\n")
    handlers: dict[int, Any] = {}
    monkeypatch.setattr(
        signal, "signal", lambda number, handler: handlers.update({number: handler})
    )
    monkeypatch.setattr(
        incluster, "http_transport", lambda *arguments: (200, completion())
    )
    assert incluster.main([str(path)]) == incluster.EXIT_OK
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [line["record"] for line in lines] == ["header", "request", "request", "end"]
    assert lines[0]["planSha256"] == core.plan_digest(text)
    assert (
        lines[0]["runnerSha256"]
        == hashlib.sha256(Path(incluster.__file__).read_bytes()).hexdigest()
    )
    # The two handlers are registered. No signal is delivered to a process here.
    assert set(handlers) == {signal.SIGTERM, signal.SIGINT}


# --------------------------------------------------------------------------
# The caller record
# --------------------------------------------------------------------------


def good() -> tuple[str, list[dict[str, Any]]]:
    answers = [(200, completion()), (503, ERROR_BODY), incluster.TransportFailure()]
    harness = Harness(lambda sequence: answers[sequence % 3], request_ceiling=6)
    harness.execute()
    harness.record()
    return harness.text, harness.lines


def text_of(lines: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(line, sort_keys=True) + "\n" for line in lines)


def request_line(lines: list[dict[str, Any]], outcome: str) -> dict[str, Any]:
    return next(
        line
        for line in lines
        if line["record"] == "request" and line["outcome"] == outcome
    )


Defect = Callable[[list[dict[str, Any]]], Any]


def header_of_another_service(lines: list[dict[str, Any]]) -> None:
    lines[0]["target"].update(
        service="another", baseUrl="http://another.inferops-release.svc:8090"
    )


DEFECTS: list[tuple[str, str, Defect]] = [
    ("a header of another Service", core.RULE_MEMBERS, header_of_another_service),
    (
        "a latency of very many digits",
        core.RULE_MEMBERS,
        lambda lines: lines[1].update(latencyMs=10**20),
    ),
    (
        "a timeout with an answer inside the deadline",
        core.RULE_OUTCOME,
        lambda lines: request_line(lines, "transport-error").update(
            outcome="timeout", httpStatus=200
        ),
    ),
    (
        "an error that names another adapter",
        core.RULE_OUTCOME,
        lambda lines: request_line(lines, "http-error").update(adapterKind="mock"),
    ),
    (
        "an error after the deadline",
        core.RULE_OUTCOME,
        lambda lines: request_line(lines, "http-error").update(latencyMs=150_001),
    ),
    (
        "a transport error that names an adapter",
        core.RULE_OUTCOME,
        lambda lines: request_line(lines, "transport-error").update(adapterKind="real"),
    ),
    (
        "an end at a ceiling that the run did not reach",
        core.RULE_COUNTS,
        lambda lines: lines[0]["bounds"].update(requestCeiling=9000),
    ),
    (
        "an end at a duration that the run did not reach",
        core.RULE_COUNTS,
        lambda lines: lines[-1].update(endState="duration", elapsedMs=0),
    ),
    (
        "a run that ends before it starts",
        core.RULE_TIME,
        lambda lines: (
            lines.__setitem__(slice(1, -1), []),
            lines[-1].update(
                dispatched=0,
                recorded=0,
                outcomes=dict.fromkeys(incluster.OUTCOMES, 0),
                endState="interrupted",
                finishedAt="2025-01-01T00:00:00.000Z",
            ),
        ),
    ),
    ("no header", core.RULE_HEADER, lambda lines: lines.pop(0)),
    ("two headers", core.RULE_HEADER, lambda lines: lines.insert(1, lines[0])),
    ("no end", core.RULE_END, lambda lines: lines.pop()),
    (
        "a line after the end",
        core.RULE_END,
        lambda lines: lines.append(lines[1]),
    ),
    ("no line", core.RULE_HEADER, lambda lines: lines.clear()),
    (
        "a lost request line",
        core.RULE_SEQUENCE,
        lambda lines: lines.pop(1),
    ),
    (
        "a request line twice",
        core.RULE_SEQUENCE,
        lambda lines: lines.insert(1, lines[1]),
    ),
    (
        "counts of another run",
        core.RULE_COUNTS,
        lambda lines: lines[-1]["outcomes"].update(success=3, **{"http-error": 1}),
    ),
    (
        "a count as a boolean",
        core.RULE_COUNTS,
        lambda lines: lines[-1]["outcomes"].update(timeout=False),
    ),
    (
        "more requests than the ceiling",
        core.RULE_COUNTS,
        lambda lines: lines[0]["bounds"].update(requestCeiling=5),
    ),
    (
        "a prompt in a new member",
        core.RULE_MEMBERS,
        lambda lines: lines[1].update(prompt=PROMPT),
    ),
    (
        "a completion in a text member",
        core.RULE_MEMBERS,
        lambda lines: request_line(lines, "success").update(
            finishReason="A completion text."
        ),
    ),
    (
        "an error message in the error code",
        core.RULE_MEMBERS,
        lambda lines: request_line(lines, "http-error").update(
            errorCode="The runtime did not answer."
        ),
    ),
    (
        "a status of zero",
        core.RULE_MEMBERS,
        lambda lines: request_line(lines, "transport-error").update(httpStatus=0),
    ),
    (
        "a latency as a float",
        core.RULE_MEMBERS,
        lambda lines: lines[1].update(latencyMs=1.5),
    ),
    (
        "an outcome that is not registered",
        core.RULE_MEMBERS,
        lambda lines: lines[1].update(outcome="ok"),
    ),
    (
        "a header with the request body",
        core.RULE_MEMBERS,
        lambda lines: lines[0].update(request={"body": {}}),
    ),
    (
        "a header that targets a pod address",
        core.RULE_MEMBERS,
        lambda lines: lines[0]["target"].update(baseUrl="http://10.1.2.3:8090"),
    ),
    (
        "an unsupported record kind",
        core.RULE_MEMBERS,
        lambda lines: lines.insert(1, {"record": "note"}),
    ),
    (
        "an end with another state",
        core.RULE_MEMBERS,
        lambda lines: lines[-1].update(endState="completed"),
    ),
    (
        "a header that says it holds prompt text",
        core.RULE_CONTENT,
        lambda lines: lines[0].update(promptText=True),
    ),
    (
        "a header that says it holds completion text",
        core.RULE_CONTENT,
        lambda lines: lines[0].update(completionText=None),
    ),
    (
        "a profile digest that is not registered",
        core.RULE_PROFILE_UNREGISTERED,
        lambda lines: lines[0]["profile"].update(profileSha256="0" * 64),
    ),
    (
        "a profile revision that is not registered",
        core.RULE_PROFILE_UNREGISTERED,
        lambda lines: lines[0]["profile"].update(profileRevision=2),
    ),
    (
        "another boundary sentence",
        core.RULE_PROFILE_UNREGISTERED,
        lambda lines: lines[0].update(boundary="RP-1 is a benchmark."),
    ),
    (
        "a header with another concurrency than the plan",
        core.RULE_PLAN_DIFFERS,
        lambda lines: lines[0].update(concurrency=4),
    ),
    (
        "a header with another plan digest",
        core.RULE_PLAN_DIFFERS,
        lambda lines: lines[0].update(planSha256="0" * 64),
    ),
    (
        "a request of another run",
        core.RULE_IDENTITY,
        lambda lines: lines[1].update(runId="run-2"),
    ),
    (
        "a request of another release",
        core.RULE_IDENTITY,
        lambda lines: lines[1].update(releaseId="c" * 64),
    ),
    (
        "a request identifier of another sequence",
        core.RULE_IDENTITY,
        lambda lines: lines[1].update(requestId="run-1-00099"),
    ),
    (
        "a worker that the run does not have",
        core.RULE_IDENTITY,
        lambda lines: lines[1].update(worker=2),
    ),
    (
        "an end of another experiment",
        core.RULE_IDENTITY,
        lambda lines: lines[-1].update(experimentId="EXP-B"),
    ),
    (
        "a time with no milliseconds",
        core.RULE_TIME,
        lambda lines: lines[1].update(startedAt="2026-01-01T00:00:00Z"),
    ),
    (
        "a time in another zone",
        core.RULE_TIME,
        lambda lines: lines[1].update(startedAt="2026-01-01T00:00:00.000+05:00"),
    ),
    (
        "a time that is not a calendar instant",
        core.RULE_TIME,
        lambda lines: lines[1].update(startedAt="2026-13-01T00:00:00.000Z"),
    ),
    (
        "a request that finishes before it starts",
        core.RULE_TIME,
        lambda lines: lines[1].update(finishedAt=lines[0]["startedAt"]),
    ),
    (
        "a request that finishes after the run ends",
        core.RULE_TIME,
        lambda lines: lines[1].update(finishedAt="2027-01-01T00:00:00.000Z"),
    ),
    (
        "a success flag on an error",
        core.RULE_OUTCOME,
        lambda lines: request_line(lines, "http-error").update(success=True),
    ),
    (
        "a success with the status of an error",
        core.RULE_OUTCOME,
        lambda lines: request_line(lines, "success").update(httpStatus=503),
    ),
    (
        "a success after the deadline",
        core.RULE_OUTCOME,
        lambda lines: request_line(lines, "success").update(latencyMs=150_001),
    ),
    (
        "a success of another adapter",
        core.RULE_OUTCOME,
        lambda lines: request_line(lines, "success").update(adapterKind="mock"),
    ),
    (
        "a success with no usage count",
        core.RULE_OUTCOME,
        lambda lines: request_line(lines, "success").update(outputTokens=None),
    ),
    (
        "a transport error with a status",
        core.RULE_OUTCOME,
        lambda lines: request_line(lines, "transport-error").update(httpStatus=200),
    ),
    (
        "an error with the required status",
        core.RULE_OUTCOME,
        lambda lines: request_line(lines, "http-error").update(httpStatus=200),
    ),
    (
        "token counts on an error",
        core.RULE_OUTCOME,
        lambda lines: request_line(lines, "http-error").update(inputTokens=3),
    ),
    (
        "an error code on a success",
        core.RULE_OUTCOME,
        lambda lines: request_line(lines, "success").update(errorCode="internal-error"),
    ),
]


#: The defects that change a value of the header that a plan also states. With
#: the plan, the rule that compares the two refuses first. They are given with no
#: plan, which is how a record is checked when its plan is not kept.
WITHOUT_PLAN = {
    "more requests than the ceiling",
    "an end at a ceiling that the run did not reach",
}


@pytest.mark.parametrize(
    ("name", "rule", "defect"),
    [pytest.param(name, rule, defect, id=name) for name, rule, defect in DEFECTS],
)
def test_a_caller_record_with_one_defect_is_refused(
    name: str, rule: str, defect: Defect
) -> None:
    plan_text, lines = good()
    stated = None if name in WITHOUT_PLAN else plan_text
    core.read_record(text_of(lines), plan=stated)
    defect(lines)
    with pytest.raises(RunnerError) as refused:
        core.read_record(text_of(lines), plan=stated)
    assert refused.value.rule == rule


@pytest.mark.parametrize(
    "text",
    [
        "not json\n",
        '{"record": "header", "record": "header"}\n',
        "[]\n",
        '{"runId": "run-1"}\n',
        '{"record": 1}\n',
        '{"record": "header"}\n\n{"record": "end"}\n',
        pytest.param("[" * 100_000 + "\n", id="deep-nesting"),
    ],
)
def test_a_caller_record_that_is_not_lines_of_json_is_unreadable(text: str) -> None:
    with pytest.raises(RunnerError) as refused:
        core.read_record(text)
    assert refused.value.rule == core.RULE_UNREADABLE


def test_a_record_is_checked_against_a_plan_only_when_one_is_given() -> None:
    _, lines = good()
    lines[0]["planSha256"] = "0" * 64
    assert core.read_record(text_of(lines)).end["dispatched"] == 6
    with pytest.raises(RunnerError) as refused:
        core.read_record(text_of(lines), plan="{")
    assert refused.value.rule == core.RULE_PLAN_DIFFERS


def test_each_rule_is_registered_once_and_each_has_a_refusal_in_this_suite() -> None:
    assert len(RULES) == len(set(RULES)) == 16
    exercised = {rule for _, rule, _ in DEFECTS} | {
        core.RULE_UNREADABLE,
        core.RULE_IDENTIFIER,
        core.RULE_PLAN,
        core.RULE_IMAGE,
        core.RULE_PROFILE,
    }
    assert exercised == set(RULES)


def test_a_profile_that_its_loader_refuses_gives_no_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import reliability_profile

    def refuse() -> Any:
        raise reliability_profile.ProfileError("rp1-source-pin-differs", "changed")

    monkeypatch.setattr(reliability_profile, "load_profile", refuse)
    with pytest.raises(RunnerError) as refused:
        core.build_plan(experiment_id="e", run_id="r", duration_seconds=1)
    assert refused.value.rule == core.RULE_PROFILE
    assert "rp1-source-pin-differs" in str(refused.value)


def test_the_summary_counts_and_grades_nothing() -> None:
    plan_text, lines = good()
    summary = core.read_record(text_of(lines), plan=plan_text).summary()
    assert summary["requests"] == 6
    assert summary["outcomes"] == {
        "success": 2,
        "http-error": 2,
        "invalid-response": 0,
        "timeout": 0,
        "transport-error": 2,
        "identity-refused": 0,
    }
    assert summary["runnerIsThisTree"] is True
    assert summary["release"] == {"releaseId": RELEASE_ID, "source": "declared"}
    assert not {"result", "verdict", "passed", "rate", "p95"} & set(summary)


# --------------------------------------------------------------------------
# The rehearsal and the committed sample
# --------------------------------------------------------------------------


def test_a_rehearsal_gives_each_outcome_twice_and_holds_no_scripted_text() -> None:
    text = core.rehearse()
    record = core.read_record(text)
    assert record.header["mode"] == "rehearsal"
    assert record.header["experimentId"] == "rehearsal"
    assert record.end["endState"] == "request-ceiling"
    assert record.end["outcomes"] == dict.fromkeys(incluster.OUTCOMES, 2)
    assert core.REHEARSAL_COMPLETION_TEXT not in text
    assert "Synthetic error message" not in text
    assert PROMPT not in text
    assert len(core.scripted_answers(plan())) == len(incluster.OUTCOMES)


def test_the_committed_sample_is_a_rehearsal_that_each_rule_accepts() -> None:
    text = SAMPLE_PATH.read_text(encoding="utf-8")
    record = core.read_record(text)
    assert record.header["mode"] == "rehearsal"
    assert record.header["release"] == {"releaseId": None, "source": "not-declared"}
    assert len(record.requests) == core.REHEARSAL_REQUESTS == 12
    assert record.end["outcomes"] == dict.fromkeys(incluster.OUTCOMES, 2)
    assert core.REHEARSAL_COMPLETION_TEXT not in text and PROMPT not in text


def test_a_job_and_a_record_have_the_registered_target_and_no_other() -> None:
    # The function takes a Service name for the suite. The command has no option
    # for it, and neither a Job nor an accepted record has another target.
    other = plan(service="kubernetes", namespace="default", port=443)
    with pytest.raises(RunnerError) as refused:
        core.build_manifest(other, image=IMAGE)
    assert refused.value.rule == core.RULE_PLAN
    assert plan()["target"] == core.registered_target()
    arguments = [
        "plan",
        "--experiment-id",
        "e",
        "--run-id",
        "r",
        "--duration-seconds",
        "1",
    ]
    for option in ("--service", "--namespace", "--port"):
        with pytest.raises(SystemExit) as usage:
            cli.main([*arguments, option, "1"])
        assert usage.value.code == 2


def test_a_job_does_not_run_a_rehearsal_plan() -> None:
    with pytest.raises(RunnerError) as refused:
        core.build_manifest(plan(mode="rehearsal"), image=IMAGE)
    assert refused.value.rule == core.RULE_PLAN


# --------------------------------------------------------------------------
# The Job
# --------------------------------------------------------------------------


def manifest(**changes: Any) -> dict[str, Any]:
    return core.build_manifest(plan(duration_seconds=300), image=IMAGE, **changes)


def test_a_run_is_one_policy_one_configmap_and_one_job_in_the_release_namespace() -> (
    None
):
    items = manifest()["items"]
    assert [(item["apiVersion"], item["kind"]) for item in items] == [
        ("networking.k8s.io/v1", "NetworkPolicy"),
        ("v1", "ConfigMap"),
        ("batch/v1", "Job"),
    ]
    for item in items:
        assert item["metadata"]["name"] == "inferops-reliability-run-1"
        assert item["metadata"]["namespace"] == "inferops-release"
    # No Service, no Ingress object, no Gateway, and no account. The one policy is
    # the allowance of the run, and the test below holds it.
    assert "Gateway" not in core.manifest_text(manifest())


def test_no_selector_of_the_release_selects_the_runner() -> None:
    selectors = []
    for document in yaml.safe_load_all(RENDER_PATH.read_text(encoding="utf-8")):
        if not document:
            continue
        spec = document.get("spec", {})
        selector = spec.get("selector") or spec.get("podSelector")
        if isinstance(selector, dict):
            selectors.append(selector.get("matchLabels", selector))
    assert len(selectors) >= 6
    policy, config_map, job = manifest()["items"]
    labels = job["spec"]["template"]["metadata"]["labels"]
    assert labels == job["metadata"]["labels"] == config_map["metadata"]["labels"]
    assert labels == policy["metadata"]["labels"]
    assert "app.kubernetes.io/instance" not in labels
    assert labels["app.kubernetes.io/name"] == "inferops-reliability-runner"
    assert labels["inferops.io/run-id"] == "run-1"
    assert labels["inferops.io/experiment-id"] == "EXP-A"
    for selector in selectors:
        assert selector, selector
        assert not all(labels.get(key) == value for key, value in selector.items())


def test_the_policy_of_a_run_admits_its_runner_to_the_api_pods_and_nothing_else() -> (
    None
):
    """The release's policy admits its own pods and a named collector to the API, so
    a network plugin that enforces it drops the runner's requests. The first attempt
    of the Sprint 5 integration validation observed that. The policy of a run admits
    the pod of that run, by its run identifier, to the API pods on the API port, and
    it is held here against the committed render of the chart."""
    documents = [
        document
        for document in yaml.safe_load_all(RENDER_PATH.read_text(encoding="utf-8"))
        if document
    ]
    (api,) = [
        document
        for document in documents
        if document["kind"] == "Deployment"
        and document["metadata"]["labels"]["app.kubernetes.io/component"]
        == "platform-api"
    ]
    assert api["spec"]["selector"]["matchLabels"] == dict(core.API_POD_SELECTOR)
    (container,) = [
        c for c in api["spec"]["template"]["spec"]["containers"] if c["name"] == "api"
    ]
    assert [port["containerPort"] for port in container["ports"]] == [
        core.API_CONTAINER_PORT
    ]
    release_policies = {
        document["metadata"]["name"]: document["spec"]
        for document in documents
        if document["kind"] == "NetworkPolicy"
    }
    assert release_policies["inferops-inferops-llm-api"]["podSelector"] == {
        "matchLabels": dict(core.API_POD_SELECTOR)
    }
    # The port that the release's own API policy admits is the port of the run's.
    assert {
        port["port"]
        for rule in release_policies["inferops-inferops-llm-api"]["ingress"]
        for port in rule["ports"]
    } == {core.API_CONTAINER_PORT}

    policy, _, job = manifest()["items"]
    assert policy["metadata"]["name"] == "inferops-reliability-run-1"
    assert policy["spec"] == {
        "podSelector": {"matchLabels": dict(core.API_POD_SELECTOR)},
        "policyTypes": ["Ingress"],
        "ingress": [
            {
                "from": [
                    {
                        "podSelector": {
                            "matchLabels": {
                                "app.kubernetes.io/name": "inferops-reliability-runner",
                                "inferops.io/run-id": "run-1",
                            }
                        }
                    }
                ],
                "ports": [{"port": 8090, "protocol": "TCP"}],
            }
        ],
    }
    # The pod of this run carries every label that the rule names; the pod of
    # another run does not, and no pod of the release does.
    runner_labels = job["spec"]["template"]["metadata"]["labels"]
    admitted = policy["spec"]["ingress"][0]["from"][0]["podSelector"]["matchLabels"]
    assert all(runner_labels[key] == value for key, value in admitted.items())
    other = core.build_manifest(
        plan(run_id="run-2", duration_seconds=300), image=IMAGE
    )["items"][2]["spec"]["template"]["metadata"]["labels"]
    assert not all(other.get(key) == value for key, value in admitted.items())
    for document in documents:
        # The pod template of a workload, and the labels of a bare pod such as the
        # pod of a Helm test.
        for labels in (
            document.get("spec", {})
            .get("template", {})
            .get("metadata", {})
            .get("labels", {}),
            document["metadata"].get("labels", {}) if document["kind"] == "Pod" else {},
        ):
            assert not all(labels.get(key) == value for key, value in admitted.items())
    # It selects the API pods and no runtime pod, and it states no egress rule.
    assert (
        policy["spec"]["podSelector"]["matchLabels"]["app.kubernetes.io/component"]
        == "platform-api"
    )
    assert "egress" not in policy["spec"]


def test_the_job_is_bounded_and_it_runs_one_pod_once() -> None:
    spec = manifest()["items"][2]["spec"]
    assert (spec["completions"], spec["parallelism"], spec["backoffLimit"]) == (1, 1, 0)
    assert spec["activeDeadlineSeconds"] == 300 + 150 + 120
    assert spec["ttlSecondsAfterFinished"] == 3600
    pod = spec["template"]["spec"]
    assert pod["restartPolicy"] == "Never"
    assert pod["terminationGracePeriodSeconds"] == 150 + 30
    assert PROFILE.request_timeout_ms == 150_000


def test_the_pod_holds_no_token_no_probe_and_no_second_container() -> None:
    pod = manifest()["items"][2]["spec"]["template"]["spec"]
    assert pod["automountServiceAccountToken"] is False
    assert pod["enableServiceLinks"] is False
    assert "serviceAccountName" not in pod
    assert "initContainers" not in pod
    (container,) = pod["containers"]
    assert not {"readinessProbe", "livenessProbe", "startupProbe", "ports"} & set(
        container
    )
    assert "env" not in container
    assert container["command"] == [
        "python",
        "-I",
        "-u",
        "-B",
        "/opt/inferops-reliability/incluster.py",
        "/opt/inferops-reliability/plan.json",
    ]
    assert container["image"] == IMAGE
    assert container["imagePullPolicy"] == "Never"
    assert pod["securityContext"] == {
        "runAsNonRoot": True,
        "runAsUser": 65534,
        "runAsGroup": 65534,
        "seccompProfile": {"type": "RuntimeDefault"},
    }
    assert container["securityContext"] == {
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": True,
        "capabilities": {"drop": ["ALL"]},
    }
    assert set(container["resources"]) == {"requests", "limits"}
    assert container["volumeMounts"] == [
        {"name": "run", "mountPath": "/opt/inferops-reliability", "readOnly": True}
    ]


def test_the_configmap_holds_the_runner_file_and_the_plan_with_their_digests() -> None:
    config_map = manifest()["items"][1]
    assert config_map["immutable"] is True
    assert set(config_map["data"]) == {"incluster.py", "plan.json"}
    source = config_map["data"]["incluster.py"]
    assert source == core.runner_source() and "\r" not in source
    annotations = config_map["metadata"]["annotations"]
    # What a pod computes of the two mounted files.
    assert (
        annotations["inferops.io/runner-sha256"]
        == hashlib.sha256(source.encode("utf-8")).hexdigest()
        == core.runner_digest()
    )
    assert (
        annotations["inferops.io/plan-sha256"]
        == hashlib.sha256(config_map["data"]["plan.json"].encode("utf-8")).hexdigest()
    )
    incluster.check_plan(json.loads(config_map["data"]["plan.json"]))
    assert len(core.manifest_text(manifest()).encode("utf-8")) < 1_048_576 // 4


@pytest.mark.parametrize(
    "image",
    [
        "localhost/inferops-api:dev",
        "localhost/inferops-api",
        "localhost/inferops-api@sha256:abc",
        "localhost/inferops-api@sha256:" + "A" * 64,
        "python:3.12-slim",
        "",
    ],
)
def test_an_image_that_is_not_named_by_digest_is_refused(image: str) -> None:
    with pytest.raises(RunnerError) as refused:
        core.build_manifest(plan(), image=image)
    assert refused.value.rule == core.RULE_IMAGE
    with pytest.raises(RunnerError) as policy:
        core.build_manifest(plan(), image=IMAGE, image_pull_policy="Always")
    assert policy.value.rule == core.RULE_IMAGE


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_command_writes_a_plan_a_manifest_and_a_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    arguments = ["--experiment-id", "EXP-A", "--run-id", "run-1"]
    assert cli.main(["plan", *arguments, "--duration-seconds", "60"]) == 0
    text = capsys.readouterr().out
    assert json.loads(text) == plan(request_ceiling=10_000, release_id=None)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(text, encoding="utf-8", newline="\n")
    assert cli.main(["manifest", "--plan", str(plan_path), "--image", IMAGE]) == 0
    assert json.loads(capsys.readouterr().out)["kind"] == "List"

    assert cli.main(["rehearse"]) == 0
    record_path = tmp_path / "caller.jsonl"
    record_path.write_text(capsys.readouterr().out, encoding="utf-8", newline="\n")
    assert cli.main(["verify", str(record_path)]) == 0
    assert json.loads(capsys.readouterr().out)["requests"] == 12


def test_the_command_exits_3_on_a_refusal_and_names_the_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        cli.main(
            ["plan", "--experiment-id", "e", "--run-id", "R", "--duration-seconds", "1"]
        )
        == 3
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"REFUSED  {core.RULE_IDENTIFIER}: ")
    absent = tmp_path / "absent"
    assert cli.main(["verify", str(absent)]) == 3
    assert core.RULE_UNREADABLE in capsys.readouterr().err
    assert cli.main(["manifest", "--plan", str(absent), "--image", IMAGE]) == 3
    assert core.RULE_PLAN in capsys.readouterr().err
    with pytest.raises(SystemExit) as usage:
        cli.main(["start"])
    assert usage.value.code == 2


# --------------------------------------------------------------------------
# The script, read as text
# --------------------------------------------------------------------------

SCRIPT = SCRIPT_PATH.read_text(encoding="utf-8")
SCRIPT_CODE = "\n".join(
    line for line in SCRIPT.splitlines() if not line.lstrip().startswith("#")
)


def test_the_script_restates_the_names_of_the_tool_and_each_agrees() -> None:
    assert f'readonly JOB_NAME_PREFIX="{core.JOB_NAME_PREFIX}"' in SCRIPT
    assert 'readonly RUNNER_MODULE="tools.reliability_runner"' in SCRIPT
    assert f"readonly TOOL_REFUSED_EXIT={cli.EXIT_REFUSED}" in SCRIPT
    assert f"app.kubernetes.io/name={core.RUNNER_NAME}" in SCRIPT
    assert "inferops.io/run-id=${run_id}" in SCRIPT
    assert core.RUN_ID.pattern in SCRIPT
    # The deletion waits longer than the pod is given to stop.
    timeout = int(re.search(r'readonly DELETE_TIMEOUT="(\d+)s"', SCRIPT)[1])  # type: ignore[index]
    assert timeout > PROFILE.request_timeout_ms // 1000 + core.GRACE_MARGIN_SECONDS


def test_the_script_changes_the_cluster_with_one_create_and_three_named_deletions() -> (
    None
):
    calls = re.findall(r"inferops::target_kubectl\s+([a-z-]+)", SCRIPT_CODE)
    assert sorted(calls) == [
        "create",
        "delete",
        "delete",
        "delete",
        "get",
        "get",
        "get",
        "get",
        "logs",
    ]
    # An existing object is a refusal: the read is before the create.
    assert SCRIPT_CODE.index("metadata.name=${job_name}") < SCRIPT_CODE.index(
        "target_kubectl create"
    )
    assert 'delete job "${job_name}" -n "${INFEROPS_RELEASE_NAMESPACE}"' in SCRIPT_CODE
    assert (
        'delete configmap "${job_name}" -n "${INFEROPS_RELEASE_NAMESPACE}"'
        in SCRIPT_CODE
    )
    assert (
        'delete networkpolicy "${job_name}" -n "${INFEROPS_RELEASE_NAMESPACE}"'
        in SCRIPT_CODE
    )
    # The Job goes first, so the pod that the policy admits is gone before it.
    assert SCRIPT_CODE.index('delete job "${job_name}"') < SCRIPT_CODE.index(
        'delete networkpolicy "${job_name}"'
    )
    # A start refuses an earlier policy of the name, and a cleanup looks for one.
    assert "get jobs,configmaps,networkpolicies" in SCRIPT_CODE
    assert "get jobs,configmaps,pods,networkpolicies" in SCRIPT_CODE
    assert not re.search(r"(?<!target_)\bkubectl[ \t]+[a-z]", SCRIPT_CODE)


def test_the_script_waits_for_no_readiness_and_opens_no_forward() -> None:
    for word in (
        "port-forward",
        "rollout",
        "kubectl wait",
        "target_kubectl wait",
        "condition=",
        "readyReplicas",
        "endpointslices",
        "get pods ",
        "helm",
        "curl",
    ):
        assert word not in SCRIPT_CODE, word
    # The one read of the release is the image that the Deployment names.
    assert SCRIPT_CODE.count(".spec.template.spec.containers") == 1
    assert '--namespace "${INFEROPS_RELEASE_NAMESPACE}")' not in SCRIPT_CODE
    # The status of the Job is read by the action `status`, and by no other.
    action = SCRIPT_CODE[
        SCRIPT_CODE.index("\n  status)") : SCRIPT_CODE.index("\n  collect)")
    ]
    assert action.count(".status.") == 5
    assert ".status." not in SCRIPT_CODE.replace(action, "")


def test_a_log_that_the_tool_refuses_is_not_kept_as_the_record() -> None:
    collect = SCRIPT_CODE[
        SCRIPT_CODE.index("\n  collect)") : SCRIPT_CODE.index("\n  cleanup)")
    ]
    assert collect.count('>"${run_dir}/caller.partial.jsonl"') == 1
    assert '>"${run_dir}/caller.jsonl"' not in SCRIPT_CODE
    assert 'mv "${run_dir}/caller.partial.jsonl" "${run_dir}/caller.jsonl"' in collect
    assert collect.count('caller.refused.jsonl"\n') == 3


def test_the_script_resolves_the_target_before_its_first_call() -> None:
    assert SCRIPT_CODE.index("inferops::resolve_target") < SCRIPT_CODE.index(
        "inferops::target_kubectl"
    )
    assert SCRIPT_CODE.index("--run-id must be") < SCRIPT_CODE.index(
        "inferops::resolve_target"
    )


# --------------------------------------------------------------------------
# The guide
# --------------------------------------------------------------------------

GUIDE = GUIDE_PATH.read_text(encoding="utf-8")


def test_the_guide_names_each_rule_in_order() -> None:
    positions = [GUIDE.index(f"`{rule}`") for rule in RULES]
    assert positions == sorted(positions)
    assert f"{len(RULES)} rules" in GUIDE


def test_the_guide_states_each_member_of_a_request_line() -> None:
    for member in core._REQUEST_MEMBERS | core._END_MEMBERS | core._HEADER_MEMBERS:
        assert f"`{member}`" in GUIDE, member
    for outcome in incluster.OUTCOMES:
        assert f"`{outcome}`" in GUIDE, outcome
    for state in incluster.END_STATES:
        assert f"`{state}`" in GUIDE, state


def test_the_guide_states_the_bounds_and_the_target_of_the_code() -> None:
    for text in (
        f"{incluster.MAXIMUM_DURATION_SECONDS:,} seconds",
        f"{incluster.MAXIMUM_REQUEST_CEILING:,} requests",
        f"{core.PAUSE_AFTER_NON_SUCCESS_MS:,} ms",
        f"{core.TTL_AFTER_FINISHED_SECONDS:,} seconds",
        f"http://{core.API_SERVICE}.{core.RELEASE_NAMESPACE}.svc:{core.API_SERVICE_PORT}",
        "scripts/environment/reliability-runner.sh",
        "v2-s5-001-pr2-rehearsal-caller.jsonl",
        BOUNDARY_STATEMENT,
    ):
        assert text in GUIDE, text


def test_the_guide_says_that_no_run_was_started_in_a_cluster() -> None:
    assert "No run was started in a cluster" in GUIDE
    assert "does not establish" in GUIDE.lower()


def test_the_pages_no_longer_say_that_no_runner_exists() -> None:
    for path in (
        "README.md",
        "docs/serving/reliability-workload-rp-1.md",
        "docs/environment/single-runtime-baseline-profile.md",
        "tools/reliability_profile/core.py",
    ):
        text = " ".join((REPO_ROOT / path).read_text(encoding="utf-8").split())
        for phrase in (
            "no runner reads it yet",
            "No runner reads it yet",
            "no runner exists yet",
            "No tool sends RP-1 yet",
            "no runner sends it",
        ):
            assert phrase not in text, (path, phrase)
