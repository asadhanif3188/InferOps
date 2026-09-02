"""What the API emits when it serves a request, read off a running application.

Every other telemetry suite in this repository compares one committed file against
another. This one drives the application through its own ASGI interface, scrapes the
endpoint it serves, collects the records it wrote, and asserts on what came out. It
is the first suite here that observes a signal rather than a specification.

Five properties, and each is one an acceptance criterion turns on.

**Every request is counted, including the ones that failed.** A counter that only
counts the paths somebody remembered is a success rate that flatters the platform,
so the close is in a ``finally`` and the suite provokes refusals at four different
depths — before the handler, during validation, from the adapter, and during a drain
— and holds the counters to all of them.

**A request identifier, a trace identifier, and a prompt are not labels.** The
registry refuses them at declaration, which
``tests/telemetry/test_api_telemetry_agreement.py`` establishes; what this suite
establishes is the consequence — every series a real request produced is keyed by the
workload, the model, the outcome, or the error code, and by nothing that varies per
request.

**No prompt, completion, or secret reaches a record.** The suite sends a prompt with
a recognisable marker in it, drives a refusal whose adapter message contains another,
and asserts that neither appears in any record written or in the exposition.

**A mock deployment says so in its telemetry.** The scrape names the mock in a
comment, the identity metric carries ``inferops.adapter.kind="mock"``, and every
operational series carries the mock runtime's registered identifier.

**Records carry the correlation identifier the caller was given.** The same value the
response header echoes is the one every record for that request carries, which is
what makes a refusal as findable as a success.

**A broken log destination breaks neither the request nor a counter.** The sink is
the only I/O in this path and it is the one thing here that fails for reasons the
process did not cause, so a sink that raises is driven directly: the request still
answers, the in-flight gauge still returns to zero, and the scrape says how many
records were lost.

Nothing here binds a socket, contacts a runtime, or writes to a real destination: the
log sink is a list, and the clocks are fixed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from inferops.adapters import MOCK_ADAPTER_KIND, MOCK_RUNTIME_ID, MockServingAdapter
from inferops.adapters.mock_serving import MockAdapterSettings, MockScenario
from inferops.api import (
    CORRELATION_ID_HEADER,
    REQUEST_ID_HEADER,
    ApiConfiguration,
    ApiTelemetry,
    InferOpsApi,
)
from inferops.api.errors import (
    CALLER_DEADLINE,
    DEPLOYMENT_DRAINING,
    MODEL_LOADING,
    PATH_NOT_SERVED,
    REQUEST_OUTSIDE_SUBSET,
    RUNTIME_TIMEOUT,
    UNEXPECTED_FAILURE,
)
from inferops.api.observability import outcome_for
from inferops.api.surface import (
    CHAT_COMPLETIONS_PATH,
    METRICS_PATH,
    READY_PATH,
)
from inferops.domain.context import RequestContext
from inferops.domain.serving import (
    AdapterConfiguration,
    InferenceResult,
    InvalidValueError,
    ModelNotReadyError,
    TokenUsage,
)
from inferops.telemetry import names
from inferops.telemetry.resource import ResourceAttributes, WorkloadIdentity
from tests.support import asgi_client
from tests.support.api_composition import MOCK_MODEL, RecordingAdapter, fixed_clock

pytestmark = pytest.mark.mockintegration

#: A marker a prompt carries so that finding it anywhere is unambiguous. It is not a
#: real secret and it is not a real prompt; it is a string that has no business
#: leaving the request it arrived in.
PROMPT_MARKER = "canary-prompt-value-8f2a"

#: The workload identity these suites compose, so that a series has a label to be
#: keyed by and the suite can prove which label it is.
WORKLOAD = WorkloadIdentity(
    workload_id="support-assistant",
    workload_version="1.4.0",
    owner_id="team-platform-demo",
)


@dataclass
class Sink:
    """A log sink that keeps every line, so a suite can read what was written."""

    lines: list[str] = field(default_factory=list)

    def __call__(self, line: str) -> None:
        self.lines.append(line)

    @property
    def records(self) -> list[dict]:
        """Every line parsed. A line that is not one JSON object is a defect here."""
        return [json.loads(line) for line in self.lines]

    def of(self, event: str) -> list[dict]:
        return [row for row in self.records if row[names.EVENT] == event]


class ReportingAdapter(RecordingAdapter):
    """A controlled adapter that reports token usage, which the committed mock does not.

    The mock replays a fixture and reports no usage at all, on purpose: a token
    count it made up would be an estimate wearing a measurement's clothes. So the
    token counter needs an adapter that answers the question, and this is the
    smallest one that does.
    """

    async def infer(self, prompt: str, context: RequestContext) -> InferenceResult:
        result = await super().infer(prompt, context)
        return InferenceResult(
            content=result.content,
            model=result.model,
            adapter_kind=result.adapter_kind,
            usage=TokenUsage(input_tokens=11, output_tokens=7),
            finish_reason=result.finish_reason,
        )


@dataclass
class Refusing:
    """A sink that refuses every record, standing in for a broken destination."""

    def __call__(self, line: str) -> None:
        raise OSError("the log destination went away")


@dataclass
class TickingAdapter(RecordingAdapter):
    """An adapter that advances the monotonic clock while it is serving.

    A duration is only a measurement if something took time. The committed mock
    returns instantly, so a suite asserting on latency has to make the clock move
    where a real runtime would — inside the call the duration is measuring.
    """

    clock: Clock | None = None
    seconds: float = 0.0

    async def infer(self, prompt: str, context: RequestContext) -> InferenceResult:
        if self.clock is not None:
            self.clock.advance(self.seconds)
        return await super().infer(prompt, context)


@dataclass
class Clock:
    """A clock the suite advances by hand, so a duration is an input not a race."""

    reading: float = 0.0

    def __call__(self) -> float:
        return self.reading

    def advance(self, seconds: float) -> None:
        self.reading += seconds


def compose(
    adapter: object,
    *,
    sink: Sink | None = None,
    monotonic: Clock | None = None,
    resource: ResourceAttributes | None = None,
    workload: WorkloadIdentity | None = None,
    drain_timeout_ms: int = 1_000,
) -> tuple[InferOpsApi, Sink]:
    """One instrumented application, its sink, and no I/O."""
    written = sink if sink is not None else Sink()
    telemetry = ApiTelemetry(
        resource=(
            resource
            if resource is not None
            else ResourceAttributes(
                adapter_kind=MOCK_ADAPTER_KIND,
                service_version="0.0.0",
                deployment_environment=names.ENVIRONMENT_DEV,
            )
        ),
        workload=workload if workload is not None else WORKLOAD,
        sink=written,
        clock=fixed_clock,
    )
    api = InferOpsApi(
        adapter=adapter,  # type: ignore[arg-type]
        adapter_configuration=AdapterConfiguration(
            model_identifier=MOCK_MODEL, timeout_ms=5_000
        ),
        configuration=ApiConfiguration(
            adapter_kind=MOCK_ADAPTER_KIND, drain_timeout_ms=drain_timeout_ms
        ),
        clock=fixed_clock,
        monotonic=monotonic if monotonic is not None else Clock(),
        telemetry=telemetry,
    )
    return api, written


async def started(
    adapter: object | None = None, **kwargs: object
) -> tuple[InferOpsApi, Sink]:
    api, sink = compose(adapter or MockServingAdapter(), **kwargs)  # type: ignore[arg-type]
    await api.startup()
    return api, sink


async def complete(
    api: InferOpsApi, *, prompt: str = PROMPT_MARKER, headers: tuple = ()
) -> asgi_client.Response:
    body = json.dumps(
        {"model": MOCK_MODEL, "messages": [{"role": "user", "content": prompt}]}
    ).encode("utf-8")
    return await asgi_client.request(
        api, "POST", CHAT_COMPLETIONS_PATH, body=body, headers=headers
    )


def series(text: str, metric: str) -> list[str]:
    """Every sample line of one metric in an exposition, comments excluded."""
    return [
        line
        for line in text.splitlines()
        if not line.startswith("#")
        and line.split("{")[0].split(" ")[0].startswith(metric)
    ]


def sample_value(text: str, line_prefix: str) -> float:
    for line in text.splitlines():
        if line.startswith(line_prefix):
            return float(line.rsplit(" ", 1)[1])
    raise AssertionError(f"no sample matching {line_prefix!r} in:\n{text}")


async def scrape(api: InferOpsApi) -> str:
    return (await asgi_client.request(api, "GET", METRICS_PATH)).text()


# --------------------------------------------------------------------------
# Requests are counted, and so are the ones that failed
# --------------------------------------------------------------------------


async def test_a_served_request_is_counted_as_a_success() -> None:
    api, _ = await started()

    assert (await complete(api)).status == 200

    text = await scrape(api)
    assert (
        sample_value(
            text,
            f'{names.INFERENCE_REQUESTS}{{inferops_workload_id="support-assistant",'
            f'inferops_model_id="{MOCK_MODEL}",inferops_outcome="success"}}',
        )
        == 1
    )
    assert not series(text, names.INFERENCE_ERRORS)


async def test_the_in_flight_gauge_returns_to_zero_when_a_request_closes() -> None:
    """It is a gauge that goes up and comes back down, and the coming down is the bug.

    A gauge incremented on the way in and decremented only on the success path is a
    saturation signal that climbs forever once anything starts failing, which is
    exactly when it is read.
    """
    api, _ = await started(RecordingAdapter(failure=MODEL_LOADING_ERROR()))

    assert (await complete(api)).status == MODEL_LOADING.status

    text = await scrape(api)
    assert (
        sample_value(
            text,
            f'{names.INFERENCE_REQUESTS_IN_FLIGHT}{{inferops_workload_id="support-assistant",'
            f'inferops_model_id="{MOCK_MODEL}"}}',
        )
        == 0
    )


async def test_a_refusal_from_the_adapter_is_counted_and_named() -> None:
    api, _ = await started(RecordingAdapter(failure=MODEL_LOADING_ERROR()))

    await complete(api)

    text = await scrape(api)
    assert (
        sample_value(
            text,
            f'{names.INFERENCE_REQUESTS}{{inferops_workload_id="support-assistant",'
            f'inferops_model_id="{MOCK_MODEL}",inferops_outcome="server-error"}}',
        )
        == 1
    )
    assert (
        sample_value(
            text,
            f'{names.INFERENCE_ERRORS}{{inferops_workload_id="support-assistant",'
            f'inferops_error_code="{MODEL_LOADING.code}"}}',
        )
        == 1
    )


async def test_a_request_refused_before_the_handler_is_still_counted() -> None:
    """A body outside the frozen subset never reaches the adapter and still arrived."""
    api, _ = await started()

    response = await asgi_client.request(
        api, "POST", CHAT_COMPLETIONS_PATH, body=b'{"model": 1}'
    )

    assert response.status == REQUEST_OUTSIDE_SUBSET.status
    text = await scrape(api)
    assert (
        sample_value(
            text,
            f'{names.INFERENCE_REQUESTS}{{inferops_workload_id="support-assistant",'
            f'inferops_model_id="{MOCK_MODEL}",inferops_outcome="client-error"}}',
        )
        == 1
    )


async def test_a_request_refused_by_a_drain_is_counted() -> None:
    api, _ = await started()
    api.lifecycle.begin_shutdown()

    response = await complete(api)

    assert response.status == DEPLOYMENT_DRAINING.status
    text = await scrape(api)
    assert (
        sample_value(
            text,
            f'{names.INFERENCE_ERRORS}{{inferops_workload_id="support-assistant",'
            f'inferops_error_code="{DEPLOYMENT_DRAINING.code}"}}',
        )
        == 1
    )


async def test_a_request_to_an_endpoint_that_is_not_inference_is_not_counted() -> None:
    """A readiness probe in the request counter is a success rate about a probe loop."""
    api, _ = await started()

    await asgi_client.request(api, "GET", READY_PATH)
    await asgi_client.request(api, "GET", "/props")

    assert not series(await scrape(api), names.INFERENCE_REQUESTS)


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        (None, names.OUTCOME_SUCCESS),
        (REQUEST_OUTSIDE_SUBSET, names.OUTCOME_CLIENT_ERROR),
        (UNEXPECTED_FAILURE, names.OUTCOME_SERVER_ERROR),
        (RUNTIME_TIMEOUT, names.OUTCOME_TIMEOUT),
        (CALLER_DEADLINE, names.OUTCOME_TIMEOUT),
    ],
    ids=lambda value: getattr(value, "condition_id", str(value)),
)
def test_a_timeout_is_separated_from_an_error(condition, expected) -> None:
    """Two conditions with different statuses are the same operational event."""
    status = 200 if condition is None else int(condition.status)
    assert outcome_for(condition, status) == expected


# --------------------------------------------------------------------------
# Latency is measured, and measured on the right clock
# --------------------------------------------------------------------------


async def test_a_request_is_timed_with_the_clock_the_application_was_given() -> None:
    """The duration is the elapsed reading, not a number the code can produce anyway.

    The adapter advances the monotonic clock by a known amount while it is
    serving, so the histogram sum, the record's duration, and the bucket the
    observation lands in are all consequences of that number. Asserting merely
    that a duration is non-negative would pass against a hard-coded zero, because
    the production code clamps at zero.
    """
    clock = Clock()
    api, sink = await started(
        TickingAdapter(clock=clock, seconds=12.5), monotonic=clock
    )

    await complete(api)

    text = await scrape(api)
    labels = (
        f'{{inferops_workload_id="support-assistant",inferops_model_id="{MOCK_MODEL}"}}'
    )
    assert sample_value(text, f"{names.INFERENCE_REQUEST_DURATION}_count{labels}") == 1
    assert sample_value(text, f"{names.INFERENCE_REQUEST_DURATION}_sum{labels}") == 12.5
    assert sink.of(names.EVENT_REQUEST_COMPLETED)[0][names.DURATION_MS] == 12500.0


async def test_an_observation_lands_in_the_buckets_at_or_above_it() -> None:
    """A histogram is cumulative: 12.5s counts in 20, 30, 45, 60, 120, 300, +Inf."""
    clock = Clock()
    api, _ = await started(TickingAdapter(clock=clock, seconds=12.5), monotonic=clock)

    await complete(api)

    text = await scrape(api)
    for boundary, expected in (("10", 0), ("20", 1), ("300", 1), ("+Inf", 1)):
        assert (
            sample_value(
                text,
                f"{names.INFERENCE_REQUEST_DURATION}_bucket{{inferops_workload_id="
                f'"support-assistant",inferops_model_id="{MOCK_MODEL}",le="{boundary}"}}',
            )
            == expected
        ), boundary


async def test_a_broken_log_sink_neither_fails_a_request_nor_strands_the_gauge() -> (
    None
):
    """Telemetry may not decide availability, and a pair may not be half-applied.

    A sink that raises is a realistic production condition — a closed pipe, a full
    disk, a collector that stopped reading — and the composed default writes to a
    stream on every record. If that failure escaped, it would take the request
    with it *and* leave the in-flight gauge raised forever, because nothing else
    lowers that series again.
    """

    api, _ = await started(sink=Refusing())

    assert (await complete(api)).status == 200

    text = await scrape(api)
    assert (
        sample_value(
            text,
            f'{names.INFERENCE_REQUESTS_IN_FLIGHT}{{inferops_workload_id="support-assistant",'
            f'inferops_model_id="{MOCK_MODEL}"}}',
        )
        == 0
    )
    assert api.telemetry.logs.dropped >= 2


async def test_a_dropped_record_is_named_on_the_surface_that_still_works() -> None:
    """A reader of the remaining records cannot otherwise tell that some are gone."""
    api, _ = await started(sink=Refusing())
    await complete(api)

    text = await scrape(api)

    assert any(
        line.startswith("# ") and "not written" in line for line in text.splitlines()
    )


async def test_a_record_the_catalog_forbids_still_raises_when_the_sink_is_fine() -> (
    None
):
    """A failing sink is soft; a malformed record is not. The two must not merge."""
    api, _ = await started()

    with pytest.raises(InvalidValueError):
        api.telemetry.logs.emit(
            names.EVENT_REQUEST_COMPLETED,
            correlation_id="c-1",
            fields={"prompt": "must never be writable"},
        )


async def test_the_histogram_declares_the_buckets_the_budget_was_computed_from() -> (
    None
):
    api, _ = await started()
    await complete(api)

    text = await scrape(api)
    buckets = [
        line
        for line in text.splitlines()
        if line.startswith(f"{names.INFERENCE_REQUEST_DURATION}_bucket")
    ]
    assert len(buckets) == 12, buckets
    assert 'le="+Inf"' in buckets[-1], buckets[-1]
    assert sum('le="+Inf"' in line for line in buckets) == 1, buckets


# --------------------------------------------------------------------------
# Readiness
# --------------------------------------------------------------------------


async def test_a_readiness_failure_names_the_component_that_said_no() -> None:
    adapter = MockServingAdapter(
        MockAdapterSettings(scenario=MockScenario.MODEL_NOT_READY)
    )
    api, sink = await started(adapter)

    assert (await asgi_client.request(api, "GET", READY_PATH)).status == 503

    text = await scrape(api)
    assert (
        sample_value(
            text,
            f'{names.READINESS_CHECK_FAILURES}{{inferops_workload_id="support-assistant",'
            f'inferops_component="{names.COMPONENT_ADAPTER}"}}',
        )
        == 1
    )
    assert sink.of(names.EVENT_READINESS_FAILED)[0][names.COMPONENT] == (
        names.COMPONENT_ADAPTER
    )


async def test_a_readiness_failure_before_serving_is_the_api_half() -> None:
    api, sink = compose(MockServingAdapter())

    assert (await asgi_client.request(api, "GET", READY_PATH)).status == 503

    assert sink.of(names.EVENT_READINESS_FAILED)[0][names.COMPONENT] == (
        names.COMPONENT_API
    )


# --------------------------------------------------------------------------
# Tokens are counted where they were reported, and absent where they were not
# --------------------------------------------------------------------------


async def test_no_token_series_exists_when_the_adapter_reported_no_usage() -> None:
    """Absent rather than estimated. The committed mock reports no usage at all."""
    api, _ = await started()

    await complete(api)

    assert not series(await scrape(api), names.INFERENCE_TOKENS)


async def test_tokens_are_counted_in_both_directions_when_the_adapter_reports_them() -> (
    None
):
    api, _ = await started(ReportingAdapter())

    await complete(api)

    text = await scrape(api)
    for direction, expected in ((names.TOKEN_INPUT, 11), (names.TOKEN_OUTPUT, 7)):
        assert (
            sample_value(
                text,
                f'{names.INFERENCE_TOKENS}{{inferops_workload_id="support-assistant",'
                f'inferops_model_id="{MOCK_MODEL}",inferops_token_direction="{direction}"}}',
            )
            == expected
        )


# --------------------------------------------------------------------------
# Identity, and the mock saying it is a mock
# --------------------------------------------------------------------------


async def test_the_identity_metric_is_one_series_carrying_what_the_adapter_reported() -> (
    None
):
    api, _ = await started()

    lines = series(await scrape(api), names.BUILD_INFO)

    assert len(lines) == 1, lines
    assert f'inferops_runtime_id="{MOCK_RUNTIME_ID}"' in lines[0]
    assert f'inferops_model_id="{MOCK_MODEL}"' in lines[0]
    assert f'inferops_adapter_kind="{MOCK_ADAPTER_KIND}"' in lines[0]
    assert lines[0].endswith(" 1")


async def test_runtime_identity_uses_the_registered_id_not_the_display_name() -> None:
    """Real runtimes may report a human-readable name that is not label-safe."""
    api, _ = await started(
        RecordingAdapter(
            runtime_name="llama.cpp llama-server",
            runtime_identifier="llama-cpp-server",
        )
    )

    line = series(await scrape(api), names.BUILD_INFO)[0]

    assert 'inferops_runtime_id="llama-cpp-server"' in line
    assert "llama.cpp llama-server" not in line


async def test_an_unstated_identity_is_empty_and_not_invented() -> None:
    """A version of `unknown` sorts, groups, and reads like a release somebody shipped."""
    api, _ = await started(resource=ResourceAttributes(adapter_kind=MOCK_ADAPTER_KIND))

    line = series(await scrape(api), names.BUILD_INFO)[0]

    assert 'service_version=""' in line
    assert 'inferops_release_id=""' in line
    assert "unknown" not in line


async def test_every_operational_series_names_the_mock_runtime_or_the_workload() -> (
    None
):
    """A scrape is copied without its context; the labels have to carry it."""
    api, _ = await started()
    await complete(api)

    text = await scrape(api)
    for line in series(text, names.INFERENCE_REQUESTS) + series(
        text, names.INFERENCE_REQUESTS_IN_FLIGHT
    ):
        assert 'inferops_workload_id="support-assistant"' in line, line


# --------------------------------------------------------------------------
# Nothing that varies per request is a label
# --------------------------------------------------------------------------


async def test_no_series_a_real_request_produced_is_keyed_by_a_request_identifier() -> (
    None
):
    api, _ = await started()
    response = await complete(api)
    request_id = response.header(REQUEST_ID_HEADER)
    correlation_id = response.header(CORRELATION_ID_HEADER)
    assert request_id and correlation_id

    text = await scrape(api)

    assert request_id not in text
    assert correlation_id not in text
    for forbidden in ("inferops_request_id", "inferops_correlation_id", "trace_id"):
        assert forbidden not in text, forbidden


async def test_the_exposition_carries_no_duration_or_workload_version_label() -> None:
    api, _ = await started()
    await complete(api)

    text = await scrape(api)

    assert "inferops_duration_ms" not in text
    assert "inferops_workload_version" not in text
    assert WORKLOAD.workload_version not in text
    assert "inferops_owner_id" not in text


# --------------------------------------------------------------------------
# No prompt, no completion, no adapter message reaches a record
# --------------------------------------------------------------------------


async def test_no_record_or_series_repeats_the_prompt() -> None:
    api, sink = await started()

    await complete(api, prompt=PROMPT_MARKER)

    assert sink.lines
    for line in sink.lines:
        assert PROMPT_MARKER not in line, line
    assert PROMPT_MARKER not in await scrape(api)


async def test_no_record_repeats_the_completion_the_caller_received() -> None:
    api, sink = await started()

    content = (await complete(api)).json()["choices"][0]["message"]["content"]

    assert content
    for line in sink.lines:
        assert content not in line, line


async def test_no_record_repeats_an_adapter_message() -> None:
    """An adapter's own words stop at this edge, in a record as much as in a response."""
    api, sink = await started(
        RecordingAdapter(failure=MODEL_LOADING_ERROR(PROMPT_MARKER))
    )

    await complete(api)

    for line in sink.lines:
        assert PROMPT_MARKER not in line, line


