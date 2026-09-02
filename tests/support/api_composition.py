"""Adapters and applications the API suites compose, in one place.

Every suite under ``tests/api`` drives the application through the ASGI
interface it implements, with no server and no socket. What differs between them
is which adapter is behind it, so the composition lives here and the suites say
what they are exercising rather than how to build one.

Two adapters appear. :class:`~inferops.adapters.MockServingAdapter` is the
committed mock — it replays a fixture, declares its own kind, and refuses a model
identity that is not mock-labelled — and it is what the end-to-end suites use.
:class:`RecordingAdapter` is a controlled double built for the suites that need
to see what the API handed the adapter, or to make an adapter behave in a way the
mock deliberately cannot.

Nothing here reads a clock, a file, a network, or an environment variable, and
the clock the applications are built with is a fixed one, so a body produced by
these suites is identical on every run except for the identifiers the API
generates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from inferops.api import ApiConfiguration, InferOpsApi
from inferops.domain.context import RequestContext
from inferops.domain.serving import (
    AdapterCapability,
    AdapterConfiguration,
    CanonicalError,
    InferenceResult,
    MinimalTestDouble,
    ModelMetadata,
    RuntimeMetadata,
)

#: The model identity the mock adapter accepts. It is mock-labelled because the
#: mock refuses anything that is not, which is the boundary rule holding at the
#: composition point rather than in a review.
MOCK_MODEL = "mock-fixed-fixture"

#: A fixed instant, so that ``created`` is a constant in these suites. A clock in
#: a test is an input; a clock in a record is a measurement, and the two are kept
#: apart deliberately.
FIXED_NOW = 1_700_000_000


def fixed_clock() -> float:
    """The clock the applications in these suites are built with."""
    return float(FIXED_NOW)


@dataclass
class RecordingAdapter(MinimalTestDouble):
    """A controlled adapter that records what the API handed it.

    It extends the domain's own conformance double rather than reimplementing the
    protocol, so a protocol change breaks it in the same place it breaks every
    other implementation.

    Attributes:
        contexts: The request context of every ``infer`` call, in order. This is
            what a suite asserting identifier propagation reads.
        prompts: The prompt of every ``infer`` call, in order.
        declared_kind: The adapter kind its results declare. It exists so that a
            suite can build the one thing the composition point is supposed to
            catch: a result whose declared kind is not the deployment's.
        failure: A canonical error to raise from ``infer`` instead of answering.
        shutdown_calls: How many times ``shutdown`` was called.
    """

    declared_kind: str = "mock"
    failure: CanonicalError | None = None
    contexts: list[RequestContext] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)
    shutdown_calls: int = 0
    ready_calls: list[RequestContext] = field(default_factory=list)
    runtime_name: str = "test-double"
    runtime_identifier: str | None = None

    async def infer(self, prompt: str, context: RequestContext) -> InferenceResult:
        self.contexts.append(context)
        self.prompts.append(prompt)
        if self.failure is not None:
            raise self.failure
        result = await super().infer(prompt, context)
        return InferenceResult(
            content=result.content,
            model=result.model,
            adapter_kind=self.declared_kind,
            usage=result.usage,
            finish_reason=result.finish_reason,
        )

    async def is_ready(self, context: RequestContext) -> bool:
        self.ready_calls.append(context)
        return await super().is_ready(context)

    async def get_runtime_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            name=self.runtime_name,
            version="0.0.1",
            identifier=self.runtime_identifier,
        )

    async def get_model_metadata(self) -> ModelMetadata:
        return await super().get_model_metadata()

    async def get_capabilities(self) -> list[AdapterCapability]:
        return await super().get_capabilities()

    async def shutdown(self, context: RequestContext) -> None:
        self.shutdown_calls += 1
        await super().shutdown(context)


def build(
    adapter: object,
    *,
    model_identifier: str = MOCK_MODEL,
    adapter_kind: str = "mock",
    drain_timeout_ms: int = 1_000,
) -> InferOpsApi:
    """Compose one application around one adapter. No I/O happens here."""
    return InferOpsApi(
        adapter=adapter,  # type: ignore[arg-type]
        adapter_configuration=AdapterConfiguration(
            model_identifier=model_identifier,
            timeout_ms=5_000,
        ),
        configuration=ApiConfiguration(
            adapter_kind=adapter_kind,
            drain_timeout_ms=drain_timeout_ms,
        ),
        clock=fixed_clock,
    )
