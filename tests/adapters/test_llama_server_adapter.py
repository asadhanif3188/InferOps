"""The real adapter, against a controlled transport. What that proves, and what it does not.

Every check in this module drives
:class:`~inferops.adapters.llama_cpp.adapter.LlamaServerAdapter` with a transport
that returns what the test decided. **The adapter is real; the thing on the other
end of it is not.** That distinction is the whole of
[the mock and real boundary](../../docs/serving/mock-and-real-boundary.md), and
this file is the place it is easiest to lose, so it is stated here rather than
only in a record:

- what a passing run establishes is that the adapter's own logic — its readiness
  gate, its two deadlines, its status mapping, its normalisation, its refusals —
  behaves as the contract requires;
- what it establishes about `llama-server`, about the pinned model, about
  latency, about token accounting, and about any failure mode nobody anticipated,
  is **nothing at all**;
- the results are `local-static`, weaker than the `mock` class this layer carries,
  and no result here may be cited for a serving claim.

A result produced here declares ``adapter_kind`` of ``real``, because the adapter
is the real one and a value object may not lie about which class produced it.
That is precisely why the controlled transport lives in this file rather than in
the distribution: an artifact carrying that label can only be produced by code a
reader is looking at.

Every check reads objects from this distribution. No network, no cluster, no
model, and no environment variable of the running process.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass, field

import pytest

from inferops.adapters.llama_cpp import (
    CHAT_COMPLETIONS_PATH,
    COMPLETION_ALIAS_DISAGREEMENT,
    HEALTH_PATH,
    LLAMA_SERVER_ADAPTER_KIND,
    LLAMA_SERVER_CAPABILITIES,
    LLAMA_SERVER_RUNTIME_NAME,
    METRICS_PATH,
    MODELS_PATH,
    NOT_INITIALIZED_MESSAGE,
    PINNED_IMAGE_DIGEST,
    PINNED_MODEL_FILE,
    PINNED_MODEL_REVISION,
    PROPS_PATH,
    SHUT_DOWN_MESSAGE,
    LlamaServerAdapter,
    LlamaServerSettings,
    ReadinessState,
    RuntimeResponse,
    TransportError,
    TransportProtocolError,
    TransportTimeout,
    TransportUnreachable,
)
from inferops.domain.context import RequestContext
from inferops.domain.serving import (
    AdapterConfiguration,
    CanonicalError,
    CapabilityUnavailableError,
    InternalError,
    InvalidAdapterConfigError,
    ModelNotReadyError,
    RequestTimeoutError,
    ServingAdapter,
    TokenUsage,
    UpstreamTimeoutError,
)
from tests.support.serving_conformance import ServingAdapterConformance

pytestmark = pytest.mark.adapter

CONTEXT = RequestContext(request_id="req-1", correlation_id="corr-2")

#: The platform model identity. Kebab-case, and different by construction from
#: the runtime alias below.
PLATFORM_MODEL = "qwen3-1-7b-instruct"

#: The alias the runtime is started with and echoes back.
RUNTIME_ALIAS = "qwen3-1.7b-q8_0"

#: A completion body of the shape the feasibility record preserved.
COMPLETION: dict[str, object] = {
    "choices": [
        {
            "finish_reason": "stop",
            "index": 0,
            "message": {"role": "assistant", "content": "a controlled answer"},
        }
    ],
    "model": RUNTIME_ALIAS,
    "usage": {"prompt_tokens": 20, "completion_tokens": 23, "total_tokens": 43},
}

#: A prompt with a shape a record must never carry.
SENSITIVE_PROMPT = "my account number is 000-11-2222 and my address is Elm Street"


@dataclass
class Call:
    """One request the adapter made, as the transport saw it."""

    method: str
    url: str
    timeout_s: float
    payload: Mapping[str, object] | None = None


@dataclass
class ControlledTransport:
    """A transport that answers what a test decided, and records what it was asked.

    It is a *test double for the far side*, not a mock serving adapter: the code
    under test is the real adapter, and this object replaces only the socket. It
    lives here rather than in the distribution because a class that could
    manufacture a real-labelled result must be visible in the file that uses it.
    """

    responses: dict[str, RuntimeResponse] = field(default_factory=dict)
    failures: dict[str, BaseException] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)
    closed: int = 0
    close_failure: BaseException | None = None
    #: Seconds to sleep before answering, ignoring the budget it was given. The
    #: adapter's outer deadline is what this exists to exercise.
    stall_s: float = 0.0

    def _answer(self, path: str) -> RuntimeResponse:
        failure = self.failures.get(path)
        if failure is not None:
            raise failure
        return self.responses.get(path, RuntimeResponse(status_code=200, body={}))

    async def get(self, url: str, *, timeout_s: float) -> RuntimeResponse:
        path = _path_of(url)
        self.calls.append(Call("GET", url, timeout_s))
        await self._stall()
        return self._answer(path)

    async def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        timeout_s: float,
    ) -> RuntimeResponse:
        path = _path_of(url)
        self.calls.append(Call("POST", url, timeout_s, payload))
        await self._stall()
        return self._answer(path)

    async def close(self) -> None:
        self.closed += 1
        if self.close_failure is not None:
            raise self.close_failure

    async def _stall(self) -> None:
        if self.stall_s:
            await asyncio.sleep(self.stall_s)

    # -- what a test asks it to do --------------------------------------

    def answer(self, path: str, status: int, body: object | None = None) -> None:
        self.responses[path] = RuntimeResponse(status_code=status, body=body)

    def fail(self, path: str, failure: BaseException) -> None:
        self.failures[path] = failure

    def paths(self) -> list[str]:
        return [_path_of(call.url) for call in self.calls]


def _path_of(url: str) -> str:
    """The path of an absolute URL, which is what a test keys its answers on."""
    return "/" + url.split("/", 3)[3] if url.count("/") > 2 else "/"


def settings(
    *,
    endpoint: str = "http://llama-server.inferops-serving.svc.cluster.local:8080",
    model_path: str = f"/models/{PINNED_MODEL_FILE}",
    model_alias: str = RUNTIME_ALIAS,
    context_size: int = 4096,
    threads: int = 6,
    startup_budget_ms: int = 300000,
    metrics_enabled: bool = True,
) -> LlamaServerSettings:
    """Valid settings, with named fields replaced. No ``# type: ignore`` anywhere."""
    return LlamaServerSettings(
        endpoint=endpoint,
        model_path=model_path,
        model_alias=model_alias,
        context_size=context_size,
        threads=threads,
        startup_budget_ms=startup_budget_ms,
        metrics_enabled=metrics_enabled,
    )


