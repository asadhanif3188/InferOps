"""The render boundary: what a renderer may be given, who owns it, and how it is gathered.

Every check reads files from this repository and nothing else. No network, no
cluster, no clock, no randomness - and one test proves the last two by making the
clock and every random source fail while the context is built.

Six things are asserted:

1. **Only a validated contract crosses.** A raw document, and a parsed contract
   that has not been validated, are refused at the boundary; a contract failing a
   semantic rule is refused with every finding; and each profile condition the
   published schema applies - which the domain's own pipeline does not - is
   refused under the published validator's rule and field. The gap this closes is
   measured on every condition, so it cannot be closed or reopened silently.
2. **Platform defaults are the chart's.** Their bounds are the chart's values
   schema, the chart's defaults construct a valid set, no setting is one the
   WorkloadContract or the EnvironmentBinding has a field for, and nothing outside
   the bounds, the supported version, or the typed revision is accepted.
3. **Every value has one owner.** The ownership table names every field each
   published schema defines exactly once - as a context value or as a field left
   out with a reason - and agrees with the binding's published ownership tables
   and with this package's own published table. No layer may override another.
4. **The context is read from the table and from nothing else.** Every value is
   its owner's value at its source path; a value no owner holds is absent; the
   sources are the digests and identities a release records, and a release built
   from them passes the release domain's provenance rules.
5. **It is deterministic and pure.** Equal inputs give equal contexts and digests,
   whatever the binding order, in another interpreter under another hash seed,
   with every clock and random source failing; the package imports only the
   standard library and the domain, and nothing outside the domain imports it.
6. **A renderer takes a context.** The interface's one input is a
   :class:`RenderContext`, and a conforming object is recognised as one.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import json
import os
import random
import re
import secrets
import shutil
import subprocess
import sys
import time
import typing
import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.domain.environment import (
    BindingSelectionError,
    EnvironmentBinding,
    parse_environment_binding,
    select_environment_binding,
)
from inferops.domain.release import (
    GitRevision,
    ReleaseSource,
    RendererReference,
    binding_digest,
    canonical_json,
    check_rendered_workload_release,
    contract_digest,
    derive_release_id,
    parse_release_workload_version,
    parse_rendered_workload_release,
    verify_release_sources,
)
from inferops.domain.render import (
    EXCLUDED_SOURCE_FIELDS,
    MILLISECONDS_CEILING,
    MILLISECONDS_FLOOR,
    OUTPUT_TOKENS_CEILING,
    OUTPUT_TOKENS_FLOOR,
    OVERRIDES,
    PROFILE_CONDITIONS,
    RENDER_FIELD_OWNERSHIP,
    SUPPORTED_PLATFORM_DEFAULTS_VERSIONS,
    ApiDefaults,
    Layer,
    PlatformDefaults,
    RefusalCategory,
    RenderContext,
    Renderer,
    RendererSupport,
    RenderRefused,
    ValidatedWorkloadContract,
    WorkloadNotAcceptedError,
    build_render_context,
    may_override,
    owner_of,
    ownership_of,
    profile_condition_findings,
    validate_for_render,
)
from inferops.domain.render import acceptance as acceptance_module
from inferops.domain.workload import (
    CompatibilityMatrixLoader,
    DnsLabel,
    InvalidValueError,
    Profile,
    WorkloadContract,
    parse_workload_contract,
    set_matrix_loader,
    validate_workload_contract,
)
from inferops.domain.workload import validation as validation_module
from tools.contract_validation.workload import validate as validate_contract_tool

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = REPO_ROOT / "src" / "inferops" / "domain" / "render"
WORKLOAD_SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "workload" / "workload-contract.v1alpha1.schema.json"
)
BINDING_SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "environment" / "environment-binding.v1alpha1.schema.json"
)
MATRIX_PATH = (
    REPO_ROOT
    / "contracts"
    / "workload"
    / "compatibility"
    / "runtime-model-compatibility.v1alpha1.json"
)
WORKLOAD_VALID_DIR = REPO_ROOT / "contracts" / "workload" / "examples" / "valid"
BINDING_VALID_DIR = REPO_ROOT / "contracts" / "environment" / "examples" / "valid"
CHART_DIR = REPO_ROOT / "charts" / "inferops-llm"
BINDING_DOC = REPO_ROOT / "docs" / "contracts" / "environment-binding.md"
BOUNDARY_DOC = REPO_ROOT / "docs" / "domain" / "renderer-input-boundary.md"

DEFAULTS_REVISION = "b" * 40
RENDERER_REVISION = "a" * 40
VALUES_SHA256 = "5" * 64

set_matrix_loader(
    CompatibilityMatrixLoader(json.loads(MATRIX_PATH.read_text(encoding="utf-8")))
)


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------


def load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def contract_document(name: str = "synchronous-llm-local") -> dict[str, Any]:
    return load(WORKLOAD_VALID_DIR / f"{name}.yaml")


def binding_document(name: str = "local-kind") -> dict[str, Any]:
    return load(BINDING_VALID_DIR / f"{name}.yaml")


def contract(name: str = "synchronous-llm-local") -> WorkloadContract:
    return parse_workload_contract(contract_document(name))


def binding_for(environment: str) -> EnvironmentBinding:
    """A binding serving an environment no committed fixture serves - `ci`, `dev`."""
    document = binding_document("local-kind")
    document["metadata"]["name"] = f"{environment}-kind"
    document["spec"]["environment"] = environment
    document["spec"]["gitops"]["destinationPath"] = (
        f"gitops/environments/{environment}-kind"
    )
    return parse_environment_binding(document)


def ci_binding() -> EnvironmentBinding:
    return binding_for("ci")


def local_bindings() -> list[EnvironmentBinding]:
    return [
        parse_environment_binding(load(path))
        for path in sorted(BINDING_VALID_DIR.glob("*.yaml"))
    ]


def chart_api_defaults() -> dict[str, Any]:
    return load(CHART_DIR / "values.yaml")["api"]


def defaults(
    *,
    request_timeout_ms: int | None = None,
    drain_timeout_ms: int | None = None,
    max_output_tokens: int | None = None,
    revision: str = DEFAULTS_REVISION,
) -> PlatformDefaults:
    """The chart's own defaults, read at a placeholder revision."""
    chart = chart_api_defaults()
    return PlatformDefaults(
        "v1alpha1",
        GitRevision(revision),
        ApiDefaults(
            request_timeout_ms=(
                chart["requestTimeoutMs"]
                if request_timeout_ms is None
                else request_timeout_ms
            ),
            drain_timeout_ms=(
                chart["drainTimeoutMs"]
                if drain_timeout_ms is None
                else drain_timeout_ms
            ),
            max_output_tokens=(
                chart["maxOutputTokens"]
                if max_output_tokens is None
                else max_output_tokens
            ),
        ),
    )


