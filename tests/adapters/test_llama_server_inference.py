"""The request sent, the response read, and the mapping — checked against source.

The most important checks in this module are the ones that read
[the accepted inference-API surface](../../docs/serving/inference-api-surface.v1alpha1.json)
and compare it to the table in
:mod:`inferops.adapters.llama_cpp.inference`. That table is a *copy* of a
decision, and the pins suite already established the habit this one continues: a
constant nobody compares to its source is a copy that drifts.

The rest is normalisation, and it has one shape. A member that is absent is
absent — ``usage`` is ``None`` and never a zero-filled or estimated stand-in — and
a member that is present and malformed is a refusal, because a token count nobody
can read is not a token count that is missing.

Two negative obligations run through the whole file:

- **no error message repeats anything from a request or a response**, which is
  asserted directly against a body carrying a container path and a prompt-shaped
  string;
- **``rate-limited`` is never produced**, because the accepted record lists it
  among the codes V1 does not emit and this adapter is not permitted to invent an
  observation of a limiter that does not exist.

Every check reads objects and files from this repository. No network, no cluster,
no model, no clock, and no randomness.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inferops.adapters.llama_cpp import (
    ENABLE_THINKING_KEY,
    ENABLE_THINKING_VALUE,
    ERROR_CODE_BY_CONDITION,
    ERROR_CONDITIONS,
    PINNED_MODEL_FILE,
    ROLE_USER,
    SURFACE_DATA_REF,
    SURFACE_DECISION_REF,
    UNREADABLE_RESPONSE_MESSAGE,
    ErrorCondition,
    LlamaServerSettings,
    NormalizedCompletion,
    build_request,
    error_for_status,
    error_for_transport_failure,
    is_success,
    normalize_response,
    request_deadline_error,
    unreachable_error,
)
from inferops.adapters.llama_cpp.transport import (
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
    ModelNotReadyError,
    RequestTimeoutError,
    TokenUsage,
    UpstreamTimeoutError,
)

pytestmark = pytest.mark.adapter

REPO_ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((REPO_ROOT / SURFACE_DATA_REF).read_text(encoding="utf-8"))

CONTEXT = RequestContext(request_id="req-1", correlation_id="corr-2")

#: A body carrying values that must never reach a caller's error: a container
#: path, and a string shaped like a prompt.
SENSITIVE_BODY = {
    "model_path": "/mnt/models/Qwen3-1.7B-Q8_0.gguf",
    "prompt": "the caller's private question about their own data",
}

#: The completion body the feasibility record preserved, reduced to the members
#: this adapter reads. The full recorded body is in that record; what is copied
#: here is its shape.
COMPLETION_BODY: dict[str, object] = {
    "choices": [
        {
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "role": "assistant",
                "content": (
                    "Kubernetes is an open-source platform for automating the "
                    "deployment, scaling, and management of containerized "
                    "applications."
                ),
            },
        }
    ],
    "model": "qwen3-1.7b-q8_0",
    "object": "chat.completion",
    "usage": {"completion_tokens": 23, "prompt_tokens": 20, "total_tokens": 43},
}


def settings(
    *,
    endpoint: str = "http://llama-server.inferops-serving.svc.cluster.local:8080",
    model_path: str = f"/models/{PINNED_MODEL_FILE}",
    model_alias: str = "qwen3-1.7b-q8_0",
    context_size: int = 4096,
    threads: int = 6,
    startup_budget_ms: int = 300000,
    metrics_enabled: bool = True,
) -> LlamaServerSettings:
    """Valid settings, with named fields replaced.

    Every parameter is named and typed rather than collected into a
    ``**overrides`` mapping, for the reason the settings suite gives: the mapping
    form forces a ``# type: ignore`` at the constructor, and there is none of
    those anywhere in this repository.
    """
    return LlamaServerSettings(
        endpoint=endpoint,
        model_path=model_path,
        model_alias=model_alias,
        context_size=context_size,
        threads=threads,
        startup_budget_ms=startup_budget_ms,
        metrics_enabled=metrics_enabled,
    )


def configuration(max_tokens: int | None = None) -> AdapterConfiguration:
    return AdapterConfiguration(
        model_identifier="qwen3-1-7b-instruct",
        timeout_ms=30000,
        max_tokens=max_tokens,
    )


# --------------------------------------------------------------------------
# The mapping, compared to the record that decided it
# --------------------------------------------------------------------------


def test_every_condition_this_adapter_holds_exists_in_the_accepted_record() -> None:
    """A condition identifier nobody else publishes is one this adapter invented."""
    published = {row["conditionId"] for row in SURFACE["errorMapping"]}
    held = {row.condition_id for row in ERROR_CONDITIONS}

    assert held <= published, sorted(held - published)


@pytest.mark.parametrize(
    "condition", ERROR_CONDITIONS, ids=lambda row: row.condition_id
)
def test_each_held_condition_maps_to_the_code_the_record_decided(
    condition: ErrorCondition,
) -> None:
    """The copy and its source, field by field."""
    row = next(
        entry
        for entry in SURFACE["errorMapping"]
        if entry["conditionId"] == condition.condition_id
    )

    assert condition.code == row["code"]
    assert condition.observed_in_trial == row["observedInTrial"]


def test_the_conditions_left_to_the_api_layer_are_absent_rather_than_stubbed() -> None:
    """Three rows belong to a component this change does not build."""
    published = {row["conditionId"] for row in SURFACE["errorMapping"]}
    held = {row.condition_id for row in ERROR_CONDITIONS}

    assert published - held == {
        "request-outside-subset",
        "streaming-requested",
        "unsupported-contract-version",
    }


def test_only_one_condition_was_ever_observed_and_the_table_says_so() -> None:
    """Five of six are mappings rather than observations, and say which."""
    observed = [row.condition_id for row in ERROR_CONDITIONS if row.observed_in_trial]

    assert observed == ["model-loading"]


@pytest.mark.parametrize(
    "condition", ERROR_CONDITIONS, ids=lambda row: row.condition_id
)
def test_every_condition_states_a_basis(condition: ErrorCondition) -> None:
    assert len(condition.basis) > 40, condition.condition_id


def test_the_lookup_and_the_table_publish_the_same_pairs() -> None:
    assert {
        row.condition_id: row.code for row in ERROR_CONDITIONS
    } == ERROR_CODE_BY_CONDITION


def test_the_records_this_module_cites_exist() -> None:
    assert (REPO_ROOT / SURFACE_DECISION_REF).is_file()
    assert (REPO_ROOT / SURFACE_DATA_REF).is_file()


def test_rate_limited_is_never_produced_and_the_record_says_why() -> None:
    """V1 has no rate limiter, so a code claiming one would be a claim.

    The runtime's own deferral series is a gauge of instantaneous state, not a
    limit InferOps enforces, and the accepted record lists the code among those
    this platform does not emit.
    """
    not_emitted = {row["code"]: row["reason"] for row in SURFACE["codesNotEmitted"]}

    assert "rate-limited" in not_emitted
    assert "rate limiter" in not_emitted["rate-limited"]
    assert "rate-limited" not in {row.code for row in ERROR_CONDITIONS}
    assert "rate-limited" not in set(ERROR_CODE_BY_CONDITION.values())


@pytest.mark.parametrize("status", [429, 503, 500, 200])
def test_no_status_produces_a_rate_limited_error(status: int) -> None:
    """A 429 is an unexpected status like any other, not an observed limit."""
    produced = error_for_status(status, CONTEXT)

    assert produced is None or produced.code != "rate-limited"


# --------------------------------------------------------------------------
# The request
# --------------------------------------------------------------------------


def test_the_request_names_the_runtime_alias_rather_than_the_platform_identity() -> (
    None
):
    """This is the runtime's API, and the alias is the name it answers to."""
    body = build_request(configuration(), settings(), "hello")

    assert body["model"] == "qwen3-1.7b-q8_0"
    assert body["model"] != configuration().model_identifier