def configuration(
    *,
    model_identifier: str = PLATFORM_MODEL,
    timeout_ms: int = 30000,
    max_tokens: int | None = None,
) -> AdapterConfiguration:
    return AdapterConfiguration(
        model_identifier=model_identifier,
        timeout_ms=timeout_ms,
        max_tokens=max_tokens,
    )


def ready_transport() -> ControlledTransport:
    """A transport whose runtime is ready and answers one completion."""
    transport = ControlledTransport()
    transport.answer(HEALTH_PATH, 200, {"status": "ok"})
    transport.answer(CHAT_COMPLETIONS_PATH, 200, COMPLETION)
    return transport


async def ready_adapter(
    transport: ControlledTransport | None = None,
    **config: object,
) -> tuple[LlamaServerAdapter, ControlledTransport]:
    """An initialized adapter over a transport whose runtime reports ready."""
    carrier = transport if transport is not None else ready_transport()
    adapter = LlamaServerAdapter(settings(), carrier)
    timeout = config.get("timeout_ms", 30000)
    bound = config.get("max_tokens")
    assert isinstance(timeout, int)
    assert bound is None or isinstance(bound, int)
    await adapter.initialize(
        configuration(timeout_ms=timeout, max_tokens=bound), CONTEXT
    )
    return adapter, carrier


# --------------------------------------------------------------------------
# Conformance
# --------------------------------------------------------------------------


