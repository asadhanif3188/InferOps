"""A transport built from the standard library, because the rule leaves no other.

`ADR 0004`'s dependency rule forbids an HTTP framework or client library
anywhere in this distribution, and
``tests/architecture/test_domain_dependency_boundary.py`` enforces it by reading
every module here. That is not an obstacle this module works around; it is the
reason it is written the way it is. :mod:`http.client` is the standard library's
own HTTP, it is not a framework, and it does exactly what an adapter talking to
one known endpoint needs.

Three properties are worth stating before the code, because each is a decision
rather than an accident.

**No redirect is followed.** :mod:`http.client` follows none, which is why it was
chosen over :mod:`urllib.request` and its opener. A `3xx` is returned as a status
like any other and the inference client maps it to ``internal-error``. Following
a redirect would mean sending a request body to a host the settings never
validated, which is the request-forgery shape the URL builder in
:mod:`~inferops.adapters.llama_cpp.settings` already refuses at the other end.

**A response body is bounded before it is parsed.** The serving pod's memory
limit is 3 GiB (`ADR 0002`), and a transport that reads an unbounded stream from
the far side into memory before deciding anything about it has put that limit at
the mercy of the peer. The cap below is a robustness bound, not a protocol
constraint.

**A connection is opened per request and closed in a ``finally``.** Keep-alive
would be faster and would add shared mutable state to an object several coroutines
may hold. `ADR 0002` records that the trial was single and sequential and decides
no concurrency limit, so there is no measurement here to trade against, and the
simpler thing is the honest thing to write.

**Nothing in this module has been executed against a runtime by this change.**
The default lane cannot reach a runtime, and the `real-runtime` lane is manual and
authorization-gated. What the suites exercise is the adapter above this seam,
against a controlled transport.
"""

from __future__ import annotations

import asyncio
import http.client
import json
from collections.abc import Mapping
from urllib.parse import urlsplit

from .transport import (
    RuntimeResponse,
    TransportProtocolError,
    TransportTimeout,
    TransportUnreachable,
)

#: The largest response body this transport will read. A chat completion bounded
#: by the context length the runtime was started with is orders of magnitude
#: smaller, and so is every descriptive endpoint the adapter reads. It is a bound
#: on what a peer can make this process allocate, not a statement about what a
#: legitimate response looks like.
MAX_RESPONSE_BYTES = 1_048_576

#: The media type sent and expected. The runtime's OpenAI-compatible surface
#: speaks JSON and nothing else this adapter asks for.
JSON_MEDIA_TYPE = "application/json"

#: Headers sent with every request. Deliberately three lines long: an adapter that
#: accumulates headers accumulates places for a credential to be added later, and
#: `ADR 0008` records that V1 has no authentication to add one for.
BASE_HEADERS: Mapping[str, str] = {"Accept": JSON_MEDIA_TYPE}


class HttpRuntimeTransport:
    """The standard library's HTTP, wrapped to the transport protocol.

    Stateless between calls. Each request builds a connection, uses it, and closes
    it, so an instance holds nothing that a second caller could disturb and
    :meth:`close` has nothing to release — which is stated rather than left for a
    reader to discover, because a ``close`` that does nothing is otherwise
    indistinguishable from one that forgot to.
    """

    async def get(self, url: str, *, timeout_s: float) -> RuntimeResponse:
        """Issue a GET and return the status and parsed body."""
        return await asyncio.to_thread(_request, "GET", url, None, timeout_s=timeout_s)

    async def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        timeout_s: float,
    ) -> RuntimeResponse:
        """Issue a JSON POST and return the status and parsed body."""
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return await asyncio.to_thread(_request, "POST", url, body, timeout_s=timeout_s)

    async def close(self) -> None:
        """Nothing is held, so nothing is released. See the class docstring."""
        return None


def _connection(url: str, timeout_s: float) -> http.client.HTTPConnection:
    """One connection to the host the URL names, and to no other.

    The scheme, host, and port come from the URL the settings built. An unknown
    scheme cannot reach a connection at all, and reporting that as *unreachable*
    is the literal truth: no connection was established.
    """
    parts = urlsplit(url)
    host = parts.hostname
    if host is None:
        raise TransportUnreachable
    if parts.scheme == "https":
        return http.client.HTTPSConnection(host, parts.port, timeout=timeout_s)
    if parts.scheme == "http":
        return http.client.HTTPConnection(host, parts.port, timeout=timeout_s)
    raise TransportUnreachable


def _target(url: str) -> str:
    """The request target: the path the URL carries, and nothing else.

    The settings refuse an endpoint with a query or a fragment, so there is
    nothing else to carry. Rebuilding the target from the parsed path rather than
    passing the absolute URL keeps that true even if a caller assembled the URL
    some other way.
    """
    return urlsplit(url).path or "/"


def _request(
    method: str,
    url: str,
    body: bytes | None,
    *,
    timeout_s: float,
) -> RuntimeResponse:
    """Issue one request on a fresh connection. Blocking; called in a thread.

    Raises:
        TransportTimeout: If the budget elapsed.
        TransportUnreachable: If no connection was established or it failed.
        TransportProtocolError: If the response could not be read as HTTP or as
            JSON.
    """
    headers = dict(BASE_HEADERS)
    if body is not None:
        headers["Content-Type"] = JSON_MEDIA_TYPE
    connection = _connection(url, timeout_s)
    try:
        connection.request(method, _target(url), body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE_BYTES)
        status = response.status
    except TimeoutError:
        # Subclass of OSError since 3.3, so it is caught first or never.
        raise TransportTimeout from None
    except http.client.HTTPException:
        raise TransportProtocolError from None
    except OSError:
        raise TransportUnreachable from None
    finally:
        connection.close()
    return RuntimeResponse(status_code=status, body=_parse(raw))


def _parse(raw: bytes) -> object | None:
    """The body as JSON, or ``None`` when there was no body.

    A body that is present and unreadable is a failure rather than an absence.
    Folding the two together would make an unparseable response and an empty one
    the same fact, and the inference client maps them to different things.
    """
    if not raw.strip():
        return None
    try:
        parsed: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise TransportProtocolError from None
    return parsed
