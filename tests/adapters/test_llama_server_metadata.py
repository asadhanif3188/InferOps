"""Metadata: what the runtime is believed about, and what it is not.

The feasibility record is explicit that the runtime's echoed model ``id`` proves
the alias flag was accepted and nothing more, and that the runtime exposes no
hash of the file it loaded. Two obligations follow, and both are tested here:

**An observation is never promoted into a pin.** The revision reported through
the domain's ``ModelMetadata`` is the configured pin, not something the runtime
attested, and the identifier is the platform's rather than the runtime's alias.

**Absence is preserved.** A runtime that reported no build string has a version
that is unknown, and the fallback is the pinned image digest — a real identifier
of real bytes — rather than an invented version. A payload whose shape cannot be
read is a failure rather than an absence, because an unreadable answer and an
empty one are different facts.

The exact JSON shape of these responses was not captured verbatim by the trial;
the parsers read a small number of members and refuse the rest, and confirming
the shape against a live runtime belongs to the change that first calls them.

Every check reads objects from this distribution. No network, no cluster, no
model, no clock, no randomness. Every payload below was written by this suite.
"""

from __future__ import annotations

import pytest

from inferops.adapters.llama_cpp import (
    ALIAS_DISAGREEMENT,
    LLAMA_SERVER_RUNTIME_NAME,
    MODEL_FILE_DISAGREEMENT,
    OBSERVED_BUILD_INFO,
    PINNED_IMAGE_DIGEST,
    PINNED_MODEL_FILE,
    PINNED_MODEL_REVISION,
    ObservedRuntimeIdentity,
    describe_model,
    describe_runtime,
    identity_disagreements,
    observe,
    parse_models_payload,
    parse_props_payload,
)
from inferops.domain.serving import InternalError, ModelMetadata, RuntimeMetadata

pytestmark = pytest.mark.adapter

ALIAS = "qwen3-1.7b-q8_0"
PLATFORM_IDENTIFIER = "qwen3-1-7b-q8-0"

MODELS_PAYLOAD = {"object": "list", "data": [{"id": ALIAS, "object": "model"}]}
PROPS_PAYLOAD = {
    "model_path": f"/models/{PINNED_MODEL_FILE}",
    "build_info": OBSERVED_BUILD_INFO,
    "total_slots": 4,
}


# --------------------------------------------------------------------------
# Reading the model list
# --------------------------------------------------------------------------


def test_the_model_list_yields_the_alias_the_runtime_echoes() -> None:
    assert parse_models_payload(MODELS_PAYLOAD) == ALIAS


def test_an_empty_model_list_is_absence_rather_than_a_failure() -> None:
    assert parse_models_payload({"object": "list", "data": []}) is None


@pytest.mark.parametrize(
    "payload",
    ["not an object", [], None, 7, {"object": "list"}, {"data": "qwen"}],
    ids=["string", "list", "none", "number", "no-data", "data-not-a-list"],
)
def test_a_model_list_whose_shape_cannot_be_read_is_refused(payload: object) -> None:
    """An unreadable answer and an empty one are different facts."""
    with pytest.raises(InternalError):
        parse_models_payload(payload)


def test_a_malformed_model_entry_is_refused() -> None:
    with pytest.raises(InternalError):
        parse_models_payload({"data": ["qwen"]})


def test_a_model_entry_with_a_non_string_identifier_is_refused() -> None:
    with pytest.raises(InternalError):
        parse_models_payload({"data": [{"id": 7}]})


def test_a_model_entry_with_no_identifier_is_absence() -> None:
    assert parse_models_payload({"data": [{"object": "model"}]}) is None


# --------------------------------------------------------------------------
# Reading the properties
# --------------------------------------------------------------------------


def test_the_properties_yield_the_build_and_the_weight_file_name() -> None:
    observed = parse_props_payload(PROPS_PAYLOAD)
    assert observed.build_info == OBSERVED_BUILD_INFO
    assert observed.model_file == PINNED_MODEL_FILE
    assert observed.total_slots == 4


def test_the_container_path_is_reduced_to_the_file_name() -> None:
    """A value this adapter does not keep is a value it cannot leak."""
    observed = parse_props_payload(
        {"model_path": "/var/lib/inferops/models/Qwen3-1.7B-Q8_0.gguf"}
    )
    assert observed.model_file == PINNED_MODEL_FILE
    assert "/var/lib" not in str(observed)


def test_absent_properties_stay_absent() -> None:
    observed = parse_props_payload({})
    assert observed.model_file is None
    assert observed.build_info is None
    assert observed.total_slots is None


@pytest.mark.parametrize(
    "payload",
    [{"model_path": 7}, {"build_info": []}, {"total_slots": "four"}],
    ids=["model-path", "build-info", "total-slots"],
)
def test_a_malformed_property_is_refused(payload: object) -> None:
    with pytest.raises(InternalError):
        parse_props_payload(payload)


