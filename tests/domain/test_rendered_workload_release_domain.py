"""The RenderedWorkloadRelease domain: parsing, the canonical form, and provenance.

Every check reads files from this repository and nothing else. No network, no
cluster, no clock, no randomness - and one test proves the last two by making the
clock and every random source fail while the package computes.

Six things are asserted:

1. **The domain's copy of the schema is the schema**, and its parser refuses what
   the published validator refuses on every committed fixture. No source identity
   can be left out: removing any member of a release is refused at that member.
2. **The canonical form is stable.** It is the evidence index's serialisation byte
   for byte, a pinned value hashes to a pinned digest, it is the same in another
   process under another hash seed, it refuses what has no single JSON spelling -
   a float, a date, an oversized integer - rather than writing it, and a source
   document's digest ignores formatting and follows every value.
3. **Nothing uncontrolled enters it.** Canonical content holds no timestamp and no
   random identifier, and computing it reads neither a clock nor a random source.
4. **Claim-relevant changes move the right result.** Each change to a contract or
   binding moves its digest and the release identifier, and a release recorded
   before the change is refused against the changed document under the rule for
   that document. A change to the output moves the release and not its
   identifier. A change of formatting moves nothing.
5. **Sensitive content is excluded or refused.** The identity carries no output
   and no content; a published credential prefix is refused wherever a release
   can hold one, at the start of a value or after a separator; the cost and the
   remaining gap are measured.
6. **The published rule table is the code's**, adds no canonical code, reuses no
   offline validator or binding identifier, and every rule refuses something.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import datetime
import hashlib
import json
import os
import random
import re
import secrets
import string
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.domain import RequestContext
from inferops.domain.environment import (
    BINDING_RULES,
    SUPPORTED_BINDING_VERSIONS,
    EnvironmentBinding,
    parse_environment_binding,
)
from inferops.domain.release import (
    LARGEST_EXACT_INTEGER,
    PART_SEPARATORS,
    RECORDABLE_BINDING_VERSIONS,
    RECORDABLE_CONTRACT_VERSIONS,
    RELEASE_RULES,
    RENDERED_WORKLOAD_RELEASE_KIND,
    SUPPORTED_RELEASE_VERSIONS,
    CanonicalFormError,
    GitRevision,
    LowercaseSemanticVersion,
    MalformedReleaseError,
    ReleaseError,
    ReleaseId,
    ReleaseRefusal,
    RenderedWorkloadRelease,
    Sha256Hex,
    UnsupportedReleaseVersionError,
    ValuesFileName,
    binding_digest,
    canonical_json,
    canonical_release,
    canonical_sha256,
    check_rendered_workload_release,
    contract_digest,
    credential_positions,
    derive_release_id,
    is_credential_shaped,
    is_supported_release_version,
    parse_rendered_workload_release,
    release_identity,
    verify_release_sources,
)
from inferops.domain.release import release as release_module
from inferops.domain.release.parsing import (
    _BINDING_FIELDS,
    _CONTRACT_FIELDS,
    _HELM_VALUES_FIELDS,
    _METADATA_FIELDS,
    _OUTPUT_FIELDS,
    _REVISION_FIELDS,
    _ROOT_FIELDS,
    _SOURCE_FIELDS,
)
from inferops.domain.workload import (
    SUPPORTED_CONTRACT_VERSIONS,
    DnsLabel,
    Environment,
    ImageReference,
    WorkloadContract,
    parse_workload_contract,
)
from inferops.domain.workload.errors import InvalidValueError
from tools.contract_validation import RULES
from tools.contract_validation import validate as validate_workload_tool
from tools.contract_validation.errors import CANONICAL_ERROR_CODES
from tools.contract_validation.rendered_workload_release import (
    validate as validate_release_tool,
)
from tools.contract_validation.workload import _CREDENTIAL_PREFIXES
from tools.evidence_index.core import entry_sha256

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    REPO_ROOT
    / "contracts"
    / "release"
    / "rendered-workload-release.v1alpha1.schema.json"
)
EXAMPLES = REPO_ROOT / "contracts" / "release" / "examples"
VALID_DIR = EXAMPLES / "valid"
INVALID_DIR = EXAMPLES / "invalid"
MANIFEST_PATH = INVALID_DIR / "expected-rejections.json"
WORKLOAD_VALID_DIR = REPO_ROOT / "contracts" / "workload" / "examples" / "valid"
BINDING_VALID_DIR = REPO_ROOT / "contracts" / "environment" / "examples" / "valid"
CONTRACT_DOC = REPO_ROOT / "docs" / "contracts" / "rendered-workload-release.md"
PACKAGE_DIR = REPO_ROOT / "src" / "inferops" / "domain" / "release"

#: A value and its canonical form and digest, pinned. If the serialisation ever
#: changes, every release identifier and digest a renderer has recorded changes
#: with it, and this is where that becomes a failing test rather than a surprise.
GOLDEN_VALUE = {"b": [1, True, None], "a": "é"}
GOLDEN_BYTES = b'{"a":"\xc3\xa9","b":[1,true,null]}'
GOLDEN_SHA256 = "170409917e32971e79e71df2c0a04cc84c3c089ef0c7c2a94dbde72cafebd52d"

RENDERER = "a" * 40
DEFAULTS = "b" * 40
VALUES_SHA256 = "5" * 64

TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}|GMT")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def schema() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return document


def defs(name: str) -> dict[str, Any]:
    node: dict[str, Any] = schema()["$defs"][name]
    return node


def manifest() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return document


def valid_paths() -> list[Path]:
    return sorted(VALID_DIR.glob("*.yaml"))


def invalid_paths() -> list[Path]:
    return sorted(INVALID_DIR.glob("*.yaml"))


def contract_document(name: str = "synchronous-llm-local") -> dict[str, Any]:
    document: dict[str, Any] = load(WORKLOAD_VALID_DIR / f"{name}.yaml")
    return document


def binding_document(name: str = "local-kind") -> dict[str, Any]:
    document: dict[str, Any] = load(BINDING_VALID_DIR / f"{name}.yaml")
    return document


def contract(name: str = "synchronous-llm-local") -> WorkloadContract:
    return parse_workload_contract(contract_document(name))


def binding(name: str = "local-kind") -> EnvironmentBinding:
    return parse_environment_binding(binding_document(name))


def independent_release_id(document: dict[str, Any]) -> str:
    """The contract document's rule, written out from its words, not the package."""
    identity = {
        "metadata": {
            "workloadId": document["metadata"]["workloadId"],
            "workloadVersion": document["metadata"]["workloadVersion"],
        },
        "source": document["source"],
    }
    return entry_sha256(identity)