def render_context(
    workload: WorkloadContract | None = None,
    *,
    bindings: list[EnvironmentBinding] | None = None,
    binding_name: str | None = "local-kind",
    platform_defaults: PlatformDefaults | None = None,
) -> RenderContext:
    return build_render_context(
        validate_for_render(contract() if workload is None else workload),
        defaults() if platform_defaults is None else platform_defaults,
        local_bindings() if bindings is None else bindings,
        binding_name=None if binding_name is None else DnsLabel(binding_name),
    )


def mock_context() -> RenderContext:
    return render_context(
        contract("mock-llm-ci"), bindings=[ci_binding()], binding_name=None
    )


def secret_refs_context() -> RenderContext:
    return render_context(
        contract("synchronous-llm-secret-refs"),
        bindings=[binding_for("dev")],
        binding_name=None,
    )


def every_context() -> list[RenderContext]:
    return [
        render_context(binding_name="local-kind"),
        render_context(binding_name="local-docker-desktop"),
        secret_refs_context(),
        mock_context(),
    ]


def lookup(document: Any, path: str) -> Any:
    node = document
    for step in path.split("."):
        if not isinstance(node, dict) or step not in node:
            raise KeyError(path)
        node = node[step]
    return node


# --------------------------------------------------------------------------
# Schema walking
# --------------------------------------------------------------------------


def resolve(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        node = schema["$defs"][node["$ref"].removeprefix("#/$defs/")]
    return node


def schema_fields(
    schema: dict[str, Any],
    node: dict[str, Any] | None = None,
    prefix: str = "",
    required_so_far: bool = True,
) -> dict[str, bool]:
    """Every leaf field a schema defines, with whether it is required unconditionally.

    An object with declared properties is walked; anything else - a scalar, an
    array, a map with no declared properties, a ``oneOf`` - is one leaf.
    """
    node = resolve(schema, schema if node is None else node)
    if node.get("type") != "object" or "properties" not in node:
        return {prefix: required_so_far}
    required = set(node.get("required", []))
    found: dict[str, bool] = {}
    for key, member in node["properties"].items():
        path = f"{prefix}.{key}" if prefix else key
        found |= schema_fields(
            schema, member, path, required_so_far and key in required
        )
    return found


def workload_schema() -> dict[str, Any]:
    return json.loads(WORKLOAD_SCHEMA_PATH.read_text(encoding="utf-8"))


def binding_schema() -> dict[str, Any]:
    return json.loads(BINDING_SCHEMA_PATH.read_text(encoding="utf-8"))


def rows(layer: Layer) -> list[Any]:
    return [row for row in RENDER_FIELD_OWNERSHIP if row.layer is layer]


# --------------------------------------------------------------------------
# 1. Only a validated contract crosses
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["synchronous-llm-local", "synchronous-llm-secret-refs", "mock-llm-ci"]
)
def test_every_valid_contract_fixture_is_accepted_unchanged(name: str) -> None:
    workload = contract(name)
    validated = validate_for_render(workload)
    assert isinstance(validated, ValidatedWorkloadContract)
    assert validated.contract is workload


@pytest.mark.parametrize(
    "raw", [None, {}, contract_document(), "synchronous-llm-local", [contract()]]
)
def test_a_raw_document_cannot_be_validated_for_render(raw: Any) -> None:
    with pytest.raises(TypeError, match="not a raw document"):
        validate_for_render(raw)


def test_a_semantically_invalid_contract_is_refused_with_every_finding() -> None:
    document = contract_document("synchronous-llm-secret-refs")
    document["spec"]["scaling"] = {"minimumReplicas": 5, "maximumReplicas": 2}
    document["spec"]["security"]["secretRefs"].append(
        copy.deepcopy(document["spec"]["security"]["secretRefs"][0])
    )
    document["spec"]["profile"] = "mock-llm"
    workload = parse_workload_contract(document)

    with pytest.raises(WorkloadNotAcceptedError) as raised:
        validate_for_render(workload)

    error = raised.value
    found = [(finding.field, finding.rule_id) for finding in error.findings]
    assert found == sorted(set(found), key=found.index), "findings repeat"
    assert {rule for _, rule in found} >= {
        "replica-range-inverted",
        "secret-ref-name-duplicated",
        "mock-secret-ref-declared",
        "field-required",
        "value-not-permitted",
    }
    assert error.retryable is False
    published = error.as_dict()["findings"]
    assert isinstance(published, list)
    assert [entry["ruleId"] for entry in published] == [rule for _, rule in found]


def test_findings_are_sorted_by_field_and_rule() -> None:
    document = contract_document("mock-llm-ci")
    document["spec"]["environment"] = "dev"
    document["spec"]["resources"]["accelerator"] = {"type": "nvidia-gpu", "count": 2}
    document["spec"]["scaling"] = {"minimumReplicas": 3, "maximumReplicas": 1}
    with pytest.raises(WorkloadNotAcceptedError) as raised:
        validate_for_render(parse_workload_contract(document))
    fields = [finding.field for finding in raised.value.findings]
    assert fields == sorted(fields)


def test_no_finding_repeats_a_value_read_from_the_document() -> None:
    document = contract_document("mock-llm-ci")
    document["spec"]["environment"] = "staging"
    document["spec"]["evidence"]["proofRefs"] = ["docs/proof/zz-unique-proof-path.md"]
    with pytest.raises(WorkloadNotAcceptedError) as raised:
        validate_for_render(parse_workload_contract(document))
    text = str(raised.value) + json.dumps(raised.value.as_dict())
    assert "staging" not in text
    assert "zz-unique-proof-path" not in text


