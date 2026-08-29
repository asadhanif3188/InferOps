"""The request this adapter sends, the response it reads, and the codes it maps to.

Three pure functions and one table, kept apart from the adapter that calls them
so that each can be read — and asserted — without a transport, a clock, or an
event loop.

**The mapping is not invented here.** `ADR 0010` decided which condition produces
which canonical code, and
[`docs/serving/inference-api-surface.v1alpha1.json`](../../../../docs/serving/inference-api-surface.v1alpha1.json)
is where that decision is published. The table below is a *copy* of the rows this
adapter can reach, carrying the same condition identifiers, and
``tests/adapters/test_llama_server_inference.py`` reads the accepted file and
fails when a copy drifts. That is the same treatment the pins get, for the same
reason: a constant nobody compares to its source is a copy that drifts.

Two consequences of following that record are worth stating, because both are
places a reader might expect something else:

- **``rate-limited`` is never produced.** The accepted record lists it among the
  codes V1 does not emit, on the ground that V1 has no rate limiter and the
  runtime's own deferral series is a gauge of instantaneous state rather than a
  limit InferOps enforces. A runtime answering `429` is therefore an
  ``internal-error`` like any other unexpected status, and not a rate limit this
  platform is claiming to have observed.
- **An unreachable runtime is ``capability-unavailable``, not
  ``model-not-ready``.** The canonical vocabulary has no member meaning
  *unavailable*, and the accepted record picks the one it has. The readiness
  question — *is the model ready?* — is answered separately and still reports a
  runtime it cannot reach as not ready;
  :mod:`~inferops.adapters.llama_cpp.readiness` is where that lives.

**The request carries no sampling parameter.** `ADR 0002` records the sampling
defaults as undecided, and the accepted surface repeats it. The frozen adapter
protocol has no parameter for one either, so there is nothing to pass through and
nothing to invent; the runtime's own defaults apply, and a request-time
temperature is `V1-S1-005`'s to wire when the API that receives one exists.

**No error message here repeats anything read from a request or a response.**
Each one names the condition in this module's vocabulary. A runtime's own words
are where a container path, a host name, or a prompt fragment arrives in a
caller's error, and this module cannot tell which message is which.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ...domain.context import RequestContext
from ...domain.serving import (
    AdapterConfiguration,
    CanonicalError,
    CapabilityUnavailableError,
    InternalError,
    InvalidValueError,
    ModelNotReadyError,
    RequestTimeoutError,
    TokenUsage,
    UpstreamTimeoutError,
)
from .readiness import HEALTH_LOADING_STATUS
from .settings import LlamaServerSettings
from .transport import (
    TransportError,
    TransportProtocolError,
    TransportTimeout,
    TransportUnreachable,
)

#: The accepted record every row in :data:`ERROR_CONDITIONS` is copied from.
SURFACE_DECISION_REF = (
    "docs/architecture/decisions/ADR-0010-inference-api-compatibility-surface.md"
)
SURFACE_DATA_REF = "docs/serving/inference-api-surface.v1alpha1.json"

# -- the request ------------------------------------------------------------

#: Members of the request body this adapter sends.
REQUEST_MODEL_KEY = "model"
REQUEST_MESSAGES_KEY = "messages"
REQUEST_MAX_TOKENS_KEY = "max_tokens"
REQUEST_CHAT_TEMPLATE_KWARGS_KEY = "chat_template_kwargs"

#: Members of one message.
MESSAGE_ROLE_KEY = "role"
MESSAGE_CONTENT_KEY = "content"

#: The only role this adapter sends. The protocol hands it one prompt string and
#: publishes no conversation, so there is exactly one message and it is the
#: caller's. A system message would be content this adapter authored, appearing in
#: a completion nobody asked for it in.
ROLE_USER = "user"

#: The chat-template argument that turns off the selected model's reasoning
#: block. It is sent because the Sprint 0 trial's request carried it and the
#: response shape this module normalises is the shape *that* request produced;
#: dropping it would mean parsing a response nobody in this project has seen. It
#: is not a sampling parameter, and `ADR 0002`'s deferral of the sampling
#: defaults does not reach it. The decision is recorded in the change's own
#: validation record rather than left implicit here.
ENABLE_THINKING_KEY = "enable_thinking"
ENABLE_THINKING_VALUE = False


def build_request(
    configuration: AdapterConfiguration,
    settings: LlamaServerSettings,
    prompt: str,
) -> dict[str, object]:
    """The chat-completion body for one prompt.

    ``model`` is the runtime's own alias rather than the platform identifier: this
    is the runtime's API, and the alias is the name the process was started with
    and answers to. The platform identifier is what the *result* reports, and
    :func:`~inferops.adapters.llama_cpp.metadata.describe_model` explains why the
    two are different strings by construction.

    ``max_tokens`` appears only when a caller configured one. An omitted bound is
    an omitted member, never a default this adapter chose.
    """
    body: dict[str, object] = {
        REQUEST_MODEL_KEY: settings.model_alias,
        REQUEST_MESSAGES_KEY: [
            {MESSAGE_ROLE_KEY: ROLE_USER, MESSAGE_CONTENT_KEY: prompt}
        ],
        REQUEST_CHAT_TEMPLATE_KWARGS_KEY: {ENABLE_THINKING_KEY: ENABLE_THINKING_VALUE},
    }
    if configuration.max_tokens is not None:
        body[REQUEST_MAX_TOKENS_KEY] = configuration.max_tokens
    return body


# -- the response -----------------------------------------------------------

#: Members of a chat-completion response this adapter reads. Everything else the
#: runtime returns is left where it is: `system_fingerprint`, `timings`, and
#: `prompt_tokens_details` are each recorded in the accepted surface as fields
#: this platform does not pass through, and a value nobody keeps is a value
#: nobody has to redact.
RESPONSE_CHOICES_KEY = "choices"
RESPONSE_MESSAGE_KEY = "message"
RESPONSE_CONTENT_KEY = "content"
RESPONSE_FINISH_REASON_KEY = "finish_reason"
RESPONSE_MODEL_KEY = "model"
RESPONSE_USAGE_KEY = "usage"
USAGE_PROMPT_TOKENS_KEY = "prompt_tokens"
USAGE_COMPLETION_TOKENS_KEY = "completion_tokens"

#: The one message this module produces for a body it cannot read. It names the
#: condition and carries nothing from the body.
UNREADABLE_RESPONSE_MESSAGE = (
    "the runtime's completion response could not be read into the shape this "
    "adapter publishes"
)


@dataclass(frozen=True, slots=True)
class NormalizedCompletion:
    """One completion, reduced to what the domain's result object carries.

    ``reported_model`` is the alias the runtime echoed. It is kept separate from
    the identity the result declares so that a disagreement between what was
    configured and what answered is *visible* rather than silently overwritten by
    whichever of the two the adapter happened to prefer.
    """

    content: str
    finish_reason: str | None = None
    usage: TokenUsage | None = None
    reported_model: str | None = None


def normalize_response(
    body: object,
    *,
    context: RequestContext,
) -> NormalizedCompletion:
    """Read one chat-completion body, or refuse it.

    Every member is read against the shape the feasibility record preserved.
    Absence of ``usage`` is absence — the domain publishes ``None`` for a value
    that was not provided, and this adapter never estimates one — while a
    ``usage`` that is present and malformed is a refusal, because a token count
    nobody can read is not a token count that is missing.

    Raises:
        InternalError: If the body is not a completion this adapter can read.
    """
    payload = _mapping(body, context)
    choices = payload.get(RESPONSE_CHOICES_KEY)
    if not isinstance(choices, list) or not choices:
        raise _unreadable(context)
    choice = _mapping(choices[0], context)
    message = _mapping(choice.get(RESPONSE_MESSAGE_KEY), context)
    content = message.get(RESPONSE_CONTENT_KEY)
    if not isinstance(content, str):
        raise _unreadable(context)
    return NormalizedCompletion(
        content=content,
        finish_reason=_optional_str(choice.get(RESPONSE_FINISH_REASON_KEY), context),
        usage=_usage(payload.get(RESPONSE_USAGE_KEY), context),
        reported_model=_optional_str(payload.get(RESPONSE_MODEL_KEY), context),
    )


def _mapping(value: object, context: RequestContext) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _unreadable(context)
    return value


def _optional_str(value: object, context: RequestContext) -> str | None:
    """A string member, where absence is a legitimate answer and a wrong type
    is not."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise _unreadable(context)
    return value or None


