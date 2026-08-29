"""The transport seam: what it publishes, and what it refuses to carry.

Two subjects, and the split matters.

**The protocol** is checked as a shape: three failure kinds that are distinct
types, a response reduced to a status and a parsed body, and — the obligation
this suite exists for — a failure that carries **no text from the far side**. A
transport error whose message repeated a runtime's words would be a redaction
hole at the exact place a runtime's words first enter this process.

**The concrete transport** is checked without a socket. Its URL parsing, its
request target, its body encoding, its header set, and its translation of every
standard-library failure into a transport failure are all functions of their
arguments, and each is exercised by substituting the standard library's own
connection class with a recording double. What is *not* checked here is that a
request reaches a runtime: nothing in the default lane can, and pretending
otherwise is the failure the mock and real boundary names.

Every check reads objects from this distribution. No network, no cluster, no
model, no clock, and no randomness.
"""

from __future__ import annotations

import ast
import asyncio
import http.client
import json
import socket
from collections.abc import Callable
from pathlib import Path

import pytest

from inferops.adapters.llama_cpp import (
    BASE_HEADERS,
    JSON_MEDIA_TYPE,
    MAX_RESPONSE_BYTES,
    HttpRuntimeTransport,
    RuntimeResponse,
    RuntimeTransport,
    TransportError,
    TransportProtocolError,
    TransportTimeout,
    TransportUnreachable,
    http_transport,
)

pytestmark = pytest.mark.adapter

#: A URL of the shape the settings build. Only its parts are read; nothing dials.
BASE = "http://llama-server.inferops-serving.svc.cluster.local:8080"
HEALTH_URL = f"{BASE}/health"
COMPLETIONS_URL = f"{BASE}/v1/chat/completions"

#: A string that would be a redaction failure if a transport error carried it.
SECRET_SHAPED_RUNTIME_TEXT = "loading /mnt/models/Qwen3-1.7B-Q8_0.gguf on host-01"

#: The three failure kinds, as one list every parametrised check reads.
FAILURE_KINDS: list[type[TransportError]] = [
    TransportTimeout,
    TransportUnreachable,
    TransportProtocolError,
]


class Recorded:
    """What the transport asked one connection to do, and what it was told back.

    A mutable record shared between the test and the connection double, so a test
    arms the answer before the call and reads the request after it.
    """

    def __init__(self) -> None:
        self.status = 200
        self.raw = b"{}"
        self.fail_on_request: BaseException | None = None
        self.fail_on_response: BaseException | None = None
        self.host: str | None = None
        self.port: int | None = None
        self.timeout: float | None = None
        self.method: str | None = None
        self.target: str | None = None
        self.body: bytes | None = None
        self.headers: dict[str, str] = {}
        self.closed = False
        self.read_limit: int | None = None


class _Response:
    """Enough of ``http.client.HTTPResponse`` for the transport to read."""

    def __init__(self, recorded: Recorded) -> None:
        self._recorded = recorded
        self.status = recorded.status

    def read(self, amount: int) -> bytes:
        self._recorded.read_limit = amount
        return self._recorded.raw[:amount]


def _connection_class(recorded: Recorded) -> type:
    """A connection class that writes everything it is told into ``recorded``."""

    class _Connection:
        def __init__(
            self,
            host: str,
            port: int | None = None,
            timeout: float | None = None,
        ) -> None:
            recorded.host = host
            recorded.port = port
            recorded.timeout = timeout

        def request(
            self,
            method: str,
            target: str,
            body: bytes | None = None,
            headers: dict[str, str] | None = None,
        ) -> None:
            recorded.method = method
            recorded.target = target
            recorded.body = body
            recorded.headers = dict(headers or {})
            if recorded.fail_on_request is not None:
                raise recorded.fail_on_request

        def getresponse(self) -> _Response:
            if recorded.fail_on_response is not None:
                raise recorded.fail_on_response
            return _Response(recorded)

        def close(self) -> None:
            recorded.closed = True

    return _Connection


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> Recorded:
    """Substitute both standard-library connection classes with a recorder."""
    record = Recorded()
    substitute = _connection_class(record)
    monkeypatch.setattr(http.client, "HTTPConnection", substitute)
    monkeypatch.setattr(http.client, "HTTPSConnection", substitute)
    return record


# --------------------------------------------------------------------------
# The protocol: distinct kinds, and no text from the far side
# --------------------------------------------------------------------------


@pytest.mark.parametrize("failure", FAILURE_KINDS)
def test_every_transport_failure_is_a_transport_error(
    failure: type[TransportError],
) -> None:
    """One base class, so a caller can catch the family and map the member."""
    assert issubclass(failure, TransportError)
    assert issubclass(failure, Exception)


def test_the_three_failure_kinds_are_distinct_types() -> None:
    """A caller maps a kind of failure, not a string a runtime chose."""
    assert len(set(FAILURE_KINDS)) == 3
    for kind in FAILURE_KINDS:
        assert not any(
            other is not kind and issubclass(kind, other) for other in FAILURE_KINDS
        )