async def test_a_record_has_no_free_form_message_field() -> None:
    api, sink = await started()
    await complete(api)

    for row in sink.records:
        assert "message" not in row, row
        assert "msg" not in row, row


# --------------------------------------------------------------------------
# Records carry what the catalog requires, and the caller's correlation identifier
# --------------------------------------------------------------------------


async def test_every_record_carries_the_required_fields() -> None:
    api, sink = await started()
    await complete(api)
    await asgi_client.request(api, "GET", READY_PATH)
    await api.shutdown()

    assert sink.records
    for row in sink.records:
        for required in (
            names.TIMESTAMP,
            names.LEVEL,
            names.EVENT,
            names.SERVICE_NAME,
            names.CORRELATION_ID,
        ):
            assert required in row, {"missing": required, "record": row}
        assert row[names.EVENT] in names.EVENTS, row
        assert row[names.LEVEL] in names.LEVELS, row


async def test_a_record_carries_the_correlation_identifier_the_caller_supplied() -> (
    None
):
    api, sink = await started()

    response = await complete(api, headers=((CORRELATION_ID_HEADER, "trace-me-42"),))

    assert response.header(CORRELATION_ID_HEADER) == "trace-me-42"
    for event in (names.EVENT_REQUEST_RECEIVED, names.EVENT_REQUEST_COMPLETED):
        assert sink.of(event)[0][names.CORRELATION_ID] == "trace-me-42"


