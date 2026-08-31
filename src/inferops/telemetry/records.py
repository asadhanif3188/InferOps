"""Structured log records, and the allowlist that is the redacting sink.

`ADR 0006` `D5` decided the shape: one JSON object per line, a required field set,
a bounded ``inferops.event`` identifier, and **no free-form message field**. The
absence of a message field is the unusual part and it is the load-bearing part.
Prose that varies per request is where an exception's string representation goes,
where a runtime's error text goes, and where ``"failed for prompt: ..."`` is one
formatting change away. It is also the field no query can match on reliably, so
removing it costs less than it looks.

**This module is the redacting sink the catalog recorded as absent.** Until now
redaction was a property of a committed document checked against another
committed document: the two content sensitivity classes have empty placement
lists, so a prompt has nowhere it may be written *in the catalog*. Here the same
rule is a field allowlist that a record is built through:
:func:`record` refuses any field name the catalog does not publish, and there is
no name in it for a prompt, a completion, a provider error body, a secret value,
an authorization header, or a value read out of a submitted document. A caller
cannot write one by passing it, and there is no ``extra``, no ``**kwargs`` pass
through to the encoder, and no message field to hide one in.

**Content capture stays disabled and still has no enabling path.** There is no
flag here, because a flag would be the whole decision -- `ADR 0006` `D7`, and the
five artifacts it requires still do not exist.

**Where records go is the composition point's decision, not this module's.** An
emitter is constructed with a sink. :data:`DISCARDING_SINK` is what a process
that has not chosen a destination gets, and it is a named state rather than a
default that quietly writes to a stream nobody picked;
:func:`stream_sink` is what :mod:`inferops.api.selection` composes a deployment
with. No log store, shipper, retention window, or access rule is selected, and
none is selected here.

**A failing sink drops a record; a malformed record is still a defect.** The two
are separated on purpose, and the line between them is the line between I/O and a
call site. Writing to a stream can fail for reasons this process did not cause --
a closed pipe, a full disk, a log collector that stopped reading -- and a
deployment that returned an internal error to every caller because its log
destination went away would be telemetry deciding availability, which is the one
thing telemetry may not do. So :meth:`StructuredLogEmitter.emit` catches what the
sink raises, counts it in :attr:`StructuredLogEmitter.dropped`, and carries on;
the exposition names a non-zero count, so a dropped record is visible on the
surface that still works rather than silent. A record that fails to *build* --
an undeclared event, a missing required field, a field name the catalog does not
publish -- raises as it always did. That is a defect in the caller, and the
allowlist refusing a forbidden field is exactly the error that may never be
swallowed.
"""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import IO, Any

from ..domain.serving.errors import InvalidValueError
from . import names
from .resource import ResourceAttributes, WorkloadIdentity

#: Where a record goes. A callable over one already-encoded line, so that a sink
#: has no opportunity to reformat a record and no reason to know what is in one.
Sink = Callable[[str], None]

#: Every field name a record may carry. It is the catalog's published attribute
#: names and nothing else -- which is why a prompt, a completion, a provider error
#: body, a secret, an authorization header, and a value read out of a document
#: each have no name here to be written under.
ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        names.TIMESTAMP,
        names.LEVEL,
        names.EVENT,
        names.SERVICE_NAME,
        names.SERVICE_VERSION,
        names.DEPLOYMENT_ENVIRONMENT,
        names.CAPABILITY_ID,
        names.RELEASE_ID,
        names.POD_NAME,
        names.MODEL_REVISION,
        names.RUNTIME_IMAGE_DIGEST,
        names.ADAPTER_KIND,
        names.WORKLOAD_ID,
        names.WORKLOAD_VERSION,
        names.OWNER_ID,
        names.MODEL_ID,
        names.RUNTIME_ID,
        names.OUTCOME,
        names.ERROR_CODE,
        names.COMPONENT,
        names.TOKEN_DIRECTION,
        names.FINISH_REASON,
        names.CORRELATION_ID,
        names.REQUEST_ID,
        names.DURATION_MS,
        names.HTTP_STATUS,
    }
)

#: The fields the catalog requires of every record. A record missing one is
#: refused here rather than written and found later, because the case that
#: matters is the refusal nobody can correlate.
REQUIRED_FIELDS: tuple[str, ...] = (
    names.TIMESTAMP,
    names.LEVEL,
    names.EVENT,
    names.SERVICE_NAME,
    names.CORRELATION_ID,
)


def encode(fields: Mapping[str, object]) -> str:
    """One record as one line: compact JSON, UTF-8, and no newline inside it.

    ``ensure_ascii`` is off so that a record stays UTF-8 rather than becoming
    escape sequences, and the separators are compact because a log line is read
    by a parser far more often than by a person.
    """
    return json.dumps(dict(fields), ensure_ascii=False, separators=(",", ":"))


