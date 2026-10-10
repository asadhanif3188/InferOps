"""The RP-1 reliability caller profile: its values, their origin, and its refusals.

Nothing here sends a request to a model. Each request is answered by an injected
transport function or by a loopback server inside this process. The suite contacts no
cluster and reads no model byte. No latency here describes serving.

The suite does three things:

- **origin** -- it holds each reused value of the profile against the V1 load
  profile, and it holds the request semantics against what the V1 load harness sends:
  the method, the path, the body, the header names, the content type, the deadline,
  and the connection behaviour of the V1 transport. It does not exercise the closed
  loop of the V1 harness, and it holds no V1 value that the profile does not carry;
- **refusal** -- it gives the loader one drift at a time, and it requires the rule
  that names that drift;
- **documents** -- it holds the guide against the profile, the rules, and the two
  digests.
"""

from __future__ import annotations

import copy
import http.server
import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from inferops.api.surface import (
    EXTENSION_ADAPTER_KIND,
    EXTENSION_MEMBER,
    EXTENSION_MODEL_REF,
)
from tools.llm_load import core as source_core
from tools.reliability_profile import __main__ as cli
from tools.reliability_profile import core
from tools.reliability_profile.core import (
    BOUNDARY_STATEMENT,
    CONCURRENCY,
    CONNECTION,
    DISPOSITIONS,
    PROFILE_PATH,
    REGISTERED_REVISIONS,
    RULES,
    SOURCE_DISPOSITION,
    SOURCE_PROFILE_REF,
    ProfileError,
    load_profile,
    profile_digest,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE_PATH = REPO_ROOT / "docs/serving/reliability-workload-rp-1.md"
SOURCE_PATH = REPO_ROOT / SOURCE_PROFILE_REF
RUNTIME_PROFILE_PATH = REPO_ROOT / "docs/serving/runtime-profile.local.v1.json"

PROFILE = load_profile()
DOCUMENT: dict[str, Any] = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
SOURCE = source_core.load_profile()
SOURCE_DOCUMENT: dict[str, Any] = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def write(tmp_path: Path, document: Mapping[str, Any], name: str) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


def mutated(members: tuple[str, ...], value: Any) -> dict[str, Any]:
    """The committed profile with one member replaced."""
    document = copy.deepcopy(DOCUMENT)
    holder: Any = document
    for member in members[:-1]:
        holder = holder[member]
    holder[members[-1]] = value
    return document


def refusal(tmp_path: Path, document: Mapping[str, Any]) -> str:
    """The rule that refuses a profile document."""
    with pytest.raises(ProfileError) as refused:
        load_profile(write(tmp_path, document, "profile.json"))
    return refused.value.rule


class _Handler(http.server.BaseHTTPRequestHandler):
    # HTTP/1.1, so that the server keeps a connection open unless the client asks
    # for it to be closed. Under HTTP/1.0 each connection closes whatever is asked.
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        server: Any = self.server
        server.requests.append(
            (
                self.path,
                self.headers.get("Connection"),
                self.headers.get("Content-Type"),
            )
        )
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/ok")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        status = 503 if self.path == "/busy" else 200
        payload = b"{}"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        return


class _Server(http.server.ThreadingHTTPServer):
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.requests: list[tuple[str, str | None, str | None]] = []
        self.connections = 0

    def get_request(self) -> Any:
        accepted = super().get_request()
        self.connections += 1
        return accepted


@pytest.fixture
def loopback() -> Iterator[_Server]:
    server = _Server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def url(server: _Server, path: str) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}{path}"


# --------------------------------------------------------------------------
# The committed profile
# --------------------------------------------------------------------------


def test_the_committed_profile_loads_as_revision_one_of_rp_1() -> None:
    assert PROFILE.profile_id == "RP-1"
    assert PROFILE.profile_revision == 1
    assert PROFILE.profile_sha256 == REGISTERED_REVISIONS[1]
    assert PROFILE.profile_sha256 == profile_digest(PROFILE_PATH)


def test_the_concurrency_is_two_closed_loop_workers() -> None:
    assert CONCURRENCY == 2
    assert PROFILE.concurrency == 2
    assert DOCUMENT["caller"] == {
        "location": "in-cluster",
        "loop": "closed",
        "concurrency": 2,
    }


