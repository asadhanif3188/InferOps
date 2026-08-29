"""The InferOps API: five routes, one adapter, and a translation between them.

This is the composition point the architecture describes — "the place that
decides which adapter is live" — and the rule that goes with it is that it must
be small and it must be the only such place. It receives an adapter, it does not
construct one, and it has no default: a mock that could become the live adapter
by omission is the failure
[the mock and real boundary](../../../docs/serving/mock-and-real-boundary.md)
rule 5 forbids. Reading the selection out of configuration is
`V1-S1-005-PR2`'s; until then the only way to compose this API is to hand it the
adapter explicitly, in code a reader can see.

**It is an ASGI application and it imports no framework.** `ADR 0004` forbids an
HTTP framework anywhere in this distribution and
``tests/architecture/test_domain_dependency_boundary.py`` enforces it by reading
every module here, so this class implements the ASGI application interface
directly — a callable taking a scope, a receive, and a send — and nothing else.
That is the same answer the real adapter's transport gave to the same rule:
`ADR 0004` did not leave a framework-shaped hole, it decided there would not be
one. ASGI is a calling convention rather than a dependency, so the application
is written against it and any conforming server can run it. **This repository
ships no such server**, which is the honest limit of what this change built: the
application is exercised through its own interface, and no socket has been bound
by anything in this repository.

**The translation lives here and nowhere else.** `ADR 0010`'s first adapter
consequence is that the compatibility shape is admitted at the edge and the
adapter interface stays runtime-neutral. So a request in the borrowed shape is
read into a platform request by :mod:`inferops.api.validation`, the adapter is
called with a prompt and a :class:`~inferops.domain.context.RequestContext`, and
the domain result is written back into the borrowed shape by
:mod:`inferops.api.responses`. Nothing compatibility-shaped crosses into the
domain and nothing runtime-shaped crosses back out.

**Two identifiers reach the adapter on every call.** The request identifier and
the correlation identifier are validated or generated at this edge and travel in
the ``RequestContext`` the adapter receives, in the response headers, and in the
extension member of a completion body — which is what makes a refusal as
traceable as a success.

**Liveness and metrics answer while the API is draining; readiness does not.**
That is the graceful-shutdown equivalent the accepted record chose, and the
ordering is in :mod:`inferops.api.lifecycle` rather than here.
"""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from ..domain.context import RequestContext
from ..domain.serving import (
    ACCEPTED_ADAPTER_KINDS,
    AdapterConfiguration,
    CanonicalError,
    InternalError,
    InvalidValueError,
    ServingAdapter,
)
from . import identifiers, metrics
from .errors import (
    CAPABILITY_UNAVAILABLE,
    CONTRACT_INVALID,
    METHOD_NOT_ALLOWED_STATUS,
    NOT_FOUND_STATUS,
    RequestRefused,
    status_for,
)
from .lifecycle import (
    DEFAULT_DRAIN_TIMEOUT_MS,
    ApplicationLifecycle,
    ShuttingDown,
)
from .responses import (
    completion_body,
    error_body,
    live_body,
    models_body,
    ready_body,
)
from .surface import (
    CORRELATION_ID_HEADER,
    REQUEST_ID_HEADER,
    ROUTES,
)
from .validation import parse_chat_completion

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

#: The largest request body this API will read into memory before deciding
#: anything about it. A chat request bounded by a context length is orders of
#: magnitude smaller. It is a bound on what a caller can make this process
#: allocate, and it mirrors the response bound the runtime transport already
#: applies in the other direction.
MAX_REQUEST_BYTES = 1_048_576

JSON_CONTENT_TYPE = "application/json; charset=utf-8"

#: The message a caller is given when this API is no longer accepting work. It
#: names the state and nothing about the process, the host, or the deployment.
DRAINING_MESSAGE = "this deployment has stopped accepting new work"

#: The message a caller is given when a failure has no canonical mapping. It is a
#: constant rather than a formatted exception, because an exception's own text is
#: where a path, a host name, or a prompt fragment reaches a caller.
UNEXPECTED_FAILURE_MESSAGE = "the request could not be completed"

#: What a completion is refused with when the adapter's own result declares a
#: different adapter kind from the one this API was composed with. It is an
#: internal error rather than a warning: a response whose ``adapterKind`` cannot
#: be trusted is a response that cannot be used to claim anything, and the mock
#: and real boundary is the rule it would break.
ADAPTER_KIND_DISAGREEMENT = (
    "the serving adapter returned a result declaring a different adapter kind "
    "than this deployment was composed with"
)