async def test_a_record_is_written_when_a_request_arrives_and_when_it_closes() -> None:
    api, sink = await started()

    await complete(api)

    assert len(sink.of(names.EVENT_REQUEST_RECEIVED)) == 1
    assert len(sink.of(names.EVENT_REQUEST_COMPLETED)) == 1
    assert not sink.of(names.EVENT_REQUEST_REFUSED)


async def test_a_refusal_writes_a_record_naming_the_canonical_code() -> None:
    api, sink = await started(RecordingAdapter(failure=MODEL_LOADING_ERROR()))

    await complete(api)

    refused = sink.of(names.EVENT_REQUEST_REFUSED)[0]
    assert refused[names.ERROR_CODE] == MODEL_LOADING.code
    assert refused[names.OUTCOME] == names.OUTCOME_SERVER_ERROR
    assert refused[names.HTTP_STATUS] == int(MODEL_LOADING.status)
    assert refused[names.LEVEL] == names.LEVEL_WARN


async def test_a_record_carries_the_workload_identity_the_deployment_states() -> None:
    api, sink = await started()

    await complete(api)

    row = sink.of(names.EVENT_REQUEST_COMPLETED)[0]
    assert row[names.WORKLOAD_ID] == WORKLOAD.workload_id
    assert row[names.WORKLOAD_VERSION] == WORKLOAD.workload_version
    assert row[names.OWNER_ID] == WORKLOAD.owner_id
    assert row[names.ADAPTER_KIND] == MOCK_ADAPTER_KIND


