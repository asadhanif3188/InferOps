"""The serving adapter for the selected runtime. It generates text, or it fails.

`V1-S1-004-PR1` deliberately shipped no class satisfying
:class:`~inferops.domain.serving.ServingAdapter`, on the ground that a class whose
``infer`` could not generate anything would be a mock wearing a real adapter's
name. This module is the other half: it composes the pins, settings,
configuration translation, readiness mapping, metadata parsers, and capability
declaration that package already holds, adds a transport seam and an inference
client, and implements the protocol for real.

**What it does not do is claim anything.** This module executing a completion is
what makes a real-runtime record *possible*; it is not itself that record. Every
check in the default lane runs it against a controlled transport, which exercises
the adapter and says nothing whatsoever about a runtime — the distinction
[the mock and real boundary](../../../../docs/serving/mock-and-real-boundary.md)
exists to keep visible. The record that does claim something is produced by the
`real-runtime` lane, which is manual and authorization-gated.

Four behaviours are decisions rather than details.

**Readiness gates inference, and a probe is what lifts the gate.** A tracker that
has observed nothing refuses a request and probes, rather than optimistically
sending one. `ADR 0002` records a load window of up to 14 s during which the
process is up and answers 503, so "the socket is open" and "the model can answer"
are different facts and the adapter is not permitted to conflate them.

**Two deadlines, not one.** The transport is given the configured budget and the
call is wrapped in an outer deadline of the same length. The inner one produces
``upstream-timeout`` — the runtime ran out of time — and the outer produces
``request-timeout``, and the outer exists because a transport is a value a caller
supplies and a protocol cannot enforce the promise it asks for. A transport that
ignores its budget stalls one request rather than the process.

**The prompt is never stored, logged, echoed, or attached to an error.** It is
built into one request body, sent, and forgotten. That is the redaction rule from
[the telemetry catalog](../../../../docs/telemetry/redaction.md) holding at the
place a prompt actually enters this distribution.

**Shutdown stops the adapter answering and forgets what it observed.** A tracker
that survived shutdown would describe a process that is gone.
"""

from __future__ import annotations

import asyncio

from ...domain.context import NO_REQUEST_CONTEXT, RequestContext
from ...domain.serving import (
    AdapterCapability,
    AdapterConfiguration,
    CanonicalError,
    InferenceResult,
    InternalError,
    ModelMetadata,
    ModelNotReadyError,
    RuntimeMetadata,
    ServingAdapter,
    TelemetryMapping,
)
from .capabilities import LLAMA_SERVER_CAPABILITIES
from .configuration import LlamaServerConfiguration, translate
from .inference import (
    build_request,
    error_for_status,
    error_for_transport_failure,
    normalize_response,
    request_deadline_error,
    unreachable_error,
)
from .metadata import (
    ObservedRuntimeIdentity,
    describe_model,
    describe_runtime,
    identity_disagreements,
    observe,
)
from .pins import LLAMA_SERVER_ADAPTER_KIND
from .readiness import (
    ReadinessState,
    ReadinessTracker,
    readiness_error,
)
from .settings import (
    CHAT_COMPLETIONS_PATH,
    HEALTH_PATH,
    MODELS_PATH,
    PROPS_PATH,
    LlamaServerSettings,
)
from .transport import RuntimeResponse, RuntimeTransport, TransportError

#: The message an uninitialized adapter refuses a request with.
NOT_INITIALIZED_MESSAGE = "the adapter has not been initialized"

#: The message a shut-down adapter refuses a request with.
SHUT_DOWN_MESSAGE = "the adapter has been shut down"

#: Reason codes for a runtime that answered a completion under a different model
#: identity than it was configured with. Recorded on the adapter and readable by
#: a caller; not raised, because a mismatch is a fact about the deployment rather
#: than a fault in the request that discovered it.
COMPLETION_ALIAS_DISAGREEMENT = "completion-model-differs-from-configured-alias"