#: One mutation per way a valid fixture can break a profile condition, with the
#: (rule, field) set the published validator refuses it with.
PROFILE_MUTATIONS: dict[str, tuple[str, Any, set[tuple[str, str]]]] = {
    "synchronous-without-its-block": (
        "synchronous-llm-local",
        lambda d: d["spec"].pop("synchronousLlm"),
        {("field-required", "spec.synchronousLlm")},
    ),
    "synchronous-with-the-mock-block": (
        "synchronous-llm-local",
        lambda d: d["spec"].__setitem__(
            "mockLlm", contract_document("mock-llm-ci")["spec"]["mockLlm"]
        ),
        {("value-not-permitted", "spec")},
    ),
    "synchronous-claiming-mock-serving": (
        "synchronous-llm-local",
        lambda d: d["spec"]["model"].__setitem__(
            "servingCapability", "inferops-mock-serving"
        ),
        {("value-not-permitted", "spec.model.servingCapability")},
    ),
    "mock-without-its-block": (
        "mock-llm-ci",
        lambda d: d["spec"].pop("mockLlm"),
        {("field-required", "spec.mockLlm")},
    ),
    "mock-with-the-synchronous-block": (
        "mock-llm-ci",
        lambda d: d["spec"].__setitem__(
            "synchronousLlm",
            contract_document("synchronous-llm-local")["spec"]["synchronousLlm"],
        ),
        {("value-not-permitted", "spec")},
    ),
    "mock-outside-ci": (
        "mock-llm-ci",
        lambda d: d["spec"].__setitem__("environment", "dev"),
        {("value-not-permitted", "spec.environment")},
    ),
    "mock-claiming-native-serving": (
        "mock-llm-ci",
        lambda d: d["spec"]["model"].__setitem__(
            "servingCapability", "inferops-native-serving"
        ),
        {("value-not-permitted", "spec.model.servingCapability")},
    ),
    "mock-asking-for-an-accelerator": (
        "mock-llm-ci",
        lambda d: d["spec"]["resources"].__setitem__(
            "accelerator", {"type": "nvidia-gpu", "count": 1}
        ),
        {
            ("value-not-permitted", "spec.resources.accelerator.type"),
            ("value-not-permitted", "spec.resources.accelerator.count"),
        },
    ),
    "mock-citing-proof": (
        "mock-llm-ci",
        lambda d: d["spec"]["evidence"].__setitem__(
            "proofRefs", ["docs/proof/README.md"]
        ),
        {("value-out-of-range", "spec.evidence.proofRefs")},
    ),
}


def mutated(case: str) -> dict[str, Any]:
    fixture, mutate, _ = PROFILE_MUTATIONS[case]
    document = contract_document(fixture)
    mutate(document)
    return document


def published_findings(document: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (finding.rule, finding.field.removeprefix("$."))
        for finding in validate_contract_tool(document)
    }


@pytest.mark.parametrize("case", sorted(PROFILE_MUTATIONS))
def test_the_domain_pipeline_alone_accepts_each_profile_break(case: str) -> None:
    """The gap, measured: the domain parses and passes what the schema refuses.

    If the workload pipeline ever applies a profile condition, this fails, and the
    duplicate here should then be removed rather than kept beside it.
    """
    workload = parse_workload_contract(mutated(case))
    assert validate_workload_contract(workload) == []


@pytest.mark.parametrize("case", sorted(PROFILE_MUTATIONS))
def test_each_profile_break_is_refused_exactly_as_the_published_validator_refuses_it(
    case: str,
) -> None:
    document = mutated(case)
    expected = PROFILE_MUTATIONS[case][2]
    assert published_findings(document) == expected

    with pytest.raises(WorkloadNotAcceptedError) as raised:
        validate_for_render(parse_workload_contract(document))
    assert {
        (finding.rule_id, finding.field) for finding in raised.value.findings
    } == expected


def test_every_profile_condition_is_broken_by_some_mutation() -> None:
    hit = {
        (
            finding.rule_id,
            finding.field,
            parse_workload_contract(mutated(case)).spec.profile,
        )
        for case in PROFILE_MUTATIONS
        for finding in profile_condition_findings(
            parse_workload_contract(mutated(case))
        )
    }
    assert hit == {
        (condition.rule_id, condition.field, condition.profile)
        for condition in PROFILE_CONDITIONS
    }


def schema_profile_conditions() -> set[tuple[str, str, str]]:
    """Every leaf of every ``then`` under ``spec.allOf``, as (profile, rule, field)."""
    schema = workload_schema()
    found: set[tuple[str, str, str]] = set()

    def walk(profile: str, node: dict[str, Any], path: str) -> None:
        for key in node.get("required", []):
            found.add((profile, "field-required", f"{path}.{key}"))
        if "not" in node:
            assert set(node["not"]) == {"required"}, node["not"]
            found.add((profile, "value-not-permitted", path))
        if "const" in node:
            found.add((profile, "value-not-permitted", path))
        if "maxItems" in node:
            found.add((profile, "value-out-of-range", path))
        for key, member in node.get("properties", {}).items():
            walk(profile, member, f"{path}.{key}")

    for clause in schema["$defs"]["spec"]["allOf"]:
        profile = clause["if"]["properties"]["profile"]["const"]
        walk(profile, clause["then"], "spec")
    return found


def test_the_profile_conditions_are_every_condition_the_schema_applies() -> None:
    assert {
        (condition.profile.value, condition.rule_id, condition.field)
        for condition in PROFILE_CONDITIONS
    } == schema_profile_conditions()


def test_a_validated_contract_cannot_be_constructed_or_copied_into_one() -> None:
    with pytest.raises(TypeError, match="validate_for_render"):
        ValidatedWorkloadContract(contract())
    validated = validate_for_render(contract())
    with pytest.raises(TypeError, match="validate_for_render"):
        dataclasses.replace(validated, contract=contract("mock-llm-ci"))


def test_the_guard_does_not_stop_a_caller_who_imports_the_private_sentinel() -> None:
    """A limit, recorded: the guard stops accidents, not intent.

    Python has no private names. Importing the sentinel forges a validated contract
    from one that would be refused - which is why the document says the guard is
    against accidents and why nothing relies on it as a security boundary.
    """
    document = contract_document()
    document["spec"]["scaling"] = {"minimumReplicas": 5, "maximumReplicas": 2}
    workload = parse_workload_contract(document)
    forged = ValidatedWorkloadContract(workload, acceptance_module._ISSUED)
    assert forged.contract is workload


def test_a_synchronous_contract_needs_the_compatibility_matrix(monkeypatch) -> None:
    monkeypatch.setattr(validation_module, "_matrix_loader", None)
    with pytest.raises(ValueError, match="Matrix loader not initialized"):
        validate_for_render(contract())
    assert validate_for_render(contract("mock-llm-ci")).contract.is_mock


# --------------------------------------------------------------------------
# 2. Platform defaults are the chart's
# --------------------------------------------------------------------------


def chart_schema() -> dict[str, Any]:
    return json.loads((CHART_DIR / "values.schema.json").read_text(encoding="utf-8"))


def test_the_defaults_bounds_are_the_charts() -> None:
    schema = chart_schema()
    api = schema["properties"]["api"]["properties"]
    milliseconds = schema["$defs"]["positiveMilliseconds"]
    for name in ("requestTimeoutMs", "drainTimeoutMs"):
        assert resolve(schema, api[name]) == milliseconds
    assert (milliseconds["minimum"], milliseconds["maximum"]) == (
        MILLISECONDS_FLOOR,
        MILLISECONDS_CEILING,
    )
    tokens = api["maxOutputTokens"]
    assert (tokens["minimum"], tokens["maximum"]) == (
        OUTPUT_TOKENS_FLOOR,
        OUTPUT_TOKENS_CEILING,
    )


