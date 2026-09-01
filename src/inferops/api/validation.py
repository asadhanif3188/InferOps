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

``max_tokens`` and ``temperature`` are deliberately outside the accepted subset.
The frozen adapter interface has nowhere to carry either value, so accepting them
would promise caller controls the implementation cannot honour. The amendment to
`ADR 0010` narrows the surface instead: both are refused by the same strict
unknown-member policy as every other unsupported generation control. The
deployment-wide adapter configuration may still bound output tokens; that is an
operator setting, not a caller field.

Nothing in this module reads a clock, a file, or an environment variable, and no
message it produces repeats a value read out of the request.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .errors import REQUEST_OUTSIDE_SUBSET, STREAMING_REQUESTED, RequestRefused
from .surface import (
    ACCEPTED_MESSAGE_ROLES,
    ACCEPTED_REQUEST_FIELDS,
    MESSAGE_CONTENT,
    MESSAGE_FIELDS,
    MESSAGE_ROLE,
    REQUEST_MESSAGES,
    REQUEST_MODEL,
    REQUEST_STREAM,
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
    """

    model: str
    prompt: str


def parse_chat_completion(
    raw: bytes,
    *,
    served_model: str,
) -> ChatCompletionRequest:
    """Read one request body against the frozen subset, or refuse it.

    Args:
        raw: The request body as received.
        served_model: The identifier of the one model this deployment serves.

    Raises:
        RequestRefused: For any body the frozen subset does not accept.
    """
    body = _object_body(raw)
    _refuse_unknown_members(body)
    _require_present(body)

    model = _model(body, served_model)
    prompt = _prompt(body)
    _refuse_streaming(body)

    return ChatCompletionRequest(model=model, prompt=prompt)


# -- the body ---------------------------------------------------------------


def _object_body(raw: bytes) -> dict[str, object]:
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RequestRefused(
            REQUEST_OUTSIDE_SUBSET, BODY, "the request body is not valid UTF-8 JSON"
        ) from error
    if not isinstance(decoded, dict):
        raise RequestRefused(
            REQUEST_OUTSIDE_SUBSET, BODY, "the request body must be a JSON object"
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
        REQUEST_OUTSIDE_SUBSET,
        unknown[0],
        "this member is outside the frozen request subset this API accepts",
    )


def _require_present(body: dict[str, object]) -> None:
    for member in sorted(REQUIRED_REQUEST_FIELDS):
        if member not in body:
            raise RequestRefused(
                REQUEST_OUTSIDE_SUBSET, member, "this member is required and was absent"
            )


# -- the members ------------------------------------------------------------


def _model(body: dict[str, object], served_model: str) -> str:
    model = body[REQUEST_MODEL]
    if not isinstance(model, str) or not model:
        raise RequestRefused(
            REQUEST_OUTSIDE_SUBSET,
            REQUEST_MODEL,
            "this member must be a non-empty string",
        )
    if model != served_model:
        # Multi-model is declared false: the member is checked against the served
        # model rather than used to select one. The served model is named because
        # it is this deployment's own published identity, and not a value read
        # out of the request.
        raise RequestRefused(
            REQUEST_OUTSIDE_SUBSET,
            REQUEST_MODEL,
            "this deployment serves exactly one model and this member must name "
            f"it: {served_model}",
        )
    return model


def _prompt(body: dict[str, object]) -> str:
    messages = body[REQUEST_MESSAGES]
    if not isinstance(messages, list) or not messages:
        raise RequestRefused(
            REQUEST_OUTSIDE_SUBSET,
            REQUEST_MESSAGES,
            "this member must be a non-empty array of objects",
        )
    checked = [_checked_message(message) for message in messages]
    if len(checked) != 1 or checked[0][0] != ROLE_USER:
        raise RequestRefused(
            REQUEST_OUTSIDE_SUBSET, REQUEST_MESSAGES, SINGLE_MESSAGE_REASON
        )
    return checked[0][1]


def _checked_message(message: object) -> tuple[str, str]:
    """One message, checked against the subset and returned as role and content."""
    if not isinstance(message, dict):
        raise RequestRefused(
            REQUEST_OUTSIDE_SUBSET,
            REQUEST_MESSAGES,
            "every element of this member must be an object",
        )
    unknown = sorted(set(message) - MESSAGE_FIELDS)
    if unknown:
        raise RequestRefused(
            REQUEST_OUTSIDE_SUBSET,
            f"{REQUEST_MESSAGES}.{unknown[0]}",
            "this member is outside the frozen request subset this API accepts",
        )
    for member in sorted(MESSAGE_FIELDS):
        if member not in message:
            raise RequestRefused(
                REQUEST_OUTSIDE_SUBSET,
                f"{REQUEST_MESSAGES}.{member}",
                "this member is required and was absent",
            )
    role = message[MESSAGE_ROLE]
    if not isinstance(role, str) or role not in ACCEPTED_MESSAGE_ROLES:
        raise RequestRefused(
            REQUEST_OUTSIDE_SUBSET,
            f"{REQUEST_MESSAGES}.{MESSAGE_ROLE}",
            "this member must be one of: " + ", ".join(ACCEPTED_MESSAGE_ROLES),
        )
    content = message[MESSAGE_CONTENT]
    if not isinstance(content, str):
        raise RequestRefused(
            REQUEST_OUTSIDE_SUBSET,
            f"{REQUEST_MESSAGES}.{MESSAGE_CONTENT}",
            "this member must be a string; the array-of-parts form is outside "
            "the frozen request subset this API accepts",
        )
    return role, content


def _refuse_streaming(body: dict[str, object]) -> None:
    if REQUEST_STREAM not in body:
        return
    value = body[REQUEST_STREAM]
    if not isinstance(value, bool):
        raise RequestRefused(
            REQUEST_OUTSIDE_SUBSET, REQUEST_STREAM, "this member must be a boolean"
        )
    if value:
        # Declared `false` as a capability, and refused with the code the
        # accepted record names for it. The retryable override that travels with
        # this refusal belongs to the error contract V1-S1-005-PR2 standardises.
        raise RequestRefused(
            STREAMING_REQUESTED,
            REQUEST_STREAM,
            "streaming is declared unsupported by this deployment and retrying "
            "does not make a capability appear",
        )