def rederive(document: dict[str, Any]) -> dict[str, Any]:
    """The same release with the identifier its (possibly edited) inputs derive."""
    document["metadata"]["releaseId"] = independent_release_id(document)
    return document


def recorded(
    workload: WorkloadContract,
    env: EnvironmentBinding,
    *,
    renderer: str = RENDERER,
    defaults: str = DEFAULTS,
    values_sha256: str = VALUES_SHA256,
) -> dict[str, Any]:
    """The release a renderer would record for these inputs, as a wire document.

    Digests and the identifier come from the package; a test below holds the
    identifier to the independent rule as well.
    """
    source: dict[str, Any] = {
        "contract": {
            "apiVersion": str(workload.api_version),
            "sha256": str(contract_digest(workload)),
        },
        "environmentBinding": {
            "apiVersion": str(env.api_version),
            "environment": env.spec.environment.value,
            "name": str(env.metadata.name),
            "sha256": str(binding_digest(env)),
        },
        "renderer": {"revision": renderer},
        "platformDefaults": {"revision": defaults},
    }
    document: dict[str, Any] = {
        "apiVersion": "inferops.io/v1alpha1",
        "kind": "RenderedWorkloadRelease",
        "metadata": {
            "workloadId": str(workload.workload_id),
            "workloadVersion": str(workload.metadata.version),
            "releaseId": "0" * 64,
        },
        "source": source,
        "output": {
            "helmValues": {"path": "values.generated.yaml", "sha256": values_sha256}
        },
    }
    parsed = parse_rendered_workload_release(document)
    document["metadata"]["releaseId"] = str(
        derive_release_id(
            parsed.metadata.workload_id,
            parsed.metadata.workload_version,
            parsed.source,
        )
    )
    return document


def parsed(document: dict[str, Any]) -> RenderedWorkloadRelease:
    return parse_rendered_workload_release(document)


def rules_of(refusals: list[ReleaseRefusal]) -> list[tuple[str, str]]:
    return [(refusal.rule_id, refusal.field) for refusal in refusals]