def test_the_request_carries_exactly_one_user_message() -> None:
    """The protocol hands the adapter one prompt and publishes no conversation."""
    body = build_request(configuration(), settings(), "what is Kubernetes?")

    assert body["messages"] == [{"role": ROLE_USER, "content": "what is Kubernetes?"}]
    assert ROLE_USER == "user"


def test_the_request_carries_no_system_message() -> None:
    """A system message would be content this adapter authored on a caller's
    behalf, appearing in a completion nobody asked for it in."""
    messages = build_request(configuration(), settings(), "hello")["messages"]

    assert isinstance(messages, list)
    assert all(message["role"] != "system" for message in messages)


@pytest.mark.parametrize(
    "parameter",
    ["temperature", "top_p", "top_k", "seed", "repeat_penalty", "min_p", "n"],
)
def test_the_request_carries_no_sampling_parameter(parameter: str) -> None:
    """`ADR 0002` records the sampling defaults as undecided.

    A value emitted here would be read back later as a recommendation nobody
    made, and the frozen adapter protocol has no parameter to pass a caller's
    through either.
    """
    assert parameter not in build_request(configuration(), settings(), "hello")


def test_an_omitted_generation_bound_is_an_omitted_member() -> None:
    """Never a default this adapter chose."""
    assert "max_tokens" not in build_request(configuration(), settings(), "hello")