def test_the_charts_defaults_construct_a_valid_set() -> None:
    chart = chart_api_defaults()
    built = defaults()
    assert built.as_document()["api"] == {
        "requestTimeoutMs": chart["requestTimeoutMs"],
        "drainTimeoutMs": chart["drainTimeoutMs"],
        "maxOutputTokens": chart["maxOutputTokens"],
    }


def test_no_ci_values_file_overrides_a_default() -> None:
    """The chart's default is what every values file the repository renders with uses."""
    for path in sorted((CHART_DIR / "ci").glob("*.yaml")):
        api = (load(path) or {}).get("api", {})
        assert {"requestTimeoutMs", "drainTimeoutMs", "maxOutputTokens"}.isdisjoint(
            api
        ), path.name


def test_no_default_is_a_field_the_contract_or_the_binding_has() -> None:
    names = {"requestTimeoutMs", "drainTimeoutMs", "maxOutputTokens"}
    for schema in (workload_schema(), binding_schema()):
        leaves = {path.rsplit(".", 1)[-1] for path in schema_fields(schema)}
        assert names.isdisjoint(leaves)
    assert {row.source for row in rows(Layer.PLATFORM_DEFAULTS)} == {
        f"api.{name}" for name in names
    }


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("request_timeout_ms", MILLISECONDS_FLOOR - 1),
        ("request_timeout_ms", MILLISECONDS_CEILING + 1),
        ("drain_timeout_ms", MILLISECONDS_FLOOR - 1),
        ("drain_timeout_ms", MILLISECONDS_CEILING + 1),
        ("max_output_tokens", OUTPUT_TOKENS_FLOOR - 1),
        ("max_output_tokens", OUTPUT_TOKENS_CEILING + 1),
        ("max_output_tokens", True),
        ("drain_timeout_ms", 15000.0),
        ("request_timeout_ms", "120000"),
    ],
)
def test_a_default_outside_its_bounds_or_type_is_refused(
    setting: str, value: Any
) -> None:
    with pytest.raises(InvalidValueError):
        defaults(**{setting: value})


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("request_timeout_ms", MILLISECONDS_FLOOR),
        ("request_timeout_ms", MILLISECONDS_CEILING),
        ("max_output_tokens", OUTPUT_TOKENS_FLOOR),
        ("max_output_tokens", OUTPUT_TOKENS_CEILING),
    ],
)
def test_a_default_on_its_bound_is_accepted(setting: str, value: int) -> None:
    arguments: dict[str, Any] = {setting: value}
    assert defaults(**arguments)


@pytest.mark.parametrize("version", ["v1alpha2", "v1", "", "inferops.io/v1alpha1"])
def test_an_unsupported_defaults_version_is_refused(version: str) -> None:
    with pytest.raises(InvalidValueError, match="supported versions are 'v1alpha1'"):
        PlatformDefaults(version, GitRevision(DEFAULTS_REVISION), defaults().api)
    assert SUPPORTED_PLATFORM_DEFAULTS_VERSIONS == ("v1alpha1",)


def test_a_defaults_revision_or_api_block_must_be_typed() -> None:
    with pytest.raises(InvalidValueError, match="GitRevision"):
        PlatformDefaults("v1alpha1", DEFAULTS_REVISION, defaults().api)  # type: ignore[arg-type]
    with pytest.raises(InvalidValueError, match="ApiDefaults"):
        PlatformDefaults(
            "v1alpha1",
            GitRevision(DEFAULTS_REVISION),
            defaults().api.as_document(),  # type: ignore[arg-type]
        )
    with pytest.raises(InvalidValueError):
        GitRevision("main")


@pytest.mark.parametrize("kind", [ApiDefaults, PlatformDefaults])
def test_no_default_has_a_default(kind: type) -> None:
    for member in dataclasses.fields(kind):
        assert member.default is dataclasses.MISSING, member.name
        assert member.default_factory is dataclasses.MISSING, member.name


# --------------------------------------------------------------------------
# 3. Every value has one owner
# --------------------------------------------------------------------------


def test_every_context_name_is_unique_and_no_name_is_another_names_prefix() -> None:
    names = [row.name for row in RENDER_FIELD_OWNERSHIP]
    assert len(names) == len(set(names))
    segments = [tuple(name.split(".")) for name in names]
    for first in segments:
        for second in segments:
            if first != second:
                assert second[: len(first)] != first, (first, second)


def test_no_source_is_read_into_two_values() -> None:
    pairs = [(row.layer, row.source) for row in RENDER_FIELD_OWNERSHIP]
    assert len(pairs) == len(set(pairs))


def test_no_layer_may_override_another() -> None:
    assert not OVERRIDES
    for winner in Layer:
        for loser in Layer:
            assert may_override(winner, loser) is False


def test_owner_lookup_is_the_table() -> None:
    for row in RENDER_FIELD_OWNERSHIP:
        assert owner_of(row.name) is row.layer
        assert ownership_of(row.name) is row
    with pytest.raises(KeyError):
        owner_of("api.replicaCount")


@pytest.mark.parametrize(
    ("layer", "schema_of"),
    [
        (Layer.WORKLOAD_INTENT, workload_schema),
        (Layer.ENVIRONMENT_BINDING, binding_schema),
    ],
)
def test_every_schema_field_is_read_or_left_out_with_a_reason(layer, schema_of) -> None:
    """Exactly once: a field added to a schema fails here until it is classified."""
    fields = schema_fields(schema_of())
    read = {row.source for row in rows(layer)}
    excluded = set(EXCLUDED_SOURCE_FIELDS[layer])
    assert read.isdisjoint(excluded)
    assert read | excluded == set(fields)


@pytest.mark.parametrize(
    ("layer", "schema_of"),
    [
        (Layer.WORKLOAD_INTENT, workload_schema),
        (Layer.ENVIRONMENT_BINDING, binding_schema),
    ],
)
def test_a_value_is_always_present_exactly_when_its_schema_requires_it(
    layer, schema_of
) -> None:
    fields = schema_fields(schema_of())
    for row in rows(layer):
        assert row.required is fields[row.source], row.name


def test_the_defaults_fields_are_read_or_left_out_with_a_reason() -> None:
    document = defaults().as_document()

    def leaves(node: Any, prefix: str = "") -> set[str]:
        if not isinstance(node, dict):
            return {prefix}
        found: set[str] = set()
        for key, member in node.items():
            found |= leaves(member, f"{prefix}.{key}" if prefix else key)
        return found

    read = {row.source for row in rows(Layer.PLATFORM_DEFAULTS)}
    excluded = set(EXCLUDED_SOURCE_FIELDS[Layer.PLATFORM_DEFAULTS])
    assert read.isdisjoint(excluded)
    assert read | excluded == leaves(document)
    assert all(row.required for row in rows(Layer.PLATFORM_DEFAULTS))


