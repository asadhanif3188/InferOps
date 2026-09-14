"""The repeatable LLM load profile: its refusals, its accounting, and its raw record.

Nothing here sends load to a model. Every request is answered either by an injected
transport function or by the rehearsal stub on a loopback socket inside this process,
so no latency in this suite is a serving measurement and none may be cited as one.
The suite contacts no cluster and reads no model byte.

It is heaviest in three places, because those are where a load record goes wrong
without anyone noticing:

- **refusal at load time** -- a profile that drifted from the chart, the runtime
  profile, or its own ceilings must fail before a run somebody paid for;
- **accounting** -- every dispatched request gets exactly one sequence number and one
  outcome, under concurrency, at a duration stop, at an abort, and at an interrupt;
- **the raw reader** -- a record set whose counts do not balance, or that claims to be
  a benchmark, or a synthetic set naming a provider, is refused rather than summarized.
"""

from __future__ import annotations

import concurrent.futures
import copy
import http.server
import itertools
import json
import socket
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.llm_load import __main__ as cli
from tools.llm_load import core
from tools.llm_load.core import (
    API_DIGEST_PLACEHOLDER,
    BOUNDARY_STATEMENT,
    END_ABORTED,
    END_COMPLETED,
    END_INTERRUPTED,
    END_TRANSPORT_LOST,
    END_WARMUP_FAILED,
    FACT_FIELDS,
    FACTS_CHECKED_AGAINST_REPOSITORY,
    FACTS_DECLARED_ONLY,
    MAXIMUM_CONSECUTIVE_TRANSPORT_ERRORS,
    MODE_REAL,
    MODE_REHEARSAL,
    OUTCOME_HTTP_ERROR,
    OUTCOME_IDENTITY,
    OUTCOME_INVALID,
    OUTCOME_SUCCESS,
    OUTCOME_TIMEOUT,
    OUTCOME_TRANSPORT,
    OUTCOMES,
    PROFILE_PATH,
    STOP_CEILING,
    STOP_DURATION,
    HostRecord,
    HttpAnswer,
    LoadError,
    LoadRefused,
    Profile,
    TransportFailure,
    TransportTimeout,
    classify,
    execute,
    load_profile,
    parse_facts,
    parse_raw,
    percentile_ms,
    probe_identity,
    raw_lines,
    render_summary,
    require_loopback_base_url,
    run_to_raw,
    summarize,
)
from tools.llm_load.rehearsal import (
    REHEARSAL_ADAPTER_KIND,
    STUB_COMPLETION_TEXT,
    rehearsal_profile,
    stub_answer,
    stub_server,
)
from tools.model_acquisition import load_manifest
from tools.runtime_packaging import load_runtime_package

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE_PATH = REPO_ROOT / "docs/serving/llm-load-generation.md"
EXAMPLE_RAW = REPO_ROOT / "docs/proof/serving/v1-s4-003-pr1-rehearsal-raw.jsonl"
EXAMPLE_SUMMARY = REPO_ROOT / "docs/proof/serving/v1-s4-003-pr1-rehearsal-summary.json"
VALIDATION_RECORD = REPO_ROOT / "docs/proof/serving/v1-s4-003-pr1-validation.md"

PROFILE = load_profile()
PROFILE_DOCUMENT: dict[str, Any] = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
REVISION = load_manifest().revision
RUNTIME_NAME = "llama.cpp llama-server"
MODEL = "qwen3-1-7b-q8-0"
HOST = HostRecord("TestOS", "1", "x86_64", 4, None, "3.12.0")
FIXTURE_TEXT = PROFILE.fixture.messages[0]["content"]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def write_profile(tmp_path: Path, document: dict[str, Any]) -> Path:
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def valid_facts() -> dict[str, Any]:
    chart = yaml.safe_load((REPO_ROOT / "charts/inferops-llm/Chart.yaml").read_text())
    return {
        "provider": "docker-desktop",
        "kubernetesServerVersion": "v1.34.3",
        "chart": f"{chart['name']}-{chart['version']}",
        "releaseRevision": 1,
        "apiImage": "localhost/inferops-api@sha256:" + "a" * 64,
        "runtimeImage": load_runtime_package().image_reference,
        "modelRevision": REVISION,
        "apiReplicas": 1,
        "runtimeReplicas": 1,
        "repositoryRevision": "b" * 40,
    }


def completion(
    *,
    adapter: str = "real",
    model: str = MODEL,
    usage: object = "default",
    choices: object = "default",
) -> dict[str, Any]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": model,
        "choices": (
            [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "SECRET-COMPLETION"},
                    "finish_reason": "stop",
                }
            ]
            if choices == "default"
            else choices
        ),
        "usage": (
            {"prompt_tokens": 30, "completion_tokens": 17, "total_tokens": 47}
            if usage == "default"
            else usage
        ),
        "x_inferops": {"adapterKind": adapter, "modelRef": model},
    }


def refusal(
    code: str, *, adapter: str = "real", condition: str = "runtime-unreachable"
) -> dict[str, Any]:
    return {
        "code": code,
        "message": "refused",
        "details": {
            "conditionId": condition,
            "adapterKind": adapter,
            "modelRef": MODEL,
        },
    }


def identity_answers(
    *,
    ready_status: int = 200,
    ready_state: str = "ready",
    ready_adapter: str = "real",
    models_adapter: str = "real",
    model_ids: tuple[str, ...] = (MODEL,),
    runtime_name: str = RUNTIME_NAME,
    revision: str = REVISION,
) -> dict[str, HttpAnswer]:
    return {
        "/health/ready": HttpAnswer(
            ready_status,
            {"status": ready_state, "adapterKind": ready_adapter, "state": "ready"},
        ),
        "/v1/models": HttpAnswer(
            200,
            {
                "object": "list",
                "data": [{"id": model_id} for model_id in model_ids],
                "x_inferops": {
                    "adapterKind": models_adapter,
                    "runtime": {
                        "name": runtime_name,
                        "version": "b1-deadbeef",
                        "modelRevision": revision,
                    },
                },
            },
        ),
    }


