"""Drive an ASGI application in process, without a server and without a socket.

The distribution ships no ASGI server — `ADR 0004` forbids one and nothing in
this repository binds a port — so a suite that wants to exercise the API drives
it through the interface the application implements. This module is that driver,
and it is deliberately in ``tests/`` rather than in the distribution: it is a
harness, not a component, and it may never become the thing that runs the API.

**What a result from this client establishes, and what it does not.** It
establishes routing, request reading, validation, translation, the response
bodies, the status codes, the headers, and the lifecycle ordering — everything
the application decides. It establishes **nothing** about HTTP itself: no bytes
crossed a socket, no server parsed a request line, and no proxy, timeout, or
connection failure was involved. A result from here may not be cited as evidence
that this API answers a network request.

The client is minimal by design. It sends one body in one message unless asked to
split it, it collects the start and body messages, and it does not implement
trailers, early responses, or streamed responses — none of which this surface
produces.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, MutableMapping, Sequence
from dataclasses import dataclass, field
from typing import Any

Message = MutableMapping[str, Any]
Application = Callable[
    [
        MutableMapping[str, Any],
        Callable[[], Awaitable[Message]],
        Callable[[Message], Awaitable[None]],
    ],
    Awaitable[None],
]


@dataclass(frozen=True, slots=True)
class Response:
    """One response, as the application sent it."""

    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes

    def header(self, name: str) -> str | None:
        """One header by name, matched case-insensitively as HTTP requires."""
        wanted = name.lower()
        for key, value in self.headers:
            if key.lower() == wanted:
                return value
        return None

    def json(self) -> Any:
        """The body decoded as JSON. Raises if it is not JSON, which is the point."""
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        """The body decoded as UTF-8 text."""
        return self.body.decode("utf-8")


@dataclass
class LifespanResult:
    """What a lifespan cycle reported back."""

    messages: list[Message] = field(default_factory=list)

    @property
    def types(self) -> list[str]:
        return [str(message.get("type")) for message in self.messages]


async def request(
    application: Application,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: Sequence[tuple[str, str]] = (),
    body_chunks: Sequence[bytes] | None = None,
) -> Response:
    """Send one request through the application and collect the response.

    Args:
        application: The ASGI application to drive.
        method: The HTTP method, as a server would report it.
        path: The request path.
        body: The whole request body, sent in one message.
        headers: Request headers, encoded as a server would deliver them.
        body_chunks: An alternative to ``body``: several messages, so that a
            handler reading a body across messages is actually exercised.
    """
    chunks: list[bytes] = (
        list(body_chunks) if body_chunks is not None else [body or b""]
    )
    pending = list(chunks)

    async def receive() -> Message:
        if pending:
            chunk = pending.pop(0)
            return {"type": "http.request", "body": chunk, "more_body": bool(pending)}
        return {"type": "http.request", "body": b"", "more_body": False}

    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    scope: MutableMapping[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "scheme": "http",
        "headers": [
            (name.lower().encode("ascii"), value.encode("latin-1"))
            for name, value in headers
        ],
        "client": None,
        "server": None,
    }

    await application(scope, receive, send)

    start = next(m for m in sent if m.get("type") == "http.response.start")
    payload = b"".join(
        bytes(m.get("body") or b"")
        for m in sent
        if m.get("type") == "http.response.body"
    )
    return Response(
        status=int(start["status"]),
        headers=tuple(
            (bytes(key).decode("latin-1"), bytes(value).decode("latin-1"))
            for key, value in start.get("headers", [])
        ),
        body=payload,
    )


class LifespanSession:
    """The lifespan protocol run as a server runs it: a task, and two events.

    A server holds the lifespan call open for the life of the process and sends
    ``lifespan.startup`` and ``lifespan.shutdown`` into it. Driving it any other
    way — calling the application once per event — would let the application
    return between them, which is the one thing a lifespan call does not do. So
    this runs it as a task and feeds it through a queue.
    """

    def __init__(self, application: Application) -> None:
        self._application = application
        self._events: asyncio.Queue[Message] = asyncio.Queue()
        self._sent: list[Message] = []
        self._task: asyncio.Task[None] | None = None

    @property
    def result(self) -> LifespanResult:
        """Everything the application has sent on this lifespan call so far."""
        return LifespanResult(messages=list(self._sent))

    async def __aenter__(self) -> LifespanSession:
        self._task = asyncio.create_task(self._run())
        await self._events.put({"type": "lifespan.startup"})
        await self._await_message(
            {"lifespan.startup.complete", "lifespan.startup.failed"}
        )
        if "lifespan.startup.failed" in self.result.types and self._task is not None:
            # A server aborts on a failed startup rather than carrying on, and the
            # application re-raises after sending the message. Awaiting the task
            # here is what surfaces that to the caller instead of leaving it in a
            # task nobody retrieved.
            await self._task
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._events.put({"type": "lifespan.shutdown"})
        if self._task is not None:
            await self._task

    async def _run(self) -> None:
        async def receive() -> Message:
            return await self._events.get()

        async def send(message: Message) -> None:
            self._sent.append(message)

        scope: MutableMapping[str, Any] = {
            "type": "lifespan",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
        }
        await self._application(scope, receive, send)

    async def _await_message(self, wanted: set[str]) -> None:
        """Wait until the application has sent one of ``wanted``.

        A bounded wait, because a lifespan that never answers is a hang and a
        hang in a suite is a failure that reports nothing.
        """
        deadline = asyncio.get_running_loop().time() + 5.0
        while not any(str(m.get("type")) in wanted for m in self._sent):
            if self._task is not None and self._task.done():
                await self._task
                return
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(f"the application sent none of {sorted(wanted)}")
            await asyncio.sleep(0.001)