def test_every_exclusion_carries_a_reason() -> None:
    for layer, fields in EXCLUDED_SOURCE_FIELDS.items():
        for name, reason in fields.items():
            assert len(reason.split()) >= 5, (layer, name)


def binding_doc_table(start: str, stop: str) -> list[str]:
    text = BINDING_DOC.read_text(encoding="utf-8")
    section = text[text.index(start) : text.index(stop)]
    return re.findall(r"^\| `(spec\.[A-Za-z.]+)` \|", section, flags=re.MULTILINE)


def test_the_binding_rows_are_the_bindings_published_ownership_table() -> None:
    owned = binding_doc_table(
        "**A binding owns environment facts.**", "Referencing is not owning"
    )
    assert set(owned) == {row.source for row in rows(Layer.ENVIRONMENT_BINDING)} | {
        "spec.environment"
    }
    assert "spec.environment" in EXCLUDED_SOURCE_FIELDS[Layer.ENVIRONMENT_BINDING]


def test_every_block_the_binding_may_not_carry_is_workload_intent_here() -> None:
    blocks = binding_doc_table(
        "**A binding may not carry workload intent.**", "## Identity"
    )
    assert len(blocks) == 10
    workload_sources = {row.source for row in rows(Layer.WORKLOAD_INTENT)}
    for block in blocks:
        assert any(
            source == block or source.startswith(f"{block}.")
            for source in workload_sources
        ), block
    binding_sources = {row.source for row in rows(Layer.ENVIRONMENT_BINDING)}
    for block in blocks:
        assert not any(
            source == block or source.startswith(f"{block}.")
            for source in binding_sources
        ), block


def published_table(heading: str, columns: int) -> list[list[str]]:
    text = BOUNDARY_DOC.read_text(encoding="utf-8")
    section = text[text.index(heading) :]
    section = (
        section[: section.index("\n## ", 1)] if "\n## " in section[1:] else section
    )
    found = []
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == columns and cells[0].startswith("`"):
            found.append([cell.strip("`") for cell in cells])
    return found


def test_the_published_ownership_table_is_the_code() -> None:
    table = published_table("## Who owns each value", 4)
    assert table == [
        [row.name, row.layer.value, row.source, "yes" if row.required else "no"]
        for row in RENDER_FIELD_OWNERSHIP
    ]


def test_the_published_profile_conditions_are_the_code() -> None:
    table = published_table("## What validated means", 4)
    assert [cells[:3] for cells in table] == [
        [condition.profile.value, condition.field, condition.rule_id]
        for condition in PROFILE_CONDITIONS
    ]


# --------------------------------------------------------------------------
# 4. The context is read from the table and from nothing else
# --------------------------------------------------------------------------


@pytest.mark.parametrize("index", range(4))
def test_every_value_is_its_owners_value_at_its_source(index: int) -> None:
    context = every_context()[index]
    workload = (
        contract("mock-llm-ci")
        if context.value("workload.profile") == "mock-llm"
        else parse_workload_contract(
            contract_document(
                "synchronous-llm-secret-refs"
                if len(context.value("security.secretRefs"))
                else "synchronous-llm-local"
            )
        )
    )
    binding_name = context.sources.environment_binding.name
    binding = next(
        candidate
        for candidate in [*local_bindings(), ci_binding(), binding_for("dev")]
        if candidate.metadata.name == binding_name
    )
    owners = {
        Layer.WORKLOAD_INTENT: workload.as_document(),
        Layer.PLATFORM_DEFAULTS: defaults().as_document(),
        Layer.ENVIRONMENT_BINDING: binding.as_document(),
    }
    for entry in context.fields:
        row = ownership_of(entry.name)
        assert (entry.layer, entry.source) == (row.layer, row.source)
        assert entry.as_document()["value"] == lookup(owners[row.layer], row.source)

    expected = set()
    for row in RENDER_FIELD_OWNERSHIP:
        try:
            lookup(owners[row.layer], row.source)
        except KeyError:
            assert not row.required, row.name
        else:
            expected.add(row.name)
    assert set(context.names()) == expected
    assert list(context.names()) == sorted(context.names())


def test_a_profile_carries_its_own_values_and_none_of_the_others() -> None:
    synchronous = set(render_context().names())
    mock = set(mock_context().names())
    real_only = {"runtime.imageReference"} | {
        name for name in synchronous if name.startswith("model.artifact.")
    }
    mock_only = {"mock.ciOnly", "mock.determinism", "mock.fixtureRef"}
    assert len(real_only) == 6
    assert real_only <= synchronous and real_only.isdisjoint(mock)
    assert mock_only <= mock and mock_only.isdisjoint(synchronous)


def test_each_layer_supplies_only_what_it_owns() -> None:
    context = render_context()
    for layer in Layer:
        assert {entry.name for entry in context.owned_by(layer)} <= {
            row.name for row in rows(layer)
        }
    assert {entry.name for entry in context.owned_by(Layer.PLATFORM_DEFAULTS)} == {
        "api.drainTimeoutMs",
        "api.maxOutputTokens",
        "api.requestTimeoutMs",
    }


def test_the_environment_comes_from_the_contract_and_the_binding_is_identified() -> (
    None
):
    context = render_context(binding_name="local-docker-desktop")
    assert context.entry("workload.environment").layer is Layer.WORKLOAD_INTENT
    assert context.value("destination.clusterProvider") == "docker-desktop"
    assert str(context.sources.environment_binding.name) == "local-docker-desktop"
    assert context.sources.environment_binding.environment.value == context.value(
        "workload.environment"
    )


def test_the_sources_are_the_digests_and_identities_a_release_records() -> None:
    workload = contract()
    binding = local_bindings()[1]
    assert str(binding.metadata.name) == "local-kind"
    context = render_context(workload, binding_name="local-kind")
    sources = context.sources
    assert sources.contract.sha256 == contract_digest(workload)
    assert str(sources.contract.api_version) == str(workload.api_version)
    assert sources.environment_binding.sha256 == binding_digest(binding)
    assert str(sources.platform_defaults.revision) == DEFAULTS_REVISION


