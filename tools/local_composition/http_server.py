"""A narrow standard-library HTTP carrier for the existing ASGI application.

The accepted API remains framework-free. This module lives in repository tooling
and implements only the HTTP/1.1 subset the five published routes need. It binds
loopback, closes every connection, and bounds body reads and response waits,
and keeps lifespan plus every request on one asyncio event loop.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable, MutableMapping, Sequence
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from inferops.api.application import InferOpsApi

Message = MutableMapping[str, Any]
Send = Callable[[Message], Awaitable[None]]

BODY_READ_TIMEOUT_SECONDS = 5.0
LIFESPAN_TIMEOUT_SECONDS = 5.0


class LocalHttpServerError(RuntimeError):
    """The local HTTP carrier could not start, serve, or stop safely."""


@dataclass(frozen=True, slots=True)
class AsgiResponse:
    status: int
    headers: tuple[tuple[bytes, bytes], ...]
    body: bytes


class _ApplicationSession:
    def __init__(self, application: InferOpsApi) -> None:
        self.application = application
        self.events: asyncio.Queue[Message] | None = None
        self.outgoing: asyncio.Queue[Message] | None = None
        self.task: asyncio.Task[None] | None = None
        self.started = False

    async def start(self) -> None:
        self.events = asyncio.Queue()
        self.outgoing = asyncio.Queue()
        self.task = asyncio.create_task(self._lifespan())
        await self.events.put({"type": "lifespan.startup"})
        message = await asyncio.wait_for(
            self.outgoing.get(), timeout=LIFESPAN_TIMEOUT_SECONDS
        )
        if message.get("type") != "lifespan.startup.complete":
            if self.task.done():
                await self.task
            raise LocalHttpServerError("the InferOps API did not complete startup")
        self.started = True

    async def stop(self) -> None:
        if (
            not self.started
            or self.events is None
            or self.outgoing is None
            or self.task is None
        ):
            return
        await self.events.put({"type": "lifespan.shutdown"})
        message = await self.outgoing.get()
        if message.get("type") != "lifespan.shutdown.complete":
            raise LocalHttpServerError("the InferOps API did not complete shutdown")
        await self.task
        self.started = False

    async def _lifespan(self) -> None:
        if self.events is None or self.outgoing is None:
            raise LocalHttpServerError("the InferOps API lifespan was not initialized")

        async def receive() -> Message:
            if self.events is None:  # pragma: no cover - guarded above
                raise LocalHttpServerError("the lifespan event queue is absent")
            return await self.events.get()

        async def send(message: Message) -> None:
            if self.outgoing is None:  # pragma: no cover - guarded above
                raise LocalHttpServerError("the lifespan output queue is absent")
            await self.outgoing.put(message)

        await self.application(
            {"type": "lifespan", "asgi": {"version": "3.0", "spec_version": "2.3"}},
            receive,
            send,
        )

    async def request(
        self,
        *,
        method: str,
        path: str,
        query: bytes,
        headers: Sequence[tuple[bytes, bytes]],
        body: bytes,
        client: tuple[str, int],
        server: tuple[str, int],
    ) -> AsgiResponse:
        pending = True

        async def receive() -> Message:
            nonlocal pending
            if pending:
                pending = False
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        sent: list[Message] = []

        async def send(message: Message) -> None:
            sent.append(message)

        scope: Message = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii", errors="surrogateescape"),
            "query_string": query,
            "root_path": "",
            "headers": list(headers),
            "client": client,
            "server": server,
        }
        await self.application(scope, receive, send)
        starts = [
            message for message in sent if message.get("type") == "http.response.start"
        ]
        if len(starts) != 1:
            raise LocalHttpServerError("the InferOps API produced no single response")
        start = starts[0]
        payload = b"".join(
            bytes(message.get("body") or b"")
            for message in sent
            if message.get("type") == "http.response.body"
        )
        return AsgiResponse(
            status=int(start["status"]),
            headers=tuple(
                (bytes(name), bytes(value)) for name, value in start.get("headers", [])
            ),
            body=payload,
        )


class _LoopThread:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            target=self._run,
            name="inferops-local-api-event-loop",
            daemon=False,
        )
        self.ready = threading.Event()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.ready.set()
        self.loop.run_forever()

    def start(self) -> None:
        self.thread.start()
        if not self.ready.wait(timeout=LIFESPAN_TIMEOUT_SECONDS):
            raise LocalHttpServerError("the InferOps API event loop did not start")

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=LIFESPAN_TIMEOUT_SECONDS)
        if self.thread.is_alive():
            raise LocalHttpServerError("the InferOps API event loop did not stop")
        self.loop.close()


class LocalApiServer:
    """Serve one InferOps API on loopback while preserving its ASGI lifecycle."""

    def __init__(
        self,
        application: InferOpsApi,
        *,
        host: str,
        port: int,
        request_body_limit_bytes: int,
        response_timeout_seconds: float,
        shutdown_timeout_seconds: float,
    ) -> None:
        self.application = application
        self.host = host
        self.port = port
        self.request_body_limit_bytes = request_body_limit_bytes
        self.response_timeout_seconds = response_timeout_seconds
        self.shutdown_timeout_seconds = shutdown_timeout_seconds
        self._loop = _LoopThread()
        self._session = _ApplicationSession(application)
        self._server: ThreadingHTTPServer | None = None
        self._serving_thread: threading.Thread | None = None

    @property
    def bound_port(self) -> int:
        if self._server is None:
            raise LocalHttpServerError("the InferOps API server is not started")
        return int(self._server.server_address[1])

    def start(self) -> None:
        self._loop.start()
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._session.start(), self._loop.loop
            )
            future.result(timeout=LIFESPAN_TIMEOUT_SECONDS + 1)
            handler = self._handler_type()
            self._server = ThreadingHTTPServer((self.host, self.port), handler)
        except Exception as error:
            self._close_after_failed_start()
            raise LocalHttpServerError(
                "the loopback InferOps API could not start"
            ) from error

    def serve_forever(self) -> None:
        if self._server is None:
            raise LocalHttpServerError("the InferOps API server is not started")
        self._server.serve_forever(poll_interval=0.1)

    def serve_in_background(self) -> None:
        self._serving_thread = threading.Thread(
            target=self.serve_forever,
            name="inferops-local-api-http",
            daemon=False,
        )
        self._serving_thread.start()

    def request_stop(self) -> None:
        if (
            self._server is not None
            and self._serving_thread is not None
            and self._serving_thread.is_alive()
        ):
            self._server.shutdown()

    def join(self) -> None:
        if self._serving_thread is not None:
            self._serving_thread.join()

    def close(self) -> None:
        failure: Exception | None = None
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._session.stop(), self._loop.loop
            )
            future.result(timeout=self.shutdown_timeout_seconds)
            if not self.application.drained_cleanly:
                failure = LocalHttpServerError(
                    "the InferOps API did not drain inside its shutdown budget"
                )
        except Exception as error:
            failure = error
        if self._server is not None:
            self._server.server_close()
        self._loop.close()
        if failure is not None:
            raise LocalHttpServerError(
                "the InferOps API shutdown was incomplete"
            ) from failure

    def _close_after_failed_start(self) -> None:
        if self._server is not None:
            self._server.server_close()
        if self._loop.thread.is_alive():
            if self._session.started:
                future = asyncio.run_coroutine_threadsafe(
                    self._session.stop(), self._loop.loop
                )
                try:
                    future.result(timeout=LIFESPAN_TIMEOUT_SECONDS)
                except Exception:
                    future.cancel()
            self._loop.close()

    def _handler_type(self) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "InferOpsLocal/1"
            sys_version = ""
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                self._dispatch()

            def do_POST(self) -> None:
                self._dispatch()

            def do_PUT(self) -> None:
                self._dispatch()

            def do_PATCH(self) -> None:
                self._dispatch()

            def do_DELETE(self) -> None:
                self._dispatch()

            def do_OPTIONS(self) -> None:
                self._dispatch()

            def do_HEAD(self) -> None:
                self._dispatch()

            def log_message(self, _format: str, *_args: object) -> None:
                return

            def _dispatch(self) -> None:
                future: Any = None
                try:
                    body = self._body()
                    split = urlsplit(self.path)
                    if split.scheme or split.netloc or not split.path.startswith("/"):
                        self._empty(HTTPStatus.BAD_REQUEST)
                        return
                    headers = tuple(
                        (name.lower().encode("ascii"), value.encode("latin-1"))
                        for name, value in self.headers.items()
                    )
                    future = asyncio.run_coroutine_threadsafe(
                        owner._session.request(
                            method=self.command,
                            path=split.path,
                            query=split.query.encode("ascii"),
                            headers=headers,
                            body=body,
                            client=(
                                str(self.client_address[0]),
                                int(self.client_address[1]),
                            ),
                            server=(owner.host, owner.bound_port),
                        ),
                        owner._loop.loop,
                    )
                    response = future.result(timeout=owner.response_timeout_seconds)
                except TimeoutError:
                    if future is not None:
                        future.cancel()
                    self._empty(HTTPStatus.GATEWAY_TIMEOUT)
                    return
                except (OSError, UnicodeError, ValueError, LocalHttpServerError):
                    self._empty(HTTPStatus.BAD_REQUEST)
                    return
                self.send_response(response.status)
                for name, value in response.headers:
                    lowered = name.lower()
                    if lowered not in {
                        b"content-length",
                        b"connection",
                        b"server",
                        b"date",
                    }:
                        self.send_header(name.decode("ascii"), value.decode("latin-1"))
                self.send_header("Content-Length", str(len(response.body)))
                self.send_header("Connection", "close")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(response.body)
                self.close_connection = True

            def _body(self) -> bytes:
                if self.headers.get("Transfer-Encoding"):
                    raise ValueError("transfer encoding is unsupported")
                raw_length = self.headers.get("Content-Length", "0")
                length = int(raw_length)
                if length < 0:
                    raise ValueError("negative content length")
                if length > owner.request_body_limit_bytes:
                    return b"x" * (owner.request_body_limit_bytes + 1)
                self.connection.settimeout(BODY_READ_TIMEOUT_SECONDS)
                return self.rfile.read(length)

            def _empty(self, status: HTTPStatus) -> None:
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True

        return Handler
