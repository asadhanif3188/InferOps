"""The local composition through controlled seams, never a real model.

These checks validate the committed real-only wiring and exercise its lifecycle
with synthetic command and transport responses. One test crosses a loopback
socket into the real adapter type, but the transport behind that adapter is a
controlled double; this is `mockintegration` evidence and cannot certify a real
runtime or model.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from inferops.adapters.llama_cpp import RuntimeResponse
from inferops.api import EXTENSION_MEMBER, InferOpsApi, build
from tools.local_composition import core
from tools.local_composition.http_server import LocalApiServer
from tools.runtime_packaging import CommandResult, ReadinessTrace

pytestmark = pytest.mark.mockintegration


class NoCommandRunner:
    def run(self, arguments: Sequence[str]) -> CommandResult:
        raise AssertionError(f"offline composition unexpectedly ran {arguments[0]}")


class SyntheticRuntimeTransport:
    """A real-adapter transport with generated responses and no runtime socket."""

    def __init__(self) -> None:
        self.closed = False

    async def get(self, url: str, *, timeout_s: float) -> RuntimeResponse:
        assert timeout_s > 0
        assert url.endswith("/health")
        return RuntimeResponse(200, {"status": "ok"})

    async def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        timeout_s: float,
    ) -> RuntimeResponse:
        assert timeout_s > 0
        assert url.endswith("/v1/chat/completions")
        assert payload["messages"]
        return RuntimeResponse(
            200,
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "controlled composition response",
                        },
                    }
                ],
                "model": "qwen3-1.7b-q8_0",
                "object": "chat.completion",
                "usage": {
                    "completion_tokens": 3,
                    "prompt_tokens": 2,
                    "total_tokens": 5,
                },
            },
        )

    async def close(self) -> None:
        self.closed = True


def test_descriptor_selects_real_only_and_matches_runtime_package() -> None:
    composition = core.load_composition()

    assert composition.adapter_selection == "real"
    assert composition.mock_fallback is False
    assert composition.environment["INFEROPS_SERVING_ADAPTER"] == "real"
    assert composition.environment["INFEROPS_LLAMA_SERVER_ENDPOINT"] == (
        "http://127.0.0.1:8080"
    )
    assert composition.startup_order == (
        "runtime",
        "runtime-readiness",
        "api",
        "api-readiness",
    )
    assert composition.shutdown_order == ("api", "runtime")
    assert composition.loopback_only is True
    assert composition.embedded_secrets == ()


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("adapter", "selection", "mock"),
        ("adapter", "mockFallback", True),
        ("api", "host", "0.0.0.0"),
        ("security", "embeddedSecrets", ["canary"]),
    ],
)
def test_descriptor_refuses_unsafe_or_mock_mutations(
    tmp_path: Path, section: str, field: str, value: object
) -> None:
    document = json.loads(core.COMPOSITION_PATH.read_text(encoding="utf-8"))
    document[section][field] = value
    candidate = tmp_path / "composition.json"
    candidate.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(core.CompositionError):
        core.load_composition(candidate)


def test_foreground_orchestration_orders_readiness_and_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []

    def start(*_args: object, **_kwargs: object) -> None:
        events.append("runtime.start")

    def ready(*_args: object, **_kwargs: object) -> ReadinessTrace:
        events.append("runtime.ready")
        return ReadinessTrace((503, 200), 12)

    def stop(*_args: object, **_kwargs: object) -> bool:
        events.append("runtime.stop")
        return True

    class FakeServer:
        def __init__(self, application: InferOpsApi) -> None:
            self.application = application

        def start(self) -> None:
            events.append("api.start")

        def serve_in_background(self) -> None:
            events.append("api.serve")

        def request_stop(self) -> None:
            events.append("api.stop")

        def join(self) -> None:
            events.append("api.join")

        def close(self) -> None:
            events.append("api.close")
            self.application._drained = True

    def server_factory(
        application: InferOpsApi,
        *,
        host: str,
        port: int,
        request_body_limit_bytes: int,
        response_timeout_seconds: float,
        shutdown_timeout_seconds: float,
    ) -> FakeServer:
        assert host == "127.0.0.1"
        assert port == 8090
        assert request_body_limit_bytes > 0
        assert response_timeout_seconds > 0
        assert shutdown_timeout_seconds > 0
        return FakeServer(application)

    def api_ready(*_args: object, **_kwargs: object) -> int:
        events.append("api.ready")
        return 7

    monkeypatch.setattr(core, "start_runtime", start)
    monkeypatch.setattr(core, "wait_runtime_ready", ready)
    monkeypatch.setattr(core, "stop_runtime", stop)
    monkeypatch.setattr(core, "wait_api_ready", api_ready)

    result = core.run_foreground(
        core.load_composition(),
        confirmed=True,
        repo_root=tmp_path,
        runner=NoCommandRunner(),
        server_factory=server_factory,
    )

    assert events == [
        "runtime.start",
        "runtime.ready",
        "api.start",
        "api.serve",
        "api.ready",
        "api.join",
        "api.stop",
        "api.join",
        "api.close",
        "runtime.stop",
    ]
    assert result.runtime_readiness_ms == 12
    assert result.api_readiness_ms == 7
    assert result.api_drained is True
    assert result.runtime_removed is True

    original_event = core.CompositionLog.event

    def fail_after_api_stop(
        self: core.CompositionLog, name: str, **fields: object
    ) -> None:
        if name == "composition.api.stopped":
            raise OSError("synthetic log failure")
        original_event(self, name, **fields)

    monkeypatch.setattr(core.CompositionLog, "event", fail_after_api_stop)
    events.clear()
    with pytest.raises(core.CompositionError, match="cleanup was incomplete"):
        core.run_foreground(
            core.load_composition(),
            confirmed=True,
            repo_root=tmp_path,
            runner=NoCommandRunner(),
            server_factory=server_factory,
        )
    assert events[-1] == "runtime.stop"


def test_loopback_carrier_reaches_explicit_real_adapter_over_controlled_transport() -> (
    None
):
    composition = core.load_composition()
    transport = SyntheticRuntimeTransport()
    records: list[str] = []
    application = build(
        core.composition_environment(composition),
        transport=transport,
        sink=records.append,
    )
    server = LocalApiServer(
        application,
        host="127.0.0.1",
        port=0,
        request_body_limit_bytes=composition.request_body_limit_bytes,
        response_timeout_seconds=3,
        shutdown_timeout_seconds=3,
    )
    server.start()
    server.serve_in_background()
    base_url = f"http://127.0.0.1:{server.bound_port}"
    try:
        with urlopen(f"{base_url}/health/ready", timeout=3) as response:
            readiness = json.loads(response.read())
        assert readiness == core.READY_BODY

        body = json.dumps(
            {
                "model": "qwen3-1-7b-q8-0",
                "messages": [{"role": "user", "content": "hello"}],
            }
        ).encode("utf-8")
        request = Request(
            f"{base_url}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            completion = json.loads(response.read())
        assert completion["choices"][0]["message"]["content"]
        assert completion[EXTENSION_MEMBER]["adapterKind"] == "real"
    finally:
        server.request_stop()
        server.join()
        server.close()

    assert transport.closed is True
    assert application.drained_cleanly is True
    assert records


def test_real_operations_require_explicit_confirmation() -> None:
    with pytest.raises(core.CompositionError, match="confirm-real-runtime"):
        core.status(core.load_composition(), NoCommandRunner(), confirmed=False)


@pytest.mark.parametrize(
    "linked_relative",
    [Path(".cache"), Path(".cache/inferops/composition/local-real.jsonl")],
    ids=("linked-parent", "linked-leaf"),
)
def test_composition_log_refuses_a_linked_component(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, linked_relative: Path
) -> None:
    linked_path = tmp_path.resolve() / linked_relative
    original = Path.is_symlink

    def linked(self: Path) -> bool:
        return self == linked_path or original(self)

    monkeypatch.setattr(Path, "is_symlink", linked)

    with pytest.raises(core.CompositionError, match="log path is unsafe"):
        core.CompositionLog(core.load_composition(), repo_root=tmp_path)