def test_properties_that_are_not_an_object_are_refused() -> None:
    with pytest.raises(InternalError):
        parse_props_payload(["model_path"])


# --------------------------------------------------------------------------
# Both responses together
# --------------------------------------------------------------------------


def test_observing_both_responses_produces_one_identity() -> None:
    observed = observe(models_payload=MODELS_PAYLOAD, props_payload=PROPS_PAYLOAD)
    assert observed.model_alias == ALIAS
    assert observed.model_file == PINNED_MODEL_FILE
    assert observed.build_info == OBSERVED_BUILD_INFO


def test_observing_nothing_is_legal_and_produces_absence() -> None:
    """Before anything has been asked, everything is genuinely unknown."""
    assert observe() == ObservedRuntimeIdentity()


def test_observing_one_response_leaves_the_other_absent() -> None:
    assert observe(models_payload=MODELS_PAYLOAD).build_info is None
    assert observe(props_payload=PROPS_PAYLOAD).model_alias is None


# --------------------------------------------------------------------------
# Domain metadata built from the observation
# --------------------------------------------------------------------------


def test_runtime_metadata_names_the_selected_runtime() -> None:
    metadata = describe_runtime(observe(props_payload=PROPS_PAYLOAD))
    assert isinstance(metadata, RuntimeMetadata)
    assert metadata.name == LLAMA_SERVER_RUNTIME_NAME
    assert metadata.version == OBSERVED_BUILD_INFO


def test_an_unreported_build_falls_back_to_the_pinned_digest() -> None:
    """A pin is a real identifier of real bytes; an invented version is not."""
    metadata = describe_runtime(ObservedRuntimeIdentity())
    assert metadata.version == PINNED_IMAGE_DIGEST


def test_model_metadata_reports_the_platform_identity_and_the_pinned_revision() -> None:
    metadata = describe_model(PLATFORM_IDENTIFIER)
    assert isinstance(metadata, ModelMetadata)
    assert metadata.identifier == PLATFORM_IDENTIFIER
    assert metadata.revision == PINNED_MODEL_REVISION


def test_the_reported_revision_is_never_read_out_of_the_runtime() -> None:
    """The runtime attests no revision, so no response can supply one.

    Both payloads carry a plausible-looking revision member and neither reaches
    the metadata, which is the mechanical form of 'an observation is not a pin'.
    """
    metadata = describe_model(
        PLATFORM_IDENTIFIER,
    )
    assert metadata.revision == PINNED_MODEL_REVISION
    forged = {"data": [{"id": ALIAS, "revision": "0" * 40}]}
    assert parse_models_payload(forged) == ALIAS


# --------------------------------------------------------------------------
# Disagreement between what was configured and what is running
# --------------------------------------------------------------------------


def test_an_agreeing_runtime_produces_no_reasons() -> None:
    reasons = identity_disagreements(
        observe(models_payload=MODELS_PAYLOAD, props_payload=PROPS_PAYLOAD),
        configured_alias=ALIAS,
        configured_model_file=PINNED_MODEL_FILE,
    )
    assert reasons == ()


def test_a_different_alias_is_reported() -> None:
    reasons = identity_disagreements(
        ObservedRuntimeIdentity(model_alias="something-else"),
        configured_alias=ALIAS,
        configured_model_file=PINNED_MODEL_FILE,
    )
    assert reasons == (ALIAS_DISAGREEMENT,)


def test_a_different_weight_file_is_reported() -> None:
    reasons = identity_disagreements(
        ObservedRuntimeIdentity(model_file="some-other-model.gguf"),
        configured_alias=ALIAS,
        configured_model_file=PINNED_MODEL_FILE,
    )
    assert reasons == (MODEL_FILE_DISAGREEMENT,)


def test_both_disagreements_are_reported_together() -> None:
    """Reporting the first and stopping hides the second until it is fixed."""
    reasons = identity_disagreements(
        ObservedRuntimeIdentity(model_alias="other", model_file="other.gguf"),
        configured_alias=ALIAS,
        configured_model_file=PINNED_MODEL_FILE,
    )
    assert set(reasons) == {ALIAS_DISAGREEMENT, MODEL_FILE_DISAGREEMENT}


def test_silence_is_not_disagreement() -> None:
    """A runtime that reported nothing has contradicted nothing."""
    reasons = identity_disagreements(
        ObservedRuntimeIdentity(),
        configured_alias=ALIAS,
        configured_model_file=PINNED_MODEL_FILE,
    )
    assert reasons == ()


def test_the_reason_codes_are_stable_identifiers_rather_than_sentences() -> None:
    """A caller writes one into a log; it must not change with the prose."""
    for reason in (ALIAS_DISAGREEMENT, MODEL_FILE_DISAGREEMENT):
        assert reason == reason.lower()
        assert " " not in reason