def set_path(document: dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    target = document
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value


def get_path(document: dict[str, Any], path: str) -> Any:
    node: Any = document
    for key in path.split("."):
        node = node[key]
    return node


def leaf_paths(node: Any, prefix: str = "") -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield from leaf_paths(value, f"{prefix}.{key}" if prefix else key)
    else:
        yield prefix


def object_paths(node: Any, prefix: str = "") -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{prefix}.{key}" if prefix else key
            yield here
            yield from object_paths(value, here)


def reversed_keys(node: Any) -> Any:
    """The same value with every object's members in the opposite order."""
    if isinstance(node, dict):
        return {key: reversed_keys(node[key]) for key in reversed(list(node))}
    if isinstance(node, list):
        return [reversed_keys(member) for member in node]
    return node


def scalar_strings(node: Any) -> list[str]:
    if isinstance(node, dict):
        return [s for v in node.values() for s in scalar_strings(v)] + [
            k for k in node if isinstance(k, str)
        ]
    if isinstance(node, list):
        return [s for v in node for s in scalar_strings(v)]
    return [node] if isinstance(node, str) else []


# --------------------------------------------------------------------------
# 1. The domain's copy of the schema is the schema, and nothing can be omitted
# --------------------------------------------------------------------------


def test_the_supported_version_and_kind_are_the_schemas():
    properties = schema()["properties"]
    assert (properties["apiVersion"]["const"],) == SUPPORTED_RELEASE_VERSIONS
    assert properties["kind"]["const"] == RENDERED_WORKLOAD_RELEASE_KIND


def test_the_release_is_versioned_apart_from_the_documents_it_names():
    assert SUPPORTED_RELEASE_VERSIONS is not SUPPORTED_CONTRACT_VERSIONS
    assert SUPPORTED_RELEASE_VERSIONS is not SUPPORTED_BINDING_VERSIONS
    assert is_supported_release_version("inferops.io/v1alpha1")
    assert not is_supported_release_version("inferops.io/v1alpha2")
    assert not is_supported_release_version(None)


def test_the_recordable_source_versions_are_the_schemas_and_are_readable():
    """A release records only versions the schema lists and the domain can read."""
    contract_ref = defs("contractReference")["properties"]["apiVersion"]
    binding_ref = defs("environmentBindingReference")["properties"]["apiVersion"]
    assert list(RECORDABLE_CONTRACT_VERSIONS) == contract_ref["enum"]
    assert list(RECORDABLE_BINDING_VERSIONS) == binding_ref["enum"]
    assert set(RECORDABLE_CONTRACT_VERSIONS) <= set(SUPPORTED_CONTRACT_VERSIONS)
    assert set(RECORDABLE_BINDING_VERSIONS) <= set(SUPPORTED_BINDING_VERSIONS)


@pytest.mark.parametrize(
    ("fields", "schema_node"),
    [
        (_ROOT_FIELDS, lambda: schema()),
        (_METADATA_FIELDS, lambda: defs("metadata")),
        (_SOURCE_FIELDS, lambda: defs("source")),
        (_CONTRACT_FIELDS, lambda: defs("contractReference")),
        (_BINDING_FIELDS, lambda: defs("environmentBindingReference")),
        (_REVISION_FIELDS, lambda: defs("renderer")),
        (_REVISION_FIELDS, lambda: defs("platformDefaults")),
        (_OUTPUT_FIELDS, lambda: defs("output")),
        (_HELM_VALUES_FIELDS, lambda: defs("helmValues")),
    ],
    ids=[
        "root",
        "metadata",
        "source",
        "contract",
        "environmentBinding",
        "renderer",
        "platformDefaults",
        "output",
        "helmValues",
    ],
)
def test_every_field_list_is_the_schemas_in_order(fields: tuple[str, ...], schema_node):
    node = schema_node()
    assert list(fields) == list(node["properties"])
    assert sorted(fields) == sorted(node["required"])
    assert node["additionalProperties"] is False


@pytest.mark.parametrize(
    ("kind", "definition"),
    [
        (DnsLabel, "dnsLabel"),
        (Sha256Hex, "sha256"),
        (ReleaseId, "releaseId"),
        (GitRevision, "gitRevision"),
        (LowercaseSemanticVersion, "lowercaseSemanticVersion"),
        (ImageReference, "digestPinnedImageReference"),
        (ValuesFileName, "valuesFileName"),
    ],
    ids=lambda value: value if isinstance(value, str) else value.__name__,
)
def test_every_constrained_string_is_the_schemas(kind, definition: str):
    node = defs(definition)
    assert kind.PATTERN is not None
    assert kind.PATTERN.pattern == node["pattern"]
    fixed = re.fullmatch(r"\^\[0-9a-f\]\{(\d+)\}\$", node["pattern"])
    if fixed:
        # The hexadecimal forms declare no bound; the pattern fixes the length.
        assert "maxLength" not in node
        assert kind.MINIMUM_LENGTH == kind.MAXIMUM_LENGTH == int(fixed.group(1))
    else:
        assert node["maxLength"] == kind.MAXIMUM_LENGTH
        assert node.get("minLength", 1) == kind.MINIMUM_LENGTH


def test_the_environment_vocabulary_is_the_schemas():
    environment = defs("environmentBindingReference")["properties"]["environment"]
    assert [member.value for member in Environment] == environment["enum"]


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_every_valid_fixture_parses_and_rebuilds_to_itself(path: Path):
    document = load(path)
    release = parse_rendered_workload_release(document)
    assert release.as_document() == document
    assert parse_rendered_workload_release(release.as_document()) == release


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_every_invalid_fixture_is_refused_where_the_validator_refuses_it(path: Path):
    entry = manifest()["fixtures"][path.name]
    expected_fields = [e["field"] for e in entry["expected"]]
    expected_codes = {e["code"] for e in entry["expected"]}
    assert validate_release_tool(load(path)), "the published validator must refuse it"
    with pytest.raises(ReleaseError) as refused:
        parse_rendered_workload_release(load(path))
    error = refused.value
    assert error.code in expected_codes
    assert any(
        field == error.field or field.startswith(f"{error.field}.")
        for field in expected_fields
    ), (error.field, expected_fields)


def test_only_the_version_fixture_is_refused_as_an_unsupported_version():
    for path in invalid_paths():
        with pytest.raises(ReleaseError) as refused:
            parse_rendered_workload_release(load(path))
        unsupported = isinstance(refused.value, UnsupportedReleaseVersionError)
        assert unsupported is (path.name == "unsupported-api-version.yaml"), path.name
        if not unsupported:
            assert isinstance(refused.value, MalformedReleaseError)


@pytest.mark.parametrize("path", invalid_paths(), ids=lambda p: p.name)
def test_no_parse_refusal_quotes_a_value_or_a_field_name_from_the_document(path: Path):
    document = load(path)
    vocabulary = set(scalar_strings(schema()))
    with pytest.raises(ReleaseError) as refused:
        parse_rendered_workload_release(document)
    rendered = json.dumps(refused.value.as_dict())
    for value in scalar_strings(document):
        if len(value) >= 6 and value not in vocabulary:
            assert value not in rendered, f"{path.name} echoed a document value"


@pytest.mark.parametrize(
    "path",
    sorted(WORKLOAD_VALID_DIR.glob("*.yaml"))
    + sorted(BINDING_VALID_DIR.glob("*.yaml")),
    ids=lambda p: p.name,
)
def test_a_contract_or_a_binding_is_not_read_as_a_release(path: Path):
    with pytest.raises(MalformedReleaseError):
        parse_rendered_workload_release(load(path))


@pytest.mark.parametrize("document", [None, [], "release", 1])
def test_a_document_that_is_not_an_object_is_refused(document: Any):
    with pytest.raises(MalformedReleaseError):
        parse_rendered_workload_release(document)


def test_a_missing_version_is_never_inferred():
    document = load(valid_paths()[0])
    del document["apiVersion"]
    with pytest.raises(UnsupportedReleaseVersionError):
        parse_rendered_workload_release(document)


def test_the_version_is_refused_before_anything_below_it_is_read():
    document = {"apiVersion": "inferops.io/v1alpha2", "kind": 7, "extra": object()}
    with pytest.raises(UnsupportedReleaseVersionError):
        parse_rendered_workload_release(document)


def every_member_path() -> list[str]:
    return list(object_paths(load(valid_paths()[0])))


@pytest.mark.parametrize("path", every_member_path())
def test_no_member_of_a_release_can_be_omitted(path: str):
    """Every input identity, the identifier, and the output: each is required."""
    document = load(valid_paths()[0])
    keys = path.split(".")
    parent = document if len(keys) == 1 else get_path(document, ".".join(keys[:-1]))
    del parent[keys[-1]]
    assert validate_release_tool(document), "the schema must refuse it as well"
    with pytest.raises(ReleaseError) as refused:
        parse_rendered_workload_release(document)
    if path == "apiVersion":
        assert isinstance(refused.value, UnsupportedReleaseVersionError)
    else:
        assert refused.value.field == f"$.{path}"
        assert refused.value.reason == "required field is missing"


@pytest.mark.parametrize(
    "where", ["", "metadata", "source", "source.renderer", "output.helmValues"]
)
@pytest.mark.parametrize("name", ["generatedAt", "token", "contractContent"])
def test_a_field_a_release_does_not_define_is_refused_without_being_named(
    where: str, name: str
):
    document = load(valid_paths()[0])
    target = document if not where else get_path(document, where)
    target[name] = "placeholder"
    with pytest.raises(MalformedReleaseError) as refused:
        parse_rendered_workload_release(document)
    assert refused.value.field == (f"$.{where}" if where else "$")
    assert name not in json.dumps(refused.value.as_dict())


def release_classes() -> list[type]:
    return [
        value
        for value in vars(release_module).values()
        if isinstance(value, type)
        and dataclasses.is_dataclass(value)
        and value.__module__ == release_module.__name__
    ]


def test_no_attribute_of_a_release_has_a_default():
    """A typed release cannot be built with an input, an identifier, or an output missing."""
    classes = release_classes()
    assert len(classes) == 9
    for kind in classes:
        for field in dataclasses.fields(kind):
            assert field.default is dataclasses.MISSING, (kind.__name__, field.name)
            assert field.default_factory is dataclasses.MISSING, (
                kind.__name__,
                field.name,
            )


def test_the_release_objects_are_frozen():
    release = parsed(load(valid_paths()[0]))
    with pytest.raises(dataclasses.FrozenInstanceError):
        release.metadata.release_id = ReleaseId("0" * 64)  # type: ignore[misc]


def test_no_attribute_could_hold_content_a_time_or_free_text():
    """The typed tree's names are the schema's, and nothing else."""
    names = {
        field.name for kind in release_classes() for field in dataclasses.fields(kind)
    }
    assert names == {
        "api_version",
        "kind",
        "metadata",
        "source",
        "output",
        "workload_id",
        "workload_version",
        "release_id",
        "contract",
        "environment_binding",
        "renderer",
        "platform_defaults",
        "sha256",
        "environment",
        "name",
        "revision",
        "helm_values",
        "path",
    }


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        (Sha256Hex, "A" * 64),
        (Sha256Hex, "sha256:" + "0" * 64),
        (ReleaseId, "3f2c9a1e-7b4d-4e8a-9c61-0d5e2f8a4b17"),
        (GitRevision, "main"),
        (GitRevision, "abc1234"),
        (ValuesFileName, "../values.yaml"),
        (LowercaseSemanticVersion, "1.0.0-RC.1"),
    ],
)
def test_a_value_constructed_directly_refuses_what_the_parser_refuses(kind, value):
    with pytest.raises(InvalidValueError):
        kind(value)


