"""The EnvironmentBinding v1alpha1 schema, its fixtures, and its ownership boundary.

Every check here reads files from this repository and nothing else. No network, no
cluster, no clock, no randomness.

A binding carries the facts one environment supplies to a release that are not the
workload's intent. Four things are asserted that a plain "the fixtures validate"
suite would not catch:

1. **The boundary with the WorkloadContract is structural.** No property under a
   binding's `spec` is one a contract's `spec` defines, other than the shared
   `environment` key, and both published ownership tables agree with the schemas.
2. **The fixtures describe the environment that exists.** Each valid fixture's
   namespace, claim, provider, and replica bounds are compared with the records
   that own those values, so a fixture cannot drift into describing somewhere else.
3. **Refusals are exactly as published**, by the bare schema as well as the
   validator, and never quote a value from the document.
4. **The credential gap is measured.** The lowercase shapes the patterns cannot
   exclude are asserted to still pass, so closing the gap is a visible change.
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

from tools.contract_validation import RULES
from tools.contract_validation import validate as validate_workload
from tools.contract_validation.environment_binding import (
    SUPPORTED_API_VERSION,
    load_schema,
    validate,
)
from tools.contract_validation.errors import CANONICAL_ERROR_CODES
from tools.contract_validation.workload import (
    load_schema as load_workload_schema,
)
from tools.contract_validation.workload import (
    looks_like_a_pasted_credential,
)

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "contracts" / "environment"
SCHEMA_PATH = CONTRACT_DIR / "environment-binding.v1alpha1.schema.json"
VALID_DIR = CONTRACT_DIR / "examples" / "valid"
INVALID_DIR = CONTRACT_DIR / "examples" / "invalid"
MANIFEST_PATH = INVALID_DIR / "expected-rejections.json"
CONTRACT_DOC = REPO_ROOT / "docs" / "contracts" / "environment-binding.md"

WORKLOAD_DIR = REPO_ROOT / "contracts" / "workload" / "examples"

# The records each valid fixture copies a value from.
LIFECYCLE_LIB = REPO_ROOT / "scripts" / "environment" / "lib.sh"
TERRAFORM_VARIABLES = (
    REPO_ROOT / "infra" / "terraform" / "environments" / "local" / "variables.tf"
)
CHART_SCHEMA = REPO_ROOT / "charts" / "inferops-llm" / "values.schema.json"
CHART_REAL_VALUES = REPO_ROOT / "charts" / "inferops-llm" / "ci" / "real-values.yaml"
PROVIDER_CONTRACT = (
    REPO_ROOT / "docs" / "environment" / "local-cluster-provider-contract.v1alpha1.json"
)

EXPECTED_SCHEMA_ID = (
    "https://inferops.io/contracts/environment/environment-binding.v1alpha1.schema.json"
)

#: The one property name a binding's spec and a contract's spec may both define.
#: It is the key a binding is matched on, not a second copy of a contract value.
SHARED_KEY = "environment"

# Field names that would be a natural home for a secret value. The schema closes
# every object, so a hit here means the schema was loosened, not that a fixture
# drifted. The same list the WorkloadContract suite applies to its fixtures.
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
        "kubeconfig",
    }
)


def load_document(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def manifest() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return document


def valid_paths() -> list[Path]:
    return sorted(VALID_DIR.glob("*.yaml"))


def invalid_paths() -> list[Path]:
    return sorted(INVALID_DIR.glob("*.yaml"))


def raw_validator() -> Draft202012Validator:
    """What a consumer holding only the schema file has."""
    return Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def as_tuples(findings: Any) -> list[tuple[str, str, str]]:
    return [(f.code, f.rule, f.field) for f in findings]


def walk(node: Any, path: str = "$") -> Iterator[tuple[str, str | None, Any]]:
    """Yield every (path, key, value) triple in a document."""
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


def iter_schema_nodes(node: Any, pointer: str = "#") -> Iterator[tuple[str, dict]]:
    if isinstance(node, dict):
        yield pointer, node
        for key, value in node.items():
            yield from iter_schema_nodes(value, f"{pointer}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_schema_nodes(value, f"{pointer}/{index}")


def resolve(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    """Follow a local `$ref`, which is the only kind either schema uses."""
    while "$ref" in node:
        ref = node["$ref"]
        assert ref.startswith("#/$defs/"), ref
        node = schema["$defs"][ref.removeprefix("#/$defs/")]
    return node


def property_names_under(schema: dict[str, Any], node: dict[str, Any]) -> set[str]:
    """Every property name reachable from a schema node, through refs and allOf."""
    names: set[str] = set()
    pending = [node]
    seen: set[int] = set()
    while pending:
        current = resolve(schema, pending.pop())
        if id(current) in seen:
            continue
        seen.add(id(current))
        for name, child in current.get("properties", {}).items():
            names.add(name)
            if isinstance(child, dict):
                pending.append(child)
        for branch in current.get("allOf", []):
            for part in ("if", "then", "else"):
                if part in branch:
                    pending.append(branch[part])
    return names


def leaf_paths(schema: dict[str, Any], node: dict[str, Any], prefix: str) -> list[str]:
    """Dotted paths to every property that has no properties of its own."""
    node = resolve(schema, node)
    children = node.get("properties")
    if not children:
        return [prefix]
    paths: list[str] = []
    for name, child in children.items():
        paths.extend(leaf_paths(schema, child, f"{prefix}.{name}"))
    return paths


def string_leaf_schemas(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every string-valued leaf of a binding, resolved, keyed by dotted path."""
    leaves: dict[str, dict[str, Any]] = {}
    for path in leaf_paths(schema, schema, ""):
        node: dict[str, Any] = schema
        for part in path.strip(".").split("."):
            node = resolve(schema, resolve(schema, node)["properties"][part])
        if node.get("type") == "string" or "enum" in node or "const" in node:
            leaves[path.strip(".")] = node
    return leaves


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
    Draft202012Validator.check_schema(load_schema())


