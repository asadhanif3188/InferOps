"""The mock serving adapter against the shared conformance suite.

The assertions are not written here. They are inherited from
:class:`tests.support.serving_conformance.ServingAdapterConformance`, the same
suite the in-memory double is held to, so that "the mock implements the contract"
means the contract and not a version of it edited until the mock passed.

This module supplies two things and nothing else: the adapter, and a
configuration it accepts. The configuration names a mock-labelled model identity
because the adapter refuses any other, which is itself one of the safeguards and
is asserted in ``test_mock_serving_adapter.py``.

Evidence class: `mock`. Ceiling: `C1`. A passing run here establishes that a
consumer and the contract agree, and nothing at all about a serving runtime.
"""

from __future__ import annotations

import pytest

from inferops.adapters import MOCK_MODEL_IDENTIFIER, MockServingAdapter
from inferops.domain.serving import AdapterConfiguration, ServingAdapter
from tests.support.serving_conformance import ServingAdapterConformance

pytestmark = pytest.mark.adapter


class TestMockServingAdapterConformance(ServingAdapterConformance):
    """The mock, held to every obligation the protocol publishes."""

    @pytest.fixture
    def adapter(self) -> ServingAdapter:
        """A mock adapter in its default configuration: succeed, no latency."""
        return MockServingAdapter()

    @pytest.fixture
    def test_config(self) -> AdapterConfiguration:
        """A configuration naming the mock model identity the fixture declares."""
        return AdapterConfiguration(
            model_identifier=MOCK_MODEL_IDENTIFIER,
            timeout_ms=30000,
        )
