"""Readiness: false until the runtime says otherwise, and false again if it stops.

The acceptance criterion this suite exists for is one sentence — *readiness
remains false until the model accepts requests* — and the only way to hold a type
to it is to try every way of getting a ``True`` out of one without an
observation. A tracker that has been constructed, reset, told the runtime is
loading, told something unrecognised, or told nothing at all must report not
ready, and exactly one input may change that.

The two status codes mapped here are the two the Sprint 0 trial observed: 503
while the model loads, 200 once it can answer. Everything else is unrecognised
rather than assumed temporary, because waiting forever on a permanently broken
runtime is the failure that assumption produces.

Every check reads objects from this distribution. No network, no cluster, no
model, no clock, no randomness, and no status code here came from a runtime.
"""

from __future__ import annotations

import pytest

from inferops.adapters.llama_cpp import (
    HEALTH_LOADING_STATUS,
    HEALTH_READY_STATUS,
    NOT_READY_MESSAGES,
    ReadinessState,
    ReadinessTracker,
    is_ready,
    map_health_status,
    readiness_error,
)
from inferops.domain import RequestContext
from inferops.domain.serving import ModelNotReadyError

pytestmark = pytest.mark.adapter

CONTEXT = RequestContext(request_id="test-req-004", correlation_id="test-corr-004")


# --------------------------------------------------------------------------
# The mapping
# --------------------------------------------------------------------------


def test_the_observed_status_codes_are_the_ones_the_trial_recorded() -> None:
    assert HEALTH_READY_STATUS == 200
    assert HEALTH_LOADING_STATUS == 503


def test_a_ready_status_maps_to_ready() -> None:
    assert map_health_status(HEALTH_READY_STATUS) is ReadinessState.READY


def test_a_loading_status_maps_to_loading() -> None:
    assert map_health_status(HEALTH_LOADING_STATUS) is ReadinessState.LOADING


@pytest.mark.parametrize("status_code", [0, 100, 204, 301, 400, 404, 429, 500, 502])
def test_any_other_status_is_unrecognised_rather_than_temporary(
    status_code: int,
) -> None:
    """Folding an unknown answer into 'loading' is how a wait becomes forever."""
    assert map_health_status(status_code) is ReadinessState.UNEXPECTED


@pytest.mark.parametrize("state", list(ReadinessState))
def test_exactly_one_state_is_ready(state: ReadinessState) -> None:
    assert is_ready(state) is (state is ReadinessState.READY)


# --------------------------------------------------------------------------
# The tracker, and the criterion it exists to hold
# --------------------------------------------------------------------------


def test_a_new_tracker_is_not_ready() -> None:
    """Readiness before any observation is the default that must not exist."""
    tracker = ReadinessTracker()
    assert tracker.state is ReadinessState.NOT_PROBED
    assert tracker.ready is False


def test_only_an_observed_ready_status_makes_a_tracker_ready() -> None:
    tracker = ReadinessTracker()
    for status_code in (503, 500, 404, 0):
        tracker.observe_health_status(status_code)
        assert tracker.ready is False
    tracker.observe_health_status(HEALTH_READY_STATUS)
    assert tracker.ready is True


def test_a_tracker_that_has_only_seen_a_loading_status_is_not_ready() -> None:
    tracker = ReadinessTracker()
    tracker.observe_health_status(HEALTH_LOADING_STATUS)
    assert tracker.state is ReadinessState.LOADING
    assert tracker.ready is False


def test_readiness_is_lost_again_when_the_runtime_reports_loading() -> None:
    """A replaced pod is a fresh process with a fresh load.

    A tracker that latched ``READY`` would keep sending requests to a runtime
    that has just said it cannot serve them.
    """
    tracker = ReadinessTracker()
    tracker.observe_health_status(HEALTH_READY_STATUS)
    assert tracker.ready is True
    tracker.observe_health_status(HEALTH_LOADING_STATUS)
    assert tracker.ready is False


def test_an_unreachable_runtime_is_not_ready() -> None:
    tracker = ReadinessTracker()
    tracker.observe_health_status(HEALTH_READY_STATUS)
    tracker.observe_unreachable()
    assert tracker.state is ReadinessState.UNREACHABLE
    assert tracker.ready is False


def test_reset_forgets_every_observation() -> None:
    """The previous observation described a process that is gone."""
    tracker = ReadinessTracker()
    tracker.observe_health_status(HEALTH_READY_STATUS)
    assert tracker.reset() is ReadinessState.NOT_PROBED
    assert tracker.ready is False


def test_a_tracker_exposes_no_way_to_assert_a_state() -> None:
    """Every public entry point records an observation; none sets one."""
    tracker = ReadinessTracker()
    # Through `setattr` rather than as an assignment, so the read-only property
    # refuses it at run time rather than the type checker refusing it first and
    # leaving the run-time guarantee unexercised. It is the idiom the domain
    # suite already uses, and it is why this repository still has no
    # `# type: ignore`.
    attribute = "state"
    with pytest.raises(AttributeError):
        setattr(tracker, attribute, ReadinessState.READY)
    assert tracker.ready is False


def test_observing_returns_the_state_it_produced() -> None:
    tracker = ReadinessTracker()
    assert tracker.observe_health_status(HEALTH_READY_STATUS) is ReadinessState.READY
    assert tracker.observe_unreachable() is ReadinessState.UNREACHABLE


# --------------------------------------------------------------------------
# The canonical error a not-ready state produces
# --------------------------------------------------------------------------


def test_a_ready_state_produces_no_error() -> None:
    assert readiness_error(ReadinessState.READY, CONTEXT) is None


@pytest.mark.parametrize(
    "state", [state for state in ReadinessState if state is not ReadinessState.READY]
)
def test_every_not_ready_state_produces_the_canonical_code(
    state: ReadinessState,
) -> None:
    error = readiness_error(state, CONTEXT)
    assert isinstance(error, ModelNotReadyError)
    assert error.code == "model-not-ready"


@pytest.mark.parametrize(
    "state", [state for state in ReadinessState if state is not ReadinessState.READY]
)
def test_every_not_ready_state_has_a_message_written_for_it(
    state: ReadinessState,
) -> None:
    """A state added without deciding what a caller is told is a missing key."""
    assert state in NOT_READY_MESSAGES
    assert NOT_READY_MESSAGES[state]


def test_the_error_preserves_the_supplied_correlation_identifiers() -> None:
    error = readiness_error(ReadinessState.LOADING, CONTEXT)
    assert error is not None
    assert error.context.request_id == "test-req-004"
    assert error.context.correlation_id == "test-corr-004"


@pytest.mark.parametrize(
    "state", [state for state in ReadinessState if state is not ReadinessState.READY]
)
def test_the_error_carries_no_status_code_and_no_endpoint(
    state: ReadinessState,
) -> None:
    """A runtime's own words are where a host name reaches a caller's error."""
    error = readiness_error(state, CONTEXT)
    assert error is not None
    body = str(error.as_dict())
    assert "503" not in body
    assert "http" not in body
