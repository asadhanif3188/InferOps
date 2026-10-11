"""The ExperimentRun v1alpha1 schema, its fixtures, its validator, and its compatibility.

Every check here reads files from this repository, or files it writes under a
temporary directory, and nothing else. No network, no cluster, no clock, no
randomness. **No run executed**: every fixture is a hand-written document with
placeholder identities.

An ExperimentRun is the manifest of one run of one experiment against one delivered
release. Six things are asserted that a plain "the fixtures validate" suite would not
catch:

1. **The result state and the evidence level are separate.** The five states and the
   five levels share no value, each of the 25 pairs validates, a level is refused as
   a state, a state is refused as a level, and the schema has no member for a claim's
   status.
2. **The forms agree with the documents the identities come from.** The identifier
   form is the reliability caller record's, and the time form accepts what that
   record writes. The binding and image forms are the RenderedWorkloadRelease's, the
   model revision form is the WorkloadContract's, and the caller profile is a
   revision that ``tools.reliability_profile`` registers. One form differs, and a
   test measures it: the model digest has no ``sha256:`` prefix here.
3. **No member is named for what a manifest must not hold** - a prompt, a response,
   the content of an evidence file, a claim status. A statement is prose, and no rule
   reads it for one of these: a test measures that too.
4. **Refusals are exactly as published**, by the bare schema where the layer is
   structural, and quote no value of 12 characters or more from the document.
5. **The three manifests committed before the schema are registered, and are not
   made to look valid.** Each is refused by the schema, each has its registered
   content, and a fourth manifest of their shape is refused.
6. **The gaps are measured.** What the text heuristics and the semantic rules still
   accept is asserted, so closing a gap is a visible change.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from tools import experiment_run
from tools.contract_validation import RULES
from tools.contract_validation.errors import CANONICAL_ERROR_CODES
from tools.contract_validation.rendered_workload_release import (
    load_schema as load_release_schema,
)
from tools.contract_validation.workload import load_schema as load_workload_schema
from tools.experiment_e01 import core as e01_core
from tools.experiment_freeze import core as freeze_core
from tools.experiment_run import __main__ as command
from tools.experiment_run import core
from tools.reliability_profile import (
    CONCURRENCY,
    PROFILE_ID,
    PROFILE_PATH,
    REGISTERED_REVISIONS,
    profile_digest,
)
from tools.reliability_runner import incluster

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "contracts" / "experiment"
SCHEMA_PATH = CONTRACT_DIR / "experiment-run.v1alpha1.schema.json"
VALID_DIR = CONTRACT_DIR / "examples" / "valid"
INVALID_DIR = CONTRACT_DIR / "examples" / "invalid"
MANIFEST_PATH = INVALID_DIR / "expected-rejections.json"
EXAMPLES_README = CONTRACT_DIR / "examples" / "README.md"
REGISTER_PATH = REPO_ROOT / core.PRE_SCHEMA_REGISTER_REF
CONTRACT_DOC = REPO_ROOT / "docs" / "contracts" / "experiment-run.md"

EXPECTED_SCHEMA_ID = (
    "https://inferops.io/contracts/experiment/experiment-run.v1alpha1.schema.json"
)

#: The top-level members of a manifest, and all of them. No `spec` and no `status`:
#: nothing reconciles one. No member for a claim.
TOP_LEVEL = [
    "apiVersion",
    "kind",
    "metadata",
    "environment",
    "release",
    "runtime",
    "model",
    "callerProfile",
    "fault",
    "result",
    "evidenceLevel",
    "evidence",
    "cleanup",
    "limitations",
    "doesNotEstablish",
]

RESULT_STATES = ("PASSED", "FAILED", "INCONCLUSIVE", "REFUSED", "ABORTED")
EVIDENCE_LEVELS = ("C0", "C1", "C2", "C3", "C4")
CLAIM_STATUSES = ("certified", "planned", "deferred", "not-claimed")

#: The leaves that hold prose. Every other string leaf has a pattern or a vocabulary.
TEXT_LEAVES = frozenset(
    {
        "callerProfile.reason",
        "fault.reason",
        "result.reason",
        "cleanup.reason",
        "cleanup.left[]",
        "limitations[]",
        "doesNotEstablish[]",
    }
)

#: Property names that would be a home for request or response content, a claim, or
#: a secret value. The schema closes every object, so a hit means it was loosened.
FORBIDDEN_KEYS = frozenset(
    {
        "prompt",
        "prompts",
        "messages",
        "completion",
        "response",
        "responsebody",
        "body",
        "content",
        "text",
        "claim",
        "claims",
        "claimstatus",
        "status",
        "certified",
        "value",
        "values",
        "secret",
        "secrets",
        "password",
        "token",
        "apikey",
        "api_key",
        "credential",
        "credentials",
        "authorization",
        "kubeconfig",
    }
)

#: The three manifests committed before the schema, written out literally. The
#: register is data, so an edit to it shows here as a changed test.
PRE_SCHEMA_RECORDS = {
    "docs/proof/experiments/v2-e01/runs/20261002-e01-abc-1/run.v1alpha1.json": (
        "96b75bf78db35805fd16c8b71218bc7eeac3626aeac7129277e2067b0db0f393"
    ),
    "docs/proof/experiments/v2-e01/runs/20261003-e01-abc-1/run.v1alpha1.json": (
        "ae2e005b5f68bc3ed017c9c3e4c2c0508390306a784c2860b6c59ed5dafb5461"
    ),
    "docs/proof/experiments/v2-e01/runs/20261006-e01-d-1/run.v1alpha1.json": (
        "62255edaa5c078f6a1f67af140b923d2ef63e8b40d24c8919691aa37653c5733"
    ),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def manifest() -> dict[str, Any]:
    document: dict[str, Any] = load_json(MANIFEST_PATH)
    return document


def valid_paths() -> list[Path]:
    return sorted(VALID_DIR.glob("*.json"))


def invalid_paths() -> list[Path]:
    return sorted(
        path for path in INVALID_DIR.glob("*.json") if path.name != MANIFEST_PATH.name
    )


def base() -> dict[str, Any]:
    """A valid manifest: a registered fault, injected, under RP-1, PASSED."""
    document: dict[str, Any] = load_json(VALID_DIR / "fault-injected-passed.json")
    return document


def raw_validator() -> Draft202012Validator:
    """What a consumer holding only the schema file has."""
    return Draft202012Validator(load_json(SCHEMA_PATH))


def as_tuples(findings: Any) -> list[tuple[str, str, str]]:
    return [(f.code, f.rule, f.field) for f in findings]


def rules_of(document: Any) -> list[str]:
    return [finding.rule for finding in core.validate(document)]


def iter_schema_nodes(node: Any, pointer: str = "#") -> Iterator[tuple[str, dict]]:
    if isinstance(node, dict):
        yield pointer, node
        for key, value in node.items():
            yield from iter_schema_nodes(value, f"{pointer}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_schema_nodes(value, f"{pointer}/{index}")


def resolve(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    """Follow a local `$ref`, which is the only kind the schema uses."""
    while "$ref" in node:
        ref = node["$ref"]
        assert ref.startswith("#/$defs/"), ref
        node = schema["$defs"][ref.removeprefix("#/$defs/")]
    return node


def leaves(
    schema: dict[str, Any],
    node: dict[str, Any],
    prefix: str = "",
    required: bool = True,
) -> dict[str, tuple[dict[str, Any], bool]]:
    """Every leaf of a manifest: dotted path to its schema and whether it is required.

    A member is required when its object lists it under `required`, outside any
    condition. An array is followed into its items, with `[]` after its name.
    """
    node = resolve(schema, node)
    if node.get("type") == "array":
        return leaves(schema, node["items"], f"{prefix}[]", required)
    children = node.get("properties")
    if not children:
        return {prefix: (node, required)}
    found: dict[str, tuple[dict[str, Any], bool]] = {}
    for name, child in children.items():
        path = f"{prefix}.{name}" if prefix else name
        found.update(leaves(schema, child, path, name in node.get("required", [])))
    return found


def schema_leaves() -> dict[str, tuple[dict[str, Any], bool]]:
    schema = core.load_schema()
    return leaves(schema, schema)


def strings_of(node: Any) -> Iterator[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings_of(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings_of(value)


def keys_of(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from keys_of(value)
    elif isinstance(node, list):
        for value in node:
            yield from keys_of(value)


def published_table(anchor: str) -> list[list[str]]:
    """The data rows of the first table after a line of the contract document."""
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    start = text.index(anchor)
    rows: list[list[str]] = []
    in_table = False
    for line in text[start:].splitlines()[1:]:
        if line.startswith("|"):
            in_table = True
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not all(set(cell) <= set("-: ") for cell in cells):
                rows.append(cells)
        elif in_table:
            break
    return rows[1:]  # drop the header row


def backticked(cell: str) -> str:
    match = re.fullmatch(r"`([^`]+)`", cell)
    assert match, cell
    return match.group(1)


# --------------------------------------------------------------------------
# The schema itself
# --------------------------------------------------------------------------


def test_schema_is_a_valid_2020_12_schema():
    Draft202012Validator.check_schema(core.load_schema())


def test_schema_declares_its_dialect_identifier_version_and_kind():
    schema = core.load_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == EXPECTED_SCHEMA_ID
    assert schema["title"] == "ExperimentRun v1alpha1"
    assert schema["properties"]["apiVersion"]["const"] == core.SUPPORTED_API_VERSION
    assert schema["properties"]["kind"]["const"] == core.KIND == "ExperimentRun"


def test_every_object_in_the_schema_is_closed():
    """A manifest has no extension point: an open map is where content would land."""
    open_objects = [
        pointer
        for pointer, node in iter_schema_nodes(core.load_schema())
        if node.get("type") == "object"
        and node.get("additionalProperties") is not False
    ]
    assert open_objects == [], open_objects


def test_the_top_level_is_a_repository_document_with_no_member_for_a_claim():
    schema = core.load_schema()
    assert list(schema["properties"]) == TOP_LEVEL
    assert schema["required"] == TOP_LEVEL


def test_no_property_is_named_for_content_a_claim_or_a_secret():
    names = {
        name.lower()
        for _, node in iter_schema_nodes(core.load_schema())
        if node.get("type") == "object"
        for name in node.get("properties", {})
    }
    assert names & FORBIDDEN_KEYS == set(), names & FORBIDDEN_KEYS


def test_every_string_leaf_is_a_pattern_or_a_vocabulary_except_the_statements():
    """Prose is held in seven places and nowhere else, and each is bounded."""
    free: set[str] = set()
    for path, (node, _) in schema_leaves().items():
        if "enum" in node or "const" in node or node.get("type") != "string":
            continue
        if "pattern" not in node:
            free.add(path)
            assert node["minLength"] == 1 and node["maxLength"] == 2000, path
    assert free == TEXT_LEAVES


def test_every_array_is_bounded():
    unbounded = [
        pointer
        for pointer, node in iter_schema_nodes(core.load_schema())
        if node.get("type") == "array" and "maxItems" not in node
    ]
    assert unbounded == [], unbounded


#: What ends each pattern. Python's `$` also matches before a final line feed,
#: and the lookahead refuses that line feed.
END = "$(?!\\n)"


def patterned_values(node: Any, path: str = "") -> Iterator[tuple[str, list[Any]]]:
    """Each string of a document whose leaf has a pattern, with the keys to it."""

    def walk(value: Any, keys: list[Any]) -> Iterator[tuple[str, list[Any]]]:
        if isinstance(value, dict):
            for key, child in value.items():
                yield from walk(child, [*keys, key])
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from walk(child, [*keys, index])
        elif isinstance(value, str):
            leaf = ""
            for key in keys:
                if isinstance(key, int):
                    leaf += "[]"
                else:
                    leaf += f".{key}" if leaf else key
            if "pattern" in schema_leaves()[leaf][0]:
                yield leaf, keys

    yield from walk(node, [])


def test_every_pattern_refuses_a_final_line_feed():
    patterns = [
        node["pattern"]
        for _, node in iter_schema_nodes(core.load_schema())
        if isinstance(node.get("pattern"), str)
    ]
    assert len(patterns) == 12
    for pattern in patterns:
        assert pattern.startswith("^") and pattern.endswith(END), pattern


def test_a_value_that_ends_with_a_line_feed_is_refused_in_every_patterned_member():
    """33 values of one valid manifest, in 27 members, one at a time."""
    places = list(patterned_values(base()))
    assert len({leaf for leaf, _ in places}) == 27
    assert len(places) == 33
    for leaf, keys in places:
        document = base()
        target = document
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] += "\n"
        assert rules_of(document) == ["value-malformed"], leaf
        assert list(raw_validator().iter_errors(document)), leaf


def test_no_pattern_uses_a_class_that_admits_non_ascii_digits():
    r"""`\d` matches every Unicode digit in Python. The schema writes `[0-9]`."""
    for pointer, node in iter_schema_nodes(core.load_schema()):
        assert "\\d" not in node.get("pattern", ""), pointer


# --------------------------------------------------------------------------
# Result state, evidence level, and claim status are three things
# --------------------------------------------------------------------------


def test_the_result_states_are_the_five_run_states():
    schema = core.load_schema()
    states = schema["$defs"]["result"]["properties"]["state"]["enum"]
    assert tuple(states) == RESULT_STATES == core.RESULT_STATES
    assert set(states) == set(e01_core.OUTCOME_STATES)


def test_the_evidence_levels_are_c0_to_c4_and_unchanged():
    schema = core.load_schema()
    levels = schema["$defs"]["evidenceLevel"]["properties"]["intended"]["enum"]
    assert tuple(levels) == EVIDENCE_LEVELS == core.EVIDENCE_LEVELS
    assert tuple(levels) == tuple(freeze_core.EVIDENCE_LEVELS)


def test_no_result_state_is_an_evidence_level_or_a_claim_status():
    assert set(RESULT_STATES) & set(EVIDENCE_LEVELS) == set()
    assert set(RESULT_STATES) & set(CLAIM_STATUSES) == set()
    assert set(EVIDENCE_LEVELS) & set(CLAIM_STATUSES) == set()


@pytest.mark.parametrize("level", EVIDENCE_LEVELS)
def test_an_evidence_level_is_refused_as_a_result_state(level: str):
    document = base()
    document["result"] = {"state": level, "reason": "A level is not a state."}
    assert as_tuples(core.validate(document)) == [
        ("contract-invalid", "value-not-permitted", "$.result.state")
    ]


@pytest.mark.parametrize("state", RESULT_STATES)
def test_a_result_state_is_refused_as_an_evidence_level(state: str):
    document = base()
    document["evidenceLevel"]["intended"] = state
    assert as_tuples(core.validate(document)) == [
        ("contract-invalid", "value-not-permitted", "$.evidenceLevel.intended")
    ]


@pytest.mark.parametrize("status", CLAIM_STATUSES)
def test_a_claim_status_has_no_member_and_is_no_result_state(status: str):
    document = base()
    document["result"] = {"state": status, "reason": "A status is not a state."}
    assert rules_of(document) == ["value-not-permitted"]
    for holder in ("$", "result", "evidenceLevel", "metadata"):
        document = base()
        target = document if holder == "$" else document[holder]
        target["claimStatus"] = status
        assert rules_of(document) == ["field-unknown"], holder


@pytest.mark.parametrize("level", EVIDENCE_LEVELS)
@pytest.mark.parametrize("state", RESULT_STATES)
def test_every_result_state_validates_at_every_evidence_level(state: str, level: str):
    """25 pairs. The state of a run does not bound the level of its evidence."""
    document = base()
    document["result"] = {"state": state, "reason": "Stated for the pair."}
    document["evidenceLevel"]["intended"] = level
    if state == "REFUSED":
        document["fault"] = {
            "registered": True,
            "type": "delete-runtime-pod",
            "injected": False,
            "reason": "The run was refused before its procedure started.",
        }
    assert core.validate(document) == []


def test_a_claim_status_word_in_a_name_or_a_statement_is_not_refused():
    """Measured. The schema refuses a member for a claim status. It does not read a
    value with an open vocabulary, or a statement, for the words."""
    document = base()
    document["evidence"]["files"][1]["role"] = "certified"
    document["environment"]["provider"] = "planned"
    document["limitations"].append("Claim status: certified. Achieved level: C2.")
    assert core.validate(document) == []


def test_a_statement_is_not_read_for_a_prompt_or_a_response():
    """Measured. No member is defined for content, and no rule reads a statement."""
    document = base()
    document["limitations"].append("Prompt: Name three things. Response: Three.")
    assert core.validate(document) == []


def test_the_run_states_one_intended_level_and_assigns_none_to_itself():
    schema = core.load_schema()
    assert list(schema["$defs"]["evidenceLevel"]["properties"]) == ["intended"]


# --------------------------------------------------------------------------
# Identities agree with the documents they are copied from
# --------------------------------------------------------------------------


def test_the_identifier_form_is_the_caller_records():
    """One run can carry one experiment identifier and one run identifier in both."""
    schema = core.load_schema()
    assert (
        schema["$defs"]["identifier"]["pattern"]
        == f"^{incluster.IDENTIFIER.pattern}{END}"
    )
    for member in ("experimentId", "runId"):
        assert schema["$defs"]["metadata"]["properties"][member] == {
            "description": schema["$defs"]["metadata"]["properties"][member][
                "description"
            ],
            "$ref": "#/$defs/identifier",
        }


def test_the_digest_form_is_the_caller_records_and_the_releases():
    schema = core.load_schema()
    release = load_release_schema()
    assert schema["$defs"]["sha256"]["pattern"] == f"^{incluster.SHA256.pattern}{END}"
    for name in ("sha256", "gitRevision"):
        released = release["$defs"][name]["pattern"]
        assert released.endswith("$")
        assert schema["$defs"][name]["pattern"] == released[:-1] + END


def test_the_time_form_accepts_what_the_caller_record_writes():
    schema = core.load_schema()
    pattern = re.compile(schema["$defs"]["utcInstant"]["pattern"])
    moment = datetime(2026, 1, 1, 10, 5, 0, 250_000, tzinfo=UTC)
    written = incluster.utc_text(moment)
    assert written == "2026-01-01T10:05:00.250Z"
    assert pattern.fullmatch(written), written
    assert core._instant(written) == moment


def test_the_binding_and_image_forms_are_the_releases():
    schema = core.load_schema()
    release = load_release_schema()
    for name in ("dnsLabel", "digestPinnedImageReference"):
        form = release["$defs"][name]["pattern"]
        assert form.endswith("$")
        assert schema["$defs"][name]["pattern"] == form[:-1] + END
        assert schema["$defs"][name]["maxLength"] == release["$defs"][name]["maxLength"]
    binding = schema["$defs"]["environmentBindingReference"]["properties"]
    released = release["$defs"]["environmentBindingReference"]["properties"]
    assert binding["environment"]["enum"] == released["environment"]["enum"]
    assert set(binding) == set(released) - {"apiVersion"}


def test_the_model_revision_form_is_the_workload_contracts():
    schema = core.load_schema()
    workload = load_workload_schema()
    contracted = workload["$defs"]["sha256Hex"]["pattern"]
    assert contracted.endswith("$")
    assert (
        schema["$defs"]["model"]["properties"]["revision"]["pattern"]
        == contracted[:-1] + END
    )


def test_the_model_digest_form_is_not_the_workload_contracts():
    """Measured. The contract writes the artifact digest with a `sha256:` prefix. A
    manifest writes 64 characters with no prefix, as it writes each other digest."""
    workload = load_workload_schema()
    contracted = re.compile(workload["$defs"]["sha256Digest"]["pattern"])
    digest = "9" * 64
    assert contracted.search(f"sha256:{digest}") and not contracted.search(digest)
    document = base()
    document["model"]["sha256"] = digest
    assert core.validate(document) == []
    document["model"]["sha256"] = f"sha256:{digest}"
    assert as_tuples(core.validate(document)) == [
        ("contract-invalid", "value-malformed", "$.model.sha256")
    ]


def test_the_registered_caller_profiles_are_the_reliability_profiles():
    assert {
        (PROFILE_ID, revision): core.CallerProfileRevision(digest, CONCURRENCY)
        for revision, digest in REGISTERED_REVISIONS.items()
    } == core.REGISTERED_CALLER_PROFILES
    assert core.REGISTERED_CALLER_PROFILES[("RP-1", 1)].concurrency == 2
    assert core.REGISTERED_CALLER_PROFILES[
        ("RP-1", 1)
    ].content_sha256 == profile_digest(PROFILE_PATH)


# --------------------------------------------------------------------------
# Valid fixtures
# --------------------------------------------------------------------------


def test_six_valid_fixtures_exist():
    assert [path.name for path in valid_paths()] == [
        "aborted-after-the-fault.json",
        "fault-injected-failed.json",
        "fault-injected-passed.json",
        "inconclusive-without-a-caller-record.json",
        "no-fault-and-no-caller-profile.json",
        "refused-before-the-procedure.json",
    ]


@pytest.mark.parametrize("path", valid_paths(), ids=lambda path: path.name)
def test_a_valid_fixture_validates(path: Path):
    document = core.read_document(path)
    assert list(raw_validator().iter_errors(document)) == []
    assert core.validate(document) == []
    assert core.is_valid(document)


def test_the_valid_fixtures_hold_every_result_state():
    states = {load_json(path)["result"]["state"] for path in valid_paths()}
    assert states == set(RESULT_STATES)


@pytest.mark.parametrize("path", valid_paths(), ids=lambda path: path.name)
def test_a_valid_fixture_says_in_its_own_contents_that_no_run_executed(path: Path):
    document = load_json(path)
    assert document["limitations"][0].startswith("Fixture. No run executed.")
    assert document["metadata"]["experimentId"].startswith("EXAMPLE-")
    assert "-example-" in document["metadata"]["runId"]


@pytest.mark.parametrize("path", valid_paths(), ids=lambda path: path.name)
def test_a_valid_fixture_names_no_committed_file_and_holds_placeholder_digests(
    path: Path,
):
    """Every digest is one repeated character, except the caller profile's."""
    document = load_json(path)
    assert not (REPO_ROOT / document["metadata"]["spec"]["freezeRecord"]).exists()
    profile = document["callerProfile"].get("contentSha256")
    for value in strings_of(document):
        if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) and value != profile:
            assert len(set(value)) == 1, value
    if profile is not None:
        assert profile == profile_digest(PROFILE_PATH)