def test_a_release_built_from_the_sources_passes_the_provenance_rules() -> None:
    """The context's sources are exactly what the release domain checks a release by."""
    workload = contract()
    binding = local_bindings()[1]
    context = render_context(workload, binding_name="local-kind")
    source = context.sources.release_source(
        RendererReference(GitRevision(RENDERER_REVISION))
    )
    assert isinstance(source, ReleaseSource)
    version = parse_release_workload_version(context.value("workload.version"))
    document = {
        "apiVersion": "inferops.io/v1alpha1",
        "kind": "RenderedWorkloadRelease",
        "metadata": {
            "workloadId": context.value("workload.id"),
            "workloadVersion": str(version),
            "releaseId": str(
                derive_release_id(
                    DnsLabel(context.value("workload.id")), version, source
                )
            ),
        },
        "source": source.as_document(),
        "output": {
            "helmValues": {"path": "values.generated.yaml", "sha256": VALUES_SHA256}
        },
    }
    release = parse_rendered_workload_release(document)
    assert check_rendered_workload_release(release) == []
    assert verify_release_sources(release, workload, binding) == []


def test_release_source_needs_a_renderer_reference() -> None:
    with pytest.raises(TypeError, match="RendererReference"):
        render_context().sources.release_source(RENDERER_REVISION)  # type: ignore[arg-type]


def test_a_parsed_but_unvalidated_contract_cannot_cross_the_boundary() -> None:
    with pytest.raises(TypeError, match="ValidatedWorkloadContract"):
        build_render_context(contract(), defaults(), local_bindings())  # type: ignore[arg-type]


@pytest.mark.parametrize("raw", [contract_document(), None, "synchronous-llm-local"])
def test_a_raw_contract_cannot_cross_the_boundary(raw: Any) -> None:
    with pytest.raises(TypeError, match="ValidatedWorkloadContract"):
        build_render_context(raw, defaults(), local_bindings())


def test_raw_defaults_cannot_cross_the_boundary() -> None:
    with pytest.raises(TypeError, match="PlatformDefaults"):
        build_render_context(
            validate_for_render(contract()),
            defaults().as_document(),  # type: ignore[arg-type]
            local_bindings(),
        )


@pytest.mark.parametrize(
    "bindings",
    [
        [binding_document("local-kind")],
        binding_document("local-kind"),
        "local-kind",
    ],
)
def test_a_raw_binding_cannot_cross_the_boundary(bindings: Any) -> None:
    with pytest.raises(TypeError):
        build_render_context(validate_for_render(contract()), defaults(), bindings)


def test_a_render_context_cannot_be_constructed_or_copied_into_one() -> None:
    context = render_context()
    with pytest.raises(TypeError, match="build_render_context"):
        RenderContext(context.fields, context.sources)
    with pytest.raises(TypeError, match="build_render_context"):
        dataclasses.replace(context, fields=())


@pytest.mark.parametrize(
    ("bindings", "binding_name", "rule"),
    [
        ("local", None, "binding-selection-ambiguous"),
        ("none", None, "binding-not-found"),
        ("local", "ci-kind", "binding-not-found"),
        ("local+ci", "ci-kind", "binding-environment-mismatch"),
    ],
)
def test_a_selection_refusal_is_a_render_refusal_under_its_own_rule(
    bindings: str, binding_name: str | None, rule: str
) -> None:
    """The binding domain's rule identifier and field survive; the category is added."""
    supplied = {
        "local": local_bindings(),
        "none": [],
        "local+ci": [*local_bindings(), ci_binding()],
    }[bindings]
    with pytest.raises(BindingSelectionError) as selected:
        select_environment_binding(
            contract(),
            supplied,
            binding_name=None if binding_name is None else DnsLabel(binding_name),
        )
    with pytest.raises(RenderRefused) as raised:
        render_context(bindings=supplied, binding_name=binding_name)
    assert raised.value.rule_ids() == (rule,)
    assert raised.value.category is RefusalCategory.BINDING_MISSING
    assert raised.value.code == "contract-invalid"
    assert [finding.field for finding in raised.value.findings] == [
        refusal.field for refusal in selected.value.refusals
    ]


def test_the_values_are_read_only() -> None:
    context = secret_refs_context()
    secret_refs = context.value("security.secretRefs")
    assert isinstance(secret_refs, tuple) and secret_refs
    with pytest.raises(TypeError):
        secret_refs[0]["name"] = "changed"
    with pytest.raises(dataclasses.FrozenInstanceError):
        context.fields[0].value = "changed"  # type: ignore[misc]
    with pytest.raises(KeyError):
        context.value("mock.ciOnly")


def test_the_context_is_hashable_and_equal_contexts_hash_alike() -> None:
    assert hash(render_context()) == hash(render_context())
    assert len({render_context(), render_context()}) == 1


# --------------------------------------------------------------------------
# 5. Deterministic and pure
# --------------------------------------------------------------------------


def test_equal_inputs_give_equal_contexts_whatever_the_binding_order() -> None:
    forward = render_context(bindings=local_bindings())
    backward = render_context(bindings=list(reversed(local_bindings())))
    assert forward == backward
    assert forward.digest() == backward.digest()
    assert canonical_json(forward.as_document()) == canonical_json(
        backward.as_document()
    )


@pytest.mark.parametrize(
    ("change", "moved_field", "moved_source"),
    [
        ("contract", "serving.replicas.maximum", "contract"),
        ("binding", "api.replicas", "environmentBinding"),
        ("defaults", "api.requestTimeoutMs", None),
        ("revision", None, "platformDefaults"),
    ],
)
def test_a_change_to_one_input_moves_its_value_and_its_identity_only(
    change: str, moved_field: str | None, moved_source: str | None
) -> None:
    before = render_context().as_document()

    workload_document = contract_document()
    binding_documents = [
        load(path) for path in sorted(BINDING_VALID_DIR.glob("*.yaml"))
    ]
    platform_defaults = defaults()
    if change == "contract":
        workload_document["spec"]["scaling"]["maximumReplicas"] += 1
    elif change == "binding":
        binding_documents[1]["spec"]["platform"]["apiReplicas"] += 1
    elif change == "defaults":
        platform_defaults = defaults(request_timeout_ms=60000)
    else:
        platform_defaults = defaults(revision="c" * 40)
    after = render_context(
        parse_workload_contract(workload_document),
        bindings=[parse_environment_binding(d) for d in binding_documents],
        platform_defaults=platform_defaults,
    ).as_document()

    assert {
        name
        for name in before["fields"]
        if before["fields"][name] != after["fields"][name]
    } == ({moved_field} if moved_field else set())
    assert {
        name
        for name in before["sources"]
        if before["sources"][name] != after["sources"][name]
    } == ({moved_source} if moved_source else set())