def test_a_release_constructed_directly_must_declare_its_own_kind():
    release = parsed(load(valid_paths()[0]))
    with pytest.raises(InvalidValueError):
        dataclasses.replace(release, kind="WorkloadContract")


def test_a_parse_refusal_carries_the_request_context():
    context = RequestContext(request_id="req-1", correlation_id="cor-1")
    with pytest.raises(ReleaseError) as refused:
        parse_rendered_workload_release({"apiVersion": 1}, context=context)
    assert refused.value.context == context
    assert refused.value.as_dict()["requestId"] == "req-1"


def test_a_version_with_a_non_ascii_digit_is_refused_by_the_domain_only():
    """Measured: JSON Schema reads `\\d` as [0-9]; Python's `re` reads any digit.

    The domain compiles its version pattern with `re.ASCII` and refuses the value.
    The offline validator applies the schema's pattern through Python's `re` and
    accepts it - a consumer in another language would refuse it. The day the
    validator agrees, this has to change.
    """
    document = load(VALID_DIR / "support-assistant-local-kind.yaml")
    document["metadata"]["workloadVersion"] = "1٣.0.0"
    rederive(document)
    assert validate_release_tool(document) == []
    with pytest.raises(MalformedReleaseError) as refused:
        parse_rendered_workload_release(document)
    assert refused.value.field == "$.metadata.workloadVersion"


# --------------------------------------------------------------------------
# 2. The canonical form is stable
# --------------------------------------------------------------------------


def test_the_canonical_form_of_a_pinned_value_is_pinned():
    assert canonical_json(GOLDEN_VALUE) == GOLDEN_BYTES
    assert str(canonical_sha256(GOLDEN_VALUE)) == GOLDEN_SHA256
    assert hashlib.sha256(GOLDEN_BYTES).hexdigest() == GOLDEN_SHA256


def canonical_subjects() -> list[Any]:
    subjects: list[Any] = [GOLDEN_VALUE]
    subjects += [load(p) for p in sorted(WORKLOAD_VALID_DIR.glob("*.yaml"))]
    subjects += [load(p) for p in sorted(BINDING_VALID_DIR.glob("*.yaml"))]
    subjects += [load(p) for p in valid_paths()]
    return subjects


@pytest.mark.parametrize("value", canonical_subjects())
def test_the_canonical_form_is_the_evidence_indexs_byte_for_byte(value: Any):
    """One serialisation in the repository, written twice and held together."""
    assert str(canonical_sha256(value)) == entry_sha256(value)


def test_key_order_does_not_move_the_canonical_form():
    for value in canonical_subjects():
        assert canonical_json(reversed_keys(value)) == canonical_json(value)


@pytest.mark.parametrize(
    ("value", "location"),
    [
        (1.5, "$"),
        (2.0, "$"),
        ({"count": float("nan")}, "$.count"),
        (datetime.date(2026, 9, 30), "$"),
        ({"at": datetime.datetime(2026, 9, 30, 10, 15)}, "$.at"),
        (LARGEST_EXACT_INTEGER + 1, "$"),
        ([-(LARGEST_EXACT_INTEGER + 1)], "$[0]"),
        ({1: "one"}, "$"),
        ((1, 2), "$"),
        ({"a", "b"}, "$"),
        (b"bytes", "$"),
        ({"text": "\ud800"}, "$.text"),
    ],
    ids=[
        "float",
        "integral-float",
        "nan",
        "date",
        "datetime",
        "integer-too-large",
        "integer-too-small",
        "non-string-key",
        "tuple",
        "set",
        "bytes",
        "lone-surrogate",
    ],
)
def test_a_value_with_no_single_json_spelling_is_refused(value: Any, location: str):
    with pytest.raises(CanonicalFormError) as refused:
        canonical_json(value)
    assert refused.value.location == location


def test_the_exact_integer_bounds_are_accepted():
    # Pinned as a literal, so an off-by-one in the constant is a failure here.
    assert LARGEST_EXACT_INTEGER == 9007199254740991
    assert canonical_json([LARGEST_EXACT_INTEGER, -LARGEST_EXACT_INTEGER]) == (
        f"[{LARGEST_EXACT_INTEGER},-{LARGEST_EXACT_INTEGER}]".encode()
    )


def test_an_unquoted_yaml_date_cannot_enter_a_canonical_form():
    """YAML reads it as a date; the canonical form refuses it rather than write it."""
    document = yaml.safe_load("renderedAt: 2026-09-30\n")
    assert isinstance(document["renderedAt"], datetime.date)
    with pytest.raises(CanonicalFormError) as refused:
        canonical_json(document)
    assert "2026" not in str(refused.value)


def test_a_canonical_refusal_names_where_and_never_what():
    with pytest.raises(CanonicalFormError) as refused:
        canonical_json({"secret": {"nested": 123.456}})
    assert "123.456" not in str(refused.value)
    assert refused.value.location == "$.secret.nested"


@pytest.mark.parametrize(
    "name", ["synchronous-llm-local", "synchronous-llm-secret-refs", "mock-llm-ci"]
)
def test_a_contract_digest_is_of_its_value_not_its_bytes(name: str):
    """Comments, key order, layout, and quoting do not move it."""
    text = (WORKLOAD_VALID_DIR / f"{name}.yaml").read_text(encoding="utf-8")
    original = contract_digest(parse_workload_contract(yaml.safe_load(text)))
    uncommented = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    reflowed = yaml.safe_dump(
        reversed_keys(yaml.safe_load(text)), default_flow_style=True, width=4096
    )
    for variant in (uncommented, reflowed, text.replace("\n", "\n\n")):
        assert contract_digest(parse_workload_contract(yaml.safe_load(variant))) == (
            original
        )


@pytest.mark.parametrize("name", ["local-kind", "local-docker-desktop"])
def test_a_binding_digest_is_of_its_value_not_its_bytes(name: str):
    text = (BINDING_VALID_DIR / f"{name}.yaml").read_text(encoding="utf-8")
    original = binding_digest(parse_environment_binding(yaml.safe_load(text)))
    reflowed = yaml.safe_dump(reversed_keys(yaml.safe_load(text)), sort_keys=False)
    # An integral float is an integer to JSON Schema, and the parser reads it as one.
    as_float = re.sub(r"(apiReplicas: \d+)\n", r"\1.0\n", text)
    assert as_float != text and "apiReplicas: " in text
    for variant in (reflowed, as_float):
        assert binding_digest(parse_environment_binding(yaml.safe_load(variant))) == (
            original
        )


