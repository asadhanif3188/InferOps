"""API readiness answers for the API, and the dependency is reported beside it.

`ADR 0020` decides the rule this suite holds: the status of ``/health/ready`` is
this API's own answer, and the selected adapter's answer is a separate member of
the body. The suite drives the application through the ASGI interface in five
situations and reads two things in each: what readiness answered, and what a
caller of the inference endpoint received.

- a runtime that is ready;
- a runtime that cannot be reached;
- a runtime that answers and whose model is still loading;
- a runtime that does not answer inside the readiness budget;
- an API that is starting, draining, or stopped.

**What a result here establishes, and what it does not.** The adapter is the real
adapter type, composed from the committed local composition, over a controlled
transport. No runtime process, no model, no socket, no kubelet, and no cluster is
involved. The suite therefore establishes what this application decides: the
status, the body, the canonical error, and the counter. It does not establish that
a Kubernetes Service keeps an API endpoint while the runtime is unavailable, and
it does not establish what a caller receives through a Service. Those need an
observation of a deployed release.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.adapters.llama_cpp import RuntimeResponse, TransportUnreachable
from inferops.api import InferOpsApi, build
from inferops.api.application import (
    DEFAULT_ADAPTER_READINESS_TIMEOUT_MS,
    ApiConfiguration,
)
from inferops.api.lifecycle import LifecycleState
from inferops.api.responses import (
    ADAPTER_STATUS_NOT_ASKED,
    ADAPTER_STATUS_NOT_READY,
    ADAPTER_STATUS_READY,
    ADAPTER_STATUSES,
    ready_body,
)
from inferops.api.surface import (
    CHAT_COMPLETIONS_PATH,
    CORRELATION_ID_HEADER,
    LIVE_PATH,
    METRICS_PATH,
    MODELS_PATH,
    READY_PATH,
    REQUEST_ID_HEADER,
)
from inferops.domain.context import RequestContext
from inferops.domain.serving import AdapterConfiguration, InvalidValueError
from inferops.telemetry import names
from tests.support import asgi_client
from tests.support.api_composition import RecordingAdapter, fixed_clock
from tools.local_composition import core as composition

pytestmark = pytest.mark.mockintegration

REPO_ROOT = Path(__file__).resolve().parents[2]
CHART_VALUES = REPO_ROOT / "charts" / "inferops-llm" / "values.yaml"

SERVED_MODEL = "qwen3-1-7b-q8-0"

#: The three things the controlled runtime can be told to do.
RUNTIME_READY = "ready"
RUNTIME_LOADING = "loading"
RUNTIME_UNREACHABLE = "unreachable"


class ControlledRuntimeTransport:
    """A transport for the real adapter whose runtime a test can change.

    It answers the two runtime paths the adapter calls, in the shapes the
    runtime's own contract records: health is 200 when ready and 503 while the
    model loads, and an unreachable runtime raises the transport's own error.
    """

    def __init__(self, state: str = RUNTIME_READY) -> None:
        self.state = state
        self.health_asks = 0
        self.completions = 0

    async def get(self, url: str, *, timeout_s: float) -> RuntimeResponse:
        assert url.endswith("/health"), url
        self.health_asks += 1
        if self.state == RUNTIME_UNREACHABLE:
            raise TransportUnreachable("connection refused by 10.0.0.7:8080")
        if self.state == RUNTIME_LOADING:
            return RuntimeResponse(503, {"error": {"message": "Loading model"}})
        return RuntimeResponse(200, {"status": "ok"})

    async def post_json(
        self, url: str, payload: Mapping[str, object], *, timeout_s: float
    ) -> RuntimeResponse:
        assert url.endswith("/v1/chat/completions"), url
        self.completions += 1
        if self.state == RUNTIME_UNREACHABLE:
            raise TransportUnreachable("connection refused by 10.0.0.7:8080")
        if self.state == RUNTIME_LOADING:
            return RuntimeResponse(503, {"error": {"message": "Loading model"}})
        return RuntimeResponse(
            200,
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "index": 0,
                        "message": {"role": "assistant", "content": "controlled"},
                    }
                ],
                "model": "qwen3-1.7b-q8_0",
                "object": "chat.completion",
                "usage": {
                    "completion_tokens": 1,
                    "prompt_tokens": 2,
                    "total_tokens": 3,
                },
            },
        )

    async def close(self) -> None:
        return None


async def real_api(
    state: str,
) -> tuple[InferOpsApi, ControlledRuntimeTransport, list[dict[str, Any]]]:
    """The real adapter type behind a started API, over a controlled runtime."""
    transport = ControlledRuntimeTransport(state)
    records: list[dict[str, Any]] = []
    api = build(
        composition.composition_environment(composition.load_composition()),
        transport=transport,
        sink=lambda line: records.append(json.loads(line)),
    )
    await api.startup()
    return api, transport, records


async def ready(api: InferOpsApi) -> asgi_client.Response:
    return await asgi_client.request(api, "GET", READY_PATH)


async def complete(api: InferOpsApi) -> asgi_client.Response:
    body = json.dumps(
        {"model": SERVED_MODEL, "messages": [{"role": "user", "content": "hello"}]}
    ).encode("utf-8")
    return await asgi_client.request(
        api,
        "POST",
        CHAT_COMPLETIONS_PATH,
        body=body,
        headers=[("content-type", "application/json")],
    )


def readiness_failures(text: str, component: str) -> float:
    """The readiness counter's value for one component, or zero when absent."""
    prefix = f"{names.READINESS_CHECK_FAILURES}{{"
    for line in text.splitlines():
        if line.startswith(prefix) and f'inferops_component="{component}"' in line:
            return float(line.rsplit(" ", 1)[1])
    return 0.0


