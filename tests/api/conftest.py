"""Fixtures the API suites share.

The composition itself lives in :mod:`tests.support.api_composition`, so that a
suite can build an application without going through a fixture when it needs to
control the construction — and so that the helpers are importable by name rather
than through the implicit conftest namespace.
"""

from __future__ import annotations

import pytest

from inferops.adapters import MockServingAdapter
from inferops.api import InferOpsApi
from tests.support.api_composition import RecordingAdapter, build


@pytest.fixture
def mock_adapter() -> MockServingAdapter:
    """The committed mock adapter, uninitialized."""
    return MockServingAdapter()


@pytest.fixture
async def mock_api(mock_adapter: MockServingAdapter) -> InferOpsApi:
    """An application serving the committed mock adapter, already started."""
    api = build(mock_adapter)
    await api.startup()
    return api


@pytest.fixture
def recording_adapter() -> RecordingAdapter:
    """A controlled adapter that records what it was handed."""
    return RecordingAdapter()


@pytest.fixture
async def recording_api(recording_adapter: RecordingAdapter) -> InferOpsApi:
    """An application serving the controlled adapter, already started."""
    api = build(recording_adapter)
    await api.startup()
    return api
