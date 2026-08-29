"""Configuration translation, in both directions, and what it refuses.

**Downwards**, platform configuration joined to operator settings. The refusals
are the interesting half: a mock-labelled identity, a generation bound larger
than the context the runtime was given, and a weight file that is not the pinned
one.

**Upwards**, a committed workload document checked against the pins. `ADR 0002`
records that the runtime publishes from a branch tip with no versioned tag
scheme, which is exactly the situation where the digest in a document and the
digest that is running drift apart quietly. The suite mutates one field of the
committed `synchronous-llm` example at a time and asserts the field path each
mutation is refused with, so a refusal names the field a consumer would have to
fix.

No refusal repeats a value read from the document. That is asserted directly,
because a mismatch is the most tempting place to print both sides and a workload
document is a place a reader's own paths and names appear.

Every check reads files from this repository and objects from this distribution.
No network, no cluster, no model, no clock, no randomness.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.adapters.llama_cpp import (
    PINNED_MODEL,
    PINNED_MODEL_FILE,
    PINNED_RUNTIME,
    LlamaServerConfiguration,
    LlamaServerSettings,
    translate,
    verify_workload,
)
from inferops.domain import RequestContext
from inferops.domain.serving import AdapterConfiguration, InvalidAdapterConfigError
from inferops.domain.workload import parse_workload_contract

pytestmark = pytest.mark.adapter

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_PATH = (
    REPO_ROOT / "contracts/workload/examples/valid/synchronous-llm-local.yaml"
)
MOCK_EXAMPLE_PATH = REPO_ROOT / "contracts/workload/examples/valid/mock-llm-ci.yaml"

SYNCHRONOUS_DOCUMENT: dict[str, Any] = yaml.safe_load(
    EXAMPLE_PATH.read_text(encoding="utf-8")
)
MOCK_DOCUMENT: dict[str, Any] = yaml.safe_load(
    MOCK_EXAMPLE_PATH.read_text(encoding="utf-8")
)

CONTEXT = RequestContext(request_id="test-req-004", correlation_id="test-corr-004")
PLATFORM_IDENTIFIER = "qwen3-1-7b-q8-0"


def settings(**overrides: object) -> LlamaServerSettings:
    values: dict[str, object] = {
        "endpoint": "http://llama-server.inferops-serving.svc.cluster.local:80",
        "model_path": f"/models/{PINNED_MODEL_FILE}",
        "model_alias": "qwen3-1.7b-q8_0",
        "context_size": 4096,
        "threads": 6,
        "startup_budget_ms": 300000,
    }
    values.update(overrides)
    return LlamaServerSettings(**values)  # type: ignore[arg-type]


def adapter_configuration(**overrides: object) -> AdapterConfiguration:
    values: dict[str, object] = {
        "model_identifier": PLATFORM_IDENTIFIER,
        "timeout_ms": 60000,
    }
    values.update(overrides)
    return AdapterConfiguration(**values)  # type: ignore[arg-type]


def document_with(path: tuple[str, ...], value: object) -> dict[str, Any]:
    """The committed example with exactly one field replaced."""
    mutated = copy.deepcopy(SYNCHRONOUS_DOCUMENT)
    cursor: Any = mutated
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    return mutated


# --------------------------------------------------------------------------
# Downwards: platform configuration joined to runtime settings
# --------------------------------------------------------------------------


def test_a_valid_pair_translates() -> None:
    configuration = translate(adapter_configuration(), settings(), context=CONTEXT)
    assert isinstance(configuration, LlamaServerConfiguration)
    assert configuration.platform_model_identifier == PLATFORM_IDENTIFIER
    assert configuration.runtime_model_alias == "qwen3-1.7b-q8_0"


def test_the_pins_default_to_the_accepted_ones() -> None:
    configuration = translate(adapter_configuration(), settings())
    assert configuration.runtime == PINNED_RUNTIME
    assert configuration.model == PINNED_MODEL


def test_the_platform_identity_and_the_runtime_alias_are_kept_apart() -> None:
    """They are different strings by construction and both must survive.

    The contract's model reference is kebab-case; the runtime's alias is whatever
    the operator passed on the command line. Collapsing them would make one of
    the two unrepresentable.
    """
    configuration = translate(adapter_configuration(), settings())
    assert configuration.platform_model_identifier != configuration.runtime_model_alias


def test_a_mock_labelled_platform_identity_is_refused() -> None:
    """A real adapter serving a mock identity is a mislabelled transcript."""
    with pytest.raises(InvalidAdapterConfigError) as caught:
        translate(
            adapter_configuration(model_identifier="mock-fixed-fixture"),
            settings(),
            context=CONTEXT,
        )
    assert caught.value.field == "model_identifier"
    assert caught.value.context.request_id == "test-req-004"


def test_a_generation_bound_larger_than_the_context_is_refused() -> None:
    with pytest.raises(InvalidAdapterConfigError) as caught:
        translate(
            adapter_configuration(max_tokens=4097),
            settings(context_size=4096),
            context=CONTEXT,
        )
    assert caught.value.field == "max_tokens"


def test_a_generation_bound_within_the_context_is_accepted() -> None:
    configuration = translate(
        adapter_configuration(max_tokens=4096), settings(context_size=4096)
    )
    assert configuration.adapter.max_tokens == 4096


def test_an_unpinned_weight_file_is_refused() -> None:
    with pytest.raises(InvalidAdapterConfigError) as caught:
        translate(
            adapter_configuration(),
            settings(model_path="/models/some-other-model.gguf"),
            context=CONTEXT,
        )
    assert caught.value.field == "modelPath"


# --------------------------------------------------------------------------
# The arguments this configuration determines
# --------------------------------------------------------------------------


def test_the_generated_arguments_carry_the_weight_path_alias_context_and_threads() -> (
    None
):
    arguments = translate(adapter_configuration(), settings()).model_serving_arguments()
    assert arguments == (
        "--model",
        f"/models/{PINNED_MODEL_FILE}",
        "--alias",
        "qwen3-1.7b-q8_0",
        "--ctx-size",
        "4096",
        "--threads",
        "6",
        "--metrics",
    )


def test_the_metrics_flag_follows_the_setting() -> None:
    arguments = translate(
        adapter_configuration(), settings(metrics_enabled=False)
    ).model_serving_arguments()
    assert "--metrics" not in arguments


@pytest.mark.parametrize("flag", ["--host", "--port"])
def test_the_bind_address_is_not_generated(flag: str) -> None:
    """Where the runtime listens is the deployment's property, not the client's."""
    arguments = translate(adapter_configuration(), settings()).model_serving_arguments()
    assert flag not in arguments


@pytest.mark.parametrize("flag", ["--temp", "--top-p", "--top-k", "--seed"])
def test_no_sampling_default_is_generated(flag: str) -> None:
    """ADR 0002 leaves sampling undecided; a default here becomes a recommendation."""
    arguments = translate(adapter_configuration(), settings()).model_serving_arguments()
    assert flag not in arguments


# --------------------------------------------------------------------------
# Upwards: a workload document checked against the pins
# --------------------------------------------------------------------------


def test_the_committed_example_agrees_with_the_pins() -> None:
    """The fixture and the adapter describe the same runtime and model."""
    verify_workload(parse_workload_contract(SYNCHRONOUS_DOCUMENT), context=CONTEXT)


def test_a_mock_workload_is_refused_by_profile() -> None:
    with pytest.raises(InvalidAdapterConfigError) as caught:
        verify_workload(parse_workload_contract(MOCK_DOCUMENT), context=CONTEXT)
    assert caught.value.field == "spec.profile"


@pytest.mark.parametrize(
    ("path", "value", "expected_field"),
    [
        (
            ("spec", "synchronousLlm", "runtime", "imageReference"),
            "ghcr.io/ggml-org/llama.cpp@sha256:" + "0" * 64,
            "spec.synchronousLlm.runtime.imageReference",
        ),
        (
            ("spec", "synchronousLlm", "modelArtifact", "repository"),
            "Qwen/Qwen3-4B-GGUF",
            "spec.synchronousLlm.modelArtifact.repository",
        ),
        (
            ("spec", "synchronousLlm", "modelArtifact", "revision"),
            "0" * 40,
            "spec.synchronousLlm.modelArtifact.revision",
        ),
        (
            ("spec", "synchronousLlm", "modelArtifact", "file"),
            "Qwen3-4B-Q8_0.gguf",
            "spec.synchronousLlm.modelArtifact.file",
        ),
        (
            ("spec", "synchronousLlm", "modelArtifact", "sha256"),
            "sha256:" + "0" * 64,
            "spec.synchronousLlm.modelArtifact.sha256",
        ),
        (
            ("spec", "synchronousLlm", "modelArtifact", "sizeBytes"),
            1234567890,
            "spec.synchronousLlm.modelArtifact.sizeBytes",
        ),
    ],
    ids=[
        "image-digest",
        "model-repository",
        "model-revision",
        "model-file",
        "model-hash",
        "model-size",
    ],
)
def test_a_document_that_names_different_bytes_is_refused(
    path: tuple[str, ...], value: object, expected_field: str
) -> None:
    contract = parse_workload_contract(document_with(path, value))
    with pytest.raises(InvalidAdapterConfigError) as caught:
        verify_workload(contract, context=CONTEXT)
    assert caught.value.field == expected_field


def test_a_refusal_does_not_repeat_the_value_it_refused() -> None:
    """A document is where a reader's own names and paths appear."""
    forged = "Qwen/private-internal-project-model"
    contract = parse_workload_contract(
        document_with(("spec", "synchronousLlm", "modelArtifact", "repository"), forged)
    )
    with pytest.raises(InvalidAdapterConfigError) as caught:
        verify_workload(contract, context=CONTEXT)
    assert forged not in str(caught.value)
    assert forged not in str(caught.value.as_dict())


def test_a_refusal_preserves_the_supplied_correlation_identifiers() -> None:
    contract = parse_workload_contract(
        document_with(("spec", "synchronousLlm", "modelArtifact", "file"), "other.gguf")
    )
    with pytest.raises(InvalidAdapterConfigError) as caught:
        verify_workload(contract, context=CONTEXT)
    assert caught.value.as_dict()["requestId"] == "test-req-004"
    assert caught.value.as_dict()["correlationId"] == "test-corr-004"


def test_verification_needs_no_context_to_refuse() -> None:
    """An offline check with no request behind it still produces a refusal."""
    contract = parse_workload_contract(
        document_with(("spec", "synchronousLlm", "modelArtifact", "file"), "other.gguf")
    )
    with pytest.raises(InvalidAdapterConfigError) as caught:
        verify_workload(contract)
    assert caught.value.context.is_empty
