"""The canonical error contract this API serves, exercised at every refusal site.

`V1-S1-005-PR1` served four of the seven members of the canonical error body and
recorded the rest as this change's. This suite is what holds the finished contract
to the accepted record and to its own rules:

- every refusal carries the whole body, and ``retryAfterMs`` appears only where a
  delay was decided rather than invented;
- ``retryable`` follows the **condition** rather than the code, which is the one
  property a code-keyed table would get wrong for ``capability-unavailable``;
- a canonical error raised below this edge is answered with this API's own
  message, so an adapter's words — the component closest to a runtime's error
  text, a prompt, an endpoint, and a file path — cannot reach a caller by being
  forwarded;
- every refusal names the adapter kind behind the deployment, because the
  accepted record's rule is that every response does and a refusal is a response.

What a passing result establishes: what this API decides. It establishes nothing
about a model, a runtime, or a network — the adapters behind it are the committed
mock and controlled doubles, and no byte crossed a socket. The evidence class is
`mock` and it ceilings at `C1`.
"""

from __future__ import annotations

import json

import pytest

from inferops.api import (
    ADAPTER_KIND_DISAGREEMENT,
    CONDITIONS,
    DRAINING_MESSAGE,
    UNEXPECTED_FAILURE_MESSAGE,
    Condition,
    InferOpsApi,
)
from inferops.api import errors as api_errors
from inferops.api.surface import (
    CHAT_COMPLETIONS_PATH,
    ERROR_BODY_FIELDS,
    LIVE_PATH,
    MODELS_PATH,
)
from inferops.domain.context import RequestContext
from inferops.domain.serving import (
    CanonicalError,
    CapabilityUnavailableError,
    InferenceResult,
    InternalError,
    ModelNotReadyError,
    RateLimitedError,
    RequestTimeoutError,
    UpstreamTimeoutError,
)
from tests.support import asgi_client
from tests.support.api_composition import MOCK_MODEL, RecordingAdapter, build

pytestmark = pytest.mark.mockintegration

#: A message an adapter might raise that must not reach a caller. It stands in
#: for the things an adapter is genuinely close to — a runtime's own error text,
#: a mounted weight-file path, an endpoint, a prompt fragment.
ADAPTER_LEAK = "/models/secret-weights.gguf said: prompt=SECRET at 10.1.2.3:8080"


def valid_body() -> bytes:
    return json.dumps(
        {"model": MOCK_MODEL, "messages": [{"role": "user", "content": "hello"}]}
    ).encode("utf-8")


async def post(api: InferOpsApi, body: bytes) -> asgi_client.Response:
    return await asgi_client.request(api, "POST", CHAT_COMPLETIONS_PATH, body=body)


async def failing_api(error: CanonicalError) -> InferOpsApi:
    """An application whose adapter raises ``error`` from ``infer``."""
    api = build(RecordingAdapter(failure=error))
    await api.startup()
    return api


# --------------------------------------------------------------------------
# The body
# --------------------------------------------------------------------------


async def test_every_refusal_carries_the_whole_canonical_body(
    mock_api: InferOpsApi,
) -> None:
    """The four members PR1 served, plus ``retryable`` and ``details``."""
    response = await post(mock_api, b'{"model": 1}')
    body = response.json()

    optional = {"retryAfterMs"}
    assert set(body) == set(ERROR_BODY_FIELDS) - optional
    assert body["code"]
    assert body["message"]
    assert body["requestId"]
    assert body["correlationId"]
    assert isinstance(body["retryable"], bool)
    assert isinstance(body["details"], dict)


async def test_details_carries_the_condition_the_refusal_was_decided_by(
    mock_api: InferOpsApi,
) -> None:
    """A caller holding a ``conditionId`` can find the row that decided the code."""
    response = await post(mock_api, b'{"model": "' + MOCK_MODEL.encode() + b'"}')
    details = response.json()["details"]

    assert details["conditionId"] in {row.condition_id for row in CONDITIONS}
    assert details["conditionId"] == api_errors.REQUEST_OUTSIDE_SUBSET.condition_id


async def test_every_refusal_names_the_adapter_kind_behind_the_deployment(
    mock_api: InferOpsApi,
) -> None:
    """A refusal is a response, and every response names the kind that served it.

    Without this, a refusal would be the one response where the mock and real
    boundary is invisible at the place a reader actually looks.
    """
    response = await post(mock_api, b"not json")

    assert response.json()["details"]["adapterKind"] == "mock"


async def test_a_refusal_about_a_member_names_it_in_details(
    mock_api: InferOpsApi,
) -> None:
    """The member name, and never the value beside it — the accepted policy."""
    body = json.dumps(
        {
            "model": MOCK_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
            "top_p": "SECRET",
        }
    ).encode("utf-8")

    response = await post(mock_api, body)
    payload = response.json()

    assert payload["details"]["member"] == "top_p"
    assert "SECRET" not in response.text()