@pytest.mark.parametrize("path", valid_paths(), ids=lambda path: path.name)
def test_a_valid_fixture_holds_no_forbidden_member_name(path: Path):
    assert {key.lower() for key in keys_of(load_json(path))} & FORBIDDEN_KEYS == set()


# --------------------------------------------------------------------------
# Invalid fixtures
# --------------------------------------------------------------------------


def test_the_rejection_manifest_names_exactly_the_invalid_fixtures():
    assert sorted(manifest()["fixtures"]) == [path.name for path in invalid_paths()]
    assert set(manifest()["layers"]) == {"structural", "semantic"}


def test_thirty_six_invalid_fixtures_exist_in_two_layers():
    layers = [entry["layer"] for entry in manifest()["fixtures"].values()]
    assert len(layers) == 36
    assert layers.count("structural") == 22
    assert layers.count("semantic") == 14


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda path: path.name)
def test_an_invalid_fixture_is_refused_exactly_as_published(path: Path):
    entry = manifest()["fixtures"][path.name]
    expected = sorted(
        (item["code"], item["rule"], item["field"]) for item in entry["expected"]
    )
    document = core.read_document(path)
    findings = core.validate(document)
    assert sorted(as_tuples(findings)) == expected
    assert findings == sorted(findings)
    assert core.validate(document) == findings
    assert entry["refusedFor"]


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda path: path.name)
def test_the_bare_schema_refuses_exactly_the_structural_fixtures(path: Path):
    """A consumer with only the schema file does not get the semantic refusals."""
    layer = manifest()["fixtures"][path.name]["layer"]
    errors = list(raw_validator().iter_errors(load_json(path)))
    assert bool(errors) == (layer == "structural")


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda path: path.name)
def test_a_refusal_quotes_no_value_of_the_document(path: Path):
    document = load_json(path)
    values = {value for value in strings_of(document) if len(value) >= 12}
    for finding in core.validate(document):
        assert finding.code in CANONICAL_ERROR_CODES
        for value in values:
            assert value not in finding.message, finding.rule
            assert value not in finding.field, finding.rule