def test_the_concurrency_is_the_one_the_v1_profile_declares_as_level_c2() -> None:
    levels = {level.level_id: level.concurrency for level in SOURCE.levels}
    assert levels["c2"] == PROFILE.concurrency


def test_the_target_is_the_api_service_and_not_a_pod_or_a_forward() -> None:
    assert DOCUMENT["target"] == {
        "kind": "api-service",
        "scheme": "http",
        "podAddress": False,
        "portForward": False,
    }


def test_the_profile_states_that_it_is_not_representative_or_a_benchmark() -> None:
    assert DOCUMENT["workloadClass"] == "reliability"
    assert DOCUMENT["evidenceLevelCeiling"] == "C2"
    for member in (
        "representativeWorkload",
        "overloadBenchmark",
        "productionBenchmark",
        "portableCapacityClaim",
    ):
        assert DOCUMENT[member] is False
    assert DOCUMENT["boundary"] == BOUNDARY_STATEMENT


def test_the_profile_digest_ignores_the_checkout_line_endings(tmp_path: Path) -> None:
    lf = PROFILE_PATH.read_bytes().replace(b"\r\n", b"\n")
    (tmp_path / "lf.json").write_bytes(lf)
    (tmp_path / "crlf.json").write_bytes(lf.replace(b"\n", b"\r\n"))
    assert profile_digest(tmp_path / "lf.json") == PROFILE.profile_sha256
    assert profile_digest(tmp_path / "crlf.json") == PROFILE.profile_sha256


def test_the_body_is_a_copy_that_a_caller_cannot_use_to_change_the_profile() -> None:
    body = PROFILE.body()
    body["messages"][0]["content"] = "changed"
    assert PROFILE.body() == DOCUMENT["request"]["body"]


# --------------------------------------------------------------------------
# Origin: each reused value is the V1 value
# --------------------------------------------------------------------------


def test_the_profile_pins_the_committed_v1_load_profile_by_digest() -> None:
    assert DOCUMENT["source"] == {
        "profileRef": SOURCE_PROFILE_REF,
        "profileId": SOURCE.profile_id,
        "profileVersion": SOURCE.profile_version,
        "contentSha256": source_core.profile_digest(SOURCE_PATH),
    }
    assert PROFILE.source_profile_sha256 == SOURCE.profile_sha256


def test_the_fixture_is_the_v1_fixture_member_for_member() -> None:
    fixture = SOURCE_DOCUMENT["fixture"]
    request = DOCUMENT["request"]
    assert request["fixtureId"] == fixture["fixtureId"]
    assert request["path"] == fixture["requestPath"]
    assert request["body"] == {
        "model": fixture["model"],
        "messages": fixture["messages"],
        "stream": fixture["stream"],
    }
    assert PROFILE.body() == SOURCE.fixture.body()


def test_the_generation_settings_are_the_v1_settings() -> None:
    source = SOURCE_DOCUMENT["generation"]
    stated = DOCUMENT["generation"]
    for member in (
        "maxOutputTokens",
        "temperature",
        "contextSizeTokens",
        "parallelSlots",
    ):
        assert stated[member] == source[member]
        assert type(stated[member]) is type(source[member])
    assert stated["sentInRequest"] is False


def test_the_request_body_carries_no_generation_setting() -> None:
    assert set(PROFILE.body()) == {"model", "messages", "stream"}


def test_no_committed_runtime_argument_sets_a_sampling_seed() -> None:
    runtime = json.loads(RUNTIME_PROFILE_PATH.read_text(encoding="utf-8"))
    arguments = runtime["runtime"]["arguments"]
    assert "--temp" in arguments
    assert arguments[arguments.index("--temp") + 1] == "0"
    assert not [
        argument
        for argument in arguments
        if argument == "-s" or argument.startswith("--seed")
    ]
    assert DOCUMENT["generation"]["samplingSeed"] == "not-set"