class TestLlamaServerAdapterConformance(ServingAdapterConformance):
    """The real adapter, held to every obligation the protocol publishes.

    The transport is controlled, so this establishes that the adapter satisfies
    the contract and nothing about the runtime. It is inherited rather than
    copied, which is what makes "it implements the contract" mean the contract
    and not a version of it edited until this adapter passed.
    """

    @pytest.fixture
    def adapter(self) -> ServingAdapter:
        return LlamaServerAdapter(settings(), ready_transport())

    @pytest.fixture
    def test_config(self) -> AdapterConfiguration:
        return configuration()


# --------------------------------------------------------------------------
# Initialization
# --------------------------------------------------------------------------


async def test_initialization_contacts_nothing() -> None:
    """A platform may start before its runtime has finished loading."""
    transport = ready_transport()
    adapter = LlamaServerAdapter(settings(), transport)
    await adapter.initialize(configuration(), CONTEXT)

    assert transport.calls == []
    assert adapter.readiness_state is ReadinessState.NOT_PROBED


async def test_a_mock_labelled_model_identity_is_refused() -> None:
    """The mirror of the mock adapter refusing a real identity."""
    adapter = LlamaServerAdapter(settings(), ready_transport())
    with pytest.raises(InvalidAdapterConfigError) as caught:
        await adapter.initialize(
            configuration(model_identifier="mock-fixed-fixture"), CONTEXT
        )

    assert caught.value.field == "model_identifier"


async def test_a_generation_bound_above_the_context_length_is_refused() -> None:
    adapter = LlamaServerAdapter(settings(context_size=512), ready_transport())
    with pytest.raises(InvalidAdapterConfigError) as caught:
        await adapter.initialize(configuration(max_tokens=4096), CONTEXT)

    assert caught.value.field == "max_tokens"


async def test_a_weight_file_the_decision_does_not_pin_is_refused() -> None:
    adapter = LlamaServerAdapter(
        settings(model_path="/models/some-other-model.gguf"), ready_transport()
    )
    with pytest.raises(InvalidAdapterConfigError) as caught:
        await adapter.initialize(configuration(), CONTEXT)

    assert caught.value.field == "modelPath"


async def test_re_initialization_forgets_every_earlier_observation() -> None:
    adapter, _ = await ready_adapter()
    await adapter.is_ready(CONTEXT)
    observed_before = adapter.readiness_state

    await adapter.initialize(configuration(), CONTEXT)

    assert observed_before is ReadinessState.READY
    assert adapter.readiness_state is ReadinessState.NOT_PROBED
    assert adapter.disagreements == ()


# --------------------------------------------------------------------------
# Readiness
# --------------------------------------------------------------------------


async def test_an_uninitialized_adapter_is_not_ready_and_probes_nothing() -> None:
    transport = ready_transport()
    adapter = LlamaServerAdapter(settings(), transport)

    assert await adapter.is_ready(CONTEXT) is False
    assert transport.calls == []


async def test_readiness_is_false_until_an_observed_two_hundred() -> None:
    """The acceptance criterion, as a property of the adapter rather than a promise."""
    transport = ready_transport()
    transport.answer(HEALTH_PATH, 503)
    adapter, _ = await ready_adapter(transport)

    assert await adapter.is_ready(CONTEXT) is False
    assert adapter.readiness_state is ReadinessState.LOADING

    transport.answer(HEALTH_PATH, 200, {"status": "ok"})

    assert await adapter.is_ready(CONTEXT) is True


async def test_a_ready_runtime_that_starts_loading_again_is_not_ready() -> None:
    """A replaced pod is a fresh process with a fresh load."""
    adapter, transport = await ready_adapter()
    assert await adapter.is_ready(CONTEXT) is True

    transport.answer(HEALTH_PATH, 503)

    assert await adapter.is_ready(CONTEXT) is False


async def test_a_status_the_mapping_does_not_publish_is_not_ready() -> None:
    transport = ready_transport()
    transport.answer(HEALTH_PATH, 418)
    adapter, _ = await ready_adapter(transport)

    assert await adapter.is_ready(CONTEXT) is False
    assert adapter.readiness_state is ReadinessState.UNEXPECTED