class FakeTransport:
    """Answers identity probes from a table and completions from a function."""

    def __init__(
        self,
        answer_for: Any = None,
        *,
        identity: dict[str, HttpAnswer] | None = None,
        tick: float = 0.0,
        clock: FakeClock | None = None,
    ) -> None:
        self.identity = identity if identity is not None else identity_answers()
        self.answer_for = answer_for or (lambda sequence: HttpAnswer(200, completion()))
        self.clock = clock
        self.tick = tick
        self.lock = threading.Lock()
        self.sequences: list[int] = []
        self.bodies: list[Any] = []

    def __call__(
        self,
        method: str,
        url: str,
        body: Any,
        headers: Any,
        timeout: float,
    ) -> HttpAnswer:
        path = "/" + url.split("/", 3)[3]
        if method == "GET":
            return self.identity[path]
        sequence = int(headers["X-InferOps-Request-ID"].rsplit("-", 1)[1])
        with self.lock:
            self.sequences.append(sequence)
            self.bodies.append(body)
        if self.clock is not None:
            self.clock.advance(self.tick)
        result = self.answer_for(sequence)
        if isinstance(result, BaseException):
            raise result
        return result


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.lock = threading.Lock()

    def __call__(self) -> float:
        with self.lock:
            return self.now

    def advance(self, seconds: float) -> None:
        with self.lock:
            self.now += seconds


def quick(profile: Profile = PROFILE, **changes: Any) -> Profile:
    """The committed profile with small bounds, for engine tests that must be fast."""
    defaults: dict[str, Any] = {"max_requests_per_level": 6, "duration_seconds": 600}
    defaults.update(changes)
    return replace(profile, **defaults)


def run(
    profile: Profile,
    transport: FakeTransport,
    *,
    mode: str = MODE_REAL,
    clock: Any = None,
) -> core.LoadRun:
    return execute(
        profile,
        base_url="http://127.0.0.1:18091",
        mode=mode,
        confirmed=True,
        facts=parse_facts(valid_facts()) if mode == MODE_REAL else None,
        transport=transport,
        host=HOST,
        **({"clock": clock} if clock is not None else {}),
    )


# --------------------------------------------------------------------------
# The committed profile
# --------------------------------------------------------------------------


def test_the_committed_profile_loads_with_the_published_defaults() -> None:
    assert PROFILE.profile_id == "inferops-llm-load"
    assert PROFILE.profile_version == "1.0.0"
    assert PROFILE.evidence_class == "local-real-cpu"
    assert PROFILE.production_benchmark is False
    assert PROFILE.portable_capacity_claim is False
    assert PROFILE.warmup_requests == 3
    assert PROFILE.warmup_concurrency == 1
    assert [(level.level_id, level.concurrency) for level in PROFILE.levels] == [
        ("c1", 1),
        ("c2", 2),
        ("c4", 4),
    ]
    assert PROFILE.duration_seconds == 180
    assert PROFILE.max_requests_per_level == 60
    assert PROFILE.request_timeout_ms == 150_000
    assert PROFILE.worst_case_seconds() == 1460
    assert PROFILE.fixture.stream is False
    assert len(PROFILE.fixture.messages) == 1


def test_the_profile_digest_ignores_the_checkout_line_endings(tmp_path: Path) -> None:
    lf = PROFILE_PATH.read_bytes().replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    (tmp_path / "lf.json").write_bytes(lf)
    (tmp_path / "crlf.json").write_bytes(crlf)
    assert core.profile_digest(tmp_path / "lf.json") == core.profile_digest(
        tmp_path / "crlf.json"
    )
    assert core.profile_digest(tmp_path / "lf.json") == PROFILE.profile_sha256


def test_the_placeholder_constant_is_the_digest_the_render_fixture_carries() -> None:
    values = yaml.safe_load(
        (REPO_ROOT / "charts/inferops-llm/ci/real-values.yaml").read_text()
    )
    assert values["api"]["image"]["digest"] == API_DIGEST_PLACEHOLDER


def _set(document: dict[str, Any], dotted: str, value: Any) -> None:
    keys = dotted.split(".")
    target: Any = document
    for key in keys[:-1]:
        target = target[int(key)] if isinstance(target, list) else target[key]
    last = keys[-1]
    if isinstance(target, list):
        target[int(last)] = value
    else:
        target[last] = value


PROFILE_CORRUPTIONS: list[tuple[str, Any, str]] = [
    ("productionBenchmark", True, "production benchmark"),
    ("boundary", "Fast enough for production.", "boundary statement verbatim"),
    ("portableCapacityClaim", True, "portable capacity"),
    ("evidenceClass", "synthetic", "identity is unsupported"),
    ("evidenceLabel", "local real runtime", "identity is unsupported"),
    ("certificationCeiling", "C3", "identity is unsupported"),
    ("profileId", "another", "identity is unsupported"),
    ("boundariesRef", "README.md", "unexpected document"),
    ("release.realValuesRef", "charts/inferops-llm/ci/mock-values.yaml", "unexpected"),
    ("target.host", "0.0.0.0", "loopback"),
    ("target.scheme", "https", "loopback"),
    ("target.readinessPath", "/health/live", "loopback"),
    ("fixture.model", "another-model", "served model"),
    ("fixture.stream", True, "served model"),
    ("fixture.requestPath", "/v1/completions", "served model"),
    (
        "fixture.messages",
        [{"role": "tool", "content": "x"}],
        "refused by the InferOps API",
    ),
    ("generation.temperature", 0.7, "drifted"),
    ("generation.maxOutputTokens", 256, "drifted"),
    ("generation.contextSizeTokens", 8192, "drifted"),
    ("generation.parallelSlots", 2, "drifted"),
    ("timeouts.requestTimeoutMs", 120_000, "exceed the API's own deadline"),
    ("timeouts.requestTimeoutMs", 60_000, "exceed the API's own deadline"),
    ("timeouts.requestTimeoutMs", 300_001, "within the ceiling"),
    (
        "levels",
        [{"levelId": "c2", "concurrency": 2}, {"levelId": "c1", "concurrency": 1}],
        "rise strictly",
    ),
    (
        "levels",
        [{"levelId": "c1", "concurrency": 1}, {"levelId": "c1b", "concurrency": 1}],
        "rise strictly",
    ),
    (
        "levels",
        [{"levelId": "c1", "concurrency": 1}, {"levelId": "c1", "concurrency": 2}],
        "distinct",
    ),
    ("levels", [{"levelId": "warmup", "concurrency": 1}], "non-reserved"),
    ("levels", [{"levelId": "C 1", "concurrency": 1}], "safe token"),
    ("levels", [{"levelId": "c16", "concurrency": 16}], "within the ceiling"),
    (
        "levels",
        [{"levelId": f"c{n}", "concurrency": n} for n in range(1, 8)],
        "number of levels",
    ),
    ("warmup.requests", 21, "execution envelope"),
    ("warmup.concurrency", 4, "execution envelope"),
    ("measured.maxRequestsPerLevel", 501, "execution envelope"),
    ("measured.maxRequestsPerLevel", 3, "execution envelope"),
    ("measured.durationSeconds", 901, "execution envelope"),
    ("measured.durationSeconds", 149, "shorter than one request deadline"),
    ("warmup.requests", 20, "worst case"),
    ("success.requiredAdapterKind", "mock", "explicitly real"),
    ("success.requiredModelRef", "another", "explicitly real"),
    ("success.requiredStatus", 201, "explicitly real"),
    ("success.requireUsage", False, "explicitly real"),
    ("results.directory", ".cache/inferops/baseline", "result layout"),
    ("results.rawFile", "../raw.jsonl", "result layout"),
    ("results.rawFile", "..\\raw.jsonl", "result layout"),
    ("results.percentileMethod", "linear", "result layout"),
    ("results.reportedPercentiles", [50, 90], "result layout"),
]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    PROFILE_CORRUPTIONS,
    ids=[f"{field}={value!r}"[:60] for field, value, _ in PROFILE_CORRUPTIONS],
)
def test_a_drifted_profile_is_refused(
    tmp_path: Path, field: str, value: Any, message: str
) -> None:
    document = copy.deepcopy(PROFILE_DOCUMENT)
    _set(document, field, value)
    with pytest.raises(LoadError, match=message):
        load_profile(write_profile(tmp_path, document))


