"""What the runtime says about itself, read carefully and believed narrowly.

`llama-server` publishes two descriptive endpoints. ``/v1/models`` echoes the
alias the process was started with, and ``/props`` describes the process and the
file it loaded. The Sprint 0 trial read both, and what it recorded is the reason
this module exists in the shape it does:

> The ``id`` is the alias this trial passed on the command line, so the runtime
> echoing it proves the flag was accepted and nothing more. […] The runtime
> exposes no hash of the file it loaded, so there is no single check that closes
> this.

So an observation here is never promoted into a pin. :func:`describe_model`
reports the **configured** model revision, because that is a pin the project
holds; it does not report the revision as something the runtime attested, since
the runtime attests no such thing. What ties a running process to the pinned
bytes is the SHA-256 verified before the file was mounted, the read-only mount,
and the self-reported parameter count and quantisation agreeing with the
published model — three things together, none of them this call.

**The exact JSON shape of these two responses was not captured verbatim in the
feasibility record**; what the record preserves is the field names and their
values. Every parser below therefore reads a small number of members, treats an
absent one as absence rather than as a default, and refuses a payload whose shape
it cannot read instead of guessing at it. Confirming the shape against a live
runtime belongs to the pull request that first issues these calls.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ...domain.serving import InternalError, ModelMetadata, RuntimeMetadata
from .pins import (
    LLAMA_SERVER_RUNTIME_ID,
    LLAMA_SERVER_RUNTIME_NAME,
    PINNED_IMAGE_DIGEST,
    PINNED_MODEL_REVISION,
)

#: The member of a ``/v1/models`` payload holding the model list.
MODELS_DATA_KEY = "data"

#: The member of a model entry holding the alias the runtime was started with.
MODEL_ID_KEY = "id"

#: Members of a ``/props`` payload this adapter reads. Everything else in that
#: payload — the chat template above all — is deliberately not read: it is large,
#: it is not identity, and a value nobody uses is a value nobody has to redact.
PROPS_MODEL_PATH_KEY = "model_path"
PROPS_BUILD_INFO_KEY = "build_info"
PROPS_TOTAL_SLOTS_KEY = "total_slots"

#: Reason codes for a disagreement between what was configured and what the
#: runtime reports. Stable strings, because a caller writing one into a log or an
#: evidence record needs it not to change when the sentence around it does.
ALIAS_DISAGREEMENT = "runtime-model-alias-differs-from-configured-alias"
MODEL_FILE_DISAGREEMENT = "runtime-model-file-differs-from-configured-file"


@dataclass(frozen=True, slots=True)
class ObservedRuntimeIdentity:
    """Identity as the runtime reported it. Every member may be absent.

    Absence is a first-class answer here and is never filled in: a runtime that
    did not report its build is a runtime whose build is unknown, and ``None``
    says that where an invented string would not.

    ``model_file`` is the weight file's own name rather than the path the runtime
    reported. The directory is a container path, it is identity for nothing, and
    a value this adapter does not keep is a value it cannot leak into a log line
    or an evidence record.
    """

    model_alias: str | None = None
    model_file: str | None = None
    build_info: str | None = None
    total_slots: int | None = None


def _as_mapping(payload: object, subject: str) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise InternalError(f"the runtime's {subject} response is not an object")
    return payload


def _optional_str(source: Mapping[str, object], key: str, subject: str) -> str | None:
    value = source.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise InternalError(f"the runtime's {subject} response has a malformed {key}")
    return value or None


def parse_models_payload(payload: object) -> str | None:
    """The alias a ``/v1/models`` response reports, or ``None`` if it lists none.

    An empty list is an answer — the runtime holds no model — and is returned as
    absence. A payload whose shape cannot be read is a failure, because silently
    returning absence there would make an unreadable response indistinguishable
    from an empty one.
    """
    body = _as_mapping(payload, "model list")
    entries = body.get(MODELS_DATA_KEY)
    if not isinstance(entries, list):
        raise InternalError("the runtime's model list response has no model list")
    if not entries:
        return None
    first = entries[0]
    if not isinstance(first, Mapping):
        raise InternalError("the runtime's model list holds a malformed entry")
    return _optional_str(first, MODEL_ID_KEY, "model list")


def parse_props_payload(payload: object) -> ObservedRuntimeIdentity:
    """The identity a ``/props`` response reports, with every member optional."""
    body = _as_mapping(payload, "properties")
    model_path = _optional_str(body, PROPS_MODEL_PATH_KEY, "properties")
    total_slots = body.get(PROPS_TOTAL_SLOTS_KEY)
    # `bool` is a subclass of `int`, so the second half of this test is what stops
    # a JSON `true` being read as a slot count of one. Every other type mismatch
    # in this parser is refused rather than coerced, and this one is no different.
    if total_slots is not None and (
        not isinstance(total_slots, int) or isinstance(total_slots, bool)
    ):
        raise InternalError(
            "the runtime's properties response has a malformed slot count"
        )
    return ObservedRuntimeIdentity(
        model_alias=None,
        model_file=None if model_path is None else model_path.rsplit("/", 1)[-1],
        build_info=_optional_str(body, PROPS_BUILD_INFO_KEY, "properties"),
        total_slots=total_slots,
    )


def observe(
    *,
    models_payload: object | None = None,
    props_payload: object | None = None,
) -> ObservedRuntimeIdentity:
    """Read both descriptive responses into one identity.

    Either may be omitted. Omitting both is legal and produces an identity in
    which everything is absent, which is exactly what is true before anything has
    been asked.
    """
    alias = None if models_payload is None else parse_models_payload(models_payload)
    props = (
        ObservedRuntimeIdentity()
        if props_payload is None
        else parse_props_payload(props_payload)
    )
    return ObservedRuntimeIdentity(
        model_alias=alias,
        model_file=props.model_file,
        build_info=props.build_info,
        total_slots=props.total_slots,
    )


def describe_runtime(observed: ObservedRuntimeIdentity) -> RuntimeMetadata:
    """Runtime metadata: the selected runtime's name, and the best version held.

    The version is the build string when the process has reported one and the
    pinned image digest otherwise. Both are real identifiers of real bytes and
    neither is invented; the digest is the stronger of the two, because it
    identifies the image rather than what a process inside it says about itself.
    """
    return RuntimeMetadata(
        name=LLAMA_SERVER_RUNTIME_NAME,
        version=observed.build_info or PINNED_IMAGE_DIGEST,
        identifier=LLAMA_SERVER_RUNTIME_ID,
    )


def describe_model(
    identifier: str,
    revision: str = PINNED_MODEL_REVISION,
) -> ModelMetadata:
    """Model metadata: the identity the platform configured, and the pinned revision.

    The identifier is the platform's, not the runtime's alias. They are different
    strings by construction — the contract's model reference is kebab-case and the
    runtime's alias is whatever the operator passed on the command line — and the
    contract publishes the platform's. Whether the runtime is serving the alias it
    was configured with is a separate question, and
    :func:`identity_disagreements` is where it is asked.
    """
    return ModelMetadata(identifier=identifier, revision=revision)


def identity_disagreements(
    observed: ObservedRuntimeIdentity,
    *,
    configured_alias: str,
    configured_model_file: str,
) -> tuple[str, ...]:
    """Reason codes for every way the runtime disagrees with its configuration.

    An unobserved member is not a disagreement. A runtime that reported no build
    string has not contradicted anything, and treating silence as conflict would
    make every partial observation look like a fault.
    """
    reasons: list[str] = []
    if observed.model_alias is not None and observed.model_alias != configured_alias:
        reasons.append(ALIAS_DISAGREEMENT)
    if observed.model_file is not None and observed.model_file != configured_model_file:
        reasons.append(MODEL_FILE_DISAGREEMENT)
    return tuple(reasons)
