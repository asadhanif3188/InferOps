"""The inference endpoint, end to end against the mock adapter.

What a passing result here establishes: this API routes a chat-completion
request, reads it against the frozen subset, calls the selected adapter with a
prompt and a request context, and writes the domain result back into the
borrowed shape with the extension member beside it.

What it does not establish, stated because this is the layer most likely to be
read as more than it is: **nothing about a model, a runtime, or a network.** The
adapter behind it replays a committed fixture, and no byte crossed a socket — the
application is driven through the ASGI interface it implements. The evidence
class is `mock` and it ceilings at `C1`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

from inferops.adapters import (
    MOCK_ADAPTER_KIND,
    MOCK_FIXTURE_CONTENT,
    MOCK_FIXTURE_FINISH_REASON,
    MockServingAdapter,
)
from inferops.api import (
    ADAPTER_KIND_DISAGREEMENT,
    CONTRACT_VERSION,
    CORRELATION_ID_HEADER,
    EXTENSION_MEMBER,
    NOT_PASSED_THROUGH,
    REQUEST_ID_HEADER,
    InferOpsApi,
)
from inferops.api.surface import CHAT_COMPLETIONS_PATH, COMPLETION_ID_PREFIX
from inferops.domain.serving import ModelNotReadyError
from tests.support import asgi_client
from tests.support.api_composition import (
    FIXED_NOW,
    MOCK_MODEL,
    RecordingAdapter,
    build,
)

pytestmark = pytest.mark.mockintegration


def request_body(**overrides: object) -> bytes:
    body: dict[str, object] = {
        "model": MOCK_MODEL,
        "messages": [{"role": "user", "content": "hello"}],
    }
    body.update(overrides)
    return json.dumps(body).encode("utf-8")


async def post(
    api: InferOpsApi,
    body: bytes,
    *,
    headers: Sequence[tuple[str, str]] = (),
) -> asgi_client.Response:
    return await asgi_client.request(
        api, "POST", CHAT_COMPLETIONS_PATH, body=body, headers=headers
    )


# --------------------------------------------------------------------------
# The completion, in the shape the accepted record publishes
# --------------------------------------------------------------------------


async def test_a_completion_is_returned_in_the_borrowed_shape(
    mock_api: InferOpsApi,
) -> None:
    response = await post(mock_api, request_body())
    assert response.status == 200, response.text()
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == MOCK_MODEL
    assert body["created"] == FIXED_NOW
    assert body["id"].startswith(COMPLETION_ID_PREFIX)


async def test_exactly_one_choice_is_returned(mock_api: InferOpsApi) -> None:
    """``n`` is outside the frozen subset, so more than one is unreachable."""
    body = (await post(mock_api, request_body())).json()
    assert len(body["choices"]) == 1
    choice = body["choices"][0]
    assert choice["index"] == 0
    assert choice["message"] == {
        "role": "assistant",
        "content": MOCK_FIXTURE_CONTENT,
    }
    assert choice["finish_reason"] == MOCK_FIXTURE_FINISH_REASON


async def test_usage_is_null_because_the_mock_counts_no_tokens(
    mock_api: InferOpsApi,
) -> None:
    """`null`, never zero-filled and never estimated.

    The mock declares token counting unsupported precisely so that it does not
    report numbers its author chose. The API publishes the absence rather than
    filling it, which is the rule the accepted record states for ``usage``.
    """
    body = (await post(mock_api, request_body())).json()
    assert body["usage"] is None


async def test_usage_carries_the_counts_an_adapter_supplied(
    recording_api: InferOpsApi,
) -> None:
    body = (await post(recording_api, request_body())).json()
    usage = body["usage"]
    assert usage is not None
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]


async def test_the_extension_member_carries_what_the_record_lists(
    mock_api: InferOpsApi,
) -> None:
    body = (await post(mock_api, request_body())).json()
    extension = body[EXTENSION_MEMBER]
    assert set(extension) == {
        "requestId",
        "correlationId",
        "contractVersion",
        "adapterKind",
        "modelRef",
    }
    assert extension["contractVersion"] == CONTRACT_VERSION
    assert extension["adapterKind"] == MOCK_ADAPTER_KIND
    assert extension["modelRef"] == MOCK_MODEL


async def test_no_response_carries_a_field_the_platform_does_not_forward(
    mock_api: InferOpsApi,
) -> None:
    """The three runtime members the accepted record drops stay dropped."""
    raw = (await post(mock_api, request_body())).text()
    for field in NOT_PASSED_THROUGH:
        assert field not in raw, field


async def test_no_response_repeats_the_prompt(recording_api: InferOpsApi) -> None:
    """The prompt reaches the adapter and nothing else.

    The controlled double echoes a truncated prompt into its content on purpose,
    so this asserts the one thing that is checkable here: the API adds no copy of
    the prompt of its own, outside the content the adapter produced.
    """
    secret = "correlation-canary-9f2a"
    body = request_body(messages=[{"role": "user", "content": secret}])
    payload = (await post(recording_api, body)).json()
    del payload["choices"]
    assert secret not in json.dumps(payload)


# --------------------------------------------------------------------------
# Identifiers reach the adapter, and come back out
# --------------------------------------------------------------------------


async def test_supplied_identifiers_propagate_to_the_adapter(
    recording_adapter: RecordingAdapter, recording_api: InferOpsApi
) -> None:
    await post(
        recording_api,
        request_body(),
        headers=[
            (REQUEST_ID_HEADER, "req-abc.1"),
            (CORRELATION_ID_HEADER, "corr-abc.1"),
        ],
    )
    context = recording_adapter.contexts[-1]
    assert context.request_id == "req-abc.1"
    assert context.correlation_id == "corr-abc.1"


async def test_identifiers_are_generated_when_none_were_supplied(
    recording_adapter: RecordingAdapter, recording_api: InferOpsApi
) -> None:
    await post(recording_api, request_body())
    context = recording_adapter.contexts[-1]
    assert context.request_id
    assert context.correlation_id
    assert context.request_id != context.correlation_id


async def test_a_malformed_identifier_is_replaced_rather_than_trusted(
    recording_adapter: RecordingAdapter, recording_api: InferOpsApi
) -> None:
    """A header a client controls does not become a header this API echoes.

    The injected value below carries a newline, which is a response-splitting
    attempt rather than an identifier, and the replacement is what stops it
    reaching a response header.
    """
    injected = "abc\r\nX-Injected: yes"
    response = await post(
        recording_api, request_body(), headers=[(REQUEST_ID_HEADER, injected)]
    )
    assert recording_adapter.contexts[-1].request_id != injected
    assert response.header(REQUEST_ID_HEADER) != injected


async def test_the_response_headers_and_body_carry_the_same_identifiers(
    mock_api: InferOpsApi,
) -> None:
    response = await post(
        mock_api,
        request_body(),
        headers=[
            (REQUEST_ID_HEADER, "req-1"),
            (CORRELATION_ID_HEADER, "corr-1"),
        ],
    )
    extension = response.json()[EXTENSION_MEMBER]
    assert response.header(REQUEST_ID_HEADER) == "req-1"
    assert response.header(CORRELATION_ID_HEADER) == "corr-1"
    assert extension["requestId"] == "req-1"
    assert extension["correlationId"] == "corr-1"


# --------------------------------------------------------------------------
# What the adapter reports, the API reports
# --------------------------------------------------------------------------


async def test_a_canonical_error_from_the_adapter_is_answered_with_its_code(
    recording_adapter: RecordingAdapter, recording_api: InferOpsApi
) -> None:
    recording_adapter.failure = ModelNotReadyError("the model is still loading")
    response = await post(recording_api, request_body())
    assert response.status == 503
    assert response.json()["code"] == "model-not-ready"


async def test_a_result_declaring_the_wrong_adapter_kind_is_refused(
    recording_adapter: RecordingAdapter, recording_api: InferOpsApi
) -> None:
    """The one check that makes ``adapterKind`` worth publishing.

    A deployment composed as `mock` whose adapter returns a `real`-labelled
    result is a response nobody can use to claim anything, so it is refused
    rather than served with a label the reader cannot rely on.
    """
    recording_adapter.declared_kind = "real"
    response = await post(recording_api, request_body())
    assert response.status == 500
    assert response.json()["message"] == ADAPTER_KIND_DISAGREEMENT


async def test_an_unexpected_adapter_failure_carries_no_adapter_text(
    recording_adapter: RecordingAdapter, recording_api: InferOpsApi
) -> None:
    """An exception's own words are where a path or a host name reaches a caller."""

    async def explode(prompt: str, context: object) -> None:
        raise RuntimeError("/var/lib/models/secret-path.gguf")

    recording_adapter.infer = explode  # type: ignore[assignment,method-assign]
    response = await post(recording_api, request_body())
    assert response.status == 500
    body = response.json()
    assert body["code"] == "internal-error"
    assert "secret-path" not in response.text()
    assert body["requestId"]