@pytest.mark.parametrize(
    "failure", [TransportUnreachable(), TransportTimeout(), TransportProtocolError()]
)
async def test_a_probe_that_fails_reports_not_ready_rather_than_raising(
    failure: TransportError,
) -> None:
    """*Unreachable* is an answer to the readiness question, not a fault."""
    transport = ready_transport()
    transport.fail(HEALTH_PATH, failure)
    adapter, _ = await ready_adapter(transport)

    assert await adapter.is_ready(CONTEXT) is False
    assert adapter.readiness_state is ReadinessState.UNREACHABLE


async def test_a_probe_asks_the_health_path_and_nothing_else() -> None:
    adapter, transport = await ready_adapter()
    await adapter.is_ready(CONTEXT)

    assert transport.paths() == [HEALTH_PATH]


# --------------------------------------------------------------------------
# Inference
# --------------------------------------------------------------------------


async def test_a_completion_is_returned_as_a_domain_result() -> None:
    adapter, _ = await ready_adapter()
    result = await adapter.infer("what is Kubernetes?", CONTEXT)

    assert result.content == "a controlled answer"
    assert result.model == PLATFORM_MODEL
    assert result.adapter_kind == LLAMA_SERVER_ADAPTER_KIND
    assert result.adapter_kind == "real"
    assert result.finish_reason == "stop"
    assert result.usage == TokenUsage(input_tokens=20, output_tokens=23)


async def test_the_result_reports_the_platform_identity_not_the_runtime_alias() -> None:
    """The contract publishes the platform's identifier; the runtime answers to
    an alias an operator chose, and the two are different strings."""
    adapter, _ = await ready_adapter()
    result = await adapter.infer("hello", CONTEXT)

    assert result.model == PLATFORM_MODEL
    assert result.model != RUNTIME_ALIAS


async def test_the_request_goes_to_the_completion_path_under_the_budget() -> None:
    adapter, transport = await ready_adapter(timeout_ms=12000)
    await adapter.infer("hello", CONTEXT)

    post = next(call for call in transport.calls if call.method == "POST")
    assert _path_of(post.url) == CHAT_COMPLETIONS_PATH
    assert post.timeout_s == 12.0


async def test_the_first_request_probes_readiness_before_sending() -> None:
    """A tracker that has observed nothing does not optimistically send."""
    adapter, transport = await ready_adapter()
    await adapter.infer("hello", CONTEXT)

    assert transport.paths() == [HEALTH_PATH, CHAT_COMPLETIONS_PATH]


async def test_a_second_request_does_not_re_probe() -> None:
    """Readiness is a state, not a per-request question."""
    adapter, transport = await ready_adapter()
    await adapter.infer("one", CONTEXT)
    await adapter.infer("two", CONTEXT)

    assert transport.paths() == [
        HEALTH_PATH,
        CHAT_COMPLETIONS_PATH,
        CHAT_COMPLETIONS_PATH,
    ]


async def test_a_loading_runtime_refuses_the_request() -> None:
    transport = ready_transport()
    transport.answer(HEALTH_PATH, 503)
    adapter, _ = await ready_adapter(transport)

    with pytest.raises(ModelNotReadyError) as caught:
        await adapter.infer("hello", CONTEXT)
    assert caught.value.code == "model-not-ready"


async def test_an_uninitialized_adapter_refuses_the_request() -> None:
    adapter = LlamaServerAdapter(settings(), ready_transport())
    with pytest.raises(ModelNotReadyError) as caught:
        await adapter.infer("hello", CONTEXT)

    assert caught.value.message == NOT_INITIALIZED_MESSAGE


async def test_a_shut_down_adapter_refuses_the_request() -> None:
    adapter, _ = await ready_adapter()
    await adapter.shutdown(CONTEXT)

    with pytest.raises(ModelNotReadyError) as caught:
        await adapter.infer("hello", CONTEXT)
    assert caught.value.message == SHUT_DOWN_MESSAGE


async def test_a_generation_bound_reaches_the_request() -> None:
    adapter, transport = await ready_adapter(max_tokens=128)
    await adapter.infer("hello", CONTEXT)

    post = next(call for call in transport.calls if call.method == "POST")
    assert post.payload is not None
    assert post.payload["max_tokens"] == 128


# --------------------------------------------------------------------------
# Canonical errors
# --------------------------------------------------------------------------