def timestamp(clock_reading: float) -> str:
    """One instant as RFC 3339, UTC, with millisecond precision.

    A local-time log record is one that cannot be joined with anything, which is
    why the zone is not a parameter.
    """
    moment = datetime.fromtimestamp(clock_reading, tz=UTC)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def record(
    *,
    event: str,
    level: str,
    correlation_id: str,
    resource: ResourceAttributes,
    workload: WorkloadIdentity,
    at: float,
    fields: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build one record, or refuse to.

    Args:
        event: The bounded identifier this record is queried by. It has to be one
            of :data:`~inferops.telemetry.names.EVENTS`; an event invented at a
            call site is how a ``bounded-small`` attribute stops being bounded.
        level: One of :data:`~inferops.telemetry.names.LEVELS`.
        correlation_id: The identifier assigned at the edge. Required, because a
            record nobody can join to a request is a record nobody can use.
        resource: What this process is.
        workload: The workload this deployment serves.
        at: The clock reading this record is stamped with.
        fields: The conditional fields this particular record carries. Every name
            has to be in :data:`ALLOWED_FIELDS`.

    Raises:
        InvalidValueError: If the event or the level is outside its declared set,
            if a field name is not one the catalog publishes, or if a required
            field is missing.
    """
    if event not in names.EVENTS:
        raise InvalidValueError(f"{event!r} is not a declared inferops.event")
    if level not in names.LEVELS:
        raise InvalidValueError(f"{level!r} is not a declared level")
    if not correlation_id:
        raise InvalidValueError("a record carries a correlation identifier")

    built: dict[str, object] = {
        names.TIMESTAMP: timestamp(at),
        names.LEVEL: level,
        names.EVENT: event,
    }
    built.update(resource.as_log_fields())
    built.update(workload.as_log_fields())
    built[names.CORRELATION_ID] = correlation_id

    for name, value in (fields or {}).items():
        if name not in ALLOWED_FIELDS:
            # The allowlist, doing the one job it exists for. The message names
            # the field and never the value: a rejected field is exactly the one
            # most likely to be carrying something that may not be repeated.
            raise InvalidValueError(
                f"{name!r} is not a field the telemetry catalog publishes; a "
                f"record carries named attributes and no free-form content"
            )
        if value is None:
            continue
        built[name] = value

    missing = [name for name in REQUIRED_FIELDS if name not in built]
    if missing:
        raise InvalidValueError(f"a record is missing {missing}")
    return built


def stream_sink(stream: IO[str]) -> Sink:
    """A sink that writes one record per line to a stream and flushes it.

    Flushing per record is deliberate. A buffered log is a log that loses exactly
    the records written just before the process that was being diagnosed stopped.
    """

    def write(line: str) -> None:
        stream.write(line + "\n")
        stream.flush()

    return write


def stderr_sink() -> Sink:
    """The standard error stream, which is where a container's logs come from.

    It is read at call time rather than captured at import, so a process that
    replaces the stream -- as a test harness does -- is honoured.
    """

    def write(line: str) -> None:
        stream_sink(sys.stderr)(line)

    return write


def _discard(line: str) -> None:
    """Accept a record and write it nowhere."""


#: What a process that has not chosen a destination gets. Naming it makes "this
#: deployment writes no records" a state a reader can see at the composition
#: point, rather than a default that turns out to have been writing to a stream
#: nobody picked.
DISCARDING_SINK: Sink = _discard


class StructuredLogEmitter:
    """Builds one record per event and hands it to a sink.

    The emitter holds the resource attributes and the workload identity, so a
    call site supplies what varies and cannot forget what does not. It holds a
    lock as well: two requests completing at once must produce two lines, not one
    interleaved line that no parser will accept.
    """

    def __init__(
        self,
        *,
        resource: ResourceAttributes,
        workload: WorkloadIdentity,
        sink: Sink = DISCARDING_SINK,
        clock: Callable[[], float],
    ) -> None:
        self._resource = resource
        self._workload = workload
        self._sink = sink
        self._clock = clock
        self._lock = threading.Lock()
        self._dropped = 0

    @property
    def resource(self) -> ResourceAttributes:
        return self._resource

    @property
    def workload(self) -> WorkloadIdentity:
        return self._workload

    @property
    def dropped(self) -> int:
        """How many records the sink refused to take.

        Non-zero means this process wrote fewer records than it produced, which a
        reader of the remaining records cannot otherwise tell.
        """
        with self._lock:
            return self._dropped

    def emit(
        self,
        event: str,
        *,
        level: str = names.LEVEL_INFO,
        correlation_id: str,
        fields: Mapping[str, Any] | None = None,
    ) -> dict[str, object]:
        """Write one record and return it, so a caller can assert on what it wrote."""
        built = record(
            event=event,
            level=level,
            correlation_id=correlation_id,
            resource=self._resource,
            workload=self._workload,
            at=self._clock(),
            fields=fields,
        )
        line = encode(built)
        with self._lock:
            try:
                self._sink(line)
            except Exception:
                # The sink is the only I/O here, and it is the composition
                # point's choice rather than this module's. Its failure is
                # counted and not raised: see the module docstring for why a
                # broken log destination may not refuse a caller's request.
                self._dropped += 1
        return built
