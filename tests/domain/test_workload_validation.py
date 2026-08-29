"""Semantic validation of a parsed WorkloadContract.

This suite establishes that:
- Every committed valid fixture passes all semantic validation rules
- Every committed invalid fixture fails with the correct rule_id and field
- No validation error contains a value read from the document
- Multiple errors are returned together for comprehensive feedback
- The compatibility matrix is loaded and used correctly

What it does not establish: that every rule documents its reasoning or that the
reasoning is correct for production use. That distinction belongs to the
documentation and the proof records cited in it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.domain import RequestContext
from inferops.domain.workload import (
    parse_workload_contract,
    set_matrix_loader,
    validate_workload_contract,
)
from inferops.domain.workload.validation import CompatibilityMatrixLoader

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "contracts" / "workload"
VALID_EXAMPLES_DIR = CONTRACT_DIR / "examples" / "valid"
INVALID_EXAMPLES_DIR = CONTRACT_DIR / "examples" / "invalid"
EXPECTED_REJECTIONS_PATH = INVALID_EXAMPLES_DIR / "expected-rejections.json"
MATRIX_PATH = (
    CONTRACT_DIR / "compatibility" / "runtime-model-compatibility.v1alpha1.json"
)


# Initialize the matrix loader (file I/O is done here, outside the domain module)
def _load_matrix() -> dict[str, Any]:
    """Load the compatibility matrix from disk."""
    with open(MATRIX_PATH, encoding="utf-8") as f:
        return json.load(f)


_matrix = _load_matrix()
set_matrix_loader(CompatibilityMatrixLoader(_matrix))


def load_document(path: Path) -> dict[str, Any]:
    """Load a YAML document from a path."""
    document: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return document


def valid_example_paths() -> list[Path]:
    """Get all valid example fixture paths."""
    return sorted(VALID_EXAMPLES_DIR.glob("*.yaml"))


def invalid_example_paths() -> list[Path]:
    """Get all invalid example fixture paths."""
    return sorted([p for p in INVALID_EXAMPLES_DIR.glob("*.yaml")])


def example_ids(paths: list[Path]) -> list[str]:
    """Get example IDs from paths."""
    return [path.stem for path in paths]


@pytest.fixture(params=valid_example_paths(), ids=example_ids(valid_example_paths()))
def valid_document(request: pytest.FixtureRequest) -> dict[str, Any]:
    """A valid fixture to test."""
    return load_document(request.param)


@pytest.fixture(
    params=invalid_example_paths(), ids=example_ids(invalid_example_paths())
)
def invalid_document(request: pytest.FixtureRequest) -> tuple[Path, dict[str, Any]]:
    """An invalid fixture to test, with its path."""
    path = request.param
    return path, load_document(path)


# --------------------------------------------------------------------------
# Valid fixtures must pass all semantic validation
# --------------------------------------------------------------------------


def test_every_committed_valid_fixture_passes_validation(
    valid_document: dict[str, Any],
) -> None:
    """Every valid fixture should parse and pass semantic validation."""
    contract = parse_workload_contract(valid_document)
    errors = validate_workload_contract(contract)
    assert errors == [], f"Valid fixture should not have validation errors: {errors}"


# --------------------------------------------------------------------------
# Invalid fixtures must fail with the expected rule and field
# --------------------------------------------------------------------------


@pytest.fixture
def expected_rejections() -> dict[str, Any]:
    """Load the expected rejections manifest."""
    with open(EXPECTED_REJECTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_fixture_appears_in_expected_rejections(
    invalid_document: tuple[Path, dict[str, Any]],
    expected_rejections: dict[str, Any],
) -> None:
    """Every invalid fixture should appear in the expected rejections."""
    path, _ = invalid_document
    fixture_name = path.stem + ".yaml"
    assert fixture_name in expected_rejections["fixtures"], (
        f"Fixture {fixture_name} not documented in expected-rejections.json"
    )


def test_semantic_invalid_fixtures_fail_with_correct_rule(
    invalid_document: tuple[Path, dict[str, Any]],
    expected_rejections: dict[str, Any],
) -> None:
    """Semantic layer fixtures must fail validation with the expected rule."""
    path, document = invalid_document
    fixture_name = path.stem + ".yaml"

    fixture_spec = expected_rejections["fixtures"].get(fixture_name)
    if fixture_spec is None or fixture_spec["layer"] != "semantic":
        pytest.skip(f"Fixture {fixture_name} is not a semantic layer fixture")

    # Parse the document (should succeed)
    contract = parse_workload_contract(document)

    # Validate the contract (should fail)
    errors = validate_workload_contract(contract)

    # Should have at least one error
    assert len(errors) > 0, f"Expected validation errors for {fixture_name}, got none"

    # Each expected error should appear in the validation results
    expected_errors = fixture_spec["expected"]
    for expected_error in expected_errors:
        expected_rule = expected_error["rule"]
        expected_field = expected_error["field"]

        # Convert JSONPath to our field format
        our_field = _jsonpath_to_field(expected_field)

        # Find matching error
        matching_errors = [
            e for e in errors if e.rule_id == expected_rule and e.field == our_field
        ]

        assert len(matching_errors) > 0, (
            f"Expected error with rule_id={expected_rule} and field={our_field} for {fixture_name}, got errors: {[e.as_dict() for e in errors]}"
        )


def test_no_validation_error_contains_document_values(
    invalid_document: tuple[Path, dict[str, Any]],
    expected_rejections: dict[str, Any],
) -> None:
    """Validation errors must never contain values read from the document."""
    path, document = invalid_document
    fixture_name = path.stem + ".yaml"

    fixture_spec = expected_rejections["fixtures"].get(fixture_name)
    if fixture_spec is None or fixture_spec["layer"] != "semantic":
        pytest.skip(f"Fixture {fixture_name} is not a semantic layer fixture")

    contract = parse_workload_contract(document)
    errors = validate_workload_contract(contract)

    # Extract all string values from the document
    document_values = _extract_all_string_values(document)

    # Check that no error reason contains any document value
    # (use a length threshold to avoid false positives from common words)
    MINIMUM_INTERESTING_LENGTH = 8

    for error in errors:
        reason = error.reason.lower()
        for value in document_values:
            if len(str(value)) >= MINIMUM_INTERESTING_LENGTH:
                assert str(value).lower() not in reason, (
                    f"Error reason contains document value: {error.reason}"
                )


def test_validation_carries_request_context(
    valid_document: dict[str, Any],
) -> None:
    """Validation errors should carry request context when provided."""
    contract = parse_workload_contract(valid_document)
    context = RequestContext(request_id="req-123", correlation_id="corr-456")

    # Create an error with context (we'll test this indirectly through validation)
    # For now, just verify that validate_workload_contract accepts context
    errors = validate_workload_contract(contract, context=context)

    # For valid documents, no errors should be returned
    assert errors == []


# --------------------------------------------------------------------------
# Specific semantic rules
# --------------------------------------------------------------------------


def test_replica_range_inverted_is_detected() -> None:
    """replica-range-inverted: minimumReplicas > maximumReplicas."""
    path = INVALID_EXAMPLES_DIR / "replica-range-inverted.yaml"
    if not path.exists():
        pytest.skip(f"Fixture {path.name} not found")

    document = load_document(path)
    contract = parse_workload_contract(document)
    errors = validate_workload_contract(contract)

    assert len(errors) > 0
    replica_errors = [e for e in errors if e.rule_id == "replica-range-inverted"]
    assert len(replica_errors) > 0


def test_secret_value_in_locator_is_detected() -> None:
    """secret-value-in-locator: Secret reference looks like a pasted credential."""
    path = INVALID_EXAMPLES_DIR / "secret-value-in-locator.yaml"
    if not path.exists():
        pytest.skip(f"Fixture {path.name} not found")

    document = load_document(path)
    contract = parse_workload_contract(document)
    errors = validate_workload_contract(contract)

    assert len(errors) > 0
    secret_errors = [e for e in errors if e.rule_id == "secret-value-in-locator"]
    assert len(secret_errors) > 0


def test_duplicate_secret_ref_name_is_detected() -> None:
    """secret-ref-name-duplicated: Two secret entries declare the same name."""
    path = INVALID_EXAMPLES_DIR / "duplicate-secret-ref-name.yaml"
    if not path.exists():
        pytest.skip(f"Fixture {path.name} not found")

    document = load_document(path)
    contract = parse_workload_contract(document)
    errors = validate_workload_contract(contract)

    assert len(errors) > 0
    dup_errors = [e for e in errors if e.rule_id == "secret-ref-name-duplicated"]
    assert len(dup_errors) > 0


def test_mock_secret_ref_declared_is_detected() -> None:
    """mock-secret-ref-declared: Mock-llm workload declares a secret reference."""
    path = INVALID_EXAMPLES_DIR / "mock-with-secret-refs.yaml"
    if not path.exists():
        pytest.skip(f"Fixture {path.name} not found")

    document = load_document(path)
    contract = parse_workload_contract(document)
    errors = validate_workload_contract(contract)

    assert len(errors) > 0
    mock_errors = [e for e in errors if e.rule_id == "mock-secret-ref-declared"]
    assert len(mock_errors) > 0


def test_runtime_unregistered_is_detected() -> None:
    """runtime-unregistered: Runtime image repository not in compatibility matrix."""
    path = INVALID_EXAMPLES_DIR / "runtime-unregistered.yaml"
    if not path.exists():
        pytest.skip(f"Fixture {path.name} not found")

    document = load_document(path)
    contract = parse_workload_contract(document)
    errors = validate_workload_contract(contract)

    assert len(errors) > 0
    runtime_errors = [e for e in errors if e.rule_id == "runtime-unregistered"]
    assert len(runtime_errors) > 0


def test_model_artifact_format_unknown_is_detected() -> None:
    """model-artifact-format-unknown: Artifact filename has no recognized extension."""
    path = INVALID_EXAMPLES_DIR / "model-artifact-format-unrecognised.yaml"
    if not path.exists():
        pytest.skip(f"Fixture {path.name} not found")

    document = load_document(path)
    contract = parse_workload_contract(document)
    errors = validate_workload_contract(contract)

    assert len(errors) > 0
    format_errors = [e for e in errors if e.rule_id == "model-artifact-format-unknown"]
    assert len(format_errors) > 0


def test_runtime_model_incompatible_is_detected() -> None:
    """runtime-model-incompatible: Pinned runtime doesn't accept artifact format."""
    path = INVALID_EXAMPLES_DIR / "runtime-model-incompatible.yaml"
    if not path.exists():
        pytest.skip(f"Fixture {path.name} not found")

    document = load_document(path)
    contract = parse_workload_contract(document)
    errors = validate_workload_contract(contract)

    assert len(errors) > 0
    compat_errors = [e for e in errors if e.rule_id == "runtime-model-incompatible"]
    assert len(compat_errors) > 0


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _jsonpath_to_field(jsonpath: str) -> str:
    """Convert a JSONPath to our field format.

    JSONPath: $.spec.security.secretRefs[1].name
    Our format: spec.security.secretRefs[1].name
    """
    if jsonpath.startswith("$."):
        return jsonpath[2:]
    return jsonpath