def _token_count(
    source: Mapping[str, object], key: str, context: RequestContext
) -> int:
    value = source.get(key)
    # `bool` is a subclass of `int`, so the second half is what stops a JSON
    # `true` being read as a count of one. The metadata parser refuses the same
    # thing in the same way.
    if not isinstance(value, int) or isinstance(value, bool):
        raise _unreadable(context)
    return value


def _usage(value: object, context: RequestContext) -> TokenUsage | None:
    if value is None:
        return None
    counts = _mapping(value, context)
    try:
        return TokenUsage(
            input_tokens=_token_count(counts, USAGE_PROMPT_TOKENS_KEY, context),
            output_tokens=_token_count(counts, USAGE_COMPLETION_TOKENS_KEY, context),
        )
    except InvalidValueError:
        # The domain refused the pair. It knows the constraint; this module knows
        # the caller, and re-raising as canonical is the division of labour the
        # domain's own error documentation describes.
        raise _unreadable(context) from None


def _unreadable(context: RequestContext) -> InternalError:
    return InternalError(UNREADABLE_RESPONSE_MESSAGE, context=context)


# -- the mapping ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ErrorCondition:
    """One row of the accepted error mapping, as this adapter holds it.

    ``condition_id`` is the identifier the accepted record publishes, so a reader
    holding one can find the other. ``observed_in_trial`` repeats what that record
    says about whether anything ever saw this condition happen — which for all but
    one of them is *no*, and saying so is the difference between a mapping and a
    claim.
    """

    condition_id: str
    code: str
    observed_in_trial: bool
    basis: str


