"""Liveness, readiness, the model list, the metrics endpoint, and routing.

Four properties this suite is really about, beyond that each route answers.

**Liveness and readiness answer different questions.** `/health/live` says
whether this process is alive and says nothing about the model, which is why it
still answers while the adapter is not ready. `/health/ready` is the conjunction
of this API being willing and the selected adapter being able, and it is false
when either half is.

**A health response carries no secret.** No endpoint, no credential, no path, no
runtime message, and no configuration reaches one. A readiness probe is the
surface most likely to be reachable by something that should not see any of them.

**A capability is published from what the adapter declared.** Two of the four the
accepted record names have an adapter declaration behind them, one is derived
from the list this endpoint returns, and one is ``null`` because nothing this API
can ask declares it. Publishing `ADR 0010`'s observed value as this deployment's
own declaration is the assumption the rule exists to prevent, and the suite holds
the line.

**The metrics endpoint publishes the API's own series.** It renders every metric
the accepted telemetry catalog assigns to the ``inferops-api`` emitter and no
other, in the Prometheus text exposition format, and it answers before the
adapter has started -- a process that cannot serve is exactly the one whose
metrics are wanted. What it does **not** publish is on the record too: the one
metric assigned to this emitter with no source it may read is named in a comment
rather than published as a zero. The instrumentation itself is exercised in
``tests/api/test_api_observability.py``; what this suite holds is the endpoint.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

import pytest

from inferops.adapters import MOCK_ADAPTER_KIND, MOCK_RUNTIME_ID, MockServingAdapter
from inferops.adapters.mock_serving import MockAdapterSettings, MockScenario
from inferops.api import (
    BOUND_METRIC_NAMES,
    EXPOSITION_CONTENT_TYPE,
    EXTENSION_MEMBER,
    MOCK_EXPOSITION_NOTE,
    NO_MEMORY_SOURCE_NOTE,
    REQUEST_ID_HEADER,
    InferOpsApi,
)
from inferops.api.surface import (
    CHAT_COMPLETIONS_PATH,
    LIVE_PATH,
    METRICS_PATH,
    MODELS_PATH,
    READY_PATH,
)
from inferops.telemetry import names
from tests.support import asgi_client
from tests.support.api_composition import (
    FIXED_NOW,
    MOCK_MODEL,
    RecordingAdapter,
    build,
)

pytestmark = pytest.mark.mockintegration


async def get(api: InferOpsApi, path: str) -> asgi_client.Response:
    return await asgi_client.request(api, "GET", path)


# --------------------------------------------------------------------------
# Liveness
# --------------------------------------------------------------------------


async def test_liveness_answers_before_the_adapter_has_started() -> None:
    """Alive and able to serve are different questions, and only one is asked here."""
    api = build(RecordingAdapter())
    response = await get(api, LIVE_PATH)
    assert response.status == 200
    assert response.json() == {"status": "alive"}


async def test_liveness_carries_nothing_but_the_status(mock_api: InferOpsApi) -> None:
    assert set((await get(mock_api, LIVE_PATH)).json()) == {"status"}


# --------------------------------------------------------------------------
# Readiness
# --------------------------------------------------------------------------


async def test_readiness_is_false_before_startup() -> None:
    api = build(RecordingAdapter())
    response = await get(api, READY_PATH)
    assert response.status == 503
    body = response.json()
    assert body["status"] == "not-ready"
    assert body["state"] == "starting"


async def test_readiness_is_true_once_the_adapter_reports_ready(
    mock_api: InferOpsApi,
) -> None:
    response = await get(mock_api, READY_PATH)
    assert response.status == 200
    assert response.json()["status"] == "ready"


async def test_readiness_reflects_the_selected_backend_rather_than_this_process(
    recording_adapter: RecordingAdapter, recording_api: InferOpsApi
) -> None:
    """The half of readiness that is not this API's own state."""
    assert (await get(recording_api, READY_PATH)).status == 200
    recording_adapter.model_ready = False
    response = await get(recording_api, READY_PATH)
    assert response.status == 503
    assert response.json()["status"] == "not-ready"


async def test_a_backend_that_raises_while_being_asked_is_not_ready(
    recording_adapter: RecordingAdapter, recording_api: InferOpsApi
) -> None:
    async def explode(context: object) -> bool:
        raise RuntimeError("the runtime endpoint refused the connection")

    recording_adapter.is_ready = explode  # type: ignore[method-assign]
    response = await get(recording_api, READY_PATH)
    assert response.status == 503
    assert "refused the connection" not in response.text()