def test_every_semantic_rule_has_a_fixture_that_fails_because_of_it():
    covered = {
        item["rule"]
        for entry in manifest()["fixtures"].values()
        if entry["layer"] == "semantic"
        for item in entry["expected"]
    }
    assert covered == set(core.SEMANTIC_RULES)
    assert len(core.SEMANTIC_RULES) == 14


def test_every_structural_rule_but_the_fallback_has_a_fixture():
    covered = {
        item["rule"]
        for entry in manifest()["fixtures"].values()
        if entry["layer"] == "structural"
        for item in entry["expected"]
    }
    structural = {name for name, rule in RULES.items() if not rule.semantic}
    assert structural - covered == {"contract-structure-invalid"}
    assert covered <= structural


def test_no_rule_of_this_validator_reuses_a_canonical_rule_identifier():
    own = set(core.SEMANTIC_RULES) | set(core.REPOSITORY_RULES)
    assert own & set(RULES) == set()
    assert set(core.SEMANTIC_RULES) & set(core.REPOSITORY_RULES) == set()
    assert all(name.startswith("run-") for name in own)


def test_the_invalid_fixtures_carry_one_published_placeholder_and_no_other_secret():
    """The one fixture for the credential rule holds the AWS documentation key."""
    holders = [
        path.name
        for path in invalid_paths()
        if "AKIAIOSFODNN7EXAMPLE" in path.read_text(encoding="utf-8")
    ]
    assert holders == ["credential-shaped-value.json"]