def test_schema_declares_its_dialect_identifier_version_and_kind():
    schema = load_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == EXPECTED_SCHEMA_ID
    assert schema["title"] == "EnvironmentBinding v1alpha1"
    assert schema["properties"]["apiVersion"]["const"] == SUPPORTED_API_VERSION
    assert schema["properties"]["kind"]["const"] == "EnvironmentBinding"


def test_every_object_in_the_schema_is_closed():
    """Stricter than the WorkloadContract's rule, which only asks for a policy.

    A binding has no extension point: an open map anywhere in it would be both a
    place a credential could land and a place a workload value could hide.
    """
    open_objects = [
        pointer
        for pointer, node in iter_schema_nodes(load_schema())
        if "properties" in node and node.get("additionalProperties") is not False
    ]
    assert open_objects == [], open_objects


def test_every_member_of_every_object_is_required():
    """A fact left out is a fact somebody else supplies silently."""
    optional = [
        pointer
        for pointer, node in iter_schema_nodes(load_schema())
        if "properties" in node and set(node["properties"]) != set(node["required"])
    ]
    assert optional == [], optional


def test_every_string_is_constrained_by_a_pattern_or_a_vocabulary():
    """No free text: every string is an identifier, a path, or a listed value."""
    for path, node in string_leaf_schemas(load_schema()).items():
        assert "pattern" in node or "enum" in node or "const" in node, path


# --------------------------------------------------------------------------
# The ownership boundary with the WorkloadContract
# --------------------------------------------------------------------------


def test_no_binding_field_is_a_field_the_workload_contract_owns():
    """The override the binding exists to make impossible, checked on the schemas.

    Property names are compared over the whole of both `spec` trees, through every
    reference and conditional branch, so a workload field cannot be reintroduced by
    nesting it one level deeper or under a differently named block.
    """
    binding = load_schema()
    workload = load_workload_schema()
    binding_names = property_names_under(binding, binding["$defs"]["spec"])
    workload_names = property_names_under(workload, workload["$defs"]["spec"])
    assert binding_names & workload_names == {SHARED_KEY}


def test_the_shared_key_has_the_same_vocabulary_in_both_schemas():
    binding = load_schema()["$defs"]["spec"]["properties"][SHARED_KEY]
    workload = load_workload_schema()["$defs"]["spec"]["properties"][SHARED_KEY]
    assert binding["enum"] == workload["enum"]


def test_the_published_binding_ownership_table_is_the_schema():
    """Every binding field in the document's table, and every one in the schema."""
    schema = load_schema()
    rows = published_table("**A binding owns environment facts.**")
    published = [backticked(row[0]) for row in rows]
    in_schema = [
        path.lstrip(".")
        for path in leaf_paths(schema, schema["$defs"]["spec"], ".spec")
    ]
    assert sorted(published) == sorted(in_schema)