async def scrape(api: InferOpsApi) -> str:
    return (await asgi_client.request(api, "GET", METRICS_PATH)).text()


# --------------------------------------------------------------------------
# A runtime that is ready
# --------------------------------------------------------------------------


async def test_a_ready_runtime_gives_a_ready_api_and_a_ready_adapter() -> None:
    api, _, _ = await real_api(RUNTIME_READY)

    response = await ready(api)

    assert response.status == 200
    assert response.json() == {
        "status": "ready",
        "adapterKind": "real",
        "state": "serving",
        "adapterStatus": ADAPTER_STATUS_READY,
    }
    assert (await complete(api)).status == 200
    assert readiness_failures(await scrape(api), names.COMPONENT_ADAPTER) == 0


# --------------------------------------------------------------------------
# A runtime that cannot be reached, and one whose model is loading
# --------------------------------------------------------------------------


@pytest.mark.parametrize("state", [RUNTIME_UNREACHABLE, RUNTIME_LOADING])
async def test_an_unavailable_runtime_does_not_make_the_api_not_ready(
    state: str,
) -> None:
    """The decision itself: the dependency is reported, and the status is the API's."""
    api, _, _ = await real_api(state)

    response = await ready(api)

    assert response.status == 200
    assert response.json() == {
        "status": "ready",
        "adapterKind": "real",
        "state": "serving",
        "adapterStatus": ADAPTER_STATUS_NOT_READY,
    }


@pytest.mark.parametrize(
    ("state", "condition", "code"),
    [
        (RUNTIME_UNREACHABLE, "runtime-unreachable", "capability-unavailable"),
        (RUNTIME_LOADING, "model-loading", "model-not-ready"),
    ],
)
async def test_a_ready_api_answers_inference_with_the_canonical_dependency_error(
    state: str, condition: str, code: str
) -> None:
    """The error path the readiness status keeps reachable.

    A caller receives this body from this application whether or not readiness
    was asked first, so the test asks for a completion on its own.
    """
    api, _, _ = await real_api(state)

    response = await complete(api)

    assert response.status == 503
    body = response.json()
    assert body["code"] == code
    assert body["retryable"] is True
    assert body["details"]["conditionId"] == condition
    assert body["details"]["adapterKind"] == "real"
    assert body["requestId"] == response.header(REQUEST_ID_HEADER)
    assert body["correlationId"] == response.header(CORRELATION_ID_HEADER)
    assert (await ready(api)).status == 200


async def test_the_two_dependency_conditions_are_one_value_in_the_readiness_body() -> (
    None
):
    """Where the distinction is published and where it is not.

    The adapter interface answers readiness with a boolean. The readiness body
    therefore reports one value for both conditions, and the canonical error of
    the inference path is what tells them apart.
    """
    unreachable, _, _ = await real_api(RUNTIME_UNREACHABLE)
    loading, _, _ = await real_api(RUNTIME_LOADING)

    assert (await ready(unreachable)).json() == (await ready(loading)).json()
    conditions = {
        (await complete(api)).json()["details"]["conditionId"]
        for api in (unreachable, loading)
    }
    assert conditions == {"runtime-unreachable", "model-loading"}


async def test_a_dependency_error_carries_no_runtime_message_or_address() -> None:
    api, _, _ = await real_api(RUNTIME_UNREACHABLE)

    for response in (await ready(api), await complete(api)):
        text = response.text()
        for forbidden in ("10.0.0.7", "8080", "connection refused", "http://"):
            assert forbidden not in text, forbidden