@pytest.mark.parametrize(
    "name", ["synchronous-llm-local", "synchronous-llm-secret-refs", "mock-llm-ci"]
)
def test_a_contract_digest_is_the_canonical_digest_of_the_committed_document(name):
    """The parsed object loses nothing, so the digest names what the file says."""
    document = contract_document(name)
    digest = contract_digest(parse_workload_contract(document))
    assert str(digest) == entry_sha256(document)


@pytest.mark.parametrize("name", ["local-kind", "local-docker-desktop"])
def test_a_binding_digest_is_the_canonical_digest_of_the_committed_document(name):
    document = binding_document(name)
    digest = binding_digest(parse_environment_binding(document))
    assert str(digest) == entry_sha256(document)


def test_a_digest_is_taken_only_of_a_parsed_document():
    with pytest.raises(TypeError):
        contract_digest(contract_document())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        binding_digest(binding_document())  # type: ignore[arg-type]


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_the_derived_identifier_is_the_published_rules(path: Path):
    document = load(path)
    release = parsed(document)
    derived = derive_release_id(
        release.metadata.workload_id,
        release.metadata.workload_version,
        release.source,
    )
    assert str(derived) == independent_release_id(document)
    assert derived == release.metadata.release_id


PROBE = """
import json, sys, yaml
from inferops.domain.release import (
    binding_digest, canonical_release, contract_digest, derive_release_id,
    parse_rendered_workload_release,
)
from inferops.domain.workload import parse_workload_contract
from inferops.domain.environment import parse_environment_binding
out = {}
for path in sys.argv[1:]:
    document = yaml.safe_load(open(path, encoding="utf-8"))
    kind = document["kind"]
    if kind == "WorkloadContract":
        out[path] = str(contract_digest(parse_workload_contract(document)))
    elif kind == "EnvironmentBinding":
        out[path] = str(binding_digest(parse_environment_binding(document)))
    else:
        r = parse_rendered_workload_release(document)
        out[path] = [
            str(derive_release_id(
                r.metadata.workload_id, r.metadata.workload_version, r.source)),
            canonical_release(r).hex(),
        ]
print(json.dumps(out, sort_keys=True))
"""


def test_every_digest_and_identifier_is_the_same_in_another_process():
    """Two interpreters, two hash seeds, one answer: nothing depends on set order."""
    paths = [
        str(p)
        for p in sorted(WORKLOAD_VALID_DIR.glob("*.yaml"))
        + sorted(BINDING_VALID_DIR.glob("*.yaml"))
        + valid_paths()
    ]
    outputs = []
    for seed in ("0", "4242"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-c", PROBE, *paths],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        outputs.append(json.loads(result.stdout))
    assert outputs[0] == outputs[1]
    here = outputs[0]
    for path in valid_paths():
        release = parsed(load(path))
        assert here[str(path)] == [
            str(release.metadata.release_id),
            canonical_release(release).hex(),
        ]


# --------------------------------------------------------------------------
# 3. Nothing uncontrolled enters the canonical content
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_canonical_content_holds_no_timestamp_and_no_random_identifier(path: Path):
    release = parsed(load(path))
    identity = release_identity(
        release.metadata.workload_id, release.metadata.workload_version, release.source
    )
    for content in (canonical_release(release), canonical_json(identity)):
        text = content.decode("utf-8")
        assert TIMESTAMP.search(text) is None
        assert UUID.search(text) is None


def test_computing_provenance_reads_no_clock_and_no_random_source(monkeypatch):
    """Every clock and random source fails while the package does all its work."""

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("provenance consulted a clock or a random source")

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
        (random, "random"),
        (random, "getrandbits"),
        (random, "randbytes"),
        (secrets, "token_bytes"),
        (secrets, "token_hex"),
    ]:
        monkeypatch.setattr(owner, name, forbidden)

    workload = contract()
    env = binding()
    document = recorded(workload, env)
    release = parsed(document)
    assert check_rendered_workload_release(release) == []
    assert verify_release_sources(release, workload, env) == []
    assert canonical_release(release) == canonical_release(
        parsed(recorded(workload, env))
    )


def test_two_recordings_of_the_same_inputs_are_one_document():
    first = parsed(recorded(contract(), binding()))
    second = parsed(recorded(contract(), binding()))
    assert canonical_release(first) == canonical_release(second)
    assert first == second


def test_a_random_identifier_of_the_right_shape_is_now_refused():
    """The gap the schema measures - an underived identifier - is closed here."""
    document = load(VALID_DIR / "support-assistant-local-kind.yaml")
    document["metadata"]["releaseId"] = "0123456789abcdef" * 4
    assert validate_release_tool(document) == [], "the schema still accepts it"
    assert rules_of(check_rendered_workload_release(parsed(document))) == [
        ("release-id-not-derived", "release.metadata.releaseId")
    ]


# --------------------------------------------------------------------------
# 4. Claim-relevant changes move the right result, and nothing else does
# --------------------------------------------------------------------------

#: Every member of a release's workload identity and source.
IDENTITY_MUTATIONS: dict[str, Any] = {
    "metadata.workloadId": "support-assistant-two",
    "metadata.workloadVersion": "0.1.1",
    "source.contract.sha256": "c" * 64,
    "source.environmentBinding.environment": "dev",
    "source.environmentBinding.name": "local-other",
    "source.environmentBinding.sha256": "d" * 64,
    "source.renderer.revision": "e" * 40,
    "source.platformDefaults.revision": "f" * 40,
}


def test_the_mutation_table_covers_every_identity_member_that_can_change():
    """Every leaf under metadata and source, except the identifier and the two
    apiVersions, which have one recordable value each and so cannot be changed."""
    document = load(valid_paths()[0])
    leaves = {
        path
        for path in leaf_paths(document)
        if path.startswith(("metadata.", "source."))
    }
    unchangeable = {
        "metadata.releaseId",
        "source.contract.apiVersion",
        "source.environmentBinding.apiVersion",
    }
    assert set(IDENTITY_MUTATIONS) == leaves - unchangeable
    assert len(RECORDABLE_CONTRACT_VERSIONS) == len(RECORDABLE_BINDING_VERSIONS) == 1


