"""The RenderedWorkloadRelease v1alpha1 schema, its fixtures, and what it can hold.

Every check here reads files from this repository and nothing else. No network, no
cluster, no clock, no randomness.

A release records the provenance of one rendered workload release: the workload,
the digests of the contract and binding it came from, the revisions of the renderer
and platform defaults, a release identifier, and the digest of the values it
produced. Five things are asserted that a plain "the fixtures validate" suite would
not catch:

1. **Every identity agrees with the schema it is copied from.** The workload
   identifier, version, environment, and the versions a release can record are held
   to the WorkloadContract's and EnvironmentBinding's own schemas.
2. **The fixtures name what exists.** Each valid fixture's workload and binding are
   committed fixtures, and its release identifier is the one the published rule
   derives.
3. **There is nowhere to put what provenance must not hold** - a timestamp, a
   document's content, a credential field, a cluster resource's status.
4. **Refusals are exactly as published**, by the bare schema as well as the
   validator, and never quote a value from the document.
5. **The gaps are measured.** A random identifier of the right shape and the
   lowercase credential shapes the patterns cannot exclude are asserted to still
   pass, so closing either is a visible change.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from tools.contract_validation import RULES
from tools.contract_validation import validate as validate_workload
from tools.contract_validation.environment_binding import (
    load_schema as load_binding_schema,
)
from tools.contract_validation.environment_binding import (
    validate as validate_binding,
)
from tools.contract_validation.errors import CANONICAL_ERROR_CODES
from tools.contract_validation.rendered_workload_release import (
    SUPPORTED_API_VERSION,
    load_schema,
    validate,
)
from tools.contract_validation.workload import (
    load_schema as load_workload_schema,
)
from tools.contract_validation.workload import (
    looks_like_a_pasted_credential,
)

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "contracts" / "release"
SCHEMA_PATH = CONTRACT_DIR / "rendered-workload-release.v1alpha1.schema.json"
VALID_DIR = CONTRACT_DIR / "examples" / "valid"
INVALID_DIR = CONTRACT_DIR / "examples" / "invalid"
MANIFEST_PATH = INVALID_DIR / "expected-rejections.json"
CONTRACT_DOC = REPO_ROOT / "docs" / "contracts" / "rendered-workload-release.md"

WORKLOAD_VALID_DIR = REPO_ROOT / "contracts" / "workload" / "examples" / "valid"
BINDING_VALID_DIR = REPO_ROOT / "contracts" / "environment" / "examples" / "valid"

EXPECTED_SCHEMA_ID = "https://inferops.io/contracts/release/rendered-workload-release.v1alpha1.schema.json"

#: The top-level members of a release, and all of them. A Kubernetes object would
#: have `spec` and `status`; a release has neither, because nothing reconciles it.
TOP_LEVEL = ["apiVersion", "kind", "metadata", "source", "output"]

#: String fields whose pattern is lowercase hexadecimal of a fixed length.
HEX_FIELDS = frozenset(
    {
        "metadata.releaseId",
        "source.contract.sha256",
        "source.environmentBinding.sha256",
        "source.renderer.revision",
        "source.platformDefaults.revision",
        "output.helmValues.sha256",
    }
)

# Field names that would be a natural home for a secret value. The schema closes
# every object, so a hit here means the schema was loosened, not that a fixture
# drifted. The same list the WorkloadContract and EnvironmentBinding suites apply.
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
    """Follow a local `$ref`, which is the only kind the schema uses."""
    while "$ref" in node:
        ref = node["$ref"]
        assert ref.startswith("#/$defs/"), ref
        node = schema["$defs"][ref.removeprefix("#/$defs/")]
    return node


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


def leaf_schema(schema: dict[str, Any], path: str) -> dict[str, Any]:
    node: dict[str, Any] = schema
    for part in path.split("."):
        node = resolve(schema, resolve(schema, node)["properties"][part])
    return node


def alternatives(schema: dict[str, Any], node: dict[str, Any]) -> list[dict[str, Any]]:
    """A leaf's accepted forms: itself, or each branch of its `oneOf`."""
    if "oneOf" in node:
        return [resolve(schema, branch) for branch in node["oneOf"]]
    return [node]


