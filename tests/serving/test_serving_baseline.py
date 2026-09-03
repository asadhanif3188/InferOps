"""The registered serving baseline: its descriptor, its parsing, and its maths.

Every test here reads committed files or synthetic fixtures. No container is
started, no model byte is read, no runtime socket is opened, and no request
leaves the process: the request seam is injected everywhere it is exercised.
These are local-static and synthetic checks. Nothing here is a serving
measurement, and no result produced by this suite may be cited as one.

The suite is deliberately heaviest on two things. The first is refusal: a
descriptor that drifts from the composition, the profile, or the model record
must fail at load rather than during a run somebody has already paid for. The
second is the summary, because the summary is the artifact a later change
publishes, and an arithmetic error there is an error in a published record.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from inferops.api.validation import parse_chat_completion
from tools.runtime_packaging import CommandResult, load_runtime_package
from tools.serving_baseline import (
    EXPERIMENT_PATH,
    BaselineError,
    BaselineRefused,
    BaselineRun,
    Environment,
    Experiment,
    RequestRecord,
    ResourceSample,
    capture_environment,
    load_experiment,
    parse_memory_bytes,
    percentile_ms,
    read_raw,
    result_directory,
    sample_resources,
    send_request,
    summarize,
    write_raw,
    write_summary,
)
from tools.serving_baseline.__main__ import main
from tools.serving_baseline.core import (
    OUTCOME_REFUSED,
    OUTCOME_SUCCESS,
    OUTCOME_TRANSPORT,
    PHASE_MEASURED,
    PHASE_WARMUP,
    PostResponse,
    execute,
)

pytestmark = pytest.mark.docs

EXPERIMENT_DOCUMENT: dict[str, Any] = json.loads(
    EXPERIMENT_PATH.read_text(encoding="utf-8")
)


# --------------------------------------------------------------------------
# Fixtures and doubles
# --------------------------------------------------------------------------


class ScriptedRunner:
    """Return one result per command and retain the exact argument vectors."""

    def __init__(self, results: list[CommandResult]) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, ...]] = []

    def run(self, arguments: Any) -> CommandResult:
        self.calls.append(tuple(arguments))
        if not self.results:
            raise AssertionError(f"unexpected command: {arguments}")
        return self.results.pop(0)


class FakeClock:
    """A clock that advances a fixed amount every time it is read."""

    def __init__(self, step: float = 0.25) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        value = self.now
        self.now += self.step
        return value


class _FakeServer:
    """Records whether `execute` asked it to stop before `on_ready` returned.

    A real `run_foreground` blocks on `server.join()` after `on_ready` returns,
    so a bounded run that never requests its own stop would hang forever. This
    double makes that requirement a test assertion rather than a fact only
    visible by running the real composition.
    """

    def __init__(self) -> None:
        self.stop_requested = False

    def request_stop(self) -> None:
        self.stop_requested = True


def _recording_server_factory(servers: list[_FakeServer]) -> Any:
    def server_factory(application: Any, **keywords: Any) -> _FakeServer:
        server = _FakeServer()
        servers.append(server)
        return server

    return server_factory


def written_experiment(tmp_path: Path, document: dict[str, Any]) -> Path:
    path = tmp_path / "local-baseline.v1.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def mutated(**changes: Any) -> dict[str, Any]:
    """A copy of the committed descriptor with one nested path replaced.

    Keys are dotted paths, so a test names the exact field it is breaking and a
    reader of the failure knows which rule fired without reading the helper.
    """
    document = copy.deepcopy(EXPERIMENT_DOCUMENT)
    for dotted, value in changes.items():
        target: Any = document
        parts = dotted.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    return document


ENVIRONMENT = Environment(
    operating_system="Linux",
    release="6.1.0",
    architecture="x86_64",
    processor_family="x86_64",
    logical_cpus=8,
    total_memory_bytes=16 * 1024**3,
    free_disk_bytes=64 * 1024**3,
    python_version="3.12.12",
    container_engine_version="27.0.0",
    accelerator="none; CPU only",
    image_reference="ghcr.io/example/runtime@sha256:" + "a" * 64,
    model_repository="Qwen/Qwen3-1.7B-GGUF",
    model_revision="9" * 40,
    model_artifact_sha256="sha256:" + "b" * 64,
    runtime_source_revision="7" * 40,
)


def request_record(
    sequence: int,
    latency_ms: int,
    *,
    phase: str = PHASE_MEASURED,
    outcome: str = OUTCOME_SUCCESS,
    output_tokens: int | None = 10,
    input_tokens: int | None = 20,
) -> RequestRecord:
    return RequestRecord(
        sequence=sequence,
        phase=phase,
        outcome=outcome,
        status=200 if outcome == OUTCOME_SUCCESS else 503,
        latency_ms=latency_ms,
        input_tokens=input_tokens if outcome == OUTCOME_SUCCESS else None,
        output_tokens=output_tokens if outcome == OUTCOME_SUCCESS else None,
        adapter_kind="real" if outcome != OUTCOME_TRANSPORT else None,
        model_ref="qwen3-1-7b-q8-0" if outcome != OUTCOME_TRANSPORT else None,
        error_code=None if outcome == OUTCOME_SUCCESS else "model_not_ready",
    )


def run_of(
    latencies: list[int],
    *,
    warmup: int = 2,
    window_ms: int = 10_000,
    samples: tuple[ResourceSample, ...] = (),
) -> BaselineRun:
    records = [
        request_record(index, 9_999, phase=PHASE_WARMUP) for index in range(warmup)
    ]
    records.extend(
        request_record(warmup + index, latency)
        for index, latency in enumerate(latencies)
    )
    return BaselineRun(
        experiment_id="inferops-local-serving-baseline",
        evidence_class="local-real-cpu",
        environment=ENVIRONMENT,
        model_load_ms=42_000,
        api_ready_ms=120,
        records=tuple(records),
        samples=samples,
        measured_window_ms=window_ms,
    )


@pytest.fixture
def experiment() -> Experiment:
    return load_experiment()


# --------------------------------------------------------------------------
# The committed descriptor
# --------------------------------------------------------------------------


def test_the_committed_descriptor_loads_and_agrees_with_the_composition(
    experiment: Experiment,
) -> None:
    """The registered experiment is consistent with everything it depends on.

    This is the only test that reads the real descriptor without mutating it, and
    it is the one that fails if the composition, the profile, the package, or the
    model record moves underneath the baseline.
    """
    assert experiment.experiment_id == "inferops-local-serving-baseline"
    assert experiment.evidence_class == "local-real-cpu"
    assert experiment.certification_ceiling == "C2"
    assert experiment.production_benchmark is False
    assert experiment.required_adapter_kind == "real"
    assert experiment.fixture.request_path == "/v1/chat/completions"
    assert experiment.fixture.stream is False
    assert experiment.concurrency == experiment.parallel_slots == 1
    assert experiment.reported_percentiles == (50, 95, 99)
    assert experiment.percentile_method == "nearest-rank"
    assert experiment.result_directory == Path(".cache/inferops/baseline")


def test_the_fixture_body_is_the_frozen_request_subset(
    experiment: Experiment,
) -> None:
    """A body outside the accepted subset would be refused by the API itself."""
    body = experiment.fixture.body()
    assert set(body) == {"model", "messages", "stream"}
    assert body["stream"] is False
    assert all(set(message) == {"role", "content"} for message in body["messages"])
    assert [message["role"] for message in body["messages"]] == ["user"]


def test_the_committed_fixture_is_accepted_by_the_real_api_validator(
    experiment: Experiment,
) -> None:
    """`V1-S2-005-PR2` found a fixture that passed every offline check here and
    was still refused by the real API on every one of thirty measured
    requests, because nothing exercised the real validator against it. This
    pins the fixture against `inferops.api.validation.parse_chat_completion`
    directly, the same reader the API uses at request time, so a fixture the
    API would refuse fails the suite rather than an authorized run.
    """
    parse_chat_completion(
        json.dumps(experiment.fixture.body()).encode("utf-8"),
        served_model=experiment.fixture.model,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("experimentId", "something-else"),
        ("evidenceClass", "synthetic"),
        ("evidenceLabel", "production benchmark"),
        ("certificationCeiling", "C3"),
        ("schemaVersion", "inferops.io/v2"),
    ],
)
def test_an_identity_that_drifts_is_refused(
    tmp_path: Path, field: str, value: str
) -> None:
    with pytest.raises(BaselineError, match="identity is unsupported"):
        load_experiment(written_experiment(tmp_path, mutated(**{field: value})))


def test_an_experiment_declaring_itself_a_benchmark_is_refused(
    tmp_path: Path,
) -> None:
    """The one refusal the project boundaries require by name."""
    document = written_experiment(tmp_path, mutated(productionBenchmark=True))
    with pytest.raises(BaselineError, match="production benchmark"):
        load_experiment(document)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fixture.requestPath", "/v1/completions"),
        ("fixture.stream", True),
        ("fixture.model", "some-other-model"),
    ],
)
def test_a_fixture_that_does_not_match_the_served_model_is_refused(
    tmp_path: Path, field: str, value: Any
) -> None:
    with pytest.raises(BaselineError, match="fixture does not match"):
        load_experiment(written_experiment(tmp_path, mutated(**{field: value})))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("generation.maxOutputTokens", 256),
        ("generation.temperature", 0.7),
        ("generation.contextSizeTokens", 8192),
        ("generation.parallelSlots", 2),
    ],
)
def test_generation_settings_that_drift_from_the_profile_are_refused(
    tmp_path: Path, field: str, value: Any
) -> None:
    """A baseline measured under settings the runtime is not pinned to is noise."""
    with pytest.raises(BaselineError, match="generation settings have drifted"):
        load_experiment(written_experiment(tmp_path, mutated(**{field: value})))


def test_a_concurrency_above_the_runtimes_parallel_slots_is_refused(
    tmp_path: Path,
) -> None:
    """The selected runtime serves one slot; four in-flight requests queue.

    Measuring at a concurrency the runtime cannot serve produces a latency
    distribution dominated by queueing, which is a measurement of the queue.
    """
    document = mutated(**{"execution.concurrency": 4})
    with pytest.raises(BaselineError, match="concurrency must equal"):
        load_experiment(written_experiment(tmp_path, document))


def test_a_request_envelope_contradicting_the_composition_is_refused(
    tmp_path: Path,
) -> None:
    document = mutated(**{"execution.requestTimeoutMs": 5_000})
    with pytest.raises(BaselineError, match="contradicts the composition"):
        load_experiment(written_experiment(tmp_path, document))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("execution.measuredRequests", 5_000),
        ("execution.warmupRequests", 5_000),
        ("success.minimumSuccessfulRequests", 1),
        ("execution.resourceSampleEveryRequests", 999),
    ],
)
def test_an_unsupported_execution_envelope_is_refused(
    tmp_path: Path, field: str, value: Any
) -> None:
    """Both phases are bounded by a constant, not by the record bounding them.

    A warm-up request costs what a measured one costs, so capping only the phase
    whose numbers get published would leave the expensive half of a run editable
    from the descriptor.
    """
    with pytest.raises(BaselineError, match="execution envelope is unsupported"):
        load_experiment(written_experiment(tmp_path, mutated(**{field: value})))


@pytest.mark.parametrize("count", [0, -1])
def test_a_warm_up_that_does_not_happen_is_refused(tmp_path: Path, count: int) -> None:
    """Zero warm-up means the first measured request measures the cold start."""
    document = mutated(**{"execution.warmupRequests": count})
    with pytest.raises(BaselineError, match="at least 1"):
        load_experiment(written_experiment(tmp_path, document))


@pytest.mark.parametrize("seconds", [1, 60, 100_000])
def test_a_duration_bound_that_cannot_stop_the_sequence_is_refused(
    tmp_path: Path, seconds: int
) -> None:
    """Below one timeout it stops before anything finishes; above the whole
    budget it can never fire. Both make the stop condition a decoration."""
    document = mutated(**{"execution.maxDurationSeconds": seconds})
    with pytest.raises(BaselineError, match="cannot stop this request sequence"):
        load_experiment(written_experiment(tmp_path, document))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("success.requiredAdapterKind", "mock"),
        ("success.requiredModelRef", "not-the-model"),
        ("success.requiredCompletionStatus", 202),
    ],
)
def test_success_criteria_that_would_accept_a_non_real_answer_are_refused(
    tmp_path: Path, field: str, value: Any
) -> None:
    with pytest.raises(BaselineError, match="explicitly real answer"):
        load_experiment(written_experiment(tmp_path, mutated(**{field: value})))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("results.directory", ".cache/elsewhere"),
        ("results.rawFile", "../raw.jsonl"),
        ("results.summaryFile", "nested/summary.json"),
        ("results.rawFormat", "text/csv"),
        ("results.summaryFormat", "text/plain"),
        ("results.percentileMethod", "linear-interpolation"),
        ("results.reportedPercentiles", [50, 90]),
    ],
)
def test_an_unsupported_result_layout_is_refused(
    tmp_path: Path, field: str, value: Any
) -> None:
    with pytest.raises(BaselineError, match="result layout is unsupported"):
        load_experiment(written_experiment(tmp_path, mutated(**{field: value})))


def test_an_unknown_member_is_refused(tmp_path: Path) -> None:
    document = copy.deepcopy(EXPERIMENT_DOCUMENT)
    document["publishHeadlineFigure"] = True
    with pytest.raises(BaselineError, match="missing or unsupported members"):
        load_experiment(written_experiment(tmp_path, document))


def test_a_missing_member_is_refused(tmp_path: Path) -> None:
    document = copy.deepcopy(EXPERIMENT_DOCUMENT)
    del document["fixture"]["messages"]
    with pytest.raises(BaselineError, match="missing or unsupported members"):
        load_experiment(written_experiment(tmp_path, document))


def test_an_assistant_message_in_the_fixture_is_refused(tmp_path: Path) -> None:
    """The fixture states the request; an assistant turn states the answer."""
    document = mutated(
        **{"fixture.messages": [{"role": "assistant", "content": "hello"}]}
    )
    with pytest.raises(BaselineError, match="must be system or user"):
        load_experiment(written_experiment(tmp_path, document))


def test_a_fixture_the_real_api_would_refuse_is_refused_offline(
    tmp_path: Path,
) -> None:
    """`V1-S2-005-PR2`'s failure, reproduced as a refusal at load time.

    A two-message fixture is individually well-formed — each message has a
    valid role and content — so no check above this one would have caught it.
    Only asking the real API surface whether it would accept the body does,
    and that is exactly what let the original fixture reach an authorized run
    and be refused thirty times in a row.
    """
    document = mutated(
        **{
            "fixture.messages": [
                {"role": "system", "content": "You are a terse assistant."},
                {"role": "user", "content": "Name three things."},
            ]
        }
    )
    with pytest.raises(BaselineError, match="refused by the InferOps API"):
        load_experiment(written_experiment(tmp_path, document))


def test_an_unreadable_descriptor_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "local-baseline.v1.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(BaselineError, match="unreadable"):
        load_experiment(path)


# --------------------------------------------------------------------------
# Percentiles
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("percentile", "expected"),
    [(50, 50), (95, 95), (99, 99), (1, 1), (10, 10)],
)
def test_nearest_rank_returns_an_observed_value(percentile: int, expected: int) -> None:
    """One to one hundred: the nearest-rank Pn is exactly n, by construction."""
    assert percentile_ms(list(range(1, 101)), percentile) == expected


def test_a_percentile_is_always_a_value_that_was_actually_observed() -> None:
    """The property the method was chosen for, over a sample that is not linear."""
    latencies = [3, 900, 12, 12, 4000, 55, 55, 7, 88, 1200]
    for percentile in (50, 95, 99):
        assert percentile_ms(latencies, percentile) in latencies


def test_percentiles_are_order_independent() -> None:
    latencies = [400, 100, 900, 200, 300]
    shuffled = [900, 200, 400, 300, 100]
    assert [percentile_ms(latencies, p) for p in (50, 95, 99)] == [
        percentile_ms(shuffled, p) for p in (50, 95, 99)
    ]


def test_a_single_observation_is_every_percentile() -> None:
    assert [percentile_ms([77], p) for p in (50, 95, 99)] == [77, 77, 77]


def test_a_percentile_of_nothing_is_refused() -> None:
    with pytest.raises(BaselineError, match="at least one observation"):
        percentile_ms([], 50)


@pytest.mark.parametrize("percentile", [0, 100, -1, 150])
def test_a_percentile_outside_the_supported_range_is_refused(
    percentile: int,
) -> None:
    with pytest.raises(BaselineError, match="between 1 and 99"):
        percentile_ms([1, 2, 3], percentile)


# --------------------------------------------------------------------------
# The summary
# --------------------------------------------------------------------------


def test_the_summary_reports_the_registered_percentiles(
    experiment: Experiment,
) -> None:
    run = run_of(list(range(1, 31)))
    summary = summarize(experiment, run)
    assert summary["latency"]["p50Ms"] == 15
    assert summary["latency"]["p95Ms"] == 29
    assert summary["latency"]["p99Ms"] == 30
    assert summary["latency"]["minMs"] == 1
    assert summary["latency"]["maxMs"] == 30


def test_the_summary_excludes_warm_up_from_every_distribution(
    experiment: Experiment,
) -> None:
    """Warm-up requests carry a 9,999 ms latency in this fixture. If any of them
    reached the distribution, the maximum would be that number."""
    run = run_of([100] * 30, warmup=3)
    summary = summarize(experiment, run)
    assert summary["requests"]["warmup"] == 3
    assert summary["requests"]["measured"] == 30
    assert summary["latency"]["maxMs"] == 100
    assert summary["latency"]["p99Ms"] == 100


def test_the_summary_is_deterministic(experiment: Experiment) -> None:
    """The property a published summary rests on: same records, same document."""
    run = run_of([5, 3, 9, 1, 7] * 6)
    assert summarize(experiment, run) == summarize(experiment, run)


def test_the_summary_never_claims_to_be_a_benchmark(
    experiment: Experiment,
) -> None:
    summary = summarize(experiment, run_of([10] * 30))
    assert summary["productionBenchmark"] is False
    assert "not a production benchmark" in summary["notABenchmark"]
    assert summary["evidenceClass"] == "local-real-cpu"
    assert summary["certificationCeiling"] == "C2"


def test_the_summary_counts_failures_and_marks_the_criteria_unmet(
    experiment: Experiment,
) -> None:
    records = [request_record(index, 10) for index in range(28)]
    records.append(request_record(28, 10, outcome=OUTCOME_REFUSED))
    records.append(request_record(29, 10, outcome=OUTCOME_TRANSPORT))
    run = BaselineRun(
        experiment_id=experiment.experiment_id,
        evidence_class=experiment.evidence_class,
        environment=ENVIRONMENT,
        model_load_ms=1,
        api_ready_ms=1,
        records=tuple(records),
        samples=(),
        measured_window_ms=1_000,
    )
    summary = summarize(experiment, run)
    assert summary["requests"]["successful"] == 28
    assert summary["requests"]["failed"] == 2
    assert summary["requests"]["outcomes"] == {
        OUTCOME_SUCCESS: 28,
        OUTCOME_REFUSED: 1,
        OUTCOME_TRANSPORT: 1,
    }
    assert summary["successCriteria"]["met"] is False


def test_a_failed_request_contributes_no_latency_and_no_token(
    experiment: Experiment,
) -> None:
    """A refusal returns fast. Counting it would flatter every percentile."""
    records = [request_record(index, 500) for index in range(30)]
    records.append(request_record(30, 1, outcome=OUTCOME_REFUSED))
    run = BaselineRun(
        experiment_id=experiment.experiment_id,
        evidence_class=experiment.evidence_class,
        environment=ENVIRONMENT,
        model_load_ms=1,
        api_ready_ms=1,
        records=tuple(records),
        samples=(),
        measured_window_ms=1_000,
    )
    summary = summarize(experiment, run)
    assert summary["latency"]["minMs"] == 500
    assert summary["tokens"]["outputTotal"] == 30 * 10


def test_the_summary_reports_rates_as_integers(experiment: Experiment) -> None:
    """Thirty successes of ten output tokens over ten seconds."""
    run = run_of([100] * 30, window_ms=10_000)
    summary = summarize(experiment, run)
    assert summary["throughput"]["requestsPerSecondMilli"] == 3_000
    assert summary["throughput"]["outputTokensPerSecondMilli"] == 30_000
    assert isinstance(summary["throughput"]["requestsPerSecondMilli"], int)


def test_a_zero_length_window_reports_no_rate(experiment: Experiment) -> None:
    """A division that cannot be performed is absent, never zero or infinite."""
    summary = summarize(experiment, run_of([10] * 30, window_ms=0))
    assert summary["throughput"]["requestsPerSecondMilli"] is None
    assert summary["throughput"]["outputTokensPerSecondMilli"] is None


def test_absent_token_counts_are_reported_as_unavailable(
    experiment: Experiment,
) -> None:
    """Token usage is a declared adapter capability, not a guarantee."""
    records = tuple(
        request_record(index, 10, output_tokens=None, input_tokens=None)
        for index in range(30)
    )
    run = BaselineRun(
        experiment_id=experiment.experiment_id,
        evidence_class=experiment.evidence_class,
        environment=ENVIRONMENT,
        model_load_ms=1,
        api_ready_ms=1,
        records=records,
        samples=(),
        measured_window_ms=1_000,
    )
    summary = summarize(experiment, run)
    assert summary["tokens"]["available"] is False
    assert summary["tokens"]["outputTotal"] is None
    assert summary["throughput"]["outputTokensPerSecondMilli"] is None


def test_the_summary_reports_the_resource_peak(experiment: Experiment) -> None:
    samples = (
        ResourceSample(sequence=5, cpu_percent=180.5, memory_bytes=2_000_000_000),
        ResourceSample(sequence=10, cpu_percent=420.0, memory_bytes=2_400_000_000),
    )
    summary = summarize(experiment, run_of([10] * 30, samples=samples))
    assert summary["resources"]["samples"] == 2
    assert summary["resources"]["cpuPercentMax"] == 420.0
    assert summary["resources"]["memoryBytesMax"] == 2_400_000_000


def test_the_summary_carries_model_load_time_and_the_environment(
    experiment: Experiment,
) -> None:
    summary = summarize(experiment, run_of([10] * 30))
    assert summary["startup"]["modelLoadMs"] == 42_000
    assert summary["environment"]["logicalCpus"] == 8
    assert summary["environment"]["accelerator"] == "none; CPU only"
    assert summary["environment"]["modelRevision"] == "9" * 40


# --------------------------------------------------------------------------
# Raw persistence and round trip
# --------------------------------------------------------------------------


def test_a_raw_result_set_round_trips(experiment: Experiment, tmp_path: Path) -> None:
    """Write then read then summarize must equal summarize of the original.

    This is what allows a summary to be regenerated from committed records
    instead of taken on trust.
    """
    samples = (ResourceSample(sequence=4, cpu_percent=99.5, memory_bytes=1_000),)
    run = run_of([5, 10, 15] * 10, samples=samples)
    path = write_raw(experiment, run, repo_root=tmp_path)
    restored = read_raw(experiment, repo_root=tmp_path)
    assert restored.records == run.records
    assert restored.samples == run.samples
    assert restored.environment == run.environment
    assert restored.model_load_ms == run.model_load_ms
    assert restored.measured_window_ms == run.measured_window_ms
    assert summarize(experiment, restored) == summarize(experiment, run)
    assert path.name == experiment.raw_file


def test_every_raw_line_is_one_json_document(
    experiment: Experiment, tmp_path: Path
) -> None:
    path = write_raw(experiment, run_of([10] * 30), repo_root=tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    kinds = [json.loads(line)["record"] for line in lines]
    assert kinds[0] == "run"
    assert kinds.count("run") == 1
    assert kinds.count("request") == 32


def test_a_real_completion_body_never_reaches_the_raw_result_set(
    experiment: Experiment, tmp_path: Path
) -> None:
    """The record is timings and counts. It is never a transcript.

    A completion carrying real answer text is pushed through the request path and
    then written, because asserting the absence of text that no fixture ever
    supplied would pass however the discarding worked.
    """
    marker = "PALIMPSEST-ANSWER-TEXT-a4f1"
    body = completion()
    body["choices"] = [
        {
            "index": 0,
            "message": {"role": "assistant", "content": marker},
            "finish_reason": "stop",
        }
    ]

    def post(url, body_sent, headers, timeout):
        return PostResponse(200, body)

    record = send_request(
        experiment,
        composition_double(),
        sequence=0,
        phase=PHASE_MEASURED,
        post=post,
        clock=FakeClock(),
    )
    assert marker not in json.dumps(record.document())
    run = BaselineRun(
        experiment_id=experiment.experiment_id,
        evidence_class=experiment.evidence_class,
        environment=ENVIRONMENT,
        model_load_ms=1,
        api_ready_ms=1,
        records=(record,),
        samples=(),
        measured_window_ms=1_000,
    )
    text = write_raw(experiment, run, repo_root=tmp_path).read_text(encoding="utf-8")
    assert marker not in text
    assert "choices" not in text
    assert "finish_reason" not in text


def test_a_raw_result_set_retains_no_fixture_prompt(
    experiment: Experiment, tmp_path: Path
) -> None:
    """The request side of the same rule: the prompt is not written either."""
    path = write_raw(experiment, run_of([10] * 30), repo_root=tmp_path)
    text = path.read_text(encoding="utf-8")
    for message in experiment.fixture.messages:
        assert message["content"] not in text


def test_a_raw_record_set_claiming_to_be_a_benchmark_is_refused(
    experiment: Experiment, tmp_path: Path
) -> None:
    write_raw(experiment, run_of([10] * 30), repo_root=tmp_path)
    path = result_directory(experiment, tmp_path) / experiment.raw_file
    lines = path.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    header["productionBenchmark"] = True
    lines[0] = json.dumps(header)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(BaselineError, match="may not claim to be a benchmark"):
        read_raw(experiment, repo_root=tmp_path)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ('{"record":"unknown"}', "unsupported kind"),
        ("{ not json", "not valid JSON"),
        (
            '{"record":"request","phase":"cooldown","outcome":"success"}',
            "unsupported phase or outcome",
        ),
        (
            '{"record":"request","phase":"measured","outcome":"maybe"}',
            "unsupported phase or outcome",
        ),
    ],
)
def test_a_malformed_raw_record_is_refused(
    experiment: Experiment, tmp_path: Path, line: str, message: str
) -> None:
    write_raw(experiment, run_of([10] * 30), repo_root=tmp_path)
    path = result_directory(experiment, tmp_path) / experiment.raw_file
    path.write_text(path.read_text(encoding="utf-8") + line + "\n", encoding="utf-8")
    with pytest.raises(BaselineError, match=message):
        read_raw(experiment, repo_root=tmp_path)


def test_two_run_headers_are_refused(experiment: Experiment, tmp_path: Path) -> None:
    """Two runs in one file is two experiments summarized as one."""
    write_raw(experiment, run_of([10] * 30), repo_root=tmp_path)
    path = result_directory(experiment, tmp_path) / experiment.raw_file
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([*lines, lines[0]]) + "\n", encoding="utf-8")
    with pytest.raises(BaselineError, match="two run records"):
        read_raw(experiment, repo_root=tmp_path)


def test_an_empty_raw_result_set_is_refused(
    experiment: Experiment, tmp_path: Path
) -> None:
    directory = result_directory(experiment, tmp_path)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / experiment.raw_file).write_text("", encoding="utf-8")
    with pytest.raises(BaselineError, match="empty or too large"):
        read_raw(experiment, repo_root=tmp_path)


def test_a_raw_result_set_with_no_request_is_refused(
    experiment: Experiment, tmp_path: Path
) -> None:
    write_raw(experiment, run_of([10] * 30), repo_root=tmp_path)
    path = result_directory(experiment, tmp_path) / experiment.raw_file
    header = path.read_text(encoding="utf-8").splitlines()[0]
    path.write_text(header + "\n", encoding="utf-8")
    with pytest.raises(BaselineError, match="no run or no request"):
        read_raw(experiment, repo_root=tmp_path)


def test_the_summary_is_written_beside_the_records(
    experiment: Experiment, tmp_path: Path
) -> None:
    run = run_of([10] * 30)
    write_raw(experiment, run, repo_root=tmp_path)
    path = write_summary(experiment, summarize(experiment, run), repo_root=tmp_path)
    assert path.parent == result_directory(experiment, tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["productionBenchmark"] is False


def test_a_result_directory_outside_the_checkout_is_refused(
    tmp_path: Path,
) -> None:
    document = written_experiment(tmp_path, mutated(**{"results.directory": "/tmp"}))
    with pytest.raises(BaselineError, match="result layout is unsupported"):
        load_experiment(document)


# --------------------------------------------------------------------------
# One request, through an injected seam
# --------------------------------------------------------------------------


def composition_double() -> Any:
    from tools.local_composition import load_composition

    return load_composition()


def completion(adapter_kind: str = "real", model_ref: str = "qwen3-1-7b-q8-0") -> dict:
    return {
        "object": "chat.completion",
        "usage": {
            "prompt_tokens": 31,
            "completion_tokens": 64,
            "total_tokens": 95,
        },
        "x_inferops": {
            "requestId": "r",
            "correlationId": "c",
            "contractVersion": "inferops.io/v1alpha1",
            "adapterKind": adapter_kind,
            "modelRef": model_ref,
        },
    }


def test_a_real_completion_is_recorded_as_a_success(
    experiment: Experiment,
) -> None:
    posts: list[tuple[str, Any, Any, float]] = []

    def post(url, body, headers, timeout):
        posts.append((url, body, headers, timeout))
        return PostResponse(200, completion())

    record = send_request(
        experiment,
        composition_double(),
        sequence=7,
        phase=PHASE_MEASURED,
        post=post,
        clock=FakeClock(0.5),
    )
    assert record.outcome == OUTCOME_SUCCESS
    assert record.status == 200
    assert record.latency_ms == 500
    assert record.input_tokens == 31
    assert record.output_tokens == 64
    assert record.adapter_kind == "real"
    url, body, headers, timeout = posts[0]
    assert url.endswith("/v1/chat/completions")
    assert body == experiment.fixture.body()
    assert timeout == experiment.request_timeout_ms / 1000
    assert headers["X-InferOps-Request-ID"].endswith("0007")


def test_a_mock_answer_stops_the_baseline(experiment: Experiment) -> None:
    """The refusal the whole evidence scheme depends on: a mock answer may never
    be written into a record labelled local real runtime."""

    def post(url, body, headers, timeout):
        return PostResponse(200, completion(adapter_kind="mock"))

    with pytest.raises(BaselineRefused, match="mock answer"):
        send_request(
            experiment,
            composition_double(),
            sequence=0,
            phase=PHASE_MEASURED,
            post=post,
            clock=FakeClock(),
        )


def test_an_answer_naming_another_model_is_not_a_success(
    experiment: Experiment,
) -> None:
    def post(url, body, headers, timeout):
        return PostResponse(200, completion(model_ref="some-other-model"))

    record = send_request(
        experiment,
        composition_double(),
        sequence=0,
        phase=PHASE_MEASURED,
        post=post,
        clock=FakeClock(),
    )
    assert record.outcome == OUTCOME_REFUSED
    assert record.input_tokens is None


def test_a_canonical_error_is_recorded_with_its_code(
    experiment: Experiment,
) -> None:
    def post(url, body, headers, timeout):
        return PostResponse(
            503,
            {
                "code": "model_not_ready",
                "message": "the model is not ready",
                "details": {"adapterKind": "real", "conditionId": "x"},
            },
        )

    record = send_request(
        experiment,
        composition_double(),
        sequence=0,
        phase=PHASE_MEASURED,
        post=post,
        clock=FakeClock(),
    )
    assert record.outcome == OUTCOME_REFUSED
    assert record.status == 503
    assert record.error_code == "model_not_ready"
    assert record.adapter_kind == "real"


def test_an_unreachable_api_is_recorded_as_a_transport_error(
    experiment: Experiment,
) -> None:
    def post(url, body, headers, timeout):
        raise BaselineError("the loopback InferOps API is unreachable")

    record = send_request(
        experiment,
        composition_double(),
        sequence=0,
        phase=PHASE_MEASURED,
        post=post,
        clock=FakeClock(),
    )
    assert record.outcome == OUTCOME_TRANSPORT
    assert record.status == 0
    assert record.adapter_kind is None


def test_an_unsupported_phase_is_refused(experiment: Experiment) -> None:
    with pytest.raises(BaselineError, match="warm-up or measured"):
        send_request(
            experiment,
            composition_double(),
            sequence=0,
            phase="cooldown",
            post=lambda *_: PostResponse(200, completion()),
            clock=FakeClock(),
        )


# --------------------------------------------------------------------------
# Resource sampling
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.5GiB / 3GiB", int(1.5 * 1024**3)),
        ("512MiB / 3GiB", 512 * 1024**2),
        ("2.25GB / 4GB", int(2.25 * 1000**3)),
        ("900KiB / 3GiB", 900 * 1024),
        ("128B / 3GiB", 128),
    ],
)
def test_a_memory_column_is_parsed_into_bytes(text: str, expected: int) -> None:
    assert parse_memory_bytes(text) == expected


@pytest.mark.parametrize("text", ["", "n/a", "1.5ZB / 3GiB", "GiB / 3GiB"])
def test_an_unparsable_memory_column_is_absent(text: str) -> None:
    assert parse_memory_bytes(text) is None


def test_a_resource_sample_reads_the_owned_container_only() -> None:
    package = load_runtime_package()
    runner = ScriptedRunner([CommandResult(0, "245.30%\t1.5GiB / 3GiB\n")])
    sample = sample_resources(package, runner, sequence=5)
    assert sample is not None
    assert sample.cpu_percent == 245.30
    assert sample.memory_bytes == int(1.5 * 1024**3)
    assert runner.calls[0][0] == package.engine
    assert package.container_name in runner.calls[0]


@pytest.mark.parametrize(
    "result",
    [
        CommandResult(1, ""),
        CommandResult(0, ""),
        CommandResult(0, "not-a-number\t1.5GiB / 3GiB\n"),
        CommandResult(0, "12.5%\tnonsense\n"),
        CommandResult(0, "12.5%\n"),
    ],
)
def test_a_sample_that_cannot_be_taken_is_absent_not_zero(
    result: CommandResult,
) -> None:
    """A zero would be indistinguishable from an idle container."""
    package = load_runtime_package()
    assert sample_resources(package, ScriptedRunner([result]), sequence=1) is None


def test_a_sample_survives_an_engine_that_raises() -> None:
    class Exploding:
        def run(self, arguments: Any) -> CommandResult:
            raise OSError("engine gone")

    assert sample_resources(load_runtime_package(), Exploding(), sequence=1) is None


# --------------------------------------------------------------------------
# Environment capture
# --------------------------------------------------------------------------


def test_the_environment_record_carries_the_pins_and_no_host_identity() -> None:
    """A committed environment record must not name the machine or its owner."""
    runner = ScriptedRunner([CommandResult(0, "27.1.1\n")])
    record = capture_environment(runner=runner)
    document = record.document()
    package = load_runtime_package()
    assert document["imageReference"] == package.image_reference
    assert document["containerEngineVersion"] == "27.1.1"
    assert document["accelerator"] == "none; CPU only"
    assert document["logicalCpus"] >= 1
    assert set(document) == {
        "operatingSystem",
        "release",
        "architecture",
        "processorFamily",
        "logicalCpus",
        "totalMemoryBytes",
        "freeDiskBytes",
        "pythonVersion",
        "containerEngineVersion",
        "accelerator",
        "imageReference",
        "modelRepository",
        "modelRevision",
        "modelArtifactSha256",
        "runtimeSourceRevision",
    }


def test_an_absent_container_engine_leaves_the_version_unknown() -> None:
    """Recorded as unknown rather than invented, which keeps the record honest."""
    runner = ScriptedRunner([CommandResult(1, "", "not found")])
    assert capture_environment(runner=runner).container_engine_version is None


# --------------------------------------------------------------------------
# The execution gate
# --------------------------------------------------------------------------


def test_an_unconfirmed_run_is_refused(experiment: Experiment) -> None:
    """No composition is started, so the refusal happens before any side effect."""

    def compose(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the composition must not start without confirmation")

    with pytest.raises(BaselineRefused, match="--confirm-real-runtime"):
        execute(experiment, confirmed=False, compose=compose)


def test_a_confirmed_run_warms_up_then_measures(
    experiment: Experiment, tmp_path: Path
) -> None:
    """The full sequence through injected seams: no container, no model, no socket."""
    sent: list[str] = []
    servers: list[_FakeServer] = []

    def post(url, body, headers, timeout):
        sent.append(headers["X-InferOps-Request-ID"])
        return PostResponse(200, completion())

    def compose(composition, *, confirmed, repo_root, runner, on_ready, server_factory):
        assert confirmed is True
        server_factory(None)
        on_ready(42_000, 250)

    runner = ScriptedRunner(
        [CommandResult(0, "27.1.1\n")]
        + [CommandResult(0, "120.0%\t1GiB / 3GiB\n")] * 10
    )
    run = execute(
        experiment,
        confirmed=True,
        repo_root=tmp_path,
        runner=runner,
        post=post,
        clock=FakeClock(0.1),
        compose=compose,
        server_factory=_recording_server_factory(servers),
    )
    assert len(sent) == experiment.total_requests
    assert run.model_load_ms == 42_000
    assert run.api_ready_ms == 250
    warmup = [r for r in run.records if r.phase == PHASE_WARMUP]
    measured = [r for r in run.records if r.phase == PHASE_MEASURED]
    assert len(warmup) == experiment.warmup_requests
    assert len(measured) == experiment.measured_requests
    assert all(record.outcome == OUTCOME_SUCCESS for record in run.records)
    assert len(run.samples) == (
        experiment.measured_requests // experiment.resource_sample_every_requests
    )
    summary = summarize(experiment, run)
    assert summary["successCriteria"]["met"] is True
    # B2: the run must request its own server's stop before returning, or a
    # real `run_foreground` would block forever on `server.join()` afterward.
    assert servers and all(server.stop_requested for server in servers)


def test_the_stop_condition_bounds_the_warm_up_too(
    experiment: Experiment, tmp_path: Path
) -> None:
    """A clock that exhausts the duration bound during the warm-up ends the run.

    Without a stop check in the warm-up loop the run would send every warm-up
    request regardless, which is the cheaper-half-only bound the phase ceilings
    exist to prevent.
    """
    sent: list[str] = []

    def post(url, body, headers, timeout):
        sent.append(headers["X-InferOps-Request-ID"])
        return PostResponse(200, completion())

    servers: list[_FakeServer] = []

    def compose(composition, *, confirmed, repo_root, runner, on_ready, server_factory):
        server_factory(None)
        on_ready(1, 1)

    run = execute(
        experiment,
        confirmed=True,
        repo_root=tmp_path,
        runner=ScriptedRunner([CommandResult(0, "27.1.1\n")]),
        post=post,
        clock=FakeClock(experiment.max_duration_seconds),
        compose=compose,
        server_factory=_recording_server_factory(servers),
    )
    assert servers and all(server.stop_requested for server in servers)
    warmup = [record for record in run.records if record.phase == PHASE_WARMUP]
    measured = [record for record in run.records if record.phase == PHASE_MEASURED]
    # One warm-up request, then the bound fires: without the check in that loop
    # all three would be sent whatever the clock said.
    assert len(warmup) == 1 < experiment.warmup_requests
    assert len(measured) < experiment.measured_requests
    assert len(sent) == len(run.records) < experiment.total_requests


# --------------------------------------------------------------------------
# The command surface
# --------------------------------------------------------------------------


def test_check_prints_the_registered_method_and_starts_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["check"]) == 0
    printed = capsys.readouterr().out
    assert "inferops-local-serving-baseline" in printed
    assert "not a production benchmark" in printed
    assert "offline experiment validation only" in printed
    assert "nearest-rank" in printed


def test_run_without_confirmation_is_refused(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["run"]) == 3
    assert "--confirm-real-runtime" in capsys.readouterr().err
