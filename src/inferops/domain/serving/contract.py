"""The serving adapter contract as a runtime-neutral interface.

This module defines the protocol that all serving adapters (mock and real) must
implement. It represents the boundary between InferOps platform concepts and
serving-runtime implementations.

**Key design decisions:**

1. **Runtime-neutral**: The interface accepts validated platform domain objects
   and returns domain objects. Runtime-specific configuration and types are
   isolated to adapter implementations, not visible in this contract.

2. **Capability declaration**: Streaming and token metrics are declared as
   optional capabilities at initialization, not assumed to always be present.

3. **Absence preservation**: Optional fields like ``usage`` in results reflect
   whether a capability is supported, not whether a field happens to be present
   in a particular response.

4. **No internal state leakage**: The adapter is responsible for translating
   runtime errors to canonical error codes before they reach InferOps.

5. **Synchronous contract**: Covers configuration, readiness, inference,
   metadata, shutdown, and telemetry mapping. Asynchronous patterns are outside
   this PR's scope.

The interface is implemented by:
- Mock adapters (deterministic, for CI)
- Real adapters (connecting to actual serving runtimes)

Both must pass the conformance test harness to verify they meet the contract.
"""

from __future__ import annotations

from typing import Protocol

from ..context import RequestContext
from .errors import CanonicalError
from .values import (
    AdapterCapability,
    AdapterConfiguration,
    InferenceResult,
    ModelMetadata,
    RuntimeMetadata,
    TelemetryMapping,
)


class ServingAdapter(Protocol):
    """Runtime-neutral interface for LLM serving adapters.

    An adapter is responsible for:
    - Validating configuration at initialization
    - Reporting capabilities and readiness
    - Executing synchronous inference requests (streaming is a capability, not a contract method)
    - Mapping runtime errors to canonical codes
    - Translating runtime metadata to platform types
    - Providing telemetry mapping for metrics and errors
    - Graceful shutdown

    **Synchronous only in V1:** Streaming is a declared capability, and this interface
    contains no streaming method. Any call to a nonexistent streaming operation must
    fail explicitly with CapabilityUnavailableError. See ADR-0010.

    **Context propagation:** Methods that execute work (initialize, infer, shutdown)
    accept RequestContext for correlation and observability. Query methods
    (get_capabilities, get_model_metadata, get_runtime_metadata, map_error_to_canonical,
    get_telemetry_mapping) do not require context since they don't execute user requests.

    Adapters MUST NOT leak runtime-specific types or configuration into this
    interface. All communication uses domain value objects.
    """

    async def initialize(
        self,
        config: AdapterConfiguration,
        context: RequestContext,
    ) -> None:
        """Initialize the adapter with configuration and validate it.

        Called once at startup. Must validate that the configuration is
        sufficient to load and serve the model.

        Args:
            config: Configuration for the adapter (model ID, timeouts, etc).
            context: Request context with correlation IDs for observability.

        Raises:
            InvalidAdapterConfigError: If configuration is invalid or insufficient.
            InternalError: If an unexpected error occurs during initialization.
        """
        ...

    async def get_capabilities(self) -> list[AdapterCapability]:
        """Report the capabilities supported by this adapter.

        Must be called after ``initialize()``. Streaming and token-counting
        capabilities MUST be reported here; they MUST NOT be assumed to be
        present. Adapters that do not support a capability MUST report it as
        unsupported so that callers can handle the explicit error.

        Returns:
            List of declared capabilities. Includes:
            - "streaming": whether the adapter supports streaming responses
            - "token-counting": whether token usage metrics are available
            - Other adapter-specific capabilities as needed

        Raises:
            InternalError: If capability discovery fails.
        """
        ...

    async def is_ready(self, context: RequestContext) -> bool:
        """Check if the model is ready to serve requests.

        Readiness means the model has been loaded and can accept inference
        requests. This may take time after initialization (model loading,
        warmup, etc).

        Returns:
            True if the model is ready; False if still loading or unavailable.

        Raises:
            InternalError: If readiness cannot be determined.
        """
        ...

    async def infer(
        self,
        prompt: str,
        context: RequestContext,
    ) -> InferenceResult:
        """Execute a synchronous inference request.

        Translates the runtime's response to a domain result object. If a
        capability (like token counting) was declared but unavailable for this
        request, returns a result with that field as None (not an error).

        Args:
            prompt: The input prompt as a string.
            context: Request context with correlation IDs.

        Returns:
            The inference result with content, model, and optional usage/finish_reason.

        Raises:
            ModelNotReadyError: If the model is not ready.
            RequestTimeoutError: If the request exceeds the configured timeout.
            UpstreamTimeoutError: If the runtime's timeout is exceeded.
            RateLimitedError: If rate-limited by the runtime.
            InternalError: For unexpected errors in the adapter or runtime.
        """
        ...

    async def get_model_metadata(self) -> ModelMetadata:
        """Get metadata about the loaded model.

        Must include the model identifier. Revision (commit hash, version tag)
        is optional but recommended for reproducibility.

        Returns:
            Metadata about the currently loaded model.

        Raises:
            InternalError: If metadata cannot be retrieved.
        """
        ...

    async def get_runtime_metadata(self) -> RuntimeMetadata:
        """Get metadata about the serving runtime itself.

        Includes runtime name and version, which are used for observability,
        documentation, and evidence.

        Returns:
            Metadata about the serving runtime.

        Raises:
            InternalError: If metadata cannot be retrieved.
        """
        ...

    async def shutdown(self, context: RequestContext) -> None:
        """Gracefully shut down the adapter and release resources.

        Called at platform shutdown. Should stop accepting new requests and
        wait for in-flight requests to complete within a reasonable timeout
        before releasing resources.

        Args:
            context: Request context for observability.

        Raises:
            InternalError: If shutdown fails or takes too long.
        """
        ...

    async def map_error_to_canonical(
        self,
        error: Exception,
    ) -> CanonicalError:
        """Map a runtime error to a canonical error code.

        Used internally by the adapter to translate runtime-specific exceptions
        to canonical codes before raising them. This is how a runtime's error
        taxonomy becomes InferOps's canonical vocabulary.

        Args:
            error: The runtime error to translate.

        Returns:
            A canonical error with a standard error code and safe message.

        Raises:
            The error unchanged if it is already canonical.
        """
        ...

    async def get_telemetry_mapping(self) -> TelemetryMapping:
        """Get telemetry mapping for adapter metrics and errors.

        Provides the canonical mapping between adapter state and platform telemetry.
        Includes whether request counting is enabled and which error code applies
        if the adapter is in an error state.

        Returns:
            TelemetryMapping describing which metrics are available and active.

        Raises:
            InternalError: If telemetry mapping cannot be determined.
        """
        ...
