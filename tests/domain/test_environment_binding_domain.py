"""The EnvironmentBinding domain: typed parsing, the set rules, and selection.

Every check reads files from this repository and nothing else. No network, no
cluster, no clock, no randomness.

Five things are asserted:

1. **The domain's copy of the schema is the schema.** Every vocabulary, pattern,
   length, bound, and field list the parser applies is compared with
   `contracts/environment/environment-binding.v1alpha1.schema.json`.
2. **The parser and the published validator agree on every committed fixture.**
   Each valid fixture parses and rebuilds to the document it came from; each
   invalid one is refused, with the canonical code the manifest publishes, at a
   field the manifest names or at the object that holds it.
3. **The binding cannot own or override WorkloadContract semantics.** No attribute
   or wire name in a binding's tree is one a contract's `spec` tree uses, other
   than `environment`, which is the contract's own type; selection returns one of
   the bindings it was given, unchanged, and leaves the contract unchanged.
4. **Conflicting, missing, and ambiguous bindings fail canonically**, under the
   published rule identifiers, with every reason at once, sorted, non-retryable,
   and without repeating a value from a document.
5. **The published rule table is the code's**, adds no canonical code, and reuses
   no identifier the offline validator already means something else by.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import json
import re
import sys
from pathlib import Path
from typing import Any, get_type_hints

import pytest
import yaml

from inferops.domain import RequestContext
from inferops.domain.environment import (
    API_REPLICAS_CEILING,
    API_REPLICAS_FLOOR,
    BINDING_RULES,
    ENVIRONMENT_BINDING_KIND,
    SUPPORTED_BINDING_VERSIONS,
    BindingRefusal,
    BindingSelectionError,
    BindingVersion,
    ClusterProvider,
    EnvironmentBinding,
    EnvironmentBindingError,
    GitOpsPath,
    MalformedEnvironmentBindingError,
    ModelCacheClass,
    PlatformSettings,
    ReleaseNamespace,
    UnsupportedBindingVersionError,
    is_supported_binding_version,
    parse_environment_binding,
    select_environment_binding,
    validate_environment_bindings,
)
from inferops.domain.environment.parsing import (
    _DESTINATION_FIELDS,
    _GITOPS_FIELDS,
    _METADATA_FIELDS,
    _MODEL_CACHE_FIELDS,
    _PLATFORM_FIELDS,
    _ROOT_FIELDS,
    _SPEC_FIELDS,
)
from inferops.domain.workload import (
    SUPPORTED_CONTRACT_VERSIONS,
    ConstrainedString,
    DnsLabel,
    Environment,
    WorkloadContract,
    parse_workload_contract,
)
from inferops.domain.workload.errors import InvalidValueError
from tools.contract_validation import RULES
from tools.contract_validation.environment_binding import validate as validate_tool
from tools.contract_validation.errors import CANONICAL_ERROR_CODES

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "environment" / "environment-binding.v1alpha1.schema.json"
)
EXAMPLES = REPO_ROOT / "contracts" / "environment" / "examples"
VALID_DIR = EXAMPLES / "valid"
INVALID_DIR = EXAMPLES / "invalid"
MANIFEST_PATH = INVALID_DIR / "expected-rejections.json"
WORKLOAD_VALID_DIR = REPO_ROOT / "contracts" / "workload" / "examples" / "valid"
CONTRACT_DOC = REPO_ROOT / "docs" / "contracts" / "environment-binding.md"
PACKAGE_DIR = REPO_ROOT / "src" / "inferops" / "domain" / "environment"

#: The one name a binding's spec tree and a contract's spec tree may share.
SHARED_KEY = "environment"


def load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def schema() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return document


def manifest() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return document


def valid_paths() -> list[Path]:
    return sorted(VALID_DIR.glob("*.yaml"))


def invalid_paths() -> list[Path]:
    return sorted(INVALID_DIR.glob("*.yaml"))


def binding(name: str) -> EnvironmentBinding:
    return parse_environment_binding(load(VALID_DIR / f"{name}.yaml"))


def contract(name: str) -> WorkloadContract:
    return parse_workload_contract(load(WORKLOAD_VALID_DIR / f"{name}.yaml"))


def variant(
    base: str = "local-kind",
    *,
    name: str | None = None,
    environment: str | None = None,
    path: str | None = None,
) -> EnvironmentBinding:
    """A valid fixture with its identity or destination changed, then parsed."""
    document = load(VALID_DIR / f"{base}.yaml")
    if name is not None:
        document["metadata"]["name"] = name
    if environment is not None:
        document["spec"]["environment"] = environment
    if path is not None:
        document["spec"]["gitops"]["destinationPath"] = path
    return parse_environment_binding(document)


def defs(name: str) -> dict[str, Any]:
    node: dict[str, Any] = schema()["$defs"][name]
    return node


# --------------------------------------------------------------------------
# 1. The domain's copy of the schema is the schema
# --------------------------------------------------------------------------


def test_the_supported_version_and_kind_are_the_schemas():
    properties = schema()["properties"]
    assert (properties["apiVersion"]["const"],) == SUPPORTED_BINDING_VERSIONS
    assert properties["kind"]["const"] == ENVIRONMENT_BINDING_KIND


def test_the_binding_is_versioned_apart_from_the_workload_contract():
    """Equal today by maturity, and two constants, so one can move alone."""
    assert SUPPORTED_BINDING_VERSIONS is not SUPPORTED_CONTRACT_VERSIONS
    assert is_supported_binding_version("inferops.io/v1alpha1")
    assert not is_supported_binding_version("inferops.io/v1alpha2")
    assert not is_supported_binding_version(None)


@pytest.mark.parametrize(
    ("fields", "schema_node"),
    [
        (_ROOT_FIELDS, lambda: schema()),
        (_METADATA_FIELDS, lambda: defs("metadata")),
        (_SPEC_FIELDS, lambda: defs("spec")),
        (_DESTINATION_FIELDS, lambda: defs("destination")),
        (_MODEL_CACHE_FIELDS, lambda: defs("modelCache")),
        (_PLATFORM_FIELDS, lambda: defs("platform")),
        (_GITOPS_FIELDS, lambda: defs("gitops")),
    ],
    ids=["root", "metadata", "spec", "destination", "modelCache", "platform", "gitops"],
)
def test_every_field_list_is_the_schemas_in_order(fields: tuple[str, ...], schema_node):
    node = schema_node()
    assert list(fields) == list(node["properties"])
    assert sorted(fields) == sorted(node["required"])
    assert node["additionalProperties"] is False


def test_the_vocabularies_are_the_schemas():
    spec = defs("spec")["properties"]
    assert [m.value for m in Environment] == spec["environment"]["enum"]
    provider = defs("destination")["properties"]["clusterProvider"]
    assert [m.value for m in ClusterProvider] == provider["enum"]
    cache = defs("modelCache")["properties"]["class"]
    assert [m.value for m in ModelCacheClass] == cache["enum"]


@pytest.mark.parametrize(
    ("kind", "definition"),
    [
        (DnsLabel, "dnsLabel"),
        (ReleaseNamespace, "releaseNamespace"),
        (GitOpsPath, "lowercaseRepositoryPath"),
    ],
    ids=["dnsLabel", "releaseNamespace", "lowercaseRepositoryPath"],
)
def test_every_constrained_string_is_the_schemas(kind, definition: str):
    node = defs(definition)
    assert kind.PATTERN is not None
    assert kind.PATTERN.pattern == node["pattern"]
    assert node["maxLength"] == kind.MAXIMUM_LENGTH
    # An absent minLength is read as the floor every constrained string has.
    assert node.get("minLength", 1) == kind.MINIMUM_LENGTH


def test_every_identifier_field_uses_the_dns_label_definition():
    """name, owner, and claimName are held as DnsLabel because the schema says so."""
    assert defs("metadata")["properties"]["name"]["$ref"] == "#/$defs/dnsLabel"
    assert defs("metadata")["properties"]["owner"]["$ref"] == "#/$defs/dnsLabel"
    claim = defs("modelCache")["properties"]["claimName"]
    assert claim["$ref"] == "#/$defs/dnsLabel"


def test_the_api_replica_bounds_are_the_schemas():
    replicas = defs("platform")["properties"]["apiReplicas"]
    assert replicas["type"] == "integer"
    assert (
        replicas["minimum"],
        replicas["maximum"],
    ) == (API_REPLICAS_FLOOR, API_REPLICAS_CEILING)


# --------------------------------------------------------------------------
# 2. The parser and the published validator agree on every committed fixture
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_every_valid_fixture_parses_and_rebuilds_to_itself(path: Path):
    document = load(path)
    parsed = parse_environment_binding(document)
    assert parsed.as_document() == document
    assert parse_environment_binding(parsed.as_document()) == parsed


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_every_invalid_fixture_is_refused_where_the_validator_refuses_it(path: Path):
    """The same verdict, the same code, and a field the manifest names or holds."""
    entry = manifest()["fixtures"][path.name]
    expected_fields = [e["field"] for e in entry["expected"]]
    expected_codes = {e["code"] for e in entry["expected"]}
    assert validate_tool(load(path)), "the published validator must refuse it too"
    with pytest.raises(EnvironmentBindingError) as refused:
        parse_environment_binding(load(path))
    error = refused.value
    assert error.code in expected_codes
    assert any(
        field == error.field or field.startswith(f"{error.field}.")
        for field in expected_fields
    ), (error.field, expected_fields)


def test_only_the_version_fixture_is_refused_as_an_unsupported_version():
    for path in invalid_paths():
        with pytest.raises(EnvironmentBindingError) as refused:
            parse_environment_binding(load(path))
        unsupported = isinstance(refused.value, UnsupportedBindingVersionError)
        assert unsupported is (path.name == "unsupported-api-version.yaml"), path.name
        if not unsupported:
            assert isinstance(refused.value, MalformedEnvironmentBindingError)


def scalar_strings(node: Any) -> list[str]:
    if isinstance(node, dict):
        return [s for v in node.values() for s in scalar_strings(v)] + [
            k for k in node if isinstance(k, str)
        ]
    if isinstance(node, list):
        return [s for v in node for s in scalar_strings(v)]
    return [node] if isinstance(node, str) else []


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_no_parse_refusal_quotes_a_value_or_a_field_name_from_the_document(path: Path):
    document = load(path)
    vocabulary = set(scalar_strings(schema()))
    with pytest.raises(EnvironmentBindingError) as refused:
        parse_environment_binding(document)
    rendered = json.dumps(refused.value.as_dict())
    for value in scalar_strings(document):
        if len(value) >= 6 and value not in vocabulary:
            assert value not in rendered, f"{path.name} echoed a document value"


def test_a_workload_contract_is_not_read_as_a_binding():
    """They share an apiVersion, so the kind is what keeps them apart."""
    for path in sorted(WORKLOAD_VALID_DIR.glob("*.yaml")):
        with pytest.raises(MalformedEnvironmentBindingError) as refused:
            parse_environment_binding(load(path))
        assert refused.value.field in {"$", "$.kind"}, path.name


@pytest.mark.parametrize("document", [None, [], "binding", 3])
def test_a_document_that_is_not_an_object_is_refused(document: Any):
    with pytest.raises(MalformedEnvironmentBindingError) as refused:
        parse_environment_binding(document)
    assert refused.value.field == "$"


def test_a_missing_version_is_never_inferred():
    document = load(VALID_DIR / "local-kind.yaml")
    del document["apiVersion"]
    with pytest.raises(UnsupportedBindingVersionError) as refused:
        parse_environment_binding(document)
    assert refused.value.field == "$.apiVersion"
    assert refused.value.code == "version-unsupported"


def test_the_version_is_refused_before_anything_below_it_is_read():
    document = {"apiVersion": "inferops.io/v1beta1", "kind": "Something", "x": 1}
    with pytest.raises(UnsupportedBindingVersionError):
        parse_environment_binding(document)


@pytest.mark.parametrize(
    ("value", "accepted"),
    [(True, False), ("2", False), (2.5, False), (2.0, True), (0, False), (17, False)],
)
def test_api_replicas_are_read_as_json_schema_reads_an_integer(value: Any, accepted):
    document = load(VALID_DIR / "local-kind.yaml")
    document["spec"]["platform"]["apiReplicas"] = value
    assert (validate_tool(document) == []) is accepted
    if accepted:
        parsed = parse_environment_binding(document)
        assert parsed.spec.platform.api_replicas == 2
        assert isinstance(parsed.spec.platform.api_replicas, int)
    else:
        with pytest.raises(MalformedEnvironmentBindingError) as refused:
            parse_environment_binding(document)
        assert refused.value.field == "$.spec.platform.apiReplicas"


def test_a_parse_refusal_carries_the_request_context():
    context = RequestContext(request_id="req-1", correlation_id="corr-1")
    with pytest.raises(MalformedEnvironmentBindingError) as refused:
        parse_environment_binding(
            load(INVALID_DIR / "malformed-identifiers.yaml"), context=context
        )
    assert refused.value.context == context
    assert refused.value.as_dict()["requestId"] == "req-1"
    assert refused.value.retryable is False


def test_an_object_constructed_directly_still_refuses_what_the_parser_refuses():
    with pytest.raises(InvalidValueError):
        PlatformSettings(api_replicas=0)
    with pytest.raises(InvalidValueError):
        PlatformSettings(api_replicas=True)
    with pytest.raises(InvalidValueError):
        ReleaseNamespace("default")
    with pytest.raises(UnsupportedBindingVersionError):
        BindingVersion(group="inferops.io", version="v2")
    parsed = binding("local-kind")
    with pytest.raises(InvalidValueError):
        dataclasses.replace(parsed, kind="WorkloadContract")


def test_the_binding_objects_are_frozen():
    parsed = binding("local-kind")
    with pytest.raises(dataclasses.FrozenInstanceError):
        parsed.spec.platform.api_replicas = 3  # type: ignore[misc]


# --------------------------------------------------------------------------
# 3. The binding cannot own or override WorkloadContract semantics
# --------------------------------------------------------------------------


def attribute_names(kind: Any) -> set[str]:
    """Every dataclass attribute reachable from a class, through its annotations.

    A constrained string is a value, not structure: every one holds a `value`, and
    descending into it would report that as a name the two trees share.
    """
    names: set[str] = set()
    pending = [kind]
    seen: set[Any] = set()
    while pending:
        current = pending.pop()
        if current in seen or not dataclasses.is_dataclass(current):
            continue
        if isinstance(current, type) and issubclass(current, ConstrainedString):
            continue
        seen.add(current)
        hints = get_type_hints(current)
        for field in dataclasses.fields(current):
            names.add(field.name)
            hint = hints[field.name]
            for argument in (hint, *getattr(hint, "__args__", ())):
                pending.append(argument)
    return names


def wire_names(node: Any) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {n for v in node.values() for n in wire_names(v)}
    if isinstance(node, list):
        return {n for v in node for n in wire_names(v)}
    return set()


def test_no_binding_attribute_is_one_a_contract_spec_uses():
    """The override the binding exists to rule out, checked on the domain types."""
    from inferops.domain.environment import BindingSpec
    from inferops.domain.workload import WorkloadSpec

    shared = attribute_names(BindingSpec) & attribute_names(WorkloadSpec)
    assert shared == {SHARED_KEY}


@pytest.mark.parametrize(
    "workload", sorted(p.stem for p in WORKLOAD_VALID_DIR.glob("*.yaml"))
)
def test_no_binding_wire_name_is_one_a_contract_spec_writes(workload: str):
    ours = wire_names(binding("local-kind").spec.as_document())
    theirs = wire_names(contract(workload).spec.as_document())
    assert ours & theirs == {SHARED_KEY}


def test_the_shared_key_is_the_contracts_own_type():
    assert type(binding("local-kind").spec.environment) is Environment


@pytest.mark.parametrize(
    "intent",
    [
        {"scaling": {"minimumReplicas": 2, "maximumReplicas": 2}},
        {"resources": {"cpu": "1", "memory": "1Gi"}},
        {"model": {"modelRef": "a-model"}},
        {"security": {"secretRefs": []}},
        {"profile": "synchronous-llm"},
    ],
    ids=["scaling", "resources", "model", "security", "profile"],
)
def test_a_binding_carrying_workload_intent_is_refused_whole(intent: dict[str, Any]):
    """No partial object and no merge: the document is refused at `spec`."""
    document = load(VALID_DIR / "local-kind.yaml")
    document["spec"].update(copy.deepcopy(intent))
    with pytest.raises(MalformedEnvironmentBindingError) as refused:
        parse_environment_binding(document)
    assert refused.value.field == "$.spec"


def test_the_serving_replica_count_cannot_hide_under_platform():
    document = load(INVALID_DIR / "workload-intent-in-binding.yaml")
    del document["spec"]["model"], document["spec"]["scaling"]
    with pytest.raises(MalformedEnvironmentBindingError) as refused:
        parse_environment_binding(document)
    assert refused.value.field == "$.spec.platform"


def test_selection_returns_a_supplied_binding_and_leaves_the_contract_alone():
    workload = contract("synchronous-llm-local")
    before = workload.as_document()
    supplied = [binding("local-docker-desktop"), binding("local-kind")]
    selected = select_environment_binding(
        workload, supplied, binding_name=DnsLabel("local-kind")
    )
    assert selected is supplied[1]
    assert workload.as_document() == before
    assert selected.as_document() == load(VALID_DIR / "local-kind.yaml")


def test_selection_reads_only_the_contracts_environment():
    """Two contracts that differ in everything but the environment select alike."""
    local = contract("synchronous-llm-local")
    mock = contract("mock-llm-ci")
    moved = dataclasses.replace(
        mock, spec=dataclasses.replace(mock.spec, environment=Environment.LOCAL)
    )
    supplied = [binding("local-kind")]
    assert select_environment_binding(local, supplied) is supplied[0]
    assert select_environment_binding(moved, supplied) is supplied[0]


# --------------------------------------------------------------------------
# 4. Conflicting, missing, and ambiguous bindings fail canonically
# --------------------------------------------------------------------------


def rules_of(refusals: Any) -> list[tuple[str, str]]:
    return [(r.rule_id, r.field) for r in refusals]


def refused_selection(*args: Any, **kwargs: Any) -> BindingSelectionError:
    with pytest.raises(BindingSelectionError) as refused:
        select_environment_binding(*args, **kwargs)
    return refused.value


def test_the_committed_valid_fixtures_are_a_valid_set():
    assert validate_environment_bindings([binding(p.stem) for p in valid_paths()]) == []


def test_the_same_identity_twice_is_refused_at_the_later_binding():
    refusals = validate_environment_bindings(
        [binding("local-kind"), variant(path="gitops/environments/other")]
    )
    assert rules_of(refusals) == [
        ("binding-identity-duplicated", "bindings[1].metadata.name")
    ]


def test_the_same_name_in_another_environment_is_a_different_identity():
    assert (
        validate_environment_bindings(
            [binding("local-kind"), variant(environment="dev", path="gitops/dev/kind")]
        )
        == []
    )


@pytest.mark.parametrize(
    ("first", "second", "conflict"),
    [
        ("gitops/environments/a", "gitops/environments/a", True),
        ("gitops/environments", "gitops/environments/a", True),
        ("gitops/environments/a", "gitops/environments", True),
        ("gitops/environments/a", "gitops/environments/ab", False),
        ("gitops/env", "gitops/environments", False),
        ("gitops/environments/a", "gitops/environments/b", False),
    ],
)
def test_destinations_conflict_by_directory_not_by_string(
    first: str, second: str, conflict: bool
):
    refusals = validate_environment_bindings(
        [variant(name="first", path=first), variant(name="second", path=second)]
    )
    expected = (
        [("binding-destination-overlaps", "bindings[1].spec.gitops.destinationPath")]
        if conflict
        else []
    )
    assert rules_of(refusals) == expected


def test_a_destination_conflict_crosses_environments():
    refusals = validate_environment_bindings(
        [binding("local-kind"), variant(name="other", environment="staging")]
    )
    assert rules_of(refusals) == [
        ("binding-destination-overlaps", "bindings[1].spec.gitops.destinationPath")
    ]


def test_every_set_refusal_is_returned_at_once_and_sorted():
    supplied = [binding("local-kind")] * 3 + [binding("local-docker-desktop")] * 2
    refusals = validate_environment_bindings(supplied)
    fields = [r.field for r in refusals]
    # Three repeated identities (two for kind, one for desktop), and four
    # overlapping destinations (every pair of the three kind copies, one desktop).
    assert [r.rule_id for r in refusals].count("binding-identity-duplicated") == 3
    assert [r.rule_id for r in refusals].count("binding-destination-overlaps") == 4
    assert len(refusals) == 7
    assert fields == sorted(
        fields,
        key=lambda f: [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", f)],
    )
    again = validate_environment_bindings(supplied)
    assert [r.as_dict() for r in again] == [r.as_dict() for r in refusals]


def test_a_contract_with_no_binding_for_its_environment_is_refused():
    error = refused_selection(contract("mock-llm-ci"), [binding("local-kind")])
    assert [(r.rule_id, r.field) for r in error.refusals] == [
        ("binding-not-found", "contract.spec.environment")
    ]


def test_an_empty_set_serves_no_contract():
    error = refused_selection(contract("synchronous-llm-local"), [])
    assert error.refusals[0].rule_id == "binding-not-found"


def test_two_bindings_for_the_environment_and_no_name_is_ambiguous():
    error = refused_selection(
        contract("synchronous-llm-local"),
        [binding("local-docker-desktop"), binding("local-kind")],
    )
    assert [(r.rule_id, r.field) for r in error.refusals] == [
        ("binding-selection-ambiguous", "contract.spec.environment")
    ]


def test_one_binding_for_the_environment_needs_no_name():
    supplied = [binding("local-docker-desktop"), variant(environment="dev", path="d")]
    selected = select_environment_binding(contract("synchronous-llm-local"), supplied)
    assert selected is supplied[0]


def test_a_name_selects_among_several():
    supplied = [binding("local-docker-desktop"), binding("local-kind")]
    workload = contract("synchronous-llm-local")
    for expected in supplied:
        chosen = select_environment_binding(
            workload, supplied, binding_name=expected.metadata.name
        )
        assert chosen is expected


def test_a_name_nobody_has_is_not_found():
    error = refused_selection(
        contract("synchronous-llm-local"),
        [binding("local-kind")],
        binding_name=DnsLabel("absent"),
    )
    assert [(r.rule_id, r.field) for r in error.refusals] == [
        ("binding-not-found", "selection.bindingName")
    ]


def test_a_named_binding_for_another_environment_is_never_followed():
    error = refused_selection(
        contract("synchronous-llm-secret-refs"),  # environment: dev
        [binding("local-docker-desktop"), binding("local-kind")],
        binding_name=DnsLabel("local-kind"),
    )
    assert [(r.rule_id, r.field) for r in error.refusals] == [
        ("binding-environment-mismatch", "bindings[1].spec.environment")
    ]


def test_a_conflicting_set_is_not_selected_from():
    """Even when the binding asked for is not one of the pair that conflicts."""
    supplied = [
        binding("local-docker-desktop"),
        variant(name="a", environment="dev", path="gitops/shared"),
        variant(name="b", environment="dev", path="gitops/shared/b"),
    ]
    error = refused_selection(
        contract("synchronous-llm-local"),
        supplied,
        binding_name=DnsLabel("local-docker-desktop"),
    )
    assert [r.rule_id for r in error.refusals] == ["binding-destination-overlaps"]


@pytest.mark.parametrize(
    "bindings",
    [
        [load(VALID_DIR / "local-kind.yaml")],
        "local-kind",
        None,
    ],
    ids=["raw-document", "string", "none"],
)
def test_raw_input_cannot_take_the_supported_path(bindings: Any):
    with pytest.raises(TypeError):
        validate_environment_bindings(bindings)
    with pytest.raises(TypeError):
        select_environment_binding(contract("synchronous-llm-local"), bindings)


def test_a_raw_contract_or_name_cannot_take_the_supported_path():
    supplied = [binding("local-kind")]
    with pytest.raises(TypeError):
        select_environment_binding(
            load(WORKLOAD_VALID_DIR / "synchronous-llm-local.yaml"), supplied
        )
    with pytest.raises(TypeError):
        select_environment_binding(
            contract("synchronous-llm-local"),
            supplied,
            binding_name="local-kind",  # type: ignore[arg-type]
        )


def every_refusal() -> list[BindingRefusal]:
    conflicting = [binding("local-kind"), binding("local-kind")]
    found = list(validate_environment_bindings(conflicting))
    found.extend(
        refused_selection(contract("mock-llm-ci"), [binding("local-kind")]).refusals
    )
    found.extend(
        refused_selection(
            contract("synchronous-llm-local"),
            [binding("local-docker-desktop"), binding("local-kind")],
        ).refusals
    )
    found.extend(
        refused_selection(
            contract("synchronous-llm-secret-refs"),
            [binding("local-kind")],
            binding_name=DnsLabel("local-kind"),
        ).refusals
    )
    return found


def test_every_refusal_is_canonical_final_and_quotes_no_value():
    document_values = {
        value
        for path in valid_paths()
        for value in scalar_strings(load(path))
        if len(value) >= 6 and value not in set(scalar_strings(schema()))
    }
    for refusal in every_refusal():
        assert refusal.code in CANONICAL_ERROR_CODES
        assert refusal.retryable is False
        rendered = json.dumps(refusal.as_dict())
        for value in document_values:
            assert value not in rendered, (refusal.rule_id, value)


def test_a_selection_refusal_carries_the_request_context():
    context = RequestContext(request_id="req-2")
    with pytest.raises(BindingSelectionError) as refused:
        select_environment_binding(
            contract("mock-llm-ci"), [binding("local-kind")], context=context
        )
    assert all(r.context == context for r in refused.value.refusals)
    assert refused.value.refusals[0].as_dict()["requestId"] == "req-2"


# --------------------------------------------------------------------------
# 5. The published rule table is the code's
# --------------------------------------------------------------------------


def test_no_canonical_code_was_added():
    assert {rule.code for rule in BINDING_RULES.values()} == {"contract-invalid"}
    assert {rule.code for rule in BINDING_RULES.values()} <= set(CANONICAL_ERROR_CODES)
    assert MalformedEnvironmentBindingError.code in CANONICAL_ERROR_CODES
    assert UnsupportedBindingVersionError.code in CANONICAL_ERROR_CODES


def test_no_binding_rule_reuses_an_offline_validator_identifier():
    assert set(BINDING_RULES).isdisjoint(RULES)


def test_an_unpublished_rule_cannot_be_cited():
    with pytest.raises(KeyError):
        BindingRefusal("contract.spec", "binding-invented", "no such rule")


def test_every_published_rule_refuses_something():
    """A rule nothing provokes is a rule nobody has seen refuse anything."""
    assert {refusal.rule_id for refusal in every_refusal()} == set(BINDING_RULES)


def published_rule_rows() -> list[list[str]]:
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    start = text.index("the set of bindings supplied together, and a selection")
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
    return rows[1:]


def test_the_document_publishes_every_binding_rule_with_its_code():
    published = {row[0].strip("`"): row[1].strip("`") for row in published_rule_rows()}
    assert published == {rule: r.code for rule, r in BINDING_RULES.items()}


# --------------------------------------------------------------------------
# The package imports nothing it should not
# --------------------------------------------------------------------------


def test_the_binding_package_imports_only_the_standard_library_and_itself():
    """No Kubernetes, Helm, Argo, or file-system dependency, and no `tools`."""
    for path in sorted(PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                roots = {(node.module or "").split(".")[0]}
            else:
                continue
            for root in roots:
                assert root == "__future__" or root in sys.stdlib_module_names, (
                    path.name,
                    root,
                )
            assert "pathlib" not in roots and "os" not in roots, path.name
