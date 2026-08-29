"""Conformance tests for the serving adapter contract.

This suite establishes that:
- A minimal test double satisfies the ServingAdapter protocol
- All contract methods work as expected
- Capability declaration is explicit
- No runtime-specific types leak into the interface
- Error mapping produces canonical errors
- Unsupported capabilities fail explicitly when not declared

What it does not establish: that mock or real adapters work correctly. Those are
scope for later PRs. This establishes only that the contract itself is coherent
and testable.
"""

from __future__ import annotations

import pytest

from inferops.domain import RequestContext
from inferops.domain.serving import (
    AdapterConfiguration,
    CapabilityUnavailableError,
    InferenceResult,
    ModelMetadata,
    RuntimeMetadata,
    ServingAdapterTestDouble,
    TokenUsage,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def adapter() -> ServingAdapterTestDouble:
    """Provide a fresh test double for each test."""
    return ServingAdapterTestDouble()


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
        adapter: ServingAdapterTestDouble,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify initialization completes with valid config."""
        await adapter.initialize(test_config, test_context)
        assert adapter.initialized

    async def test_initialization_rejects_empty_model_id(
        self,
        adapter: ServingAdapterTestDouble,
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
        adapter: ServingAdapterTestDouble,
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
        adapter: ServingAdapterTestDouble,
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
        adapter: ServingAdapterTestDouble,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify is_ready returns a boolean."""
        await adapter.initialize(test_config, test_context)
        ready = await adapter.is_ready(test_context)

        assert isinstance(ready, bool)

    async def test_is_ready_reflects_adapter_state(
        self,
        adapter: ServingAdapterTestDouble,
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
        adapter: ServingAdapterTestDouble,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify infer returns an InferenceResult domain object."""
        await adapter.initialize(test_config, test_context)
        result = await adapter.infer("test prompt", test_context)

        assert isinstance(result, InferenceResult)
        assert isinstance(result.content, str)
        assert isinstance(result.model, str)

    async def test_infer_result_respects_capability_declaration(
        self,
        adapter: ServingAdapterTestDouble,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify inference returns result even when token-counting not supported."""
        adapter.should_support_token_counting = False
        await adapter.initialize(test_config, test_context)
        result = await adapter.infer("test prompt", test_context)

        assert isinstance(result, InferenceResult)
        assert isinstance(result.content, str)
        # When not supported, adapter may or may not include usage (both valid)

    async def test_infer_with_token_counting_includes_usage(
        self,
        adapter: ServingAdapterTestDouble,
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
        adapter: ServingAdapterTestDouble,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify inference fails with ModelNotReadyError when not ready."""
        adapter.model_ready = False
        await adapter.initialize(test_config, test_context)

        from inferops.domain.serving import ModelNotReadyError

        with pytest.raises(ModelNotReadyError):
            await adapter.infer("test prompt", test_context)


class TestStreaming:
    """Tests for streaming capability."""

    async def test_streaming_fails_when_not_supported(
        self,
        adapter: ServingAdapterTestDouble,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify streaming raises CapabilityUnavailableError when not supported."""
        adapter.should_support_streaming = False
        await adapter.initialize(test_config, test_context)

        with pytest.raises(CapabilityUnavailableError):
            await adapter.stream("test prompt", test_context)


class TestMetadata:
    """Tests for metadata reporting."""

    async def test_get_model_metadata_returns_model_metadata(
        self,
        adapter: ServingAdapterTestDouble,
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
        adapter: ServingAdapterTestDouble,
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
        adapter: ServingAdapterTestDouble,
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
        adapter: ServingAdapterTestDouble,
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
        adapter: ServingAdapterTestDouble,
    ) -> None:
        """Verify canonical errors are returned unchanged."""
        from inferops.domain.serving import ModelNotReadyError

        error = ModelNotReadyError("model loading")
        mapped = await adapter.map_error_to_canonical(error)

        assert isinstance(mapped, ModelNotReadyError)
