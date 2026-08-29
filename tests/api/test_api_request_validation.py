"""What this API refuses, and what a refusal is allowed to say.

The accepted surface's unknown-member policy is **refuse**, and the argument for
it is that silently ignoring a parameter which changes the result hands a caller
a wrong answer they cannot detect. A policy nothing enforces is a paragraph, so
this suite is the enforcement: every member outside the frozen subset, every
malformed member inside it, and the streaming refusal.

The second half of the suite is the property that matters more than any single
refusal: **no refusal repeats a value read out of the request.** A refusal names
the member and states the constraint in this API's own vocabulary. That is what
`ADR 0010`'s security section requires and what the canonical error contract
forbids breaking.
"""

from __future__ import annotations

import json

import pytest

from inferops.api import CONTRACT_INVALID, InferOpsApi
from inferops.api.surface import CHAT_COMPLETIONS_PATH
from tests.support import asgi_client
from tests.support.api_composition import MOCK_MODEL, RecordingAdapter, build

pytestmark = pytest.mark.mockintegration


async def refuse(api: InferOpsApi, body: object) -> asgi_client.Response:
    payload = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    return await asgi_client.request(api, "POST", CHAT_COMPLETIONS_PATH, body=payload)


def valid(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "model": MOCK_MODEL,
        "messages": [{"role": "user", "content": "hello"}],
    }
    body.update(overrides)
    return body


# --------------------------------------------------------------------------
# The strict policy
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "member",
    ["top_p", "n", "presence_penalty", "stop", "frequency_penalty", "tools", "x_other"],
)
async def test_a_member_outside_the_frozen_subset_is_refused(
    mock_api: InferOpsApi, member: str
) -> None:
    """Including the upstream defaults a client library sends by habit.

    The cost of the strict policy is exactly this list, and the accepted record
    states it rather than hiding it. The suite asserts the cost is real.
    """
    response = await refuse(mock_api, valid(**{member: 1}))
    assert response.status == 400
    body = response.json()
    assert body["code"] == CONTRACT_INVALID
    assert body["message"].startswith(f"{member}:")


async def test_a_member_outside_the_subset_inside_a_message_is_refused(
    mock_api: InferOpsApi,
) -> None:
    response = await refuse(
        mock_api,
        valid(messages=[{"role": "user", "content": "hi", "name": "someone"}]),
    )
    assert response.status == 400
    assert response.json()["message"].startswith("messages.name:")


@pytest.mark.parametrize("member", ["model", "messages"])
async def test_a_required_member_that_is_absent_is_refused(
    mock_api: InferOpsApi, member: str
) -> None:
    body = valid()
    del body[member]
    response = await refuse(mock_api, body)
    assert response.status == 400
    assert response.json()["message"].startswith(f"{member}:")


# --------------------------------------------------------------------------
# The members inside the subset
# --------------------------------------------------------------------------


async def test_a_model_that_is_not_the_served_model_is_refused(
    mock_api: InferOpsApi,
) -> None:
    """Multi-model is declared false: the member is checked, never used to select."""
    response = await refuse(mock_api, valid(model="some-other-model"))
    assert response.status == 400
    body = response.json()
    assert body["code"] == CONTRACT_INVALID
    assert body["message"].startswith("model:")
    assert "some-other-model" not in response.text()


async def test_a_role_outside_the_accepted_set_is_refused(
    mock_api: InferOpsApi,
) -> None:
    response = await refuse(
        mock_api, valid(messages=[{"role": "tool", "content": "hi"}])
    )
    assert response.status == 400
    assert response.json()["message"].startswith("messages.role:")


async def test_the_array_of_parts_content_form_is_refused(
    mock_api: InferOpsApi,
) -> None:
    """It is outside the frozen subset, and a string is what the subset accepts."""
    response = await refuse(
        mock_api,
        valid(messages=[{"role": "user", "content": [{"type": "text"}]}]),
    )
    assert response.status == 400
    assert response.json()["message"].startswith("messages.content:")


async def test_a_conversation_is_refused_rather_than_flattened(
    mock_api: InferOpsApi,
) -> None:
    """The reduction this API makes, and it is a refusal rather than an invention.

    The frozen adapter interface carries one prompt. Flattening a conversation
    into it would apply a prompt format no chat template agreed to, silently, so
    the request is refused and the reason is published.
    """
    response = await refuse(
        mock_api,
        valid(
            messages=[
                {"role": "system", "content": "be brief"},
                {"role": "user", "content": "hello"},
            ]
        ),
    )
    assert response.status == 400
    body = response.json()
    assert body["code"] == CONTRACT_INVALID
    assert body["message"].startswith("messages:")
    assert "single prompt" in body["message"]