async def test_a_refusal_with_no_member_carries_no_member() -> None:
    """``details.member`` is absent rather than empty when nothing named one.

    A failure raised below this edge is about the backend rather than about
    something in the request, so there is no member to name and none is invented.
    """
    api = await failing_api(ModelNotReadyError())
    response = await post(api, valid_body())

    assert "member" not in response.json()["details"]


# --------------------------------------------------------------------------
# `retryable`, which follows the condition
# --------------------------------------------------------------------------


async def test_a_validation_refusal_is_not_retryable(mock_api: InferOpsApi) -> None:
    """Resending the same body produces the same refusal."""
    response = await post(mock_api, b'{"model": 1}')

    assert response.json()["retryable"] is False


async def test_a_streaming_request_is_refused_as_not_retryable(
    mock_api: InferOpsApi,
) -> None:
    """The one override the accepted record itself argues.

    ``capability-unavailable`` defaults to retryable, which is right for a
    capability that is temporarily gone and wrong for one that was never built.
    """
    body = json.dumps(
        {
            "model": MOCK_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        }
    ).encode("utf-8")

    response = await post(mock_api, body)
    payload = response.json()

    assert payload["code"] == "capability-unavailable"
    assert payload["retryable"] is False
    assert response.status == 400


async def test_an_unreachable_backend_is_the_same_code_and_is_retryable() -> None:
    """The same code as the row above, and the opposite flag and status.

    This pair is why a condition rather than a code is the unit: a table keyed by
    the code alone would have to answer one of these two wrongly.
    """
    api = await failing_api(CapabilityUnavailableError())
    response = await post(api, valid_body())
    payload = response.json()

    assert payload["code"] == "capability-unavailable"
    assert payload["retryable"] is True
    assert response.status == 503


# --------------------------------------------------------------------------
# `retryAfterMs`, which is served where a delay was decided
# --------------------------------------------------------------------------


async def test_no_refusal_invents_a_retry_delay(mock_api: InferOpsApi) -> None:
    """Nothing but a drain has a decided one, so nothing but a drain publishes one."""
    response = await post(mock_api, b'{"model": 1}')

    assert "retryAfterMs" not in response.json()


async def test_a_draining_deployment_publishes_the_budget_it_actually_has() -> None:
    """The one number here that was configured rather than guessed."""
    api = build(RecordingAdapter(), drain_timeout_ms=4_321)
    await api.startup()
    api.lifecycle.begin_shutdown()

    response = await post(api, valid_body())
    payload = response.json()

    assert response.status == 503
    assert payload["message"] == DRAINING_MESSAGE
    assert payload["retryable"] is True
    assert payload["retryAfterMs"] == 4_321


# --------------------------------------------------------------------------
# The mapping from an adapter's canonical error
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "code", "status", "retryable"),
    [
        (ModelNotReadyError(), "model-not-ready", 503, True),
        (CapabilityUnavailableError(), "capability-unavailable", 503, True),
        (UpstreamTimeoutError(), "upstream-timeout", 504, True),
        (RequestTimeoutError(), "request-timeout", 504, True),
        (RateLimitedError(), "rate-limited", 429, True),
        (InternalError(), "internal-error", 500, True),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
async def test_each_canonical_code_an_adapter_may_raise_is_mapped(
    error: CanonicalError, code: str, status: int, retryable: bool
) -> None:
    """The six codes the serving contract publishes, each answered as itself.

    ``rate-limited`` is mapped and **never originated**: InferOps enforces no
    rate limit, and the accepted record's reason for listing the code as not
    emitted stays true. What the mapping buys is that a backend reporting its own
    limit is not reported as an internal error.
    """
    api = await failing_api(error)
    response = await post(api, valid_body())
    payload = response.json()

    assert response.status == status
    assert payload["code"] == code
    assert payload["retryable"] is retryable


async def test_an_unknown_canonical_code_falls_back_without_inventing_a_meaning() -> (
    None
):
    """A code with no row is a defect in the mapping, answered as a 500."""
    api = await failing_api(CanonicalError("something-nobody-decided", "x"))
    response = await post(api, valid_body())

    assert response.status == 500
    assert response.json()["code"] == "internal-error"


# --------------------------------------------------------------------------
# What an adapter's own words may not do
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        ModelNotReadyError(ADAPTER_LEAK),
        UpstreamTimeoutError(ADAPTER_LEAK),
        InternalError(ADAPTER_LEAK),
        CanonicalError("something-nobody-decided", ADAPTER_LEAK),
    ],
    ids=["model-not-ready", "upstream-timeout", "internal-error", "unmapped"],
)
async def test_an_adapters_message_never_reaches_a_caller(
    error: CanonicalError,
) -> None:
    """The hardening this change adds over `V1-S1-005-PR1`.

    PR1 forwarded an adapter's canonical message, which was safe because every
    canonical message in this repository happens to be a constant — safe by
    review rather than by construction. An adapter is the component closest to a
    runtime's own error text, a mounted path, an endpoint, and a prompt, and the
    redaction rules name a provider error body as the surface most likely to be
    logged and kept. So the message is this API's, per condition.
    """
    api = await failing_api(error)
    response = await post(api, valid_body())

    assert "SECRET" not in response.text()
    assert ".gguf" not in response.text()
    assert "10.1.2.3" not in response.text()
    assert response.json()["message"] in {row.message for row in CONDITIONS}