def string_leaves() -> dict[str, list[dict[str, Any]]]:
    """Every leaf of a release, keyed by dotted path, with its accepted forms."""
    schema = load_schema()
    return {
        path.strip("."): alternatives(schema, leaf_schema(schema, path.strip(".")))
        for path in leaf_paths(schema, schema, "")
    }


def accepts(forms: list[dict[str, Any]], value: str) -> bool:
    """Whether any accepted form of a leaf takes this string, by the schema's words."""
    for form in forms:
        if "pattern" in form:
            if re.search(form["pattern"], value) and len(value) <= form.get(
                "maxLength", len(value)
            ):
                return True
        elif value in form.get("enum", [form.get("const")]):
            return True
    return False


def set_path(document: dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    target = document
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value


def derived_release_id(document: dict[str, Any]) -> str:
    """The release identifier the contract document's rule gives for a release.

    Written out here, from the document's words, rather than imported: no helper
    in the repository computes it yet, and the rule is what the fixtures are held
    to, not an implementation of it.
    """
    identity = {
        "metadata": {
            "workloadId": document["metadata"]["workloadId"],
            "workloadVersion": document["metadata"]["workloadVersion"],
        },
        "source": document["source"],
    }
    canonical = json.dumps(
        identity, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    assert schema["title"] == "RenderedWorkloadRelease v1alpha1"
    assert schema["properties"]["apiVersion"]["const"] == SUPPORTED_API_VERSION
    assert schema["properties"]["kind"]["const"] == "RenderedWorkloadRelease"


def test_every_object_in_the_schema_is_closed():
    """A release has no extension point: an open map is where a secret would land."""
    open_objects = [
        pointer
        for pointer, node in iter_schema_nodes(load_schema())
        if "properties" in node and node.get("additionalProperties") is not False
    ]
    assert open_objects == [], open_objects


def test_every_member_of_every_object_is_required():
    """An input left out is an input nobody can trace the release back to."""
    optional = [
        pointer
        for pointer, node in iter_schema_nodes(load_schema())
        if "properties" in node and set(node["properties"]) != set(node["required"])
    ]
    assert optional == [], optional


def test_every_string_is_constrained_by_a_pattern_or_a_vocabulary():
    """No free text: every string, in every accepted form, is shaped or listed."""
    for path, forms in string_leaves().items():
        for form in forms:
            assert form.get("type") == "string" or "enum" in form or "const" in form
            assert "pattern" in form or "enum" in form or "const" in form, path


def test_the_top_level_is_a_repository_document_not_a_cluster_resource():
    """No `spec` to reconcile and no `status` for a controller to write."""
    assert list(load_schema()["properties"]) == TOP_LEVEL


def test_no_field_is_named_for_a_time():
    """There is no field a timestamp belongs in, so none can be written."""
    names = {
        name
        for _, node in iter_schema_nodes(load_schema())
        for name in node.get("properties", {})
    }
    timely = {
        name
        for name in names
        if re.search(r"(At|Time|time|Date|date|Timestamp|timestamp)$", name)
    }
    assert timely == set(), timely


def test_nothing_in_the_repository_installs_a_release_into_a_cluster():
    """No chart, manifest, or infrastructure file defines or applies one."""
    tracked = subprocess.run(
        ["git", "ls-files", "charts", "deploy", "infra"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert tracked, "git ls-files returned nothing to check"
    mentions = [
        path
        for path in tracked
        if b"RenderedWorkloadRelease" in (REPO_ROOT / path).read_bytes()
    ]
    assert mentions == []


# --------------------------------------------------------------------------
# Agreement with the documents a release names
# --------------------------------------------------------------------------


def test_the_workload_identifier_is_the_contracts():
    ours = load_schema()["$defs"]["dnsLabel"]
    theirs = load_workload_schema()["$defs"]["dnsLabel"]
    for key in ("type", "minLength", "maxLength", "pattern"):
        assert ours[key] == theirs[key], key


def test_the_binding_name_is_the_bindings():
    ours = load_schema()["$defs"]["dnsLabel"]
    theirs = load_binding_schema()["$defs"]["dnsLabel"]
    for key in ("type", "minLength", "maxLength", "pattern"):
        assert ours[key] == theirs[key], key


def test_a_digest_pinned_version_is_accepted_exactly_as_the_contract_accepts_it():
    ours = load_schema()["$defs"]["digestPinnedImageReference"]
    theirs = load_workload_schema()["$defs"]["digestPinnedImageReference"]
    for key in ("type", "maxLength", "pattern"):
        assert ours[key] == theirs[key], key


def test_the_semantic_version_is_the_contracts_without_uppercase():
    """Narrower on purpose, by exactly the uppercase letters and nothing else."""
    ours = load_schema()["$defs"]["lowercaseSemanticVersion"]["pattern"]
    theirs = load_workload_schema()["$defs"]["semanticVersion"]["pattern"]
    assert "A-Z" not in ours
    assert ours == theirs.replace("a-zA-Z", "a-z")


@pytest.mark.parametrize(
    "path", sorted(WORKLOAD_VALID_DIR.glob("*.yaml")), ids=lambda p: p.name
)
def test_every_committed_contract_version_can_be_recorded(path: Path):
    """The narrowing refuses no version a committed contract fixture uses."""
    release = load_document(VALID_DIR / "support-assistant-local-kind.yaml")
    release["metadata"]["workloadVersion"] = load_document(path)["metadata"]["version"]
    assert validate(release) == []


def test_an_uppercase_contract_version_cannot_be_recorded():
    """The cost of the narrowing, measured: the contract takes it, a release does not."""
    contract = load_document(WORKLOAD_VALID_DIR / "synchronous-llm-local.yaml")
    contract["metadata"]["version"] = "1.0.0-RC.1"
    assert validate_workload(contract) == []
    release = load_document(VALID_DIR / "support-assistant-local-kind.yaml")
    release["metadata"]["workloadVersion"] = "1.0.0-RC.1"
    assert as_tuples(validate(release)) == [
        ("contract-invalid", "value-not-permitted", "$.metadata.workloadVersion")
    ]


def test_the_contract_versions_a_release_records_are_the_contracts():
    ours = load_schema()["$defs"]["contractReference"]["properties"]["apiVersion"]
    assert ours["enum"] == [load_workload_schema()["properties"]["apiVersion"]["const"]]


def test_the_binding_versions_a_release_records_are_the_bindings():
    ours = load_schema()["$defs"]["environmentBindingReference"]["properties"]
    assert ours["apiVersion"]["enum"] == [
        load_binding_schema()["properties"]["apiVersion"]["const"]
    ]


def test_the_environment_vocabulary_is_the_bindings_and_the_contracts():
    ours = load_schema()["$defs"]["environmentBindingReference"]["properties"]
    binding = load_binding_schema()["$defs"]["spec"]["properties"]["environment"]
    workload = load_workload_schema()["$defs"]["spec"]["properties"]["environment"]
    assert ours["environment"]["enum"] == binding["enum"] == workload["enum"]


def test_the_published_field_table_is_the_schema():
    """Every field the document says a release records, and every one it has."""
    schema = load_schema()
    rows = published_table("**What a release records.**")
    published = [backticked(row[0]) for row in rows]
    in_schema = [
        path.strip(".")
        for path in leaf_paths(schema, schema, "")
        if path.strip(".") not in ("apiVersion", "kind")
    ]
    assert sorted(published) == sorted(in_schema)


def test_a_workload_contract_is_not_a_release():
    """No other schema's documents are accepted, so none can be misread as one."""
    for path in sorted(WORKLOAD_VALID_DIR.glob("*.yaml")):
        assert validate(load_document(path)), path.name


def test_a_binding_is_not_a_release():
    for path in sorted(BINDING_VALID_DIR.glob("*.yaml")):
        assert validate(load_document(path)), path.name


def test_a_release_is_neither_a_contract_nor_a_binding():
    for path in valid_paths():
        assert validate_workload(load_document(path)), path.name
        assert validate_binding(load_document(path)), path.name


# --------------------------------------------------------------------------
# Valid fixtures
# --------------------------------------------------------------------------


def test_the_valid_fixtures_are_the_two_published():
    assert [p.name for p in valid_paths()] == [
        "support-assistant-local-docker-desktop.yaml",
        "support-assistant-local-kind.yaml",
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
def test_valid_fixture_is_named_after_its_workload_and_binding(path: Path):
    document = load_document(path)
    workload = document["metadata"]["workloadId"]
    binding = document["source"]["environmentBinding"]["name"]
    assert path.stem == f"{workload}-{binding}"


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_valid_fixture_carries_no_field_that_could_hold_a_secret(path: Path):
    hits = [
        where
        for where, key, _ in walk(load_document(path))
        if key is not None and key.lower() in FORBIDDEN_SECRET_KEYS
    ]
    assert hits == [], hits


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_valid_fixture_names_a_committed_contract_and_binding(path: Path):
    """The identities are real ones, and the two documents serve one environment."""
    document = load_document(path)
    reference = document["source"]["environmentBinding"]
    identity = (
        document["metadata"]["workloadId"],
        document["metadata"]["workloadVersion"],
    )
    contracts = [load_document(p) for p in sorted(WORKLOAD_VALID_DIR.glob("*.yaml"))]
    named = [
        c
        for c in contracts
        if (c["metadata"]["name"], c["metadata"]["version"]) == identity
    ]
    assert len(named) == 1, path.name
    bindings = {
        (b["spec"]["environment"], b["metadata"]["name"])
        for b in (load_document(p) for p in sorted(BINDING_VALID_DIR.glob("*.yaml")))
    }
    assert (reference["environment"], reference["name"]) in bindings
    assert named[0]["spec"]["environment"] == reference["environment"]


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_valid_fixture_carries_the_release_id_its_inputs_derive(path: Path):
    document = load_document(path)
    assert document["metadata"]["releaseId"] == derived_release_id(document)


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_valid_fixture_digests_and_revisions_name_nothing(path: Path):
    """The README says each is a repeated character, so a reader cannot mistake one."""
    document = load_document(path)
    for field in HEX_FIELDS - {"metadata.releaseId"}:
        node: Any = document
        for key in field.split("."):
            node = node[key]
        assert len(set(node)) == 1, (path.name, field)


def test_valid_fixtures_have_distinct_release_ids():
    ids = [load_document(p)["metadata"]["releaseId"] for p in valid_paths()]
    assert len(set(ids)) == len(ids)


# --------------------------------------------------------------------------
# Invalid fixtures, refused exactly as published
# --------------------------------------------------------------------------


def test_every_invalid_fixture_is_in_the_manifest_and_the_reverse():
    assert {p.name for p in invalid_paths()} == set(manifest()["fixtures"])


def test_the_invalid_fixtures_are_the_fifteen_published():
    assert len(invalid_paths()) == 15


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
    """Every release rule is structural, so a raw-schema consumer loses nothing."""
    assert manifest()["fixtures"][path.name]["layer"] == "structural"
    assert list(raw_validator().iter_errors(load_document(path)))


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_refusal_is_repeatable_and_non_retryable(path: Path):
    document = load_document(path)
    runs = [as_tuples(validate(document)) for _ in range(5)]
    assert all(run == runs[0] for run in runs)
    assert all(found.retryable is False for found in validate(document))


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


def test_the_rule_matrix_is_every_rule_a_release_can_cite():
    """Every structural rule, and no semantic one: the release has no such layer."""
    rows = published_table(
        "The table below is every rule a release can be refused under."
    )
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
    assert "Two valid and fifteen invalid fixtures" in text
    assert len(valid_paths()) == 2
    assert len(invalid_paths()) == 15


# --------------------------------------------------------------------------
# Time and randomness: what the patterns exclude, and the gap they leave
# --------------------------------------------------------------------------

#: Timestamps in the forms a renderer would write one. The first two are RFC 3339.
TIMESTAMPS = [
    "2026-09-29T10:15:00Z",
    "2026-09-29T10:15:00+00:00",
    "Tue, 29 Sep 2026 10:15:00 GMT",
]


@pytest.mark.parametrize("stamp", TIMESTAMPS)
def test_no_string_field_accepts_a_timestamp(stamp: str):
    for path, forms in string_leaves().items():
        assert not accepts(forms, stamp), path


def test_a_random_uuid_is_not_a_release_id():
    forms = string_leaves()["metadata.releaseId"]
    assert not accepts(forms, "3f2c9a1e-7b4d-4e8a-9c61-0d5e2f8a4b17")
    assert not accepts(forms, "3f2c9a1e7b4d4e8a9c610d5e2f8a4b17")


def test_a_release_id_that_was_not_derived_still_passes():
    """The documented gap: shape is checked, derivation is not. Closing it comes here."""
    document = load_document(VALID_DIR / "support-assistant-local-kind.yaml")
    underived = "0123456789abcdef" * 4
    assert underived != derived_release_id(document)
    document["metadata"]["releaseId"] = underived
    assert validate(document) == []


# --------------------------------------------------------------------------
# Secrets: what the patterns exclude, and the gap they leave
# --------------------------------------------------------------------------

#: Credential shapes every string field in a release refuses, in every accepted
#: form. Each is a vendor's published placeholder, an all-zero synthetic, or the
#: public JWT header.
EXCLUDED_SHAPES = [
    "AKIAIOSFODNN7EXAMPLE",
    "ghp_0000000000000000000000000000000000",
    "github_pat_00000000000000000000000000",
    "hf_000000000000000000000000000000000000",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
    "Zx4Kq9TbLm2Rd7Wf1Hs3Nv8Yc6Ej0Pa",
    "token = placeholder",
    "0.1.0-AKIAIOSFODNN7EXAMPLE",
]


@pytest.mark.parametrize("shape", EXCLUDED_SHAPES, ids=lambda s: s[:16])
def test_no_string_field_accepts_an_excluded_credential_shape(shape: str):
    for path, forms in string_leaves().items():
        assert not accepts(forms, shape), path


#: Lowercase credential shapes the patterns cannot exclude, placed in every field
#: that accepts them. Each is an all-zero synthetic of a published format.
LOWERCASE_SHAPES = [
    "sk-000000000000000000000000000000000000",
    "glpat-00000000000000000000",
    "gldt-00000000000000000000",
    "xoxb-000000000000-000000000000-000000",
]

#: Where each lowercase shape lands, and whether the WorkloadContract's credential
#: heuristic - which the release does not apply - would see it there. The heuristic
#: tests for a published prefix at the start of the value, so it sees a shape that
#: begins a field and misses one behind a version's pre-release separator.
GAP_PLACEMENTS: dict[str, tuple[str, bool]] = {
    "metadata.workloadId": ("{}", True),
    "metadata.workloadVersion": ("0.1.0-{}", False),
    "source.environmentBinding.name": ("{}", True),
    "output.helmValues.path": ("{}.yaml", True),
}


@pytest.mark.parametrize("shape", LOWERCASE_SHAPES, ids=lambda s: s[:8])
@pytest.mark.parametrize("field", sorted(GAP_PLACEMENTS))
def test_the_documented_gap_is_a_gap(field: str, shape: str):
    """The release has no semantic layer, so these pass. Closing it comes here."""
    template, heuristic_sees_it = GAP_PLACEMENTS[field]
    document = load_document(VALID_DIR / "support-assistant-local-docker-desktop.yaml")
    value = template.format(shape)
    set_path(document, field, value)
    assert validate(document) == [], field
    caught = looks_like_a_pasted_credential(value) is not None
    assert caught is heuristic_sees_it, (field, shape)


@pytest.mark.parametrize("shape", LOWERCASE_SHAPES, ids=lambda s: s[:8])
@pytest.mark.parametrize("field", sorted(HEX_FIELDS))
def test_no_hexadecimal_field_accepts_a_lowercase_credential_shape(
    field: str, shape: str
):
    assert not accepts(string_leaves()[field], shape)


def test_every_patterned_field_is_measured():
    """Each patterned field is a gap placement or a hexadecimal one, never neither."""
    patterned = {
        path
        for path, forms in string_leaves().items()
        if any("pattern" in form for form in forms)
    }
    assert patterned == set(GAP_PLACEMENTS) | HEX_FIELDS
    assert set(GAP_PLACEMENTS).isdisjoint(HEX_FIELDS)


def test_the_document_states_the_gap_it_measures():
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    for shape in LOWERCASE_SHAPES:
        assert f"`{shape.split('-')[0]}-`" in text, shape