@pytest.mark.parametrize("section", ["root", "fixture", "warmup", "success"])
def test_a_profile_with_an_unknown_or_missing_member_is_refused(
    tmp_path: Path, section: str
) -> None:
    extra = copy.deepcopy(PROFILE_DOCUMENT)
    target = extra if section == "root" else extra[section]
    target["unexpected"] = 1
    with pytest.raises(LoadError, match="missing or unsupported"):
        load_profile(write_profile(tmp_path, extra))
    missing = copy.deepcopy(PROFILE_DOCUMENT)
    target = missing if section == "root" else missing[section]
    target.pop(next(iter(target)))
    with pytest.raises(LoadError, match="missing or unsupported"):
        load_profile(write_profile(tmp_path, missing))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("warmup.requests", 0),
        ("warmup.requests", True),
        ("measured.durationSeconds", "180"),
        ("generation.temperature", "0"),
        ("fixture.stream", "false"),
    ],
)
def test_a_profile_field_of_the_wrong_type_is_refused(
    tmp_path: Path, field: str, value: Any
) -> None:
    document = copy.deepcopy(PROFILE_DOCUMENT)
    _set(document, field, value)
    with pytest.raises(LoadError, match="must be"):
        load_profile(write_profile(tmp_path, document))


# --------------------------------------------------------------------------
# Environment facts
# --------------------------------------------------------------------------


def test_valid_facts_parse_and_their_provenance_partitions_every_field() -> None:
    facts = parse_facts(valid_facts())
    assert facts.document() == valid_facts()
    assert set(FACTS_CHECKED_AGAINST_REPOSITORY) | set(FACTS_DECLARED_ONLY) == set(
        FACT_FIELDS
    )
    assert not set(FACTS_CHECKED_AGAINST_REPOSITORY) & set(FACTS_DECLARED_ONLY)


@pytest.mark.parametrize("provider", ["kind", "docker-desktop"])
def test_every_provider_the_contract_publishes_is_accepted(provider: str) -> None:
    assert parse_facts({**valid_facts(), "provider": provider}).provider == provider


FACT_CORRUPTIONS: list[tuple[str, Any, str]] = [
    ("provider", "minikube", "provider contract does not publish"),
    ("chart", "inferops-llm-0.2.0", "chart other than"),
    ("runtimeImage", "ghcr.io/ggml-org/llama.cpp@sha256:" + "0" * 64, "runtime image"),
    ("modelRevision", "0" * 40, "model revision"),
    ("apiImage", "localhost/inferops-api:dev", "by digest"),
    ("apiImage", "localhost/inferops-api@" + API_DIGEST_PLACEHOLDER, "placeholder"),
    ("repositoryRevision", "abc1234", "full commit"),
    ("repositoryRevision", "B" * 40, "full commit"),
    ("kubernetesServerVersion", "v1.34 3", "plain reference"),
    ("kubernetesServerVersion", "", "non-empty"),
    ("releaseRevision", 0, "at least 1"),
    ("apiReplicas", "1", "integer"),
]


@pytest.mark.parametrize(("field", "value", "message"), FACT_CORRUPTIONS)
def test_a_wrong_environment_fact_is_refused(
    field: str, value: Any, message: str
) -> None:
    with pytest.raises(LoadError, match=message):
        parse_facts({**valid_facts(), field: value})


def test_facts_with_a_missing_or_extra_member_are_refused() -> None:
    missing = valid_facts()
    missing.pop("provider")
    with pytest.raises(LoadError, match="missing or unsupported"):
        parse_facts(missing)
    with pytest.raises(LoadError, match="missing or unsupported"):
        parse_facts({**valid_facts(), "hostname": "somebody"})


# --------------------------------------------------------------------------
# The loopback target and the identity probe
# --------------------------------------------------------------------------


@pytest.mark.parametrize("url", ["http://127.0.0.1:18091", "http://127.0.0.1:18091/"])
def test_a_loopback_forward_is_accepted(url: str) -> None:
    assert require_loopback_base_url(url, PROFILE) == "http://127.0.0.1:18091"


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:18091",
        "http://localhost:18091",
        "http://0.0.0.0:18091",
        "http://10.0.0.5:8090",
        "http://127.0.0.1",
        "http://127.0.0.1:18091/v1",
        "http://127.0.0.1:18091?x=1",
        "http://user:pass@127.0.0.1:18091",
        "http://127.0.0.1:99999",
        "127.0.0.1:18091",
    ],
)
def test_a_target_that_is_not_a_plain_loopback_forward_is_refused(url: str) -> None:
    with pytest.raises(LoadRefused):
        require_loopback_base_url(url, PROFILE)


def test_the_identity_probe_records_what_the_release_said() -> None:
    identity = probe_identity(PROFILE, "http://127.0.0.1:1", transport=FakeTransport())
    assert identity.document() == {
        "readinessStatus": "ready",
        "adapterKind": "real",
        "modelId": MODEL,
        "modelRevision": REVISION,
        "runtimeName": RUNTIME_NAME,
        "runtimeVersion": "b1-deadbeef",
    }


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"ready_status": 503}, "not ready"),
        ({"ready_state": "not-ready"}, "not ready"),
        ({"ready_adapter": "mock"}, "readiness names an adapter"),
        ({"models_adapter": "mock"}, "model list names an adapter"),
        ({"models_adapter": REHEARSAL_ADAPTER_KIND}, "model list names an adapter"),
        ({"model_ids": (MODEL, "another")}, "exactly one model"),
        ({"model_ids": ("another",)}, "model other than"),
        ({"runtime_name": "vllm"}, "runtime other than"),
        ({"revision": "0" * 40}, "revision other than"),
    ],
)
def test_the_identity_probe_refuses_a_target_that_is_not_the_release(
    changes: dict[str, Any], message: str
) -> None:
    transport = FakeTransport(identity=identity_answers(**changes))
    with pytest.raises(LoadRefused, match=message):
        probe_identity(PROFILE, "http://127.0.0.1:1", transport=transport)
    assert transport.sequences == []