# --------------------------------------------------------------------------
# The semantic layer, beyond the fixtures
# --------------------------------------------------------------------------


def test_the_semantic_layer_does_not_run_on_a_document_the_schema_refuses():
    document = base()
    document["metadata"]["finishedAt"] = "2026-01-01T09:00:00Z"
    assert rules_of(document) == ["run-time-order-inverted"]
    document["claimStatus"] = "certified"
    assert rules_of(document) == ["field-unknown"]


@pytest.mark.parametrize(
    "text",
    [
        "2026-02-29T10:00:00Z",
        "2026-00-10T10:00:00Z",
        "2026-01-32T10:00:00Z",
        "2026-01-01T24:00:00Z",
        "2026-01-01T10:60:00Z",
        "2026-01-01T10:00:60Z",
        "2026-01-01T10:00:61Z",
        "0000-01-01T10:00:00Z",
    ],
)
def test_a_time_of_the_right_form_that_names_no_instant_is_refused(text: str):
    assert re.fullmatch(core.load_schema()["$defs"]["utcInstant"]["pattern"], text), (
        "the schema accepts the form"
    )
    document = base()
    document["metadata"]["startedAt"] = text
    assert as_tuples(core.validate(document)) == [
        ("contract-invalid", "run-time-not-an-instant", "$.metadata.startedAt")
    ]


def test_a_fault_at_the_first_or_the_last_instant_of_the_run_is_accepted():
    for instant in ("2026-01-01T10:00:00Z", "2026-01-01T10:20:00.000000Z"):
        document = base()
        document["fault"]["injectedAt"] = instant
        assert core.validate(document) == []