async def test_a_runtime_that_answers_loading_to_a_completion_is_not_ready() -> None:
    """And the tracker learns it here rather than waiting for the next probe."""
    transport = ready_transport()
    transport.answer(CHAT_COMPLETIONS_PATH, 503, {"error": {"code": 503}})
    adapter, _ = await ready_adapter(transport)

    with pytest.raises(ModelNotReadyError):
        await adapter.infer("hello", CONTEXT)
    assert adapter.readiness_state is ReadinessState.LOADING


@pytest.mark.parametrize("status", [400, 404, 429, 500, 502, 504, 301])
async def test_an_unexpected_status_is_an_internal_error(status: int) -> None:
    transport = ready_transport()
    transport.answer(CHAT_COMPLETIONS_PATH, status, {"error": "whatever"})
    adapter, _ = await ready_adapter(transport)

    with pytest.raises(InternalError) as caught:
        await adapter.infer("hello", CONTEXT)
    assert caught.value.code == "internal-error"


async def test_a_runtime_that_ran_out_of_time_is_an_upstream_timeout() -> None:
    transport = ready_transport()
    transport.fail(CHAT_COMPLETIONS_PATH, TransportTimeout())
    adapter, _ = await ready_adapter(transport)

    with pytest.raises(UpstreamTimeoutError) as caught:
        await adapter.infer("hello", CONTEXT)
    assert caught.value.code == "upstream-timeout"


async def test_a_transport_that_ignores_its_budget_hits_the_outer_deadline() -> None:
    """The reason the outer deadline exists: a transport is a value a caller
    supplies, and a protocol cannot enforce the promise it asks for."""
    transport = ready_transport()
    transport.stall_s = 0.5
    adapter = LlamaServerAdapter(settings(), transport)
    await adapter.initialize(configuration(timeout_ms=20), CONTEXT)
    transport.answer(HEALTH_PATH, 200, {"status": "ok"})

    with pytest.raises(RequestTimeoutError) as caught:
        await adapter.infer("hello", CONTEXT)
    assert caught.value.code == "request-timeout"


async def test_an_unreachable_runtime_is_capability_unavailable() -> None:
    """The code the accepted mapping decided, and not ``model-not-ready``."""
    transport = ready_transport()
    transport.fail(HEALTH_PATH, TransportUnreachable())
    adapter, _ = await ready_adapter(transport)

    with pytest.raises(CapabilityUnavailableError) as caught:
        await adapter.infer("hello", CONTEXT)
    assert caught.value.code == "capability-unavailable"


async def test_an_unreachable_completion_is_capability_unavailable() -> None:
    """Discovered on the request rather than on the probe, and the same code."""
    transport = ready_transport()
    transport.fail(CHAT_COMPLETIONS_PATH, TransportUnreachable())
    adapter, _ = await ready_adapter(transport)

    with pytest.raises(CapabilityUnavailableError):
        await adapter.infer("hello", CONTEXT)


async def test_a_body_the_adapter_cannot_read_is_an_internal_error() -> None:
    transport = ready_transport()
    transport.answer(CHAT_COMPLETIONS_PATH, 200, {"unexpected": "shape"})
    adapter, _ = await ready_adapter(transport)

    with pytest.raises(InternalError):
        await adapter.infer("hello", CONTEXT)


@pytest.mark.parametrize(
    ("arrange", "expected_code"),
    [
        pytest.param(
            lambda t: t.answer(CHAT_COMPLETIONS_PATH, 500, None),
            "internal-error",
            id="runtime-error-response",
        ),
        pytest.param(
            lambda t: t.fail(CHAT_COMPLETIONS_PATH, TransportTimeout()),
            "upstream-timeout",
            id="runtime-timeout",
        ),
        pytest.param(
            lambda t: t.fail(CHAT_COMPLETIONS_PATH, TransportUnreachable()),
            "capability-unavailable",
            id="runtime-unreachable",
        ),
    ],
)
async def test_every_failure_carries_the_identifiers_the_caller_supplied(
    arrange: object, expected_code: str
) -> None:
    transport = ready_transport()
    assert callable(arrange)
    arrange(transport)
    adapter, _ = await ready_adapter(transport)

    with pytest.raises(CanonicalError) as caught:
        await adapter.infer("hello", CONTEXT)
    rendered = caught.value.as_dict()
    assert rendered["code"] == expected_code
    assert rendered["requestId"] == "req-1"
    assert rendered["correlationId"] == "corr-2"