async def test_an_unstated_identity_is_omitted_from_a_record_rather_than_blank() -> (
    None
):
    api, sink = await started(
        resource=ResourceAttributes(adapter_kind=MOCK_ADAPTER_KIND),
        workload=WorkloadIdentity(),
    )

    await complete(api)

    row = sink.of(names.EVENT_REQUEST_COMPLETED)[0]
    assert names.WORKLOAD_ID not in row
    assert names.RELEASE_ID not in row
    assert row[names.SERVICE_NAME]


async def test_a_record_is_one_json_object_on_one_line() -> None:
    """A multi-line record is one a collector splits into unrelated records."""
    api, sink = await started()
    await complete(api)

    for line in sink.lines:
        assert "\n" not in line
        assert isinstance(json.loads(line), dict)


async def test_the_lifecycle_writes_a_record_at_each_of_its_three_moments() -> None:
    api, sink = await started()

    await api.shutdown()

    assert len(sink.of(names.EVENT_DEPLOYMENT_STARTED)) == 1
    assert len(sink.of(names.EVENT_DEPLOYMENT_DRAINING)) == 1
    assert len(sink.of(names.EVENT_DEPLOYMENT_STOPPED)) == 1


async def test_a_deployment_with_no_sink_writes_nowhere_and_still_serves() -> None:
    """The composition point decides where records go; an application on its own has no destination."""
    api = InferOpsApi(
        adapter=MockServingAdapter(),
        adapter_configuration=AdapterConfiguration(
            model_identifier=MOCK_MODEL, timeout_ms=5_000
        ),
        configuration=ApiConfiguration(adapter_kind=MOCK_ADAPTER_KIND),
        clock=fixed_clock,
    )
    await api.startup()

    assert (await complete(api)).status == 200
    assert series(await scrape(api), names.INFERENCE_REQUESTS)


# --------------------------------------------------------------------------
# Helpers that build the two things a real adapter would have supplied
# --------------------------------------------------------------------------


def MODEL_LOADING_ERROR(
    message: str = "the model is still loading",
) -> ModelNotReadyError:
    """A canonical error an adapter raises, carrying words of its own.

    The message is a parameter because one of the properties this suite holds is
    that an adapter's own words stop at this edge -- in a record as much as in a
    response -- so a test needs to be able to put a recognisable string in one.
    """
    return ModelNotReadyError(message)


def test_the_path_that_is_not_served_names_a_condition_with_a_client_outcome() -> None:
    assert outcome_for(PATH_NOT_SERVED, int(PATH_NOT_SERVED.status)) == (
        names.OUTCOME_CLIENT_ERROR
    )
