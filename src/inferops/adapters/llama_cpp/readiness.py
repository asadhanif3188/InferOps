"""Readiness for `llama-server`, as a state that only an observation can change.

The runtime's health endpoint returns **503 while the model loads** and **200
once it can answer**. That is the single most consequential behaviour the Sprint
0 trial found, and it is behaviour no mock could have surfaced: it is correct
readiness reporting and wrong liveness reporting, so a liveness probe aimed at it
restarts the pod mid-load and never converges. The trial's manifest points the
startup and readiness probes at health and the liveness probe at the TCP socket
for exactly that reason, and seven starts produced zero restarts.

This module is the platform's half of the same mapping. It holds one rule that
is worth stating on its own:

**Readiness is false until the runtime has said otherwise.** A tracker begins in
:attr:`ReadinessState.NOT_PROBED` and only an observed ``200`` moves it to
:attr:`ReadinessState.READY`. There is no optimistic default, no "assume ready
until proven otherwise", and no way to construct a ready tracker without an
observation — which is what makes "readiness remains false until the model
accepts requests" a property of the type rather than a promise in a document.

**Nothing here performs the observation.** A tracker is fed a status code; the
transport that obtains one arrives with the inference client. The
:attr:`ReadinessState.UNREACHABLE` member exists so that the transport has a
state to report into rather than inventing one, and it is reachable today only
through :meth:`ReadinessTracker.observe_unreachable`.
"""

from __future__ import annotations

from enum import StrEnum

from ...domain.context import RequestContext
from ...domain.serving import ModelNotReadyError

#: What the runtime answers once the model can accept requests.
HEALTH_READY_STATUS = 200

#: What the runtime answers while the model is still loading. Observed directly
#: from the control plane during the first start of the feasibility trial.
HEALTH_LOADING_STATUS = 503


class ReadinessState(StrEnum):
    """Where the runtime is, as far as this platform has been told.

    Four members, and the distinction between the last three is deliberate. A
    caller that collapsed them would lose the difference between *the runtime
    answered and is loading*, *the runtime answered something nobody expected*,
    and *the runtime did not answer at all* — which are three different
    operational situations with the same effect on a request.
    """

    #: Nothing has been observed yet. The state every tracker starts in.
    NOT_PROBED = "not-probed"

    #: The runtime answered that it is not ready. The model is loading.
    LOADING = "loading"

    #: The runtime answered that it can accept requests.
    READY = "ready"

    #: The runtime answered with a status this mapping does not publish.
    UNEXPECTED = "unexpected-status"

    #: The runtime could not be reached at all.
    UNREACHABLE = "unreachable"


def map_health_status(status_code: int) -> ReadinessState:
    """Translate one health status code into a readiness state.

    Only the two codes the trial observed are mapped. Everything else becomes
    :attr:`ReadinessState.UNEXPECTED` rather than being folded into "loading",
    because treating an unknown answer as a temporary one is how a permanently
    broken runtime is waited on forever.
    """
    if status_code == HEALTH_READY_STATUS:
        return ReadinessState.READY
    if status_code == HEALTH_LOADING_STATUS:
        return ReadinessState.LOADING
    return ReadinessState.UNEXPECTED


def is_ready(state: ReadinessState) -> bool:
    """True for exactly one state, and it is the one an observation produced."""
    return state is ReadinessState.READY


#: The message each not-ready state produces. A mapping rather than a chain of
#: conditionals, so that adding a state without deciding what a caller is told is
#: a missing key rather than a silent fall-through to a generic message.
NOT_READY_MESSAGES = {
    ReadinessState.NOT_PROBED: "the runtime has not yet reported its readiness",
    ReadinessState.LOADING: "the runtime is loading the model",
    ReadinessState.UNEXPECTED: "the runtime reported a readiness status this "
    "adapter does not recognise",
    ReadinessState.UNREACHABLE: "the runtime could not be reached",
}


def readiness_error(
    state: ReadinessState,
    context: RequestContext,
) -> ModelNotReadyError | None:
    """The canonical error a not-ready state produces, or ``None`` when ready.

    The message names the state in this module's own vocabulary and carries no
    status code, no response body, and no endpoint. A runtime's own words are
    where a path or a host name arrives in a caller's error, and a caller does
    not need them to know that the model is not ready.
    """
    if state is ReadinessState.READY:
        return None
    return ModelNotReadyError(NOT_READY_MESSAGES[state], context=context)


class ReadinessTracker:
    """The readiness of one runtime deployment, as last observed.

    Mutable by design and by exactly three methods, each of which records an
    observation. There is no setter: a state cannot be asserted, only observed.
    """

    def __init__(self) -> None:
        self._state = ReadinessState.NOT_PROBED

    @property
    def state(self) -> ReadinessState:
        """The last observed state, or ``NOT_PROBED`` if nothing was observed."""
        return self._state

    @property
    def ready(self) -> bool:
        """Whether the runtime last said it can accept requests."""
        return is_ready(self._state)

    def observe_health_status(self, status_code: int) -> ReadinessState:
        """Record one health response and return the state it produced.

        A ready runtime that later answers 503 becomes ``LOADING`` again. That is
        not a defect being papered over: a replaced pod is a fresh process with a
        fresh load, and a tracker that latched ``READY`` would keep sending
        requests to a runtime that has said it cannot serve them.
        """
        self._state = map_health_status(status_code)
        return self._state

    def observe_unreachable(self) -> ReadinessState:
        """Record that the runtime could not be reached."""
        self._state = ReadinessState.UNREACHABLE
        return self._state

    def reset(self) -> ReadinessState:
        """Forget every observation, returning to the state a tracker starts in.

        Used when the deployment behind the tracker is replaced or the adapter is
        shut down. Forgetting is the honest operation: the previous observation
        described a process that is gone.
        """
        self._state = ReadinessState.NOT_PROBED
        return self._state
