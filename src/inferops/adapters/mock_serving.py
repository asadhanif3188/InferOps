"""The deterministic mock serving adapter. CI only, and it says so itself.

This is the adapter normal CI runs against. It implements the whole
:class:`~inferops.domain.serving.ServingAdapter` protocol, replays one committed
fixture, and needs no model file, no credential, no container engine, no cluster,
and no network. Running the contract on every change is what it is for.

**It is a mock, and every artifact it produces says so in its own contents.**
That is boundary rule 6 in
``docs/serving/mock-and-real-boundary.md``: a label that lives in the directory a
file sits in is a label that does not survive the file being copied out of it. So
the adapter kind is ``mock``, the runtime identity is the ``inferops-mock-serving``
row the compatibility matrix already publishes, the model identity it will accept
is required to be mock-labelled, and :meth:`MockServingAdapter.mock_identity`
carries the same notice the committed response fixture carries.

**Three things it deliberately does not do**, because each would manufacture
evidence the project cannot support:

1. *It counts no tokens.* Token counting is declared an unsupported capability
   and ``usage`` is ``None``. A real runtime's counts come from its own
   tokeniser; a mock's would be numbers its author chose, and a number nobody
   measured that looks exactly like a number somebody did is the worst kind.
2. *It measures no latency.* Latency is a setting, applied by sleeping for it.
   It is an input to a test, never an observation, and it may not be reported as
   one.
3. *It refuses a real model identity.* ``initialize`` rejects a model identifier
   that is not mock-labelled, so a transcript from this adapter cannot be made to
   name the model in ADR 0002.

What it may be used to claim is settled elsewhere and is not this module's to
nominate: its evidence class is ``mock``, and that class ceilings at ``C1`` in
``docs/testing/certification.md``. No configuration of this adapter reaches
``C2``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum

from ..domain.context import NO_REQUEST_CONTEXT, RequestContext
from ..domain.serving import (
    AdapterCapability,
    AdapterConfiguration,
    CanonicalError,
    InferenceResult,
    InternalError,
    InvalidAdapterConfigError,
    InvalidValueError,
    ModelMetadata,
    ModelNotReadyError,
    RateLimitedError,
    RequestTimeoutError,
    RuntimeMetadata,
    ServingAdapter,
    TelemetryMapping,
    UpstreamTimeoutError,
)

#: The adapter kind every result this adapter produces declares. It is one of the
#: two members of the closed vocabulary the domain publishes, and it is a constant
#: here rather than a setting: an adapter that could be configured to call itself
#: ``real`` is the failure the vocabulary exists to prevent.
MOCK_ADAPTER_KIND = "mock"

#: The registered runtime identifier for this adapter, as
#: ``contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json``
#: publishes it. The telemetry catalog's ``inferops.runtime.id`` is the attribute
#: that carries it, and carrying it is how a mock result stays visibly a mock
#: result wherever it is read.
MOCK_RUNTIME_ID = "inferops-mock-serving"

#: The serving capability a ``mock-llm`` workload binds to. The schema pins the
#: profile to this capability and to the ``ci`` environment; this constant is the
#: adapter's half of that pairing.
MOCK_SERVING_CAPABILITY = "inferops-mock-serving"

#: Version reported as the runtime version. It names the contract generation and
#: the fact that this is a mock, because a serving-runtime version read out of a
#: record is a thing readers compare against release notes.
MOCK_RUNTIME_VERSION = "mock-v1alpha1"

#: How responses are produced, in the vocabulary ``spec.mockLlm.determinism``
#: publishes. Fixed fixtures are the only permitted mode: a mock that varies is a
#: mock nobody can assert against.
MOCK_DETERMINISM = "fixed-fixture"

#: The model identity this adapter reports when it has not been configured, and
#: the identity the committed ``mock-llm`` example declares as its ``modelRef``.
MOCK_MODEL_IDENTIFIER = "mock-fixed-fixture"

#: Every model identity this adapter will accept starts with this. See
#: :meth:`MockServingAdapter.initialize` for why the restriction is here rather
#: than in a review checklist.
MOCK_MODEL_IDENTIFIER_PREFIX = "mock-"

#: The committed response fixture this adapter replays.
MOCK_FIXTURE_REF = "contracts/workload/fixtures/mock-llm-chat-completion.response.json"

#: The completion text in that fixture, and the only text this adapter returns.
#: ``tests/adapters/`` reads the fixture and fails if the two disagree, which is
#: what keeps this constant honest without the module reading a file.
MOCK_FIXTURE_CONTENT = (
    "This is a deterministic InferOps mock fixture, not model output."
)

#: The finish reason in that fixture.
MOCK_FIXTURE_FINISH_REASON = "stop"

#: The notice the fixture carries in its own ``_inferopsMock`` block, repeated
#: here so that an artifact this adapter produces carries it too.
MOCK_NOTICE = (
    "Deterministic mock fixture. No model produced this. It is not evidence of "
    "real serving behaviour, latency, token accounting, or model quality."
)

#: The accepted rule this adapter exists under.
MOCK_BOUNDARY_RULE_REF = "docs/serving/mock-and-real-boundary.md"

#: The evidence class every result from this adapter belongs to, as
#: ``docs/testing/test-strategy.v1alpha1.json`` publishes it.
MOCK_EVIDENCE_CLASS = "mock"

#: The highest certification level that evidence class can support. Declared so
#: that a caller writing a record does not have to look it up, and asserted
#: against the committed strategy data rather than trusted.
MOCK_MAX_CERTIFICATION = "C1"

#: Capability declared by an adapter that replays a fixture rather than
#: generating text.
CAPABILITY_DETERMINISTIC_FIXTURE_REPLAY = "deterministic-fixture-replay"

#: Capability an adapter declares when a model produced the response. This one
#: reports it unsupported, which is the capability layer's statement of the same
#: thing ``adapter_kind`` says.
CAPABILITY_REAL_MODEL_INFERENCE = "real-model-inference"

#: Streaming, which V1 has no protocol method for at all.
CAPABILITY_STREAMING = "streaming"

#: Token counting, unsupported here for the reason in the module docstring.
CAPABILITY_TOKEN_COUNTING = "token-counting"

#: What :meth:`MockServingAdapter.get_capabilities` returns, in one place so that
#: a reader sees the whole declaration without executing anything. It is a tuple
#: because a list would be a shared mutable default in every caller's hands.
MOCK_CAPABILITIES: tuple[AdapterCapability, ...] = (
    AdapterCapability(name=CAPABILITY_STREAMING, supported=False),
    AdapterCapability(name=CAPABILITY_TOKEN_COUNTING, supported=False),
    AdapterCapability(name=CAPABILITY_DETERMINISTIC_FIXTURE_REPLAY, supported=True),
    AdapterCapability(name=CAPABILITY_REAL_MODEL_INFERENCE, supported=False),
)


class MockScenario(StrEnum):
    """What the adapter does when a request arrives.

    Each failing member's value **is** the canonical error code it produces, so
    a scenario and the code a caller sees cannot drift apart: there is only one
    string. ``SUCCESS`` is the one member that names no code, because a success
    is not an error with an empty code.

    ``capability-unavailable`` is absent on purpose. It is raised when a caller
    asks for a capability an adapter does not support, and V1's protocol has no
    optional-capability call to make — streaming is not a method, and absent
    token usage is ``None`` rather than a failure. Injecting it here would mean
    inventing a call site to fail.
    """

    SUCCESS = "success"
    MODEL_NOT_READY = "model-not-ready"
    REQUEST_TIMEOUT = "request-timeout"
    UPSTREAM_TIMEOUT = "upstream-timeout"
    RATE_LIMITED = "rate-limited"
    INTERNAL_ERROR = "internal-error"


@dataclass(frozen=True, slots=True)
class MockAdapterSettings:
    """How one mock adapter instance behaves, fixed at construction.

    These are the adapter's own settings and they are deliberately not part of
    :class:`~inferops.domain.serving.AdapterConfiguration`: the platform
    configuration describes a workload, and failure injection describes a test.
    Putting the second in the first would put mock-specific fields in the
    interface every real adapter also implements.

    Attributes:
        scenario: What a request does. ``SUCCESS`` replays the fixture.
        latency_ms: How long a request sleeps before answering. A setting, never
            a measurement, and never reportable as one.
    """

    scenario: MockScenario = MockScenario.SUCCESS
    latency_ms: int = 0

    def __post_init__(self) -> None:
        if self.latency_ms < 0:
            raise InvalidValueError("latency_ms must be non-negative")


class MockServingAdapter:
    """A deterministic, CI-only implementation of the serving adapter contract.

    Identical input produces identical output: the fixture is a constant, the
    injected failure is a setting, and nothing here reads a clock, a random
    source, an environment variable, or a file.

    The instance is not safe to share across event loops, which is the same
    caveat any adapter holding a connection carries and is stated so that a
    future real adapter is not held to a stricter rule than this one.
    """

    def __init__(self, settings: MockAdapterSettings | None = None) -> None:
        self._settings = settings if settings is not None else MockAdapterSettings()
        self._config: AdapterConfiguration | None = None
        self._is_shut_down = False

    @property
    def settings(self) -> MockAdapterSettings:
        """The settings this instance was constructed with."""
        return self._settings

    # -- the contract ----------------------------------------------------

    async def initialize(
        self,
        config: AdapterConfiguration,
        context: RequestContext,
    ) -> None:
        """Accept a configuration, provided it names a mock model identity.

        The identity check is the safeguard that cannot be left to review. A
        mock configured with the model revision in ADR 0002 would emit a
        transcript naming that model, and a transcript naming a real model is
        the exact artifact somebody later cites as real-runtime evidence. The
        refusal is canonical, carries the field location, and repeats no value
        read from the configuration.

        Raises:
            InvalidAdapterConfigError: If the model identity is not mock-labelled.
        """
        if not config.model_identifier.startswith(MOCK_MODEL_IDENTIFIER_PREFIX):
            raise InvalidAdapterConfigError(
                "model_identifier",
                "a mock adapter accepts only a mock-labelled model identity, "
                f"which starts with '{MOCK_MODEL_IDENTIFIER_PREFIX}'",
                context=context,
            )
        self._config = config
        self._is_shut_down = False

    async def get_capabilities(self) -> list[AdapterCapability]:
        """Declare what this adapter supports, including what it does not.

        The declaration is static: nothing this adapter can be configured to do
        changes it. Streaming and token counting are unsupported, fixture replay
        is supported, and real model inference is unsupported — which is the
        capability layer saying the same thing ``adapter_kind`` says, in the
        place a caller inspecting capabilities will look.
        """
        return list(MOCK_CAPABILITIES)

    async def is_ready(self, context: RequestContext) -> bool:
        """Report readiness: configured, not shut down, and not held not-ready.

        The ``model-not-ready`` scenario makes this ``False`` as well as making
        :meth:`infer` raise, because an adapter that reports itself ready and
        then refuses every request is a state no real runtime produces and no
        caller should be written against.
        """
        if self._config is None or self._is_shut_down:
            return False
        return self._settings.scenario is not MockScenario.MODEL_NOT_READY

    async def infer(
        self,
        prompt: str,
        context: RequestContext,
    ) -> InferenceResult:
        """Replay the committed fixture, or raise the injected canonical error.

        The prompt is accepted and not read. That is not an oversight: a fixed
        fixture is what ``spec.mockLlm.determinism`` requires, and a mock whose
        output varied with the prompt would tempt a reader into treating the
        variation as behaviour.

        The prompt is also not stored, logged, or echoed into any result or
        error, which is the redaction rule holding at the one place in this
        distribution that currently receives one.

        Raises:
            ModelNotReadyError: If not initialized, shut down, or held not-ready.
            RequestTimeoutError: If injected, or if the configured latency
                reaches the configured request timeout.
            UpstreamTimeoutError: If injected.
            RateLimitedError: If injected.
            InternalError: If injected.
        """
        if self._config is None:
            raise ModelNotReadyError(
                "adapter has not been initialized", context=context
            )
        if self._is_shut_down:
            raise ModelNotReadyError("adapter has been shut down", context=context)

        self._raise_injected_failure(context)

        # Checked before sleeping, not after: a mock that has to burn the whole
        # timeout to report a timeout makes the default lane slower for nothing.
        if self._settings.latency_ms >= self._config.timeout_ms:
            raise RequestTimeoutError(
                "configured mock latency reaches the configured request timeout",
                context=context,
            )
        await self._sleep_configured_latency()

        return InferenceResult(
            content=MOCK_FIXTURE_CONTENT,
            model=self._config.model_identifier,
            adapter_kind=MOCK_ADAPTER_KIND,
            usage=None,
            finish_reason=MOCK_FIXTURE_FINISH_REASON,
        )

    async def get_model_metadata(self) -> ModelMetadata:
        """Report the configured mock model identity, and no revision.

        ``revision`` is ``None`` rather than invented. There is no model, so
        there is no revision, and ``None`` is what the domain publishes for a
        value that was not provided.
        """
        return ModelMetadata(
            identifier=(
                self._config.model_identifier
                if self._config is not None
                else MOCK_MODEL_IDENTIFIER
            ),
            revision=None,
        )

    async def get_runtime_metadata(self) -> RuntimeMetadata:
        """Report the registered mock runtime identity from the matrix."""
        return RuntimeMetadata(name=MOCK_RUNTIME_ID, version=MOCK_RUNTIME_VERSION)

    async def shutdown(self, context: RequestContext) -> None:
        """Stop answering. There is nothing to release, and that is the point."""
        self._is_shut_down = True

    async def map_error_to_canonical(
        self,
        error: Exception,
        context: RequestContext | None = None,
    ) -> CanonicalError:
        """Return a canonical error unchanged; map anything else to internal.

        The unrecognised error's own message is dropped rather than wrapped. A
        runtime message is the place a path, a host name, or a credential
        arrives in a response, and this adapter has no way to tell which
        message is which.
        """
        if isinstance(error, CanonicalError):
            return error
        return InternalError(
            "internal-error",
            context=context if context is not None else NO_REQUEST_CONTEXT,
        )

    async def get_telemetry_mapping(self) -> TelemetryMapping:
        """Map this adapter's state onto platform telemetry.

        It reports no metric of its own. ADR 0002 leaves the request counter to
        InferOps because the selected runtime exposes no cumulative counter, and
        a mock producing one would be the platform reading its own number back.
        """
        return TelemetryMapping(
            platform_metric_ids=(),
            error_code=self.injected_error_code(),
            token_usage=False,
        )

    # -- mock identity, which is not part of the contract ----------------

    def injected_error_code(self) -> str | None:
        """The canonical code this adapter is configured to produce, if any."""
        if self._settings.scenario is MockScenario.SUCCESS:
            return None
        return str(self._settings.scenario)

    def telemetry_identity(self) -> dict[str, str]:
        """Mock identity as telemetry attributes, for a log field or a record.

        Every key is an attribute the committed telemetry catalog publishes, and
        every one is permitted in a log field and in an evidence field. The
        catalog's note on ``inferops.runtime.id`` is the mechanism being used
        here: the registered runtime identifier includes the mock runtime, which
        is how a mock result stays visibly a mock result.
        """
        return {
            "inferops.runtime.id": MOCK_RUNTIME_ID,
            "inferops.capability.id": MOCK_SERVING_CAPABILITY,
            "inferops.model.id": (
                self._config.model_identifier
                if self._config is not None
                else MOCK_MODEL_IDENTIFIER
            ),
        }

    def mock_identity(self) -> dict[str, object]:
        """A self-describing block for any artifact this adapter contributes to.

        It is the same shape the committed response fixture carries in its own
        ``_inferopsMock`` member, and it exists for the same reason: a label in
        a directory name does not survive the file being copied elsewhere, and a
        label in the contents does.
        """
        return {
            "isMock": True,
            "notice": MOCK_NOTICE,
            "boundaryRule": MOCK_BOUNDARY_RULE_REF,
            "adapterKind": MOCK_ADAPTER_KIND,
            "runtimeId": MOCK_RUNTIME_ID,
            "determinism": MOCK_DETERMINISM,
            "fixtureRef": MOCK_FIXTURE_REF,
            "evidenceClass": MOCK_EVIDENCE_CLASS,
            "maxCertification": MOCK_MAX_CERTIFICATION,
        }

    # -- internals -------------------------------------------------------

    def _raise_injected_failure(self, context: RequestContext) -> None:
        """Raise the canonical error the configured scenario names."""
        scenario = self._settings.scenario
        if scenario is MockScenario.SUCCESS:
            return
        if scenario is MockScenario.MODEL_NOT_READY:
            raise ModelNotReadyError("injected mock scenario", context=context)
        if scenario is MockScenario.REQUEST_TIMEOUT:
            raise RequestTimeoutError("injected mock scenario", context=context)
        if scenario is MockScenario.UPSTREAM_TIMEOUT:
            raise UpstreamTimeoutError("injected mock scenario", context=context)
        if scenario is MockScenario.RATE_LIMITED:
            raise RateLimitedError("injected mock scenario", context=context)
        raise InternalError("injected mock scenario", context=context)

    async def _sleep_configured_latency(self) -> None:
        """Sleep the configured latency. Zero by default, and zero in CI."""
        if self._settings.latency_ms:
            await asyncio.sleep(self._settings.latency_ms / 1000)


# Static conformance check: the mock satisfies the protocol the domain owns.
# It is an assignment rather than a comment because a comment does not fail
# `mypy` when a protocol method is renamed.
_protocol_check: ServingAdapter = MockServingAdapter()