def test_instants_compare_by_value_and_not_as_text():
    """`10:00:00.5Z` is later than `10:00:00Z`, and sorts before it as text."""
    document = base()
    document["metadata"]["startedAt"] = "2026-01-01T10:00:00.5Z"
    document["metadata"]["finishedAt"] = "2026-01-01T10:00:00Z"
    assert rules_of(document) == ["run-time-order-inverted"]
    document["metadata"]["startedAt"] = "2026-01-01T10:00:00Z"
    document["metadata"]["finishedAt"] = "2026-01-01T10:00:00.5Z"
    document["fault"]["injectedAt"] = "2026-01-01T10:00:00.25Z"
    assert core.validate(document) == []


def test_a_fault_before_the_run_starts_is_refused():
    document = base()
    document["fault"]["injectedAt"] = "2026-01-01T09:59:59.999Z"
    assert rules_of(document) == ["run-fault-time-outside-run"]


def test_a_run_that_starts_and_ends_at_one_instant_is_accepted():
    document = load_json(VALID_DIR / "refused-before-the-procedure.json")
    document["metadata"]["finishedAt"] = document["metadata"]["startedAt"]
    assert core.validate(document) == []


@pytest.mark.parametrize("state", ["FAILED", "INCONCLUSIVE", "ABORTED"])
def test_a_run_that_is_not_passed_or_refused_is_not_bound_to_the_injection(
    state: str,
):
    """Measured: a FAILED run whose registered fault was not injected validates."""
    document = base()
    document["fault"] = {
        "registered": True,
        "type": "delete-runtime-pod",
        "injected": False,
        "reason": "The fault was not injected.",
    }
    document["result"] = {"state": state, "reason": "Stated."}
    assert core.validate(document) == []


@pytest.mark.parametrize("state", ["INCONCLUSIVE", "REFUSED", "ABORTED"])
def test_a_run_that_decides_nothing_needs_no_caller_evidence(state: str):
    document = load_json(VALID_DIR / "refused-before-the-procedure.json")
    document["result"] = {"state": state, "reason": "Stated."}
    assert document["evidence"]["files"] == []
    assert core.validate(document) == []


@pytest.mark.parametrize("state", ["PASSED", "FAILED"])
def test_a_run_that_decides_its_criteria_names_an_evidence_file(state: str):
    document = load_json(VALID_DIR / "no-fault-and-no-caller-profile.json")
    document["result"] = {"state": state, "reason": "Stated."}
    document["evidence"]["files"] = []
    assert as_tuples(core.validate(document)) == [
        ("contract-invalid", "run-decided-without-evidence", "$.evidence.files")
    ]
    document = base()
    document["result"] = {"state": state, "reason": "Stated."}
    document["evidence"]["files"] = []
    assert rules_of(document) == [
        "run-caller-evidence-missing",
        "run-decided-without-evidence",
    ]


def test_a_cleanup_states_a_reason_only_when_it_is_not_verified():
    document = base()
    document["cleanup"] = {"state": "verified", "reason": "Stated."}
    assert as_tuples(core.validate(document)) == [
        ("contract-invalid", "value-not-permitted", "$.cleanup")
    ]


@pytest.mark.parametrize("state", ["verified", "incomplete"])
def test_a_cleanup_that_ran_can_list_what_it_left(state: str):
    """Measured: a verified cleanup that lists an item it left validates."""
    document = base()
    document["cleanup"] = {"state": state, "left": ["One image, in the node."]}
    if state == "incomplete":
        document["cleanup"]["reason"] = "Stated."
    assert core.validate(document) == []


def test_evidence_paths_that_no_directory_can_hold_together_still_validate():
    """Measured: `pods` and `pods/a.json` cannot both be files. No rule reads that."""
    document = base()
    document["evidence"]["files"][1]["path"] = "pods"
    document["evidence"]["files"][2]["path"] = "pods/a.json"
    assert core.validate(document) == []


def test_a_failed_run_under_a_caller_profile_needs_caller_evidence():
    document = load_json(VALID_DIR / "fault-injected-failed.json")
    document["evidence"]["files"] = document["evidence"]["files"][1:]
    assert rules_of(document) == ["run-caller-evidence-missing"]


def test_a_run_with_no_caller_profile_needs_no_caller_evidence():
    document = load_json(VALID_DIR / "no-fault-and-no-caller-profile.json")
    assert "caller" not in {entry["role"] for entry in document["evidence"]["files"]}
    assert core.validate(document) == []


def test_an_unregistered_profile_reports_one_finding_and_not_three():
    document = base()
    document["callerProfile"].update(
        profileId="RP-2", contentSha256="e" * 64, concurrency=8
    )
    assert as_tuples(core.validate(document)) == [
        (
            "contract-invalid",
            "run-caller-profile-unregistered",
            "$.callerProfile.profileRevision",
        )
    ]


def test_a_registered_profile_reports_its_digest_and_its_concurrency_apart():
    document = base()
    document["callerProfile"].update(contentSha256="e" * 64, concurrency=1)
    assert rules_of(document) == [
        "run-caller-concurrency-differs",
        "run-caller-profile-digest-differs",
    ]


def test_json_true_is_not_the_integer_one():
    """`1 == True` in Python. The schema reads JSON types."""
    document = base()
    document["callerProfile"]["profileRevision"] = True
    assert rules_of(document) == ["value-wrong-type"]
    document = base()
    document["fault"]["registered"] = 1
    assert "value-wrong-type" in rules_of(document)
    document = base()
    document["environment"]["nodeCount"] = 1.0
    assert core.validate(document) == [], "JSON Schema reads 1.0 as an integer"


# --- the text heuristics ---------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "The operator pasted AKIAIOSFODNN7EXAMPLE into the notes.",
        'The notes hold "ghp_0000000000000000000000000000000000" in quotes.',
        "A token (glpat-00000000000000000000) is in the transcript.",
        "The segment Zx4Kq9TbLm2Rd7Wf1Hs3Nv8Yc6Ej0Pa is in the transcript.",
        "The notes hold key=AKIAIOSFODNN7EXAMPLE behind an equals sign.",
    ],
)
def test_a_statement_with_a_credential_shaped_word_is_refused(statement: str):
    document = base()
    document["limitations"].append(statement)
    findings = core.validate(document)
    assert as_tuples(findings) == [
        ("contract-invalid", "run-value-credential-shaped", "$.limitations[2]")
    ]
    long_words = [word for word in statement.split() if len(word) >= 12]
    assert long_words and all(word not in findings[0].message for word in long_words)


@pytest.mark.parametrize(
    "statement",
    [
        "The value q7f3k9x2m4p8w6z1 is a lowercase secret with no published prefix.",
        "A token *glpat-00000000000000000000* is behind an asterisk.",
        "A token key=glpat-00000000000000000000 is behind an equals sign.",
    ],
)
def test_credential_shapes_the_heuristic_still_accepts(statement: str):
    """Measured gaps. The heuristic reads the start of a word and one opaque shape."""
    assert not core.credential_shaped(statement)
    document = base()
    document["limitations"].append(statement)
    assert core.validate(document) == []