@pytest.mark.parametrize("path", sorted(IDENTITY_MUTATIONS))
def test_every_identity_change_moves_the_release_identifier(path: str):
    document = load(VALID_DIR / "support-assistant-local-kind.yaml")
    before = parsed(document).metadata.release_id
    set_path(document, path, IDENTITY_MUTATIONS[path])
    release = parsed(document)
    after = derive_release_id(
        release.metadata.workload_id, release.metadata.workload_version, release.source
    )
    assert after != before
    # The recorded identifier is now stale, and the single-release rule says so.
    assert rules_of(check_rendered_workload_release(release)) == [
        ("release-id-not-derived", "release.metadata.releaseId")
    ]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("output.helmValues.path", "values.other.yaml"),
        ("output.helmValues.sha256", "9" * 64),
    ],
)
def test_an_output_change_moves_the_release_and_not_its_identifier(path: str, value):
    """Same identifier, different bytes: same inputs, different output."""
    document = load(VALID_DIR / "support-assistant-local-kind.yaml")
    before = parsed(document)
    set_path(document, path, value)
    after = parsed(document)
    assert check_rendered_workload_release(after) == []
    assert after.metadata.release_id == before.metadata.release_id
    assert canonical_release(after) != canonical_release(before)


#: Changes to what a workload is, each still a valid contract.
CONTRACT_MUTATIONS: dict[str, Any] = {
    "metadata.owner": "team-other",
    "metadata.description": "Another description.",
    "spec.model.runtimeProfile": "balanced",
    "spec.model.modelRef": "another-model",
    "spec.resources.memory": "4Gi",
    "spec.resources.cpu": "4",
    "spec.scaling.maximumReplicas": 2,
    "spec.integrations.telemetry.required": False,
    "spec.security.dataClassification": "confidential",
    "spec.attribution.costCenter": "another-cost-center",
    "spec.synchronousLlm.runtime.imageReference": (
        "ghcr.io/ggml-org/llama.cpp@sha256:" + "0" * 64
    ),
    "spec.synchronousLlm.modelArtifact.revision": "0" * 40,
    "spec.synchronousLlm.modelArtifact.sha256": "sha256:" + "0" * 64,
}

#: Changes to what an environment supplies, each still a valid binding.
BINDING_MUTATIONS: dict[str, Any] = {
    "metadata.owner": "someone-else",
    "spec.destination.clusterProvider": "docker-desktop",
    "spec.destination.namespace": "inferops-other",
    "spec.modelCache.claimName": "another-cache",
    "spec.platform.apiReplicas": 2,
    "spec.gitops.destinationPath": "gitops/environments/other",
}


@pytest.mark.parametrize("path", sorted(CONTRACT_MUTATIONS))
def test_a_contract_change_moves_its_digest_and_the_release_and_is_caught(path: str):
    workload, env = contract(), binding()
    before = parsed(recorded(workload, env))
    document = contract_document()
    set_path(document, path, CONTRACT_MUTATIONS[path])
    assert validate_workload_tool(document) == [], "the mutation must stay valid"
    changed = parse_workload_contract(document)
    assert contract_digest(changed) != contract_digest(workload)
    after = parsed(recorded(changed, env))
    assert after.metadata.release_id != before.metadata.release_id
    assert rules_of(verify_release_sources(before, changed, env)) == [
        ("release-contract-digest-mismatch", "release.source.contract.sha256")
    ]
    assert verify_release_sources(after, changed, env) == []


@pytest.mark.parametrize("path", sorted(BINDING_MUTATIONS))
def test_a_binding_change_moves_its_digest_and_the_release_and_is_caught(path: str):
    workload, env = contract(), binding()
    before = parsed(recorded(workload, env))
    document = binding_document()
    set_path(document, path, BINDING_MUTATIONS[path])
    changed = parse_environment_binding(document)
    assert binding_digest(changed) != binding_digest(env)
    after = parsed(recorded(workload, changed))
    assert after.metadata.release_id != before.metadata.release_id
    assert rules_of(verify_release_sources(before, workload, changed)) == [
        (
            "release-binding-digest-mismatch",
            "release.source.environmentBinding.sha256",
        )
    ]
    assert verify_release_sources(after, workload, changed) == []


def test_a_contract_identity_change_is_refused_as_a_mismatch_and_a_digest():
    workload, env = contract(), binding()
    before = parsed(recorded(workload, env))
    document = contract_document()
    document["metadata"]["name"] = "support-assistant-two"
    document["metadata"]["version"] = "0.2.0"
    assert rules_of(
        verify_release_sources(before, parse_workload_contract(document), env)
    ) == [
        ("release-contract-mismatch", "release.metadata.workloadId"),
        ("release-contract-mismatch", "release.metadata.workloadVersion"),
        ("release-contract-digest-mismatch", "release.source.contract.sha256"),
    ]


def test_another_binding_for_the_same_environment_is_refused():
    kind_release = parsed(recorded(contract(), binding("local-kind")))
    assert rules_of(
        verify_release_sources(
            kind_release, contract(), binding("local-docker-desktop")
        )
    ) == [
        ("release-binding-mismatch", "release.source.environmentBinding.name"),
        (
            "release-binding-digest-mismatch",
            "release.source.environmentBinding.sha256",
        ),
    ]


def test_a_contract_and_a_binding_for_different_environments_are_refused():
    ci_contract = contract("mock-llm-ci")
    release = parsed(recorded(contract(), binding()))
    found = rules_of(verify_release_sources(release, ci_contract, binding()))
    assert ("release-environment-mismatch", "contract.spec.environment") in found


def test_a_binding_environment_recorded_wrongly_is_refused():
    document = recorded(contract(), binding())
    document["source"]["environmentBinding"]["environment"] = "dev"
    assert rules_of(
        verify_release_sources(parsed(document), contract(), binding())
    ) == [
        (
            "release-binding-mismatch",
            "release.source.environmentBinding.environment",
        )
    ]


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_a_committed_fixture_is_not_a_record_of_its_named_documents(path: Path):
    """Its digests are placeholders, so beside the documents it names, both refuse.

    The fixture names real identities; only the digests are repeated characters.
    This is the measured statement that neither is a record of a render.
    """
    document = load(path)
    env = binding(document["source"]["environmentBinding"]["name"])
    assert rules_of(verify_release_sources(parsed(document), contract(), env)) == [
        ("release-contract-digest-mismatch", "release.source.contract.sha256"),
        (
            "release-binding-digest-mismatch",
            "release.source.environmentBinding.sha256",
        ),
    ]


def test_verification_changes_neither_the_release_nor_its_sources():
    workload, env = contract(), binding()
    release = parsed(recorded(workload, env))
    snapshots = [copy.deepcopy(x.as_document()) for x in (release, workload, env)]
    verify_release_sources(release, workload, env)
    check_rendered_workload_release(release)
    assert [x.as_document() for x in (release, workload, env)] == snapshots