async def test_no_canonical_error_repeats_the_prompt() -> None:
    """The redaction rule at the one place in this distribution that has a prompt."""
    transport = ready_transport()
    transport.answer(CHAT_COMPLETIONS_PATH, 500, {"echo": SENSITIVE_PROMPT})
    adapter, _ = await ready_adapter(transport)

    with pytest.raises(InternalError) as caught:
        await adapter.infer(SENSITIVE_PROMPT, CONTEXT)
    rendered = json.dumps(caught.value.as_dict())
    assert SENSITIVE_PROMPT not in rendered
    assert "000-11-2222" not in rendered


async def test_the_prompt_is_not_retained_on_the_adapter() -> None:
    """It is built into one body, sent, and forgotten.

    The transport is excluded from the sweep because the double in this file
    records every request it was given on purpose — that recording is the test's,
    not the adapter's, and asserting against it would assert against the harness.
    """
    adapter, _ = await ready_adapter()
    await adapter.infer(SENSITIVE_PROMPT, CONTEXT)

    retained = {
        name: value for name, value in vars(adapter).items() if name != "_transport"
    }
    assert SENSITIVE_PROMPT not in repr(retained)
    assert "000-11-2222" not in repr(retained)
    assert "_transport" in vars(adapter)


# --------------------------------------------------------------------------
# Error mapping through the protocol
# --------------------------------------------------------------------------


async def test_a_canonical_error_passes_through_unchanged() -> None:
    adapter, _ = await ready_adapter()
    original = ModelNotReadyError("something", context=CONTEXT)

    assert await adapter.map_error_to_canonical(original, CONTEXT) is original


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (TransportTimeout(), "upstream-timeout"),
        (TransportUnreachable(), "capability-unavailable"),
        (TransportProtocolError(), "internal-error"),
    ],
)
async def test_a_transport_failure_maps_to_its_canonical_code(
    failure: TransportError, expected: str
) -> None:
    adapter, _ = await ready_adapter()

    assert (await adapter.map_error_to_canonical(failure, CONTEXT)).code == expected


async def test_an_unrecognised_error_loses_its_message() -> None:
    """A runtime message is where a path or a credential arrives in a response."""
    adapter, _ = await ready_adapter()
    mapped = await adapter.map_error_to_canonical(
        RuntimeError("/mnt/models/Qwen3-1.7B-Q8_0.gguf failed"), CONTEXT
    )

    assert mapped.code == "internal-error"
    assert "/mnt/models" not in mapped.message


# --------------------------------------------------------------------------
# Metadata, capabilities, telemetry
# --------------------------------------------------------------------------


async def test_model_metadata_reports_the_configured_identity_and_pinned_revision() -> (
    None
):
    adapter, _ = await ready_adapter()
    metadata = await adapter.get_model_metadata()

    assert metadata.identifier == PLATFORM_MODEL
    assert metadata.revision == PINNED_MODEL_REVISION


async def test_model_metadata_before_initialization_is_a_failure_not_a_guess() -> None:
    adapter = LlamaServerAdapter(settings(), ready_transport())
    with pytest.raises(InternalError):
        await adapter.get_model_metadata()


async def test_runtime_metadata_falls_back_to_the_pinned_digest() -> None:
    """Both identify real bytes; neither is invented."""
    adapter, _ = await ready_adapter()
    metadata = await adapter.get_runtime_metadata()

    assert metadata.name == LLAMA_SERVER_RUNTIME_NAME
    assert metadata.version == PINNED_IMAGE_DIGEST


async def test_runtime_metadata_prefers_an_observed_build_string() -> None:
    transport = ready_transport()
    transport.answer(MODELS_PATH, 200, {"data": [{"id": RUNTIME_ALIAS}]})
    transport.answer(
        PROPS_PATH,
        200,
        {
            "model_path": f"/models/{PINNED_MODEL_FILE}",
            "build_info": "b10588-70adb1b4c",
            "total_slots": 4,
        },
    )
    adapter, _ = await ready_adapter(transport)
    await adapter.observe_identity(CONTEXT)

    assert (await adapter.get_runtime_metadata()).version == "b10588-70adb1b4c"