async def test_the_model_list_does_not_depend_on_the_runtime_being_reachable() -> None:
    """What the metadata endpoint answers while the dependency is down.

    The real adapter reads the model identity from its configuration, so this
    endpoint answers while the runtime does not.
    """
    api, transport, _ = await real_api(RUNTIME_UNREACHABLE)

    response = await asgi_client.request(api, "GET", MODELS_PATH)

    assert response.status == 200
    assert [row["id"] for row in response.json()["data"]] == [SERVED_MODEL]
    assert transport.health_asks == 0


async def test_readiness_asks_the_adapter_on_every_request() -> None:
    """Why the ask was kept: the real adapter learns the runtime's state from it.

    The adapter refuses inference until one of its own probes has seen the
    runtime ready. A model that finishes loading is observed by the next
    readiness request, and the next completion is then served.
    """
    api, transport, _ = await real_api(RUNTIME_LOADING)
    assert (await ready(api)).json()["adapterStatus"] == ADAPTER_STATUS_NOT_READY
    assert (await complete(api)).json()["details"]["conditionId"] == "model-loading"

    transport.state = RUNTIME_READY
    assert (await complete(api)).status == 503, "no probe has seen the change yet"
    assert (await ready(api)).json()["adapterStatus"] == ADAPTER_STATUS_READY

    assert (await complete(api)).status == 200
    assert transport.health_asks == 2, "one for each readiness request"


async def test_a_ready_adapter_that_becomes_unreachable_is_reported_and_served() -> (
    None
):
    api, transport, _ = await real_api(RUNTIME_READY)
    assert (await ready(api)).json()["adapterStatus"] == ADAPTER_STATUS_READY

    transport.state = RUNTIME_UNREACHABLE
    response = await ready(api)

    assert response.status == 200
    assert response.json()["adapterStatus"] == ADAPTER_STATUS_NOT_READY
    refusal = await complete(api)
    assert refusal.status == 503
    assert refusal.json()["details"]["conditionId"] == "runtime-unreachable"


# --------------------------------------------------------------------------
# Telemetry
# --------------------------------------------------------------------------


async def test_an_adapter_that_is_not_ready_is_counted_and_the_status_is_200() -> None:
    api, _, records = await real_api(RUNTIME_LOADING)

    statuses = [(await ready(api)).status for _ in range(3)]

    assert statuses == [200, 200, 200]
    text = await scrape(api)
    assert readiness_failures(text, names.COMPONENT_ADAPTER) == 3
    assert readiness_failures(text, names.COMPONENT_API) == 0
    failed = [
        row for row in records if row["inferops.event"] == names.EVENT_READINESS_FAILED
    ]
    assert [row[names.COMPONENT] for row in failed] == [names.COMPONENT_ADAPTER] * 3


async def test_an_api_that_is_not_accepting_work_is_counted_as_the_api() -> None:
    api, transport, _ = await real_api(RUNTIME_READY)
    api.lifecycle.begin_shutdown()

    assert (await ready(api)).status == 503

    text = await scrape(api)
    assert readiness_failures(text, names.COMPONENT_API) == 1
    assert readiness_failures(text, names.COMPONENT_ADAPTER) == 0
    assert transport.health_asks == 0


# --------------------------------------------------------------------------
# A runtime that does not answer inside the budget
# --------------------------------------------------------------------------


class SilentAdapter(RecordingAdapter):
    """An adapter whose readiness answer never arrives."""

    cancelled = False

    async def is_ready(self, context: RequestContext) -> bool:
        self.ready_calls.append(context)
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return True


def api_with_budget(adapter: object, budget_ms: int) -> InferOpsApi:
    return InferOpsApi(
        adapter=adapter,  # type: ignore[arg-type]
        adapter_configuration=AdapterConfiguration(
            model_identifier="mock-fixed-fixture", timeout_ms=5_000
        ),
        configuration=ApiConfiguration(
            adapter_kind="mock", adapter_readiness_timeout_ms=budget_ms
        ),
        clock=fixed_clock,
    )


async def test_an_adapter_that_does_not_answer_cannot_delay_readiness() -> None:
    """A late readiness answer is a failed probe, so the ask is bounded.

    The outer wait is the assertion: without the budget this request would not
    return, and the test would fail on the outer timeout.
    """
    adapter = SilentAdapter()
    api = api_with_budget(adapter, budget_ms=50)
    await api.startup()

    response = await asyncio.wait_for(ready(api), timeout=5)

    assert response.status == 200
    assert response.json()["status"] == "ready"
    assert response.json()["adapterStatus"] == ADAPTER_STATUS_NOT_READY
    assert adapter.cancelled is True
    assert readiness_failures(await scrape(api), names.COMPONENT_ADAPTER) == 1