def test_the_defaults_values_are_not_in_the_sources() -> None:
    """A limit, recorded: a release names defaults by revision alone.

    Two defaults sets with one revision and different values give contexts whose
    sources agree. The revision is the caller's statement of what it read; the
    boundary has no file to check it against, and a later change that reads the
    defaults from the repository is where that check belongs.
    """
    first = render_context()
    second = render_context(platform_defaults=defaults(request_timeout_ms=60000))
    assert first.sources == second.sources
    assert first.digest() != second.digest()


def test_building_a_context_reads_no_clock_and_no_random_source(monkeypatch) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("the render boundary consulted a clock or a random source")

    workload = contract()
    bindings = local_bindings()
    platform_defaults = defaults()
    expected = render_context().digest()
    for owner, name in [
        (time, "time"),
        (time, "time_ns"),
        (time, "monotonic"),
        (time, "perf_counter"),
        (time, "localtime"),
        (time, "gmtime"),
        (uuid, "uuid1"),
        (uuid, "uuid4"),
        (os, "urandom"),
        (os, "getenv"),
        (random, "random"),
        (random, "getrandbits"),
        (random, "randbytes"),
        (secrets, "token_bytes"),
        (secrets, "token_hex"),
    ]:
        monkeypatch.setattr(owner, name, forbidden)

    context = build_render_context(
        validate_for_render(workload),
        platform_defaults,
        bindings,
        binding_name=DnsLabel("local-kind"),
    )
    assert context.digest() == expected


DIGEST_PROGRAM = """
import json, sys
sys.path[:0] = [{root!r}, {src!r}]
import tests.domain.test_renderer_input_boundary as suite
print(json.dumps([str(context.digest()) for context in suite.every_context()]))
"""


def test_two_interpreters_under_two_hash_seeds_agree() -> None:
    program = DIGEST_PROGRAM.format(root=str(REPO_ROOT), src=str(REPO_ROOT / "src"))
    answers = []
    for seed in ("0", "4242"):
        result = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed},
            timeout=120,
        )
        answers.append(json.loads(result.stdout.strip().splitlines()[-1]))
    assert answers[0] == answers[1]
    assert answers[0] == [str(context.digest()) for context in every_context()]
    assert len(set(answers[0])) == 4


def test_the_canonical_form_holds_no_timestamp_and_no_random_identifier() -> None:
    timestamp = re.compile(r"\d{4}-\d{2}-\d{2}T|\d{2}:\d{2}:\d{2}|GMT")
    identifier = re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    )
    for context in every_context():
        text = canonical_json(context.as_document()).decode("utf-8")
        assert timestamp.search(text) is None
        assert identifier.search(text) is None


def module_trees() -> list[tuple[Path, ast.Module]]:
    return [
        (path, ast.parse(path.read_text(encoding="utf-8")))
        for path in sorted(PACKAGE_DIR.glob("*.py"))
    ]


#: Standard-library modules the package may import, and nothing else.
PERMITTED_STANDARD_LIBRARY = {
    "__future__",
    "collections",
    "dataclasses",
    "enum",
    "re",
    "types",
    "typing",
}

#: The one module that touches a file, and the two modules it may add to the set
#: above. The suite of the generated release holds what it may name.
WRITER_MODULE = "writing.py"
WRITER_STANDARD_LIBRARY = {"os", "pathlib"}

#: Domain packages the package may reach by relative import.
PERMITTED_RELATIVE = {
    "context",
    "environment",
    "release",
    "workload",
}