def test_the_published_workload_ownership_table_is_the_workload_schema():
    """Every contract `spec` member named as off limits, and absent from a binding."""
    rows = published_table("**A binding may not carry workload intent.**")
    published = {backticked(row[0]).removeprefix("spec.") for row in rows}
    workload_spec = load_workload_schema()["$defs"]["spec"]["properties"]
    assert published == set(workload_spec) - {SHARED_KEY}
    binding_spec = load_schema()["$defs"]["spec"]["properties"]
    assert published.isdisjoint(binding_spec)


def test_a_workload_contract_is_not_a_binding():
    """Neither schema accepts the other's documents, so neither can be misread."""
    for path in sorted((WORKLOAD_DIR / "valid").glob("*.yaml")):
        assert validate(load_document(path)), path.name


def test_a_binding_is_not_a_workload_contract():
    for path in valid_paths():
        assert validate_workload(load_document(path)), path.name


# --------------------------------------------------------------------------
# Valid fixtures
# --------------------------------------------------------------------------


def test_the_valid_fixtures_are_the_two_published():
    assert [p.name for p in valid_paths()] == [
        "local-docker-desktop.yaml",
        "local-kind.yaml",
    ]


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_valid_fixture_validates(path: Path):
    document = load_document(path)
    assert list(raw_validator().iter_errors(document)) == []
    findings = validate(document)
    assert findings == [], "\n".join(f"{f.field}: {f.rule}" for f in findings)


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_valid_fixture_is_json_representable(path: Path):
    document = load_document(path)
    assert json.loads(json.dumps(document)) == document
    for _, key, _ in walk(document):
        if key is not None:
            assert isinstance(key, str), f"non-string key in {path.name}: {key!r}"


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_valid_fixture_is_named_after_its_binding(path: Path):
    assert load_document(path)["metadata"]["name"] == path.stem


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_valid_fixture_carries_no_field_that_could_hold_a_secret(path: Path):
    hits = [
        where
        for where, key, _ in walk(load_document(path))
        if key is not None and key.lower() in FORBIDDEN_SECRET_KEYS
    ]
    assert hits == [], hits


def test_valid_fixtures_have_distinct_identities_and_destinations():
    documents = [load_document(path) for path in valid_paths()]
    identities = [(d["spec"]["environment"], d["metadata"]["name"]) for d in documents]
    destinations = [d["spec"]["gitops"]["destinationPath"] for d in documents]
    assert len(set(identities)) == len(identities)
    assert len(set(destinations)) == len(destinations)


def test_the_valid_fixtures_bind_only_the_environment_this_project_has_run():
    """`local` is the only environment any record describes a run in."""
    for path in valid_paths():
        assert load_document(path)["spec"]["environment"] == "local", path.name


# --------------------------------------------------------------------------
# The valid fixtures describe the environment that exists
# --------------------------------------------------------------------------


def terraform_default(variable: str) -> str:
    text = TERRAFORM_VARIABLES.read_text(encoding="utf-8")
    block = re.search(
        rf'variable "{variable}" \{{(?P<body>.*?)\n\}}', text, flags=re.DOTALL
    )
    assert block, variable
    default = re.search(r'default\s*=\s*"(?P<value>[^"]*)"', block.group("body"))
    assert default, variable
    return default.group("value")


def release_namespace() -> str:
    text = LIFECYCLE_LIB.read_text(encoding="utf-8")
    match = re.search(r'^readonly INFEROPS_RELEASE_NAMESPACE="([^"]+)"$', text, re.M)
    assert match
    return match.group(1)


def provider_ids() -> list[str]:
    contract = json.loads(PROVIDER_CONTRACT.read_text(encoding="utf-8"))
    return [provider["providerId"] for provider in contract["providers"]]


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_fixture_namespace_is_the_one_the_release_lifecycle_installs_into(path: Path):
    namespace = load_document(path)["spec"]["destination"]["namespace"]
    assert namespace == release_namespace()
    assert namespace == terraform_default("namespace")


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_fixture_claim_is_the_one_the_prerequisite_layer_creates(path: Path):
    claim = load_document(path)["spec"]["modelCache"]["claimName"]
    assert claim == terraform_default("model_cache_claim_name")
    real_values = load_document(CHART_REAL_VALUES)
    assert claim == real_values["model"]["cache"]["claimName"]