def test_a_configured_generation_bound_is_sent() -> None:
    body = build_request(configuration(max_tokens=128), settings(), "hello")

    assert body["max_tokens"] == 128


def test_the_request_turns_off_the_reasoning_block() -> None:
    """The trial's request carried this, and its response is the shape parsed here."""
    body = build_request(configuration(), settings(), "hello")

    assert body["chat_template_kwargs"] == {ENABLE_THINKING_KEY: ENABLE_THINKING_VALUE}
    assert ENABLE_THINKING_VALUE is False


def test_the_request_carries_no_streaming_member() -> None:
    """V1's protocol has no streaming method, so nothing may ask for one."""
    assert "stream" not in build_request(configuration(), settings(), "hello")


def test_the_request_body_is_json_serialisable() -> None:
    """It is about to be encoded, so a body that cannot be is a defect here."""
    body = build_request(configuration(max_tokens=64), settings(), "hello")

    assert json.loads(json.dumps(body)) == body


# --------------------------------------------------------------------------
# The response
# --------------------------------------------------------------------------


def test_the_recorded_completion_shape_is_read() -> None:
    """The one response shape this project has ever observed."""
    completion = normalize_response(COMPLETION_BODY, context=CONTEXT)

    assert completion.content.startswith("Kubernetes is an open-source platform")
    assert completion.finish_reason == "stop"
    assert completion.usage == TokenUsage(input_tokens=20, output_tokens=23)
    assert completion.reported_model == "qwen3-1.7b-q8_0"


def test_token_usage_totals_are_derived_rather_than_read() -> None:
    """The domain derives the total, so a runtime disagreeing about arithmetic
    cannot put a wrong total into a result."""
    completion = normalize_response(COMPLETION_BODY, context=CONTEXT)

    assert completion.usage is not None
    assert completion.usage.total_tokens == 43


def test_an_absent_usage_is_absence_and_never_a_zero() -> None:
    """The accepted record: never estimated and never zero-filled."""
    body = {key: value for key, value in COMPLETION_BODY.items() if key != "usage"}
    completion = normalize_response(body, context=CONTEXT)

    assert completion.usage is None


def test_an_absent_finish_reason_is_absence() -> None:
    body = json.loads(json.dumps(COMPLETION_BODY))
    del body["choices"][0]["finish_reason"]

    assert normalize_response(body, context=CONTEXT).finish_reason is None


def test_an_empty_finish_reason_is_absence() -> None:
    """An empty string is not a reason the runtime gave."""
    body = json.loads(json.dumps(COMPLETION_BODY))
    body["choices"][0]["finish_reason"] = ""

    assert normalize_response(body, context=CONTEXT).finish_reason is None


def test_an_empty_completion_is_content_rather_than_a_failure() -> None:
    """The domain permits empty content, and deciding that the runtime meant
    something else by it is not this adapter's call."""
    body = json.loads(json.dumps(COMPLETION_BODY))
    body["choices"][0]["message"]["content"] = ""

    assert normalize_response(body, context=CONTEXT).content == ""


