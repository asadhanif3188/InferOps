"""Shared fixtures for domain tests.

This conftest enables reusable conformance tests for serving adapters.
Future adapters can override the adapter_factory fixture to test their
implementation against the contract harness.
"""

from __future__ import annotations

import pytest

from inferops.domain.serving import ServingAdapter, ServingAdapterTestDouble


@pytest.fixture
def adapter_factory() -> type[ServingAdapter]:
    """Factory for creating adapter instances under test.

    Override this fixture in a subproject's conftest.py to test a different
    adapter implementation:

        @pytest.fixture
        def adapter_factory():
            from my_adapter import MyRealAdapter
            return MyRealAdapter

    The conformance test suite (test_serving_adapter_conformance.py) uses this
    fixture to instantiate adapters, so overriding it enables the same tests
    to validate any adapter without duplication.
    """
    return ServingAdapterTestDouble


@pytest.fixture
def adapter(adapter_factory: type[ServingAdapter]) -> ServingAdapter:
    """Provide a fresh adapter instance for each test.

    Uses adapter_factory so that tests can work with any adapter implementation.
    """
    return adapter_factory()