def test_an_unreachable_target_is_refused_before_any_load() -> None:
    def failing(*_: Any) -> HttpAnswer:
        raise TransportFailure()

    with pytest.raises(LoadRefused, match="identity probe"):
        probe_identity(PROFILE, "http://127.0.0.1:1", transport=failing)


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

CLASSIFICATIONS: list[
    tuple[str, HttpAnswer | None, str | None, int, str, str | None]
] = [
    ("client timeout", None, OUTCOME_TIMEOUT, 150_001, OUTCOME_TIMEOUT, None),
    ("connection failure", None, OUTCOME_TRANSPORT, 3, OUTCOME_TRANSPORT, None),
    ("success", HttpAnswer(200, completion()), None, 900, OUTCOME_SUCCESS, None),
    (
        "success after the deadline",
        HttpAnswer(200, completion()),
        None,
        150_001,
        OUTCOME_TIMEOUT,
        None,
    ),
    (
        "success exactly at the deadline",
        HttpAnswer(200, completion()),
        None,
        150_000,
        OUTCOME_SUCCESS,
        None,
    ),
    (
        "mock completion",
        HttpAnswer(200, completion(adapter="mock")),
        None,
        10,
        OUTCOME_IDENTITY,
        None,
    ),
    (
        "mock refusal",
        HttpAnswer(503, refusal("model-not-ready", adapter="mock")),
        None,
        10,
        OUTCOME_IDENTITY,
        None,
    ),
    (
        "canonical refusal",
        HttpAnswer(503, refusal("model-not-ready")),
        None,
        10,
        OUTCOME_HTTP_ERROR,
        "model-not-ready",
    ),
    (
        "upstream timeout",
        HttpAnswer(504, refusal("upstream-timeout")),
        None,
        120_010,
        OUTCOME_HTTP_ERROR,
        "upstream-timeout",
    ),
    (
        "error code carrying free text",
        HttpAnswer(500, {"code": "Traceback: secret at /home/x"}),
        None,
        10,
        OUTCOME_HTTP_ERROR,
        "unrecognized",
    ),
    ("proxy error page", HttpAnswer(502, None), None, 10, OUTCOME_HTTP_ERROR, None),
    (
        "carrier deadline, empty body",
        HttpAnswer(504, None),
        None,
        120_004,
        OUTCOME_HTTP_ERROR,
        None,
    ),
    (
        "late mock answer",
        HttpAnswer(200, completion(adapter="mock")),
        None,
        150_001,
        OUTCOME_IDENTITY,
        None,
    ),
    (
        "another model",
        HttpAnswer(200, completion(model="another-model")),
        None,
        10,
        OUTCOME_INVALID,
        None,
    ),
    (
        "no usage",
        HttpAnswer(200, completion(usage=None)),
        None,
        10,
        OUTCOME_INVALID,
        None,
    ),
    (
        "usage with a negative count",
        HttpAnswer(
            200, completion(usage={"prompt_tokens": -1, "completion_tokens": 1})
        ),
        None,
        10,
        OUTCOME_INVALID,
        None,
    ),
    (
        "no choices",
        HttpAnswer(200, completion(choices=[])),
        None,
        10,
        OUTCOME_INVALID,
        None,
    ),
    ("body not JSON", HttpAnswer(200, None), None, 10, OUTCOME_INVALID, None),
    (
        "no identity at all",
        HttpAnswer(200, {**completion(), "x_inferops": None}),
        None,
        10,
        OUTCOME_INVALID,
        None,
    ),
]


@pytest.mark.parametrize(
    ("answer", "failure", "latency", "outcome", "code"),
    [case[1:] for case in CLASSIFICATIONS],
    ids=[case[0] for case in CLASSIFICATIONS],
)
def test_classification_is_a_fixed_function_of_what_came_back(
    answer: HttpAnswer | None,
    failure: str | None,
    latency: int,
    outcome: str,
    code: str | None,
) -> None:
    first = classify(PROFILE, answer=answer, failure=failure, latency_ms=latency)
    second = classify(PROFILE, answer=answer, failure=failure, latency_ms=latency)
    assert first == second
    assert first.outcome == outcome
    assert first.error_code == code
    if outcome == OUTCOME_SUCCESS:
        assert (first.input_tokens, first.output_tokens) == (30, 17)
        assert first.finish_reason == "stop"
    else:
        assert first.input_tokens is None
        assert first.output_tokens is None


def test_every_outcome_is_reachable_by_classification() -> None:
    reached = {
        classify(PROFILE, answer=case[1], failure=case[2], latency_ms=case[3]).outcome
        for case in CLASSIFICATIONS
    }
    assert reached == set(OUTCOMES)


# --------------------------------------------------------------------------
# The bounded closed loop
# --------------------------------------------------------------------------


def test_a_completed_run_dispatches_exactly_each_ceiling_and_records_every_request() -> (
    None
):
    transport = FakeTransport()
    result = run(quick(), transport)
    assert result.end_state == END_COMPLETED
    assert [phase.level_id for phase in result.phases] == ["warmup", "c1", "c2", "c4"]
    assert [phase.dispatched for phase in result.phases] == [3, 6, 6, 6]
    assert all(phase.stop_reason == STOP_CEILING for phase in result.phases)
    assert [record.sequence for record in result.records] == list(range(21))
    assert sorted(transport.sequences) == list(range(21))
    for record in result.records:
        assert 0 <= record.worker < record.concurrency


def test_a_level_never_dispatches_past_its_ceiling_under_concurrency() -> None:
    for _ in range(5):
        transport = FakeTransport()
        result = run(quick(max_requests_per_level=17), transport)
        c4 = [record for record in result.records if record.level_id == "c4"]
        assert len(c4) == 17
        assert len({record.sequence for record in c4}) == 17
        assert len(transport.sequences) == len(set(transport.sequences)) == 3 + 17 * 3


def test_every_request_sends_the_fixture_byte_for_byte() -> None:
    transport = FakeTransport()
    run(quick(), transport)
    assert all(body == PROFILE.fixture.body() for body in transport.bodies)