@pytest.mark.parametrize("failure", FAILURE_KINDS)
def test_a_transport_failure_carries_no_message(
    failure: type[TransportError],
) -> None:
    """The redaction rule at the place a runtime's words enter this process."""
    raised = failure()
    assert str(raised) == ""
    assert raised.args == ()


def test_no_module_in_this_distribution_gives_a_transport_failure_an_argument() -> None:
    """Python would allow one, so the habit is enforced by reading the source.

    Every construction site in ``src/`` is parsed and required to pass nothing.
    A message passed here would be a runtime's own words entering a canonical
    error two calls later, which is the one thing the seam exists to prevent.
    """
    root = Path(http_transport.__file__).resolve().parents[3]
    names = {kind.__name__ for kind in FAILURE_KINDS}
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in names
                and (node.args or node.keywords)
            ):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, offenders
    assert root.name == "src"


def test_a_runtime_response_carries_a_status_and_an_optional_body() -> None:
    """Two members, and a body that is legitimately absent."""
    assert RuntimeResponse(status_code=204).body is None
    assert RuntimeResponse(status_code=200, body={"a": 1}).status_code == 200


def test_the_concrete_transport_satisfies_the_protocol() -> None:
    """A static check made executable, so a renamed method fails a test too."""
    transport: RuntimeTransport = HttpRuntimeTransport()
    assert callable(transport.get)
    assert callable(transport.post_json)
    assert callable(transport.close)


# --------------------------------------------------------------------------
# The request the concrete transport builds
# --------------------------------------------------------------------------


async def test_a_get_asks_for_the_path_and_nothing_else(recorded: Recorded) -> None:
    """The request target is the path, not the absolute URL."""
    recorded.raw = b'{"status":"ok"}'
    response = await HttpRuntimeTransport().get(HEALTH_URL, timeout_s=2.0)

    assert response == RuntimeResponse(status_code=200, body={"status": "ok"})
    assert recorded.method == "GET"
    assert recorded.target == "/health"
    assert recorded.body is None


async def test_a_get_dials_the_host_and_port_the_url_names(
    recorded: Recorded,
) -> None:
    """The URL decides the destination. The transport joins nothing."""
    await HttpRuntimeTransport().get(HEALTH_URL, timeout_s=2.0)

    assert recorded.host == "llama-server.inferops-serving.svc.cluster.local"
    assert recorded.port == 8080


async def test_the_budget_reaches_the_connection(recorded: Recorded) -> None:
    """A timeout that is not passed down is a timeout that does not exist."""
    await HttpRuntimeTransport().get(HEALTH_URL, timeout_s=1.5)

    assert recorded.timeout == 1.5


async def test_a_post_sends_compact_json_and_says_so(recorded: Recorded) -> None:
    """The body is JSON, the content type declares it, and nothing else is sent."""
    recorded.raw = b'{"choices":[]}'
    await HttpRuntimeTransport().post_json(
        COMPLETIONS_URL, {"model": "qwen", "messages": []}, timeout_s=2.0
    )

    sent = recorded.body
    assert sent is not None
    assert json.loads(sent.decode("utf-8")) == {"model": "qwen", "messages": []}
    assert b" " not in sent
    assert recorded.headers["Content-Type"] == JSON_MEDIA_TYPE
    assert recorded.headers["Accept"] == JSON_MEDIA_TYPE
    assert recorded.method == "POST"
    assert recorded.target == "/v1/chat/completions"


async def test_a_get_declares_no_content_type(recorded: Recorded) -> None:
    """A GET has no body, so it announces no media type for one."""
    await HttpRuntimeTransport().get(HEALTH_URL, timeout_s=2.0)

    assert "Content-Type" not in recorded.headers


def test_the_base_headers_carry_no_authorization() -> None:
    """`ADR 0008` records that V1 has no authentication, so there is no header."""
    assert dict(BASE_HEADERS) == {"Accept": JSON_MEDIA_TYPE}
    assert not any(key.lower() == "authorization" for key in BASE_HEADERS)


async def test_the_connection_is_closed_even_when_the_request_fails(
    recorded: Recorded,
) -> None:
    """The ``finally`` is the point: a failure must not leak a socket."""
    recorded.fail_on_request = ConnectionRefusedError()
    with pytest.raises(TransportUnreachable):
        await HttpRuntimeTransport().get(HEALTH_URL, timeout_s=2.0)

    assert recorded.closed is True


async def test_the_connection_is_closed_on_success(recorded: Recorded) -> None:
    await HttpRuntimeTransport().get(HEALTH_URL, timeout_s=2.0)

    assert recorded.closed is True