def test_the_render_package_imports_only_what_a_pure_boundary_needs() -> None:
    """No Kubernetes, Helm, Git, subprocess, socket, file, clock, or random module.

    Every absolute import is one of seven standard-library modules; every relative
    import that leaves the package reaches the workload, environment, or release
    domain, or the request context. ``tools`` is unreachable. Fourteen modules: the
    Helm values renderer and its YAML form joined the ten of the boundary, and the
    generated release and its writer joined those. The writer alone may also import
    ``os`` and ``pathlib``, because writing files is what it is for.
    """
    assert len(module_trees()) == 14
    for path, tree in module_trees():
        permitted = PERMITTED_STANDARD_LIBRARY | (
            WRITER_STANDARD_LIBRARY if path.name == WRITER_MODULE else set()
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] in permitted, (
                        path.name,
                        alias.name,
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    root = (node.module or "").split(".")[0]
                    assert root in permitted, (path.name, root)
                elif node.level == 2:
                    root = (node.module or "").split(".")[0]
                    assert root in PERMITTED_RELATIVE, (path.name, root)
                else:
                    assert node.level == 1, (path.name, node.level)


def test_the_render_package_cannot_import_anything_at_run_time() -> None:
    """No module names a dynamic import, and none but the writer opens a file."""
    dynamic = {"__import__", "importlib", "builtins", "eval", "exec", "open"}
    for path, tree in module_trees():
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        forbidden = dynamic - {"open"} if path.name == WRITER_MODULE else dynamic
        assert (names | attributes).isdisjoint(forbidden), path.name


def test_only_the_writer_and_the_package_index_import_the_writer() -> None:
    """Every other module stays pure: nothing reaches ``os`` through the writer."""
    importers = set()
    for path, tree in module_trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level != 1:
                continue
            # `from .writing import x`, or `from . import writing`.
            if node.module == "writing" or (
                node.module is None
                and any(alias.name == "writing" for alias in node.names)
            ):
                importers.add(path.name)
    assert importers == {"__init__.py"}


RENDER_MODULE = "inferops.domain.render"


def imports_render_package(source: str, package: tuple[str, ...] | None) -> bool:
    """Whether Python source imports ``inferops.domain.render``, by any spelling.

    Read from the syntax tree, so a docstring that names the package is not an
    import. A relative import is resolved against ``package``, the dotted parts of
    the package the source lives in; with no package, relative imports cannot reach
    the distribution and are ignored.
    """
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            if any(alias.name.startswith(RENDER_MODULE) for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                module = node.module or ""
            elif package is None:
                continue
            else:
                base = package[: len(package) - node.level + 1]
                module = ".".join(part for part in (*base, node.module) if part)
            names = {alias.name for alias in node.names}
            if module.startswith(RENDER_MODULE) or (
                module == "inferops.domain" and "render" in names
            ):
                return True
    return False


#: The tools allowed to import the render package, by directory name under
#: ``tools``. Each is a repository check, not a delivery path, and the second test below
#: holds that nothing on a delivery path reaches either in turn.
#:
#: - ``generated_release`` derives the committed generated releases again from their
#:   declared inputs, and writes only a declared release directory in this
#:   repository, when a contributor names it.
#: - ``experiment_e01`` runs the static parts of the V2-E01 experiment as its freeze
#:   record registers them, and writes only a new run directory under
#:   ``docs/proof/experiments/v2-e01/runs/``, when a contributor names a run. Its
#:   ``--check`` reads committed runs and writes nothing. It reads the platform
#:   defaults with the generated-release reader, because the freeze record names
#:   that reader.
#: - ``gitops_desired_state`` verifies the Git desired-state tree and regenerates a
#:   release in it, when a contributor names one. It does not import the render
#:   package: it calls ``generated_release``, which is why it is listed. Its output
#:   is the first that a controller reconciles: one Application reads it, on a
#:   cluster where an operator applied that Application. The second test below
#:   holds that no script, workflow, chart, or distribution module calls it.
#: - ``desired_state_provenance`` reads the desired-state release as one Git commit
#:   holds it and prints its identities. It writes nothing. It does not import the
#:   render package: it names ``generated_release`` and ``gitops_desired_state`` for
#:   the declared releases, which is why it is listed.
REPOSITORY_CHECKS: tuple[str, ...] = (
    "desired_state_provenance",
    "experiment_e01",
    "generated_release",
    "gitops_desired_state",
)

#: The repository checks that import the render package themselves.
RENDER_IMPORTERS: tuple[str, ...] = ("experiment_e01", "generated_release")


def _repository_check(path: Path) -> str | None:
    """The repository check ``path`` belongs to, by directory name, or None."""
    for name in REPOSITORY_CHECKS:
        if REPO_ROOT / "tools" / name in path.parents:
            return name
    return None


def test_nothing_outside_the_render_package_imports_it() -> None:
    """The boundary is not wired to any delivery path: no API, adapter, tool, or script.

    Python modules under ``src`` and ``tools`` are read for imports; shell, YAML, and
    Terraform files under ``scripts``, ``charts``, ``deploy``, and ``infra`` for the
    module path at all. The tools in :data:`REPOSITORY_CHECKS` are exempt by name.
    """
    offenders = []
    exempt: dict[str, list[str]] = {}
    src = REPO_ROOT / "src"
    for path in sorted(src.rglob("*.py")):
        if PACKAGE_DIR in path.parents:
            continue
        package = path.parent.relative_to(src).parts
        if imports_render_package(path.read_text(encoding="utf-8"), package):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    for path in sorted((REPO_ROOT / "tools").rglob("*.py")):
        if imports_render_package(path.read_text(encoding="utf-8"), None):
            check = _repository_check(path)
            if check is not None:
                exempt.setdefault(check, []).append(path.name)
            else:
                offenders.append(path.relative_to(REPO_ROOT).as_posix())
    # Each exemption is used, so none can outlive the tool it names.
    assert exempt == {name: ["core.py"] for name in RENDER_IMPORTERS}
    for root in ("scripts", "charts", "deploy", "infra"):
        for path in sorted((REPO_ROOT / root).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".sh", ".yaml", ".tf"}:
                text = path.read_text(encoding="utf-8", errors="replace")
                if RENDER_MODULE in text:
                    offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == []


def _whole_word(name: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z0-9_]){name}(?![A-Za-z0-9_])")


def test_nothing_on_a_delivery_path_reaches_the_repository_check() -> None:
    """The exempt repository checks are reached from a contributor's shell or the test
    suite, never from the distribution, another tool, a script, a chart, a deployment
    or infrastructure file, a workflow, or the project configuration.

    Every tracked file under those paths is read as text, whatever its suffix, for each
    check's package name as a whole word - which ``tools.generated_release``,
    ``tools/generated_release``, and ``from tools import generated_release`` all hold,
    and ``test_generated_release`` does not. A file inside a repository check is not on
    a delivery path, so it is not read: the E01 run names the generated-release reader.
    """
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    roots = ("src", "tools", "scripts", "charts", "deploy", "infra", ".github")
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", *roots, "pyproject.toml"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    names = {check: _whole_word(check) for check in REPOSITORY_CHECKS}
    offenders: list[str] = []
    for relative in filter(None, listed.split("\0")):
        path = REPO_ROOT / relative
        if _repository_check(path) is not None or not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", errors="replace")
        offenders.extend(
            f"{relative}: {check}"
            for check, pattern in names.items()
            if pattern.search(text)
        )
    assert offenders == []
    # The pattern sees each spelling it names, and not a test module's name.
    for check, pattern in names.items():
        for spelling in (
            f"python -m tools.{check} --check",
            f"tools/{check}/core.py",
            f"from tools import {check}",
        ):
            assert pattern.search(spelling), spelling
        assert not pattern.search(f"tests/domain/test_{check}.py")


@pytest.mark.parametrize(
    "source",
    [
        "import inferops.domain.render\n",
        "from inferops.domain.render import build_render_context\n",
        "from inferops.domain import render\n",
        "from ..domain.render import RenderContext\n",
        "from ..domain import render\n",
    ],
)
def test_the_import_check_finds_each_spelling_of_an_import(source: str) -> None:
    """The check above would find an import if one were added, in each form."""
    assert imports_render_package(source, ("inferops", "api"))


@pytest.mark.parametrize(
    "source",
    [
        '"""Mentions inferops.domain.render in prose."""\n',
        "from .render import render_rules\n",
        "from ..domain import release\n",
    ],
)
def test_the_import_check_ignores_what_is_not_an_import_of_it(source: str) -> None:
    assert not imports_render_package(source, ("inferops", "api"))


# --------------------------------------------------------------------------
# 6. A renderer takes a context
# --------------------------------------------------------------------------


class _EchoRenderer:
    """A renderer of the interface's shape: returns the context's digest."""

    revision = GitRevision(RENDERER_REVISION)
    support = RendererSupport(
        contract_versions=frozenset({"inferops.io/v1alpha1"}),
        binding_versions=frozenset({"inferops.io/v1alpha1"}),
        platform_defaults_versions=frozenset({"v1alpha1"}),
        profiles=frozenset(Profile),
    )

    def render(self, context: RenderContext) -> str:
        return str(context.digest())


class _NotARenderer:
    """Has a revision and a render method, and declares no support."""

    revision = GitRevision(RENDERER_REVISION)

    def render(self, context: RenderContext) -> str:
        return str(context.digest())


def test_a_conforming_object_is_a_renderer_and_others_are_not() -> None:
    assert isinstance(_EchoRenderer(), Renderer)
    assert not isinstance(_NotARenderer(), Renderer)
    renderer: Renderer[str] = _EchoRenderer()
    context = render_context()
    assert renderer.render(context) == renderer.render(render_context())


def test_the_interfaces_one_input_is_a_render_context() -> None:
    hints = typing.get_type_hints(Renderer.render)
    assert hints["context"] is RenderContext
    assert list(hints) == ["context", "return"]
    revision = vars(Renderer)["revision"]
    assert isinstance(revision, property)
    assert typing.get_type_hints(revision.fget)["return"] is GitRevision
