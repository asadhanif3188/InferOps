"""Deterministic validation of the WorkloadContract v1alpha1 schema and fixtures.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness: a run that passes today must pass
identically on a machine that has never had internet access.

This suite covers the schema and the documents that must validate. Invalid
fixtures, canonical error codes, and the semantic rules JSON Schema cannot express
- the replica range, the runtime and model compatibility matrix, pasted-secret
detection - live in `test_workload_contract_validation.py` beside it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "contracts" / "workload"
SCHEMA_PATH = CONTRACT_DIR / "workload-contract.v1alpha1.schema.json"
VALID_EXAMPLES_DIR = CONTRACT_DIR / "examples" / "valid"

EXPECTED_API_VERSION = "inferops.io/v1alpha1"
EXPECTED_SCHEMA_ID = (
    "https://inferops.io/contracts/workload/workload-contract.v1alpha1.schema.json"
)

# ADR 0002 selected exactly one runtime image digest and one model revision. The
# real fixture must carry those values and not a paraphrase of them.
ADR_0002_PATH = (
    REPO_ROOT
    / "docs"
    / "architecture"
    / "decisions"
    / "ADR-0002-model-and-serving-runtime.md"
)

# Field names that would be a natural home for a secret value. None may appear
# anywhere in a contract fixture. The schema already closes every object, so a
# hit here means the schema was loosened, not that a fixture drifted.
FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "value",
        "values",
        "secret",
        "secrets",
        "password",
        "passphrase",
        "token",
        "apikey",
        "api_key",
        "accesskey",
        "access_key",
        "privatekey",
        "private_key",
        "credential",
        "credentials",
        "bearer",
        "authorization",
    }
)


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def valid_example_paths() -> list[Path]:
    return sorted(VALID_EXAMPLES_DIR.glob("*.yaml"))


def load_example(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema())


def walk(node: Any, path: str = "$") -> Iterator[tuple[str, str | None, Any]]:
    """Yield every (json-pointer-ish path, key, value) pair in a document."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}"
            yield here, key, value
            yield from walk(value, here)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            here = f"{path}[{index}]"
            yield here, None, value
            yield from walk(value, here)


# --------------------------------------------------------------------------
# The schema itself
# --------------------------------------------------------------------------


def test_schema_file_is_valid_json():
    load_schema()


def test_schema_is_a_valid_2020_12_schema():
    Draft202012Validator.check_schema(load_schema())


def test_schema_declares_its_dialect_and_identifier():
    schema = load_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == EXPECTED_SCHEMA_ID
    assert schema["title"] == "WorkloadContract v1alpha1"


def test_schema_pins_api_version_and_kind():
    schema = load_schema()
    assert schema["properties"]["apiVersion"]["const"] == EXPECTED_API_VERSION
    assert schema["properties"]["kind"]["const"] == "WorkloadContract"


