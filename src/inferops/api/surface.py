"""The frozen subset, copied from the record that decided it.

`ADR 0010` decided the compatibility target, the five endpoints, the request and
response field lists, the extension namespace, and the declared capability set,
and
[`docs/serving/inference-api-surface.v1alpha1.json`](../../../docs/serving/inference-api-surface.v1alpha1.json)
is where that decision is published. Every constant below is a **copy** of a row
in that file, and ``tests/serving/test_inference_api_implementation_agreement.py`` reads the accepted
file and fails when a copy drifts. That is the same treatment the runtime pins
get, for the same reason: a constant nobody compares to its source is a copy that
drifts.

Nothing here decides anything. A change to the shape of this API is a change to
the accepted record first and to this module second, in that order.

**Two version identifiers travel together and mean different things.** The `/v1`
path prefix belongs to the borrowed shape and is not an InferOps version claim;
:data:`CONTRACT_VERSION` is InferOps's own version for this surface and moves
independently of the path. Both are published on every response that carries the
extension member, because a reader who takes one for the other has been misled.
"""

from __future__ import annotations

from dataclasses import dataclass

# -- versions ---------------------------------------------------------------

#: InferOps's own version for this surface. It travels in the extension member,
#: never in the path.
CONTRACT_VERSION = "inferops.io/v1alpha1"

#: The borrowed shape's path prefix. Not an InferOps version claim.
PATH_PREFIX = "/v1"

# -- the extension namespace ------------------------------------------------

#: The one object-valued body member carrying what the compatibility target has
#: no place for.
EXTENSION_MEMBER = "x_inferops"

#: The header namespace, which is a different namespace with a different purpose.
HEADER_PREFIX = "X-InferOps-"

#: The two transport headers this API reads and echoes. The integration
#: specification names five; the other three carry workload identity, which no
#: component supplies to this API yet.
REQUEST_ID_HEADER = "X-InferOps-Request-ID"
CORRELATION_ID_HEADER = "X-InferOps-Correlation-ID"

# -- the endpoints ----------------------------------------------------------

CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
MODELS_PATH = "/v1/models"
LIVE_PATH = "/health/live"
READY_PATH = "/health/ready"
METRICS_PATH = "/metrics"


@dataclass(frozen=True, slots=True)
class Route:
    """One row of the accepted endpoint table, as this API registers it.

    ``endpoint_id`` is the identifier the accepted record publishes, and it is
    what the agreement suite matches on. A route this module registers under an
    identifier the record does not publish is a route nobody decided.
    """

    endpoint_id: str
    method: str
    path: str


#: Every route this API serves, and no other. The accepted record lists five
#: endpoints in scope and records everything else as out of scope with a reason;
#: this tuple is the executable half of that list.
ROUTES: tuple[Route, ...] = (
    Route("chat-completions", "POST", CHAT_COMPLETIONS_PATH),
    Route("models-list", "GET", MODELS_PATH),
    Route("health-live", "GET", LIVE_PATH),
    Route("health-ready", "GET", READY_PATH),
    Route("metrics", "GET", METRICS_PATH),
)

# -- the request subset -----------------------------------------------------

REQUEST_MODEL = "model"
REQUEST_MESSAGES = "messages"
REQUEST_MAX_TOKENS = "max_tokens"
REQUEST_TEMPERATURE = "temperature"
REQUEST_STREAM = "stream"

#: The whole request subset. A member outside it is refused, and the refusal
#: names the member — never its value.
ACCEPTED_REQUEST_FIELDS: frozenset[str] = frozenset(
    {
        REQUEST_MODEL,
        REQUEST_MESSAGES,
        REQUEST_MAX_TOKENS,
        REQUEST_TEMPERATURE,
        REQUEST_STREAM,
    }
)

#: The two the accepted record marks required.
REQUIRED_REQUEST_FIELDS: frozenset[str] = frozenset({REQUEST_MODEL, REQUEST_MESSAGES})

MESSAGE_ROLE = "role"
MESSAGE_CONTENT = "content"

#: A message carries exactly these two members.
MESSAGE_FIELDS: frozenset[str] = frozenset({MESSAGE_ROLE, MESSAGE_CONTENT})

ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"

#: The roles the frozen subset accepts. A role outside this set is refused.
ACCEPTED_MESSAGE_ROLES: tuple[str, ...] = (ROLE_SYSTEM, ROLE_USER, ROLE_ASSISTANT)

# -- the response shapes ----------------------------------------------------