async def test_capabilities_are_the_declaration_the_package_publishes() -> None:
    adapter, _ = await ready_adapter()

    assert await adapter.get_capabilities() == list(LLAMA_SERVER_CAPABILITIES)


async def test_token_counting_is_declared_supported_and_the_result_carries_it() -> None:
    """A supported capability with a record behind it, unlike the mock's."""
    adapter, _ = await ready_adapter()
    declared = {row.name: row.supported for row in await adapter.get_capabilities()}
    result = await adapter.infer("hello", CONTEXT)

    assert declared["token-counting"] is True
    assert result.usage is not None


async def test_absent_token_counts_are_absence_rather_than_zero() -> None:
    transport = ready_transport()
    transport.answer(
        CHAT_COMPLETIONS_PATH,
        200,
        {key: value for key, value in COMPLETION.items() if key != "usage"},
    )
    adapter, _ = await ready_adapter(transport)

    assert (await adapter.infer("hello", CONTEXT)).usage is None


async def test_streaming_is_declared_unsupported() -> None:
    adapter, _ = await ready_adapter()
    declared = {row.name: row.supported for row in await adapter.get_capabilities()}

    assert declared["streaming"] is False


async def test_the_adapter_reports_no_metric_of_its_own() -> None:
    """`ADR 0002`'s `T7` failed on exactly this, so InferOps counts its own."""
    adapter, _ = await ready_adapter()
    mapping = await adapter.get_telemetry_mapping()

    assert mapping.platform_metric_ids == ()
    assert mapping.token_usage is True
    assert mapping.error_code is None


# --------------------------------------------------------------------------
# Identity disagreement
# --------------------------------------------------------------------------


async def test_a_runtime_serving_the_configured_alias_disagrees_about_nothing() -> None:
    transport = ready_transport()
    transport.answer(MODELS_PATH, 200, {"data": [{"id": RUNTIME_ALIAS}]})
    transport.answer(PROPS_PATH, 200, {"model_path": f"/models/{PINNED_MODEL_FILE}"})
    adapter, _ = await ready_adapter(transport)
    await adapter.observe_identity(CONTEXT)

    assert adapter.disagreements == ()


async def test_a_runtime_serving_another_alias_is_recorded_as_a_disagreement() -> None:
    transport = ready_transport()
    transport.answer(MODELS_PATH, 200, {"data": [{"id": "something-else"}]})
    transport.answer(PROPS_PATH, 200, {"model_path": f"/models/{PINNED_MODEL_FILE}"})
    adapter, _ = await ready_adapter(transport)
    await adapter.observe_identity(CONTEXT)

    assert "runtime-model-alias-differs-from-configured-alias" in adapter.disagreements


async def test_a_completion_naming_another_model_is_recorded_not_raised() -> None:
    """A deployment fact an operator needs to see. Failing the request that
    discovered it would hide the fact behind an error nobody could explain."""
    transport = ready_transport()
    transport.answer(
        CHAT_COMPLETIONS_PATH, 200, {**COMPLETION, "model": "a-different-model"}
    )
    adapter, _ = await ready_adapter(transport)
    result = await adapter.infer("hello", CONTEXT)

    assert result.content == "a controlled answer"
    assert COMPLETION_ALIAS_DISAGREEMENT in adapter.disagreements


async def test_a_completion_naming_the_configured_alias_clears_the_disagreement() -> (
    None
):
    transport = ready_transport()
    transport.answer(
        CHAT_COMPLETIONS_PATH, 200, {**COMPLETION, "model": "a-different-model"}
    )
    adapter, _ = await ready_adapter(transport)
    await adapter.infer("hello", CONTEXT)
    assert COMPLETION_ALIAS_DISAGREEMENT in adapter.disagreements

    transport.answer(CHAT_COMPLETIONS_PATH, 200, COMPLETION)
    await adapter.infer("hello", CONTEXT)

    assert COMPLETION_ALIAS_DISAGREEMENT not in adapter.disagreements