def test_a_duration_stop_lets_the_dispatched_request_finish_and_records_it() -> None:
    clock = FakeClock()
    transport = FakeTransport(clock=clock, tick=40.0)
    # One sequential level, so the fake clock's order of events is the only order.
    profile = quick(
        duration_seconds=100, max_requests_per_level=60, levels=(core.Level("c1", 1),)
    )
    result = run(profile, transport, clock=clock)
    level = result.phases[1]
    # Dispatched at 0, 40, and 80 seconds; the third finishes at 120, after the
    # duration, and is still recorded. The fourth is never sent.
    assert level.dispatched == 3
    assert level.stop_reason == STOP_DURATION
    assert level.window_ms == 120_000
    offsets = [r.dispatch_offset_ms for r in result.records if r.level_id == "c1"]
    assert offsets == [0, 40_000, 80_000]
    assert len(result.records) == 3 + level.dispatched


def test_a_failed_warmup_runs_no_level() -> None:
    transport = FakeTransport(
        lambda sequence: (
            HttpAnswer(503, refusal("model-not-ready"))
            if sequence == 1
            else HttpAnswer(200, completion())
        )
    )
    result = run(quick(), transport)
    assert result.end_state == END_WARMUP_FAILED
    assert [phase.phase for phase in result.phases] == ["warmup"]
    assert len(result.records) == 3
    summary = summarize(run_to_raw(result))
    assert summary["usable"] is False
    assert summary["levels"] == []


def test_a_mock_answer_aborts_the_run_and_is_never_a_success() -> None:
    transport = FakeTransport(
        lambda sequence: (
            HttpAnswer(200, completion(adapter="mock"))
            if sequence == 5
            else HttpAnswer(200, completion())
        )
    )
    result = run(quick(), transport)
    assert result.end_state == END_ABORTED
    refused = [record for record in result.records if record.sequence == 5]
    assert refused[0].outcome == OUTCOME_IDENTITY
    assert refused[0].output_tokens is None
    assert [phase.level_id for phase in result.phases] == ["warmup", "c1"]
    raw = run_to_raw(result)
    assert summarize(raw)["usable"] is False


def test_an_interrupt_stops_dispatch_and_keeps_what_was_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_wait = concurrent.futures.wait
    calls = itertools.count()

    def interrupting_wait(*args: Any, **kwargs: Any) -> Any:
        if next(calls) == 1:
            raise KeyboardInterrupt
        return real_wait(*args, **kwargs)

    monkeypatch.setattr(concurrent.futures, "wait", interrupting_wait)
    result = run(quick(max_requests_per_level=500), FakeTransport())
    assert result.end_state == END_INTERRUPTED
    raw = run_to_raw(result)
    assert raw.end["dispatched"] == len(raw.records)


def test_a_worker_that_fails_unexpectedly_stops_the_run_rather_than_hiding() -> None:
    transport = FakeTransport(
        lambda sequence: (
            RuntimeError("boom") if sequence == 4 else HttpAnswer(200, completion())
        )
    )
    with pytest.raises(RuntimeError, match="boom"):
        run(quick(), transport)


@pytest.mark.parametrize(
    ("mode", "confirmed", "with_facts", "message"),
    [
        (MODE_REAL, False, True, "confirm-real-load"),
        (MODE_REAL, True, False, "environment-facts"),
        (MODE_REHEARSAL, False, True, "may not carry environment facts"),
        ("benchmark", True, False, "either real or a rehearsal"),
    ],
)
def test_a_run_refuses_a_wrong_mode_confirmation_or_facts_combination(
    mode: str, confirmed: bool, with_facts: bool, message: str
) -> None:
    transport = FakeTransport()
    with pytest.raises(LoadError, match=message):
        execute(
            quick(),
            base_url="http://127.0.0.1:18091",
            mode=mode,
            confirmed=confirmed,
            facts=parse_facts(valid_facts()) if with_facts else None,
            transport=transport,
            host=HOST,
        )
    assert transport.sequences == []


def test_a_real_run_refuses_a_rehearsal_stub_as_it_refuses_a_mock() -> None:
    transport = FakeTransport(
        identity=identity_answers(
            ready_adapter=REHEARSAL_ADAPTER_KIND, models_adapter=REHEARSAL_ADAPTER_KIND
        )
    )
    with pytest.raises(LoadRefused):
        run(quick(), transport)
    assert transport.sequences == []


# --------------------------------------------------------------------------
# The raw record set and its reader
# --------------------------------------------------------------------------


def completed_lines() -> list[str]:
    transport = FakeTransport(
        lambda sequence: (
            HttpAnswer(504, refusal("upstream-timeout"))
            if sequence % 5 == 4
            else HttpAnswer(200, completion())
        )
    )
    return raw_lines(run(quick(), transport))


def test_the_raw_record_set_carries_no_prompt_completion_or_host_identity() -> None:
    text = "\n".join(completed_lines())
    assert "SECRET-COMPLETION" not in text
    assert FIXTURE_TEXT not in text
    assert "http://127.0.0.1:18091" not in text
    header = json.loads(text.splitlines()[0])
    assert set(header["environment"]["generatorHost"]) == {
        "operatingSystem",
        "release",
        "architecture",
        "logicalCpus",
        "totalMemoryBytes",
        "pythonVersion",
    }
    assert header["boundary"] == BOUNDARY_STATEMENT
    assert header["productionBenchmark"] is False
    assert header["portableCapacityClaim"] is False


def test_a_raw_record_set_round_trips_and_summarizes_identically() -> None:
    text = "\n".join(completed_lines()) + "\n"
    first = render_summary(summarize(parse_raw(text)))
    second = render_summary(summarize(parse_raw(text)))
    assert first == second
    summary = json.loads(first)
    assert summary["accounting"]["dispatched"] == 21
    assert summary["accounting"]["outcomes"][OUTCOME_HTTP_ERROR] == 4
    assert set(summary["accounting"]["outcomes"]) == set(OUTCOMES)


def _mutate(lines: list[str], index: int, **changes: Any) -> list[str]:
    document = json.loads(lines[index])
    document.update(changes)
    copied = list(lines)
    copied[index] = json.dumps(document)
    return copied


def _first(lines: list[str], kind: str, **match: Any) -> int:
    for index, line in enumerate(lines):
        document = json.loads(line)
        if document["record"] == kind and all(
            document.get(key) == value for key, value in match.items()
        ):
            return index
    raise AssertionError(f"no {kind} record matching {match}")


