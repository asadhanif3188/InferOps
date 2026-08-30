"""The canonical error contract this API serves, as a table of conditions.

`ADR 0010` decided the canonical error *body* — a code, a safe message, a request
identifier, a correlation identifier, a ``retryable`` flag, and optional
``retryAfterMs`` and ``details`` — and mapped nine observable conditions onto
canonical codes. `V1-S1-005-PR1` served the first four members and recorded the
rest as this change's. This module is the rest of it.

**A condition is the unit, not a code.** The accepted record's own mapping makes
that unavoidable: ``capability-unavailable`` appears twice in it, once for a
runtime that cannot be reached — retryable — and once for a caller asking for
streaming, which is retryable ``false`` because retrying does not make a
capability appear. A single code-to-``retryable`` table would have to pick one
and be wrong for the other, and the same is true of the HTTP status. So each
refusal site names a :class:`Condition`, and the code, the flag, the status, and
the fallback message travel together from there.

**Nine conditions are copied from the accepted record and seven are this API's
own.** The record maps request and runtime conditions and says nothing about
routing, about a body larger than this deployment will read, about a deployment
that has stopped accepting work, or about an adapter whose result contradicts the
kind the deployment was composed with — none of which existed when it was
written. Those seven carry ``in_accepted_record=False`` so that a reader can tell
a copied row from an added one, and
``tests/serving/test_inference_api_implementation_agreement.py`` reads the record
and fails when a copied row drifts from it. **No row of the accepted record was
edited by this change.**

**The message a caller receives is chosen here, never taken from an adapter.**
`V1-S1-005-PR1` forwarded an adapter's canonical message to the caller, which was
safe because every canonical message in this repository is a constant — safe by
review rather than by construction. An adapter is the component closest to a
runtime's own words, a prompt, an endpoint, and a file path, and the redaction
rules name a provider error body as the surface most likely to be logged and
kept. So a canonical error raised below this edge is answered with **this
module's** message for its condition, and the adapter's own message stops here.
Refusals this API produces itself carry a member and a reason written in this
module's vocabulary, which never repeats a value read out of a request.

**``retryAfterMs`` is served for exactly one condition.** A deployment that has
begun draining knows how long its own drain budget is, so ``deployment-draining``
carries it. Nothing else here has a decided retry delay — `ADR 0002` decides no
concurrency limit, no deployment sets a termination grace period, and no
measurement exists to derive a backoff from — and a number invented for the other
conditions would be a recommendation nobody made, arriving in the one field a
client library reads automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus

from ..domain.serving import CanonicalError

# -- the canonical codes ----------------------------------------------------

#: A request the frozen subset does not accept.
CONTRACT_INVALID = "contract-invalid"

#: A capability the selected adapter does not have, or that V1 never built.
CAPABILITY_UNAVAILABLE = "capability-unavailable"

#: A contract or API version this deployment does not serve.
VERSION_UNSUPPORTED = "version-unsupported"

#: The model is loading, or the selected backend reported itself unable.
MODEL_NOT_READY = "model-not-ready"

#: The runtime did not answer inside the deadline the adapter gave it.
UPSTREAM_TIMEOUT = "upstream-timeout"

#: The caller's own deadline elapsed first.
REQUEST_TIMEOUT = "request-timeout"

#: An adapter or the runtime behind it rate-limited a request. **InferOps
#: enforces no rate limit and originates none of these**; see
#: :data:`ADAPTER_RATE_LIMITED`.
RATE_LIMITED = "rate-limited"

#: Anything this API could not complete and cannot describe more precisely.
INTERNAL_ERROR = "internal-error"

# -- messages a caller is given ---------------------------------------------

#: What a caller is told when this deployment has stopped accepting work. It
#: names the state and nothing about the process, the host, or the deployment.
DRAINING_MESSAGE = "this deployment has stopped accepting new work"

#: What a caller is told when a failure has no more precise description. A
#: constant rather than a formatted exception, because an exception's own text is
#: where a path, a host name, or a prompt fragment reaches a caller.
UNEXPECTED_FAILURE_MESSAGE = "the request could not be completed"

#: What a completion is refused with when the adapter's own result declares a
#: different adapter kind from the one this API was composed with. It is an
#: internal error rather than a warning: a response whose ``adapterKind`` cannot
#: be trusted is a response that cannot be used to claim anything, and the mock
#: and real boundary is the rule it would break.
ADAPTER_KIND_DISAGREEMENT = (
    "the serving adapter returned a result declaring a different adapter kind "
    "than this deployment was composed with"
)


# -- the conditions ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Condition:
    """One reason this API refuses, with everything a refusal needs.

    Attributes:
        condition_id: The identifier a refusal publishes in ``details``. For a
            row copied from the accepted record it is that record's own
            ``conditionId``, so a reader holding one can find the other.
        code: The canonical error code.
        retryable: Whether retrying this request could succeed. Per condition
            rather than per code, because the accepted record maps one code to
            both answers.
        status: The HTTP status a refusal on this condition carries.
        message: What a caller is told when the refusal site supplies no more
            specific message of its own.
        in_accepted_record: Whether this row is copied from the accepted record's
            error mapping, or added by this API for a condition that record does
            not cover.
        retryable_override: Whether ``retryable`` differs from the canonical
            default for this code. Recorded so that a reader comparing this API
            against the code table finds an argued difference rather than a
            discrepancy.
        basis: Why this row reads as it does.
    """

    condition_id: str
    code: str
    retryable: bool
    status: HTTPStatus
    message: str
    in_accepted_record: bool = True
    retryable_override: bool = False
    basis: str = ""


# -- conditions the accepted record publishes -------------------------------

MODEL_LOADING = Condition(
    condition_id="model-loading",
    code=MODEL_NOT_READY,
    retryable=True,
    status=HTTPStatus.SERVICE_UNAVAILABLE,
    message="the selected backend is not ready to serve a request",
    basis=(
        "The runtime answers 503 while it loads. It is the one row of the "
        "accepted mapping anything ever observed."
    ),
)

RUNTIME_UNREACHABLE = Condition(
    condition_id="runtime-unreachable",
    code=CAPABILITY_UNAVAILABLE,
    retryable=True,
    status=HTTPStatus.SERVICE_UNAVAILABLE,
    message="the selected backend could not be reached",
    basis=(
        "The canonical vocabulary has no member meaning 'unavailable', and the "
        "accepted record picks the one it has. A backend that is not there is a "
        "server state rather than a client error, so this is 503 while the "
        "streaming refusal on the same code is 400."
    ),
)

RUNTIME_TIMEOUT = Condition(
    condition_id="runtime-timeout",
    code=UPSTREAM_TIMEOUT,
    retryable=True,
    status=HTTPStatus.GATEWAY_TIMEOUT,
    message="the selected backend did not answer within its deadline",
    basis="The far side ran out of time, so the timeout is upstream.",
)

CALLER_DEADLINE = Condition(
    condition_id="caller-deadline",
    code=REQUEST_TIMEOUT,
    retryable=True,
    status=HTTPStatus.GATEWAY_TIMEOUT,
    message="the request did not complete within its deadline",
    basis=(
        "The adapter's own outer deadline elapsed. Retryability is 'maybe' in "
        "the code table because it depends on idempotency; this API serves one "
        "synchronous completion that stores nothing, so a retry is safe here."
    ),
)

REQUEST_OUTSIDE_SUBSET = Condition(
    condition_id="request-outside-subset",
    code=CONTRACT_INVALID,
    retryable=False,
    status=HTTPStatus.BAD_REQUEST,
    message="the request is outside the subset this API accepts",
    basis=(
        "The strict unknown-member policy. Resending the same body produces the "
        "same refusal, so it is not retryable."
    ),
)

STREAMING_REQUESTED = Condition(
    condition_id="streaming-requested",
    code=CAPABILITY_UNAVAILABLE,
    retryable=False,
    status=HTTPStatus.BAD_REQUEST,
    message="streaming is declared unsupported by this deployment",
    retryable_override=True,
    basis=(
        "The one override the accepted record itself argues: the canonical "
        "default for this code is retryable, which is right for a capability "
        "that is temporarily gone and wrong for one that was never built."
    ),
)

UNSUPPORTED_CONTRACT_VERSION = Condition(
    condition_id="unsupported-contract-version",
    code=VERSION_UNSUPPORTED,
    retryable=False,
    status=HTTPStatus.BAD_REQUEST,
    message="this deployment does not serve the API version this path names",
    basis=(
        "Reached by a path whose first segment is a version other than the one "
        "the accepted surface publishes. It is a client error rather than a "
        "missing resource: the path exists in the compatibility target's shape "
        "and this deployment does not serve that version of it."
    ),
)

RUNTIME_ERROR_RESPONSE = Condition(
    condition_id="runtime-error-response",
    code=INTERNAL_ERROR,
    retryable=True,
    status=HTTPStatus.INTERNAL_SERVER_ERROR,
    message=UNEXPECTED_FAILURE_MESSAGE,
    basis=(
        "The backend answered with something this platform could not use. What "
        "it said stops at the adapter."
    ),
)

RUNTIME_UNPARSEABLE_RESPONSE = Condition(
    condition_id="runtime-unparseable-response",
    code=INTERNAL_ERROR,
    retryable=True,
    status=HTTPStatus.INTERNAL_SERVER_ERROR,
    message=UNEXPECTED_FAILURE_MESSAGE,
    basis=(
        "The backend answered 2xx with a body the adapter could not read. It is "
        "indistinguishable from the row above at this layer, and both carry the "
        "same code by the accepted record's own mapping."
    ),
)

# -- conditions this API adds -----------------------------------------------

PATH_NOT_SERVED = Condition(
    condition_id="path-not-served",
    code=CONTRACT_INVALID,
    retryable=False,
    status=HTTPStatus.NOT_FOUND,
    message="this path is not part of the API surface this deployment serves",
    in_accepted_record=False,
    basis=(
        "The accepted record maps request and runtime conditions and does not "
        "cover routing. A path outside the frozen endpoint subset is the same "
        "class of mistake as a member outside the frozen request subset, so it "
        "carries the same code and the status HTTP already has for it."
    ),
)

METHOD_NOT_SERVED = Condition(
    condition_id="method-not-served",
    code=CONTRACT_INVALID,
    retryable=False,
    status=HTTPStatus.METHOD_NOT_ALLOWED,
    message="this method is not served on this path",
    in_accepted_record=False,
    basis="As for the path. The response carries an `Allow` header besides.",
)

REQUEST_TOO_LARGE = Condition(
    condition_id="request-too-large",
    code=CONTRACT_INVALID,
    retryable=False,
    status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
    message="the request body exceeds this deployment's bound",
    in_accepted_record=False,
    basis=(
        "A bound on what a caller can make this process allocate, rather than a "
        "protocol constraint. Resending the same body fails the same way."
    ),
)

DEPLOYMENT_DRAINING = Condition(
    condition_id="deployment-draining",
    code=CAPABILITY_UNAVAILABLE,
    retryable=True,
    status=HTTPStatus.SERVICE_UNAVAILABLE,
    message=DRAINING_MESSAGE,
    in_accepted_record=False,
    basis=(
        "The graceful-shutdown equivalent the accepted record chose has a state "
        "in which this API answers and refuses work, and the record maps no "
        "condition to it. It is retryable because the capability is going away "
        "with this process rather than being absent from the platform, and it "
        "is the one condition here that knows its own delay."
    ),
)

ADAPTER_KIND_DISAGREES = Condition(
    condition_id="adapter-kind-disagreement",
    code=INTERNAL_ERROR,
    retryable=False,
    status=HTTPStatus.INTERNAL_SERVER_ERROR,
    message=ADAPTER_KIND_DISAGREEMENT,
    in_accepted_record=False,
    retryable_override=True,
    basis=(
        "The second override, and the reason is the mock and real boundary: a "
        "deployment whose adapter contradicts the kind it was composed with is "
        "misconfigured, and a misconfiguration does not resolve itself between "
        "one request and the next."
    ),
)

ADAPTER_RATE_LIMITED = Condition(
    condition_id="adapter-rate-limited",
    code=RATE_LIMITED,
    retryable=True,
    status=HTTPStatus.TOO_MANY_REQUESTS,
    message="the selected backend rate-limited this request",
    in_accepted_record=False,
    basis=(
        "The accepted record lists `rate-limited` among the codes V1 does not "
        "emit, and the reason it gives is that V1 has no rate limiter — which "
        "stays true: **InferOps originates no refusal on this condition.** The "
        "mapping exists because the serving adapter contract publishes "
        "`RateLimitedError` as a code an adapter may raise, and reporting a "
        "backend's own limit as an internal error would be worse than reporting "
        "it as what it is. The selected real adapter raises it nowhere; it maps "
        "a 429 from the runtime to `internal-error` by its own accepted record."
    ),
)

UNEXPECTED_FAILURE = Condition(
    condition_id="unexpected-failure",
    code=INTERNAL_ERROR,
    retryable=True,
    status=HTTPStatus.INTERNAL_SERVER_ERROR,
    message=UNEXPECTED_FAILURE_MESSAGE,
    in_accepted_record=False,
    basis=(
        "Anything raised that is not canonical. Its own text never reaches a "
        "caller, because an exception raised by something that touches a file, "
        "a socket, or a prompt is exactly where one of those reaches a response."
    ),
)

#: Every condition this API can refuse on. A refusal site names one of these and
#: nothing else, so a code, a flag, and a status cannot be combined in a way
#: nobody decided.
CONDITIONS: tuple[Condition, ...] = (
    MODEL_LOADING,
    RUNTIME_UNREACHABLE,
    RUNTIME_TIMEOUT,
    CALLER_DEADLINE,
    REQUEST_OUTSIDE_SUBSET,
    STREAMING_REQUESTED,
    UNSUPPORTED_CONTRACT_VERSION,
    RUNTIME_ERROR_RESPONSE,
    RUNTIME_UNPARSEABLE_RESPONSE,
    PATH_NOT_SERVED,
    METHOD_NOT_SERVED,
    REQUEST_TOO_LARGE,
    DEPLOYMENT_DRAINING,
    ADAPTER_KIND_DISAGREES,
    ADAPTER_RATE_LIMITED,
    UNEXPECTED_FAILURE,
)

#: The condition each canonical code an adapter may raise is answered as. The
#: domain publishes six such codes and the two the API layer owns —
#: ``contract-invalid`` and ``version-unsupported`` — are here as well, so that
#: an adapter raising one is answered rather than collapsed into a 500.
CONDITION_FOR_ADAPTER_CODE: dict[str, Condition] = {
    MODEL_NOT_READY: MODEL_LOADING,
    CAPABILITY_UNAVAILABLE: RUNTIME_UNREACHABLE,
    UPSTREAM_TIMEOUT: RUNTIME_TIMEOUT,
    REQUEST_TIMEOUT: CALLER_DEADLINE,
    RATE_LIMITED: ADAPTER_RATE_LIMITED,
    INTERNAL_ERROR: RUNTIME_ERROR_RESPONSE,
    CONTRACT_INVALID: REQUEST_OUTSIDE_SUBSET,
    VERSION_UNSUPPORTED: UNSUPPORTED_CONTRACT_VERSION,
}


def condition_for(error: CanonicalError) -> Condition:
    """The condition a canonical error raised below this edge is answered as.

    A code with no entry above is a defect in the mapping, and
    :data:`UNEXPECTED_FAILURE` is the answer that invents no meaning for it.
    """
    return CONDITION_FOR_ADAPTER_CODE.get(error.code, UNEXPECTED_FAILURE)


class RequestRefused(Exception):
    """A refusal this API produced itself, rather than one an adapter raised.

    Carries the condition, the member the refusal is about when there is one, and
    a reason written here. It carries no value read out of the request, which is
    the one property of this class a reviewer should check first.
    """

    def __init__(
        self,
        condition: Condition,
        member: str | None,
        reason: str,
    ) -> None:
        super().__init__(f"{member}: {reason}" if member else reason)
        self.condition = condition
        self.member = member
        self.reason = reason

    @property
    def code(self) -> str:
        """The canonical code this refusal carries."""
        return self.condition.code

    @property
    def status(self) -> HTTPStatus:
        """The HTTP status this refusal carries."""
        return self.condition.status

    @property
    def message(self) -> str:
        """The message a caller is given: the member, and what was wrong with it."""
        return f"{self.member}: {self.reason}" if self.member else self.reason
