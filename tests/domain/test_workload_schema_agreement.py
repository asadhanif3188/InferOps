"""The domain's copy of the contract, compared to the published contract.

The domain cannot import a JSON Schema validator. ``jsonschema`` is a development
dependency, the distribution declares no runtime dependency at all, and a domain
object that needed one in order to exist would have made validation a
precondition for having a value. So every published format, vocabulary, and bound
is written twice: once in the schema, which is the artifact consumers in any
language validate against, and once in ``inferops.domain.workload.values``, which
is what Python constructs an object with.

Two copies of one fact drift. This suite is why they cannot: it reads the schema
and fails if a single pattern, enumerated value, bound, field list, or required
field disagrees with the domain. A change to the published contract that is not
carried into the domain fails here, and so does the reverse.

Every check reads files from this repository and nothing else. No network, no
cluster, no model, no clock, no randomness.

What this suite does **not** check is the second half of the contract: the
semantic rules the schema cannot express and the conditional requirements under
its ``allOf`` — the profile and its block, the replica range, the compatibility
matrix. Those are not implemented in this change, two tests at the end assert
that they are not, and the pipeline that implements them is `V1-S1-001-PR2`.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.domain.workload import (
    AcceleratorType,
    AnnotationKey,
    AnnotationValue,
    ArtifactFile,
    ArtifactRepository,
    ConstrainedString,
    DataClassification,
    Description,
    DnsLabel,
    Environment,
    ImageReference,
    KebabCaseName,
    MockDeterminism,
    Profile,
    RepositoryPath,
    ResourceQuantity,
    RuntimeProfile,
    SecretLocator,
    SecretProvider,
    SecretRotation,
    SemanticVersion,
    ServingCapability,
    Sha256Digest,
    UpstreamRevision,
    WorkloadContractError,
    parse_workload_contract,
)

# The parser's field lists are private because nothing outside it should read
# them. They are read here for one reason: a list of the fields a contract
# version defines is a copy of the schema, and an uncompared copy drifts.
from inferops.domain.workload import values as domain_values
from inferops.domain.workload.parsing import (
    _ACCELERATOR_FIELDS,
    _ATTRIBUTION_FIELDS,
    _EVIDENCE_FIELDS,
    _INTEGRATION_FIELDS,
    _INTEGRATIONS_FIELDS,
    _METADATA_FIELDS,
    _MOCK_LLM_FIELDS,
    _MODEL_ARTIFACT_FIELDS,
    _MODEL_FIELDS,
    _RESOURCES_FIELDS,
    _ROOT_FIELDS,
    _RUNTIME_FIELDS,
    _SCALING_FIELDS,
    _SECRET_REFERENCE_FIELDS,
    _SECURITY_FIELDS,
    _SPEC_FIELDS,
    _SYNCHRONOUS_LLM_FIELDS,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "contracts" / "workload"
SCHEMA_PATH = CONTRACT_DIR / "workload-contract.v1alpha1.schema.json"
VALID_EXAMPLES_DIR = CONTRACT_DIR / "examples" / "valid"

SCHEMA: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
DEFS: dict[str, Any] = SCHEMA["$defs"]


def resolve(node: dict[str, Any]) -> dict[str, Any]:
    """Follow a local ``$ref``. Every reference in this schema is a local one."""
    while "$ref" in node:
        reference = node["$ref"]
        assert reference.startswith("#/$defs/"), reference
        node = DEFS[reference.removeprefix("#/$defs/")]
    return node


def at(*path: str) -> dict[str, Any]:
    """The schema node at a dotted path through ``$defs`` and ``properties``."""
    node = DEFS[path[0]]
    for step in path[1:]:
        node = resolve(node)["properties"][step]
    return resolve(node)


def load_document(name: str) -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load(
        (VALID_EXAMPLES_DIR / name).read_text(encoding="utf-8")
    )
    return document


# --------------------------------------------------------------------------
# Formats
# --------------------------------------------------------------------------

#: Each domain type beside the schema node it copies its constraints from.
FORMATS: dict[str, tuple[type[ConstrainedString], dict[str, Any]]] = {
    "dnsLabel": (DnsLabel, at("dnsLabel")),
    "kebabCaseName": (KebabCaseName, at("kebabCaseName")),
    "semanticVersion": (SemanticVersion, at("semanticVersion")),
    "digestPinnedImageReference": (ImageReference, at("digestPinnedImageReference")),
    "sha256Digest": (Sha256Digest, at("sha256Digest")),
    "sha256Hex": (UpstreamRevision, at("sha256Hex")),
    "repositoryPath": (RepositoryPath, at("repositoryPath")),
    "kubernetesQuantity": (ResourceQuantity, at("kubernetesQuantity")),
    "metadata.description": (Description, at("metadata", "description")),
    "secretReference.reference": (SecretLocator, at("secretReference", "reference")),
    "modelArtifact.repository": (
        ArtifactRepository,
        at("synchronousLlm", "modelArtifact", "repository"),
    ),
    "modelArtifact.file": (
        ArtifactFile,
        at("synchronousLlm", "modelArtifact", "file"),
    ),
    "annotations.propertyNames": (
        AnnotationKey,
        at("metadata", "annotations")["propertyNames"],
    ),
    "annotations.additionalProperties": (
        AnnotationValue,
        at("metadata", "annotations")["additionalProperties"],
    ),
}


@pytest.mark.parametrize("name", sorted(FORMATS), ids=sorted(FORMATS))
def test_a_domain_format_is_the_published_format(name: str) -> None:
    kind, published = FORMATS[name]
    if "pattern" in published:
        assert kind.PATTERN is not None, name
        assert kind.PATTERN.pattern == published["pattern"], name
    else:
        assert kind.PATTERN is None, name


@pytest.mark.parametrize("name", sorted(FORMATS), ids=sorted(FORMATS))
def test_a_domain_length_bound_is_the_published_bound(name: str) -> None:
    """Compared where the schema declares one.

    Three definitions declare no length bound at all — a semantic version, a
    ``sha256:`` digest, and an upstream revision are bounded by their patterns.
    The domain still carries a maximum for each, because a value object should
    not have to run a regular expression over an unbounded string to refuse it.
    That number is a local guard rather than a published rule, so there is
    nothing here for it to disagree with.
    """
    kind, published = FORMATS[name]
    if "minLength" in published:
        assert published["minLength"] == kind.MINIMUM_LENGTH, name
    if "maxLength" in published:
        assert published["maxLength"] == kind.MAXIMUM_LENGTH, name


def test_the_repository_path_exclusion_is_the_published_one() -> None:
    """The ``not`` clause that keeps a personal filesystem path out of a document."""
    published = at("repositoryPath")["not"]["pattern"]
    assert RepositoryPath.FORBIDDEN is not None
    assert RepositoryPath.FORBIDDEN.pattern == published


# --------------------------------------------------------------------------
# Controlled vocabularies
# --------------------------------------------------------------------------

VOCABULARIES: dict[str, tuple[Any, list[str]]] = {
    "profile": (Profile, at("spec", "profile")["enum"]),
    "environment": (Environment, at("spec", "environment")["enum"]),
    "servingCapability": (
        ServingCapability,
        at("model", "servingCapability")["enum"],
    ),
    "runtimeProfile": (RuntimeProfile, at("model", "runtimeProfile")["enum"]),
    "acceleratorType": (
        AcceleratorType,
        at("resources", "accelerator", "type")["enum"],
    ),
    "dataClassification": (
        DataClassification,
        at("security", "dataClassification")["enum"],
    ),
    "secretProvider": (SecretProvider, at("secretReference", "provider")["enum"]),
    "secretRotation": (SecretRotation, at("secretReference", "rotation")["enum"]),
    "mockDeterminism": (
        MockDeterminism,
        [at("mockLlm", "determinism")["const"]],
    ),
}


@pytest.mark.parametrize("name", sorted(VOCABULARIES), ids=sorted(VOCABULARIES))
def test_a_domain_vocabulary_is_the_published_vocabulary(name: str) -> None:
    kind, published = VOCABULARIES[name]
    assert [member.value for member in kind] == list(published), name


# --------------------------------------------------------------------------
# Bounds
# --------------------------------------------------------------------------

BOUNDS: dict[str, tuple[int, int]] = {
    "minimumReplicas.minimum": (
        domain_values.MINIMUM_REPLICAS_FLOOR,
        at("scaling", "minimumReplicas")["minimum"],
    ),
    "minimumReplicas.maximum": (
        domain_values.MINIMUM_REPLICAS_CEILING,
        at("scaling", "minimumReplicas")["maximum"],
    ),
    "maximumReplicas.minimum": (
        domain_values.MAXIMUM_REPLICAS_FLOOR,
        at("scaling", "maximumReplicas")["minimum"],
    ),
    "maximumReplicas.maximum": (
        domain_values.MAXIMUM_REPLICAS_CEILING,
        at("scaling", "maximumReplicas")["maximum"],
    ),
    "accelerator.count.minimum": (
        domain_values.ACCELERATOR_COUNT_FLOOR,
        at("resources", "accelerator", "count")["minimum"],
    ),
    "accelerator.count.maximum": (
        domain_values.ACCELERATOR_COUNT_CEILING,
        at("resources", "accelerator", "count")["maximum"],
    ),
    "modelArtifact.sizeBytes.minimum": (
        domain_values.ARTIFACT_SIZE_BYTES_FLOOR,
        at("synchronousLlm", "modelArtifact", "sizeBytes")["minimum"],
    ),
    "security.secretRefs.maxItems": (
        domain_values.MAXIMUM_SECRET_REFERENCES,
        at("security", "secretRefs")["maxItems"],
    ),
    "evidence.proofRefs.maxItems": (
        domain_values.MAXIMUM_PROOF_REFERENCES,
        at("evidence", "proofRefs")["maxItems"],
    ),
}


@pytest.mark.parametrize("name", sorted(BOUNDS), ids=sorted(BOUNDS))
def test_a_domain_bound_is_the_published_bound(name: str) -> None:
    domain_bound, published = BOUNDS[name]
    assert domain_bound == published, name


# --------------------------------------------------------------------------
# The fields each contract version defines
# --------------------------------------------------------------------------

FIELD_LISTS: dict[str, tuple[tuple[str, ...], dict[str, Any]]] = {
    "$": (_ROOT_FIELDS, SCHEMA),
    "metadata": (_METADATA_FIELDS, at("metadata")),
    "spec": (_SPEC_FIELDS, at("spec")),
    "model": (_MODEL_FIELDS, at("model")),
    "resources": (_RESOURCES_FIELDS, at("resources")),
    "accelerator": (_ACCELERATOR_FIELDS, at("resources", "accelerator")),
    "scaling": (_SCALING_FIELDS, at("scaling")),
    "integrations": (_INTEGRATIONS_FIELDS, at("integrations")),
    "integration": (_INTEGRATION_FIELDS, at("integration")),
    "security": (_SECURITY_FIELDS, at("security")),
    "secretReference": (_SECRET_REFERENCE_FIELDS, at("secretReference")),
    "attribution": (_ATTRIBUTION_FIELDS, at("attribution")),
    "evidence": (_EVIDENCE_FIELDS, at("evidence")),
    "synchronousLlm": (_SYNCHRONOUS_LLM_FIELDS, at("synchronousLlm")),
    "runtime": (_RUNTIME_FIELDS, at("synchronousLlm", "runtime")),
    "modelArtifact": (_MODEL_ARTIFACT_FIELDS, at("synchronousLlm", "modelArtifact")),
    "mockLlm": (_MOCK_LLM_FIELDS, at("mockLlm")),
}


@pytest.mark.parametrize("name", sorted(FIELD_LISTS), ids=sorted(FIELD_LISTS))
def test_the_fields_the_domain_defines_are_the_fields_the_schema_defines(
    name: str,
) -> None:
    defined, published = FIELD_LISTS[name]
    assert list(defined) == list(published["properties"]), name


@pytest.mark.parametrize("name", sorted(FIELD_LISTS), ids=sorted(FIELD_LISTS))
def test_every_object_the_domain_reads_is_closed_in_the_schema(name: str) -> None:
    """A domain that refused unknown fields where the schema allowed them would
    be stricter than the published contract, which is its own kind of drift."""
    _, published = FIELD_LISTS[name]
    assert published.get("additionalProperties") is False, name


# --------------------------------------------------------------------------
# The fields the schema requires, required
# --------------------------------------------------------------------------


def required_fields(
    node: dict[str, Any], document: dict[str, Any], path: tuple[str, ...]
) -> list[tuple[tuple[str, ...], str]]:
    """Every unconditionally required field, addressed as it is in a document.

    Only the ``required`` list each object declares outright. The conditional
    ones under ``spec.allOf`` — which profile block must be present for which
    profile — are cross-field rules, they are not implemented in this change, and
    a test below asserts that rather than leaving it to be noticed.
    """
    found = [(path, key) for key in node.get("required", [])]
    for key, subschema in node.get("properties", {}).items():
        member = document.get(key)
        if isinstance(member, dict):
            found += required_fields(resolve(subschema), member, (*path, key))
    return found


def required_field_cases() -> list[tuple[str, tuple[str, ...], str]]:
    cases: list[tuple[str, tuple[str, ...], str]] = []
    for name in ("synchronous-llm-local.yaml", "mock-llm-ci.yaml"):
        document = load_document(name)
        for path, key in required_fields(SCHEMA, document, ()):
            cases.append((name, path, key))
    return cases


@pytest.mark.parametrize(
    ("fixture", "path", "key"),
    required_field_cases(),
    ids=[
        f"{name.removesuffix('.yaml')}:{'.'.join((*path, key))}"
        for name, path, key in required_field_cases()
    ],
)
def test_a_field_the_schema_requires_is_required_by_the_parser(
    fixture: str, path: tuple[str, ...], key: str
) -> None:
    """Refused, and at the field's own address.

    The assertion is on the base error rather than on
    ``MalformedWorkloadContractError``, because one of the fields the schema
    requires is ``apiVersion``, and a document with no version is refused as an
    unsupported version rather than as a missing field. That distinction is the
    point of ``versions``, and it is asserted directly in the suite beside this
    one.
    """
    document = load_document(fixture)
    parent: Any = document
    for step in path:
        parent = parent[step]
    del parent[key]

    with pytest.raises(WorkloadContractError) as raised:
        parse_workload_contract(document)

    assert raised.value.field == "$." + ".".join((*path, key))


def test_the_sweep_covers_the_fields_a_reader_would_expect_it_to() -> None:
    """A generated sweep that generated nothing would pass silently."""
    addresses = {
        "$." + ".".join((*path, key)) for _, path, key in required_field_cases()
    }
    assert {
        "$.apiVersion",
        "$.kind",
        "$.metadata.owner",
        "$.spec.resources",
        "$.spec.resources.accelerator.count",
        "$.spec.integrations.telemetry",
        "$.spec.security.secretRefs",
        "$.spec.evidence.runbookRef",
        "$.spec.synchronousLlm.modelArtifact.sha256",
        "$.spec.mockLlm.fixtureRef",
    } <= addresses, sorted(addresses)


# --------------------------------------------------------------------------
# What this change deliberately does not enforce
# --------------------------------------------------------------------------


def test_the_profile_and_its_block_are_not_paired_here() -> None:
    """A cross-field rule, and `V1-S1-001-PR2` is what applies it.

    The schema requires ``synchronousLlm`` under the ``synchronous-llm`` profile
    through a conditional. This parser reads whichever block is present and
    refuses neither its absence nor a mismatched pair, so a document like this one
    parses into an object the validation pipeline will refuse. Asserting it here
    is what stops the boundary being crossed quietly in either direction.
    """
    document = load_document("synchronous-llm-local.yaml")
    del document["spec"]["synchronousLlm"]

    contract = parse_workload_contract(document)

    assert contract.spec.profile is Profile.SYNCHRONOUS_LLM
    assert contract.spec.synchronous_llm is None
    assert contract.spec.mock_llm is None


def test_an_inverted_replica_range_is_not_refused_here() -> None:
    """``replica-range-inverted`` is a published *semantic* rule. Same boundary."""
    document = load_document("synchronous-llm-local.yaml")
    document["spec"]["scaling"] = {"minimumReplicas": 5, "maximumReplicas": 2}

    contract = parse_workload_contract(copy.deepcopy(document))

    assert contract.spec.scaling.minimum_replicas == 5
    assert contract.spec.scaling.maximum_replicas == 2