RAW_CORRUPTIONS = [
    ("benchmark", lambda rows: _mutate(rows, 0, productionBenchmark=True), "benchmark"),
    ("capacity", lambda rows: _mutate(rows, 0, portableCapacityClaim=True), "portable"),
    ("dropped boundary", lambda rows: _mutate(rows, 0, boundary="fast"), "boundary"),
    (
        "real labelled synthetic",
        lambda rows: _mutate(rows, 0, evidenceClass="synthetic"),
        "wrong evidence class",
    ),
    (
        "ceiling raised",
        lambda rows: _mutate(rows, 0, certificationCeiling="C3"),
        "ceiling",
    ),
    ("unknown mode", lambda rows: _mutate(rows, 0, mode="benchmark"), "mode"),
    (
        "a gap",
        lambda rows: (
            rows[: _first(rows, "request", sequence=7)]
            + rows[_first(rows, "request", sequence=7) + 1 :]
        ),
        "dispatched",
    ),
    (
        "a repeat",
        lambda rows: _mutate(rows, _first(rows, "request", sequence=8), sequence=7),
        "gap or a repeat",
    ),
    (
        "phase count",
        lambda rows: _mutate(rows, _first(rows, "phase", levelId="c2"), dispatched=5),
        "says it dispatched",
    ),
    (
        "past ceiling",
        lambda rows: _mutate(
            rows, _first(rows, "phase", levelId="c2"), requestCeiling=5
        ),
        "past its ceiling",
    ),
    (
        "request under another phase",
        lambda rows: _mutate(rows, _first(rows, "request", sequence=10), levelId="c4"),
        "not under its own phase",
    ),
    (
        "tokens on a failure",
        lambda rows: _mutate(
            rows, _first(rows, "request", sequence=4), outputTokens=12
        ),
        "counts tokens",
    ),
    (
        "worker outside concurrency",
        lambda rows: _mutate(rows, _first(rows, "request", sequence=5), worker=1),
        "worker",
    ),
    (
        "free text in a code",
        lambda rows: _mutate(
            rows, _first(rows, "request", sequence=4), errorCode="Bad Text"
        ),
        "plain token",
    ),
    (
        "end disagrees",
        lambda rows: _mutate(rows, -1, dispatched=99),
        "end record disagrees",
    ),
    ("end state", lambda rows: _mutate(rows, -1, state="great"), "unsupported state"),
    ("no end", lambda rows: rows[:-1], "start with run and end with end"),
    (
        "unknown record",
        lambda rows: [*rows[:-1], '{"record":"note"}', rows[-1]],
        "kind",
    ),
    (
        "unknown outcome",
        lambda rows: _mutate(rows, 2, outcome="slow"),
        "phase or outcome",
    ),
    ("not json", lambda rows: [*rows[:-1], "{", rows[-1]], "not valid JSON"),
]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [case[1:] for case in RAW_CORRUPTIONS],
    ids=[case[0] for case in RAW_CORRUPTIONS],
)
def test_a_raw_record_set_that_does_not_balance_is_refused(
    mutation: Any, message: str
) -> None:
    lines = mutation(completed_lines())
    with pytest.raises(LoadError, match=message):
        parse_raw("\n".join(lines) + "\n")


def test_a_real_record_set_must_name_a_supported_provider() -> None:
    lines = completed_lines()
    header = json.loads(lines[0])
    header["environment"]["facts"]["provider"] = "minikube"
    with pytest.raises(LoadError, match="supported provider"):
        parse_raw("\n".join([json.dumps(header), *lines[1:]]))


def test_a_synthetic_record_set_may_not_name_a_provider() -> None:
    lines = raw_lines(run(quick(), FakeTransport(), mode=MODE_REHEARSAL))
    parse_raw("\n".join(lines))
    header = json.loads(lines[0])
    header["environment"]["facts"] = valid_facts()
    with pytest.raises(LoadError, match="may not name a provider"):
        parse_raw("\n".join([json.dumps(header), *lines[1:]]))


# --------------------------------------------------------------------------
# The summary
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sample", "percentile", "expected"),
    [
        ([5], 99, 5),
        ([1, 2, 3, 4], 50, 2),
        ([1, 2, 3, 4], 51, 3),
        (list(range(1, 101)), 95, 95),
        (list(range(1, 101)), 99, 99),
        ([40, 10, 30, 20], 95, 40),
    ],
)
def test_percentiles_are_nearest_rank(
    sample: list[int], percentile: int, expected: int
) -> None:
    assert percentile_ms(sample, percentile) == expected


@pytest.mark.parametrize(("sample", "percentile"), [([], 50), ([1], 0), ([1], 100)])
def test_a_percentile_outside_its_domain_is_refused(
    sample: list[int], percentile: int
) -> None:
    with pytest.raises(LoadError):
        percentile_ms(sample, percentile)


def test_a_level_summary_counts_latency_of_successes_only_in_integer_rates() -> None:
    clock = FakeClock()
    latencies = {3: 1.0, 4: 2.0, 5: 3.0, 6: 4.0}

    def answer(sequence: int) -> HttpAnswer:
        clock.advance(latencies.get(sequence, 0.5))
        if sequence == 6:
            return HttpAnswer(503, refusal("model-not-ready"))
        return HttpAnswer(200, completion())

    profile = quick(
        max_requests_per_level=4, levels=(core.Level("c1", 1),), warmup_requests=3
    )
    result = run(profile, FakeTransport(answer), clock=clock)
    level = summarize(run_to_raw(result))["levels"][0]
    assert level["dispatched"] == 4
    assert level["successful"] == 3
    assert level["outcomes"][OUTCOME_HTTP_ERROR] == 1
    assert level["latencyOfSuccesses"] == {
        "p50Ms": 2000,
        "p95Ms": 3000,
        "p99Ms": 3000,
        "minMs": 1000,
        "maxMs": 3000,
    }
    assert level["windowMs"] == 10_000
    assert level["successfulRequestsPerSecondMilli"] == 300
    assert level["outputTokensPerSecondMilli"] == 5100
    assert level["tokens"] == {"inputTotal": 90, "outputTotal": 51}


# --------------------------------------------------------------------------
# The rehearsal and its committed example
# --------------------------------------------------------------------------

#: What the stub's fixed schedule makes of the committed profile's rehearsal.
EXPECTED_REHEARSAL = {
    "warmup": {
        "dispatched": 3,
        OUTCOME_SUCCESS: 3,
        OUTCOME_HTTP_ERROR: 0,
        OUTCOME_INVALID: 0,
    },
    "c1": {
        "dispatched": 12,
        OUTCOME_SUCCESS: 10,
        OUTCOME_HTTP_ERROR: 1,
        OUTCOME_INVALID: 1,
    },
    "c2": {
        "dispatched": 12,
        OUTCOME_SUCCESS: 9,
        OUTCOME_HTTP_ERROR: 2,
        OUTCOME_INVALID: 1,
    },
    "c4": {
        "dispatched": 12,
        OUTCOME_SUCCESS: 10,
        OUTCOME_HTTP_ERROR: 1,
        OUTCOME_INVALID: 1,
    },
}


