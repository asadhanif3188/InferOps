"""The API end to end against the committed mock adapter: success and every failure.

The suites beside this one exercise one concern each — routing, validation, the
error contract, the lifecycle. This one goes the other way: it drives the whole
path a caller takes, from a configuration to a response, for a success and for
each failure the mock adapter can be made to produce. It is the mock half of what
`V1-S1-005-PR2` owes; the real half is
[`tests/realruntime/test_api_real_adapter_smoke.py`](../realruntime/test_api_real_adapter_smoke.py),
which is deselected by default and needs a runtime.

**The failure scenarios come from the mock's own vocabulary.**
:class:`~inferops.adapters.MockScenario`'s failing members *are* the canonical
codes they produce, so a scenario and the code a caller sees cannot drift apart.
The parametrisation below reads that enumeration rather than repeating it, which
is why a code added to the domain and to the mock will fail here until this API
maps it.

**What a passing result establishes and what it does not.** It establishes that
this API composes an adapter from configuration, routes, validates, translates,
calls, and answers — including the error contract. It establishes **nothing about
a model, a runtime, or a network**: the adapter replays a committed fixture, and
the application is driven through the ASGI interface it implements rather than
over a socket. The evidence class is `mock` and it ceilings at `C1`.
"""

from __future__ import annotations

import json

import pytest

from inferops.adapters import (
    MOCK_FIXTURE_CONTENT,
    MOCK_FIXTURE_FINISH_REASON,
    MOCK_MODEL_IDENTIFIER,
    MockAdapterSettings,
    MockScenario,
    MockServingAdapter,
)
from inferops.api import (
    ADAPTER_MOCK,
    CONDITIONS,
    CONTRACT_VERSION,
    CORRELATION_ID_HEADER,
    ENV_ADAPTER,
    ENV_MODEL_IDENTIFIER,
    ENV_REQUEST_TIMEOUT_MS,
    EXTENSION_MEMBER,
    REQUEST_ID_HEADER,
    ApiConfiguration,
    InferOpsApi,
    build,
)
from inferops.api.surface import (
    CHAT_COMPLETIONS_PATH,
    LIVE_PATH,
    METRICS_PATH,
    MODELS_PATH,
    READY_PATH,
)
from inferops.domain.context import RequestContext
from inferops.domain.serving import AdapterConfiguration, InferenceResult
from tests.support import asgi_client

pytestmark = pytest.mark.mockintegration

#: The environment a mock deployment is configured with. It is the same shape an
#: operator would set, which is the point of driving the composition from it.
MOCK_ENVIRONMENT = {
    ENV_ADAPTER: ADAPTER_MOCK,
    ENV_MODEL_IDENTIFIER: MOCK_MODEL_IDENTIFIER,
    ENV_REQUEST_TIMEOUT_MS: "5000",
}

#: The identifiers a caller supplies, so that propagation is observable end to end
#: rather than inferred from a generated value.
SUPPLIED_REQUEST_ID = "v1-s1-005-pr2-request"
SUPPLIED_CORRELATION_ID = "v1-s1-005-pr2-correlation"

#: Every failing scenario the mock publishes, which are the canonical codes it
#: raises. Read from the enumeration rather than listed here.
FAILURE_SCENARIOS = [row for row in MockScenario if row is not MockScenario.SUCCESS]


def completion_request() -> bytes:
    return json.dumps(
        {
            "model": MOCK_MODEL_IDENTIFIER,
            "messages": [
                {"role": "user", "content": "In one sentence, what is a pod?"}
            ],
        }
    ).encode("utf-8")


async def started(scenario: MockScenario = MockScenario.SUCCESS) -> InferOpsApi:
    """One deployment, composed from configuration and started.

    A failing scenario cannot be configured through the environment — failure
    injection is a test input rather than deployment configuration — so a
    scenario is applied by composing the application directly with the settings.
    """
    if scenario is MockScenario.SUCCESS:
        api = build(MOCK_ENVIRONMENT)
    else:
        api = InferOpsApi(
            adapter=MockServingAdapter(MockAdapterSettings(scenario=scenario)),
            adapter_configuration=AdapterConfiguration(
                model_identifier=MOCK_MODEL_IDENTIFIER, timeout_ms=5_000
            ),
            configuration=ApiConfiguration(adapter_kind="mock"),
        )
    await api.startup()
    return api


async def complete(api: InferOpsApi) -> asgi_client.Response:
    return await asgi_client.request(
        api,
        "POST",
        CHAT_COMPLETIONS_PATH,
        body=completion_request(),
        headers=[
            (REQUEST_ID_HEADER, SUPPLIED_REQUEST_ID),
            (CORRELATION_ID_HEADER, SUPPLIED_CORRELATION_ID),
        ],
    )


# --------------------------------------------------------------------------
# The success path
# --------------------------------------------------------------------------


async def test_a_deployment_configured_as_mock_answers_a_completion() -> None:
    """Configuration to completion, through every layer this change touches."""
    api = await started()

    response = await complete(api)
    body = response.json()

    assert response.status == 200
    assert body["choices"][0]["message"]["content"] == MOCK_FIXTURE_CONTENT
    assert body["choices"][0]["finish_reason"] == MOCK_FIXTURE_FINISH_REASON
    assert body["model"] == MOCK_MODEL_IDENTIFIER


async def test_the_completion_declares_the_kind_that_produced_it() -> None:
    """The label a reader looks at to decide what a response may be used to claim."""
    api = await started()

    body = (await complete(api)).json()

    assert body[EXTENSION_MEMBER]["adapterKind"] == "mock"
    assert body[EXTENSION_MEMBER]["contractVersion"] == CONTRACT_VERSION


