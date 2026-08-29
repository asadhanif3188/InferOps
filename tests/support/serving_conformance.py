"""The serving-adapter conformance suite, written once and inherited.

Every obligation the ``ServingAdapter`` protocol publishes is asserted here, and
only through members the protocol publishes: no test reads an attribute an
implementation happens to expose, and none assumes a particular adapter kind. An
adapter suite subclasses :class:`ServingAdapterConformance`, supplies an
``adapter`` and a ``test_config``, and inherits the whole thing::

    class TestMyAdapterConformance(ServingAdapterConformance):
        @pytest.fixture
        def adapter(self):
            return MyAdapter()

        @pytest.fixture
        def test_config(self):
            return AdapterConfiguration(model_identifier="...", timeout_ms=30000)

This module is deliberately not named ``test_*``: it is imported, never
collected, so the assertions run once per adapter that inherits them rather than
once here on nobody's behalf.

Two kinds of test are **not** here. Ones that need an adapter driven into a state
the protocol cannot reach — a not-ready adapter, an injected failure — live in
that adapter's own suite. Ones that exercise a domain value object rather than an
adapter live with the domain.

What this establishes is that an implementation satisfies the contract. It does
not establish that the implementation is correct beyond it, and for a mock it
establishes nothing whatsoever about a serving runtime.
"""

from __future__ import annotations

import pytest