@dataclass(frozen=True, slots=True)
class ApiConfiguration:
    """What this API needs to know that the adapter does not tell it.

    Attributes:
        adapter_kind: Which kind of adapter this deployment was composed with,
            from the domain's closed vocabulary. It is supplied at composition
            rather than read from the adapter because the protocol publishes no
            method for it — and it is checked against every result the adapter
            produces, so a deployment that labelled itself wrongly fails loudly
            instead of serving mislabelled responses.
        max_output_tokens: The ceiling a request's ``max_tokens`` may not exceed,
            or ``None`` when this deployment configures none. ``None`` is the
            accurate default: `ADR 0002` left the context length undecided and
            `ADR 0010` records the ceiling as depending on it, so there is no
            decided number to put here.
        drain_timeout_ms: The budget a graceful shutdown gives in-flight work.
    """

    adapter_kind: str
    max_output_tokens: int | None = None
    drain_timeout_ms: int = DEFAULT_DRAIN_TIMEOUT_MS

    def __post_init__(self) -> None:
        if self.adapter_kind not in ACCEPTED_ADAPTER_KINDS:
            raise InvalidValueError(
                f"adapter_kind must be one of {sorted(ACCEPTED_ADAPTER_KINDS)}"
            )
        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
            raise InvalidValueError("max_output_tokens must be positive")
        if self.drain_timeout_ms <= 0:
            raise InvalidValueError("drain_timeout_ms must be positive")