def test_only_the_first_choice_is_read() -> None:
    """V1 never asks for more than one, and reading a second would be reading a
    response to a request this adapter did not send."""
    body = json.loads(json.dumps(COMPLETION_BODY))
    body["choices"].append(
        {"finish_reason": "length", "message": {"content": "second"}}
    )

    assert normalize_response(body, context=CONTEXT).content != "second"


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda body: body.pop("choices"), id="no-choices"),
        pytest.param(lambda body: body.update(choices=[]), id="empty-choices"),
        pytest.param(lambda body: body.update(choices={}), id="choices-not-a-list"),
        pytest.param(
            lambda body: body.update(choices=["text"]), id="choice-not-an-object"
        ),
        pytest.param(lambda body: body["choices"][0].pop("message"), id="no-message"),
        pytest.param(
            lambda body: body["choices"][0]["message"].pop("content"), id="no-content"
        ),
        pytest.param(
            lambda body: body["choices"][0]["message"].update(content=None),
            id="null-content",
        ),
        pytest.param(
            lambda body: body["choices"][0]["message"].update(content=7),
            id="numeric-content",
        ),
        pytest.param(
            lambda body: body["choices"][0].update(finish_reason=3),
            id="numeric-finish-reason",
        ),
        pytest.param(lambda body: body.update(model=5), id="numeric-model"),
        pytest.param(lambda body: body.update(usage="none"), id="usage-not-an-object"),
        pytest.param(
            lambda body: body["usage"].pop("prompt_tokens"), id="no-prompt-tokens"
        ),
        pytest.param(
            lambda body: body["usage"].update(completion_tokens=True),
            id="boolean-completion-tokens",
        ),
        pytest.param(
            lambda body: body["usage"].update(prompt_tokens=-1),
            id="negative-prompt-tokens",
        ),
        pytest.param(
            lambda body: body["usage"].update(completion_tokens="23"),
            id="string-completion-tokens",
        ),
    ],
)
def test_a_body_this_adapter_cannot_read_is_refused(mutate: object) -> None:
    """Refused rather than guessed at, and always with the same canonical code."""
    body = json.loads(json.dumps(COMPLETION_BODY))
    assert callable(mutate)
    mutate(body)

    with pytest.raises(InternalError) as caught:
        normalize_response(body, context=CONTEXT)
    assert caught.value.code == "internal-error"
    assert caught.value.message == UNREADABLE_RESPONSE_MESSAGE


@pytest.mark.parametrize("body", [None, "a string", 7, [1, 2], True])
def test_a_body_that_is_not_an_object_is_refused(body: object) -> None:
    with pytest.raises(InternalError):
        normalize_response(body, context=CONTEXT)


def test_a_refusal_carries_the_identifiers_the_caller_supplied() -> None:
    with pytest.raises(InternalError) as caught:
        normalize_response("not a completion", context=CONTEXT)

    assert caught.value.as_dict()["requestId"] == "req-1"
    assert caught.value.as_dict()["correlationId"] == "corr-2"


def test_a_refusal_repeats_nothing_from_the_body() -> None:
    """A container path and a prompt-shaped string, neither of which may escape."""
    with pytest.raises(InternalError) as caught:
        normalize_response(SENSITIVE_BODY, context=CONTEXT)

    rendered = json.dumps(caught.value.as_dict())
    for value in SENSITIVE_BODY.values():
        assert value not in rendered
    assert "/mnt/models" not in rendered


def test_a_completion_this_adapter_reads_is_not_stored_anywhere_in_the_result() -> None:
    """Absence preservation on the value object: nothing is carried that was not
    read, and nothing read is carried twice."""
    completion = normalize_response(COMPLETION_BODY, context=CONTEXT)

    assert completion == NormalizedCompletion(
        content=completion.content,
        finish_reason="stop",
        usage=TokenUsage(input_tokens=20, output_tokens=23),
        reported_model="qwen3-1.7b-q8_0",
    )


@pytest.mark.parametrize(
    "dropped", ["system_fingerprint", "timings", "prompt_tokens_details"]
)
def test_a_field_the_accepted_record_drops_is_not_read(dropped: str) -> None:
    """A value nobody keeps is a value nobody has to redact."""
    published = {row["field"] for row in SURFACE["notPassedThrough"]}
    assert dropped in published

    body = json.loads(json.dumps(COMPLETION_BODY))
    body[dropped] = {"anything": "at all"}
    completion = normalize_response(body, context=CONTEXT)

    assert dropped not in repr(completion)