def test_the_provider_vocabulary_is_the_provider_contracts():
    """Both directions: a provider the contract drops is a provider bindings lose."""
    destination = load_schema()["$defs"]["destination"]["properties"]
    assert destination["clusterProvider"]["enum"] == provider_ids()


def test_the_api_replica_bounds_are_the_charts():
    chart = json.loads(CHART_SCHEMA.read_text(encoding="utf-8"))
    chart_bounds = chart["properties"]["api"]["properties"]["replicaCount"]
    ours = load_schema()["$defs"]["platform"]["properties"]["apiReplicas"]
    assert (ours["type"], ours["minimum"], ours["maximum"]) == (
        chart_bounds["type"],
        chart_bounds["minimum"],
        chart_bounds["maximum"],
    )


def test_the_namespace_pattern_carries_the_prefix_the_chart_checks():
    pattern = load_schema()["$defs"]["releaseNamespace"]["pattern"]
    assert pattern.startswith("^inferops-")
    values = CHART_REAL_VALUES.parent.parent / "values.yaml"
    assert "namespacePrefixCheck: true" in values.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Invalid fixtures, refused exactly as published
# --------------------------------------------------------------------------


def test_every_invalid_fixture_is_in_the_manifest_and_the_reverse():
    assert {p.name for p in invalid_paths()} == set(manifest()["fixtures"])


def test_the_invalid_fixtures_are_the_eleven_published():
    assert len(invalid_paths()) == 11


def test_every_expected_rule_is_registered_with_its_code():
    for name, entry in manifest()["fixtures"].items():
        assert entry["layer"] in manifest()["layers"], name
        for expected in entry["expected"]:
            assert expected["rule"] in RULES, f"{name}: {expected['rule']}"
            assert RULES[expected["rule"]].code == expected["code"], name
            assert expected["code"] in CANONICAL_ERROR_CODES, name


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_invalid_fixture_is_refused_for_exactly_the_published_reasons(path: Path):
    entry = manifest()["fixtures"][path.name]
    expected = [(e["code"], e["rule"], e["field"]) for e in entry["expected"]]
    assert as_tuples(validate(load_document(path))) == expected


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_the_bare_schema_refuses_every_invalid_fixture(path: Path):
    """Every binding rule is structural, so a raw-schema consumer loses nothing."""
    assert manifest()["fixtures"][path.name]["layer"] == "structural"
    assert list(raw_validator().iter_errors(load_document(path)))


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_refusal_is_repeatable_and_non_retryable(path: Path):
    document = load_document(path)
    runs = [as_tuples(validate(document)) for _ in range(5)]
    assert all(run == runs[0] for run in runs)
    assert all(found.retryable is False for found in validate(document))


def test_the_workload_intent_fixture_names_every_field_it_tried_to_own():
    fields = {
        f.field
        for f in validate(
            load_document(INVALID_DIR / "workload-intent-in-binding.yaml")
        )
    }
    assert fields == {
        "$.spec.model",
        "$.spec.scaling",
        "$.spec.platform.runtimeReplicas",
    }
    assert all(
        f.rule == "field-unknown"
        for f in validate(
            load_document(INVALID_DIR / "workload-intent-in-binding.yaml")
        )
    )


def scalar_strings(node: Any) -> list[str]:
    if isinstance(node, dict):
        return [s for value in node.values() for s in scalar_strings(value)]
    if isinstance(node, list):
        return [s for value in node for s in scalar_strings(value)]
    if isinstance(node, str):
        return [node]
    return []


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_no_finding_quotes_a_value_from_the_document(path: Path):
    """A refusal says what was wrong, never what the value was."""
    document = load_document(path)
    vocabulary = set(scalar_strings(load_schema()))
    values = [
        s for s in scalar_strings(document) if len(s) >= 8 and s not in vocabulary
    ]
    rendered = json.dumps([f.as_dict() for f in validate(document)])
    for value in values:
        assert value not in rendered, f"{path.name} echoed a document value"


# --------------------------------------------------------------------------
# The published rule matrix
# --------------------------------------------------------------------------


