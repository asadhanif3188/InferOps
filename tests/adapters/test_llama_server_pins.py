"""The pins in the adapter, checked against the records they were copied from.

A constant copied out of an accepted decision is a copy, and a copy nobody
compares to its source drifts. Every assertion here reads a committed file — the
compatibility matrix, the accepted runtime decision, the feasibility record, and
the committed `synchronous-llm` example — and fails when the adapter's idea of the
selected runtime and model stops matching what the project actually decided.

That direction matters. These checks do not verify that the pinned image or the
pinned weights are correct; nothing in this repository can. They verify that one
value appears identically in the place that decided it and in the code that acts
on it, which is the only part of the question a repository-only check can answer.

Every check reads files from this repository and objects from this distribution.
No network, no cluster, no model, no credential, no clock, no randomness.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from inferops.adapters.llama_cpp import (
    COMPATIBILITY_MATRIX_REF,
    LLAMA_SERVER_ADAPTER_KIND,
    LLAMA_SERVER_RUNTIME_ID,
    LLAMA_SERVER_RUNTIME_NAME,
    LLAMA_SERVER_SERVING_CAPABILITY,
    OBSERVED_BUILD_INFO,
    PINNED_ARTIFACT_FORMAT,
    PINNED_IMAGE_DIGEST,
    PINNED_IMAGE_REFERENCE,
    PINNED_IMAGE_REPOSITORY,
    PINNED_MODEL,
    PINNED_MODEL_FILE,
    PINNED_MODEL_REPOSITORY,
    PINNED_MODEL_REVISION,
    PINNED_MODEL_SHA256,
    PINNED_MODEL_SIZE_BYTES,
    PINNED_RUNTIME,
    RUNTIME_DECISION_REF,
    RUNTIME_FEASIBILITY_REF,
)
from inferops.domain.serving import ACCEPTED_ADAPTER_KINDS

pytestmark = pytest.mark.adapter

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO_ROOT / COMPATIBILITY_MATRIX_REF
DECISION_PATH = REPO_ROOT / RUNTIME_DECISION_REF
FEASIBILITY_PATH = REPO_ROOT / RUNTIME_FEASIBILITY_REF
EXAMPLE_PATH = (
    REPO_ROOT / "contracts/workload/examples/valid/synchronous-llm-local.yaml"
)

MATRIX = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
DECISION_TEXT = DECISION_PATH.read_text(encoding="utf-8")
FEASIBILITY_TEXT = FEASIBILITY_PATH.read_text(encoding="utf-8")
EXAMPLE = yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))

RUNTIME_ROW = next(
    row for row in MATRIX["runtimes"] if row["runtimeId"] == LLAMA_SERVER_RUNTIME_ID
)
EXECUTED_PAIR = next(
    row
    for row in MATRIX["executedPairs"]
    if row["runtimeId"] == LLAMA_SERVER_RUNTIME_ID
)
EXAMPLE_PROFILE = EXAMPLE["spec"]["synchronousLlm"]


# --------------------------------------------------------------------------
# The record every pin was copied from exists
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [MATRIX_PATH, DECISION_PATH, FEASIBILITY_PATH, EXAMPLE_PATH],
    ids=lambda path: path.name,
)
def test_every_cited_record_exists(path: Path) -> None:
    """A reference to a record that is not there certifies nothing."""
    assert path.is_file(), path


def test_the_decision_reference_names_the_accepted_runtime_decision() -> None:
    assert RUNTIME_DECISION_REF.endswith("ADR-0002-model-and-serving-runtime.md")
    assert PINNED_RUNTIME.decision_ref == RUNTIME_DECISION_REF
    assert PINNED_MODEL.decision_ref == RUNTIME_DECISION_REF


# --------------------------------------------------------------------------
# The runtime identity agrees with the matrix that registers it
# --------------------------------------------------------------------------


def test_the_runtime_identity_is_the_registered_one() -> None:
    """The matrix is where a runtime becomes supported. This is its row."""
    assert RUNTIME_ROW["name"] == LLAMA_SERVER_RUNTIME_NAME
    assert RUNTIME_ROW["servingCapability"] == LLAMA_SERVER_SERVING_CAPABILITY
    assert PINNED_IMAGE_REPOSITORY in RUNTIME_ROW["imageRepositories"]


def test_the_runtime_is_the_selected_one_rather_than_a_fallback() -> None:
    """A recorded fallback is not a selection, and the matrix says which is which."""
    assert RUNTIME_ROW["status"] == "selected"
    assert RUNTIME_ROW["decisionRef"] == RUNTIME_DECISION_REF


def test_the_pinned_artifact_format_is_one_the_runtime_accepts() -> None:
    assert PINNED_ARTIFACT_FORMAT in RUNTIME_ROW["acceptedArtifactFormats"]
    assert PINNED_MODEL.artifact_format == PINNED_ARTIFACT_FORMAT


def test_the_adapter_kind_is_real_and_is_in_the_closed_vocabulary() -> None:
    """A real adapter names itself with the domain's word, not with its own."""
    assert LLAMA_SERVER_ADAPTER_KIND == "real"
    assert LLAMA_SERVER_ADAPTER_KIND in ACCEPTED_ADAPTER_KINDS


