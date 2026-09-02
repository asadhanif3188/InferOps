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

**The inference endpoint is instrumented; the other four are not.** A request to
``/v1/chat/completions`` that reached a matched route is counted in flight,
timed, and closed with an outcome, and one structured record is written when it
arrives and one when it closes. Liveness, readiness, the model list, and the
metrics scrape are deliberately outside that: they are not inference requests,
and counting a readiness probe in the same counter would make the success rate a
figure about a probe loop. What readiness contributes instead is
``inferops_readiness_check_failures_total``, which names the half that said no.
The instruments themselves are in :mod:`inferops.api.observability`, and the
names they use are the accepted catalog's.
"""

from __future__ import annotations

import json
import re
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
    InvalidValueError,
    ServingAdapter,
)
from ..telemetry import names as telemetry_names
from ..telemetry.registry import EXPOSITION_CONTENT_TYPE
from ..telemetry.resource import ResourceAttributes
from . import identifiers
from .errors import (
    ADAPTER_KIND_DISAGREEMENT,
    ADAPTER_KIND_DISAGREES,
    DEPLOYMENT_DRAINING,
    METHOD_NOT_SERVED,
    PATH_NOT_SERVED,
    REQUEST_OUTSIDE_SUBSET,
    REQUEST_TOO_LARGE,
    UNEXPECTED_FAILURE,
    UNSUPPORTED_CONTRACT_VERSION,
    Condition,
    RequestRefused,
    condition_for,
)
from .lifecycle import (
    DEFAULT_DRAIN_TIMEOUT_MS,
    ApplicationLifecycle,
    ShuttingDown,
)
from .observability import ApiTelemetry, outcome_for
from .responses import (
    completion_body,
    error_body,
    live_body,
    models_body,
    ready_body,
)
from .surface import (
    CORRELATION_ID_HEADER,
    PATH_PREFIX,
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

#: The path segment that names a version in the compatibility target's shape.
#: A first segment matching this pattern and naming a version other than the one
#: :data:`~inferops.api.surface.PATH_PREFIX` publishes is what makes
#: ``version-unsupported`` reachable: it is the one place a caller can name an
#: API version, because this surface reads no version header and defines no
#: request-body extension member a caller could put one in.
VERSION_SEGMENT = re.compile(r"^v[0-9]+$")


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
        drain_timeout_ms: The budget a graceful shutdown gives in-flight work.
    """

    adapter_kind: str
    drain_timeout_ms: int = DEFAULT_DRAIN_TIMEOUT_MS

    def __post_init__(self) -> None:
        if self.adapter_kind not in ACCEPTED_ADAPTER_KINDS:
            raise InvalidValueError(
                f"adapter_kind must be one of {sorted(ACCEPTED_ADAPTER_KINDS)}"
            )
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
        monotonic: Callable[[], float] = time.monotonic,
        telemetry: ApiTelemetry | None = None,
    ) -> None:
        self._adapter = adapter
        self._adapter_configuration = adapter_configuration
        self._configuration = configuration
        self._lifecycle = lifecycle or ApplicationLifecycle(
            drain_timeout_ms=configuration.drain_timeout_ms
        )
        self._clock = clock
        # Durations are measured on a monotonic clock and timestamps are written
        # from a wall clock, because they answer different questions and one
        # clock cannot answer both: a wall clock that steps backwards turns a
        # latency observation into a negative number.
        self._monotonic = monotonic
        self._telemetry = telemetry or ApiTelemetry(
            resource=ResourceAttributes(adapter_kind=configuration.adapter_kind),
            clock=clock,
        )
        self._started_at = 0
        self._drained: bool | None = None

    @property
    def lifecycle(self) -> ApplicationLifecycle:
        """The lifecycle this API answers readiness from."""
        return self._lifecycle

    @property
    def telemetry(self) -> ApiTelemetry:
        """The instruments and records this deployment emits."""
        return self._telemetry

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
        await self._bind_telemetry_identity()
        self._lifecycle.begin_serving()
        self._telemetry.deployment_event(
            telemetry_names.EVENT_DEPLOYMENT_STARTED,
            correlation_id=context.correlation_id or identifiers.generate(),
        )

    async def _bind_telemetry_identity(self) -> None:
        """Record the model and runtime the adapter reported, for the identity metric.

        It is asked of the adapter rather than configured, because the adapter is
        looking at the artifact and a variable beside it is only describing one.
        A failure here leaves the identity labels empty and does **not** fail
        startup: telemetry that could refuse to serve would be telemetry that
        decides availability, and an empty identity label is visibly empty.
        """
        try:
            model = await self._adapter.get_model_metadata()
            runtime = await self._adapter.get_runtime_metadata()
        except Exception:
            return
        self._telemetry.bind_identity(
            model_id=model.identifier,
            model_revision=model.revision,
            runtime_id=runtime.identifier or runtime.name,
        )

    async def shutdown(self) -> None:
        """Stop accepting work, drain what is in flight, then shut the adapter down.

        The adapter is shut down last. Releasing a backend while requests are
        still being answered through it would turn a graceful shutdown into a
        batch of internal errors.
        """
        correlation_id = identifiers.generate()
        self._telemetry.deployment_event(
            telemetry_names.EVENT_DEPLOYMENT_DRAINING, correlation_id=correlation_id
        )
        self._drained = await self._lifecycle.drain()
        await self._adapter.shutdown(self._new_context())
        self._telemetry.deployment_event(
            telemetry_names.EVENT_DEPLOYMENT_STOPPED, correlation_id=correlation_id
        )

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
        answer = _Answer(
            request_id=request_id,
            correlation_id=correlation_id,
            adapter_kind=self._configuration.adapter_kind,
        )

        method = str(scope.get("method", ""))
        path = str(scope.get("path", ""))

        matched = [route for route in ROUTES if route.path == path]
        if not matched:
            if _names_another_version(path):
                # The caller named an API version this deployment does not serve.
                # It is a different refusal from a path nobody publishes, and it
                # is the one the accepted record has a code for.
                await answer.refuse(send, UNSUPPORTED_CONTRACT_VERSION, member="path")
                return
            await answer.refuse(send, PATH_NOT_SERVED, member="path")
            return
        allowed = sorted({route.method for route in matched})
        route = next((row for row in matched if row.method == method), None)
        if route is None:
            await answer.refuse(
                send,
                METHOD_NOT_SERVED,
                member="method",
                headers=[(b"allow", ", ".join(allowed).encode("ascii"))],
            )
            return

        if route.endpoint_id == "health-live":
            await answer.send_json(send, HTTPStatus.OK, live_body())
        elif route.endpoint_id == "metrics":
            await answer.send_text(
                send,
                HTTPStatus.OK,
                self._telemetry.exposition(),
                EXPOSITION_CONTENT_TYPE,
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
        failed_component = telemetry_names.COMPONENT_API if not ready else None
        if ready:
            try:
                ready = await self._adapter.is_ready(context)
            except Exception:
                ready = False
            if not ready:
                failed_component = telemetry_names.COMPONENT_ADAPTER
        if failed_component is not None:
            self._telemetry.readiness_failed(
                correlation_id=answer.correlation_id, component=failed_component
            )
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
                await self._answer_models(send, answer)
        except ShuttingDown:
            await self._refuse_draining(send, answer)

    async def _answer_models(self, send: Send, answer: _Answer) -> None:
        """Answer inside the accepted slot, so the drain waits for the response.

        The send is inside :meth:`ApplicationLifecycle.accept` rather than after
        it. Releasing the slot first would let a drain report itself finished
        while a response it is responsible for had not been handed to the server,
        which is the one thing the drain exists to prevent.
        """
        try:
            model = await self._adapter.get_model_metadata()
            runtime = await self._adapter.get_runtime_metadata()
            capabilities = await self._adapter.get_capabilities()
        except CanonicalError as error:
            await answer.refuse(send, condition_for(error))
            return
        except Exception:
            await answer.refuse(send, UNEXPECTED_FAILURE)
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
        """Serve one inference request, counted in flight and closed with an outcome.

        The close is in a ``finally`` on purpose. Every refusal this endpoint can
        produce is a request that arrived, and a counter that only counts the
        paths somebody remembered is a success rate that flatters the platform.

        The **open** is inside that same ``try``, which is the less obvious half.
        The in-flight gauge is a pair of a raise and a lower, and a raise that can
        throw before the ``try`` begins is a pair that can be left half-applied --
        permanently, because nothing else ever lowers that series again. A gauge
        that only climbs is a saturation signal that reads as saturation forever,
        which is worse than no gauge in exactly the incident it exists for.
        """
        started = self._monotonic()
        try:
            self._telemetry.request_started(
                correlation_id=answer.correlation_id, request_id=answer.request_id
            )
            try:
                with self._lifecycle.accept():
                    await self._answer_completion(scope, receive, send, answer, context)
            except ShuttingDown:
                await self._refuse_draining(send, answer)
        finally:
            self._telemetry.request_closed(
                correlation_id=answer.correlation_id,
                request_id=answer.request_id,
                outcome=outcome_for(answer.condition, answer.status),
                duration_seconds=max(self._monotonic() - started, 0.0),
                http_status=answer.status,
                error_code=None if answer.condition is None else answer.condition.code,
                finish_reason=answer.finish_reason,
                input_tokens=answer.input_tokens,
                output_tokens=answer.output_tokens,
            )

    async def _refuse_draining(self, send: Send, answer: _Answer) -> None:
        """The one refusal that knows its own retry delay.

        A deployment that has begun draining will be gone when its drain budget
        runs out, and that budget is configured rather than guessed — so it is
        the one condition where ``retryAfterMs`` is a decided number instead of
        an invented one.
        """
        await answer.refuse(
            send,
            DEPLOYMENT_DRAINING,
            retry_after_ms=self._configuration.drain_timeout_ms,
        )

    async def _answer_completion(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        answer: _Answer,
        context: RequestContext,
    ) -> None:
        """Answer inside the accepted slot, so the drain waits for the response.

        As in :meth:`_answer_models`, the send happens while the request is still
        counted. A drain that returned between the adapter answering and the
        response being handed to the server would report a clean shutdown over a
        request nobody received.
        """
        try:
            body = await self._serve_completion(scope, receive, answer, context)
        except RequestRefused as refusal:
            await answer.refuse(
                send,
                refusal.condition,
                message=refusal.message,
                member=refusal.member,
            )
            return
        except CanonicalError as error:
            # The adapter's own message stops here. What a caller is told is this
            # API's message for the condition, so a runtime's words, a path, or a
            # prompt fragment inside an adapter's message cannot reach a response
            # by being forwarded.
            await answer.refuse(send, condition_for(error))
            return
        except Exception:
            await answer.refuse(send, UNEXPECTED_FAILURE)
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
        )
        result = await self._adapter.infer(request.prompt, context)
        if result.adapter_kind != self._configuration.adapter_kind:
            raise RequestRefused(
                ADAPTER_KIND_DISAGREES, None, ADAPTER_KIND_DISAGREEMENT
            )
        # What the adapter reported about the work, for the token counter and the
        # closing record. Both are absent rather than estimated when the adapter
        # reported none, and neither is content: a finish reason is why generation
        # stopped and a token count is how many there were.
        answer.observe_result(
            finish_reason=result.finish_reason,
            input_tokens=None if result.usage is None else result.usage.input_tokens,
            output_tokens=None if result.usage is None else result.usage.output_tokens,
        )
        return completion_body(
            result,
            completion_id=identifiers.completion_id(),
            created=int(self._clock()),
            request_id=answer.request_id,
            correlation_id=answer.correlation_id,
        )


