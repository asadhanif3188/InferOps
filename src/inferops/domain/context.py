"""Request-scoped context a domain failure carries when a caller supplied one.

The platform's canonical error body carries a ``requestId`` and a
``correlationId`` (ADR 0010, and the error shape in
``docs/serving/inference-api-surface.md``). A domain error raised while parsing a
document has to be able to carry the same two, or a refusal is less traceable
than a success.

Two rules hold this to what it can honestly do.

**The domain never invents an identifier.** The architecture assigns the
correlation identifier at the edge, before anything can fail, and nothing here
runs at an edge. An offline parse called with no context produces an error whose
context is empty, and ``empty`` is a state this module names rather than one a
reader has to infer from two ``None`` values.

**The context is not a place to put a document.** It carries identifiers the
platform generated. It does not carry the workload, the prompt, or any value read
out of the document being parsed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Identifiers a trusted component assigned to the request being served.

    Both members are optional because both are genuinely absent in the case this
    package can execute today: a parse invoked from a test or from a command-line
    tool has no request behind it.
    """

    request_id: str | None = None
    correlation_id: str | None = None

    @property
    def is_empty(self) -> bool:
        """True when no identifier was supplied, rather than when none exists."""
        return self.request_id is None and self.correlation_id is None

    def as_dict(self) -> dict[str, str]:
        """The identifiers that are present, for an error body or a log record."""
        present = {
            "requestId": self.request_id,
            "correlationId": self.correlation_id,
        }
        return {key: value for key, value in present.items() if value is not None}


#: The context of a call nobody supplied one for. Named so that "no context" is a
#: value a caller can pass deliberately rather than a sentinel each caller invents.
NO_REQUEST_CONTEXT = RequestContext()
