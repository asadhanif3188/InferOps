"""Rehearse a load run end to end against an in-process stub, with no cluster or model.

A rehearsal drives the same :func:`tools.llm_load.core.execute` a real run does -- the
loopback check, the identity probe, the warm-up, the closed-loop levels, the
classifier, the raw writer, and the raw reader's accounting checks -- over real HTTP
on a loopback socket. What answers is a stub in this process.

**Its output is synthetic and says so.** The stub names its adapter
``synthetic-stub`` rather than ``real``, the rehearsal profile requires that name, the
raw header is ``synthetic`` with ceiling ``C1``, and it carries no environment facts,
so no provider. A real run refuses a ``synthetic-stub`` answer exactly as it refuses a
``mock`` one. Every latency a rehearsal records is the stub's own sleep plus loopback,
and describes nothing about serving.

The stub's answers are a function of the request's sequence number, which it reads
from the request identifier header, so the outcome of every request in a rehearsal is
fixed in advance. Because each level's request ceiling is reached long before its
duration, the count of requests per level is fixed too. Only the timings vary.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from inferops.api.surface import (
    CONTRACT_VERSION,
    EXTENSION_MEMBER,
    REQUEST_ID_HEADER,
)
from tools.model_acquisition import load_manifest

from .core import LOOPBACK_HOST, Profile

REHEARSAL_ADAPTER_KIND = "synthetic-stub"
REHEARSAL_RUNTIME_NAME = "synthetic rehearsal stub"
REHEARSAL_RUNTIME_VERSION = "synthetic"

#: A rehearsal's bounds. Small enough to finish in seconds, and chosen so that every
#: level stops on its request ceiling rather than its duration.
REHEARSAL_DURATION_SECONDS = 20
REHEARSAL_MAX_REQUESTS_PER_LEVEL = 12
REHEARSAL_REQUEST_TIMEOUT_MS = 5_000
REHEARSAL_IDENTITY_TIMEOUT_MS = 2_000

#: How long the stub holds each completion before answering.
STUB_LATENCY_SECONDS = 0.02

#: The completion text the stub returns. A test asserts it never reaches a raw
#: record, which is the rehearsal's proof that completions are not retained.
STUB_COMPLETION_TEXT = "SYNTHETIC-COMPLETION-TEXT-THAT-MUST-NEVER-BE-RECORDED"

STUB_PROMPT_TOKENS = 31
STUB_COMPLETION_TOKENS = 17


def rehearsal_profile(profile: Profile) -> Profile:
    """The committed profile, shrunk to seconds and pointed at the stub's identity.

    Only the bounds and the identity change. The fixture, the generation settings, the
    warm-up size, the levels, and the result layout are the committed ones, so a
    rehearsal exercises the profile a real run would send.
    """
    return replace(
        profile,
        duration_seconds=REHEARSAL_DURATION_SECONDS,
        max_requests_per_level=REHEARSAL_MAX_REQUESTS_PER_LEVEL,
        request_timeout_ms=REHEARSAL_REQUEST_TIMEOUT_MS,
        identity_probe_timeout_ms=REHEARSAL_IDENTITY_TIMEOUT_MS,
        required_adapter_kind=REHEARSAL_ADAPTER_KIND,
        required_runtime_name=REHEARSAL_RUNTIME_NAME,
    )


def stub_answer(sequence: int, model: str) -> tuple[int, dict[str, Any]]:
    """What the stub answers to request ``sequence``: a fixed function of the number.

    Every ninth request (8, 17, 26, 35) is a canonical ``model-not-ready`` refusal and
    every thirteenth (12, 25, 38) is a completion with no usage counts. The first
    three, the warm-up, always succeed.
    """
    extension = {
        "requestId": f"stub-{sequence:05d}",
        "correlationId": "stub",
        "contractVersion": CONTRACT_VERSION,
        "adapterKind": REHEARSAL_ADAPTER_KIND,
        "modelRef": model,
    }
    if sequence % 9 == 8:
        return 503, {
            "code": "model-not-ready",
            "message": "the model is loading",
            "requestId": extension["requestId"],
            "correlationId": "stub",
            "retryable": True,
            "details": {"adapterKind": REHEARSAL_ADAPTER_KIND, "modelRef": model},
        }
    completion = {
        "id": f"chatcmpl-stub-{sequence:05d}",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": STUB_COMPLETION_TEXT},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": STUB_PROMPT_TOKENS,
            "completion_tokens": STUB_COMPLETION_TOKENS,
            "total_tokens": STUB_PROMPT_TOKENS + STUB_COMPLETION_TOKENS,
        },
        EXTENSION_MEMBER: extension,
    }
    if sequence % 13 == 12:
        completion["usage"] = None
    return 200, completion


def _handler(profile: Profile) -> type[BaseHTTPRequestHandler]:
    model = profile.fixture.model
    revision = load_manifest().revision

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: Any) -> None:
            return None

        def _send(self, status: int, body: object) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            if self.path == profile.readiness_path:
                self._send(
                    200,
                    {
                        "status": "ready",
                        "adapterKind": REHEARSAL_ADAPTER_KIND,
                        "state": "ready",
                    },
                )
            elif self.path == profile.models_path:
                self._send(
                    200,
                    {
                        "object": "list",
                        "data": [{"id": model, "object": "model", "owned_by": "stub"}],
                        EXTENSION_MEMBER: {
                            "contractVersion": CONTRACT_VERSION,
                            "adapterKind": REHEARSAL_ADAPTER_KIND,
                            "runtime": {
                                "name": REHEARSAL_RUNTIME_NAME,
                                "version": REHEARSAL_RUNTIME_VERSION,
                                "modelRevision": revision,
                            },
                        },
                    },
                )
            else:
                self._send(404, {"code": "contract-invalid"})

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            request_id = self.headers.get(REQUEST_ID_HEADER) or ""
            try:
                sequence = int(request_id.rsplit("-", 1)[1])
            except (IndexError, ValueError):
                self._send(400, {"code": "contract-invalid"})
                return
            time.sleep(STUB_LATENCY_SECONDS)
            status, body = stub_answer(sequence, model)
            self._send(status, body)

    return Handler


@contextmanager
def stub_server(profile: Profile) -> Iterator[str]:
    """Serve the stub on an ephemeral loopback port for the duration of the block."""
    server = ThreadingHTTPServer((LOOPBACK_HOST, 0), _handler(profile))
    server.daemon_threads = True
    thread = threading.Thread(
        target=server.serve_forever, name="inferops-load-stub", daemon=True
    )
    thread.start()
    try:
        yield f"http://{LOOPBACK_HOST}:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