def test_the_rule_matrix_is_every_rule_a_binding_can_cite():
    """Every structural rule, and no semantic one: the binding has no such layer."""
    rows = published_table("the table below is the single-document one.")
    published = {backticked(row[0]): (backticked(row[1]), row[2]) for row in rows}
    structural = {
        identifier: (rule.code, "Structural")
        for identifier, rule in RULES.items()
        if not rule.semantic
    }
    assert published == structural


def test_the_only_structural_rule_without_a_fixture_is_the_fallback():
    exercised = {
        expected["rule"]
        for entry in manifest()["fixtures"].values()
        for expected in entry["expected"]
    }
    structural = {i for i, rule in RULES.items() if not rule.semantic}
    assert structural - exercised == {"contract-structure-invalid"}
    assert exercised <= structural


def test_the_document_counts_the_fixtures_it_publishes():
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    assert "Two valid and eleven invalid fixtures" in text
    assert len(valid_paths()) == 2
    assert len(invalid_paths()) == 11


# --------------------------------------------------------------------------
# Secrets: what the patterns exclude, and the gap they leave
# --------------------------------------------------------------------------

#: Credential shapes every string pattern in a binding refuses. Each is a vendor's
#: published placeholder, an all-zero synthetic, or the public JWT header.
EXCLUDED_SHAPES = [
    "AKIAIOSFODNN7EXAMPLE",
    "ghp_0000000000000000000000000000000000",
    "github_pat_00000000000000000000000000",
    "hf_000000000000000000000000000000000000",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
    "Zx4Kq9TbLm2Rd7Wf1Hs3Nv8Yc6Ej0Pa",
    "token = placeholder",
]


@pytest.mark.parametrize("shape", EXCLUDED_SHAPES, ids=lambda s: s[:16])
def test_no_string_field_accepts_an_excluded_credential_shape(shape: str):
    for path, node in string_leaf_schemas(load_schema()).items():
        if "pattern" in node:
            assert not re.search(node["pattern"], shape), path
        else:
            assert shape not in node.get("enum", [node.get("const")]), path


#: Lowercase credential shapes the patterns cannot exclude, placed in every field
#: that accepts them. Each is an all-zero synthetic of a published format.
LOWERCASE_SHAPES = [
    "sk-000000000000000000000000000000000000",
    "glpat-00000000000000000000",
    "gldt-00000000000000000000",
    "xoxb-000000000000-000000000000-000000",
]

#: Where each lowercase shape lands, and whether the WorkloadContract's credential
#: heuristic - which the binding does not apply - would see it there. The heuristic
#: tests for a published prefix at the start of the value, so it sees a shape that
#: begins a field and misses one inside a path or behind the namespace's prefix.
GAP_PLACEMENTS: dict[str, tuple[tuple[str, ...], str, bool]] = {
    "metadata.name": (("metadata", "name"), "{}", True),
    "metadata.owner": (("metadata", "owner"), "{}", True),
    "spec.modelCache.claimName": (("spec", "modelCache", "claimName"), "{}", True),
    "spec.gitops.destinationPath": (
        ("spec", "gitops", "destinationPath"),
        "gitops/environments/{}",
        False,
    ),
    "spec.destination.namespace": (
        ("spec", "destination", "namespace"),
        "inferops-{}",
        False,
    ),
}


@pytest.mark.parametrize("shape", LOWERCASE_SHAPES, ids=lambda s: s[:8])
@pytest.mark.parametrize("field", sorted(GAP_PLACEMENTS))
def test_the_documented_gap_is_a_gap(field: str, shape: str):
    """The binding has no semantic layer, so these pass. Closing it comes here."""
    keys, template, heuristic_sees_it = GAP_PLACEMENTS[field]
    document = load_document(VALID_DIR / "local-docker-desktop.yaml")
    target = document
    for key in keys[:-1]:
        target = target[key]
    value = template.format(shape)
    target[keys[-1]] = value
    assert validate(document) == [], field
    caught = looks_like_a_pasted_credential(value) is not None
    assert caught is heuristic_sees_it, (field, shape)


def test_the_gap_fields_are_every_free_string_in_a_binding():
    """Every patterned string field is measured above, so none is left unmeasured."""
    patterned = {
        path
        for path, node in string_leaf_schemas(load_schema()).items()
        if "pattern" in node
    }
    assert patterned == set(GAP_PLACEMENTS)


def test_the_document_states_the_gap_it_measures():
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    for shape in LOWERCASE_SHAPES:
        assert f"`{shape.split('-')[0]}-`" in text, shape