# --------------------------------------------------------------------------
# Status and transport failures
# --------------------------------------------------------------------------


@pytest.mark.parametrize("status", [200, 201, 202, 299])
def test_a_success_status_produces_no_error(status: int) -> None:
    assert is_success(status)
    assert error_for_status(status, CONTEXT) is None


def test_the_loading_status_is_model_not_ready() -> None:
    """The one condition anything in this project has ever observed."""
    produced = error_for_status(503, CONTEXT)

    assert isinstance(produced, ModelNotReadyError)
    assert produced.code == "model-not-ready"


@pytest.mark.parametrize(
    "status",
    [100, 199, 300, 301, 302, 307, 400, 401, 403, 404, 408, 429, 500, 502, 504],
)
def test_every_other_status_is_an_internal_error(status: int) -> None:
    """Deliberately wide. Narrowing it would mean inventing behaviour for
    statuses this project has never seen."""
    produced = error_for_status(status, CONTEXT)

    assert isinstance(produced, InternalError)
    assert produced.code == "internal-error"


def test_a_status_error_repeats_no_status_code_or_body() -> None:
    produced = error_for_status(418, CONTEXT)

    assert produced is not None
    assert "418" not in produced.message


@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [
        (TransportTimeout(), "upstream-timeout"),
        (TransportUnreachable(), "capability-unavailable"),
        (TransportProtocolError(), "internal-error"),
        (TransportError(), "internal-error"),
    ],
)
def test_a_transport_failure_maps_to_the_code_the_record_decided(
    failure: TransportError, expected_code: str
) -> None:
    assert error_for_transport_failure(failure, CONTEXT).code == expected_code


def test_a_runtime_that_ran_out_of_time_is_an_upstream_timeout() -> None:
    """The far side ran out of time, so the timeout is upstream."""
    produced = error_for_transport_failure(TransportTimeout(), CONTEXT)

    assert isinstance(produced, UpstreamTimeoutError)


def test_the_adapters_own_deadline_is_a_request_timeout() -> None:
    """A different condition with a different code: this side ran out of time."""
    produced = request_deadline_error(CONTEXT)

    assert isinstance(produced, RequestTimeoutError)
    assert produced.code == "request-timeout"


def test_an_unreachable_runtime_has_exactly_one_error_wherever_it_is_found() -> None:
    """A probe that could not connect and a completion that could not be
    delivered are the same condition, and must not acquire two codes."""
    from_transport = error_for_transport_failure(TransportUnreachable(), CONTEXT)
    from_readiness = unreachable_error(CONTEXT)

    assert isinstance(from_readiness, CapabilityUnavailableError)
    assert from_transport.code == from_readiness.code
    assert from_transport.message == from_readiness.message


@pytest.mark.parametrize(
    "produced",
    [
        error_for_transport_failure(TransportTimeout(), CONTEXT),
        error_for_transport_failure(TransportUnreachable(), CONTEXT),
        error_for_transport_failure(TransportProtocolError(), CONTEXT),
        request_deadline_error(CONTEXT),
    ],
    ids=["upstream-timeout", "unreachable", "protocol", "request-timeout"],
)
def test_every_produced_error_carries_the_caller_identifiers(
    produced: CanonicalError,
) -> None:
    rendered = produced.as_dict()
    assert rendered["requestId"] == "req-1"
    assert rendered["correlationId"] == "corr-2"


@pytest.mark.parametrize(
    "produced",
    [
        error_for_transport_failure(TransportTimeout(), CONTEXT),
        error_for_transport_failure(TransportUnreachable(), CONTEXT),
        request_deadline_error(CONTEXT),
    ],
    ids=["upstream-timeout", "unreachable", "request-timeout"],
)
def test_no_produced_error_names_a_host_a_path_or_a_port(
    produced: CanonicalError,
) -> None:
    rendered = json.dumps(produced.as_dict())

    for fragment in ("http://", "svc.cluster.local", "8080", "/v1/", "/mnt/"):
        assert fragment not in rendered
