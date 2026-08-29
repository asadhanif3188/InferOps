"""Reading a chat-completion request against the frozen subset, and refusing the rest.

The accepted surface's unknown-member policy is **refuse**, and this module is
where that policy is executed. It is the strict reading of it: a member outside
:data:`~inferops.api.surface.ACCEPTED_REQUEST_FIELDS` is refused and the refusal
names the member, because silently ignoring a parameter that changes the result
hands a caller a wrong answer they have no way to detect.

**One reduction is made here that the accepted surface did not decide, and it is
a refusal rather than an invention.** The serving adapter interface `V1-S1-002`
froze takes a single ``prompt`` string. A ``messages`` array carrying a
conversation cannot be passed through it without flattening several messages into
one string — which would apply a prompt format no runtime chat template agreed
to, and would do it silently. So a request carrying more than one message, or a
single message whose role is not ``user``, is refused with ``contract-invalid``
naming ``messages``. That is a real reduction in what this surface accepts, it is
recorded rather than hidden, and the thing that would remove it is a
conversation-carrying parameter on the adapter interface, which is not this
change's to add.

**Two accepted members are validated and not forwarded, for the same reason.**
``max_tokens`` and ``temperature`` are in the frozen subset and are checked here,
and the frozen adapter interface has no parameter for either. What actually
bounds generation is the ``max_tokens`` on the adapter's own configuration, set
at composition time.

That is a conflict between two accepted records rather than a choice made here:
the accepted surface says both members are passed to the adapter, and the frozen
adapter interface has nowhere to pass them. Neither record is edited by this
change. The two members are accepted because the published subset accepts them,
they are validated because a member outside its stated type is still a refusal,
and the gap is recorded — in
[the API document](../../../docs/serving/inference-api.md), in the change's
validation record, and as follow-up work that needs a superseding decision on the
adapter interface. Refusing them instead would narrow a published subset without
a record deciding to.

Nothing in this module reads a clock, a file, or an environment variable, and no
message it produces repeats a value read out of the request.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .errors import CAPABILITY_UNAVAILABLE, CONTRACT_INVALID, RequestRefused
from .surface import (
    ACCEPTED_MESSAGE_ROLES,
    ACCEPTED_REQUEST_FIELDS,
    MESSAGE_CONTENT,
    MESSAGE_FIELDS,
    MESSAGE_ROLE,
    REQUEST_MAX_TOKENS,
    REQUEST_MESSAGES,
    REQUEST_MODEL,
    REQUEST_STREAM,
    REQUEST_TEMPERATURE,
    REQUIRED_REQUEST_FIELDS,
    ROLE_USER,
)

#: The member name a refusal uses when the failure is the body itself rather than
#: a member of it. It is not a member of the frozen subset and cannot collide
#: with one.
BODY = "body"

#: Why a conversation is refused, in one place so that the reason a caller reads
#: and the reason a reviewer reads are the same string.
SINGLE_MESSAGE_REASON = (
    "this deployment forwards exactly one user message; the serving adapter "
    "interface carries a single prompt and has no parameter a conversation "
    "could be passed through without inventing a prompt format"
)


@dataclass(frozen=True, slots=True)
class ChatCompletionRequest:
    """One accepted request, reduced to what the adapter interface can carry.

    Attributes:
        model: The model identifier the caller named. Already checked against the
            served model, so it is the served model by construction.
        prompt: The content of the single user message.
        max_tokens: The bound the caller asked for, or ``None``. Validated here
            and not forwarded; see the module docstring.
        temperature: The sampling temperature the caller asked for, or ``None``.
            Validated here and not forwarded, for the same reason.
    """

    model: str
    prompt: str
    max_tokens: int | None = None
    temperature: float | None = None


def parse_chat_completion(
    raw: bytes,
    *,
    served_model: str,
    max_tokens_ceiling: int | None,
) -> ChatCompletionRequest:
    """Read one request body against the frozen subset, or refuse it.

    Args:
        raw: The request body as received.
        served_model: The identifier of the one model this deployment serves.
        max_tokens_ceiling: The configured ceiling, or ``None`` when this
            deployment configures none. A ceiling is a deployment setting the
            accepted record deliberately left undecided.

    Raises:
        RequestRefused: For any body the frozen subset does not accept.
    """
    body = _object_body(raw)
    _refuse_unknown_members(body)
    _require_present(body)

    model = _model(body, served_model)
    prompt = _prompt(body)
    _refuse_streaming(body)

    return ChatCompletionRequest(
        model=model,
        prompt=prompt,
        max_tokens=_max_tokens(body, max_tokens_ceiling),
        temperature=_temperature(body),
    )


# -- the body ---------------------------------------------------------------


def _object_body(raw: bytes) -> dict[str, object]:
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RequestRefused(
            CONTRACT_INVALID, BODY, "the request body is not valid UTF-8 JSON"
        ) from error
    if not isinstance(decoded, dict):
        raise RequestRefused(
            CONTRACT_INVALID, BODY, "the request body must be a JSON object"
        )
    return decoded


def _refuse_unknown_members(body: dict[str, object]) -> None:
    """Refuse a member outside the subset, naming it and never its value.

    The member *name* is a caller-supplied string and it appears in exactly one
    place: the member position of the refusal. That is the accepted policy — the
    refusal names the offending member — and it is why the value beside it is
    never read.
    """
    unknown = sorted(set(body) - ACCEPTED_REQUEST_FIELDS)
    if not unknown:
        return
    raise RequestRefused(
        CONTRACT_INVALID,
        unknown[0],
        "this member is outside the frozen request subset this API accepts",
    )


def _require_present(body: dict[str, object]) -> None:
    for member in sorted(REQUIRED_REQUEST_FIELDS):
        if member not in body:
            raise RequestRefused(
                CONTRACT_INVALID, member, "this member is required and was absent"
            )


# -- the members ------------------------------------------------------------


def _model(body: dict[str, object], served_model: str) -> str:
    model = body[REQUEST_MODEL]
    if not isinstance(model, str) or not model:
        raise RequestRefused(
            CONTRACT_INVALID, REQUEST_MODEL, "this member must be a non-empty string"
        )
    if model != served_model:
        # Multi-model is declared false: the member is checked against the served
        # model rather than used to select one. The served model is named because
        # it is this deployment's own published identity, and not a value read
        # out of the request.
        raise RequestRefused(
            CONTRACT_INVALID,
            REQUEST_MODEL,
            "this deployment serves exactly one model and this member must name "
            f"it: {served_model}",
        )
    return model


def _prompt(body: dict[str, object]) -> str:
    messages = body[REQUEST_MESSAGES]
    if not isinstance(messages, list) or not messages:
        raise RequestRefused(
            CONTRACT_INVALID,
            REQUEST_MESSAGES,
            "this member must be a non-empty array of objects",
        )
    checked = [_checked_message(message) for message in messages]
    if len(checked) != 1 or checked[0][0] != ROLE_USER:
        raise RequestRefused(CONTRACT_INVALID, REQUEST_MESSAGES, SINGLE_MESSAGE_REASON)
    return checked[0][1]


def _checked_message(message: object) -> tuple[str, str]:
    """One message, checked against the subset and returned as role and content."""
    if not isinstance(message, dict):
        raise RequestRefused(
            CONTRACT_INVALID,
            REQUEST_MESSAGES,
            "every element of this member must be an object",
        )
    unknown = sorted(set(message) - MESSAGE_FIELDS)
    if unknown:
        raise RequestRefused(
            CONTRACT_INVALID,
            f"{REQUEST_MESSAGES}.{unknown[0]}",
            "this member is outside the frozen request subset this API accepts",
        )
    for member in sorted(MESSAGE_FIELDS):
        if member not in message:
            raise RequestRefused(
                CONTRACT_INVALID,
                f"{REQUEST_MESSAGES}.{member}",
                "this member is required and was absent",
            )
    role = message[MESSAGE_ROLE]
    if not isinstance(role, str) or role not in ACCEPTED_MESSAGE_ROLES:
        raise RequestRefused(
            CONTRACT_INVALID,
            f"{REQUEST_MESSAGES}.{MESSAGE_ROLE}",
            "this member must be one of: " + ", ".join(ACCEPTED_MESSAGE_ROLES),
        )
    content = message[MESSAGE_CONTENT]
    if not isinstance(content, str):
        raise RequestRefused(
            CONTRACT_INVALID,
            f"{REQUEST_MESSAGES}.{MESSAGE_CONTENT}",
            "this member must be a string; the array-of-parts form is outside "
            "the frozen request subset this API accepts",
        )
    return role, content


def _max_tokens(body: dict[str, object], ceiling: int | None) -> int | None:
    if REQUEST_MAX_TOKENS not in body:
        return None
    value = body[REQUEST_MAX_TOKENS]
    # `bool` is a subclass of `int` in Python and `true` is a JSON boolean, so
    # the boolean check is what stops `"max_tokens": true` being read as 1.
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RequestRefused(
            CONTRACT_INVALID,
            REQUEST_MAX_TOKENS,
            "this member must be a positive integer",
        )
    if ceiling is not None and value > ceiling:
        # Refused rather than silently clamped, which is what the accepted record
        # requires. The ceiling is this deployment's own configuration.
        raise RequestRefused(
            CONTRACT_INVALID,
            REQUEST_MAX_TOKENS,
            f"this member must not exceed this deployment's ceiling of {ceiling}",
        )
    return value


def _temperature(body: dict[str, object]) -> float | None:
    if REQUEST_TEMPERATURE not in body:
        return None
    value = body[REQUEST_TEMPERATURE]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RequestRefused(
            CONTRACT_INVALID, REQUEST_TEMPERATURE, "this member must be a number"
        )
    return float(value)


def _refuse_streaming(body: dict[str, object]) -> None:
    if REQUEST_STREAM not in body:
        return
    value = body[REQUEST_STREAM]
    if not isinstance(value, bool):
        raise RequestRefused(
            CONTRACT_INVALID, REQUEST_STREAM, "this member must be a boolean"
        )
    if value:
        # Declared `false` as a capability, and refused with the code the
        # accepted record names for it. The retryable override that travels with
        # this refusal belongs to the error contract V1-S1-005-PR2 standardises.
        raise RequestRefused(
            CAPABILITY_UNAVAILABLE,
            REQUEST_STREAM,
            "streaming is declared unsupported by this deployment and retrying "
            "does not make a capability appear",
        )