async def test_the_mock_adapter_names_itself_in_every_completion(
    mock_adapter: MockServingAdapter, mock_api: InferOpsApi
) -> None:
    """The boundary rule at the place a reader looks: the response itself."""
    body = (await post(mock_api, request_body())).json()
    assert body[EXTENSION_MEMBER]["adapterKind"] == MOCK_ADAPTER_KIND
    assert mock_adapter.mock_identity()["isMock"] is True


async def test_a_body_split_across_messages_is_read_whole(
    mock_api: InferOpsApi,
) -> None:
    """A server delivers a body in as many messages as it likes."""
    body = request_body()
    half = len(body) // 2
    response = await asgi_client.request(
        mock_api,
        "POST",
        CHAT_COMPLETIONS_PATH,
        body_chunks=[body[:half], body[half:]],
    )
    assert response.status == 200, response.text()


async def test_the_same_request_twice_produces_the_same_completion_content(
    mock_api: InferOpsApi,
) -> None:
    """Determinism is what makes this layer assertable at all."""
    first = (await post(mock_api, request_body())).json()
    second = (await post(mock_api, request_body())).json()
    assert first["choices"] == second["choices"]
    assert first["created"] == second["created"]
    assert first["id"] != second["id"]


async def test_composing_the_api_performs_no_work_until_startup() -> None:
    """Construction is not initialization, so a composition point cannot fail late."""
    adapter = RecordingAdapter()
    build(adapter)
    assert adapter.initialized is False