#: The conditions this adapter can reach, copied from the accepted record. The
#: rows it cannot reach — a request outside the frozen subset, a streaming
#: request, an unsupported contract version — belong to the API layer that has
#: not been built, and are absent rather than stubbed.
ERROR_CONDITIONS: tuple[ErrorCondition, ...] = (
    ErrorCondition(
        condition_id="model-loading",
        code="model-not-ready",
        observed_in_trial=True,
        basis=(
            "The runtime answers 503 while it loads the model. The control plane "
            "recorded exactly that during the first start of the feasibility "
            "trial."
        ),
    ),
    ErrorCondition(
        condition_id="runtime-unreachable",
        code="capability-unavailable",
        observed_in_trial=False,
        basis=(
            "No connection to the runtime could be established. The canonical "
            "vocabulary has no member meaning 'unavailable', and the accepted "
            "record picks the one it has."
        ),
    ),
    ErrorCondition(
        condition_id="runtime-timeout",
        code="upstream-timeout",
        observed_in_trial=False,
        basis=(
            "The runtime did not answer within the deadline this adapter gave "
            "it. The far side ran out of time, so the timeout is upstream."
        ),
    ),
    ErrorCondition(
        condition_id="caller-deadline",
        code="request-timeout",
        observed_in_trial=False,
        basis=(
            "This adapter's own outer deadline elapsed. It is reached only when "
            "the transport did not honour the budget it was given, which is why "
            "the outer deadline exists at all."
        ),
    ),
    ErrorCondition(
        condition_id="runtime-error-response",
        code="internal-error",
        observed_in_trial=False,
        basis=(
            "The runtime answered with a status other than 2xx and other than "
            "the 503 that means loading. A 429 lands here rather than on "
            "'rate-limited', which the accepted record lists among the codes V1 "
            "does not emit."
        ),
    ),
    ErrorCondition(
        condition_id="runtime-unparseable-response",
        code="internal-error",
        observed_in_trial=False,
        basis=(
            "The runtime answered 2xx with a body this adapter could not read "
            "into the shape it publishes."
        ),
    ),
)

