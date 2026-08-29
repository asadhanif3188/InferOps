"""Minimal test double for the serving adapter contract.

This module provides a deterministic in-memory adapter implementation used by
conformance tests. It is not a mock in the mocking-framework sense; it is a
concrete minimal implementation that satisfies the protocol.

**Properties:**
- No external dependencies or network access
- Deterministic responses based on input
- Can be configured to simulate various states (ready, not ready, errors)
- V1 protocol: synchronous only (streaming always unsupported)
- Adapter kind: always "mock"
- Tracks initialization and calls for test verification
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..context import NO_REQUEST_CONTEXT, RequestContext
from .contract import ServingAdapter
from .errors import (
    CanonicalError,
    InternalError,
    InvalidAdapterConfigError,
    ModelNotReadyError,
)
from .values import (
    AdapterCapability,
    AdapterConfiguration,
    InferenceResult,
    ModelMetadata,
    RuntimeMetadata,
    TelemetryMapping,
    TokenUsage,
)

# Accepted adapter kinds (closed vocabulary)
ACCEPTED_ADAPTER_KINDS = {"mock", "real"}


@dataclass
class MinimalTestDouble:
    """Minimal test double for adapter conformance testing.

    Used by conformance tests to verify the protocol works. Not suitable for
    integration tests or production use.

    Attributes:
        model_ready: Whether the model is ready (can be controlled for testing).
        should_support_token_counting: Whether token counting is supported.
        initialized: Whether initialize() was called.
    """

    model_ready: bool = True
    should_support_token_counting: bool = True
    initialized: bool = False

    _config: AdapterConfiguration | None = field(default=None, init=False)
    _inference_count: int = field(default=0, init=False)

    async def initialize(
        self,
        config: AdapterConfiguration,
        context: RequestContext,
    ) -> None:
        """Initialize the test double with configuration."""
        if not config.model_identifier:
            raise InvalidAdapterConfigError(
                "model_identifier", "must not be empty", context=context
            )
        self._config = config
        self.initialized = True

    async def get_capabilities(self) -> list[AdapterCapability]:
        """Report supported capabilities.

        V1 is synchronous-only: streaming is declared as unsupported capability,
        never as a protocol method.
        """
        return [
            AdapterCapability(
                name="streaming",
                supported=False,  # V1 constraint: streaming always unsupported
            ),
            AdapterCapability(
                name="token-counting",
                supported=self.should_support_token_counting,
            ),
        ]

    async def is_ready(self, context: RequestContext) -> bool:
        """Report model readiness."""
        return self.model_ready

    async def infer(
        self,
        prompt: str,
        context: RequestContext,
    ) -> InferenceResult:
        """Generate a deterministic response."""
        if not self.model_ready:
            raise ModelNotReadyError("model is loading", context=context)

        self._inference_count += 1

        usage = None
        if self.should_support_token_counting:
            prompt_len = len(prompt.split())
            usage = TokenUsage(input_tokens=prompt_len, output_tokens=5)

        return InferenceResult(
            content=f"Test response to: {prompt[:50]}",
            model=self._config.model_identifier if self._config else "test-model",
            adapter_kind="mock",  # Test double is always mock adapter
            usage=usage,
            finish_reason="stop",
        )

    async def get_model_metadata(self) -> ModelMetadata:
        """Report model metadata."""
        return ModelMetadata(
            identifier=self._config.model_identifier if self._config else "test-model",
            revision="test-revision",
        )

    async def get_runtime_metadata(self) -> RuntimeMetadata:
        """Report runtime metadata."""
        return RuntimeMetadata(
            name="test-double",
            version="0.0.1",
        )

    async def shutdown(self, context: RequestContext) -> None:
        """Shut down the test double (no-op)."""
        self.initialized = False

    async def map_error_to_canonical(
        self,
        error: Exception,
        context: RequestContext | None = None,
    ) -> CanonicalError:
        """Map errors to canonical types, preserving request context."""
        if isinstance(error, CanonicalError):
            return error
        error_context = context if context is not None else NO_REQUEST_CONTEXT
        return InternalError("internal-error", context=error_context)

    async def get_telemetry_mapping(self) -> TelemetryMapping:
        """Get telemetry mapping.

        Per ADR-0002: InferOps owns request counter production.
        Adapter maps only to accepted canonical metric identifiers.
        """
        return TelemetryMapping(
            platform_metric_ids=(),  # Test double reports no custom metrics
        )


# Accepted adapter kinds as a module constant
__all__ = ["ACCEPTED_ADAPTER_KINDS", "MinimalTestDouble", "ServingAdapterTestDouble"]


# Static conformance check: MinimalTestDouble satisfies ServingAdapter protocol
_protocol_check: ServingAdapter = MinimalTestDouble()

# Alias for clarity in imports: the test double implements the protocol
ServingAdapterTestDouble = MinimalTestDouble