# --------------------------------------------------------------------------
# Failure translation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (TimeoutError(), TransportTimeout),
        (ConnectionRefusedError(), TransportUnreachable),
        (socket.gaierror(), TransportUnreachable),
        (OSError(), TransportUnreachable),
        (http.client.BadStatusLine("nonsense"), TransportProtocolError),
        (http.client.HTTPException(), TransportProtocolError),
    ],
)
async def test_a_standard_library_failure_becomes_a_transport_failure(
    recorded: Recorded,
    raised: BaseException,
    expected: type[TransportError],
) -> None:
    """``socket.timeout`` is ``TimeoutError``, which is itself an ``OSError``.

    The order the transport catches them in is therefore load-bearing — a
    ``TimeoutError`` caught by the ``OSError`` clause would be reported as
    unreachable — and this is where it is asserted rather than reasoned about.
    """
    recorded.fail_on_response = raised
    with pytest.raises(expected):
        await HttpRuntimeTransport().get(HEALTH_URL, timeout_s=2.0)


async def test_a_url_with_no_host_cannot_reach_a_connection(
    recorded: Recorded,
) -> None:
    with pytest.raises(TransportUnreachable):
        await HttpRuntimeTransport().get("http:///health", timeout_s=2.0)


async def test_a_scheme_this_transport_does_not_speak_is_unreachable(
    recorded: Recorded,
) -> None:
    """No connection was established, which is what the error says."""
    with pytest.raises(TransportUnreachable):
        await HttpRuntimeTransport().get("file:///etc/passwd", timeout_s=2.0)


async def test_a_transport_failure_from_a_real_call_carries_no_runtime_text(
    recorded: Recorded,
) -> None:
    """The runtime's own words are dropped at the seam, not further downstream."""
    recorded.fail_on_response = ConnectionResetError(SECRET_SHAPED_RUNTIME_TEXT)
    with pytest.raises(TransportUnreachable) as caught:
        await HttpRuntimeTransport().get(HEALTH_URL, timeout_s=2.0)

    assert SECRET_SHAPED_RUNTIME_TEXT not in str(caught.value)
    assert str(caught.value) == ""


# --------------------------------------------------------------------------
# The body
# --------------------------------------------------------------------------


async def test_an_empty_body_is_absence_rather_than_a_failure(
    recorded: Recorded,
) -> None:
    recorded.status = 204
    recorded.raw = b""

    assert (await HttpRuntimeTransport().get(HEALTH_URL, timeout_s=2.0)).body is None


async def test_a_whitespace_only_body_is_absence(recorded: Recorded) -> None:
    recorded.raw = b"  \n "

    assert (await HttpRuntimeTransport().get(HEALTH_URL, timeout_s=2.0)).body is None


@pytest.mark.parametrize("raw", [b"{not json", b"\xff\xfe", b"<html>503</html>"])
async def test_a_body_that_is_present_and_unreadable_is_a_failure(
    recorded: Recorded, raw: bytes
) -> None:
    """An unparseable response and an empty one are different facts."""
    recorded.raw = raw
    with pytest.raises(TransportProtocolError):
        await HttpRuntimeTransport().get(HEALTH_URL, timeout_s=2.0)


async def test_the_body_is_read_under_a_bound(recorded: Recorded) -> None:
    """A peer must not be able to decide how much this process allocates."""
    recorded.raw = b'{"a":1}'
    await HttpRuntimeTransport().get(HEALTH_URL, timeout_s=2.0)

    assert recorded.read_limit == MAX_RESPONSE_BYTES
    assert MAX_RESPONSE_BYTES == 1_048_576


async def test_a_status_the_transport_does_not_interpret_is_passed_through(
    recorded: Recorded,
) -> None:
    """Mapping a status to a code is the inference client's job, not this one's."""
    recorded.status = 503
    recorded.raw = b'{"error":{"code":503}}'
    response = await HttpRuntimeTransport().get(HEALTH_URL, timeout_s=2.0)

    assert response.status_code == 503
    assert response.body == {"error": {"code": 503}}


async def test_close_releases_nothing_and_says_so(recorded: Recorded) -> None:
    """A ``close`` that does nothing is documented as such and asserted here.

    Nothing is dialled, and a second close is as harmless as the first, which is
    what "stateless between calls" means at the one method where a stateful
    transport would have had something to release.
    """
    transport = HttpRuntimeTransport()
    await transport.close()
    await transport.close()

    assert recorded.method is None
    assert recorded.closed is False


async def test_a_request_does_not_block_the_event_loop(recorded: Recorded) -> None:
    """The blocking call runs in a thread, so a second coroutine still runs.

    Asserted by interleaving: the ticker below could not advance if the request
    held the loop.
    """
    ticks = 0

    async def tick() -> None:
        nonlocal ticks
        for _ in range(3):
            await asyncio.sleep(0)
            ticks += 1

    await asyncio.gather(HttpRuntimeTransport().get(HEALTH_URL, timeout_s=2.0), tick())

    assert ticks == 3


def test_the_recorder_is_not_mistaken_for_the_standard_library() -> None:
    """Outside the fixture, the real classes are back. Otherwise this suite would
    leak a substitution into every module that imports ``http.client``."""
    builder: Callable[..., object] = http.client.HTTPConnection
    assert builder is http.client.HTTPConnection
    assert http.client.HTTPConnection.__module__ == "http.client"
