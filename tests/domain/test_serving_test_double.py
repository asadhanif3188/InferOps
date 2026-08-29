"""Adapter-specific tests for the in-memory serving test double.

The conformance suite in ``test_serving_adapter_conformance.py`` uses only what
the ``ServingAdapter`` protocol publishes, so it can validate any adapter. Some
obligations cannot be exercised that way: a not-ready adapter, an adapter with
token counting switched off, and the bookkeeping an implementation keeps for
initialization and shutdown are all reached through members the protocol does
not declare.

Those tests live here, bound to ``MinimalTestDouble`` deliberately. A real
adapter drives the same scenarios through its own means (an unreachable
runtime, a model still loading) and carries its own file alongside the shared
conformance suite.

What this does not establish: protocol conformance. That is the other file's
job, and the double is run through it via the ``adapter_factory`` fixture.
"""

from __future__ import annotations

import pytest

from inferops.domain import RequestContext
from inferops.domain.serving import (
    AdapterConfiguration,
    MinimalTestDouble,
    ModelNotReadyError,
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


class TestInitializationState:
    """Tests for the double's initialization bookkeeping."""

    async def test_initialize_marks_adapter_initialized(
        self,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify the double records that initialization happened."""
        adapter = MinimalTestDouble()
        assert not adapter.initialized

        await adapter.initialize(test_config, test_context)

        assert adapter.initialized

    async def test_shutdown_clears_initialized(
        self,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify shutdown returns the double to its uninitialized state."""
        adapter = MinimalTestDouble()
        await adapter.initialize(test_config, test_context)

        await adapter.shutdown(test_context)

        assert not adapter.initialized


class TestReadinessState:
    """Tests for inference against a not-ready double."""

    async def test_is_ready_reflects_configured_state(
        self,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify is_ready reports the state the double was built with."""
        ready = MinimalTestDouble(model_ready=True)
        not_ready = MinimalTestDouble(model_ready=False)
        await ready.initialize(test_config, test_context)
        await not_ready.initialize(test_config, test_context)

        assert await ready.is_ready(test_context) is True
        assert await not_ready.is_ready(test_context) is False

    async def test_infer_fails_when_not_ready(
        self,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify inference against a loading model raises ModelNotReadyError."""
        adapter = MinimalTestDouble(model_ready=False)
        await adapter.initialize(test_config, test_context)

        with pytest.raises(ModelNotReadyError):
            await adapter.infer("test prompt", test_context)

    async def test_infer_error_preserves_request_context(
        self,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify errors from infer() carry the request and correlation IDs.

        The conformance suite covers context preservation through
        ``map_error_to_canonical``; this covers the path where the adapter
        raises the canonical error itself.
        """
        adapter = MinimalTestDouble(model_ready=False)
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


class TestTokenCountingCapability:
    """Tests for the optional token-counting capability."""

    async def test_capability_declaration_follows_configuration(
        self,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify the declared capability matches how the double was built."""
        with_counting = MinimalTestDouble(should_support_token_counting=True)
        without_counting = MinimalTestDouble(should_support_token_counting=False)
        await with_counting.initialize(test_config, test_context)
        await without_counting.initialize(test_config, test_context)

        declared = {c.name: c.supported for c in await with_counting.get_capabilities()}
        undeclared = {
            c.name: c.supported for c in await without_counting.get_capabilities()
        }

        assert declared["token-counting"] is True
        assert undeclared["token-counting"] is False

    async def test_usage_present_when_token_counting_supported(
        self,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify a result carries token usage when the capability is declared."""
        adapter = MinimalTestDouble(should_support_token_counting=True)
        await adapter.initialize(test_config, test_context)

        result = await adapter.infer("one two three", test_context)

        assert isinstance(result.usage, TokenUsage)
        assert result.usage.input_tokens == 3

    async def test_usage_absent_when_token_counting_unsupported(
        self,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify absence is preserved when the capability is not declared.

        ``usage`` is None because the capability is absent, not because a value
        happened to be missing from a response.
        """
        adapter = MinimalTestDouble(should_support_token_counting=False)
        await adapter.initialize(test_config, test_context)

        result = await adapter.infer("one two three", test_context)

        assert result.usage is None


class TestAdapterKindProvenance:
    """Tests for the provenance this particular adapter reports."""

    async def test_double_always_reports_mock(
        self,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Verify the in-memory double never claims to be a real adapter."""
        adapter = MinimalTestDouble()
        await adapter.initialize(test_config, test_context)

        result = await adapter.infer("test prompt", test_context)

        assert result.adapter_kind == "mock"
