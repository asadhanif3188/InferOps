"""Refusals this API produces at its own edge, and the status each one carries.

**This is provisional, and the provisionality is the point.** `ADR 0010` decided
the canonical error *body* — a code, a safe message, a request identifier, a
correlation identifier, a ``retryable`` flag, and optional ``retryAfterMs`` and
``details`` — and `V1-S1-005-PR2` is the change that standardises it. What this
module carries is the smallest thing the endpoints in this PR cannot work
without: the two codes an edge refusal produces, the mapping from a failure to an
HTTP status, and the guarantee that a refusal names a member rather than
repeating its value.

Three properties are decisions rather than accidents.

**A refusal names the member and never its value.** `ADR 0010`'s security section
and the canonical error contract both forbid an error body that echoes something
read out of the request, and the strict unknown-member policy makes that easy to
get wrong: the natural way to report a rejected member is to print it, and the
member *name* is safe while the value is not. Every constructor here takes a
member name and a reason written in this module's own vocabulary.

**The HTTP status is decided by where the failure happened, not by the code
alone.** ``capability-unavailable`` is produced in two places — a caller asking
for streaming, and a backend that cannot serve — and those are a client error and
a server state respectively. Deciding the status from the refusal site rather
than from the code is what keeps both honest. A single code-to-status table would
have to pick one and be wrong for the other.

**Two codes appear here that the platform domain does not publish.**
``contract-invalid`` and ``version-unsupported`` are canonical codes in the
accepted API surface and are not members of the domain's canonical error family,
because that family is the vocabulary an *adapter* may raise and neither of these
is reachable from one. Whether they move into the domain is `V1-S1-005-PR2`'s to
settle along with the rest of the error contract.
"""

from __future__ import annotations

from http import HTTPStatus

from ..domain.serving import CanonicalError

#: A request the frozen subset does not accept.
CONTRACT_INVALID = "contract-invalid"

#: A capability the selected adapter does not have, or that V1 never built.
CAPABILITY_UNAVAILABLE = "capability-unavailable"

#: The status every edge refusal carries. The caller sent something this surface
#: does not accept, and no backend was reached.
EDGE_REFUSAL_STATUS = HTTPStatus.BAD_REQUEST

#: The status a route outside the frozen subset carries.
NOT_FOUND_STATUS = HTTPStatus.NOT_FOUND

#: The status a known path reached with the wrong method carries.
METHOD_NOT_ALLOWED_STATUS = HTTPStatus.METHOD_NOT_ALLOWED

#: The status each canonical code carries **when an adapter or the platform
#: raised it**, rather than when the edge refused a request. Provisional: the
#: accepted record maps conditions to codes and says nothing about statuses, and
#: `V1-S1-005-PR2` is where that gap is closed.
STATUS_FOR_CANONICAL_CODE: dict[str, HTTPStatus] = {
    "model-not-ready": HTTPStatus.SERVICE_UNAVAILABLE,
    "capability-unavailable": HTTPStatus.SERVICE_UNAVAILABLE,
    "upstream-timeout": HTTPStatus.GATEWAY_TIMEOUT,
    "request-timeout": HTTPStatus.GATEWAY_TIMEOUT,
    "rate-limited": HTTPStatus.TOO_MANY_REQUESTS,
    "internal-error": HTTPStatus.INTERNAL_SERVER_ERROR,
}

#: What a failure whose code this API has no status for is reported as. An
#: unknown code is a defect in the mapping above, and answering `500` is the
#: response that does not invent a meaning for it.
FALLBACK_STATUS = HTTPStatus.INTERNAL_SERVER_ERROR


class RequestRefused(Exception):
    """A request this API refused at its own edge, before any adapter was called.

    Carries the canonical code, the member the refusal is about, and a reason
    written here. It carries no value read out of the request, which is the one
    property of this class a reviewer should check first.
    """

    def __init__(
        self,
        code: str,
        member: str,
        reason: str,
        *,
        status: HTTPStatus = EDGE_REFUSAL_STATUS,
    ) -> None:
        super().__init__(f"{member}: {reason}")
        self.code = code
        self.member = member
        self.reason = reason
        self.status = status

    @property
    def message(self) -> str:
        """The message a caller is given: the member, and what was wrong with it."""
        return f"{self.member}: {self.reason}"


def status_for(error: CanonicalError) -> HTTPStatus:
    """The HTTP status for a canonical error an adapter or the platform raised."""
    return STATUS_FOR_CANONICAL_CODE.get(error.code, FALLBACK_STATUS)