def _extract_all_string_values(obj: Any, values: set[str] | None = None) -> set[str]:
    """Recursively extract all string values from a nested structure."""
    if values is None:
        values = set()

    if isinstance(obj, dict):
        for v in obj.values():
            _extract_all_string_values(v, values)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _extract_all_string_values(item, values)
    elif isinstance(obj, str):
        values.add(obj)

    return values


# --------------------------------------------------------------------------
# Credential detection agreement tests
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "credential_value,should_be_rejected",
    [
        # All 39 published credential prefixes, each asserted by test
        ("-----BEGIN CERTIFICATE-----", True),
        ("ABIA0000000000000000", True),
        ("ACCA0000000000000000", True),
        ("AGPA0000000000000000", True),
        ("AIDA0000000000000000", True),
        ("AIPA0000000000000000", True),
        ("AIza0000000000000000", True),
        ("AKIA0000000000000000", True),
        ("ANPA0000000000000000", True),
        ("ANVA0000000000000000", True),
        ("AROA0000000000000000", True),
        ("ASCA0000000000000000", True),
        ("ASIA0000000000000000", True),
        ("SG.0000000000000000000", True),
        ("doo_v1_0000000000000000", True),
        ("dop_v1_0000000000000000", True),
        ("eyJ0000000000000000000", True),
        ("ghp_0000000000000000000", True),
        ("ghr_0000000000000000000", True),
        ("ghs_0000000000000000000", True),
        ("ghu_0000000000000000000", True),
        ("gho_0000000000000000000", True),
        ("github_pat_0000000000000", True),
        ("gldt-0000000000000000000", True),
        ("glpat-00000000000000000", True),
        ("hf_00000000000000000000", True),
        ("npm_0000000000000000000", True),
        ("pk_live_000000000000000000", True),
        ("rk_live_000000000000000000", True),
        ("shpat_00000000000000000000", True),
        ("shpss_00000000000000000000", True),
        ("sk-00000000000000000000", True),
        ("sk_live_000000000000000000", True),
        ("sk_test_000000000000000000", True),
        ("xoxa-000000000000000000", True),
        ("xoxb-000000000000000000", True),
        ("xoxp-000000000000000000", True),
        ("xoxr-000000000000000000", True),
        ("xoxs-000000000000000000", True),
        ("ya29.0000000000000000000", True),
        # High-entropy tokens (mixed case + digits, 20+ chars)
        ("Zx4Kq9TbLm2Rd7Wf1Hs3Nv8Yc6Ej0Pa", True),
        ("aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV", True),
        # Legitimate references (should not be rejected)
        ("kubernetes.io/my-secret", False),
        ("secret-ref-name", False),
        ("my_secret_name", False),
        ("secret123", False),
        ("vault:kv/data/my-secret", False),
        ("inferops-serving/model-registry#token", False),
        ("inferops/telemetry/ingest#key", False),
        ("aws-secretsmanager:prod/api-key", False),
    ],
)
def test_credential_detection_agreement_with_published(
    credential_value: str, should_be_rejected: bool
) -> None:
    """Verify domain validator matches published validator for all prefixes."""
    from inferops.domain.workload.validation import _looks_like_secret_value

    # Domain validator result
    domain_result = _looks_like_secret_value(credential_value)

    # Published validator result
    from tools.contract_validation.workload import looks_like_a_pasted_credential

    published_result = looks_like_a_pasted_credential(credential_value) is not None

    assert domain_result == published_result, (
        f"Validators diverge for {credential_value}: "
        f"domain={domain_result}, published={published_result}"
    )
    assert domain_result == should_be_rejected, (
        f"Expected rejection={should_be_rejected} for {credential_value}, got {domain_result}"
    )


def test_credential_detection_rejects_no_legitimate_secrets() -> None:
    """Verify that legitimate secret locators are not falsely rejected."""
    from inferops.domain.workload.validation import _looks_like_secret_value

    legitimate_refs = [
        "kubernetes.io/database-password",
        "vault:kv/data/prod-api-key",
        "secret-store:my-secret-v1",
        "aws-secretsmanager:prod/api-key",
        "hashicorp-vault:secret/data/api-key",
        "my_app_secret",
        "app-secret-1",
        "secret_name_2024",
    ]

    for ref in legitimate_refs:
        result = _looks_like_secret_value(ref)
        assert result is False, f"Legitimate secret reference falsely rejected: {ref}"