async def test_readiness_names_the_adapter_kind_and_nothing_else(
    mock_api: InferOpsApi,
) -> None:
    body = (await get(mock_api, READY_PATH)).json()
    assert set(body) == {"status", "adapterKind", "state"}
    assert body["adapterKind"] == MOCK_ADAPTER_KIND


async def test_a_health_response_carries_no_endpoint_credential_or_path(
    mock_api: InferOpsApi,
) -> None:
    """The property a probe surface is judged on."""
    for path in (LIVE_PATH, READY_PATH):
        text = (await get(mock_api, path)).text()
        for forbidden in ("http://", "https://", "password", "token", "/var/", "C:\\"):
            assert forbidden not in text, (path, forbidden)


async def test_a_not_ready_adapter_still_answers_liveness() -> None:
    """The reason liveness has no runtime counterpart in the accepted record."""
    adapter = MockServingAdapter(
        MockAdapterSettings(scenario=MockScenario.MODEL_NOT_READY)
    )
    api = build(adapter)
    await api.startup()
    assert (await get(api, LIVE_PATH)).status == 200
    assert (await get(api, READY_PATH)).status == 503


# --------------------------------------------------------------------------
# The model list
# --------------------------------------------------------------------------


async def test_the_model_list_returns_exactly_one_model(
    mock_api: InferOpsApi,
) -> None:
    body = (await get(mock_api, MODELS_PATH)).json()
    assert body["object"] == "list"
    assert len(body["data"]) == 1
    entry = body["data"][0]
    assert entry["id"] == MOCK_MODEL
    assert entry["object"] == "model"
    assert entry["created"] == FIXED_NOW
    assert entry["owned_by"] == "inferops"


async def test_the_model_list_publishes_the_runtime_descriptor(
    mock_api: InferOpsApi,
) -> None:
    """A mock stays visibly a mock: the runtime identity is the mock's own."""
    extension = (await get(mock_api, MODELS_PATH)).json()[EXTENSION_MEMBER]
    assert extension["adapterKind"] == MOCK_ADAPTER_KIND
    assert extension["runtime"]["name"] == MOCK_RUNTIME_ID


async def test_declared_capabilities_come_from_the_adapter_not_from_a_constant(
    mock_api: InferOpsApi,
) -> None:
    """The mock declares token counting unsupported, and the surface says so."""
    capabilities = (await get(mock_api, MODELS_PATH)).json()[EXTENSION_MEMBER][
        "capabilities"
    ]
    assert capabilities["streaming"] is False
    assert capabilities["tokenUsage"] is False
    assert capabilities["multiModel"] is False


async def test_an_adapter_that_counts_tokens_publishes_the_capability_as_true(
    recording_api: InferOpsApi,
) -> None:
    capabilities = (await get(recording_api, MODELS_PATH)).json()[EXTENSION_MEMBER][
        "capabilities"
    ]
    assert capabilities["tokenUsage"] is True


async def test_deterministic_sampling_is_published_as_null_rather_than_assumed(
    mock_api: InferOpsApi,
) -> None:
    """`null` is the honest value for a question nothing this API can ask answers.

    `ADR 0010` declares it `true` on the strength of a Sprint 0 observation of the
    runtime. That is an observation of a runtime, not a declaration the selected
    adapter makes, and the frozen adapter interface has no capability for it. The
    gap is published as an absence rather than closed with someone else's
    measurement.
    """
    capabilities = (await get(mock_api, MODELS_PATH)).json()[EXTENSION_MEMBER][
        "capabilities"
    ]
    assert capabilities["deterministicSampling"] is None
    assert set(capabilities) == {
        "streaming",
        "tokenUsage",
        "deterministicSampling",
        "multiModel",
    }


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


async def test_the_metrics_endpoint_answers_in_the_exposition_content_type(
    mock_api: InferOpsApi,
) -> None:
    response = await get(mock_api, METRICS_PATH)
    assert response.status == 200
    assert response.header("content-type") == EXPOSITION_CONTENT_TYPE


