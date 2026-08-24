"""Rejection behaviour of the WorkloadContract v1alpha1 boundary.

The first pull request of this story proved that valid documents validate. This
one proves the harder half: that invalid documents are refused, that they are
refused for a reason a consumer can act on, and that the reason does not drift.

Like its sibling suite, every check here reads files from this repository and
nothing else. No network, no cluster, no model, no clock, no randomness.

Three things are asserted that a plain "this must fail" test would not catch:

1. **Which layer refuses.** A fixture labelled `semantic` in the manifest must be
   *accepted* by the published schema on its own. If the schema ever grows strict
   enough to catch it, that is a compatibility event and the test says so.
2. **Exactly what the refusal says.** Code, rule, and field are compared against a
   committed manifest, so a message a reviewer quoted last month still means the
   same thing.
3. **That a refusal cannot leak.** Neither half of a finding - the message or the
   field location - may contain a value read out of the document, because an error
   body is the surface most likely to be logged and kept.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from tools.contract_validation import RULES, validate
from tools.contract_validation.errors import CANONICAL_ERROR_CODES
from tools.contract_validation.workload import (
    load_compatibility_matrix,
    load_schema,
    looks_like_a_pasted_credential,
    semantic_findings,
    structural_findings,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "contracts" / "workload"
VALID_DIR = CONTRACT_DIR / "examples" / "valid"
INVALID_DIR = CONTRACT_DIR / "examples" / "invalid"
MANIFEST_PATH = INVALID_DIR / "expected-rejections.json"
CONTRACT_DOC = REPO_ROOT / "docs" / "contracts" / "workload-contract.md"
ADR_0002_PATH = (
    REPO_ROOT
    / "docs"
    / "architecture"
    / "decisions"
    / "ADR-0002-model-and-serving-runtime.md"
)


def load_document(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def invalid_paths() -> list[Path]:
    return sorted(INVALID_DIR.glob("*.yaml"))


def valid_paths() -> list[Path]:
    return sorted(VALID_DIR.glob("*.yaml"))


def as_tuples(findings: Any) -> list[tuple[str, str, str]]:
    return [(f.code, f.rule, f.field) for f in findings]


def expected_tuples(entry: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(e["code"], e["rule"], e["field"]) for e in entry["expected"]]


# --------------------------------------------------------------------------
# Every valid fixture from the first pull request still passes, both layers
# --------------------------------------------------------------------------


def test_the_valid_fixtures_this_change_inherited_are_all_still_here():
    """A rejection suite that quietly dropped a valid fixture would look green."""
    names = {p.name for p in valid_paths()}
    assert names == {
        "mock-llm-ci.yaml",
        "synchronous-llm-local.yaml",
        "synchronous-llm-secret-refs.yaml",
    }


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_valid_fixture_passes_both_layers(path: Path):
    findings = validate(load_document(path))
    assert findings == [], "\n".join(f"{f.field}: {f.rule}" for f in findings)


def test_the_secret_reference_example_survives_the_credential_heuristic():
    """The heuristic's first duty is to leave real locators alone.

    A check that refuses well-formed references is worse than no check, because
    it is switched off within a week and then nothing is checked at all.
    """
    document = load_document(VALID_DIR / "synchronous-llm-secret-refs.yaml")
    for ref in document["spec"]["security"]["secretRefs"]:
        assert looks_like_a_pasted_credential(ref["reference"]) is None


# --------------------------------------------------------------------------
# The manifest and the fixture directory agree
# --------------------------------------------------------------------------


def test_every_invalid_fixture_is_in_the_manifest_and_the_reverse():
    on_disk = {p.name for p in invalid_paths()}
    declared = set(manifest()["fixtures"])
    assert on_disk == declared


def test_the_manifest_declares_a_known_layer_for_every_fixture():
    layers = set(manifest()["layers"])
    for name, entry in manifest()["fixtures"].items():
        assert entry["layer"] in layers, name


def test_every_expected_rule_is_a_registered_rule():
    for name, entry in manifest()["fixtures"].items():
        for expected in entry["expected"]:
            assert expected["rule"] in RULES, f"{name}: {expected['rule']}"
            assert RULES[expected["rule"]].code == expected["code"], name


def test_every_expected_code_is_a_canonical_code():
    for entry in manifest()["fixtures"].values():
        for expected in entry["expected"]:
            assert expected["code"] in CANONICAL_ERROR_CODES


# --------------------------------------------------------------------------
# Rejection, exactly as published
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_invalid_fixture_is_refused(path: Path):
    assert validate(load_document(path)), f"{path.name} was accepted"


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_invalid_fixture_is_refused_for_exactly_the_published_reasons(path: Path):
    entry = manifest()["fixtures"][path.name]
    assert as_tuples(validate(load_document(path))) == expected_tuples(entry)


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_refusal_is_repeatable(path: Path):
    """Five runs, one answer, in one order."""
    document = load_document(path)
    runs = [as_tuples(validate(document)) for _ in range(5)]
    assert all(run == runs[0] for run in runs)


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_refusal_declares_itself_non_retryable(path: Path):
    for found in validate(load_document(path)):
        assert found.retryable is False, "an invalid document is not fixed by retrying"


# --------------------------------------------------------------------------
# Which layer refuses, and therefore what a raw-schema consumer gets
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_declared_layer_matches_the_layer_that_actually_refuses(path: Path):
    """The manifest's `layer` is a claim about the schema, so it is checked.

    A `semantic` fixture that the schema starts refusing is not a bug - it is a
    strengthening, and a compatibility event, and the manifest has to say so
    rather than the change passing unnoticed.
    """
    document = load_document(path)
    layer = manifest()["fixtures"][path.name]["layer"]
    structural = structural_findings(document)
    semantic = semantic_findings(document)

    if layer == "structural":
        assert structural, "declared structural but the schema accepts it"
    else:
        assert not structural, (
            "declared semantic but the schema now refuses it; the schema became "
            "stricter, which is a compatibility event and a manifest change"
        )
        assert semantic, "declared semantic but no semantic rule refuses it"


def test_the_semantic_layer_is_load_bearing():
    """At least one fixture must be one the published schema cannot catch.

    ADR 0003 accepted a split between a portable structural layer and a local
    semantic one. If nothing ever exercised the second, the split would be a
    claim rather than a fact.
    """
    semantic_only = [
        name
        for name, entry in manifest()["fixtures"].items()
        if entry["layer"] == "semantic"
    ]
    assert len(semantic_only) >= 5, semantic_only


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_a_raw_schema_consumer_reaches_the_same_verdict_on_structural_fixtures(
    path: Path,
):
    """What a consumer validating against the bare schema file actually sees."""
    if manifest()["fixtures"][path.name]["layer"] != "structural":
        pytest.skip("semantic-layer fixture; the bare schema is expected to accept it")
    validator = Draft202012Validator(load_schema())
    assert list(validator.iter_errors(load_document(path)))


# --------------------------------------------------------------------------
# A refusal must not become a leak
# --------------------------------------------------------------------------


def scalar_strings(node: Any) -> list[str]:
    if isinstance(node, dict):
        return [s for value in node.values() for s in scalar_strings(value)]
    if isinstance(node, list):
        return [s for value in node for s in scalar_strings(value)]
    if isinstance(node, str):
        return [node]
    return []


def schema_declared_strings() -> set[str]:
    """Every string that appears anywhere in the schema document.

    That is broader than the enum and const vocabulary - it also takes titles,
    descriptions, and patterns - and the breadth is deliberate: exclusion needs an
    exact whole-string match against a document value, so a description sentence
    can only ever exempt a document value identical to that whole sentence.

    The set exists because a message may legitimately repeat public vocabulary.
    Saying that a `mock-llm` workload may not hold a credential is the point of the
    message, and it discloses nothing, because the value came from the published
    schema rather than from the document.
    """
    return set(scalar_strings(load_schema()))


#: The floor for what counts as a value worth protecting. Below it a document
#: string is something like `6`, `3Gi`, or `demo`, which collides with ordinary
#: English in a message for reasons that have nothing to do with disclosure.
LEAK_CHECK_MINIMUM_LENGTH = 8


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_no_finding_quotes_a_value_from_the_document(path: Path):
    """The rule that keeps an error body safe to log.

    The field most likely to be refused for looking wrong is the field most
    likely to hold a secret, so a refusal says what was wrong and never what the
    value was. Both halves of a finding are checked: the message, and the field
    location - which is where an offending property name would otherwise land,
    and `metadata.annotations` is an open map whose keys the author writes.
    """
    document = load_document(path)
    vocabulary = schema_declared_strings()
    values = [
        s
        for s in scalar_strings(document)
        if len(s) >= LEAK_CHECK_MINIMUM_LENGTH and s not in vocabulary
    ]
    for found in validate(document):
        for value in values:
            assert value not in found.message, (
                f"{found.rule} echoed a document value into its message"
            )
            assert value not in found.field, (
                f"{found.rule} echoed a document value into its field location"
            )


def test_the_credential_locator_finding_names_no_credential():
    document = load_document(INVALID_DIR / "secret-value-in-locator.yaml")
    references = [
        ref["reference"] for ref in document["spec"]["security"]["secretRefs"]
    ]
    rendered = json.dumps([f.as_dict() for f in validate(document)])
    for reference in references:
        assert reference not in rendered
        # Not even the distinctive part of it.
        assert reference.split("/")[-1] not in rendered


@pytest.mark.parametrize(
    "key",
    [
        "ghp_0000000000000000000000000000000000",
        "AKIAIOSFODNN7EXAMPLE",
        "inferops.io/" + "A" * 300,
    ],
    ids=["credential-prefix", "aws-placeholder", "overlong"],
)
def test_an_annotation_key_that_should_not_be_repeated_is_not_repeated(key: str):
    """`metadata.annotations` is the contract's one open map.

    Its keys are as author-controlled as any value, so a pasted token in a key is
    a realistic mistake rather than a contrived one. The refusal still happens and
    still says where; it just declines to quote the key back.
    """
    document = load_document(VALID_DIR / "synchronous-llm-local.yaml")
    document["metadata"]["annotations"] = {key: "x"}
    findings = validate(document)
    assert findings, "a malformed annotation key must still be refused"
    for found in findings:
        assert key not in found.field
        assert key not in found.message
    assert any(f.field == "$.metadata.annotations" for f in findings)


def test_one_bad_property_name_produces_one_finding():
    """A key that breaks two constraints at once is still one thing being wrong.

    Taking the rule from the inner keyword of a propertyNames subschema would
    refuse such a key twice, under two rule identifiers, with the same message
    under each - which makes a published rule identifier mean less than it says.
    """
    document = load_document(VALID_DIR / "synchronous-llm-local.yaml")
    # Too long for maxLength and malformed against the pattern, simultaneously.
    document["metadata"]["annotations"] = {"NOT A NAMESPACE " * 20: "x"}
    findings = [f for f in validate(document) if f.field.startswith("$.metadata.anno")]
    assert len(findings) == 1, findings
    assert findings[0].rule == "value-malformed"


def test_findings_are_ordered_by_array_index_as_a_number():
    """Ten entries in one array must not sort before two."""
    document = load_document(VALID_DIR / "synchronous-llm-secret-refs.yaml")
    document["spec"]["security"]["secretRefs"] = [
        {
            "name": "same-name-everywhere",
            "provider": "kubernetes-secret",
            "reference": "inferops-serving/model-registry#token",
            "owner": "team-platform-demo",
            "rotation": "owner-managed",
        }
        for _ in range(12)
    ]
    indexes = [
        int(f.field.split("[")[1].split("]")[0])
        for f in validate(document)
        if "secretRefs[" in f.field
    ]
    assert indexes == sorted(indexes), indexes
    assert indexes == list(range(1, 12))


# --------------------------------------------------------------------------
# The credential heuristic, stated as what it does and does not catch
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "locator",
    [
        "inferops-serving/model-registry#token",
        "inferops/telemetry/ingest#key",
        "secret/data/inferops/serving#registry-token",
        "projects/inferops/secrets/telemetry-ingest/versions/latest",
        "inferops-serving/TelemetryIngestPathForServing#key",
        "arn:aws:secretsmanager:eu-west-1:000000000000:secret:inferops-telemetry",
    ],
    ids=lambda s: s[:40],
)
def test_a_real_locator_is_not_mistaken_for_a_credential(locator: str):
    assert looks_like_a_pasted_credential(locator) is None


@pytest.mark.parametrize(
    "credential",
    [
        "AKIAIOSFODNN7EXAMPLE",
        "ASIAIOSFODNN7EXAMPLE",
        "ghp_0000000000000000000000000000000000",
        "github_pat_00000000000000000000000000",
        "glpat-00000000000000000000",
        "hf_000000000000000000000000000000000000",
        "xoxb-000000000000-000000000000-000000",
        "sk-000000000000000000000000000000000000",
        "AIza00000000000000000000000000000000000",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "inferops/telemetry/Zx4Kq9TbLm2Rd7Wf1Hs3Nv8Yc6Ej0Pa",
    ],
    ids=lambda s: s[:24],
)
def test_a_credential_shaped_locator_is_caught(credential: str):
    """None of these authenticate against anything; each is a shape, not a secret."""
    assert looks_like_a_pasted_credential(credential) is not None


@pytest.mark.parametrize(
    "missed",
    ["Winter2026", "inferops/telemetry/hunter2", "correcthorsebatterystaple"],
    ids=lambda s: s[:24],
)
def test_the_documented_gap_is_a_gap(missed: str):
    """The check is a heuristic over shape, and a short or low-entropy secret has
    the shape of a name. This test exists so that the limitation the contract
    document publishes is a measured fact rather than a hedge, and so that a
    future change which closes it has to come here and say so.
    """
    assert looks_like_a_pasted_credential(missed) is None


# --------------------------------------------------------------------------
# The runtime and model compatibility matrix
# --------------------------------------------------------------------------


def test_the_matrix_is_valid_json_with_the_shape_the_validator_reads():
    matrix = load_compatibility_matrix()
    assert matrix["contractVersion"] == "inferops.io/v1alpha1"
    assert matrix["artifactFormats"]
    assert matrix["runtimes"]
    for runtime in matrix["runtimes"]:
        assert set(runtime) >= {
            "runtimeId",
            "imageRepositories",
            "servingCapability",
            "acceptedArtifactFormats",
            "status",
            "decisionRef",
        }


def test_matrix_runtime_identifiers_and_repositories_are_unique():
    matrix = load_compatibility_matrix()
    identifiers = [r["runtimeId"] for r in matrix["runtimes"]]
    assert len(identifiers) == len(set(identifiers))
    repositories = [
        repository
        for runtime in matrix["runtimes"]
        for repository in runtime["imageRepositories"]
    ]
    assert len(repositories) == len(set(repositories)), (
        "one repository mapping to two runtimes would make the lookup order-dependent"
    )


def test_every_matrix_reference_resolves_in_this_repository():
    matrix = load_compatibility_matrix()
    refs = [runtime["decisionRef"] for runtime in matrix["runtimes"]]
    refs.extend(pair["proofRef"] for pair in matrix["executedPairs"])
    for ref in refs:
        assert (REPO_ROOT / ref).is_file(), f"matrix references missing {ref}"


def test_no_matrix_extension_is_a_suffix_of_another():
    """Otherwise which format wins depends on iteration order.

    Today no extension shadows another. The day one does - `.tar.gz` beside `.gz`,
    `.q4.bin` beside `.bin` - the lookup must pick the specific one, and this test
    is what makes that a decision rather than an accident.
    """
    extensions = sorted(load_compatibility_matrix()["artifactFormats"])
    overlapping = [
        (a, b) for a in extensions for b in extensions if a != b and a.endswith(b)
    ]
    assert overlapping == [], overlapping


def test_matrix_accepted_formats_are_declared_formats():
    matrix = load_compatibility_matrix()
    known = set(matrix["artifactFormats"].values())
    for runtime in matrix["runtimes"]:
        assert set(runtime["acceptedArtifactFormats"]) <= known, runtime["runtimeId"]


def test_the_one_executed_pair_is_the_pair_adr_0002_selected():
    """The matrix may list runtimes nobody ran. It may not claim one was run."""
    matrix = load_compatibility_matrix()
    assert len(matrix["executedPairs"]) == 1
    pair = matrix["executedPairs"][0]
    adr = ADR_0002_PATH.read_text(encoding="utf-8")
    assert pair["imageReference"].split("@sha256:")[1] in adr
    assert pair["modelRevision"] in adr
    assert pair["modelFile"] in adr
    assert (REPO_ROOT / pair["proofRef"]).is_file()


def test_the_real_valid_fixtures_pin_a_runtime_the_matrix_has_executed():
    matrix = load_compatibility_matrix()
    executed = {pair["imageReference"] for pair in matrix["executedPairs"]}
    for path in valid_paths():
        spec = load_document(path)["spec"]
        if spec["profile"] != "synchronous-llm":
            continue
        assert spec["synchronousLlm"]["runtime"]["imageReference"] in executed


# --------------------------------------------------------------------------
# The published rule matrix and the code that applies it agree
# --------------------------------------------------------------------------


def test_every_rule_the_validator_can_cite_is_published_in_the_contract_document():
    """A rule a document does not name is a rule a consumer cannot look up."""
    published = CONTRACT_DOC.read_text(encoding="utf-8")
    missing = sorted(
        identifier for identifier in RULES if f"`{identifier}`" not in published
    )
    assert missing == [], f"rules absent from the contract document: {missing}"


def test_every_canonical_code_the_validator_can_emit_is_published():
    published = CONTRACT_DOC.read_text(encoding="utf-8")
    for code in CANONICAL_ERROR_CODES:
        assert f"`{code}`" in published


def test_no_canonical_code_this_validator_emits_is_retryable():
    assert not any(CANONICAL_ERROR_CODES.values())


def exercised_rules() -> set[str]:
    return {
        expected["rule"]
        for entry in manifest()["fixtures"].values()
        for expected in entry["expected"]
    }


def test_the_rule_registry_and_the_manifest_do_not_drift_apart():
    """Every semantic rule must have a fixture. An untested rule is a claim."""
    semantic = {identifier for identifier, rule in RULES.items() if rule.semantic}
    unexercised = sorted(semantic - exercised_rules())
    assert unexercised == [], f"semantic rules with no invalid fixture: {unexercised}"


#: Structural rules that no fixture exercises, and why each is allowed to have
#: none. The contract document publishes the same two, so a reader is never left
#: to infer coverage from the absence of a fixture.
STRUCTURAL_RULES_WITHOUT_A_FIXTURE = {
    # A JSON type error is unreachable from a YAML fixture wherever the schema
    # also constrains the value's format: the pattern or enum fails first, and
    # the pattern rule is what surfaces.
    "value-wrong-type",
    # The fallback for a keyword the translation table does not map. Reaching it
    # means the table needs a row, so a fixture pinning it would pin a defect.
    "contract-structure-invalid",
}


def test_the_structural_rules_without_a_fixture_are_the_two_we_declared():
    """The coverage gap is fixed in size, and it is this one.

    The manifest test above only binds semantic rules. This one stops the
    structural half from quietly growing rules nothing demonstrates.
    """
    structural = {identifier for identifier, rule in RULES.items() if not rule.semantic}
    unexercised = structural - exercised_rules()
    assert unexercised == STRUCTURAL_RULES_WITHOUT_A_FIXTURE, sorted(unexercised)


def test_the_uncovered_structural_rules_are_named_in_the_contract_document():
    published = CONTRACT_DOC.read_text(encoding="utf-8")
    for identifier in STRUCTURAL_RULES_WITHOUT_A_FIXTURE:
        assert f"`{identifier}`" in published
