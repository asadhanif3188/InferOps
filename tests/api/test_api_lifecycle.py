"""Starting, serving, draining, and stopping — and the order they happen in.

`ADR 0010` declines to give this API a shutdown endpoint, because an HTTP route
that stops a process would be an unauthenticated remote-stop control on a surface
with no authentication in V1. What it chose instead is an equivalent: readiness
goes false, what is in flight drains, and the process exits.

**The order is the property, not the fact that a shutdown happens.** A process
that drains before reporting itself unready spends the drain window receiving
exactly the requests it was trying to finish without. So the first assertion in
this suite is that readiness is false *while* work is still in flight, and the
last is that the adapter is released only after the drain.

The suite drives the ASGI lifespan protocol the way a server drives it — one call
held open, two events sent into it — because calling the application once per
event would let it return between them, which is the one thing a lifespan call
does not do.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import MutableMapping
from typing import Any

import pytest

from inferops.api import (
    DRAINING_MESSAGE,
    ApiConfiguration,
    ApplicationLifecycle,
    InferOpsApi,
    LifecycleState,
    ShuttingDown,
    install_termination_handlers,
)
from inferops.api.lifecycle import TERMINATION_SIGNALS
from inferops.api.surface import CHAT_COMPLETIONS_PATH, LIVE_PATH, READY_PATH
from inferops.domain.serving import InvalidAdapterConfigError, InvalidValueError
from tests.support import asgi_client
from tests.support.api_composition import MOCK_MODEL, RecordingAdapter, build

pytestmark = pytest.mark.mockintegration


def completion_request() -> bytes:
    return json.dumps(
        {"model": MOCK_MODEL, "messages": [{"role": "user", "content": "hi"}]}
    ).encode("utf-8")


# --------------------------------------------------------------------------
# The state machine
# --------------------------------------------------------------------------


def test_a_lifecycle_starts_not_accepting_work() -> None:
    lifecycle = ApplicationLifecycle()
    assert lifecycle.state is LifecycleState.STARTING
    assert lifecycle.is_accepting_work is False


def test_shutdown_stops_accepting_work_before_anything_is_drained() -> None:
    """The ordering the accepted equivalent rests on."""
    lifecycle = ApplicationLifecycle()
    lifecycle.begin_serving()
    with lifecycle.accept():
        lifecycle.begin_shutdown()
        assert lifecycle.is_accepting_work is False
        assert lifecycle.in_flight == 1
        with pytest.raises(ShuttingDown), lifecycle.accept():
            pass


def test_beginning_a_shutdown_twice_is_not_an_error() -> None:
    """A termination signal can arrive more than once."""
    lifecycle = ApplicationLifecycle()
    lifecycle.begin_serving()
    lifecycle.begin_shutdown()
    lifecycle.begin_shutdown()
    assert lifecycle.state is LifecycleState.DRAINING


async def test_a_drain_waits_for_in_flight_work_and_reports_that_it_finished() -> None:
    lifecycle = ApplicationLifecycle(drain_timeout_ms=1_000)
    lifecycle.begin_serving()
    released = asyncio.Event()

    async def one_request() -> None:
        with lifecycle.accept():
            await released.wait()

    task = asyncio.create_task(one_request())
    await asyncio.sleep(0)
    drain = asyncio.create_task(lifecycle.drain())
    await asyncio.sleep(0.02)
    assert not drain.done(), "the drain returned while a request was in flight"
    released.set()
    await task
    assert await drain is True
    assert lifecycle.state is LifecycleState.STOPPED


async def test_a_drain_that_runs_out_of_budget_reports_that_it_did_not_finish() -> None:
    """A truncated drain is recorded, because the requests it abandoned are real."""
    lifecycle = ApplicationLifecycle(drain_timeout_ms=20)
    lifecycle.begin_serving()
    forever = asyncio.Event()

    async def one_request() -> None:
        with lifecycle.accept():
            await forever.wait()

    task = asyncio.create_task(one_request())
    await asyncio.sleep(0)
    assert await lifecycle.drain() is False
    assert lifecycle.state is LifecycleState.STOPPED
    forever.set()
    await task


async def test_a_termination_handler_reports_which_signals_it_installed() -> None:
    """What is installed is reported, so a platform that supports none is visible.

    No signal is sent. A suite that raised `SIGTERM` would be raising it at the
    process running the suite, and what is checkable without that is the pair
    this function is: which signals were registered, and that the callback it
    registers is the one that stops this API accepting work.
    """
    lifecycle = ApplicationLifecycle()
    lifecycle.begin_serving()
    loop = asyncio.get_running_loop()
    installed = install_termination_handlers(loop, lifecycle)
    try:
        assert set(installed) <= set(TERMINATION_SIGNALS)
        lifecycle.begin_shutdown()
        assert lifecycle.is_accepting_work is False
        assert lifecycle.state is LifecycleState.DRAINING
    finally:
        for number in installed:
            loop.remove_signal_handler(number)


# --------------------------------------------------------------------------
# The application through it
# --------------------------------------------------------------------------


async def test_startup_initializes_the_adapter_before_readiness_can_be_true() -> None:
    adapter = RecordingAdapter()
    api = build(adapter)
    assert (await asgi_client.request(api, "GET", READY_PATH)).status == 503
    await api.startup()
    assert adapter.initialized is True
    assert (await asgi_client.request(api, "GET", READY_PATH)).status == 200


async def test_a_draining_api_refuses_new_work_and_still_answers_liveness(
    recording_api: InferOpsApi,
) -> None:
    recording_api.lifecycle.begin_shutdown()
    refused = await asgi_client.request(
        recording_api, "POST", CHAT_COMPLETIONS_PATH, body=completion_request()
    )
    assert refused.status == 503
    body = refused.json()
    assert body["code"] == "capability-unavailable"
    assert body["message"] == DRAINING_MESSAGE
    assert (await asgi_client.request(recording_api, "GET", LIVE_PATH)).status == 200
    assert (await asgi_client.request(recording_api, "GET", READY_PATH)).status == 503


async def test_shutdown_drains_before_it_releases_the_adapter() -> None:
    """Releasing a backend under in-flight work turns a drain into a batch of errors."""
    adapter = RecordingAdapter()
    api = build(adapter, drain_timeout_ms=1_000)
    await api.startup()
    released = asyncio.Event()
    observed: list[int] = []

    async def slow_infer(prompt: str, context: object) -> object:
        await released.wait()
        observed.append(adapter.shutdown_calls)
        return await RecordingAdapter.infer(adapter, prompt, context)  # type: ignore[arg-type]

    adapter.infer = slow_infer  # type: ignore[assignment,method-assign]

    request = asyncio.create_task(
        asgi_client.request(
            api, "POST", CHAT_COMPLETIONS_PATH, body=completion_request()
        )
    )
    await asyncio.sleep(0.01)
    shutdown = asyncio.create_task(api.shutdown())
    await asyncio.sleep(0.02)
    assert not shutdown.done(), "the shutdown returned while a request was in flight"
    released.set()
    response = await request
    await shutdown

    assert response.status == 200, response.text()
    assert observed == [0], "the adapter was shut down before the request finished"
    assert adapter.shutdown_calls == 1
    assert api.drained_cleanly is True


async def test_the_lifespan_protocol_starts_and_stops_the_application() -> None:
    adapter = RecordingAdapter()
    api = build(adapter)
    async with asgi_client.LifespanSession(api) as session:
        assert "lifespan.startup.complete" in session.result.types
        assert adapter.initialized is True
        assert (await asgi_client.request(api, "GET", READY_PATH)).status == 200
    assert "lifespan.shutdown.complete" in session.result.types
    assert adapter.shutdown_calls == 1
    assert api.lifecycle.state is LifecycleState.STOPPED


async def test_a_startup_failure_is_reported_without_the_adapter_message() -> None:
    """A startup failure's own words are where a model path reaches a server log."""
    adapter = RecordingAdapter()

    async def refuse(config: object, context: object) -> None:
        raise InvalidAdapterConfigError(
            "model_identifier", "/var/lib/models/secret-path.gguf"
        )

    adapter.initialize = refuse  # type: ignore[method-assign]
    api = build(adapter)
    session = asgi_client.LifespanSession(api)
    with pytest.raises(InvalidAdapterConfigError):
        await session.__aenter__()

    reported = [str(message.get("message", "")) for message in session.result.messages]
    assert "lifespan.startup.failed" in session.result.types
    assert "secret-path" not in "".join(reported)
    assert api.lifecycle.state is LifecycleState.STARTING


