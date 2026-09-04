"""Starting, serving, draining, and stopping — and what each state answers.

`ADR 0010` declines to give this API a shutdown endpoint. An HTTP route that
stops a process would be an unauthenticated remote-stop control on a surface
`ADR 0008` `D4` accepts with no authentication in V1, so graceful shutdown is met
by the equivalent the accepted record names: **readiness goes false, what is in
flight drains, and the process exits.** This module is that equivalent, and it is
a state machine rather than a flag because the ordering is the whole property.

**The order is fixed and it is the point.** ``begin_shutdown`` flips readiness
false *before* anything is drained, so a load balancer or a Kubernetes readiness
probe stops sending new work while the work already accepted is still running. A
process that drains first and then reports itself unready has spent the drain
window receiving exactly the requests it was trying to finish without.

**A request in flight is tracked by the object that answers it**, through
:meth:`ApplicationLifecycle.accept`. That method is what refuses new work once
draining has started, which is why accepting and tracking are one call: a check
followed by a separate registration is a window in which a request is accepted
and not counted, and a drain that misses it exits underneath it.

**The drain is bounded and reports whether it finished.** An unbounded drain is a
process that will not exit, and a Kubernetes termination grace period ends in
`SIGKILL` regardless of what this code would have preferred. ``drain`` returns
whether everything finished inside the budget, so a caller can record a
truncated drain rather than discover it in a log.

**Signal handling is installed by a caller, not by importing this module.**
:func:`install_termination_handlers` takes the running loop and registers
``SIGTERM`` — and ``SIGINT``, so a local run behaves the same way — on the
platforms that support it. It is a function rather than an import side effect
because a library that installs a process-wide signal handler when it is imported
takes a decision away from the program that imported it. On Windows,
``loop.add_signal_handler`` raises :class:`NotImplementedError`; the function
reports that rather than swallowing it, so a caller knows the equivalent is not
installed rather than assuming it is.
"""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum

#: The default budget a drain is given, in milliseconds. It is a default rather
#: than a decision: `ADR 0002` decides no concurrency limit, and no drain has
#: been measured, so there is nothing to derive one from.
#:
#: It is no longer unrelated to a termination grace period. The Helm chart
#: configures one, and refuses a values file where it does not cover this budget
#: and the pre-stop pause together — because a grace period that expires
#: mid-drain ends in `SIGKILL`, and the drain this module performs was then
#: decoration. Nothing has installed that chart, so the relationship is between
#: two configured numbers and not between two observed behaviours.
DEFAULT_DRAIN_TIMEOUT_MS = 15_000

#: How often the drain loop checks whether the in-flight count has reached zero.
#: A poll rather than a condition variable because the count is changed from the
#: same event loop that waits on it, and a short sleep is the smaller thing.
DRAIN_POLL_SECONDS = 0.01

#: The signals a termination handler is installed for.
TERMINATION_SIGNALS: tuple[signal.Signals, ...] = (signal.SIGTERM, signal.SIGINT)


class LifecycleState(StrEnum):
    """The four states this API can be in, in the order it passes through them.

    ``STARTING`` and ``STOPPED`` both report not-ready and both refuse work, and
    they are separate members because a caller reading a readiness body wants to
    know which one it is: a deployment that has not come up yet and a deployment
    that has been asked to go away are operated differently.
    """

    STARTING = "starting"
    SERVING = "serving"
    DRAINING = "draining"
    STOPPED = "stopped"


class ShuttingDown(Exception):
    """New work arrived after this API stopped accepting it."""


class ApplicationLifecycle:
    """The state this API is in, and the count of what it is still answering.

    Not safe to share across event loops, which is the same caveat every adapter
    in this distribution carries.
    """

    def __init__(self, *, drain_timeout_ms: int = DEFAULT_DRAIN_TIMEOUT_MS) -> None:
        if drain_timeout_ms <= 0:
            raise ValueError("drain_timeout_ms must be positive")
        self._drain_timeout_ms = drain_timeout_ms
        self._state = LifecycleState.STARTING
        self._in_flight = 0

    @property
    def state(self) -> LifecycleState:
        """Which of the four states this API is in."""
        return self._state

    @property
    def in_flight(self) -> int:
        """How many requests this API has accepted and not yet finished."""
        return self._in_flight

    @property
    def drain_timeout_ms(self) -> int:
        """The budget a drain is given."""
        return self._drain_timeout_ms

    @property
    def is_accepting_work(self) -> bool:
        """Whether new work would be accepted right now.

        This is the platform half of readiness. The other half is the selected
        adapter's own answer, and a readiness response is the conjunction: this
        API being willing and the backend being able are different questions and
        both have to be yes.
        """
        return self._state is LifecycleState.SERVING

    def begin_serving(self) -> None:
        """Leave ``STARTING``. Called once, after the adapter has initialized."""
        if self._state is not LifecycleState.STARTING:
            raise RuntimeError(f"cannot begin serving from {self._state}")
        self._state = LifecycleState.SERVING

    def begin_shutdown(self) -> None:
        """Stop accepting work. Idempotent, because a signal can arrive twice.

        This is the first half of the graceful-shutdown equivalent and it happens
        before any draining: readiness is false from the moment this returns.
        """
        if self._state is LifecycleState.STOPPED:
            return
        self._state = LifecycleState.DRAINING

    @contextmanager
    def accept(self) -> Iterator[None]:
        """Accept one request and count it, or refuse it because we are draining.

        Raises:
            ShuttingDown: If this API has stopped accepting work. Deciding and
                counting in one call is what leaves no window between them.
        """
        if not self.is_accepting_work:
            raise ShuttingDown(self._state)
        self._in_flight += 1
        try:
            yield
        finally:
            self._in_flight -= 1

    async def drain(self, *, timeout_ms: int | None = None) -> bool:
        """Wait for in-flight work to finish, then stop.

        Args:
            timeout_ms: The budget, or ``None`` for the configured one.

        Returns:
            ``True`` if everything in flight finished inside the budget, and
            ``False`` if the budget ran out first. A truncated drain is reported
            rather than hidden, because the requests it abandoned are real.
        """
        self.begin_shutdown()
        budget = self._drain_timeout_ms if timeout_ms is None else timeout_ms
        deadline = asyncio.get_running_loop().time() + budget / 1000
        drained = True
        while self._in_flight > 0:
            if asyncio.get_running_loop().time() >= deadline:
                drained = False
                break
            await asyncio.sleep(DRAIN_POLL_SECONDS)
        self._state = LifecycleState.STOPPED
        return drained


def install_termination_handlers(
    loop: asyncio.AbstractEventLoop,
    lifecycle: ApplicationLifecycle,
) -> tuple[signal.Signals, ...]:
    """Register ``SIGTERM`` and ``SIGINT`` to begin the shutdown, where supported.

    The handler calls :meth:`ApplicationLifecycle.begin_shutdown` and nothing
    else. Draining is the server's to run when its own shutdown path executes,
    and a signal handler that awaited a drain would be doing work in a callback
    that is not allowed to.

    Returns:
        The signals that were installed. Empty on a platform where the running
        loop supports none — Windows is one — so that a caller can record that
        the equivalent is not installed instead of assuming it is.
    """
    installed: list[signal.Signals] = []
    for number in TERMINATION_SIGNALS:
        try:
            loop.add_signal_handler(number, lifecycle.begin_shutdown)
        except (NotImplementedError, RuntimeError, ValueError, OSError):
            continue
        installed.append(number)
    return tuple(installed)