async def test_a_disagreement_is_not_recorded_twice() -> None:
    transport = ready_transport()
    transport.answer(
        CHAT_COMPLETIONS_PATH, 200, {**COMPLETION, "model": "a-different-model"}
    )
    adapter, _ = await ready_adapter(transport)
    await adapter.infer("one", CONTEXT)
    await adapter.infer("two", CONTEXT)

    assert adapter.disagreements.count(COMPLETION_ALIAS_DISAGREEMENT) == 1


async def test_identity_is_not_read_on_the_request_path() -> None:
    """Two round trips per completion to re-answer an operational question would
    be charging every caller for it."""
    adapter, transport = await ready_adapter()
    await adapter.infer("hello", CONTEXT)

    assert MODELS_PATH not in transport.paths()
    assert PROPS_PATH not in transport.paths()


async def test_observing_identity_before_initialization_is_refused() -> None:
    adapter = LlamaServerAdapter(settings(), ready_transport())
    with pytest.raises(ModelNotReadyError):
        await adapter.observe_identity(CONTEXT)


async def test_an_identity_read_that_fails_is_canonical() -> None:
    transport = ready_transport()
    transport.fail(PROPS_PATH, TransportUnreachable())
    adapter, _ = await ready_adapter(transport)

    with pytest.raises(CapabilityUnavailableError):
        await adapter.observe_identity(CONTEXT)


async def test_an_identity_endpoint_answering_an_error_status_is_canonical() -> None:
    transport = ready_transport()
    transport.answer(MODELS_PATH, 500, {"error": "no"})
    adapter, _ = await ready_adapter(transport)

    with pytest.raises(InternalError):
        await adapter.observe_identity(CONTEXT)


# --------------------------------------------------------------------------
# Shutdown
# --------------------------------------------------------------------------


async def test_shutdown_releases_the_transport_and_forgets_the_observations() -> None:
    adapter, transport = await ready_adapter()
    await adapter.is_ready(CONTEXT)
    await adapter.shutdown(CONTEXT)

    assert transport.closed == 1
    assert adapter.readiness_state is ReadinessState.NOT_PROBED
    assert adapter.observed_identity.build_info is None


async def test_shutdown_does_not_fail_on_a_transport_that_will_not_close() -> None:
    """The adapter has already stopped accepting work by then."""
    transport = ready_transport()
    transport.close_failure = TransportUnreachable()
    adapter, _ = await ready_adapter(transport)
    await adapter.shutdown(CONTEXT)

    assert transport.closed == 1
    assert adapter.readiness_state is ReadinessState.NOT_PROBED


async def test_a_shut_down_adapter_is_not_ready_and_probes_nothing() -> None:
    adapter, transport = await ready_adapter()
    await adapter.shutdown(CONTEXT)
    before = len(transport.calls)

    assert await adapter.is_ready(CONTEXT) is False
    assert len(transport.calls) == before


# --------------------------------------------------------------------------
# Isolation
# --------------------------------------------------------------------------


async def test_the_adapter_builds_no_url_outside_the_published_paths() -> None:
    """Every URL it ever dials comes from the settings' closed path set."""
    transport = ready_transport()
    transport.answer(MODELS_PATH, 200, {"data": [{"id": RUNTIME_ALIAS}]})
    transport.answer(PROPS_PATH, 200, {"model_path": f"/models/{PINNED_MODEL_FILE}"})
    adapter, _ = await ready_adapter(transport)
    await adapter.infer("hello", CONTEXT)
    await adapter.observe_identity(CONTEXT)

    published = {
        HEALTH_PATH,
        PROPS_PATH,
        MODELS_PATH,
        METRICS_PATH,
        CHAT_COMPLETIONS_PATH,
    }
    assert set(transport.paths()) <= published


async def test_no_runtime_vocabulary_reaches_the_domain_result() -> None:
    """A context length, a thread count, an endpoint, and a build string are
    `llama.cpp` concepts. None of them is in what a caller receives."""
    adapter, _ = await ready_adapter()
    result = await adapter.infer("hello", CONTEXT)

    rendered = repr(result)
    for leaked in ("ctx-size", "8080", "svc.cluster.local", "/models/", "threads"):
        assert leaked not in rendered