def test_an_identifier_with_a_credential_prefix_is_refused_where_the_pattern_admits_it():
    document = base()
    document["metadata"]["runId"] = "AKIAIOSFODNN7EXAMPLE"
    assert as_tuples(core.validate(document)) == [
        ("contract-invalid", "run-value-credential-shaped", "$.metadata.runId")
    ]


@pytest.mark.parametrize(
    "statement",
    [
        "The transcript was copied from D:\\work\\example\\transcript.txt.",
        "The driver ran from c:/work/example on the host.",
        # Each account root is joined here: the security baseline refuses the two
        # written out in any committed file.
        "The files are under /" + "home" + "/example/runs/ on the host.",
        "The files are under /" + "Users" + "/example/runs/ on the host.",
        "The driver ran as root, from /root/example.",
    ],
)
def test_a_statement_with_a_host_path_is_refused(statement: str):
    document = base()
    document["doesNotEstablish"].append(statement)
    assert as_tuples(core.validate(document)) == [
        ("contract-invalid", "run-text-host-path", "$.doesNotEstablish[2]")
    ]


@pytest.mark.parametrize(
    "statement",
    [
        "The record is at docs/proof/experiments/example-e1/freeze-r1.v1alpha1.json.",
        "The method is at https://example.invalid/home/method on the public site.",
        "The ratio is 3:/4 in the notes.",
        "The absolute path of the repository on the host is replaced by <repository>.",
    ],
)
def test_a_statement_with_no_host_path_is_accepted(statement: str):
    document = base()
    document["limitations"].append(statement)
    assert core.validate(document) == []


@pytest.mark.parametrize(
    "statement",
    [
        "The files are under /var/lib/example on the node.",
        "The files are under \\\\host\\share\\example on the network.",
        "The files are under ~/example on the host.",
        "The files are under /mnt/d/work/example on the host.",
        "The driver ran as root, from /root.",
        "The files are under D:work on the host.",
    ],
)
def test_host_paths_the_heuristic_still_accepts(statement: str):
    """Measured gaps. The rule reads a drive letter and three account roots."""
    assert not core.holds_host_path(statement)
    document = base()
    document["limitations"].append(statement)
    assert core.validate(document) == []


def test_ordinary_text_that_the_heuristics_refuse():
    """Measured false positives. A writer must reword such a statement."""
    assert core.credential_shaped("See Kubernetes1ControllerManagerAdmission.")
    assert core.holds_host_path("The option is -f:/dev in the notes.")


def test_the_statements_of_the_pre_schema_manifests_trip_neither_heuristic():
    """Prose that three real run manifests hold is not read as a credential or a path."""
    statements = [
        statement
        for ref in PRE_SCHEMA_RECORDS
        for member in ("limitations", "doesNotEstablish")
        for statement in load_json(REPO_ROOT / ref).get(member, [])
    ]
    assert len(statements) >= 20
    for statement in statements:
        assert not core.credential_shaped(statement), statement
        assert not core.holds_host_path(statement), statement


# --------------------------------------------------------------------------
# Reading a file
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ('{"kind": "ExperimentRun", "kind": "ExperimentRun"}', "one member twice"),
        ('{"result": {"state": "FAILED", "state": "PASSED"}}', "one member twice"),
        ("[]", "not a JSON object"),
        ('"ExperimentRun"', "not a JSON object"),
        ("{", "not JSON"),
        ('{"nodeCount": NaN}', "not JSON"),
        ('{"nodeCount": Infinity}', "not JSON"),
        ("", "not JSON"),
        ("[" * 100_000, "not JSON"),
    ],
    ids=[
        "member twice",
        "nested member twice",
        "array",
        "string",
        "truncated",
        "NaN",
        "Infinity",
        "empty",
        "100,000 nested arrays",
    ],
)
def test_a_file_that_is_not_one_json_object_is_refused(
    tmp_path: Path, text: str, said: str
):
    path = tmp_path / "run.v1alpha1.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(core.RunDocumentError) as refused:
        core.read_document(path)
    assert refused.value.rule == "run-document-unreadable"
    assert said in refused.value.message


def test_a_file_that_is_absent_or_not_utf8_is_refused(tmp_path: Path):
    with pytest.raises(core.RunDocumentError) as refused:
        core.read_document(tmp_path / "absent.json")
    assert refused.value.rule == "run-document-unreadable"
    path = tmp_path / "run.v1alpha1.json"
    path.write_bytes(b'{"kind": "\xff"}')
    with pytest.raises(core.RunDocumentError):
        core.read_document(path)


def test_the_content_digest_ignores_the_line_endings_of_a_checkout():
    assert core.content_digest(b"a\r\nb\r\n") == core.content_digest(b"a\nb\n")
    assert core.content_digest(b"a\nb\n") != core.content_digest(b"a\nb")


# --------------------------------------------------------------------------
# Compatibility: the manifests committed before the schema
# --------------------------------------------------------------------------


def test_the_register_names_the_three_manifests_committed_before_the_schema():
    assert core.load_pre_schema_register() == PRE_SCHEMA_RECORDS
    document = load_json(REGISTER_PATH)
    assert document["kind"] == "PreSchemaExperimentRunRegister"
    assert set(document) == {"schemaVersion", "kind", "description", "records"}


@pytest.mark.parametrize("ref", sorted(PRE_SCHEMA_RECORDS))
def test_a_pre_schema_manifest_states_the_kind_and_the_schema_refuses_it(ref: str):
    """The three are registered because they do not conform, and they do not."""
    path = REPO_ROOT / ref
    document = core.read_document(path)
    assert document["apiVersion"] == core.SUPPORTED_API_VERSION
    assert document["kind"] == core.KIND
    assert core.content_digest(path.read_bytes()) == PRE_SCHEMA_RECORDS[ref]
    rules = set(rules_of(document))
    assert {"field-required", "field-unknown"} <= rules


def test_the_committed_tree_holds_three_pre_schema_manifests_and_no_other():
    report = core.repository_report()
    assert not report.refused
    assert report.findings == ()
    assert [(entry.path, entry.status) for entry in report.manifests] == [
        (ref, core.PRE_SCHEMA) for ref in sorted(PRE_SCHEMA_RECORDS)
    ]


def test_the_e01_runner_writes_the_registered_name_and_kind():
    """The runner's constants are the name, the kind, and the version of this schema.
    The test executes no run: that a fourth manifest of the earlier shape is refused
    is held by the test of that name below."""
    assert e01_core.MANIFEST == core.MANIFEST_NAME
    assert e01_core.KIND == core.KIND
    assert e01_core.API_VERSION == core.SUPPORTED_API_VERSION


def tree(tmp_path: Path) -> Path:
    """A copy of the register and of the three manifests, under a temporary root."""
    root = tmp_path / "tree"
    for ref in (core.PRE_SCHEMA_REGISTER_REF, *PRE_SCHEMA_RECORDS):
        target = root / ref
        target.parent.mkdir(parents=True)
        shutil.copyfile(REPO_ROOT / ref, target)
    return root