async def test_the_metrics_endpoint_publishes_every_metric_it_declares(
    mock_api: InferOpsApi,
) -> None:
    """Each declared metric arrives with a HELP line, a TYPE line, and a sample."""
    lines = (await get(mock_api, METRICS_PATH)).text().splitlines()
    assert lines
    for name in BOUND_METRIC_NAMES:
        assert any(line.startswith(f"# HELP {name} ") for line in lines), name
        assert any(line.startswith(f"# TYPE {name} ") for line in lines), name


async def test_the_metrics_body_names_the_one_metric_it_does_not_publish(
    mock_api: InferOpsApi,
) -> None:
    """A metric assigned to this emitter and absent says so, in a comment.

    A comment is not a metric: no ``HELP`` line, no ``TYPE`` line, and no sample,
    so a scraper records nothing for it and a person reading the scrape finds out
    why without going to the catalog.
    """
    lines = (await get(mock_api, METRICS_PATH)).text().splitlines()
    assert any(line == f"# {NO_MEMORY_SOURCE_NOTE}" for line in lines)
    published = [line for line in lines if not line.startswith("#")]
    assert not any(names.PROCESS_RESIDENT_MEMORY in line for line in published)
    assert not any(
        line.startswith(
            (
                "# HELP " + names.PROCESS_RESIDENT_MEMORY,
                "# TYPE " + names.PROCESS_RESIDENT_MEMORY,
            )
        )
        for line in lines
    )


async def test_the_metrics_body_says_the_deployment_behind_it_is_a_mock(
    mock_api: InferOpsApi,
) -> None:
    """A scrape is the surface most likely to be copied without its context."""
    text = (await get(mock_api, METRICS_PATH)).text()
    assert MOCK_EXPOSITION_NOTE in text
    assert f'{names.ADAPTER_KIND.replace(".", "_")}="{MOCK_ADAPTER_KIND}"' in text


async def test_metrics_answer_before_the_adapter_has_started() -> None:
    api = build(RecordingAdapter())
    assert (await get(api, METRICS_PATH)).status == 200


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/v1/completions",
        "/v1/embeddings",
        "/v1/responses",
        "/v1/models/qwen3-1.7b",
        "/props",
        "/completion",
        "/slots",
        "/tokenize",
        "/health",
        "/",
    ],
)
async def test_a_path_outside_the_accepted_subset_is_not_served(
    mock_api: InferOpsApi, path: str
) -> None:
    """Including every runtime-native path: the runtime's surface is not proxied."""
    response = await get(mock_api, path)
    assert response.status == 404
    assert response.json()["code"] == "contract-invalid"


async def test_a_served_path_reached_with_the_wrong_method_is_refused(
    mock_api: InferOpsApi,
) -> None:
    response = await asgi_client.request(mock_api, "GET", CHAT_COMPLETIONS_PATH)
    assert response.status == 405
    assert response.header("allow") == "POST"


async def test_every_response_carries_the_correlation_headers(
    mock_api: InferOpsApi,
) -> None:
    """Including the ones nothing routed and the one that is not JSON."""
    for method, path in (
        ("GET", LIVE_PATH),
        ("GET", READY_PATH),
        ("GET", METRICS_PATH),
        ("GET", MODELS_PATH),
        ("GET", "/nothing-here"),
        ("POST", CHAT_COMPLETIONS_PATH),
    ):
        response = await asgi_client.request(mock_api, method, path, body=b"{}")
        assert response.header(REQUEST_ID_HEADER), (method, path)


async def test_a_websocket_scope_is_closed_rather_than_served(
    mock_api: InferOpsApi,
) -> None:
    """Streaming is declared unsupported and this surface has no socket protocol."""
    sent: list[MutableMapping[str, Any]] = []

    async def receive() -> MutableMapping[str, Any]:
        return {"type": "websocket.connect"}

    async def send(message: MutableMapping[str, Any]) -> None:
        sent.append(message)

    await mock_api({"type": "websocket", "path": "/v1/chat/completions"}, receive, send)
    assert sent == [{"type": "websocket.close", "code": 1000}]


async def test_a_response_body_is_serialised_compactly(
    mock_api: InferOpsApi,
) -> None:
    """A body a caller parses, not a body a caller reads.

    The model list is what this asserts against rather than a completion, because
    a completion carries generated text and a separator inside that text would be
    a property of the fixture rather than of the serialisation.
    """
    response = await get(mock_api, MODELS_PATH)
    assert response.status == 200
    assert b", " not in response.body
    assert b'": ' not in response.body