class InferOpsApi:
    """The ASGI application serving the accepted V1 inference API surface.

    Construct it with the adapter it should serve, the configuration that adapter
    is initialized with, and this API's own configuration. The adapter is
    initialized on lifespan startup and shut down after the drain on lifespan
    shutdown, so composing this object performs no I/O.
    """

    def __init__(
        self,
        *,
        adapter: ServingAdapter,
        adapter_configuration: AdapterConfiguration,
        configuration: ApiConfiguration,
        lifecycle: ApplicationLifecycle | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._adapter = adapter
        self._adapter_configuration = adapter_configuration
        self._configuration = configuration
        self._lifecycle = lifecycle or ApplicationLifecycle(
            drain_timeout_ms=configuration.drain_timeout_ms
        )
        self._clock = clock
        self._started_at = 0
        self._drained: bool | None = None

    @property
    def lifecycle(self) -> ApplicationLifecycle:
        """The lifecycle this API answers readiness from."""
        return self._lifecycle

    @property
    def drained_cleanly(self) -> bool | None:
        """Whether the last shutdown finished its in-flight work inside the budget.

        ``None`` until a shutdown has run. A truncated drain is recorded rather
        than logged and forgotten, because the requests it abandoned were real.
        """
        return self._drained

    # -- ASGI ---------------------------------------------------------------

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """The ASGI entry point: lifespan, HTTP, and a refusal for anything else."""
        kind = scope.get("type")
        if kind == "lifespan":
            await self._lifespan(receive, send)
            return
        if kind == "http":
            await self._http(scope, receive, send)
            return
        if kind == "websocket":
            # Streaming is declared unsupported and this surface has no socket
            # protocol. Closing is the conforming refusal.
            await send({"type": "websocket.close", "code": 1000})
            return
        raise NotImplementedError(f"unsupported ASGI scope type: {kind!r}")

    async def _lifespan(self, receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            kind = message.get("type")
            if kind == "lifespan.startup":
                try:
                    await self.startup()
                except Exception:
                    # The message carries no exception text. A startup failure's
                    # own words are where a model path or an endpoint reaches a
                    # server log that may be shipped anywhere.
                    await send(
                        {
                            "type": "lifespan.startup.failed",
                            "message": "the serving adapter did not initialize",
                        }
                    )
                    raise
                await send({"type": "lifespan.startup.complete"})
            elif kind == "lifespan.shutdown":
                await self.shutdown()
                await send({"type": "lifespan.shutdown.complete"})
                return

    # -- lifecycle ----------------------------------------------------------

    async def startup(self) -> None:
        """Initialize the adapter, then begin serving.

        The order matters: readiness cannot become true before the adapter has
        accepted its configuration, or this API would report itself ready on
        behalf of something that had refused to start.
        """
        context = self._new_context()
        await self._adapter.initialize(self._adapter_configuration, context)
        self._started_at = int(self._clock())
        self._lifecycle.begin_serving()

    async def shutdown(self) -> None:
        """Stop accepting work, drain what is in flight, then shut the adapter down.

        The adapter is shut down last. Releasing a backend while requests are
        still being answered through it would turn a graceful shutdown into a
        batch of internal errors.
        """
        self._drained = await self._lifecycle.drain()
        await self._adapter.shutdown(self._new_context())

    def _new_context(self) -> RequestContext:
        """A context for work this API initiates rather than receives."""
        return RequestContext(
            request_id=identifiers.generate(),
            correlation_id=identifiers.generate(),
        )

    # -- HTTP ---------------------------------------------------------------

    async def _http(self, scope: Scope, receive: Receive, send: Send) -> None:
        headers = _request_headers(scope)
        request_id = identifiers.accept_or_generate(headers.get(REQUEST_ID_HEADER))
        correlation_id = identifiers.accept_or_generate(
            headers.get(CORRELATION_ID_HEADER)
        )
        context = RequestContext(request_id=request_id, correlation_id=correlation_id)
        answer = _Answer(request_id=request_id, correlation_id=correlation_id)

        method = str(scope.get("method", ""))
        path = str(scope.get("path", ""))

        matched = [route for route in ROUTES if route.path == path]
        if not matched:
            await answer.refuse(
                send,
                NOT_FOUND_STATUS,
                CONTRACT_INVALID,
                "path: this path is not part of the API surface this deployment serves",
            )
            return
        allowed = sorted({route.method for route in matched})
        route = next((row for row in matched if row.method == method), None)
        if route is None:
            await answer.refuse(
                send,
                METHOD_NOT_ALLOWED_STATUS,
                CONTRACT_INVALID,
                "method: this method is not served on this path",
                headers=[(b"allow", ", ".join(allowed).encode("ascii"))],
            )
            return

        if route.endpoint_id == "health-live":
            await answer.send_json(send, HTTPStatus.OK, live_body())
        elif route.endpoint_id == "metrics":
            await answer.send_text(
                send,
                HTTPStatus.OK,
                metrics.exposition(),
                metrics.EXPOSITION_CONTENT_TYPE,
            )
        elif route.endpoint_id == "health-ready":
            await self._ready(send, answer, context)
        elif route.endpoint_id == "models-list":
            await self._models(send, answer, context)
        else:
            await self._completion(scope, receive, send, answer, context)

    async def _ready(
        self, send: Send, answer: _Answer, context: RequestContext
    ) -> None:
        """Readiness: this API willing, and the selected adapter able.

        Both halves have to be yes. An adapter that raises while being asked is
        not ready — the question was whether it can serve, and a backend that
        cannot answer it has answered it.
        """
        ready = self._lifecycle.is_accepting_work
        if ready:
            try:
                ready = await self._adapter.is_ready(context)
            except Exception:
                ready = False
        body = ready_body(
            ready=ready,
            adapter_kind=self._configuration.adapter_kind,
            lifecycle_state=str(self._lifecycle.state),
        )
        status = HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE
        await answer.send_json(send, status, body)

    async def _models(
        self, send: Send, answer: _Answer, context: RequestContext
    ) -> None:
        try:
            with self._lifecycle.accept():
                model = await self._adapter.get_model_metadata()
                runtime = await self._adapter.get_runtime_metadata()
                capabilities = await self._adapter.get_capabilities()
        except ShuttingDown:
            await answer.refuse(
                send,
                HTTPStatus.SERVICE_UNAVAILABLE,
                CAPABILITY_UNAVAILABLE,
                DRAINING_MESSAGE,
            )
            return
        except CanonicalError as error:
            await answer.refuse(send, status_for(error), error.code, error.message)
            return
        except Exception:
            await answer.refuse(
                send,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                InternalError().code,
                UNEXPECTED_FAILURE_MESSAGE,
            )
            return
        await answer.send_json(
            send,
            HTTPStatus.OK,
            models_body(
                model,
                runtime,
                capabilities,
                adapter_kind=self._configuration.adapter_kind,
                created=self._started_at,
            ),
        )

    async def _completion(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        answer: _Answer,
        context: RequestContext,
    ) -> None:
        try:
            with self._lifecycle.accept():
                body = await self._serve_completion(scope, receive, answer, context)
        except ShuttingDown:
            await answer.refuse(
                send,
                HTTPStatus.SERVICE_UNAVAILABLE,
                CAPABILITY_UNAVAILABLE,
                DRAINING_MESSAGE,
            )
            return
        except RequestRefused as refusal:
            await answer.refuse(send, refusal.status, refusal.code, refusal.message)
            return
        except CanonicalError as error:
            await answer.refuse(send, status_for(error), error.code, error.message)
            return
        except Exception:
            await answer.refuse(
                send,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                InternalError().code,
                UNEXPECTED_FAILURE_MESSAGE,
            )
            return
        await answer.send_json(send, HTTPStatus.OK, body)

    async def _serve_completion(
        self,
        scope: Scope,
        receive: Receive,
        answer: _Answer,
        context: RequestContext,
    ) -> dict[str, object]:
        raw = await _read_body(receive)
        model = await self._adapter.get_model_metadata()
        request = parse_chat_completion(
            raw,
            served_model=model.identifier,
            max_tokens_ceiling=self._configuration.max_output_tokens,
        )
        result = await self._adapter.infer(request.prompt, context)
        if result.adapter_kind != self._configuration.adapter_kind:
            raise InternalError(ADAPTER_KIND_DISAGREEMENT, context=context)
        return completion_body(
            result,
            completion_id=identifiers.completion_id(),
            created=int(self._clock()),
            request_id=answer.request_id,
            correlation_id=answer.correlation_id,
        )


@dataclass(frozen=True, slots=True)
class _Answer:
    """The identifiers every response to one request carries, and how it is sent.

    It exists so that no response path can forget the two headers: an error sent
    without them is a refusal a caller cannot correlate, which is the failure
    that makes a canonical error worth less than the log line it replaced.
    """

    request_id: str
    correlation_id: str

    def _headers(self, content_type: str) -> list[tuple[bytes, bytes]]:
        return [
            (b"content-type", content_type.encode("ascii")),
            (
                REQUEST_ID_HEADER.lower().encode("ascii"),
                self.request_id.encode("ascii"),
            ),
            (
                CORRELATION_ID_HEADER.lower().encode("ascii"),
                self.correlation_id.encode("ascii"),
            ),
        ]

    async def send_json(self, send: Send, status: HTTPStatus, body: object) -> None:
        await self._send(
            send,
            status,
            json.dumps(body, separators=(",", ":")).encode("utf-8"),
            JSON_CONTENT_TYPE,
        )

    async def send_text(
        self, send: Send, status: HTTPStatus, body: str, content_type: str
    ) -> None:
        await self._send(send, status, body.encode("utf-8"), content_type)

    async def refuse(
        self,
        send: Send,
        status: HTTPStatus,
        code: str,
        message: str,
        *,
        headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        body = error_body(
            code,
            message,
            request_id=self.request_id,
            correlation_id=self.correlation_id,
        )
        await self._send(
            send,
            status,
            json.dumps(body, separators=(",", ":")).encode("utf-8"),
            JSON_CONTENT_TYPE,
            extra=headers,
        )

    async def _send(
        self,
        send: Send,
        status: HTTPStatus,
        payload: bytes,
        content_type: str,
        *,
        extra: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": int(status),
                "headers": self._headers(content_type) + list(extra or []),
            }
        )
        await send({"type": "http.response.body", "body": payload})


def _request_headers(scope: Scope) -> dict[str, str]:
    """The request headers, keyed by their canonical spelling.

    HTTP header names are case-insensitive and ASGI delivers them lower-cased, so
    they are matched lower-cased and returned under the spelling the accepted
    surface publishes.
    """
    raw = scope.get("headers") or []
    found: dict[str, str] = {}
    for name in (REQUEST_ID_HEADER, CORRELATION_ID_HEADER):
        wanted = name.lower().encode("ascii")
        for key, value in raw:
            if bytes(key).lower() == wanted:
                found[name] = bytes(value).decode("latin-1")
                break
    return found


async def _read_body(receive: Receive) -> bytes:
    """Read the request body under a bound, refusing anything larger.

    The bound is a robustness property rather than a protocol constraint: without
    one, how much this process allocates is a decision the caller makes.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        message = await receive()
        if message.get("type") == "http.disconnect":
            raise RequestRefused(
                CONTRACT_INVALID, "body", "the caller disconnected before sending one"
            )
        chunk = bytes(message.get("body") or b"")
        total += len(chunk)
        if total > MAX_REQUEST_BYTES:
            raise RequestRefused(
                CONTRACT_INVALID,
                "body",
                f"the request body exceeds this deployment's bound of "
                f"{MAX_REQUEST_BYTES} bytes",
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        chunks.append(chunk)
        if not message.get("more_body"):
            return b"".join(chunks)