@pytest.mark.parametrize(
    "arguments",
    [
        ("release", "contract", "binding"),
        ("parsed", "document", "binding"),
        ("parsed", "contract", "document"),
    ],
)
def test_raw_documents_cannot_take_the_supported_path(arguments):
    workload, env = contract(), binding()
    document = recorded(workload, env)
    values: dict[str, Callable[[], Any]] = {
        "release": lambda: document,
        "parsed": lambda: parsed(document),
        "contract": lambda: workload,
        "binding": lambda: env,
        "document": lambda: {"kind": "WorkloadContract"},
    }
    with pytest.raises(TypeError):
        verify_release_sources(*(values[name]() for name in arguments))
    with pytest.raises(TypeError):
        check_rendered_workload_release(document)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# 5. Sensitive content is excluded or refused
# --------------------------------------------------------------------------


def test_the_identity_carries_no_output_and_no_document_content():
    release = parsed(load(valid_paths()[0]))
    identity = release_identity(
        release.metadata.workload_id, release.metadata.workload_version, release.source
    )
    assert set(identity) == {"metadata", "source"}
    assert set(identity["metadata"]) == {"workloadId", "workloadVersion"}
    assert identity["source"] == release.source.as_document()
    assert "output" not in canonical_json(identity).decode()


#: Credential shapes the schema cannot refuse, shortened: each is a published
#: prefix followed by a short run of zeros, which is all the rule looks at.
LOWERCASE_SHAPES = ["sk-0000", "glpat-0000", "gldt-0000", "xoxb-0000"]

#: Every place a lowercase shape can sit in a release, at the start of a value
#: and behind a separator. The WorkloadContract's heuristic alone sees only the
#: first kind; the release rule sees both.
PLACEMENTS: dict[str, list[str]] = {
    "metadata.workloadId": ["{}", "support-{}"],
    "metadata.workloadVersion": [
        "0.1.0-{}",
        "0.1.0-rc.{}",
        "0.1.0+{}",
        # The digest-pinned image reference form: a path segment, and a part of
        # one behind the `_` its pattern admits.
        "registry.example/org/{}@sha256:" + "0" * 64,
        "registry.example/org/app_{}@sha256:" + "0" * 64,
    ],
    "source.environmentBinding.name": ["{}", "local-{}"],
    "output.helmValues.path": ["{}.yaml", "values.{}.yaml"],
}


@pytest.mark.parametrize("shape", LOWERCASE_SHAPES, ids=lambda s: s.split("-")[0])
@pytest.mark.parametrize(
    ("field", "template"),
    [(field, t) for field, templates in PLACEMENTS.items() for t in templates],
)
def test_a_lowercase_credential_shape_is_refused_wherever_it_sits(
    field: str, template: str, shape: str
):
    document = load(VALID_DIR / "support-assistant-local-docker-desktop.yaml")
    set_path(document, field, template.format(shape))
    rederive(document)
    assert validate_release_tool(document) == [], "the schema accepts it"
    refusals = check_rendered_workload_release(parsed(document))
    assert rules_of(refusals) == [
        ("release-value-credential-shaped", f"release.{field}")
    ]
    assert template.format(shape) not in json.dumps([r.as_dict() for r in refusals])


@pytest.mark.parametrize("prefix", ["ghp_", "hf_", "npm_", "sk_live_", "doo_v1_"])
@pytest.mark.parametrize(
    "template",
    [
        "registry.example/org/{}0000@sha256:" + "0" * 64,
        "registry.example/org/app_{}0000@sha256:" + "0" * 64,
    ],
)
def test_an_underscore_shape_in_an_image_reference_passes_the_schema_only(
    template: str, prefix: str
):
    """Measured: the image reference's path admits `_`, so the schema takes these."""
    document = load(VALID_DIR / "support-assistant-local-docker-desktop.yaml")
    document["metadata"]["workloadVersion"] = template.format(prefix)
    rederive(document)
    assert validate_release_tool(document) == [], "the schema accepts it"
    assert rules_of(check_rendered_workload_release(parsed(document))) == [
        ("release-value-credential-shaped", "release.metadata.workloadVersion")
    ]


def reachable(field: str, value: str) -> bool:
    document = load(VALID_DIR / "support-assistant-local-docker-desktop.yaml")
    set_path(document, field, value)
    try:
        parsed(document)
    except ReleaseError:
        return False
    return True


def test_every_published_prefix_a_field_can_hold_is_refused_there():
    """No prefix reaches a release field without the rule seeing it."""
    reached: set[str] = set()
    for field, templates in PLACEMENTS.items():
        for template in templates:
            for prefix in _CREDENTIAL_PREFIXES:
                value = template.format(f"{prefix}0000")
                if not reachable(field, value):
                    continue
                reached.add(prefix)
                assert is_credential_shaped(value), (field, value)
    # Every lowercase prefix: those built from letters, digits, and a hyphen or a
    # dot reach several fields; those with an underscore reach only the image
    # reference form of the workload version.
    assert reached == {
        "doo_v1_",
        "dop_v1_",
        "ghp_",
        "ghr_",
        "ghs_",
        "ghu_",
        "gho_",
        "github_pat_",
        "gldt-",
        "glpat-",
        "hf_",
        "npm_",
        "pk_live_",
        "rk_live_",
        "shpat_",
        "shpss_",
        "sk-",
        "sk_live_",
        "sk_test_",
        "xoxa-",
        "xoxb-",
        "xoxp-",
        "xoxr-",
        "xoxs-",
        "ya29.",
    }
    assert len(reached) == 25
    assert reached == {p for p in _CREDENTIAL_PREFIXES if p == p.lower()}


def test_no_published_prefix_fits_a_hexadecimal_field():
    """Every prefix has a character outside 0-9a-f, so digests and revisions refuse it."""
    for prefix in _CREDENTIAL_PREFIXES:
        assert set(prefix) - set("0123456789abcdef"), prefix


def test_the_positions_are_every_separator_an_accepted_form_admits():
    assert credential_positions("0.1.0-rc.sk-0") == (
        "0.1.0-rc.sk-0",
        "1.0-rc.sk-0",
        "0-rc.sk-0",
        "rc.sk-0",
        "sk-0",
        "0",
    )
    # Which punctuation some accepted form admits, found by asking each form's
    # own type rather than by reading its pattern.
    digest = "0" * 64
    candidates = [
        (DnsLabel, "a{}b"),
        (LowercaseSemanticVersion, "0{}1{}0"),
        (LowercaseSemanticVersion, "0.1.0{}a"),
        (LowercaseSemanticVersion, "0.1.0-a{}b"),
        (ValuesFileName, "a{}b.yaml"),
        (ImageReference, "reg.io/a{}b@sha256:" + digest),
        (ImageReference, "reg.io{}a/b@sha256:" + digest),
        (ImageReference, "reg.io{}5000/a/b@sha256:" + digest),
        (ImageReference, "reg.io/a/b{}sha256:" + digest),
    ]
    admitted = set()
    for character in string.punctuation:
        for kind, template in candidates:
            try:
                kind(template.replace("{}", character))
            except InvalidValueError:
                continue
            admitted.add(character)
    assert admitted == set(PART_SEPARATORS)