@pytest.mark.parametrize("value", [0, -1, "12", True, 1.5])
async def test_a_max_tokens_that_is_not_a_positive_integer_is_refused(
    mock_api: InferOpsApi, value: object
) -> None:
    response = await refuse(mock_api, valid(max_tokens=value))
    assert response.status == 400
    assert response.json()["message"].startswith("max_tokens:")


async def test_a_max_tokens_above_the_configured_ceiling_is_refused() -> None:
    """Refused, not silently clamped. The accepted record is explicit about it."""
    api = build(RecordingAdapter(), max_output_tokens=32)
    await api.startup()
    response = await refuse(api, valid(max_tokens=64))
    assert response.status == 400
    assert response.json()["message"].startswith("max_tokens:")


async def test_a_max_tokens_at_the_ceiling_is_accepted() -> None:
    api = build(RecordingAdapter(), max_output_tokens=32)
    await api.startup()
    response = await refuse(api, valid(max_tokens=32))
    assert response.status == 200, response.text()


async def test_no_ceiling_is_configured_by_default(mock_api: InferOpsApi) -> None:
    """`None` is the accurate default: no context length is decided anywhere."""
    response = await refuse(mock_api, valid(max_tokens=1_000_000))
    assert response.status == 200, response.text()


@pytest.mark.parametrize("value", ["hot", True, None, []])
async def test_a_temperature_that_is_not_a_number_is_refused(
    mock_api: InferOpsApi, value: object
) -> None:
    response = await refuse(mock_api, valid(temperature=value))
    assert response.status == 400
    assert response.json()["message"].startswith("temperature:")


async def test_streaming_is_refused_with_the_code_the_record_names(
    mock_api: InferOpsApi,
) -> None:
    response = await refuse(mock_api, valid(stream=True))
    assert response.status == 400
    body = response.json()
    assert body["code"] == "capability-unavailable"
    assert body["message"].startswith("stream:")


async def test_streaming_declared_false_is_accepted(mock_api: InferOpsApi) -> None:
    """The member is in the subset; only ``true`` is refused."""
    response = await refuse(mock_api, valid(stream=False))
    assert response.status == 200, response.text()


# --------------------------------------------------------------------------
# The body itself
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw", [b"", b"not json", b"[]", b'"a string"', b"123", b"\xff\xfe"]
)
async def test_a_body_that_is_not_a_json_object_is_refused(
    mock_api: InferOpsApi, raw: bytes
) -> None:
    response = await refuse(mock_api, raw)
    assert response.status == 400
    body = response.json()
    assert body["code"] == CONTRACT_INVALID
    assert body["message"].startswith("body:")


async def test_a_body_beyond_the_bound_is_refused_rather_than_allocated(
    mock_api: InferOpsApi,
) -> None:
    """The caller does not decide how much this process allocates."""
    oversized = b"{" + b"x" * 2_000_000
    response = await refuse(mock_api, oversized)
    assert response.status == 413
    assert response.json()["message"].startswith("body:")


# --------------------------------------------------------------------------
# What a refusal is allowed to say
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"model": "wrong-model", "messages": [{"role": "user", "content": "SECRET"}]},
        {"model": MOCK_MODEL, "messages": [{"role": "SECRET", "content": "x"}]},
        {
            "model": MOCK_MODEL,
            "messages": [{"role": "user", "content": "x"}],
            "temperature": "SECRET",
        },
    ],
)
async def test_no_refusal_repeats_a_value_read_out_of_the_request(
    mock_api: InferOpsApi, body: dict[str, object]
) -> None:
    """The single property that keeps a refusal safe to return to a caller."""
    response = await refuse(mock_api, body)
    assert response.status == 400
    assert "SECRET" not in response.text()


async def test_every_refusal_carries_the_identifiers_it_can_be_correlated_by(
    mock_api: InferOpsApi,
) -> None:
    """A refusal nobody can correlate is worth less than the log line it replaced."""
    response = await refuse(mock_api, {"model": MOCK_MODEL})
    body = response.json()
    assert body["requestId"]
    assert body["correlationId"]
    assert set(body) == {"code", "message", "requestId", "correlationId"}