@dataclass(slots=True)
class _Answer:
    """The identifiers every response to one request carries, and how it is sent.

    It exists so that no response path can forget the two headers: an error sent
    without them is a refusal a caller cannot correlate, which is the failure
    that makes a canonical error worth less than the log line it replaced. It
    carries the adapter kind for the same reason — every response names the kind
    behind it, and a refusal is a response.

    It also **records what it sent**, which is why it is not frozen. The
    instrumented request path needs the status, the condition, and what the
    adapter reported about the work, and reading them off the object that sent
    the response is the only way that cannot disagree with the response — a
    second place to decide the outcome is a second place to get it wrong.

    Attributes:
        status: The HTTP status that was sent, or ``None`` if nothing was.
        condition: The condition a refusal named, or ``None`` on a success.
        finish_reason: Why generation stopped, when the adapter reported one.
        input_tokens: Tokens read, when the adapter reported a count.
        output_tokens: Tokens written, when the adapter reported a count.
    """

    request_id: str
    correlation_id: str
    adapter_kind: str
    status: int | None = None
    condition: Condition | None = None
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    def observe_result(
        self,
        *,
        finish_reason: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> None:
        """Record what the adapter reported about the work it did."""
        self.finish_reason = finish_reason
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

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
        condition: Condition,
        *,
        message: str | None = None,
        member: str | None = None,
        retry_after_ms: int | None = None,
        headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        """One refusal, in the canonical error body.

        The condition decides the code, the ``retryable`` flag, and the status
        together, so no refusal site can combine three values nobody decided.
        ``message`` is supplied only where this API has something more specific
        to say than the condition's own text — which is the validation refusals,
        and nothing that came from below this edge.
        """
        body = error_body(
            condition,
            condition.message if message is None else message,
            request_id=self.request_id,
            correlation_id=self.correlation_id,
            adapter_kind=self.adapter_kind,
            member=member,
            retry_after_ms=retry_after_ms,
        )
        self.condition = condition
        await self._send(
            send,
            condition.status,
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
        self.status = int(status)
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
                REQUEST_OUTSIDE_SUBSET,
                "body",
                "the caller disconnected before sending one",
            )
        chunk = bytes(message.get("body") or b"")
        total += len(chunk)
        if total > MAX_REQUEST_BYTES:
            raise RequestRefused(
                REQUEST_TOO_LARGE,
                "body",
                f"the request body exceeds this deployment's bound of "
                f"{MAX_REQUEST_BYTES} bytes",
            )
        chunks.append(chunk)
        if not message.get("more_body"):
            return b"".join(chunks)


def _names_another_version(path: str) -> bool:
    """Whether a path's first segment names an API version this API does not serve.

    ``/v2/chat/completions`` is a caller asking for a version of the borrowed
    shape this deployment does not serve, which the accepted record has a code
    for. ``/healthz`` is a path nobody publishes, which it does not. Telling the
    two apart is the whole reason this function exists, and it is the only place
    a caller can name a version: this surface reads no version header and the
    accepted record defines no request-body extension member.
    """
    first = path.lstrip("/").split("/", 1)[0]
    return VERSION_SEGMENT.match(first) is not None and f"/{first}" != PATH_PREFIX