#: The mapping as a lookup, so a caller naming a condition cannot name one that
#: is not in the table.
ERROR_CODE_BY_CONDITION: Mapping[str, str] = {
    row.condition_id: row.code for row in ERROR_CONDITIONS
}

#: The lowest and highest status this adapter reads as success.
SUCCESS_STATUS_FLOOR = 200
SUCCESS_STATUS_CEILING = 299

#: Messages for the conditions a status produces. Each names the condition and
#: carries no status code, no body, and no URL: a caller does not need the
#: runtime's own words to know which of these happened.
LOADING_MESSAGE = "the runtime is loading the model"
RUNTIME_ERROR_MESSAGE = "the runtime answered with a status this adapter refuses"


def is_success(status_code: int) -> bool:
    """Whether a status is one this adapter reads a completion out of."""
    return SUCCESS_STATUS_FLOOR <= status_code <= SUCCESS_STATUS_CEILING


def error_for_status(
    status_code: int,
    context: RequestContext,
) -> CanonicalError | None:
    """The canonical error a completion status produces, or ``None`` on success.

    Two branches, and the second is deliberately wide. `503` is the loading
    status the trial observed; **everything** else that is not a success is
    ``internal-error``, including a `429`, a `3xx` this transport did not follow,
    and a status nobody has ever seen. Narrowing that would mean inventing
    behaviour for statuses this project has not observed.
    """
    if is_success(status_code):
        return None
    if status_code == HEALTH_LOADING_STATUS:
        return ModelNotReadyError(LOADING_MESSAGE, context=context)
    return InternalError(RUNTIME_ERROR_MESSAGE, context=context)


#: Messages for the transport conditions. As above, each names the condition.
UNREACHABLE_MESSAGE = "the runtime could not be reached"
UPSTREAM_TIMEOUT_MESSAGE = "the runtime did not answer within the adapter's deadline"
REQUEST_TIMEOUT_MESSAGE = "the adapter's own deadline for this request elapsed"
TRANSPORT_FAILURE_MESSAGE = "the request to the runtime could not be completed"


def error_for_transport_failure(
    error: TransportError,
    context: RequestContext,
) -> CanonicalError:
    """The canonical error a transport failure produces.

    The transport's own exception carries no text from the far side, so nothing
    is dropped in this translation — which is the point of that constraint being
    on the transport rather than here.
    """
    if isinstance(error, TransportTimeout):
        return UpstreamTimeoutError(UPSTREAM_TIMEOUT_MESSAGE, context=context)
    if isinstance(error, TransportUnreachable):
        return unreachable_error(context)
    if isinstance(error, TransportProtocolError):
        return InternalError(UNREADABLE_RESPONSE_MESSAGE, context=context)
    return InternalError(TRANSPORT_FAILURE_MESSAGE, context=context)


def request_deadline_error(context: RequestContext) -> RequestTimeoutError:
    """The error the adapter's own outer deadline produces."""
    return RequestTimeoutError(REQUEST_TIMEOUT_MESSAGE, context=context)


def unreachable_error(context: RequestContext) -> CapabilityUnavailableError:
    """The error an unreachable runtime produces, wherever it is discovered.

    A readiness probe that could not reach the runtime and a completion that
    could not be delivered are the same condition, and this function is why they
    cannot acquire two different codes or two different messages.
    """
    return CapabilityUnavailableError(UNREACHABLE_MESSAGE, context=context)