async def test_the_completion_carries_no_token_counts_it_did_not_measure() -> None:
    """The mock declares token counting unsupported, so ``usage`` is ``null``.

    A number here would be one its author chose wearing a measurement's clothes,
    which is the row the boundary document names for exactly this case.
    """
    api = await started()

    assert (await complete(api)).json()["usage"] is None


@pytest.mark.parametrize(
    "path", [LIVE_PATH, READY_PATH, MODELS_PATH, METRICS_PATH], ids=lambda p: p
)
async def test_every_other_endpoint_answers_on_the_same_deployment(path: str) -> None:
    """One composition, five endpoints, which is what a deployment actually is."""
    api = await started()

    response = await asgi_client.request(api, "GET", path)

    assert response.status == 200


# --------------------------------------------------------------------------
# Correlation, end to end
# --------------------------------------------------------------------------


async def test_the_identifiers_a_caller_supplied_come_back_on_a_success() -> None:
    api = await started()

    response = await complete(api)
    body = response.json()

    assert response.header(REQUEST_ID_HEADER) == SUPPLIED_REQUEST_ID
    assert response.header(CORRELATION_ID_HEADER) == SUPPLIED_CORRELATION_ID
    assert body[EXTENSION_MEMBER]["requestId"] == SUPPLIED_REQUEST_ID
    assert body[EXTENSION_MEMBER]["correlationId"] == SUPPLIED_CORRELATION_ID


@pytest.mark.parametrize("scenario", FAILURE_SCENARIOS, ids=lambda row: row.value)
async def test_the_identifiers_come_back_on_every_failure(
    scenario: MockScenario,
) -> None:
    """A refusal nobody can correlate is worth less than the log line it replaced.

    This is the half of correlation that is easy to get wrong: a success path is
    written first and the failure path is written by whoever gets there next.
    """
    api = await started(scenario)

    response = await complete(api)
    body = response.json()

    assert response.header(REQUEST_ID_HEADER) == SUPPLIED_REQUEST_ID
    assert response.header(CORRELATION_ID_HEADER) == SUPPLIED_CORRELATION_ID
    assert body["requestId"] == SUPPLIED_REQUEST_ID
    assert body["correlationId"] == SUPPLIED_CORRELATION_ID


class ObservingMock(MockServingAdapter):
    """The committed mock, with the contexts it was handed kept for reading.

    It subclasses rather than replaces so that what is exercised is the adapter a
    mock deployment actually composes, and the only thing added is a list.
    """

    def __init__(self) -> None:
        super().__init__()
        self.contexts: list[RequestContext] = []

    async def infer(self, prompt: str, context: RequestContext) -> InferenceResult:
        self.contexts.append(context)
        return await super().infer(prompt, context)


async def test_the_identifiers_reach_the_adapter_that_serves_the_request() -> None:
    """Propagation to the component that would carry them into a runtime call."""
    adapter = ObservingMock()
    api = InferOpsApi(
        adapter=adapter,
        adapter_configuration=AdapterConfiguration(
            model_identifier=MOCK_MODEL_IDENTIFIER, timeout_ms=5_000
        ),
        configuration=ApiConfiguration(adapter_kind="mock"),
    )
    await api.startup()

    await complete(api)

    assert [row.request_id for row in adapter.contexts] == [SUPPLIED_REQUEST_ID]
    assert [row.correlation_id for row in adapter.contexts] == [SUPPLIED_CORRELATION_ID]


# --------------------------------------------------------------------------
# Every failure the mock can produce
# --------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", FAILURE_SCENARIOS, ids=lambda row: row.value)
async def test_each_injected_failure_is_answered_as_its_canonical_code(
    scenario: MockScenario,
) -> None:
    """The scenario's value **is** the code, so this cannot drift apart.

    A canonical code the domain gains and the mock can raise will fail here until
    this API has a condition for it, which is the property worth having.
    """
    api = await started(scenario)

    body = (await complete(api)).json()

    assert body["code"] == scenario.value


@pytest.mark.parametrize("scenario", FAILURE_SCENARIOS, ids=lambda row: row.value)
async def test_each_injected_failure_carries_the_whole_error_contract(
    scenario: MockScenario,
) -> None:
    api = await started(scenario)

    response = await complete(api)
    body = response.json()

    assert response.status >= 400
    assert isinstance(body["retryable"], bool)
    assert body["details"]["adapterKind"] == "mock"
    assert body["details"]["conditionId"] in {row.condition_id for row in CONDITIONS}
    assert body["message"] in {row.message for row in CONDITIONS}


@pytest.mark.parametrize("scenario", FAILURE_SCENARIOS, ids=lambda row: row.value)
async def test_no_failure_response_carries_the_prompt_that_produced_it(
    scenario: MockScenario,
) -> None:
    """The redaction rules name a provider error body as the surface most likely
    to be logged and kept, and a prompt is what must not be in one."""
    api = await started(scenario)

    response = await complete(api)

    assert "what is a pod" not in response.text().lower()


async def test_a_failing_deployment_still_answers_liveness() -> None:
    """Liveness answers nothing about the model, which is what makes it useful.

    A liveness probe aimed at a readiness answer restarts a pod mid-load and
    never converges — the failure the Sprint 0 trial actually surfaced.
    """
    api = await started(MockScenario.MODEL_NOT_READY)

    response = await asgi_client.request(api, "GET", LIVE_PATH)

    assert response.status == 200
    assert response.json()["status"] == "alive"


async def test_readiness_follows_the_selected_backend() -> None:
    """The mock reports itself ready once initialized, and this is that answer
    read through the API rather than from the adapter."""
    api = await started()

    response = await asgi_client.request(api, "GET", READY_PATH)

    assert response.status == 200
    assert response.json() == {
        "status": "ready",
        "adapterKind": "mock",
        "state": "serving",
    }