def _phase_counts(summary: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {
        phase["levelId"]: {
            "dispatched": phase["dispatched"],
            OUTCOME_SUCCESS: phase["outcomes"][OUTCOME_SUCCESS],
            OUTCOME_HTTP_ERROR: phase["outcomes"][OUTCOME_HTTP_ERROR],
            OUTCOME_INVALID: phase["outcomes"][OUTCOME_INVALID],
        }
        for phase in [summary["warmup"], *summary["levels"]]
    }


def test_the_stub_schedule_is_a_fixed_function_of_the_sequence() -> None:
    assert [n for n in range(39) if stub_answer(n, MODEL)[0] == 503] == [8, 17, 26, 35]
    assert [
        n
        for n in range(39)
        if stub_answer(n, MODEL)[0] == 200 and stub_answer(n, MODEL)[1]["usage"] is None
    ] == [12, 25, 38]


def test_a_rehearsal_over_loopback_http_produces_the_scheduled_accounting() -> None:
    profile = rehearsal_profile(PROFILE)
    with stub_server(profile) as base_url:
        result = execute(
            profile,
            base_url=base_url,
            mode=MODE_REHEARSAL,
            confirmed=False,
            facts=None,
            host=HOST,
        )
    lines = raw_lines(result)
    text = "\n".join(lines)
    assert STUB_COMPLETION_TEXT not in text
    assert FIXTURE_TEXT not in text
    raw = parse_raw(text)
    summary = summarize(raw)
    assert summary["evidenceClass"] == "synthetic"
    assert summary["certificationCeiling"] == "C1"
    assert summary["environment"]["facts"] is None
    assert summary["end"]["state"] == END_COMPLETED
    assert _phase_counts(summary) == EXPECTED_REHEARSAL


def test_the_committed_rehearsal_example_is_the_summary_of_its_raw_records() -> None:
    raw = parse_raw(EXAMPLE_RAW.read_text(encoding="utf-8"))
    assert render_summary(summarize(raw)) == EXAMPLE_SUMMARY.read_text(encoding="utf-8")


def test_the_committed_rehearsal_example_is_synthetic_and_holds_no_content() -> None:
    text = EXAMPLE_RAW.read_text(encoding="utf-8")
    assert STUB_COMPLETION_TEXT not in text
    assert FIXTURE_TEXT not in text
    summary = json.loads(EXAMPLE_SUMMARY.read_text(encoding="utf-8"))
    assert summary["mode"] == MODE_REHEARSAL
    assert summary["evidenceClass"] == "synthetic"
    assert summary["evidenceLabel"] == "synthetic rehearsal"
    assert summary["environment"]["facts"] is None
    assert summary["environment"]["target"]["kind"] == "in-process-stub"
    assert summary["profile"]["profileSha256"] == PROFILE.profile_sha256
    assert _phase_counts(summary) == EXPECTED_REHEARSAL


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------


def test_check_validates_offline_and_prints_the_profile(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["check"]) == cli.EXIT_OK
    output = capsys.readouterr().out
    assert "inferops-llm-load 1.0.0" in output
    assert "c1=1, c2=2, c4=4" in output
    assert "not started" in output


@pytest.mark.parametrize(
    "argv",
    [
        ["run"],
        ["run", "--target-url", "http://127.0.0.1:18091"],
        [
            "run",
            "--target-url",
            "http://127.0.0.1:18091",
            "--environment-facts",
            "facts.json",
        ],
        ["rehearse", "--confirm-real-load"],
        ["rehearse", "--target-url", "http://127.0.0.1:18091"],
        ["summarize"],
    ],
)
def test_the_command_line_refuses_an_incomplete_invocation(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(argv) == cli.EXIT_REFUSED
    assert "REFUSED llm load" in capsys.readouterr().err


def test_run_refuses_a_non_loopback_target_before_sending_anything(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    facts = tmp_path / "facts.json"
    facts.write_text(json.dumps(valid_facts()), encoding="utf-8")
    argv = [
        "run",
        "--target-url",
        "http://10.0.0.5:8090",
        "--environment-facts",
        str(facts),
        "--confirm-real-load",
    ]
    assert cli.main(argv) == cli.EXIT_REFUSED
    assert "must name 127.0.0.1" in capsys.readouterr().err


# --------------------------------------------------------------------------
# The guide and the ignore rules
# --------------------------------------------------------------------------


def test_the_guide_publishes_the_committed_defaults_and_vocabulary() -> None:
    guide = GUIDE_PATH.read_text(encoding="utf-8")
    for outcome in OUTCOMES:
        assert f"`{outcome}`" in guide
    for field in FACT_FIELDS:
        assert f'"{field}"' in guide
    for phrase in (
        "`llm-load-single-turn-v1`",
        "| Warm-up | 3 requests at concurrency 1 |",
        "| Levels | `c1` = 1, `c2` = 2, `c4` = 4 |",
        "| Level bound | 180 s or 60 requests, whichever is reached first |",
        "| Request deadline | 150,000 ms |",
        "| Worst case | 1,460 s |",
        "python -m tools.llm_load check",
        "python -m tools.llm_load rehearse",
        "python -m tools.llm_load run",
        "python -m tools.llm_load summarize",
        "--confirm-real-load",
        "not a benchmark",
    ):
        assert phrase in guide, phrase


def test_the_raw_results_directory_is_ignored_by_version_control() -> None:
    ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/.cache/inferops/load/" in ignore


def test_the_validation_record_states_the_example_is_synthetic() -> None:
    record = VALIDATION_RECORD.read_text(encoding="utf-8")
    assert "synthetic" in record
    assert "No real load run was performed" in record


# --------------------------------------------------------------------------
# The HTTP transport, over a real loopback socket
# --------------------------------------------------------------------------


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_: Any) -> None:
        return None

    def _reply(self, status: int, payload: bytes, **headers: str) -> None:
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path == "/slow":
            time.sleep(1.0)
            self._reply(200, b"{}")
        elif self.path == "/refuse":
            self._reply(503, json.dumps(refusal("model-not-ready")).encode())
        elif self.path == "/redirect":
            self._reply(302, b"", Location="http://10.0.0.5/elsewhere")
        elif self.path == "/huge":
            self._reply(
                200, b'{"x":"' + b"a" * (core.MAXIMUM_RESPONSE_BYTES + 10) + b'"}'
            )
        else:
            self._reply(200, json.dumps(completion()).encode())


@pytest.fixture
def loopback() -> Any:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_the_transport_parses_a_success_and_a_canonical_refusal(loopback: str) -> None:
    ok = core.http_transport("POST", f"{loopback}/ok", {"a": 1}, {}, 5)
    assert ok.status == 200
    assert isinstance(ok.body, dict)
    refused = core.http_transport("POST", f"{loopback}/refuse", {"a": 1}, {}, 5)
    assert refused.status == 503
    assert isinstance(refused.body, dict)
    assert refused.body["code"] == "model-not-ready"


def test_the_transport_reports_a_client_timeout_as_a_timeout(loopback: str) -> None:
    with pytest.raises(TransportTimeout):
        core.http_transport("POST", f"{loopback}/slow", {"a": 1}, {}, 0.2)


def test_the_transport_reports_a_refused_connection_as_a_transport_failure() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    # The deadline is generous on purpose. Windows retries a connection to a closed
    # loopback port for about two seconds before refusing it, so a deadline shorter
    # than that reports the refusal as a timeout. The guide records this.
    with pytest.raises(TransportFailure):
        core.http_transport("POST", f"http://127.0.0.1:{port}/", {"a": 1}, {}, 15)


def test_the_transport_never_follows_a_redirect(loopback: str) -> None:
    answer = core.http_transport("POST", f"{loopback}/redirect", {"a": 1}, {}, 5)
    assert answer.status == 302
    result = classify(PROFILE, answer=answer, failure=None, latency_ms=1)
    assert result.outcome == OUTCOME_HTTP_ERROR


def test_the_transport_refuses_to_parse_an_oversized_body(loopback: str) -> None:
    answer = core.http_transport("POST", f"{loopback}/huge", {"a": 1}, {}, 5)
    assert answer.status == 200
    assert answer.body is None


def test_the_transport_ignores_proxy_variables(
    loopback: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://10.255.255.1:9")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    assert core.http_transport("POST", f"{loopback}/ok", {"a": 1}, {}, 5).status == 200


def test_a_refusal_keeps_its_condition_so_draining_and_unreachable_differ() -> None:
    draining = classify(
        PROFILE,
        answer=HttpAnswer(
            503, refusal("capability-unavailable", condition="deployment-draining")
        ),
        failure=None,
        latency_ms=5,
    )
    unreachable = classify(
        PROFILE,
        answer=HttpAnswer(503, refusal("capability-unavailable")),
        failure=None,
        latency_ms=5,
    )
    assert draining.error_code == unreachable.error_code == "capability-unavailable"
    assert draining.error_condition == "deployment-draining"
    assert unreachable.error_condition == "runtime-unreachable"
    empty = classify(PROFILE, answer=HttpAnswer(504, None), failure=None, latency_ms=5)
    assert (empty.error_code, empty.error_condition) == (None, None)


def test_a_lost_target_stops_the_run_instead_of_filling_every_level() -> None:
    transport = FakeTransport(
        lambda sequence: (
            TransportFailure() if sequence >= 5 else HttpAnswer(200, completion())
        )
    )
    result = run(quick(max_requests_per_level=60), transport)
    assert result.end_state == END_TRANSPORT_LOST
    failures = [r for r in result.records if r.outcome == OUTCOME_TRANSPORT]
    assert len(failures) == MAXIMUM_CONSECUTIVE_TRANSPORT_ERRORS
    assert [phase.level_id for phase in result.phases] == ["warmup", "c1"]
    assert result.phases[-1].stop_reason == "transport-lost"
    raw = run_to_raw(result)
    assert summarize(raw)["usable"] is False


def test_transport_errors_that_are_not_consecutive_do_not_stop_the_run() -> None:
    transport = FakeTransport(
        lambda sequence: (
            TransportFailure()
            if sequence >= 3 and sequence % 3 == 0
            else HttpAnswer(200, completion())
        )
    )
    result = run(quick(levels=(core.Level("c1", 1),)), transport)
    assert result.end_state == END_COMPLETED
    assert sum(r.outcome == OUTCOME_TRANSPORT for r in result.records) == 2


def test_platform_refusals_in_a_row_never_stop_the_run() -> None:
    transport = FakeTransport(
        lambda sequence: (
            HttpAnswer(503, refusal("model-not-ready"))
            if sequence >= 3
            else HttpAnswer(200, completion())
        )
    )
    result = run(quick(max_requests_per_level=20), transport)
    assert result.end_state == END_COMPLETED
    assert [phase.dispatched for phase in result.phases] == [3, 20, 20, 20]


def test_a_worker_failure_under_concurrency_stops_its_siblings() -> None:
    gate = threading.Event()

    def answer(sequence: int) -> Any:
        if sequence == 5:
            gate.set()
            return RuntimeError("boom")
        if sequence > 5:
            gate.wait(timeout=5)
            time.sleep(0.01)
        return HttpAnswer(200, completion())

    profile = quick(max_requests_per_level=500, levels=(core.Level("c4", 4),))
    transport = FakeTransport(answer)
    with pytest.raises(RuntimeError, match="boom"):
        run(profile, transport)
    # Each sibling may finish the one request it had already dispatched and then
    # stops; none keeps dispatching toward the 500-request ceiling.
    assert len(transport.sequences) < 3 + 20


def test_the_level_summary_counts_each_http_status() -> None:
    transport = FakeTransport(
        lambda sequence: (
            HttpAnswer(504, None)
            if sequence in (4, 6)
            else HttpAnswer(200, completion())
        )
    )
    result = run(quick(levels=(core.Level("c1", 1),)), transport)
    level = summarize(run_to_raw(result))["levels"][0]
    assert level["httpStatuses"] == {"200": 4, "504": 2}


@pytest.mark.parametrize(
    ("end_state", "expected"),
    [
        (END_COMPLETED, cli.EXIT_OK),
        (END_WARMUP_FAILED, cli.EXIT_NOT_USABLE),
        (END_ABORTED, cli.EXIT_REFUSED),
        (END_TRANSPORT_LOST, cli.EXIT_REFUSED),
        (END_INTERRUPTED, cli.EXIT_INTERRUPTED),
    ],
)
def test_the_command_line_exit_code_follows_the_end_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    end_state: str,
    expected: int,
) -> None:
    finished = replace(
        run(quick(), FakeTransport(), mode=MODE_REHEARSAL), end_state=end_state
    )
    monkeypatch.setattr(cli, "execute", lambda *args, **kwargs: finished)
    monkeypatch.setattr(
        cli, "write_raw", lambda *args, **kwargs: tmp_path / "raw.jsonl"
    )
    monkeypatch.setattr(
        cli, "write_summary", lambda *args, **kwargs: tmp_path / "summary.json"
    )
    assert cli.main(["rehearse"]) == expected
    assert end_state in capsys.readouterr().out