def iter_schema_nodes(node: Any, pointer: str = "#") -> Iterator[tuple[str, dict]]:
    """Yield every (json pointer, mapping) pair inside a schema document."""
    if isinstance(node, dict):
        yield pointer, node
        for key, value in node.items():
            yield from iter_schema_nodes(value, f"{pointer}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_schema_nodes(value, f"{pointer}/{index}")


def test_every_object_in_the_schema_declares_its_additional_property_policy():
    """An undeclared policy is the one outcome the contract must not have.

    A typo in an optional field name is indistinguishable from an omission when
    unknown properties are silently accepted, so the policy is stated on every
    object rather than inherited from a default.
    """
    undeclared = [
        pointer
        for pointer, node in iter_schema_nodes(load_schema())
        if node.get("type") == "object"
        and "properties" in node
        and "additionalProperties" not in node
        and "propertyNames" not in node
    ]
    assert undeclared == [], f"objects without a declared policy: {undeclared}"


def test_root_and_spec_reject_unknown_fields():
    schema = load_schema()
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["spec"]["additionalProperties"] is False
    assert schema["$defs"]["metadata"]["additionalProperties"] is False


def test_secret_reference_has_no_field_a_value_could_be_written_into():
    ref = load_schema()["$defs"]["secretReference"]
    assert ref["additionalProperties"] is False
    assert set(ref["required"]) == {
        "name",
        "provider",
        "reference",
        "owner",
        "rotation",
    }
    assert set(ref["properties"]) == set(ref["required"])
    assert "owner" in ref["properties"], "secret ownership must be explicit"
    assert "rotation" in ref["properties"], "rotation responsibility must be explicit"


def test_data_classification_vocabulary_is_closed():
    classes = load_schema()["$defs"]["security"]["properties"]["dataClassification"]
    assert classes["enum"] == ["public", "internal", "confidential", "restricted"]


def test_resources_are_mandatory_so_an_unsized_workload_cannot_pass():
    spec = load_schema()["$defs"]["spec"]
    assert "resources" in spec["required"]
    resources = load_schema()["$defs"]["resources"]
    assert set(resources["required"]) == {"cpu", "memory", "accelerator"}


# --------------------------------------------------------------------------
# Valid fixtures
# --------------------------------------------------------------------------


def test_valid_examples_exist():
    names = {p.name for p in valid_example_paths()}
    assert "synchronous-llm-local.yaml" in names
    assert "mock-llm-ci.yaml" in names


@pytest.mark.parametrize("path", valid_example_paths(), ids=lambda p: p.name)
def test_valid_example_validates(path: Path):
    errors = sorted(validator().iter_errors(load_example(path)), key=str)
    assert errors == [], "\n".join(f"{e.json_path}: {e.message}" for e in errors)


@pytest.mark.parametrize("path", valid_example_paths(), ids=lambda p: p.name)
def test_valid_example_is_json_representable(path: Path):
    """YAML is the authoring form; JSON is the wire form.

    A fixture that only round-trips through a YAML loader is a fixture the
    platform cannot transport, so anything YAML adds beyond JSON - dates,
    non-string keys, tags - is rejected here rather than at the boundary.
    """
    document = load_example(path)
    json.loads(json.dumps(document))
    for _, key, _ in walk(document):
        if key is not None:
            assert isinstance(key, str), f"non-string key in {path.name}: {key!r}"


@pytest.mark.parametrize("path", valid_example_paths(), ids=lambda p: p.name)
def test_valid_example_declares_the_supported_api_version(path: Path):
    document = load_example(path)
    assert document["apiVersion"] == EXPECTED_API_VERSION
    assert document["kind"] == "WorkloadContract"


@pytest.mark.parametrize("path", valid_example_paths(), ids=lambda p: p.name)
def test_valid_example_carries_no_field_that_could_hold_a_secret(path: Path):
    hits = [
        where
        for where, key, _ in walk(load_example(path))
        if key is not None and key.lower() in FORBIDDEN_SECRET_KEYS
    ]
    assert hits == [], f"secret-shaped field names in {path.name}: {hits}"


@pytest.mark.parametrize("path", valid_example_paths(), ids=lambda p: p.name)
def test_valid_example_paths_resolve_in_this_repository(path: Path):
    """Every repository-relative reference in a fixture must point at a file.

    A runbook or proof link that does not resolve is the cheapest way for a
    contract to make a claim it cannot support.
    """
    document = load_example(path)
    spec = document["spec"]
    refs = [spec["evidence"]["runbookRef"]]
    refs.extend(spec["evidence"].get("proofRefs", []))
    if "mockLlm" in spec:
        refs.append(spec["mockLlm"]["fixtureRef"])
    for ref in refs:
        assert (REPO_ROOT / ref).is_file(), f"{path.name} references missing {ref}"


# --------------------------------------------------------------------------
# The real fixture is tied to the accepted decision
# --------------------------------------------------------------------------


def test_synchronous_fixture_matches_the_accepted_runtime_and_model():
    spec = load_example(VALID_EXAMPLES_DIR / "synchronous-llm-local.yaml")["spec"]
    artifact = spec["synchronousLlm"]["modelArtifact"]
    image = spec["synchronousLlm"]["runtime"]["imageReference"]
    adr = ADR_0002_PATH.read_text(encoding="utf-8")

    assert "@sha256:" in image, "runtime image must be pinned by digest, not by tag"
    image_digest = image.split("@sha256:")[1]
    assert image_digest in adr, "image digest is not the one ADR 0002 selected"
    assert artifact["revision"] in adr, (
        "model revision is not the one ADR 0002 selected"
    )
    assert artifact["sha256"].removeprefix("sha256:") in adr, (
        "model content hash is not the one ADR 0002 selected"
    )
    assert artifact["file"] in adr
    assert f"{artifact['sizeBytes']:,}" in adr


def test_synchronous_fixture_pins_bytes_as_well_as_a_revision():
    artifact = load_example(VALID_EXAMPLES_DIR / "synchronous-llm-local.yaml")["spec"][
        "synchronousLlm"
    ]["modelArtifact"]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", artifact["sha256"])
    assert re.fullmatch(r"[0-9a-f]{40,64}", artifact["revision"])


# --------------------------------------------------------------------------
# The mock cannot pass itself off as real serving
# --------------------------------------------------------------------------


def test_mock_fixture_is_self_labelling():
    document = load_example(VALID_EXAMPLES_DIR / "mock-llm-ci.yaml")
    spec = document["spec"]
    assert spec["profile"] == "mock-llm"
    assert spec["environment"] == "ci"
    assert spec["model"]["servingCapability"] == "inferops-mock-serving"
    assert spec["mockLlm"]["ciOnly"] is True
    assert spec["mockLlm"]["determinism"] == "fixed-fixture"
    assert "synchronousLlm" not in spec


def test_mock_fixture_cites_no_runtime_proof():
    spec = load_example(VALID_EXAMPLES_DIR / "mock-llm-ci.yaml")["spec"]
    assert spec["evidence"].get("proofRefs", []) == []


def test_mock_response_fixture_identifies_itself_from_its_own_contents():
    """Rule 1 of the mock and real boundary: the label travels with the artifact.

    A fixture that is only identifiable by the directory it sits in stops being
    identifiable the moment somebody copies it into an evidence record.
    """
    fixture_ref = load_example(VALID_EXAMPLES_DIR / "mock-llm-ci.yaml")["spec"][
        "mockLlm"
    ]["fixtureRef"]
    body = json.loads((REPO_ROOT / fixture_ref).read_text(encoding="utf-8"))
    assert body["_inferopsMock"]["isMock"] is True
    assert body["model"] == "inferops-mock-serving"
    assert "mock" in body["_inferopsMock"]["notice"].lower()


def test_a_mock_profile_cannot_be_edited_into_a_real_environment():
    """The guard is in the schema, not in a reviewer's attention span."""
    document = load_example(VALID_EXAMPLES_DIR / "mock-llm-ci.yaml")
    document["spec"]["environment"] = "production"
    assert list(validator().iter_errors(document)), (
        "mock-llm outside the ci environment must not validate"
    )


def test_a_mock_profile_cannot_claim_native_serving():
    document = load_example(VALID_EXAMPLES_DIR / "mock-llm-ci.yaml")
    document["spec"]["model"]["servingCapability"] = "inferops-native-serving"
    assert list(validator().iter_errors(document)), (
        "mock-llm bound to the native serving capability must not validate"
    )


def test_a_mock_profile_cannot_cite_real_runtime_proof():
    document = load_example(VALID_EXAMPLES_DIR / "mock-llm-ci.yaml")
    document["spec"]["evidence"]["proofRefs"] = [
        "docs/proof/serving/v1-s0-003-pr2-runtime-feasibility.md"
    ]
    assert list(validator().iter_errors(document)), (
        "mock-llm citing real-runtime proof must not validate"
    )


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", valid_example_paths(), ids=lambda p: p.name)
def test_validation_is_repeatable(path: Path):
    document = load_example(path)
    runs = [
        [
            f"{e.json_path}:{e.validator}:{e.message}"
            for e in validator().iter_errors(document)
        ]
        for _ in range(5)
    ]
    assert all(run == runs[0] for run in runs)


def test_error_output_is_stable_for_a_known_bad_document():
    """Two runs over the same invalid document must produce the same diagnosis.

    Sorting is applied by the caller, not assumed from the validator: this test
    fixes the contract that a consumer can sort and compare, which is what makes
    an error message quotable in a review.
    """
    document = load_example(VALID_EXAMPLES_DIR / "synchronous-llm-local.yaml")
    del document["metadata"]["owner"]
    first = sorted(
        f"{e.json_path}:{e.validator}" for e in validator().iter_errors(document)
    )
    second = sorted(
        f"{e.json_path}:{e.validator}" for e in validator().iter_errors(document)
    )
    assert first == second
    assert first, "a contract missing its owner must not validate"