# --------------------------------------------------------------------------
# The image and model pins agree with the pair the project executed
# --------------------------------------------------------------------------


def test_the_image_reference_is_the_executed_one() -> None:
    assert EXECUTED_PAIR["imageReference"] == PINNED_IMAGE_REFERENCE
    assert PINNED_RUNTIME.reference == PINNED_IMAGE_REFERENCE
    assert PINNED_IMAGE_REFERENCE.endswith(f"@{PINNED_IMAGE_DIGEST}")


def test_the_image_is_pinned_by_digest_and_never_by_tag() -> None:
    """ADR 0002 records that the publisher's tag is rebuilt on a schedule."""
    assert PINNED_IMAGE_DIGEST.startswith("sha256:")
    assert len(PINNED_IMAGE_DIGEST) == len("sha256:") + 64
    assert ":" not in PINNED_IMAGE_REFERENCE.split("@", 1)[0]


def test_the_model_pins_are_the_executed_ones() -> None:
    assert EXECUTED_PAIR["modelRepository"] == PINNED_MODEL_REPOSITORY
    assert EXECUTED_PAIR["modelRevision"] == PINNED_MODEL_REVISION
    assert EXECUTED_PAIR["modelFile"] == PINNED_MODEL_FILE
    assert EXECUTED_PAIR["artifactFormat"] == PINNED_ARTIFACT_FORMAT


def test_the_executed_pair_cites_the_record_that_executed_it() -> None:
    assert EXECUTED_PAIR["proofRef"] == RUNTIME_FEASIBILITY_REF


# --------------------------------------------------------------------------
# The pins agree with the committed workload example, field for field
# --------------------------------------------------------------------------


def test_the_committed_example_names_the_same_runtime_image() -> None:
    assert EXAMPLE_PROFILE["runtime"]["imageReference"] == PINNED_IMAGE_REFERENCE


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("repository", PINNED_MODEL_REPOSITORY),
        ("revision", PINNED_MODEL_REVISION),
        ("file", PINNED_MODEL_FILE),
        ("sizeBytes", PINNED_MODEL_SIZE_BYTES),
        ("sha256", PINNED_MODEL_SHA256),
    ],
)
def test_the_committed_example_names_the_same_model_artifact(
    key: str, expected: object
) -> None:
    """One drift between the fixture and the adapter is one failing assertion."""
    assert EXAMPLE_PROFILE["modelArtifact"][key] == expected


def test_the_example_binds_the_native_serving_capability() -> None:
    assert EXAMPLE["spec"]["model"]["servingCapability"] == (
        LLAMA_SERVER_SERVING_CAPABILITY
    )


# --------------------------------------------------------------------------
# The values only the accepted decision publishes
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        PINNED_IMAGE_DIGEST,
        PINNED_MODEL_REPOSITORY,
        PINNED_MODEL_REVISION,
        PINNED_MODEL_FILE,
    ],
    ids=["image-digest", "model-repository", "model-revision", "model-file"],
)
def test_the_accepted_decision_carries_the_value(value: str) -> None:
    """The decision record is the source; this fails when the copy drifts."""
    assert value in DECISION_TEXT


def test_the_model_hash_is_the_published_one() -> None:
    """Held as a contract-shaped digest, and present in the decision as hex.

    The decision writes the hash without the ``sha256:`` prefix and the workload
    contract requires it, so the two spellings are compared as what they are
    rather than by pretending they are one string.
    """
    assert PINNED_MODEL_SHA256.startswith("sha256:")
    assert PINNED_MODEL_SHA256.removeprefix("sha256:") in DECISION_TEXT


def test_the_model_size_is_the_one_that_was_transferred() -> None:
    assert f"{PINNED_MODEL_SIZE_BYTES:,}" in DECISION_TEXT


def test_the_build_string_is_an_observation_the_trial_recorded() -> None:
    """It is what the process said about itself, once, on one host.

    Recorded as an observation rather than as a pin: the digest identifies the
    bytes, and this identifies what a process inside them reported.
    """
    assert OBSERVED_BUILD_INFO in FEASIBILITY_TEXT