from inferops.domain import RequestContext
from inferops.domain.serving import (
    ACCEPTED_ADAPTER_KINDS,
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

#: The canonical error codes this story introduced.
CANONICAL_ERROR_CODES = frozenset(
    {
        "model-not-ready",
        "request-timeout",
        "upstream-timeout",
        "rate-limited",
        "capability-unavailable",
        "internal-error",
    }
)

#: A metric InferOps owns and no adapter may report. ADR 0002 records that the
#: selected runtime exposes no cumulative request counter, so the platform
#: produces this one.
PLATFORM_OWNED_METRIC = "inferops_inference_requests_total"


class ServingAdapterConformance:
    """The contract, as tests. Subclass it; do not copy it."""

    @pytest.fixture
    def adapter(self) -> ServingAdapter:
        """The adapter under test. A conformance subclass provides this."""
        raise NotImplementedError(
            "a ServingAdapterConformance subclass provides an `adapter` fixture"
        )

    @pytest.fixture
    def test_config(self) -> AdapterConfiguration:
        """A configuration the adapter under test accepts."""
        raise NotImplementedError(
            "a ServingAdapterConformance subclass provides a `test_config` fixture"
        )

    @pytest.fixture
    def test_context(self) -> RequestContext:
        """Request identifiers a caller supplied."""
        return RequestContext(
            request_id="test-req-001",
            correlation_id="test-corr-002",
        )

    # -- initialization --------------------------------------------------

    async def test_initialization_reports_the_configured_model(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Initialization is observable only through the protocol.

        After it returns, the adapter reports metadata for the model it was
        configured with. Whatever bookkeeping an implementation keeps is its own
        business and is not asserted here.
        """
        await adapter.initialize(test_config, test_context)

        metadata = await adapter.get_model_metadata()
        assert metadata.identifier == test_config.model_identifier

    # -- capabilities ----------------------------------------------------

    async def test_get_capabilities_returns_capability_objects(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Capabilities are declared as domain objects, not as loose strings."""
        await adapter.initialize(test_config, test_context)
        capabilities = await adapter.get_capabilities()

        assert isinstance(capabilities, list)
        assert capabilities
        assert all(isinstance(item, AdapterCapability) for item in capabilities)

    async def test_capabilities_include_streaming_and_token_counting(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Both optional capabilities are declared rather than assumed.

        Declaring one unsupported is a passing answer. Not declaring it at all is
        the failure: a caller then has to guess, and a guess about token metrics
        is how an invented number reaches a record.
        """
        await adapter.initialize(test_config, test_context)
        names = {item.name for item in await adapter.get_capabilities()}

        assert "streaming" in names
        assert "token-counting" in names

    async def test_streaming_is_declared_unsupported(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """V1 is synchronous-only, so no adapter may declare streaming."""
        await adapter.initialize(test_config, test_context)
        capabilities = await adapter.get_capabilities()
        streaming = next(item for item in capabilities if item.name == "streaming")

        assert streaming.supported is False, (
            "V1 has no streaming method; an adapter declaring streaming supported "
            "promises a call nobody can make"
        )

    # -- readiness -------------------------------------------------------

    async def test_is_ready_returns_a_boolean(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Readiness is a decision the adapter has already made, not a status."""
        await adapter.initialize(test_config, test_context)

        assert isinstance(await adapter.is_ready(test_context), bool)

    # -- inference -------------------------------------------------------

    async def test_infer_returns_an_inference_result(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Inference returns a domain object, not a runtime's response body."""
        await adapter.initialize(test_config, test_context)
        result = await adapter.infer("test prompt", test_context)

        assert isinstance(result, InferenceResult)
        assert isinstance(result.content, str)
        assert isinstance(result.model, str)

    async def test_infer_result_declares_an_accepted_adapter_kind(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Provenance is present and drawn from the closed vocabulary.

        Which kind is not asserted: a real adapter reports ``real`` and passes
        this unchanged. What the contract requires is that a result says which it
        was.
        """
        await adapter.initialize(test_config, test_context)
        result = await adapter.infer("test prompt", test_context)

        assert result.adapter_kind in ACCEPTED_ADAPTER_KINDS

    # -- metadata --------------------------------------------------------

    async def test_get_model_metadata_returns_model_metadata(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Model metadata is a domain object naming the configured model."""
        await adapter.initialize(test_config, test_context)
        metadata = await adapter.get_model_metadata()

        assert isinstance(metadata, ModelMetadata)
        assert metadata.identifier == test_config.model_identifier

    async def test_get_runtime_metadata_returns_runtime_metadata(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Runtime metadata names the thing on the other end of the call."""
        await adapter.initialize(test_config, test_context)
        metadata = await adapter.get_runtime_metadata()

        assert isinstance(metadata, RuntimeMetadata)
        assert metadata.name
        assert metadata.version

    # -- shutdown --------------------------------------------------------

    async def test_shutdown_completes(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """Shutdown returns rather than raising.

        The protocol publishes no post-shutdown state to assert on, and what an
        implementation releases is its own business.
        """
        await adapter.initialize(test_config, test_context)
        await adapter.shutdown(test_context)

    # -- error mapping ---------------------------------------------------

    async def test_map_error_returns_a_canonical_error(
        self,
        adapter: ServingAdapter,
    ) -> None:
        """An unrecognised error becomes a canonical one with a published code."""
        mapped = await adapter.map_error_to_canonical(ValueError("test error"))

        assert isinstance(mapped, CanonicalError)
        assert mapped.code in CANONICAL_ERROR_CODES

    async def test_map_error_passes_canonical_errors_through(
        self,
        adapter: ServingAdapter,
    ) -> None:
        """An error that is already canonical is returned unchanged."""
        mapped = await adapter.map_error_to_canonical(ModelNotReadyError("loading"))

        assert isinstance(mapped, ModelNotReadyError)

    async def test_map_error_does_not_repeat_the_original_message(
        self,
        adapter: ServingAdapter,
    ) -> None:
        """A runtime message is where a path or a credential arrives.

        The mapped error carries a code and a message the contract publishes, and
        never the text of the error it was given.
        """
        secret_shaped = "ghp_1234567890abcdefghijklmnopqrst"
        mapped = await adapter.map_error_to_canonical(ValueError(secret_shaped))

        assert secret_shaped not in mapped.message
        assert secret_shaped not in str(mapped.as_dict())

    async def test_map_error_preserves_supplied_context(
        self,
        adapter: ServingAdapter,
    ) -> None:
        """Correlation survives translation, or a refusal is untraceable."""
        context = RequestContext(
            request_id="test-req-789",
            correlation_id="test-corr-012",
        )
        mapped = await adapter.map_error_to_canonical(ValueError("unknown"), context)

        assert isinstance(mapped, InternalError)
        assert mapped.context.request_id == "test-req-789"
        assert mapped.context.correlation_id == "test-corr-012"

    # -- telemetry mapping -----------------------------------------------

    async def test_get_telemetry_mapping_returns_a_mapping(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """The mapping is a domain object with an immutable metric list."""
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
        """A telemetry error code is one the contract publishes, or absent."""
        await adapter.initialize(test_config, test_context)
        mapping = await adapter.get_telemetry_mapping()

        if mapping.error_code is not None:
            assert mapping.error_code in CANONICAL_ERROR_CODES

    async def test_telemetry_mapping_lists_only_platform_metrics(
        self,
        adapter: ServingAdapter,
        test_context: RequestContext,
        test_config: AdapterConfiguration,
    ) -> None:
        """An adapter reports only metrics the platform catalog admits.

        The request counter is InferOps's to produce, and an adapter reporting it
        would be the platform reading its own number back.
        """
        await adapter.initialize(test_config, test_context)
        mapping = await adapter.get_telemetry_mapping()

        assert all(isinstance(item, str) for item in mapping.platform_metric_ids)
        assert PLATFORM_OWNED_METRIC not in mapping.platform_metric_ids
