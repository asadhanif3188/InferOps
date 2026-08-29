"""The bodies this API returns, built from what the adapter reported.

Every shape here is a copy of a row in the accepted surface, and the agreement
suite reads that file rather than trusting this one. What the module adds is the
rules the shape does not state on its own, and each is worth reading before the
code.

**Absence is published as ``null``, never as a zero and never as an estimate.**
``usage`` is the counts the adapter supplied and is ``null`` where it supplied
none. A count this API derived by tokenising a prompt itself would be an estimate
wearing a measurement's clothes, and the mock and real boundary names token
accounting as a property a mock cannot honestly reproduce.

**A capability is published from what the selected adapter declared, not from a
constant.** Two of the four capability identifiers the accepted surface publishes
have an adapter declaration behind them — ``streaming`` and ``tokenUsage`` — and
those two are read from :meth:`~inferops.domain.serving.ServingAdapter.get_capabilities`
on every request rather than from a table here. ``multiModel`` is derived from
the list this endpoint actually returns, which serves exactly one model.
``deterministicSampling`` is published as ``null``: the frozen adapter interface
carries no declaration for it, and `ADR 0010`'s value of ``true`` rests on a
Sprint 0 observation of the runtime rather than on anything the selected adapter
says about itself. Publishing that observation as this deployment's own
declaration would be the assumption the "declared, not assumed" rule exists to
prevent.

**``adapterKind`` is on every response because it decides what the response may
be used to claim.** It is not decoration and it is not deployment configuration:
a completion carries the kind the adapter's own result declared, and
:mod:`inferops.api.application` refuses to serve a completion whose declared kind
disagrees with the kind this API was composed with.

**No response carries a prompt, a secret, a stack trace, or a runtime message.**
The three members the runtime returns and this platform does not forward —
``system_fingerprint``, ``timings``, and ``prompt_tokens_details`` — never reach
this module: the adapter drops them, and
:data:`~inferops.api.surface.NOT_PASSED_THROUGH` is what a test checks a built
body against.
"""

from __future__ import annotations

from ..domain.serving import (
    AdapterCapability,
    InferenceResult,
    ModelMetadata,
    RuntimeMetadata,
)
from .surface import (
    ADAPTER_CAPABILITY_FOR,
    CAPABILITY_DETERMINISTIC_SAMPLING,
    CAPABILITY_MULTI_MODEL,
    COMPLETION_OBJECT,
    CONTRACT_VERSION,
    EXTENSION_ADAPTER_KIND,
    EXTENSION_CONTRACT_VERSION,
    EXTENSION_CORRELATION_ID,
    EXTENSION_MEMBER,
    EXTENSION_MODEL_REF,
    EXTENSION_REQUEST_ID,
    MESSAGE_CONTENT,
    MESSAGE_ROLE,
    MODEL_LIST_OBJECT,
    MODEL_OBJECT,
    MODEL_OWNER,
    ROLE_ASSISTANT,
)

#: The status a liveness answer reports about the process.
STATUS_ALIVE = "alive"

#: The two readiness answers. ``ready`` means the selected adapter said it can
#: accept an inference request now; ``not-ready`` means it did not, or that this
#: API has stopped accepting work.
STATUS_READY = "ready"
STATUS_NOT_READY = "not-ready"


def completion_body(
    result: InferenceResult,
    *,
    completion_id: str,
    created: int,
    request_id: str,
    correlation_id: str,
) -> dict[str, object]:
    """One chat completion, in the borrowed shape with the extension beside it.

    ``choices`` carries exactly one element, because ``n`` is outside the frozen
    subset and this API never produces more than one.
    """
    return {
        "id": completion_id,
        "object": COMPLETION_OBJECT,
        "created": created,
        "model": result.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    MESSAGE_ROLE: ROLE_ASSISTANT,
                    MESSAGE_CONTENT: result.content,
                },
                "finish_reason": result.finish_reason,
            }
        ],
        "usage": _usage(result),
        EXTENSION_MEMBER: {
            EXTENSION_REQUEST_ID: request_id,
            EXTENSION_CORRELATION_ID: correlation_id,
            EXTENSION_CONTRACT_VERSION: CONTRACT_VERSION,
            EXTENSION_ADAPTER_KIND: result.adapter_kind,
            EXTENSION_MODEL_REF: result.model,
        },
    }


