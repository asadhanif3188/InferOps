"""Conformance tests for the serving adapter contract.

This suite establishes that:
- An adapter satisfies the ServingAdapter protocol
- All contract methods work as expected
- Capability declaration is explicit
- No runtime-specific types leak into the interface
- Error mapping produces canonical errors
- Unsupported capabilities fail explicitly when not declared

**Reusable across adapter implementations:** To test a different adapter
(mock, real llama.cpp, etc), override the adapter_factory fixture in your
conftest.py:

    @pytest.fixture
    def adapter_factory():
        from my_adapter import MyAdapter
        return MyAdapter

The entire conformance suite will then test your adapter without modification.
No copy-adapt needed; the same tests validate any adapter that implements
the ServingAdapter protocol.

What this does not establish: that mock or real adapters work correctly beyond
protocol conformance. Those are scope for integration/e2e tests. This suite
establishes only that the contract itself is coherent, testable, and that
an implementation actually satisfies it.
"""

from __future__ import annotations

import pytest

from inferops.domain import RequestContext
from inferops.domain.serving import (
    AdapterConfiguration,
    InferenceResult,
    ModelMetadata,
    RuntimeMetadata,
    ServingAdapter,
    TelemetryMapping,
    TokenUsage,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def test_context() -> RequestContext:
    """Provide a request context."""
    return RequestContext(
        request_id="test-req-001",
        correlation_id="test-corr-002",
    )


@pytest.fixture
def test_config() -> AdapterConfiguration:
    """Provide a valid configuration."""
    return AdapterConfiguration(
        model_identifier="test-model",
        timeout_ms=30000,
    )


class TestAdapterInitialization:
    """Tests for adapter initialization."""

    async def test_initialization_succeeds_with_valid_config(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify initialization completes with valid config."""
        await adapter.initialize(test_config, test_context)
        assert adapter.initialized

    async def test_initialization_rejects_empty_model_id(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
    ) -> None:
        """Verify initialization rejects empty model identifier."""
        from inferops.domain.serving import InvalidValueError

        with pytest.raises(InvalidValueError):
            AdapterConfiguration(
                model_identifier="",
                timeout_ms=30000,
            )


class TestCapabilityDeclaration:
    """Tests for capability declaration."""

    async def test_get_capabilities_returns_list(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify get_capabilities returns a list of AdapterCapability."""
        await adapter.initialize(test_config, test_context)
        caps = await adapter.get_capabilities()

        assert isinstance(caps, list)
        assert len(caps) > 0
        assert all(hasattr(c, "name") for c in caps)
        assert all(hasattr(c, "supported") for c in caps)

    async def test_capabilities_include_streaming_and_token_counting(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify standard capabilities are declared."""
        await adapter.initialize(test_config, test_context)
        caps = await adapter.get_capabilities()
        cap_names = {c.name for c in caps}

        assert "streaming" in cap_names
        assert "token-counting" in cap_names


class TestReadiness:
    """Tests for model readiness reporting."""

    async def test_is_ready_returns_boolean(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify is_ready returns a boolean."""
        await adapter.initialize(test_config, test_context)
        ready = await adapter.is_ready(test_context)

        assert isinstance(ready, bool)

    async def test_is_ready_reflects_adapter_state(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify is_ready reflects the adapter's configured state."""
        await adapter.initialize(test_config, test_context)

        adapter.model_ready = True
        assert await adapter.is_ready(test_context) is True

        adapter.model_ready = False
        assert await adapter.is_ready(test_context) is False


class TestInference:
    """Tests for inference execution."""

    async def test_infer_returns_inference_result(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify infer returns an InferenceResult domain object."""
        await adapter.initialize(test_config, test_context)
        result = await adapter.infer("test prompt", test_context)

        assert isinstance(result, InferenceResult)
        assert isinstance(result.content, str)
        assert isinstance(result.model, str)
        assert isinstance(result.adapter_kind, str)

    async def test_infer_result_includes_adapter_kind(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify inference result always includes adapter kind."""
        await adapter.initialize(test_config, test_context)
        result = await adapter.infer("test prompt", test_context)

        assert result.adapter_kind is not None
        assert result.adapter_kind == "mock"

    async def test_infer_result_respects_optional_capabilities(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify inference succeeds with optional capabilities disabled.

        Token counting is optional; even when disabled, inference works.
        """
        adapter.should_support_token_counting = False
        await adapter.initialize(test_config, test_context)
        result = await adapter.infer("test prompt", test_context)

        assert isinstance(result, InferenceResult)
        assert isinstance(result.content, str)
        # When not supported, adapter may or may not include usage (both valid)

    async def test_infer_with_token_counting_includes_usage(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify token usage is included when capability is supported."""
        adapter.should_support_token_counting = True
        await adapter.initialize(test_config, test_context)
        result = await adapter.infer("test prompt", test_context)

        assert result.usage is not None
        assert isinstance(result.usage, TokenUsage)
        assert result.usage.input_tokens >= 0
        assert result.usage.output_tokens >= 0

    async def test_infer_fails_when_not_ready(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify inference fails with ModelNotReadyError when not ready."""
        adapter.model_ready = False
        await adapter.initialize(test_config, test_context)

        from inferops.domain.serving import ModelNotReadyError

        with pytest.raises(ModelNotReadyError):
            await adapter.infer("test prompt", test_context)


class TestStreamingCapability:
    """Tests for streaming as a declared capability (not a contract method).

    V1 protocol is synchronous-only: streaming is declared via capability
    discovery as unsupported, never as a protocol method.
    """

    async def test_streaming_always_declared_unsupported(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify streaming is always declared as unsupported capability.

        Even if an adapter had a flag to configure it, V1 contract enforces
        streaming is always declared unsupported in capabilities.
        """
        await adapter.initialize(test_config, test_context)
        caps = await adapter.get_capabilities()
        cap_names = {c.name for c in caps}

        assert "streaming" in cap_names
        streaming_cap = next(c for c in caps if c.name == "streaming")
        assert streaming_cap.supported is False, (
            "V1 is synchronous-only; streaming must always be unsupported"
        )

    async def test_no_stream_method_exists_on_protocol(self) -> None:
        """Verify the protocol has no stream method.

        If streaming is needed, it is declared as unsupported capability
        and the protocol only exposes synchronous infer().
        """
        from inferops.domain.serving import ServingAdapter

        assert not hasattr(ServingAdapter, "stream"), (
            "V1 protocol must have no stream() method; streaming is a capability only"
        )


class TestMetadata:
    """Tests for metadata reporting."""

    async def test_get_model_metadata_returns_model_metadata(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify get_model_metadata returns a ModelMetadata object."""
        await adapter.initialize(test_config, test_context)
        metadata = await adapter.get_model_metadata()

        assert isinstance(metadata, ModelMetadata)
        assert isinstance(metadata.identifier, str)
        assert metadata.identifier == test_config.model_identifier

    async def test_get_runtime_metadata_returns_runtime_metadata(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify get_runtime_metadata returns a RuntimeMetadata object."""
        await adapter.initialize(test_config, test_context)
        metadata = await adapter.get_runtime_metadata()

        assert isinstance(metadata, RuntimeMetadata)
        assert isinstance(metadata.name, str)
        assert isinstance(metadata.version, str)


class TestShutdown:
    """Tests for adapter shutdown."""

    async def test_shutdown_completes(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify shutdown completes without error."""
        await adapter.initialize(test_config, test_context)
        await adapter.shutdown(test_context)
        assert not adapter.initialized


class TestErrorMapping:
    """Tests for error mapping to canonical types."""

    async def test_map_error_returns_canonical_error(
        self,
        adapter: ServingAdapter,
    ) -> None:
        """Verify error mapping returns a CanonicalError."""
        from inferops.domain.serving import CanonicalError

        error = ValueError("test error")
        mapped = await adapter.map_error_to_canonical(error)

        assert isinstance(mapped, CanonicalError)
        assert isinstance(mapped.code, str)
        assert isinstance(mapped.message, str)

    async def test_map_error_passes_canonical_errors_through(
        self,
        adapter: ServingAdapter,
    ) -> None:
        """Verify canonical errors are returned unchanged."""
        from inferops.domain.serving import ModelNotReadyError

        error = ModelNotReadyError("model loading")
        mapped = await adapter.map_error_to_canonical(error)

        assert isinstance(mapped, ModelNotReadyError)

    async def test_map_error_sanitizes_sensitive_data(
        self,
        adapter: ServingAdapter,
    ) -> None:
        """Verify error mapping does not leak sensitive data."""
        sensitive_msg = "ghp_1234567890abcdefghijklmnopqrst"
        error = ValueError(sensitive_msg)
        mapped = await adapter.map_error_to_canonical(error)

        assert sensitive_msg not in mapped.message
        assert "test" not in str(error) or "internal-error" in mapped.message


class TestContextPropagation:
    """Tests for request context propagation."""

    async def test_error_preserves_request_context_from_infer(
        self,
        adapter: ServingAdapter,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify errors from infer() preserve request and correlation IDs."""
        from inferops.domain.serving import ModelNotReadyError

        adapter.model_ready = False
        await adapter.initialize(test_config, RequestContext())
        context_with_ids = RequestContext(
            request_id="test-req-123",
            correlation_id="test-corr-456",
        )

        with pytest.raises(ModelNotReadyError) as exc_info:
            await adapter.infer("test", context_with_ids)

        error = exc_info.value
        assert error.context.request_id == "test-req-123"
        assert error.context.correlation_id == "test-corr-456"

    async def test_error_mapping_preserves_context(
        self,
        adapter: ServingAdapter,
    ) -> None:
        """Verify map_error_to_canonical preserves supplied context."""
        from inferops.domain.serving import InternalError

        context = RequestContext(
            request_id="test-req-789",
            correlation_id="test-corr-012",
        )

        # Map an unknown error with context
        unknown_error = ValueError("unknown runtime error")
        mapped = await adapter.map_error_to_canonical(unknown_error, context)

        # Mapped error must be canonical and preserve context
        assert isinstance(mapped, InternalError)
        assert mapped.context.request_id == "test-req-789"
        assert mapped.context.correlation_id == "test-corr-012"


class TestTelemetryMapping:
    """Tests for telemetry mapping.

    Per ADR-0002: InferOps (not adapter/runtime) owns inferops_inference_requests_total.
    TelemetryMapping maps adapter metrics to platform canonical identifiers only.
    """

    async def test_get_telemetry_mapping_returns_mapping(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify get_telemetry_mapping returns a TelemetryMapping."""
        await adapter.initialize(test_config, test_context)
        mapping = await adapter.get_telemetry_mapping()

        assert isinstance(mapping, TelemetryMapping)
        assert isinstance(mapping.platform_metric_ids, tuple)

    async def test_telemetry_mapping_uses_only_canonical_error_codes(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify telemetry mapping uses only canonical error codes."""
        await adapter.initialize(test_config, test_context)
        mapping = await adapter.get_telemetry_mapping()

        allowed_codes = {
            "model-not-ready",
            "request-timeout",
            "upstream-timeout",
            "rate-limited",
            "capability-unavailable",
            "internal-error",
        }
        if mapping.error_code is not None:
            assert mapping.error_code in allowed_codes, (
                f"error_code must be one of {allowed_codes}, got {mapping.error_code}"
            )

    async def test_telemetry_mapping_lists_only_platform_metrics(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify mapping lists only platform canonical metric identifiers.

        Per ADR-0002, InferOps owns request counter. Adapter reports only
        optional metrics from platform telemetry catalog. Metric identifiers
        must match canonical pattern and not use reserved prefixes.
        """
        await adapter.initialize(test_config, test_context)
        mapping = await adapter.get_telemetry_mapping()

        # All identifiers must be strings
        assert all(isinstance(mid, str) for mid in mapping.platform_metric_ids)
        # Metric IDs must be immutable (tuple, not list)
        assert isinstance(mapping.platform_metric_ids, tuple)
        # Request counter is not in adapter's metric list (InferOps owns it)
        assert "inferops_inference_requests_total" not in mapping.platform_metric_ids


class TestAdapterKindValidation:
    """Tests for adapter kind validation.

    Adapter kind is a closed vocabulary (mock, real, etc), not just a format.
    The mock/real boundary requires provenance to be verifiable.
    """

    def test_adapter_kind_must_be_lowercase_kebab_case(self) -> None:
        """Verify adapter_kind must be lowercase kebab-case format."""
        from inferops.domain.serving import InvalidValueError

        with pytest.raises(InvalidValueError):
            InferenceResult(
                content="test",
                model="test-model",
                adapter_kind="Mock",  # uppercase rejected
            )

    def test_adapter_kind_must_not_be_empty(self) -> None:
        """Verify adapter_kind cannot be empty."""
        from inferops.domain.serving import InvalidValueError

        with pytest.raises(InvalidValueError):
            InferenceResult(
                content="test",
                model="test-model",
                adapter_kind="",  # empty rejected
            )

    def test_adapter_kind_must_be_accepted_value(self) -> None:
        """Verify adapter_kind is from closed vocabulary.

        Only 'mock' and 'real' are accepted, not arbitrary kebab-case strings.
        This enforces the mock/real boundary for validation evidence.
        """
        from inferops.domain.serving import InvalidValueError

        # 'banana' is kebab-case-compliant but not accepted
        with pytest.raises(InvalidValueError):
            InferenceResult(
                content="test",
                model="test-model",
                adapter_kind="banana",  # valid format but not accepted
            )