async def test_an_uncaught_exception_reports_nothing_of_its_own() -> None:
    """A non-canonical failure is the likeliest carrier of a path or a host name."""

    class Exploding(RecordingAdapter):
        async def infer(self, prompt: str, context: RequestContext) -> InferenceResult:
            raise RuntimeError(ADAPTER_LEAK)

    api = build(Exploding())
    await api.startup()

    response = await post(api, valid_body())

    assert response.status == 500
    assert response.json()["message"] == UNEXPECTED_FAILURE_MESSAGE
    assert "SECRET" not in response.text()


async def test_a_mislabelled_result_is_refused_and_is_not_retryable() -> None:
    """A misconfiguration does not resolve itself between one request and the next."""
    api = build(RecordingAdapter(declared_kind="real"), adapter_kind="mock")
    await api.startup()

    response = await post(api, valid_body())
    payload = response.json()

    assert response.status == 500
    assert payload["code"] == "internal-error"
    assert payload["message"] == ADAPTER_KIND_DISAGREEMENT
    assert payload["retryable"] is False


# --------------------------------------------------------------------------
# Routing, which the accepted record does not map and this API does
# --------------------------------------------------------------------------


async def test_a_path_this_deployment_does_not_serve_is_a_contract_refusal(
    mock_api: InferOpsApi,
) -> None:
    response = await asgi_client.request(mock_api, "GET", "/healthz")
    payload = response.json()

    assert response.status == 404
    assert payload["code"] == "contract-invalid"
    assert payload["retryable"] is False
    assert payload["details"]["conditionId"] == "path-not-served"


async def test_a_method_this_path_does_not_serve_names_what_it_does(
    mock_api: InferOpsApi,
) -> None:
    response = await asgi_client.request(mock_api, "POST", LIVE_PATH)

    assert response.status == 405
    assert response.header("allow") == "GET"
    assert response.json()["details"]["conditionId"] == "method-not-served"


@pytest.mark.parametrize("path", ["/v2/chat/completions", "/v0/models", "/v11/models"])
async def test_a_path_naming_another_api_version_is_version_unsupported(
    mock_api: InferOpsApi, path: str
) -> None:
    """The one place a caller can name a version, so the one place the code is
    reachable: this surface reads no version header and the accepted record
    defines no request-body extension member a caller could put one in."""
    response = await asgi_client.request(mock_api, "POST", path)
    payload = response.json()

    assert response.status == 400
    assert payload["code"] == "version-unsupported"
    assert payload["retryable"] is False


async def test_the_served_version_prefix_is_not_read_as_another_version(
    mock_api: InferOpsApi,
) -> None:
    """`/v1/models` is served rather than refused, which is the boundary case."""
    response = await asgi_client.request(mock_api, "GET", MODELS_PATH)

    assert response.status == 200


async def test_a_path_that_merely_looks_versioned_is_not_a_version_refusal(
    mock_api: InferOpsApi,
) -> None:
    """`/version` is a path nobody publishes, not a version nobody serves."""
    response = await asgi_client.request(mock_api, "GET", "/version")

    assert response.status == 404
    assert response.json()["code"] == "contract-invalid"


async def test_a_body_above_the_bound_is_refused_before_it_is_read(
    mock_api: InferOpsApi,
) -> None:
    oversized = b"x" * (1_048_576 + 1)
    response = await asgi_client.request(
        mock_api, "POST", CHAT_COMPLETIONS_PATH, body=oversized
    )
    payload = response.json()

    assert response.status == 413
    assert payload["details"]["conditionId"] == "request-too-large"
    assert payload["retryable"] is False


# --------------------------------------------------------------------------
# The table itself
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "condition", CONDITIONS, ids=[row.condition_id for row in CONDITIONS]
)
def test_every_condition_is_complete(condition: Condition) -> None:
    """A row with no basis is a row nobody argued."""
    assert condition.condition_id
    assert condition.code
    assert condition.message
    assert condition.basis


def test_condition_identifiers_are_unique() -> None:
    identifiers = [row.condition_id for row in CONDITIONS]
    assert len(set(identifiers)) == len(identifiers)


def test_no_condition_message_repeats_an_adapter_or_runtime_word() -> None:
    """Every message is this API's own vocabulary about its own surface."""
    for condition in CONDITIONS:
        assert "llama" not in condition.message.lower(), condition.condition_id
        assert "gguf" not in condition.message.lower(), condition.condition_id
        assert "http://" not in condition.message, condition.condition_id