async def test_an_api_refuses_a_configuration_naming_an_unknown_adapter_kind() -> None:
    """The closed vocabulary is what stops a deployment labelling itself anything."""
    with pytest.raises(InvalidValueError):
        ApiConfiguration(adapter_kind="banana")


async def test_a_request_stays_counted_until_its_response_has_been_sent() -> None:
    """The slot is released after the send, not after the adapter answers.

    A drain that returned in the gap between those two would report a clean
    shutdown over a response nobody received, which is the one outcome the drain
    exists to prevent. The check reads the in-flight count from inside the send
    itself, which is the only place the distinction is visible.
    """
    adapter = RecordingAdapter()
    api = build(adapter)
    await api.startup()
    counted: list[int] = []

    async def receive() -> MutableMapping[str, Any]:
        return {
            "type": "http.request",
            "body": completion_request(),
            "more_body": False,
        }

    async def send(message: MutableMapping[str, Any]) -> None:
        counted.append(api.lifecycle.in_flight)

    scope: MutableMapping[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": CHAT_COMPLETIONS_PATH,
        "headers": [],
    }
    await api(scope, receive, send)

    assert counted == [1, 1], counted
    assert api.lifecycle.in_flight == 0


async def test_a_caller_that_disconnects_before_sending_a_body_is_refused() -> None:
    """A server reports a disconnect as a message, and it is not an empty body."""
    adapter = RecordingAdapter()
    api = build(adapter)
    await api.startup()
    sent: list[MutableMapping[str, Any]] = []

    async def receive() -> MutableMapping[str, Any]:
        return {"type": "http.disconnect"}

    async def send(message: MutableMapping[str, Any]) -> None:
        sent.append(message)

    scope: MutableMapping[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": CHAT_COMPLETIONS_PATH,
        "headers": [],
    }
    await api(scope, receive, send)

    start = next(m for m in sent if m["type"] == "http.response.start")
    assert start["status"] == 400
    assert adapter.prompts == [], "the adapter was called for a request nobody sent"