class LlamaServerAdapter:
    """A :class:`~inferops.domain.serving.ServingAdapter` over `llama-server`.

    Construct it with the operator's settings and a transport. The transport is a
    parameter rather than something this class builds, so that composing an
    adapter is where the decision to open sockets is made, and so a suite can
    exercise every branch here against controlled responses without intercepting
    the standard library.

    An instance is not safe to share across event loops, which is the caveat the
    mock adapter states for itself and which this one inherits rather than
    escapes.
    """

    def __init__(
        self,
        settings: LlamaServerSettings,
        transport: RuntimeTransport,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._configuration: LlamaServerConfiguration | None = None
        self._readiness = ReadinessTracker()
        self._observed = ObservedRuntimeIdentity()
        self._is_shut_down = False
        self._disagreements: tuple[str, ...] = ()

    # -- what the instance holds, which is not part of the contract ------

    @property
    def settings(self) -> LlamaServerSettings:
        """The runtime settings this instance was constructed with."""
        return self._settings

    @property
    def readiness_state(self) -> ReadinessState:
        """The last readiness observation, in the runtime package's vocabulary."""
        return self._readiness.state

    @property
    def observed_identity(self) -> ObservedRuntimeIdentity:
        """What the runtime last said about itself. Absent until asked."""
        return self._observed

    @property
    def disagreements(self) -> tuple[str, ...]:
        """Reason codes for every way the runtime last disagreed with its
        configuration.

        Empty until something has been observed, which is not the same as
        agreement and is why :meth:`observe_identity` exists as a separate call.
        """
        return self._disagreements

    # -- the contract ----------------------------------------------------

    async def initialize(
        self,
        config: AdapterConfiguration,
        context: RequestContext,
    ) -> None:
        """Join the platform configuration to the settings and the pins.

        Nothing is contacted. Initialization validates a pair of configurations
        against each other and against the accepted decision, and a runtime that
        is not up yet is a readiness question rather than an initialization
        failure — which is what lets a platform start before its runtime has
        finished loading.

        Raises:
            InvalidAdapterConfigError: If the platform identity is mock-labelled,
                if the generation bound exceeds the configured context length, or
                if the settings name a weight file the accepted decision does not
                pin.
        """
        self._configuration = translate(config, self._settings, context=context)
        self._readiness.reset()
        self._observed = ObservedRuntimeIdentity()
        self._disagreements = ()
        self._is_shut_down = False

    async def get_capabilities(self) -> list[AdapterCapability]:
        """Declare what this runtime supports, with the basis recorded beside it.

        The declaration is static and lives in
        :mod:`~inferops.adapters.llama_cpp.capabilities`, where each entry cites
        the record that observed the behaviour. Nothing an operator configures
        changes it.
        """
        return list(LLAMA_SERVER_CAPABILITIES)

    async def is_ready(self, context: RequestContext) -> bool:
        """Probe the runtime's health endpoint and report what it said.

        Returns ``False`` rather than raising when the runtime cannot be reached:
        *unreachable* is an answer to the readiness question, and a probe that
        raised would make an ordinary not-ready state look like a fault in the
        platform.
        """
        if self._configuration is None or self._is_shut_down:
            return False
        try:
            response = await self._get(HEALTH_PATH, self._timeout_seconds())
        except (TransportError, TimeoutError):
            self._readiness.observe_unreachable()
            return False
        self._readiness.observe_health_status(response.status_code)
        return self._readiness.ready

    async def infer(
        self,
        prompt: str,
        context: RequestContext,
    ) -> InferenceResult:
        """Generate one completion through the runtime, or fail canonically.

        Raises:
            ModelNotReadyError: If the adapter is not initialized, is shut down,
                or the runtime is loading or has not been probed successfully.
            CapabilityUnavailableError: If the runtime cannot be reached.
            UpstreamTimeoutError: If the runtime did not answer within the
                configured budget.
            RequestTimeoutError: If this adapter's own outer deadline elapsed.
            InternalError: If the runtime answered with an unexpected status or
                with a body this adapter cannot read.
        """
        configuration = self._require_live(context)
        await self._require_ready(context)
        body = build_request(configuration.adapter, self._settings, prompt)
        response = await self._post(CHAT_COMPLETIONS_PATH, body, context)
        failure = error_for_status(response.status_code, context)
        if failure is not None:
            if isinstance(failure, ModelNotReadyError):
                # The runtime answered the loading status to a completion. The
                # tracker learns it here rather than waiting for the next probe.
                self._readiness.observe_health_status(response.status_code)
            raise failure
        completion = normalize_response(response.body, context=context)
        self._record_completion_identity(completion.reported_model)
        return InferenceResult(
            content=completion.content,
            model=configuration.platform_model_identifier,
            adapter_kind=LLAMA_SERVER_ADAPTER_KIND,
            usage=completion.usage,
            finish_reason=completion.finish_reason,
        )

    async def get_model_metadata(self) -> ModelMetadata:
        """The identity the platform configured, and the revision the pins hold.

        The revision is *configured*, not attested. The runtime exposes no hash of
        the file it loaded and echoes only the alias it was started with, so
        reporting an observed revision would be reporting something nobody
        observed.
        """
        if self._configuration is None:
            raise InternalError(NOT_INITIALIZED_MESSAGE)
        return describe_model(self._configuration.platform_model_identifier)

    async def get_runtime_metadata(self) -> RuntimeMetadata:
        """The selected runtime's name, and the best version identifier held.

        The build string when the process has reported one through ``/props``, and
        the pinned image digest otherwise. Both identify real bytes; neither is
        invented.
        """
        return describe_runtime(self._observed)

    async def shutdown(self, context: RequestContext) -> None:
        """Stop answering, forget every observation, and release the transport.

        Shutdown does not fail on a transport that refuses to close. The adapter
        has already stopped accepting work by the time the transport is asked,
        and raising here would turn a clean stop into a failed one over a resource
        the process is about to drop anyway.
        """
        self._is_shut_down = True
        self._readiness.reset()
        self._observed = ObservedRuntimeIdentity()
        self._disagreements = ()
        try:
            await self._transport.close()
        except TransportError:
            return None

    async def map_error_to_canonical(
        self,
        error: Exception,
        context: RequestContext | None = None,
    ) -> CanonicalError:
        """Return a canonical error unchanged; translate a transport failure;
        map anything else to ``internal-error``.

        An unrecognised error's own message is dropped rather than wrapped, for
        the reason the mock adapter gives for the same choice: a runtime message
        is where a path, a host name, or a credential arrives in a response, and
        this adapter cannot tell which message is which.
        """
        resolved = context if context is not None else NO_REQUEST_CONTEXT
        if isinstance(error, CanonicalError):
            return error
        if isinstance(error, TransportError):
            return error_for_transport_failure(error, resolved)
        return InternalError(context=resolved)

    async def get_telemetry_mapping(self) -> TelemetryMapping:
        """Map this adapter's state onto platform telemetry.

        It reports no metric of its own. `ADR 0002`'s `T7` failed on exactly this:
        the runtime exposes two gauges of instantaneous state and no cumulative
        request counter, so InferOps counts the requests it receives and the
        adapter claims none of it. Token usage is ``True`` because the runtime
        derives counts from its own tokeniser and returns them — a supported
        capability with a record behind it, unlike the mock's, which is ``False``
        because inventing one is the alternative.
        """
        return TelemetryMapping(
            platform_metric_ids=(),
            error_code=None,
            token_usage=True,
        )

    # -- inspection beyond the contract ----------------------------------

    async def observe_identity(
        self, context: RequestContext
    ) -> ObservedRuntimeIdentity:
        """Ask the runtime what it is, and record any disagreement.

        Reads ``/v1/models`` and ``/props``. Neither is required for inference and
        neither is called on the request path: identity is an operational
        question, and paying two round trips per completion to re-answer it would
        be charging every caller for it.

        Raises:
            ModelNotReadyError: If the adapter is not initialized or shut down.
            CapabilityUnavailableError: If the runtime cannot be reached.
            UpstreamTimeoutError: If the runtime did not answer in time.
            InternalError: If either response cannot be read.
        """
        configuration = self._require_live(context)
        models = await self._read_json(MODELS_PATH, context)
        props = await self._read_json(PROPS_PATH, context)
        self._observed = observe(models_payload=models, props_payload=props)
        self._disagreements = identity_disagreements(
            self._observed,
            configured_alias=configuration.runtime_model_alias,
            configured_model_file=self._settings.model_file,
        )
        return self._observed

    # -- internals -------------------------------------------------------

    def _require_live(self, context: RequestContext) -> LlamaServerConfiguration:
        """The configuration, or the canonical refusal of an adapter that has none."""
        if self._configuration is None:
            raise ModelNotReadyError(NOT_INITIALIZED_MESSAGE, context=context)
        if self._is_shut_down:
            raise ModelNotReadyError(SHUT_DOWN_MESSAGE, context=context)
        return self._configuration

    async def _require_ready(self, context: RequestContext) -> None:
        """Refuse unless the runtime last said it can accept requests.

        A tracker that has observed nothing probes once here. That is the only
        place readiness is obtained implicitly, and it exists so that a caller's
        first request does not have to be preceded by a readiness call the
        protocol never told it to make.
        """
        if self._readiness.state is ReadinessState.NOT_PROBED:
            await self.is_ready(context)
        if self._readiness.ready:
            return
        if self._readiness.state is ReadinessState.UNREACHABLE:
            raise unreachable_error(context)
        refusal = readiness_error(self._readiness.state, context)
        if refusal is not None:
            raise refusal

    def _record_completion_identity(self, reported_model: str | None) -> None:
        """Record whether the completion named the alias the runtime was given.

        Not raised on. A completion that arrived under a different alias is a
        deployment fact an operator needs to see, and failing the request that
        discovered it would hide the fact behind an error nobody could explain.
        """
        if reported_model is None:
            return
        if reported_model == self._settings.model_alias:
            self._disagreements = tuple(
                reason
                for reason in self._disagreements
                if reason != COMPLETION_ALIAS_DISAGREEMENT
            )
            return
        if COMPLETION_ALIAS_DISAGREEMENT not in self._disagreements:
            self._disagreements = (*self._disagreements, COMPLETION_ALIAS_DISAGREEMENT)

    def _timeout_seconds(self) -> float:
        """The configured request budget, in the unit a transport takes."""
        if self._configuration is None:
            raise InternalError(NOT_INITIALIZED_MESSAGE)
        return self._configuration.adapter.timeout_ms / 1000

    async def _get(self, path: str, timeout_s: float) -> RuntimeResponse:
        """One GET against a published runtime path."""
        return await self._transport.get(
            self._settings.url_for(path), timeout_s=timeout_s
        )

    async def _read_json(self, path: str, context: RequestContext) -> object:
        """One descriptive GET, with its status and transport failures mapped."""
        try:
            response = await asyncio.wait_for(
                self._get(path, self._timeout_seconds()),
                timeout=self._timeout_seconds(),
            )
        except TransportError as failure:
            raise error_for_transport_failure(failure, context) from None
        except TimeoutError:
            raise request_deadline_error(context) from None
        status_failure = error_for_status(response.status_code, context)
        if status_failure is not None:
            raise status_failure
        return response.body

    async def _post(
        self,
        path: str,
        body: dict[str, object],
        context: RequestContext,
    ) -> RuntimeResponse:
        """One completion POST, under both deadlines."""
        timeout_s = self._timeout_seconds()
        try:
            return await asyncio.wait_for(
                self._transport.post_json(
                    self._settings.url_for(path), body, timeout_s=timeout_s
                ),
                timeout=timeout_s,
            )
        except TransportError as failure:
            raise error_for_transport_failure(failure, context) from None
        except TimeoutError:
            # `asyncio.wait_for` raises `TimeoutError` on Python 3.11 and later.
            # Reaching it means the transport did not honour the budget it was
            # given, which is the case the outer deadline exists for.
            raise request_deadline_error(context) from None


def _protocol_check(adapter: LlamaServerAdapter) -> ServingAdapter:
    """The real adapter satisfies the protocol the domain owns.

    A function rather than a module-level assignment because constructing one
    requires settings and a transport, and a check that needs a fixture is a
    check that runs somewhere other than at import. `mypy` fails here when a
    protocol member is renamed, which is the whole job.
    """
    return adapter
