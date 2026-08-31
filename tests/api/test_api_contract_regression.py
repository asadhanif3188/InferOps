"""Every condition this API can refuse on, driven from the table that declares it.

``tests/api/test_api_error_contract.py`` exercises the refusal sites and argues
about each one: why ``retryable`` follows the condition rather than the code, why
an adapter's own words stop at the edge, why a draining deployment is the one
refusal that knows its own delay. Every one of those tests was written by hand,
and that is the gap this module closes: a condition added to
:data:`~inferops.api.errors.CONDITIONS` and never provoked passes every check in
this repository, because the check that would have caught it is the one nobody
remembered to write.

So the table is the input here. :data:`PROVOCATION` names, for every condition,
the request that reaches it, and a check asserts the mapping is exhaustive in
both directions before any of it runs. What each provocation is then held to is
the row's own declaration: the canonical code, the ``retryable`` flag, the HTTP
status, and the condition identifier a caller is given to look the row up by.

One condition is not reachable at this edge and says so rather than being
omitted; :data:`UNREACHABLE_AT_THIS_EDGE` carries the reason.

The success half is the same idea applied to :data:`~inferops.api.surface.ROUTES`:
every route this API serves, driven once, and held to the properties every
response carries — the identifiers, and the adapter kind behind the deployment.

**Three limits travel with every result here.** Nothing crosses a socket: this
repository ships no server, and the application is driven through the ASGI
interface it implements, so a passing run establishes what the application
decides and nothing about HTTP. The adapter behind it is the committed mock or a
controlled double. And the third is a property of driving a table rather than
retyping one: these checks establish that a refusal follows the row it names,
**not that the row is right**. Editing a row edits the expectation with it. The
nine rows copied from the accepted record are pinned against that record by
``tests/serving/test_inference_api_implementation_agreement.py``; the seven this
API added carry an argued ``basis`` and nothing pins them, which is the honest
state and is recorded here rather than papered over with a second copy of the
table.

The evidence class is `mock` and it ceilings at `C1`.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

import pytest

from inferops.adapters import MOCK_ADAPTER_KIND, MockServingAdapter
from inferops.api import (
    CONDITIONS,
    Condition,
    InferOpsApi,
)
from inferops.api import errors as api_errors
from inferops.api.surface import (
    CHAT_COMPLETIONS_PATH,
    CORRELATION_ID_HEADER,
    ERROR_BODY_FIELDS,
    EXTENSION_MEMBER,
    LIVE_PATH,
    REQUEST_ID_HEADER,
    ROUTES,
    Route,
)
from inferops.domain.context import RequestContext
from inferops.domain.serving import (
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
from tools.contract_validation import CANONICAL_ERROR_CODES

pytestmark = pytest.mark.mockintegration

#: A correlation identifier a caller supplies. Fixed, so that a body produced by
#: this suite is identical on every run except for the identifiers the API
#: generates for itself.
SUPPLIED_CORRELATION_ID = "11111111-1111-4111-8111-111111111111"

#: The member of the canonical error body that is present only where a delay was
#: decided rather than invented.
OPTIONAL_ERROR_MEMBER = "retryAfterMs"

#: Conditions no request to this API can produce, with the reason each is here.
#: Recorded rather than omitted, because a condition that is simply missing from
#: the provocation table is indistinguishable from one somebody forgot.
UNREACHABLE_AT_THIS_EDGE: dict[str, str] = {
    "runtime-unparseable-response": (
        "an adapter that answered 2xx with a body it could not read raises the "
        "same canonical error as one that answered with an error, so the two are "
        "indistinguishable at this edge and a request cannot select between "
        "them; the distinction is the adapter's and its suite owns it"
    ),
}


def valid_body() -> bytes:
    return json.dumps(
        {"model": MOCK_MODEL, "messages": [{"role": "user", "content": "hello"}]}
    ).encode("utf-8")


async def started(adapter: object, **kwargs: object) -> InferOpsApi:
    api = build(adapter, **kwargs)  # type: ignore[arg-type]
    await api.startup()
    return api


async def post_to_mock(body: bytes, path: str = CHAT_COMPLETIONS_PATH):
    api = await started(MockServingAdapter())
    return await asgi_client.request(api, "POST", path, body=body)


async def refused_by(error: Exception):
    """One completion against an adapter that raises ``error`` from ``infer``."""
    api = await started(RecordingAdapter(failure=error))  # type: ignore[arg-type]
    return await asgi_client.request(
        api, "POST", CHAT_COMPLETIONS_PATH, body=valid_body()
    )


async def provoke_model_loading():
    return await refused_by(ModelNotReadyError())


async def provoke_runtime_unreachable():
    return await refused_by(CapabilityUnavailableError())


async def provoke_runtime_timeout():
    return await refused_by(UpstreamTimeoutError())


async def provoke_caller_deadline():
    return await refused_by(RequestTimeoutError())


async def provoke_adapter_rate_limited():
    return await refused_by(RateLimitedError())


async def provoke_runtime_error_response():
    return await refused_by(InternalError())


async def provoke_request_outside_subset():
    return await post_to_mock(b'{"model": 1}')


async def provoke_streaming_requested():
    body = json.dumps(
        {
            "model": MOCK_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        }
    ).encode("utf-8")
    return await post_to_mock(body)


async def provoke_unsupported_contract_version():
    return await post_to_mock(valid_body(), path="/v2/chat/completions")


async def provoke_path_not_served():
    api = await started(MockServingAdapter())
    return await asgi_client.request(api, "GET", "/healthz")


async def provoke_method_not_served():
    api = await started(MockServingAdapter())
    return await asgi_client.request(api, "POST", LIVE_PATH)


async def provoke_request_too_large():
    return await post_to_mock(b"x" * (1_048_576 + 1))


async def provoke_deployment_draining():
    api = await started(MockServingAdapter(), drain_timeout_ms=4_321)
    api.lifecycle.begin_shutdown()
    return await asgi_client.request(
        api, "POST", CHAT_COMPLETIONS_PATH, body=valid_body()
    )


async def provoke_adapter_kind_disagreement():
    api = await started(RecordingAdapter(declared_kind="real"), adapter_kind="mock")
    return await asgi_client.request(
        api, "POST", CHAT_COMPLETIONS_PATH, body=valid_body()
    )


async def provoke_unexpected_failure():
    class Exploding(RecordingAdapter):
        async def infer(self, prompt: str, context: RequestContext) -> InferenceResult:
            raise RuntimeError("a failure that is not canonical")

    api = await started(Exploding())
    return await asgi_client.request(
        api, "POST", CHAT_COMPLETIONS_PATH, body=valid_body()
    )


#: The request that reaches each condition. Asserted exhaustive against the
#: table this API publishes, so a condition added without a provocation fails
#: here rather than shipping unexercised.
PROVOCATION: dict[str, Callable[[], Awaitable[asgi_client.Response]]] = {
    "model-loading": provoke_model_loading,
    "runtime-unreachable": provoke_runtime_unreachable,
    "runtime-timeout": provoke_runtime_timeout,
    "caller-deadline": provoke_caller_deadline,
    "request-outside-subset": provoke_request_outside_subset,
    "streaming-requested": provoke_streaming_requested,
    "unsupported-contract-version": provoke_unsupported_contract_version,
    "runtime-error-response": provoke_runtime_error_response,
    "path-not-served": provoke_path_not_served,
    "method-not-served": provoke_method_not_served,
    "request-too-large": provoke_request_too_large,
    "deployment-draining": provoke_deployment_draining,
    "adapter-kind-disagreement": provoke_adapter_kind_disagreement,
    "adapter-rate-limited": provoke_adapter_rate_limited,
    "unexpected-failure": provoke_unexpected_failure,
}

PROVOKED_CONDITIONS = [row for row in CONDITIONS if row.condition_id in PROVOCATION]


def condition_id(row: Condition) -> str:
    return row.condition_id


# --------------------------------------------------------------------------
# The table, before anything is driven from it
# --------------------------------------------------------------------------


def test_every_condition_is_provoked_or_recorded_as_unreachable() -> None:
    """The check that makes every check below complete rather than merely passing.

    Asserted in both directions. A condition added to the API without a request
    that reaches it lands in the first list; a provocation left behind for a
    condition that no longer exists lands in the second.
    """
    declared = {row.condition_id for row in CONDITIONS}
    accounted = set(PROVOCATION) | set(UNREACHABLE_AT_THIS_EDGE)
    assert declared == accounted, {
        "declared and never provoked": sorted(declared - accounted),
        "provoked and not declared": sorted(accounted - declared),
    }


def test_no_condition_is_both_provoked_and_recorded_unreachable() -> None:
    overlap = set(PROVOCATION) & set(UNREACHABLE_AT_THIS_EDGE)
    assert not overlap, sorted(overlap)


def test_an_unreachable_condition_is_still_owned_somewhere() -> None:
    """A condition nothing at this edge reaches is still a condition of a code.

    Recording it here is only acceptable while it remains part of the published
    table with a canonical code and a status, which is what a caller who ever
    does receive it will be given.
    """
    by_id = {row.condition_id: row for row in CONDITIONS}
    for condition_identifier, reason in UNREACHABLE_AT_THIS_EDGE.items():
        row = by_id[condition_identifier]
        assert row.code
        assert row.message
        assert reason


# --------------------------------------------------------------------------
# Every refusal, held to the row that declares it
# --------------------------------------------------------------------------


@pytest.mark.parametrize("row", PROVOKED_CONDITIONS, ids=condition_id)
async def test_every_refusal_matches_the_condition_that_declares_it(
    row: Condition,
) -> None:
    """Code, flag, status, and identifier, taken from the table rather than retyped.

    A hand-written expectation is a second copy of the contract, and a second
    copy drifts. These assertions read the row the API itself refused on, so the
    only way to pass is for the response to say what the table says.
    """
    response = await PROVOCATION[row.condition_id]()
    payload = response.json()

    assert response.status == int(row.status), payload
    assert payload["code"] == row.code, payload
    assert payload["retryable"] is row.retryable, payload
    assert payload["details"]["conditionId"] == row.condition_id, payload


@pytest.mark.parametrize("row", PROVOKED_CONDITIONS, ids=condition_id)
async def test_every_refusal_carries_the_whole_canonical_body(row: Condition) -> None:
    """Seven members, one of them optional, on every refusal this API can produce.

    The existing suite asserts this for one refusal. Driving it from the table
    is what turns "the body is right" into "the body is right at every refusal
    site", which is the property a caller writing one error handler depends on.
    """
    response = await PROVOCATION[row.condition_id]()
    payload = response.json()

    required = set(ERROR_BODY_FIELDS) - {OPTIONAL_ERROR_MEMBER}
    assert required <= set(payload), sorted(required - set(payload))
    assert set(payload) <= set(ERROR_BODY_FIELDS), sorted(
        set(payload) - set(ERROR_BODY_FIELDS)
    )
    assert payload["message"]
    assert payload["requestId"]
    assert payload["correlationId"]
    assert isinstance(payload["details"], dict)


@pytest.mark.parametrize("row", PROVOKED_CONDITIONS, ids=condition_id)
async def test_every_refusal_names_the_adapter_kind_behind_the_deployment(
    row: Condition,
) -> None:
    """A refusal is a response, and every response names the kind that served it.

    The deployments in this module are composed with ``mock``, including the one
    whose adapter contradicts it — which is the point of that row, and the
    refusal still reports the kind the deployment was composed with rather than
    the one the adapter claimed.
    """
    response = await PROVOCATION[row.condition_id]()
    assert response.json()["details"]["adapterKind"] == MOCK_ADAPTER_KIND


@pytest.mark.parametrize("row", PROVOKED_CONDITIONS, ids=condition_id)
async def test_a_retry_delay_is_served_only_where_one_was_decided(
    row: Condition,
) -> None:
    """``retryAfterMs`` arrives in the one field a client library reads on its own.

    A number invented for the other conditions would be a recommendation nobody
    made. Exactly one condition knows its own delay — a deployment that has begun
    draining knows its drain budget — and this asserts the other fourteen serve
    none.
    """
    response = await PROVOCATION[row.condition_id]()
    payload = response.json()

    if row is api_errors.DEPLOYMENT_DRAINING:
        assert payload[OPTIONAL_ERROR_MEMBER] == 4_321
    else:
        assert OPTIONAL_ERROR_MEMBER not in payload, payload


@pytest.mark.parametrize("row", PROVOKED_CONDITIONS, ids=condition_id)
async def test_no_refusal_repeats_the_deployments_own_internals(
    row: Condition,
) -> None:
    """A refusal names a condition and a member. It names nothing it read or ran.

    The strings checked for are the ones this suite's own doubles would leak if
    an exception's text, an adapter's message, or a module path reached a caller.
    """
    response = await PROVOCATION[row.condition_id]()
    text = response.text()

    for leaked in ("Traceback", "inferops.adapters", "RecordingAdapter", ".py"):
        assert leaked not in text, (row.condition_id, text)


# --------------------------------------------------------------------------
# Every route, and what every response carries
# --------------------------------------------------------------------------


def route_id(route: Route) -> str:
    return route.endpoint_id


async def call(route: Route) -> asgi_client.Response:
    api = await started(MockServingAdapter())
    body = valid_body() if route.method == "POST" else None
    return await asgi_client.request(
        api,
        route.method,
        route.path,
        body=body,
        headers=[(CORRELATION_ID_HEADER, SUPPLIED_CORRELATION_ID)],
    )


@pytest.mark.parametrize("route", ROUTES, ids=route_id)
async def test_every_route_this_api_publishes_is_served(route: Route) -> None:
    """The frozen endpoint table, driven rather than read.

    A route in the tuple that no handler serves would answer 404 with a
    ``path-not-served`` refusal — a published endpoint that is published and not
    served, which is the failure this catches.
    """
    response = await call(route)
    assert response.status == 200, response.text()


@pytest.mark.parametrize("route", ROUTES, ids=route_id)
async def test_every_route_returns_the_callers_correlation_identifier(
    route: Route,
) -> None:
    """Correlation propagation is a property of the API, not of one endpoint.

    A caller correlating a completion against a readiness probe needs the
    identifier on both, and the endpoint that omits it is the one a reader will
    not think to check.
    """
    response = await call(route)
    assert response.header(CORRELATION_ID_HEADER.lower()) == SUPPLIED_CORRELATION_ID


@pytest.mark.parametrize("route", ROUTES, ids=route_id)
async def test_every_route_issues_a_request_identifier(route: Route) -> None:
    """The identifier this API generates, on every response including a refusal."""
    response = await call(route)
    issued = response.header(REQUEST_ID_HEADER.lower())
    assert issued, route.endpoint_id
    assert issued != SUPPLIED_CORRELATION_ID


async def test_a_completion_from_the_mock_declares_the_mock_identity() -> None:
    """The label lives in the response, not in the deployment somebody remembers.

    Boundary rule 6: a label that lives in the directory a file sits in does not
    survive the file being copied out of it. The same is true of a transcript
    pasted into a record, so the completion names the mock-labelled model and the
    extension member names the adapter kind.
    """
    response = await call(ROUTES[0])
    payload = response.json()

    assert payload["model"] == MOCK_MODEL
    assert payload[EXTENSION_MEMBER]["adapterKind"] == MOCK_ADAPTER_KIND


async def test_the_readiness_response_names_the_adapter_kind() -> None:
    """The endpoint most likely to be scraped by something that reads nothing else."""
    response = await asgi_client.request(
        await started(MockServingAdapter()), "GET", "/health/ready"
    )
    assert response.json()["adapterKind"] == MOCK_ADAPTER_KIND


# --------------------------------------------------------------------------
# One canonical vocabulary, across the API and the offline contract check
# --------------------------------------------------------------------------


def test_every_code_the_contract_validator_emits_is_a_code_this_api_serves() -> None:
    """A document refused offline and a request refused here speak one vocabulary.

    The offline validator concludes ``contract-invalid`` or
    ``version-unsupported`` about a workload document; this API answers requests.
    They are different surfaces with different inputs, and the canonical code is
    the thing a consumer switches on across both — so a code one of them can
    produce and the other cannot name is a vocabulary that has split in two.
    """
    served = {row.code for row in CONDITIONS}
    assert set(CANONICAL_ERROR_CODES) <= served, sorted(
        set(CANONICAL_ERROR_CODES) - served
    )


def test_the_shared_codes_agree_about_whether_a_retry_could_help() -> None:
    """Both surfaces publish a retryable default, and they must not contradict.

    The validator's two codes are both non-retryable: resubmitting the same
    document produces the same refusal. Every condition this API carries on those
    codes must agree, or a client library retrying on the API's answer would be
    retrying something the contract surface already called permanent.
    """
    for code, retryable in CANONICAL_ERROR_CODES.items():
        for row in CONDITIONS:
            if row.code == code:
                assert row.retryable is retryable, (row.condition_id, code)
