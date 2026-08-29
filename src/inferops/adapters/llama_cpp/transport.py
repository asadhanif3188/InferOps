"""The one place this distribution is allowed to touch a socket, as a seam.

Everything else in this package is a pure function of its arguments. This module
is where that stops being possible: an inference client has to send a request,
and a request needs a transport. So the transport is a *protocol* rather than a
concrete thing, and the concrete thing lives in
:mod:`~inferops.adapters.llama_cpp.http_transport` beside it.

**Why a seam and not a method on the adapter.** Two reasons, and neither is
testability on its own. The first is that a suite exercising the adapter against a
controlled response is exercising the adapter, and the moment the socket is inside
the adapter that suite has to intercept the standard library — which tests the
interception. The second is the boundary rule: a transport that is a value can be
refused, replaced, or closed by whoever composed it, and one that is a private
method cannot.

**A transport failure carries no message from the far side.** The three errors
below take no argument and hold no runtime text, host name, path, or response
body. That is the redaction rule applied at the place a runtime's own words first
enter this process: a message that reached here can reach a log line, and this
module has no way to tell which message is safe. What a caller needs from a
transport failure is which of three things happened, and that is what the type
says.

Nothing here has run. The concrete transport beside it has issued no request in
any check recorded by this change, and the shapes this module publishes were
chosen against the responses the Sprint 0 feasibility record preserved.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


class TransportError(Exception):
    """A request did not produce a response. Carries no text from the far side.

    Subclassed rather than parametrised so that a caller maps a *kind* of
    failure to a canonical code, instead of matching on a string a runtime
    chose.
    """


class TransportTimeout(TransportError):
    """The far side did not answer within the budget it was given."""


class TransportUnreachable(TransportError):
    """No connection could be established, or it failed before a response."""


class TransportProtocolError(TransportError):
    """A response arrived and could not be read as HTTP or as JSON."""


@dataclass(frozen=True, slots=True)
class RuntimeResponse:
    """One response, reduced to the two things this adapter reads.

    Attributes:
        status_code: The HTTP status. Every mapping decision starts here.
        body: The parsed JSON body, or ``None`` when the response carried none.
            A body that is present and unparseable is a
            :class:`TransportProtocolError` rather than a ``None`` body, because
            "no body" and "a body nobody could read" are different facts.
    """

    status_code: int
    body: object | None = None


class RuntimeTransport(Protocol):
    """What the inference client needs from whatever carries its requests.

    Two methods, both taking an absolute URL that
    :meth:`~inferops.adapters.llama_cpp.settings.LlamaServerSettings.url_for`
    built. The transport does not know the endpoint, does not join paths, and
    cannot be aimed at a host the settings did not validate — the URL builder is
    the only thing that decides where a request goes.

    ``timeout_s`` is a budget and not a suggestion. A transport that cannot
    honour it raises :class:`TransportTimeout`; a transport that ignores it is
    caught by the adapter's own outer deadline, which exists because this
    protocol cannot enforce the promise it asks for.
    """

    async def get(self, url: str, *, timeout_s: float) -> RuntimeResponse:
        """Issue a GET and return the status and parsed body.

        Raises:
            TransportTimeout: If the budget elapsed.
            TransportUnreachable: If no connection was established.
            TransportProtocolError: If the response could not be read.
        """
        ...

    async def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        timeout_s: float,
    ) -> RuntimeResponse:
        """Issue a JSON POST and return the status and parsed body.

        Raises:
            TransportTimeout: If the budget elapsed.
            TransportUnreachable: If no connection was established.
            TransportProtocolError: If the response could not be read.
        """
        ...

    async def close(self) -> None:
        """Release whatever the transport holds. Called at adapter shutdown."""
        ...