def test_no_chart_file_sets_a_sampling_seed() -> None:
    chart = REPO_ROOT / "charts/inferops-llm"
    files = [path for path in chart.rglob("*") if path.is_file()]
    assert len(files) > 10
    for path in files:
        assert b"--seed" not in path.read_bytes(), path.name


def test_the_deadline_and_the_success_rule_are_the_v1_values() -> None:
    assert (
        DOCUMENT["timeouts"]["requestTimeoutMs"]
        == SOURCE_DOCUMENT["timeouts"]["requestTimeoutMs"]
    )
    source = dict(SOURCE_DOCUMENT["success"])
    # The V1 harness requires the runtime name of the identity probe, and not of an
    # answer. The profile does not carry it.
    del source["requiredRuntimeName"]
    # The V1 file has no member for the first choice. The V1 classification requires
    # one, and the next test holds that.
    source["requireChoice"] = True
    assert DOCUMENT["success"] == source


def test_the_v1_classification_requires_a_choice_of_a_success() -> None:
    body = {
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        EXTENSION_MEMBER: {
            EXTENSION_ADAPTER_KIND: "real",
            EXTENSION_MODEL_REF: SOURCE.fixture.model,
        },
    }
    for choices, outcome in (
        ([{"finish_reason": "stop"}], source_core.OUTCOME_SUCCESS),
        ([], source_core.OUTCOME_INVALID),
        (None, source_core.OUTCOME_INVALID),
    ):
        answer = source_core.HttpAnswer(200, {**body, "choices": choices})
        result = source_core.classify(SOURCE, answer=answer, failure=None, latency_ms=1)
        assert result.outcome == outcome
    assert DOCUMENT["success"]["requireChoice"] is True