def committed_names() -> list[str]:
    names = ["values.generated.yaml"]
    for path in sorted(WORKLOAD_VALID_DIR.glob("*.yaml")):
        document = load(path)
        names += [document["metadata"]["name"], document["metadata"]["version"]]
    for path in sorted(BINDING_VALID_DIR.glob("*.yaml")):
        names.append(load(path)["metadata"]["name"])
    return names


@pytest.mark.parametrize("name", committed_names())
def test_no_committed_identity_is_mistaken_for_a_credential(name: str):
    assert not is_credential_shaped(name)


@pytest.mark.parametrize("path", valid_paths(), ids=lambda p: p.name)
def test_every_committed_release_passes_the_single_release_rules(path: Path):
    assert check_rendered_workload_release(parsed(load(path))) == []


@pytest.mark.parametrize("name", ["sk-demo", "task-sk-demo"])
def test_the_cost_a_workload_name_the_contract_accepts_has_no_release(name: str):
    """Measured, like the uppercase narrowing: the contract takes it, a release not."""
    document = contract_document()
    document["metadata"]["name"] = name
    assert validate_workload_tool(document) == []
    workload = parse_workload_contract(document)
    release = parsed(recorded(workload, binding()))
    assert rules_of(check_rendered_workload_release(release)) == [
        ("release-value-credential-shaped", "release.metadata.workloadId")
    ]


def test_the_remaining_gap_is_a_gap():
    """A lowercase token with no published prefix has the shape of a name.

    The heuristic's other branch needs mixed case, which no release string can
    hold, so nothing here can tell such a token from an identifier. The day a
    change closes this, it has to say so here.
    """
    unprefixed = "q7x2k9m4v8c1z6b3n5w0"
    document = load(VALID_DIR / "support-assistant-local-docker-desktop.yaml")
    document["metadata"]["workloadId"] = unprefixed
    rederive(document)
    assert check_rendered_workload_release(parsed(document)) == []


# --------------------------------------------------------------------------
# 6. The published rule table is the code's
# --------------------------------------------------------------------------


def every_refusal() -> list[ReleaseRefusal]:
    found: list[ReleaseRefusal] = []
    underived = load(valid_paths()[0])
    underived["metadata"]["releaseId"] = "0" * 64
    found += check_rendered_workload_release(parsed(underived))
    shaped = load(valid_paths()[0])
    shaped["metadata"]["workloadId"] = "sk-0000"
    found += check_rendered_workload_release(parsed(rederive(shaped)))
    stale = parsed(load(valid_paths()[0]))
    found += verify_release_sources(stale, contract("mock-llm-ci"), binding())
    wrong = parsed(recorded(contract(), binding("local-kind")))
    found += verify_release_sources(wrong, contract(), binding("local-docker-desktop"))
    return found


def test_every_published_rule_refuses_something():
    """A rule nothing provokes is a rule nobody has seen refuse anything."""
    assert {refusal.rule_id for refusal in every_refusal()} == set(RELEASE_RULES)


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
        for value in document_values | {"sk-0000"}:
            assert value not in rendered, (refusal.rule_id, value)


def test_refusals_are_sorted_and_carry_the_request_context():
    context = RequestContext(request_id="req-2")
    stale = parsed(load(valid_paths()[0]))
    refusals = verify_release_sources(
        stale, contract("mock-llm-ci"), binding(), context=context
    )
    assert len(refusals) > 1
    assert [r.field for r in refusals] == sorted(r.field for r in refusals)
    assert all(r.context == context for r in refusals)
    assert refusals[0].as_dict()["requestId"] == "req-2"
    # The single-release rules carry it too, each of them.
    both = load(valid_paths()[0])
    both["metadata"]["workloadId"] = "sk-0000"
    alone = check_rendered_workload_release(parsed(both), context=context)
    assert {r.rule_id for r in alone} == {
        "release-id-not-derived",
        "release-value-credential-shaped",
    }
    assert all(r.context == context for r in alone)


def test_no_canonical_code_was_added():
    assert {rule.code for rule in RELEASE_RULES.values()} == {"contract-invalid"}
    assert MalformedReleaseError.code in CANONICAL_ERROR_CODES
    assert UnsupportedReleaseVersionError.code in CANONICAL_ERROR_CODES


def test_no_release_rule_reuses_an_offline_validator_or_binding_identifier():
    assert set(RELEASE_RULES).isdisjoint(RULES)
    assert set(RELEASE_RULES).isdisjoint(BINDING_RULES)


def test_an_unpublished_rule_cannot_be_cited():
    with pytest.raises(KeyError):
        ReleaseRefusal("release.metadata", "release-invented", "no such rule")


def published_rule_rows() -> list[list[str]]:
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    start = text.index("The table below is every rule the platform domain applies")
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


def test_the_document_publishes_every_release_rule_with_its_code():
    published = {row[0].strip("`"): row[1].strip("`") for row in published_rule_rows()}
    assert published == {rule: r.code for rule, r in RELEASE_RULES.items()}


def test_the_offline_validator_is_still_structural_only():
    """The domain's rules are not the validator's: a bare-schema consumer and the
    published validator still agree, and neither applies a rule in this table."""
    underived = load(valid_paths()[0])
    underived["metadata"]["releaseId"] = "0" * 64
    assert validate_release_tool(underived) == []


# --------------------------------------------------------------------------
# The package imports nothing it should not
# --------------------------------------------------------------------------


def test_the_release_package_imports_only_the_standard_library_and_itself():
    """Every absolute import is the standard library, and none is `os` or `pathlib`.

    Relative imports stay inside `inferops.domain` by construction. This rules out
    a Kubernetes, Helm, or Argo client, a clock or random module, and the
    repository's `tools` package.
    """
    forbidden = {"os", "pathlib", "time", "datetime", "random", "secrets", "uuid"}
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
            assert roots.isdisjoint(forbidden), (path.name, roots)


def test_the_release_package_cannot_import_anything_at_run_time():
    """The import test reads static imports only; this closes the dynamic route.

    No module in the package names `__import__`, `importlib`, `builtins`, `eval`,
    or `exec`, so the clock and random modules the import test forbids cannot be
    reached any other way. Together with the patched-clock test this is what the
    document's "reads no clock and no random source" rests on.
    """
    dynamic = {"__import__", "importlib", "builtins", "eval", "exec"}
    for path in sorted(PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        assert (names | attributes).isdisjoint(dynamic), path.name
