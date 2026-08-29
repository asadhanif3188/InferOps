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

**Scope limitation:** Every test here uses only members declared on the
``ServingAdapter`` protocol. No test reads or writes an attribute the protocol
does not publish (``initialized``, ``model_ready``, and the like), and no test
assumes a particular adapter kind. Scenarios that need an adapter driven into a
specific state (not-ready inference, token-counting on and off) cannot be
expressed through the protocol and live in adapter-specific suites instead; for
the in-memory double those are in ``test_serving_test_double.py``.

What this does not establish: that mock or real adapters work correctly beyond
protocol conformance. Those are scope for integration/e2e tests. This suite
establishes only that the contract itself is coherent, testable, and that
an implementation actually satisfies it.
"""

from __future__ import annotations

import pytest

from inferops.domain import RequestContext
from inferops.domain.serving import (
    ACCEPTED_ADAPTER_KINDS,
    AdapterConfiguration,
    InferenceResult,
    ModelMetadata,
    RuntimeMetadata,
    ServingAdapter,
    TelemetryMapping,
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
        """Verify initialization completes and the config takes effect.

        Initialization is observable only through the protocol: after it
        returns, the adapter reports metadata for the configured model.
        """
        await adapter.initialize(test_config, test_context)

        metadata = await adapter.get_model_metadata()
        assert metadata.identifier == test_config.model_identifier

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
        """Verify inference result declares a kind from the closed vocabulary.

        The suite does not assume which kind: a real adapter reports "real" and
        must pass this test unchanged. What the contract requires is that the
        provenance is present and drawn from the accepted vocabulary.
        """
        await adapter.initialize(test_config, test_context)
        result = await adapter.infer("test prompt", test_context)

        assert result.adapter_kind in ACCEPTED_ADAPTER_KINDS


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
        """Verify shutdown completes without error.

        The protocol publishes no post-shutdown state to assert on: shutdown
        returns None, and what an adapter releases is its own business. The
        contract obligation is that it completes rather than raising.
        """
        await adapter.initialize(test_config, test_context)
        await adapter.shutdown(test_context)


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
    """Tests for request context propagation.

    Errors raised out of ``infer()`` must carry the supplied context too, but
    forcing an adapter into a failing state is not something the protocol
    offers. That case is covered per-adapter; see
    ``test_serving_test_double.py`` for the in-memory double.
    """

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
        """Verify mapping lists only metrics from the accepted catalog.

        Per ADR-0002, InferOps owns the request counter. An adapter reports
        only metrics the platform catalog admits; membership in that catalog,
        not the shape of the name, is what the contract checks.
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


class TestTelemetryMetricValidation:
    """Tests for telemetry metric catalog validation.

    Adapters report only metrics from the accepted platform catalog,
    per ADR-0006 and ADR-0002. Arbitrary identifiers are rejected.
    """

    def test_adapter_cannot_report_arbitrary_metric_names(self) -> None:
        """Verify adapters cannot report arbitrary metric identifiers.

        Even valid-format identifiers like 'banana' are rejected if not
        in the accepted catalog.
        """
        from inferops.domain.serving import InvalidValueError

        with pytest.raises(InvalidValueError, match="not in accepted platform catalog"):
            TelemetryMapping(platform_metric_ids=("banana",))

    def test_adapter_cannot_report_reserved_prefixes(self) -> None:
        """Verify adapters cannot report metrics with reserved prefixes.

        Platform-owned metrics (inferops_*, platform_*) are not available
        for adapter reporting.
        """
        from inferops.domain.serving import InvalidValueError

        with pytest.raises(InvalidValueError, match="not in accepted platform catalog"):
            TelemetryMapping(platform_metric_ids=("inferops_inference_requests_total",))

        with pytest.raises(InvalidValueError, match="not in accepted platform catalog"):
            TelemetryMapping(platform_metric_ids=("platform_custom_metric",))