#: The literal a completion's ``object`` member carries.
COMPLETION_OBJECT = "chat.completion"

#: The prefix of a completion identifier. The identifier is generated here rather
#: than passed through from the runtime, and the prefix is the one the recorded
#: response carried, so that a client parsing for it is not surprised.
COMPLETION_ID_PREFIX = "chatcmpl-"

#: The literal the model list's ``object`` member carries.
MODEL_LIST_OBJECT = "list"

#: The literal a model entry's ``object`` member carries.
MODEL_OBJECT = "model"

#: What a model entry reports as its owner. One deployment serves one model and
#: this platform is what serves it; there is no model registry behind this value
#: and it is not read from one.
MODEL_OWNER = "inferops"

# -- the declared capability set --------------------------------------------

#: The capability identifiers the accepted record publishes at ``/v1/models``
#: under ``x_inferops.capabilities``.
CAPABILITY_STREAMING = "streaming"
CAPABILITY_TOKEN_USAGE = "tokenUsage"
CAPABILITY_DETERMINISTIC_SAMPLING = "deterministicSampling"
CAPABILITY_MULTI_MODEL = "multiModel"

#: Which capability the surface publishes is answered by which capability the
#: **adapter declares**, because a capability that is a constant in the API is an
#: assumption and one the adapter declares is a fact about the thing that will
#: serve the request. Two of the four have an adapter declaration behind them and
#: two do not; see :mod:`inferops.api.responses` for what the other two publish
#: and why.
ADAPTER_CAPABILITY_FOR: dict[str, str] = {
    CAPABILITY_STREAMING: "streaming",
    CAPABILITY_TOKEN_USAGE: "token-counting",
}

# -- the extension members a response carries -------------------------------

EXTENSION_REQUEST_ID = "requestId"
EXTENSION_CORRELATION_ID = "correlationId"
EXTENSION_CONTRACT_VERSION = "contractVersion"
EXTENSION_ADAPTER_KIND = "adapterKind"
EXTENSION_MODEL_REF = "modelRef"

#: What a completion's extension member carries, as the accepted record lists it.
COMPLETION_EXTENSION_FIELDS: tuple[str, ...] = (
    EXTENSION_REQUEST_ID,
    EXTENSION_CORRELATION_ID,
    EXTENSION_CONTRACT_VERSION,
    EXTENSION_ADAPTER_KIND,
    EXTENSION_MODEL_REF,
)

# -- the canonical error body -----------------------------------------------

#: The members of the canonical error body, as the accepted surface enumerates
#: them: a code, a safe message, the two identifiers, a ``retryable`` flag, and
#: optional ``retryAfterMs`` and ``details``. The two identifiers reuse the
#: extension member names above, because they are the same two identifiers.
ERROR_CODE = "code"
ERROR_MESSAGE = "message"
ERROR_RETRYABLE = "retryable"
ERROR_RETRY_AFTER_MS = "retryAfterMs"
ERROR_DETAILS = "details"

#: The members ``details`` carries. Each is a value this API produced — the
#: decided condition identifier, the kind of adapter behind this deployment, and
#: the name of the member a refusal is about. **None of them is a value read out
#: of a request.**
ERROR_CONDITION_ID = "conditionId"
ERROR_MEMBER = "member"

#: Every member the canonical error body may carry. ``retryAfterMs`` is optional
#: and is present only where a delay was decided; ``details`` is always present.
ERROR_BODY_FIELDS: tuple[str, ...] = (
    ERROR_CODE,
    ERROR_MESSAGE,
    EXTENSION_REQUEST_ID,
    EXTENSION_CORRELATION_ID,
    ERROR_RETRYABLE,
    ERROR_RETRY_AFTER_MS,
    ERROR_DETAILS,
)

# -- what this API does not publish -----------------------------------------

#: The three members the runtime returns that this platform does not forward. The
#: adapter already drops them; the constant is here so that a response builder
#: adding one back fails a test rather than a review.
NOT_PASSED_THROUGH: tuple[str, ...] = (
    "system_fingerprint",
    "timings",
    "prompt_tokens_details",
)

#: Where the shape above was decided, for a reader who arrives at this module
#: first.
SURFACE_DECISION_REF = (
    "docs/architecture/decisions/ADR-0010-inference-api-compatibility-surface.md"
)
SURFACE_DATA_REF = "docs/serving/inference-api-surface.v1alpha1.json"
SURFACE_DOCUMENT_REF = "docs/serving/inference-api-surface.md"