def statuses(root: Path) -> dict[str, str]:
    return {
        entry.path: entry.status for entry in core.repository_report(root).manifests
    }


def write_run(root: Path, name: str, document: Any) -> str:
    ref = f"{core.RUNS_ROOT_REF}/example-e1/runs/{name}/{core.MANIFEST_NAME}"
    path = root / ref
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return ref


def test_a_copy_of_the_tree_reports_what_the_tree_reports(tmp_path: Path):
    root = tree(tmp_path)
    assert statuses(root) == dict.fromkeys(PRE_SCHEMA_RECORDS, core.PRE_SCHEMA)
    assert not core.repository_report(root).refused


def test_a_new_manifest_that_validates_is_conforming(tmp_path: Path):
    root = tree(tmp_path)
    ref = write_run(root, "20260101-example-e1-1", base())
    report = core.repository_report(root)
    assert statuses(root)[ref] == core.CONFORMING
    assert not report.refused
    assert len(report.manifests) == 4


def test_a_new_manifest_that_does_not_validate_is_refused(tmp_path: Path):
    root = tree(tmp_path)
    document = base()
    document["result"]["state"] = "C2"
    ref = write_run(root, "20260101-example-e1-1", document)
    report = core.repository_report(root)
    entry = next(entry for entry in report.manifests if entry.path == ref)
    assert entry.status == core.REFUSED
    assert [finding.rule for finding in entry.findings] == ["value-not-permitted"]
    assert report.refused


def test_a_fourth_manifest_of_the_pre_schema_shape_is_refused(tmp_path: Path):
    """The list is closed: the shape is admitted by name and digest, not by form."""
    root = tree(tmp_path)
    earlier = load_json(REPO_ROOT / sorted(PRE_SCHEMA_RECORDS)[2])
    ref = write_run(root, "20260101-example-e1-1", earlier)
    assert statuses(root)[ref] == core.REFUSED
    assert core.repository_report(root).refused


def test_a_file_with_the_manifest_name_in_another_case_is_not_listed(
    tmp_path: Path,
):
    """The name is compared as text, so a host that ignores case lists what a host
    that does not ignore it lists."""
    root = tree(tmp_path)
    ref = write_run(root, "20260101-example-e1-1", {"kind": "ExperimentRun"})
    path = root / ref
    path.rename(path.with_name(core.MANIFEST_NAME.upper()))
    report = core.repository_report(root)
    assert len(report.manifests) == 3
    assert not report.refused


def test_a_manifest_that_cannot_be_read_is_refused(tmp_path: Path):
    root = tree(tmp_path)
    ref = write_run(root, "20260101-example-e1-1", base())
    (root / ref).write_text("{", encoding="utf-8")
    entry = next(e for e in core.repository_report(root).manifests if e.path == ref)
    assert [finding.rule for finding in entry.findings] == ["run-document-unreadable"]


def test_an_edited_pre_schema_manifest_is_refused(tmp_path: Path):
    root = tree(tmp_path)
    ref = sorted(PRE_SCHEMA_RECORDS)[0]
    path = root / ref
    path.write_bytes(path.read_bytes().replace(b"PASSED", b"FAILED", 1))
    report = core.repository_report(root)
    entry = next(entry for entry in report.manifests if entry.path == ref)
    assert entry.status == core.REFUSED
    assert [finding.rule for finding in entry.findings] == [
        "run-pre-schema-record-edited"
    ]


def test_a_pre_schema_manifest_with_other_line_endings_is_not_edited(tmp_path: Path):
    root = tree(tmp_path)
    ref = sorted(PRE_SCHEMA_RECORDS)[0]
    path = root / ref
    lf = path.read_bytes().replace(b"\r\n", b"\n")
    path.write_bytes(lf.replace(b"\n", b"\r\n"))
    assert statuses(root)[ref] == core.PRE_SCHEMA


def test_an_absent_pre_schema_manifest_is_a_finding(tmp_path: Path):
    root = tree(tmp_path)
    ref = sorted(PRE_SCHEMA_RECORDS)[1]
    (root / ref).unlink()
    report = core.repository_report(root)
    assert [finding.rule for finding in report.findings] == [
        "run-pre-schema-record-missing"
    ]
    assert ref in report.findings[0].message
    assert report.refused


def edit_register(root: Path, edit: Any) -> None:
    path = root / core.PRE_SCHEMA_REGISTER_REF
    document = load_json(path)
    edit(document)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


REGISTER_DEFECTS = {
    "another kind": lambda d: d.__setitem__("kind", "ExperimentRun"),
    "another version": lambda d: d.__setitem__("schemaVersion", "inferops.io/v1"),
    "records not a list": lambda d: d.__setitem__("records", {}),
    "a record that is a string": lambda d: d["records"].append("run.v1alpha1.json"),
    "a record with a third member": lambda d: d["records"][0].__setitem__(
        "reason", "earlier"
    ),
    "a record with no digest": lambda d: d["records"][0].pop("contentSha256"),
    "a digest in uppercase": lambda d: d["records"][0].__setitem__(
        "contentSha256", "A" * 64
    ),
    "a digest that is a number": lambda d: d["records"][0].__setitem__(
        "contentSha256", 1
    ),
    "a path named twice": lambda d: d["records"].append(dict(d["records"][0])),
    "a path with a parent segment": lambda d: d["records"][0].__setitem__(
        "path", "docs/../docs/run.v1alpha1.json"
    ),
    "a path that is absolute": lambda d: d["records"][0].__setitem__(
        "path", "/docs/proof/experiments/run.v1alpha1.json"
    ),
    "a path that is not a run manifest": lambda d: d["records"][0].__setitem__(
        "path", "docs/proof/experiments/v2-e01/freeze-r1.v1alpha1.json"
    ),
}


@pytest.mark.parametrize("defect", sorted(REGISTER_DEFECTS))
def test_a_register_with_a_defect_is_refused(tmp_path: Path, defect: str):
    root = tree(tmp_path)
    edit_register(root, REGISTER_DEFECTS[defect])
    with pytest.raises(core.RunDocumentError) as refused:
        core.load_pre_schema_register(root)
    assert refused.value.rule == "run-pre-schema-register-unreadable"
    report = core.repository_report(root)
    assert report.manifests == ()
    assert [finding.rule for finding in report.findings] == [
        "run-pre-schema-register-unreadable"
    ]
    assert report.refused


def test_an_absent_register_is_refused(tmp_path: Path):
    root = tree(tmp_path)
    (root / core.PRE_SCHEMA_REGISTER_REF).unlink()
    report = core.repository_report(root)
    assert report.refused
    assert [finding.rule for finding in report.findings] == [
        "run-pre-schema-register-unreadable"
    ]


def test_a_register_that_gains_a_record_admits_the_manifest_it_names(tmp_path: Path):
    """Measured. The register is a tripwire and not a lock: the literal list above
    is what shows such an edit in review."""
    root = tree(tmp_path)
    earlier = load_json(REPO_ROOT / sorted(PRE_SCHEMA_RECORDS)[2])
    ref = write_run(root, "20260101-example-e1-1", earlier)
    digest = core.content_digest((root / ref).read_bytes())
    edit_register(
        root, lambda d: d["records"].append({"path": ref, "contentSha256": digest})
    )
    assert statuses(root)[ref] == core.PRE_SCHEMA