def _usage(result: InferenceResult) -> dict[str, int] | None:
    """The counts the adapter supplied, or ``null``. Never zero-filled."""
    if result.usage is None:
        return None
    return {
        "prompt_tokens": result.usage.input_tokens,
        "completion_tokens": result.usage.output_tokens,
        "total_tokens": result.usage.total_tokens,
    }


def models_body(
    model: ModelMetadata,
    runtime: RuntimeMetadata,
    capabilities: list[AdapterCapability],
    *,
    adapter_kind: str,
    created: int,
) -> dict[str, object]:
    """The one model this deployment serves, with the runtime descriptor beside it.

    ``created`` is the moment this deployment began serving, not a model build
    date. There is no model registry behind this endpoint and no build date to
    read from one, and a fabricated timestamp would be worse than a true one that
    means less than a reader might assume.

    The request and correlation identifiers are not repeated in the body here.
    They travel in the response headers on every response this API sends, and the
    accepted record enumerates this endpoint's extension member as the runtime
    descriptor and the declared capability set — with ``adapterKind`` and
    ``contractVersion`` beside them, because the first is on every response by
    decision and the second is what stops the ``/v1`` prefix being read as an
    InferOps version.
    """
    data: list[dict[str, object]] = [
        {
            "id": model.identifier,
            "object": MODEL_OBJECT,
            "created": created,
            "owned_by": MODEL_OWNER,
        }
    ]
    return {
        "object": MODEL_LIST_OBJECT,
        "data": data,
        EXTENSION_MEMBER: {
            EXTENSION_CONTRACT_VERSION: CONTRACT_VERSION,
            EXTENSION_ADAPTER_KIND: adapter_kind,
            "runtime": {
                "name": runtime.name,
                "version": runtime.version,
                "modelRevision": model.revision,
            },
            "capabilities": declared_capabilities(
                capabilities, served_models=len(data)
            ),
        },
    }


def declared_capabilities(
    capabilities: list[AdapterCapability],
    *,
    served_models: int,
) -> dict[str, bool | None]:
    """The four capability identifiers the accepted surface publishes.

    Two are read from the adapter's own declaration, one is derived from the
    number of models this endpoint returns, and one is ``null`` because nothing
    this API can ask declares it. ``null`` is the honest value for a question
    nobody answered; ``true`` would be this API asserting a Sprint 0 observation
    as its own declaration.
    """
    declared = {entry.name: entry.supported for entry in capabilities}
    published: dict[str, bool | None] = {
        published_id: declared.get(adapter_name)
        for published_id, adapter_name in ADAPTER_CAPABILITY_FOR.items()
    }
    published[CAPABILITY_DETERMINISTIC_SAMPLING] = None
    published[CAPABILITY_MULTI_MODEL] = served_models > 1
    return published


def live_body() -> dict[str, object]:
    """Whether this process is alive. It answers nothing about the model.

    It carries no adapter state, no runtime identity, and no configuration, which
    is what makes it answerable while the model is still loading and while this
    API is draining.
    """
    return {"status": STATUS_ALIVE}


def ready_body(
    *, ready: bool, adapter_kind: str, lifecycle_state: str
) -> dict[str, object]:
    """Whether the selected adapter can accept an inference request now.

    It carries the adapter kind and the lifecycle state and nothing else. No
    endpoint, no credential, no path, and no runtime message reaches a health
    response — a readiness probe is the surface most likely to be reachable by
    something that should not see any of them.
    """
    return {
        "status": STATUS_READY if ready else STATUS_NOT_READY,
        "adapterKind": adapter_kind,
        "state": lifecycle_state,
    }


def error_body(
    code: str,
    message: str,
    *,
    request_id: str,
    correlation_id: str,
) -> dict[str, object]:
    """A refusal, in the provisional shape this change carries.

    `ADR 0010` decided a canonical error body with a ``retryable`` flag and
    optional ``retryAfterMs`` and ``details`` beside the four members below.
    `V1-S1-005-PR2` is the change that standardises it; this is deliberately the
    subset those endpoints cannot answer without, and it is a subset rather than
    a variant so that PR2 adds members instead of renaming them.

    The message names a member and a constraint. It never carries a value read
    out of the request, a runtime's own words, a stack trace, or a path.
    """
    return {
        "code": code,
        "message": message,
        EXTENSION_REQUEST_ID: request_id,
        EXTENSION_CORRELATION_ID: correlation_id,
    }
