"""The in-memory test double against the shared conformance suite.

The suite itself lives in :mod:`tests.support.serving_conformance` and is
inherited rather than copied, which is what makes it reusable: the mock adapter's
suite under ``tests/adapters/`` inherits exactly the same assertions and supplies
its own adapter. A conformance test written here would be a test the mock is not
held to.

What stays in this module is what belongs to the domain rather than to an
adapter: the closed vocabulary an ``InferenceResult`` may declare, the metric
catalog a ``TelemetryMapping`` may name, and the absence of a streaming method on
the protocol itself. None of those needs an adapter to exercise.

Scenarios that need the double driven into a state the protocol cannot reach — a
not-ready adapter, token counting switched off — are in
``test_serving_test_double.py``.

Every check here reads objects from this distribution and nothing else. No
network, no cluster, no model, no clock, no randomness.
"""

from __future__ import annotations

import pytest

from inferops.domain.serving import (
    AdapterConfiguration,
    InferenceResult,
    InvalidValueError,
    ServingAdapter,
    TelemetryMapping,
)
from tests.support.serving_conformance import ServingAdapterConformance

pytestmark = pytest.mark.unit


class TestMinimalTestDoubleConformance(ServingAdapterConformance):
    """The in-memory double, held to every obligation the protocol publishes."""

    @pytest.fixture
    def adapter(self, adapter_factory: type[ServingAdapter]) -> ServingAdapter:
        """The double, built through the factory ``conftest.py`` publishes."""
        return adapter_factory()

    @pytest.fixture
    def test_config(self) -> AdapterConfiguration:
        """A configuration the double accepts."""
        return AdapterConfiguration(
            model_identifier="test-model",
            timeout_ms=30000,
        )


class TestTheProtocolItself:
    """Obligations of the interface, exercised without any implementation."""

    def test_no_stream_method_exists_on_the_protocol(self) -> None:
        """V1 declares streaming as a capability and offers no method for it."""
        assert not hasattr(ServingAdapter, "stream"), (
            "V1 protocol must have no stream() method; streaming is a capability only"
        )

    def test_configuration_rejects_an_empty_model_identifier(self) -> None:
        """A configuration that cannot name a model refuses itself."""
        with pytest.raises(InvalidValueError):
            AdapterConfiguration(model_identifier="", timeout_ms=30000)


class TestAdapterKindValidation:
    """Adapter kind is a closed vocabulary, not a format.

    ``mock`` and ``real`` are the two members. The mock and real boundary is what
    makes the distinction load-bearing: provenance has to be verifiable, and a
    value that merely looks well-formed is not.
    """

    def test_adapter_kind_must_be_lowercase_kebab_case(self) -> None:
        """Verify adapter_kind must be lowercase kebab-case format."""
        with pytest.raises(InvalidValueError):
            InferenceResult(
                content="test",
                model="test-model",
                adapter_kind="Mock",  # uppercase rejected
            )

    def test_adapter_kind_must_not_be_empty(self) -> None:
        """Verify adapter_kind cannot be empty."""
        with pytest.raises(InvalidValueError):
            InferenceResult(
                content="test",
                model="test-model",
                adapter_kind="",  # empty rejected
            )

    def test_adapter_kind_must_be_an_accepted_value(self) -> None:
        """Only 'mock' and 'real' are accepted, not arbitrary kebab-case."""
        with pytest.raises(InvalidValueError):
            InferenceResult(
                content="test",
                model="test-model",
                adapter_kind="banana",  # valid format but not accepted
            )


class TestTelemetryMetricValidation:
    """Adapters report only metrics from the accepted platform catalog.

    Per ADR 0006 and ADR 0002, an arbitrary identifier is rejected even when it
    is well-formed, and the platform-owned prefixes are not available at all.
    """

    def test_adapter_cannot_report_arbitrary_metric_names(self) -> None:
        """A well-formed identifier outside the catalog is still refused."""
        with pytest.raises(InvalidValueError, match="not in accepted platform catalog"):
            TelemetryMapping(platform_metric_ids=("banana",))

    def test_adapter_cannot_report_reserved_prefixes(self) -> None:
        """Platform-owned metrics are not available for adapter reporting."""
        with pytest.raises(InvalidValueError, match="not in accepted platform catalog"):
            TelemetryMapping(platform_metric_ids=("inferops_inference_requests_total",))

        with pytest.raises(InvalidValueError, match="not in accepted platform catalog"):
            TelemetryMapping(platform_metric_ids=("platform_custom_metric",))