def test_a_tree_with_no_runs_directory_holds_no_manifest(tmp_path: Path):
    root = tmp_path / "tree"
    target = root / core.PRE_SCHEMA_REGISTER_REF
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "schemaVersion": core.SUPPORTED_API_VERSION,
                "kind": "PreSchemaExperimentRunRegister",
                "records": [],
            }
        ),
        encoding="utf-8",
    )
    report = core.repository_report(root)
    assert report.manifests == () and not report.refused


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_check_command_accepts_every_valid_fixture(
    capsys: pytest.CaptureFixture[str],
):
    assert command.main(["check", *map(str, valid_paths())]) == 0
    output = capsys.readouterr().out.splitlines()
    assert len(output) == 6
    assert all(line.startswith("ok ") for line in output)


def test_the_check_command_refuses_an_invalid_fixture_and_names_the_rule(
    capsys: pytest.CaptureFixture[str],
):
    path = INVALID_DIR / "evidence-level-as-result-state.json"
    assert command.main(["check", str(path), str(valid_paths()[0])]) == 3
    output = capsys.readouterr().out
    assert "REFUSED" in output and "(1 finding(s))" in output
    assert "contract-invalid  value-not-permitted  $.result.state" in output
    assert "ok " in output


def test_the_check_command_refuses_a_file_it_cannot_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    assert command.main(["check", str(tmp_path / "absent.json")]) == 3
    assert "run-document-unreadable" in capsys.readouterr().out


def test_the_repository_command_lists_the_committed_manifests(
    capsys: pytest.CaptureFixture[str],
):
    assert command.main(["repository"]) == 0
    output = capsys.readouterr().out.splitlines()
    assert output[:3] == [f"pre-schema {ref}" for ref in sorted(PRE_SCHEMA_RECORDS)]
    assert output[3] == "manifests  3: 3 pre-schema, 0 conforming, 0 refused"


def test_the_repository_command_exits_3_on_a_refused_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    root = tree(tmp_path)
    document = base()
    document["evidenceLevel"]["intended"] = "PASSED"
    write_run(root, "20260101-example-e1-1", document)
    (root / sorted(PRE_SCHEMA_RECORDS)[0]).unlink()
    monkeypatch.setattr(command, "REPO_ROOT", root)
    assert command.main(["repository"]) == 3
    output = capsys.readouterr().out
    assert "run-pre-schema-record-missing" in output
    assert "value-not-permitted  $.evidenceLevel.intended" in output
    assert "manifests  3: 2 pre-schema, 0 conforming, 1 refused" in output


def test_the_command_exits_4_on_a_failure_no_rule_names(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    def fail(_: Path) -> Any:
        raise RuntimeError("D:\\work\\example")

    monkeypatch.setattr(command, "repository_report", fail)
    assert command.main(["repository"]) == 4
    captured = capsys.readouterr()
    assert captured.err == "FAILED     experiment run: unexpected local failure\n"
    assert "example" not in captured.out + captured.err


@pytest.mark.parametrize("argv", [[], ["check"], ["judge"], ["repository", "x"]])
def test_the_command_exits_2_on_arguments_it_cannot_use(argv: list[str]):
    with pytest.raises(SystemExit) as stopped:
        command.main(argv)
    assert stopped.value.code == 2


def test_the_command_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    root = tree(tmp_path)
    ref = write_run(root, "20260101-example-e1-1", base())

    def snapshot() -> dict[str, bytes | None]:
        return {
            path.relative_to(root).as_posix(): (
                path.read_bytes() if path.is_file() else None
            )
            for path in sorted(root.rglob("*"))
        }

    before = snapshot()
    monkeypatch.setattr(command, "REPO_ROOT", root)
    assert command.main(["repository"]) == 0
    assert command.main(["check", str(root / ref)]) == 0
    assert snapshot() == before
    assert capsys.readouterr().out.count("ok ") == 2


def test_the_check_command_prints_no_line_break_from_a_path():
    assert command._printable("run\nok         forged.json") == (
        "run?ok         forged.json"
    )
    assert command._printable("docs/proof/run.v1alpha1.json") == (
        "docs/proof/run.v1alpha1.json"
    )


# --------------------------------------------------------------------------
# The documents
# --------------------------------------------------------------------------


def test_the_published_field_table_is_the_schema():
    rows = published_table("## Structure")
    published = {backticked(row[0]): row[1] for row in rows}
    expected = {
        path: "yes" if required else "no"
        for path, (_, required) in schema_leaves().items()
    }
    assert published == expected
    assert len(rows) == len(expected) == 47


def test_the_published_semantic_rules_are_the_validators():
    rows = published_table("### Semantic rules")
    assert {backticked(row[0]): row[1] for row in rows} == dict(core.SEMANTIC_RULES)


def test_the_published_repository_rules_are_the_validators():
    rows = published_table("### Rules of reading and of the repository listing")
    assert {backticked(row[0]): row[1] for row in rows} == dict(core.REPOSITORY_RULES)


def test_the_published_structural_matrix_names_a_fixture_for_each_rule():
    rows = published_table("### Structural rules")
    assert {backticked(row[0]) for row in rows} == {
        name for name, rule in RULES.items() if not rule.semantic
    }
    fixtures = manifest()["fixtures"]
    for row in rows:
        rule = RULES[backticked(row[0])]
        assert backticked(row[1]) == rule.code
        if rule.identifier == "contract-structure-invalid":
            assert row[2].startswith("None.")
            continue
        refused_by = {item["rule"] for item in fixtures[backticked(row[2])]["expected"]}
        assert rule.identifier in refused_by, row[2]


def test_the_documents_name_every_fixture():
    document = CONTRACT_DOC.read_text(encoding="utf-8")
    readme = EXAMPLES_README.read_text(encoding="utf-8")
    for path in [*valid_paths(), *invalid_paths()]:
        assert f"{path.parent.name}/{path.name}" in readme, path.name
    for name, entry in manifest()["fixtures"].items():
        assert name in readme
        for item in entry["expected"]:
            if entry["layer"] == "semantic":
                assert f"`{item['rule']}`" in document


def test_the_document_states_the_three_pre_schema_manifests_and_their_digests():
    document = CONTRACT_DOC.read_text(encoding="utf-8")
    for ref, digest in PRE_SCHEMA_RECORDS.items():
        assert ref.removeprefix("docs/proof/experiments/") in document
        assert digest in document


def test_the_package_exports_the_names_of_its_core_module():
    for name in experiment_run.__all__:
        assert getattr(experiment_run, name) is getattr(core, name)
    assert copy.deepcopy(core.load_schema()) == core.load_schema()
    schema = core.load_schema()
    schema["properties"].clear()
    assert core.load_schema()["properties"], "each caller gets its own copy"