def test_the_v1_harness_sends_the_request_the_profile_states() -> None:
    sent: list[tuple[str, str, Mapping[str, Any] | None, Mapping[str, str], float]] = []

    def transport(
        method: str,
        target: str,
        body: Mapping[str, Any] | None,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> source_core.HttpAnswer:
        sent.append((method, target, body, headers, timeout_seconds))
        return source_core.HttpAnswer(200, None)

    source_core.send_one(
        SOURCE,
        "http://api.invalid",
        run_id="run",
        sequence=1,
        phase=source_core.PHASE_MEASURED,
        level_id="c2",
        concurrency=2,
        worker=0,
        dispatch_offset_ms=0,
        transport=transport,
        clock=lambda: 0.0,
    )
    ((method, target, body, headers, timeout_seconds),) = sent
    assert method == PROFILE.request_method
    assert target == f"http://api.invalid{PROFILE.request_path}"
    assert body == PROFILE.body()
    assert set(headers) == {PROFILE.request_id_header, PROFILE.correlation_id_header}
    assert timeout_seconds * 1000 == PROFILE.request_timeout_ms


def test_the_v1_classification_gives_no_late_answer_the_outcome_success() -> None:
    def completion(adapter_kind: str) -> source_core.HttpAnswer:
        return source_core.HttpAnswer(
            200,
            {
                "choices": [{"finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                EXTENSION_MEMBER: {
                    EXTENSION_ADAPTER_KIND: adapter_kind,
                    EXTENSION_MODEL_REF: SOURCE.fixture.model,
                },
            },
        )

    answer = completion("real")
    # A late answer that names another adapter is not a timeout. The V1
    # classification reads the adapter before the deadline.
    other = source_core.classify(
        SOURCE,
        answer=completion("mock"),
        failure=None,
        latency_ms=PROFILE.request_timeout_ms + 1,
    )
    assert other.outcome == source_core.OUTCOME_IDENTITY
    in_time = source_core.classify(SOURCE, answer=answer, failure=None, latency_ms=1)
    late = source_core.classify(
        SOURCE,
        answer=answer,
        failure=None,
        latency_ms=PROFILE.request_timeout_ms + 1,
    )
    assert in_time.outcome == source_core.OUTCOME_SUCCESS
    assert late.outcome == source_core.OUTCOME_TIMEOUT
    assert DOCUMENT["timeouts"]["answerAfterDeadline"] == "not-a-success"


def test_the_v1_transport_sends_json_on_a_new_connection_each_time(
    loopback: _Server,
) -> None:
    for _ in range(2):
        source_core.http_transport("POST", url(loopback, "/ok"), {"a": 1}, {}, 5)
    assert loopback.connections == 2
    assert [connection for _, connection, _ in loopback.requests] == ["close"] * 2
    assert CONNECTION["newConnectionPerRequest"] is True
    assert [content for _, _, content in loopback.requests] == [
        DOCUMENT["request"]["contentType"]
    ] * 2
    assert DOCUMENT["request"]["contentType"] == core.REQUEST_CONTENT_TYPE


def test_the_v1_transport_follows_no_redirect(loopback: _Server) -> None:
    answer = source_core.http_transport(
        "POST", url(loopback, "/redirect"), {"a": 1}, {}, 5
    )
    assert answer.status == 302
    assert [path for path, _, _ in loopback.requests] == ["/redirect"]
    assert CONNECTION["followRedirects"] is False


def test_the_v1_transport_sends_a_request_that_gets_a_503_once(
    loopback: _Server,
) -> None:
    # One status only. A connection failure and a timeout are not given here: the V1
    # transport raises on each, and its code has no loop.
    answer = source_core.http_transport("POST", url(loopback, "/busy"), {"a": 1}, {}, 5)
    assert answer.status == 503
    assert len(loopback.requests) == 1
    assert CONNECTION["retries"] == 0


def test_the_v1_transport_reads_no_proxy_variable(loopback: _Server) -> None:
    # The V1 transport builds its opener when the module is imported. A variable
    # that a test sets after the import cannot reach that opener, so each request
    # here is sent by a new interpreter that starts with the variable set. The
    # first interpreter is the control: the default opener of the standard library
    # reads the variable, and its request does not arrive.
    proxied = {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
    environment = {
        name: value for name, value in os.environ.items() if name.lower() not in proxied
    }
    environment["HTTP_PROXY"] = "http://127.0.0.1:9"
    environment["ALL_PROXY"] = "http://127.0.0.1:9"
    target = url(loopback, "/ok")

    def child(script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-c", script, target],
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

    transport = child(
        "import sys\n"
        "from tools.llm_load import core\n"
        "print(core.http_transport('POST', sys.argv[1], {'a': 1}, {}, 20).status)\n"
    )
    assert transport.stdout.strip() == "200", transport.stderr
    assert [path for path, _, _ in loopback.requests] == ["/ok"]
    assert CONNECTION["proxyFromEnvironment"] is False


def test_the_profile_states_the_connection_behaviour_of_the_v1_transport() -> None:
    assert DOCUMENT["connection"] == dict(CONNECTION)


# --------------------------------------------------------------------------
# Disposition: each V1 member has one, and nothing is left out
# --------------------------------------------------------------------------


def test_each_member_of_the_v1_file_has_exactly_one_disposition() -> None:
    stated = [entry["member"] for entry in DOCUMENT["sourceDisposition"]]
    assert stated == list(SOURCE_DOCUMENT)
    assert set(stated) == set(SOURCE_DISPOSITION)
    for entry in DOCUMENT["sourceDisposition"]:
        assert entry["disposition"] == SOURCE_DISPOSITION[entry["member"]]
        assert entry["disposition"] in DISPOSITIONS
        assert entry["reason"].endswith(".")


def test_a_v1_member_with_no_registered_disposition_is_refused() -> None:
    # The V1 loader of this tree refuses a member that it does not know, so the
    # loader of this tool cannot be given this case. The helper is called directly.
    stated = [
        *DOCUMENT["sourceDisposition"],
        {"member": "burst", "disposition": "not-carried", "reason": "None."},
    ]
    with pytest.raises(ProfileError) as refused:
        core._check_disposition(stated, set(SOURCE_DOCUMENT) | {"burst"})
    assert refused.value.rule == core.RULE_DISPOSITION
    assert "registers no disposition" in str(refused.value)


def test_a_disposition_entry_of_another_shape_is_refused(tmp_path: Path) -> None:
    entries = DOCUMENT["sourceDisposition"]
    for value in (
        {"warmup": "not-carried"},
        [{**entries[0], "note": "More."}, *entries[1:]],
        [{**entries[0], "reason": ""}, *entries[1:]],
        ["schemaVersion", *entries[1:]],
    ):
        document = mutated(("sourceDisposition",), value)
        assert refusal(tmp_path, document) == core.RULE_MEMBERS


def test_a_missing_a_repeated_and_an_extra_disposition_are_each_refused(
    tmp_path: Path,
) -> None:
    entries = DOCUMENT["sourceDisposition"]
    extra = {"member": "burst", "disposition": "not-carried", "reason": "None."}
    for value in (entries[1:], [*entries, entries[0]], [*entries, extra]):
        document = mutated(("sourceDisposition",), value)
        assert refusal(tmp_path, document) == core.RULE_DISPOSITION


def test_a_disposition_that_is_not_the_registered_one_is_refused(
    tmp_path: Path,
) -> None:
    entries = copy.deepcopy(DOCUMENT["sourceDisposition"])
    warmup = next(entry for entry in entries if entry["member"] == "warmup")
    warmup["disposition"] = "reused"
    document = mutated(("sourceDisposition",), entries)
    assert refusal(tmp_path, document) == core.RULE_DISPOSITION


# --------------------------------------------------------------------------
# Refusal: one drift at a time
# --------------------------------------------------------------------------

DRIFTS: tuple[tuple[tuple[str, ...], Any, str], ...] = (
    (("schemaVersion",), "inferops.io/v1", core.RULE_IDENTITY),
    (("kind",), "LoadProfile", core.RULE_IDENTITY),
    (("profileId",), "RP-2", core.RULE_IDENTITY),
    (("profileRevision",), 2, core.RULE_IDENTITY),
    (("profileRevision",), "1", core.RULE_MEMBERS),
    (("profileRevision",), True, core.RULE_MEMBERS),
    (("workloadClass",), "representative", core.RULE_PURPOSE),
    (("evidenceLevelCeiling",), "C3", core.RULE_PURPOSE),
    (("representativeWorkload",), True, core.RULE_PURPOSE),
    (("overloadBenchmark",), True, core.RULE_PURPOSE),
    (("productionBenchmark",), True, core.RULE_PURPOSE),
    (("portableCapacityClaim",), True, core.RULE_PURPOSE),
    (("boundary",), "RP-1 is a benchmark.", core.RULE_PURPOSE),
    (("boundariesRef",), "README.md", core.RULE_PURPOSE),
    (("source", "profileRef"), "deploy/serving/load/other.json", core.RULE_SOURCE_PIN),
    (("source", "profileId"), "other", core.RULE_SOURCE_PIN),
    (("source", "profileVersion"), "1.0.1", core.RULE_SOURCE_PIN),
    (("source", "contentSha256"), "0" * 64, core.RULE_SOURCE_PIN),
    (("caller", "location"), "operator-host", core.RULE_CALLER),
    (("caller", "loop"), "open", core.RULE_CALLER),
    (("caller", "concurrency"), 1, core.RULE_CALLER),
    (("caller", "concurrency"), 4, core.RULE_CALLER),
    (("caller", "concurrency"), 3, core.RULE_CALLER),
    (("caller", "concurrency"), 2.0, core.RULE_MEMBERS),
    (("target", "kind"), "pod", core.RULE_TARGET),
    (("target", "scheme"), "https", core.RULE_TARGET),
    (("target", "podAddress"), True, core.RULE_TARGET),
    (("target", "portForward"), True, core.RULE_TARGET),
    (("request", "fixtureId"), "other-fixture", core.RULE_REQUEST),
    (("request", "method"), "GET", core.RULE_REQUEST),
    (("request", "path"), "/v1/completions", core.RULE_REQUEST),
    (("request", "contentType"), "text/plain", core.RULE_REQUEST),
    (("request", "requestIdHeader"), "X-Request-ID", core.RULE_REQUEST),
    (("request", "correlationIdHeader"), "X-Correlation-ID", core.RULE_REQUEST),
    (("request", "body", "model"), "another-model", core.RULE_REQUEST),
    (("request", "body", "stream"), True, core.RULE_REQUEST),
    (("request", "body", "stream"), 0, core.RULE_REQUEST),
    (
        ("request", "body", "messages"),
        [{"role": "user", "content": "Another prompt."}],
        core.RULE_REQUEST,
    ),
    (("request", "body", "max_tokens"), 128, core.RULE_REQUEST),
    (("generation", "sentInRequest"), True, core.RULE_GENERATION),
    (("generation", "maxOutputTokens"), 64, core.RULE_GENERATION),
    (("generation", "maxOutputTokens"), 128.0, core.RULE_GENERATION),
    (("generation", "temperature"), 0.7, core.RULE_GENERATION),
    (("generation", "temperature"), 0.0, core.RULE_GENERATION),
    (("generation", "temperature"), False, core.RULE_MEMBERS),
    (("generation", "samplingSeed"), "42", core.RULE_GENERATION),
    (("generation", "contextSizeTokens"), 8192, core.RULE_GENERATION),
    (("generation", "parallelSlots"), 2, core.RULE_GENERATION),
    (("connection", "newConnectionPerRequest"), False, core.RULE_CONNECTION),
    (("connection", "followRedirects"), True, core.RULE_CONNECTION),
    (("connection", "proxyFromEnvironment"), True, core.RULE_CONNECTION),
    (("connection", "retries"), 1, core.RULE_CONNECTION),
    (("connection", "retries"), False, core.RULE_CONNECTION),
    (("timeouts", "requestTimeoutMs"), 120000, core.RULE_TIMEOUT),
    (("timeouts", "answerAfterDeadline"), "a-success", core.RULE_TIMEOUT),
    (("success", "requiredStatus"), 204, core.RULE_SUCCESS),
    (("success", "requiredAdapterKind"), "mock", core.RULE_SUCCESS),
    (("success", "requiredModelRef"), "another-model", core.RULE_SUCCESS),
    (("success", "requiredStatus"), 200.0, core.RULE_SUCCESS),
    (("success", "requireUsage"), False, core.RULE_SUCCESS),
    (("success", "requireUsage"), 1, core.RULE_SUCCESS),
    (("success", "requireChoice"), False, core.RULE_SUCCESS),
    (("success", "requireChoice"), 1, core.RULE_SUCCESS),
    (("results", "promptText"), True, core.RULE_RESULTS),
    (("results", "completionText"), True, core.RULE_RESULTS),
)


@pytest.mark.parametrize(
    ("members", "value", "rule"),
    DRIFTS,
    ids=[f"{'.'.join(members)}={value!r}"[:60] for members, value, _ in DRIFTS],
)
def test_one_drifted_member_is_refused_by_the_rule_that_names_it(
    tmp_path: Path, members: tuple[str, ...], value: Any, rule: str
) -> None:
    assert refusal(tmp_path, mutated(members, value)) == rule


@pytest.mark.parametrize(
    "section",
    [
        "root",
        "source",
        "caller",
        "target",
        "request",
        "generation",
        "connection",
        "timeouts",
        "success",
        "results",
    ],
)
def test_an_unknown_member_is_refused_in_each_section(
    tmp_path: Path, section: str
) -> None:
    document = copy.deepcopy(DOCUMENT)
    holder = document if section == "root" else document[section]
    holder["duration"] = 60
    assert refusal(tmp_path, document) == core.RULE_MEMBERS


def test_a_missing_member_is_refused(tmp_path: Path) -> None:
    document = copy.deepcopy(DOCUMENT)
    del document["timeouts"]["answerAfterDeadline"]
    assert refusal(tmp_path, document) == core.RULE_MEMBERS


def test_a_file_that_is_absent_or_not_an_object_is_unreadable(tmp_path: Path) -> None:
    with pytest.raises(ProfileError) as absent:
        load_profile(tmp_path / "absent.json")
    assert absent.value.rule == core.RULE_UNREADABLE
    (tmp_path / "list.json").write_text("[]", encoding="utf-8")
    (tmp_path / "text.json").write_text("{", encoding="utf-8")
    for name in ("list.json", "text.json"):
        with pytest.raises(ProfileError) as refused:
            load_profile(tmp_path / name)
        assert refused.value.rule == core.RULE_UNREADABLE


def test_a_member_that_the_file_states_twice_is_refused(tmp_path: Path) -> None:
    text = PROFILE_PATH.read_text(encoding="utf-8")
    for once, twice in (
        ('"profileRevision": 1,', '"profileRevision": 1, "profileRevision": 1,'),
        ('"stream": false', '"stream": true, "stream": false'),
    ):
        assert text.count(once) == 1
        path = tmp_path / "profile.json"
        path.write_text(text.replace(once, twice), encoding="utf-8")
        with pytest.raises(ProfileError) as refused:
            load_profile(path)
        assert refused.value.rule == core.RULE_MEMBERS
        assert "twice" in str(refused.value)


def test_a_file_that_the_json_reader_cannot_hold_is_unreadable(tmp_path: Path) -> None:
    text = PROFILE_PATH.read_text(encoding="utf-8")
    huge = text.replace('"profileRevision": 1,', f'"profileRevision": {"9" * 5000},')
    assert huge != text
    for name, content in (("huge.json", huge), ("deep.json", "[" * 100_000)):
        (tmp_path / name).write_text(content, encoding="utf-8")
        with pytest.raises(ProfileError) as refused:
            load_profile(tmp_path / name)
        assert refused.value.rule == core.RULE_UNREADABLE


def test_a_v1_file_that_the_json_reader_cannot_hold_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("[" * 100_000, encoding="utf-8")
    with pytest.raises(ProfileError) as refused:
        load_profile(source_path=source)
    assert refused.value.rule == core.RULE_SOURCE_REFUSED


def test_each_rule_constant_is_listed_once() -> None:
    constants = [
        value for name, value in vars(core).items() if name.startswith("RULE_")
    ]
    assert sorted(constants) == sorted(RULES)
    assert len(set(RULES)) == len(RULES)


def test_a_change_that_no_other_rule_sees_is_refused_by_the_revision_digest(
    tmp_path: Path,
) -> None:
    entries = copy.deepcopy(DOCUMENT["sourceDisposition"])
    entries[0]["reason"] = "Another reason."
    document = mutated(("sourceDisposition",), entries)
    assert refusal(tmp_path, document) == core.RULE_REVISION


def test_a_copy_of_the_committed_bytes_loads(tmp_path: Path) -> None:
    copied = tmp_path / "profile.json"
    copied.write_bytes(PROFILE_PATH.read_bytes())
    assert load_profile(copied) == PROFILE


# --------------------------------------------------------------------------
# Refusal: the V1 load profile changed
# --------------------------------------------------------------------------


def test_a_v1_profile_with_other_bytes_and_the_same_values_is_refused(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    source.write_text(json.dumps(SOURCE_DOCUMENT), encoding="utf-8")
    assert json.loads(source.read_text(encoding="utf-8")) == SOURCE_DOCUMENT
    assert source_core.profile_digest(source) != SOURCE.profile_sha256
    with pytest.raises(ProfileError) as refused:
        load_profile(source_path=source)
    assert refused.value.rule == core.RULE_SOURCE_PIN
    assert "new revision" in str(refused.value)


def test_a_v1_profile_that_its_own_loader_refuses_is_refused(tmp_path: Path) -> None:
    document = copy.deepcopy(SOURCE_DOCUMENT)
    document["generation"]["maxOutputTokens"] = 64
    with pytest.raises(ProfileError) as refused:
        load_profile(source_path=write(tmp_path, document, "source.json"))
    assert refused.value.rule == core.RULE_SOURCE_REFUSED


def test_a_v1_profile_with_another_prompt_is_refused(tmp_path: Path) -> None:
    document = copy.deepcopy(SOURCE_DOCUMENT)
    document["fixture"]["messages"][0]["content"] = "Another prompt."
    with pytest.raises(ProfileError) as refused:
        load_profile(source_path=write(tmp_path, document, "source.json"))
    assert refused.value.rule == core.RULE_SOURCE_PIN


def test_a_v1_profile_without_a_level_at_concurrency_two_is_refused(
    tmp_path: Path,
) -> None:
    document = copy.deepcopy(SOURCE_DOCUMENT)
    document["levels"] = [
        {"levelId": "c1", "concurrency": 1},
        {"levelId": "c4", "concurrency": 4},
    ]
    source = write(tmp_path, document, "source.json")
    # The source pin refuses this file first. The pin is moved to the changed file
    # here, so that the rule behind it is the one that answers.
    profile = mutated(("source", "contentSha256"), source_core.profile_digest(source))
    with pytest.raises(ProfileError) as refused:
        load_profile(write(tmp_path, profile, "profile.json"), source_path=source)
    assert refused.value.rule == core.RULE_CALLER


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_check_command_prints_the_identity_and_the_main_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["check"]) == cli.EXIT_OK
    output = capsys.readouterr().out
    assert "RP-1 revision 1" in output
    assert PROFILE.profile_sha256 in output
    assert PROFILE.source_profile_sha256 in output
    assert "2 closed-loop workers" in output
    assert "execution    not started" in output
    assert DOCUMENT["request"]["body"]["messages"][0]["content"] not in output


def test_the_check_command_exits_3_and_names_the_rule_of_a_refusal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse() -> core.ReliabilityProfile:
        raise ProfileError(core.RULE_SOURCE_PIN, "the pin differs")

    monkeypatch.setattr(cli, "load_profile", refuse)
    assert cli.main(["check"]) == cli.EXIT_REFUSED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "REFUSED  rp1-source-pin-differs: the pin differs\n"


def test_the_check_command_exits_4_for_a_failure_that_no_rule_names(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail() -> core.ReliabilityProfile:
        raise RuntimeError("a detail that the command does not print")

    monkeypatch.setattr(cli, "load_profile", fail)
    assert cli.main(["check"]) == cli.EXIT_FAILED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unexpected local failure" in captured.err
    assert "a detail" not in captured.err


def test_the_command_refuses_arguments_it_does_not_know() -> None:
    for arguments in ([], ["run"], ["check", "--target-url", "http://x"]):
        with pytest.raises(SystemExit) as stopped:
            cli.main(arguments)
        assert stopped.value.code == 2


# --------------------------------------------------------------------------
# The guide
# --------------------------------------------------------------------------


def test_the_guide_states_both_digests_and_the_concurrency() -> None:
    guide = GUIDE_PATH.read_text(encoding="utf-8")
    assert f"`{PROFILE.profile_sha256}`" in guide
    assert f"`{PROFILE.source_profile_sha256}`" in guide
    assert "| Concurrency | 2 |" in guide


def test_the_guide_states_each_value_of_the_profile() -> None:
    guide = GUIDE_PATH.read_text(encoding="utf-8")
    for value in (
        PROFILE.fixture_id,
        f"`{PROFILE.request_method} {PROFILE.request_path}`",
        f"`{PROFILE.request_body['model']}`",
        PROFILE.request_body["messages"][0]["content"],
        f"`maxOutputTokens` {PROFILE.max_output_tokens}",
        f"`temperature` {PROFILE.temperature:g}",
        f"`contextSizeTokens` {PROFILE.context_size_tokens}",
        f"`parallelSlots` {PROFILE.parallel_slots}",
        f"{PROFILE.request_timeout_ms:,} ms",
        f"`{PROFILE.request_id_header}`",
        f"`{PROFILE.correlation_id_header}`",
        BOUNDARY_STATEMENT,
    ):
        assert value in " ".join(guide.split()), value


def test_the_guide_lists_each_rule_once_and_in_order() -> None:
    guide = GUIDE_PATH.read_text(encoding="utf-8")
    rows = [
        line.split("`")[1]
        for line in guide.splitlines()
        if line.startswith("| ") and "`rp1-" in line.split("|")[2]
    ]
    assert tuple(rows) == RULES
    assert f"{len(RULES)} rules" in guide


def test_the_guide_gives_each_v1_member_its_registered_disposition() -> None:
    guide = GUIDE_PATH.read_text(encoding="utf-8")
    rows = {}
    for line in guide.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) >= 4 and cells[1].startswith("`") and cells[2] in DISPOSITIONS:
            rows[cells[1].strip("`")] = cells[2]
    assert rows == dict(SOURCE_DISPOSITION)