@pytest.mark.parametrize("budget_ms", [0, -1])
def test_a_readiness_budget_that_is_not_positive_is_refused(budget_ms: int) -> None:
    with pytest.raises(InvalidValueError):
        ApiConfiguration(adapter_kind="mock", adapter_readiness_timeout_ms=budget_ms)


def test_the_default_budget_is_shorter_than_the_default_probe_timeout() -> None:
    """The relation the budget exists for, on the chart's default values.

    It is a comparison of two declared numbers. The chart does not refuse a
    values file that sets a shorter probe timeout, and no probe was timed.
    """
    values = yaml.safe_load(CHART_VALUES.read_text(encoding="utf-8"))
    timeout_ms = values["api"]["probes"]["readiness"]["timeoutSeconds"] * 1000

    assert timeout_ms > DEFAULT_ADAPTER_READINESS_TIMEOUT_MS


# --------------------------------------------------------------------------
# An API that cannot honor its contract
# --------------------------------------------------------------------------


async def test_an_api_that_has_not_started_is_not_ready_and_does_not_ask() -> None:
    adapter = RecordingAdapter()
    api = api_with_budget(adapter, budget_ms=1_000)

    response = await ready(api)

    assert response.status == 503
    assert response.json() == {
        "status": "not-ready",
        "adapterKind": "mock",
        "state": "starting",
        "adapterStatus": ADAPTER_STATUS_NOT_ASKED,
    }
    assert adapter.ready_calls == []


async def test_a_draining_api_is_not_ready_while_its_adapter_still_is() -> None:
    """Shutdown: the API's own state decides, and a ready adapter does not help."""
    adapter = RecordingAdapter()
    api = api_with_budget(adapter, budget_ms=1_000)
    await api.startup()
    assert (await ready(api)).status == 200
    asked = len(adapter.ready_calls)

    api.lifecycle.begin_shutdown()
    response = await ready(api)

    assert response.status == 503
    assert response.json() == {
        "status": "not-ready",
        "adapterKind": "mock",
        "state": "draining",
        "adapterStatus": ADAPTER_STATUS_NOT_ASKED,
    }
    assert len(adapter.ready_calls) == asked
    assert (await asgi_client.request(api, "GET", LIVE_PATH)).status == 200


async def test_a_draining_api_refuses_inference_with_its_own_condition() -> None:
    """The refusal a draining API gives is about the API, not about the runtime."""
    api, transport, _ = await real_api(RUNTIME_READY)
    api.lifecycle.begin_shutdown()

    response = await complete(api)

    assert response.status == 503
    body = response.json()
    assert body["details"]["conditionId"] == "deployment-draining"
    assert body["retryable"] is True
    assert body["retryAfterMs"] > 0
    assert transport.completions == 0


async def test_a_stopped_api_stays_not_ready() -> None:
    api, _, _ = await real_api(RUNTIME_READY)
    await api.shutdown()

    response = await ready(api)

    assert api.lifecycle.state is LifecycleState.STOPPED
    assert response.status == 503
    assert response.json()["state"] == "stopped"
    assert response.json()["adapterStatus"] == ADAPTER_STATUS_NOT_ASKED


# --------------------------------------------------------------------------
# The body
# --------------------------------------------------------------------------


def test_the_adapter_status_vocabulary_is_closed() -> None:
    assert ADAPTER_STATUSES == ("ready", "not-ready", "not-asked")
    with pytest.raises(ValueError, match="not a declared adapter status"):
        ready_body(
            ready=True,
            adapter_kind="mock",
            lifecycle_state="serving",
            adapter_status="loading",
        )


@pytest.mark.parametrize(
    ("ready_flag", "adapter_status"),
    [
        (True, ADAPTER_STATUS_READY),
        (True, ADAPTER_STATUS_NOT_READY),
        (False, ADAPTER_STATUS_NOT_ASKED),
    ],
)
def test_the_status_member_follows_the_api_and_not_the_adapter(
    ready_flag: bool, adapter_status: str
) -> None:
    body = ready_body(
        ready=ready_flag,
        adapter_kind="real",
        lifecycle_state="serving",
        adapter_status=adapter_status,
    )

    assert body["status"] == ("ready" if ready_flag else "not-ready")
    assert body["adapterStatus"] == adapter_status
    assert set(body) == {"status", "adapterKind", "state", "adapterStatus"}
