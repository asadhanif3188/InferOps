"""The workload domain model: what parses, what is refused, and what survives.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness. That is not incidental to this
suite — it is the architecture's dependency rule paying for itself. The domain
imports nothing that needs a cluster, so its tests need nothing that needs one.

What this suite establishes: the committed valid fixtures parse; a parsed
document rebuilds byte-for-byte into the document it came from, so nothing is
silently dropped or defaulted; a contract version this package does not implement
is refused before any field below it is read; a document that cannot be
represented is refused with a field location and a constraint; and no refusal
repeats a value read out of the document.

What it does not establish: that a parsed document is one the platform accepts.
The cross-field and matrix rules — the profile and its block, the replica range,
the duplicate secret name, the pasted credential — are the published semantic
layer, and the pipeline that applies them is `V1-S1-001-PR2`. A test here that
asserted one of those would be asserting behaviour this change does not have.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.domain import NO_REQUEST_CONTEXT, RequestContext
from inferops.domain.workload import (
    SUPPORTED_CONTRACT_VERSIONS,
    ContractVersion,
    DataClassification,
    Description,
    DnsLabel,
    Environment,
    InvalidValueError,
    KebabCaseName,
    MalformedWorkloadContractError,
    MockDeterminism,
    Profile,
    RepositoryPath,
    ResourceQuantity,
    SecretProvider,
    SecretRotation,
    ServingCapability,
    UnsupportedContractVersionError,
    WorkloadContractError,
    WorkloadVersion,
    is_supported_contract_version,
    parse_workload_contract,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "contracts" / "workload"
VALID_EXAMPLES_DIR = CONTRACT_DIR / "examples" / "valid"
SCHEMA_PATH = CONTRACT_DIR / "workload-contract.v1alpha1.schema.json"

SUPPORTED_API_VERSION = "inferops.io/v1alpha1"

# Strings short enough to collide with ordinary English in a sentence about a
# field. The same floor the contract suite uses, for the same reason: below it a
# document value is something like "6", "3Gi", or "demo", and a match says
# nothing about disclosure.
MINIMUM_INTERESTING_LENGTH = 8


def valid_example_paths() -> list[Path]:
    return sorted(VALID_EXAMPLES_DIR.glob("*.yaml"))


def load_document(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return document


def example_ids() -> list[str]:
    return [path.stem for path in valid_example_paths()]


@pytest.fixture(params=valid_example_paths(), ids=example_ids())
def valid_document(request) -> dict[str, Any]:
    return load_document(request.param)


@pytest.fixture
def synchronous_document() -> dict[str, Any]:
    return load_document(VALID_EXAMPLES_DIR / "synchronous-llm-local.yaml")


@pytest.fixture
def mock_document() -> dict[str, Any]:
    return load_document(VALID_EXAMPLES_DIR / "mock-llm-ci.yaml")


# --------------------------------------------------------------------------
# There are fixtures to parse, and they are the committed ones
# --------------------------------------------------------------------------


def test_the_committed_valid_fixtures_are_the_ones_this_suite_reads() -> None:
    """A suite that silently found no fixtures would pass by doing nothing."""
    names = set(example_ids())
    assert {"synchronous-llm-local", "mock-llm-ci"} <= names, sorted(names)


def test_every_committed_valid_fixture_parses(valid_document: dict[str, Any]) -> None:
    contract = parse_workload_contract(valid_document)
    assert contract.kind == "WorkloadContract"
    assert str(contract.api_version) == SUPPORTED_API_VERSION


def test_the_synchronous_fixture_parses_into_the_values_it_declares(
    synchronous_document: dict[str, Any],
) -> None:
    contract = parse_workload_contract(synchronous_document)

    assert contract.workload_id == DnsLabel("support-assistant")
    assert contract.owner_id == DnsLabel("team-platform-demo")
    assert contract.tenant_id == DnsLabel("demo")
    assert contract.is_mock is False
    assert contract.spec.profile is Profile.SYNCHRONOUS_LLM
    assert contract.spec.environment is Environment.LOCAL
    assert contract.spec.model.serving_capability is ServingCapability.NATIVE
    assert contract.spec.resources.cpu == ResourceQuantity("6")
    assert contract.spec.resources.accelerator.count == 0
    assert contract.spec.scaling.minimum_replicas == 1
    assert contract.spec.integrations.telemetry.required is True
    assert contract.spec.security.data_classification is DataClassification.INTERNAL
    assert contract.spec.security.secret_refs == ()
    assert contract.spec.mock_llm is None

    profile_block = contract.spec.synchronous_llm
    assert profile_block is not None
    assert profile_block.model_artifact.size_bytes == 1834426016
    assert str(profile_block.model_artifact.sha256).startswith("sha256:")


def test_the_mock_fixture_parses_and_says_it_is_a_mock(
    mock_document: dict[str, Any],
) -> None:
    contract = parse_workload_contract(mock_document)

    assert contract.is_mock is True
    assert contract.spec.environment is Environment.CI
    assert contract.spec.model.serving_capability is ServingCapability.MOCK
    assert contract.spec.synchronous_llm is None

    profile_block = contract.spec.mock_llm
    assert profile_block is not None
    assert profile_block.ci_only is True
    assert profile_block.determinism is MockDeterminism.FIXED_FIXTURE
    assert profile_block.fixture_ref == RepositoryPath(
        "contracts/workload/fixtures/mock-llm-chat-completion.response.json"
    )


def test_the_secret_reference_fixture_parses_every_declared_entry() -> None:
    document = load_document(VALID_EXAMPLES_DIR / "synchronous-llm-secret-refs.yaml")
    contract = parse_workload_contract(document)

    refs = contract.spec.security.secret_refs
    assert len(refs) == 2
    assert refs[0].provider is SecretProvider.KUBERNETES_SECRET
    assert refs[0].rotation is SecretRotation.OWNER_MANAGED
    assert refs[1].provider is SecretProvider.EXTERNAL_SECRET
    assert refs[1].rotation is SecretRotation.PLATFORM_MANAGED

    annotations = contract.metadata.annotations
    assert annotations is not None
    assert annotations["inferops.io/example"] == "secret-reference-shape"


# --------------------------------------------------------------------------
# Nothing is dropped, and nothing is added
# --------------------------------------------------------------------------


def test_a_parsed_fixture_rebuilds_the_document_it_came_from(
    valid_document: dict[str, Any],
) -> None:
    """The property that makes "the domain loses nothing" checkable.

    A field this package forgot to read is a field missing from the rebuilt
    document; a field it defaulted is one that appears where the author wrote
    none. Both fail here rather than in whatever renders a document later.
    """
    contract = parse_workload_contract(copy.deepcopy(valid_document))
    assert contract.as_document() == valid_document


def test_the_rebuilt_document_is_json_serialisable(
    valid_document: dict[str, Any],
) -> None:
    """The wire form is JSON. A domain object that rebuilt something else - an
    enum, a value object, a mapping proxy - would be carrying a Python type into
    a document."""
    rebuilt = parse_workload_contract(valid_document).as_document()
    assert json.loads(json.dumps(rebuilt)) == rebuilt


def test_an_absent_optional_field_stays_absent(
    synchronous_document: dict[str, Any],
) -> None:
    document = copy.deepcopy(synchronous_document)
    del document["metadata"]["description"]

    contract = parse_workload_contract(document)

    assert contract.metadata.description is None
    assert "description" not in contract.as_document()["metadata"]


def test_a_declared_empty_list_is_not_the_same_as_an_absent_one(
    mock_document: dict[str, Any],
) -> None:
    """`proofRefs` absent and `proofRefs: []` are two different documents.

    Both comply, and the mock fixture uses the first. Collapsing them would make
    a rendered document say something its author did not write.
    """
    absent = parse_workload_contract(copy.deepcopy(mock_document))
    assert absent.spec.evidence.proof_refs is None
    assert "proofRefs" not in absent.as_document()["spec"]["evidence"]

    declared = copy.deepcopy(mock_document)
    declared["spec"]["evidence"]["proofRefs"] = []
    parsed = parse_workload_contract(declared)
    assert parsed.spec.evidence.proof_refs == ()
    assert parsed.as_document()["spec"]["evidence"]["proofRefs"] == []


def test_parsing_does_not_mutate_the_document_it_was_given(
    valid_document: dict[str, Any],
) -> None:
    before = copy.deepcopy(valid_document)
    parse_workload_contract(valid_document)
    assert valid_document == before


def test_parsing_the_same_document_twice_produces_equal_objects(
    valid_document: dict[str, Any],
) -> None:
    first = parse_workload_contract(copy.deepcopy(valid_document))
    second = parse_workload_contract(copy.deepcopy(valid_document))
    assert first == second


def test_a_domain_object_is_frozen(synchronous_document: dict[str, Any]) -> None:
    contract = parse_workload_contract(synchronous_document)
    # Through `setattr` rather than as an assignment, so that the frozen dataclass
    # refuses it at run time rather than the type checker refusing to compile the
    # test. There is no `# type: ignore` in this repository, and this is one of the
    # places that would otherwise need the first one.
    attribute = "minimum_replicas"
    with pytest.raises(AttributeError):
        setattr(contract.spec.scaling, attribute, 2)


# --------------------------------------------------------------------------
# Contract-version handling, which is explicit and comes first
# --------------------------------------------------------------------------


def test_exactly_one_contract_version_is_implemented_today() -> None:
    assert SUPPORTED_CONTRACT_VERSIONS == (SUPPORTED_API_VERSION,)
    assert is_supported_contract_version(SUPPORTED_API_VERSION)


@pytest.mark.parametrize(
    "declared",
    [
        "inferops.io/v1alpha2",
        "inferops.io/v1beta1",
        "inferops.io/v1",
        "example.com/v1alpha1",
        "v1alpha1",
        "",
    ],
)
def test_an_unsupported_contract_version_is_refused(
    synchronous_document: dict[str, Any], declared: str
) -> None:
    document = copy.deepcopy(synchronous_document)
    document["apiVersion"] = declared

    with pytest.raises(UnsupportedContractVersionError) as raised:
        parse_workload_contract(document)

    assert raised.value.field == "$.apiVersion"
    assert not is_supported_contract_version(declared)


@pytest.mark.parametrize("declared", [None, 1, ["inferops.io/v1alpha1"]])
def test_a_contract_version_of_the_wrong_type_is_refused(
    synchronous_document: dict[str, Any], declared: object
) -> None:
    document = copy.deepcopy(synchronous_document)
    document["apiVersion"] = declared

    with pytest.raises(UnsupportedContractVersionError):
        parse_workload_contract(document)


def test_an_absent_contract_version_is_refused_rather_than_inferred(
    synchronous_document: dict[str, Any],
) -> None:
    document = copy.deepcopy(synchronous_document)
    del document["apiVersion"]

    with pytest.raises(UnsupportedContractVersionError) as raised:
        parse_workload_contract(document)

    assert raised.value.field == "$.apiVersion"


def test_an_unsupported_version_is_refused_before_anything_below_it_is_read(
    synchronous_document: dict[str, Any],
) -> None:
    """A document of another version is not described in this version's terms.

    The spec below is emptied as well as the version changed. If the version were
    not decided first, the refusal would be about a missing `spec.profile` - a
    field path in a shape this package has no claim over.
    """
    document = copy.deepcopy(synchronous_document)
    document["apiVersion"] = "inferops.io/v1alpha2"
    document["spec"] = {}
    document["metadata"] = {}

    with pytest.raises(UnsupportedContractVersionError) as raised:
        parse_workload_contract(document)

    assert raised.value.field == "$.apiVersion"


def test_a_supported_version_splits_into_group_and_version() -> None:
    version = ContractVersion.parse(SUPPORTED_API_VERSION)
    assert version.group == "inferops.io"
    assert version.version == "v1alpha1"
    assert str(version) == SUPPORTED_API_VERSION


def test_a_document_of_another_kind_is_refused(
    synchronous_document: dict[str, Any],
) -> None:
    document = copy.deepcopy(synchronous_document)
    document["kind"] = "Workload"

    with pytest.raises(MalformedWorkloadContractError) as raised:
        parse_workload_contract(document)

    assert raised.value.field == "$.kind"


# --------------------------------------------------------------------------
# What cannot be represented is refused, with an address
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mutate", "expected_field"),
    [
        pytest.param(
            lambda document: document["metadata"].pop("owner"),
            "$.metadata.owner",
            id="missing-owner",
        ),
        pytest.param(
            lambda document: document["metadata"].pop("name"),
            "$.metadata.name",
            id="missing-name",
        ),
        pytest.param(
            lambda document: document["spec"].pop("resources"),
            "$.spec.resources",
            id="missing-resources",
        ),
        pytest.param(
            lambda document: document["spec"]["integrations"].pop("telemetry"),
            "$.spec.integrations.telemetry",
            id="missing-telemetry",
        ),
        pytest.param(
            lambda document: document["spec"].pop("evidence"),
            "$.spec.evidence",
            id="missing-evidence",
        ),
        pytest.param(
            lambda document: document["spec"].update(profile="asynchronous-llm"),
            "$.spec.profile",
            id="profile-outside-the-vocabulary",
        ),
        pytest.param(
            lambda document: document["spec"].update(environment="preprod"),
            "$.spec.environment",
            id="environment-outside-the-vocabulary",
        ),
        pytest.param(
            lambda document: document["spec"]["security"].update(
                dataClassification="secret"
            ),
            "$.spec.security.dataClassification",
            id="classification-outside-the-vocabulary",
        ),
        pytest.param(
            lambda document: document["metadata"].update(owner="Team-Platform"),
            "$.metadata.owner",
            id="owner-not-dns-safe",
        ),
        pytest.param(
            lambda document: document["metadata"].update(version="1.0"),
            "$.metadata.version",
            id="version-neither-semver-nor-digest",
        ),
        pytest.param(
            lambda document: document["spec"]["scaling"].update(minimumReplicas="1"),
            "$.spec.scaling.minimumReplicas",
            id="replicas-not-an-integer",
        ),
        pytest.param(
            lambda document: document["spec"]["scaling"].update(minimumReplicas=True),
            "$.spec.scaling.minimumReplicas",
            id="replicas-a-boolean",
        ),
        pytest.param(
            lambda document: document["spec"]["scaling"].update(minimumReplicas=-1),
            "$.spec.scaling.minimumReplicas",
            id="replicas-below-the-floor",
        ),
        pytest.param(
            lambda document: document["spec"]["scaling"].update(maximumReplicas=1000),
            "$.spec.scaling.maximumReplicas",
            id="replicas-above-the-ceiling",
        ),
        pytest.param(
            lambda document: document["spec"]["resources"].update(cpu="six"),
            "$.spec.resources.cpu",
            id="resource-quantity-malformed",
        ),
        pytest.param(
            lambda document: document["spec"]["resources"]["accelerator"].update(
                count=65
            ),
            "$.spec.resources.accelerator.count",
            id="accelerator-count-above-the-ceiling",
        ),
        pytest.param(
            lambda document: document["spec"]["evidence"].update(
                runbookRef="/etc/passwd"
            ),
            "$.spec.evidence.runbookRef",
            id="runbook-path-absolute",
        ),
        pytest.param(
            lambda document: document["spec"]["evidence"].update(
                runbookRef="docs/../../secrets/runbook.md"
            ),
            "$.spec.evidence.runbookRef",
            id="runbook-path-traverses",
        ),
        pytest.param(
            lambda document: document["spec"]["integrations"]["telemetry"].update(
                required="yes"
            ),
            "$.spec.integrations.telemetry.required",
            id="required-not-a-boolean",
        ),
        pytest.param(
            lambda document: document["spec"]["synchronousLlm"]["runtime"].update(
                imageReference="ghcr.io/ggml-org/llama.cpp:latest"
            ),
            "$.spec.synchronousLlm.runtime.imageReference",
            id="image-pinned-by-tag",
        ),
        pytest.param(
            lambda document: document["spec"]["synchronousLlm"]["modelArtifact"].update(
                sizeBytes=0
            ),
            "$.spec.synchronousLlm.modelArtifact.sizeBytes",
            id="artifact-size-below-the-floor",
        ),
        pytest.param(
            lambda document: document["spec"]["synchronousLlm"]["modelArtifact"].update(
                sha256="061b54daade076b5"
            ),
            "$.spec.synchronousLlm.modelArtifact.sha256",
            id="artifact-digest-malformed",
        ),
        pytest.param(
            lambda document: document["metadata"].update(
                annotations={"unnamespaced": "value"}
            ),
            "$.metadata.annotations",
            id="annotation-key-unnamespaced",
        ),
        pytest.param(
            lambda document: document["metadata"].update(
                annotations={"inferops.io/example": "x" * 1025}
            ),
            "$.metadata.annotations",
            id="annotation-value-too-long",
        ),
        pytest.param(
            lambda document: document["spec"].update(maxiumumReplicas=2),
            "$.spec",
            id="field-this-version-does-not-define",
        ),
        pytest.param(
            lambda document: document["metadata"].update(description=""),
            "$.metadata.description",
            id="description-below-its-floor",
        ),
    ],
)
def test_a_document_that_cannot_be_represented_is_refused_with_a_location(
    synchronous_document: dict[str, Any], mutate, expected_field: str
) -> None:
    document = copy.deepcopy(synchronous_document)
    mutate(document)

    with pytest.raises(MalformedWorkloadContractError) as raised:
        parse_workload_contract(document)

    assert raised.value.field == expected_field


@pytest.mark.parametrize("document", [None, [], "workload", 7])
def test_a_document_that_is_not_an_object_is_refused(document: object) -> None:
    with pytest.raises(MalformedWorkloadContractError) as raised:
        parse_workload_contract(document)

    assert raised.value.field == "$"


def test_too_many_secret_references_are_refused(
    synchronous_document: dict[str, Any],
) -> None:
    document = copy.deepcopy(synchronous_document)
    document["spec"]["security"]["secretRefs"] = [
        {
            "name": f"secret-{index}",
            "provider": "kubernetes-secret",
            "reference": f"inferops-serving/secret-{index}#key",
            "owner": "team-platform-demo",
            "rotation": "owner-managed",
        }
        for index in range(33)
    ]

    with pytest.raises(MalformedWorkloadContractError) as raised:
        parse_workload_contract(document)

    assert raised.value.field == "$.spec.security.secretRefs"


def test_a_refusal_inside_an_array_names_the_entry_it_came_from(
    synchronous_document: dict[str, Any],
) -> None:
    document = copy.deepcopy(synchronous_document)
    document["spec"]["security"]["secretRefs"] = [
        {
            "name": "model-registry-token",
            "provider": "kubernetes-secret",
            "reference": "inferops-serving/model-registry#token",
            "owner": "team-platform-demo",
            "rotation": "owner-managed",
        },
        {
            "name": "telemetry-ingest-key",
            "provider": "vault",
            "reference": "inferops/telemetry/ingest#key",
            "owner": "team-platform-demo",
            "rotation": "platform-managed",
        },
    ]

    with pytest.raises(MalformedWorkloadContractError) as raised:
        parse_workload_contract(document)

    assert raised.value.field == "$.spec.security.secretRefs[1].provider"


# --------------------------------------------------------------------------
# A refusal never carries a value read out of the document
# --------------------------------------------------------------------------


def schema_vocabulary(node: Any) -> set[str]:
    """Every string the published schema itself publishes.

    Field names, ``$defs`` names, enumerated values, and constants. A refusal is
    allowed to repeat these - it is how it says which values are permitted - and
    a document that uses one is using the schema's word, not disclosing its own.
    """
    found: set[str] = set()
    if isinstance(node, dict):
        for keyword in ("properties", "$defs"):
            member = node.get(keyword)
            if isinstance(member, dict):
                found |= set(member)
        for keyword in ("enum", "required"):
            member = node.get(keyword)
            if isinstance(member, list):
                found |= {entry for entry in member if isinstance(entry, str)}
        constant = node.get("const")
        if isinstance(constant, str):
            found.add(constant)
        for member in node.values():
            found |= schema_vocabulary(member)
    elif isinstance(node, list):
        for member in node:
            found |= schema_vocabulary(member)
    return found


PUBLISHED_VOCABULARY = schema_vocabulary(
    json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
)


def document_strings(value: Any) -> set[str]:
    """Every string of interesting length anywhere in a document."""
    found: set[str] = set()
    if isinstance(value, str):
        if len(value) >= MINIMUM_INTERESTING_LENGTH:
            found.add(value)
    elif isinstance(value, dict):
        for key, member in value.items():
            found |= document_strings(key)
            found |= document_strings(member)
    elif isinstance(value, list):
        for member in value:
            found |= document_strings(member)
    return found


# NEITHER STRING BELOW IS A CREDENTIAL. `AKIAIOSFODNN7EXAMPLE` is the placeholder
# access key published in AWS's own documentation, and the `ghp_` value is that
# prefix followed by a run of zeroes: a shape, deliberately not a plausible value.
# Both are the forms this repository already allowlists for its secret scanner, and
# they appear here so that a refusal can be checked for *not* repeating them.
CREDENTIAL_SHAPED_LOCATOR = "AKIAIOSFODNN7EXAMPLE"
CREDENTIAL_SHAPED_NAME = "ghp_" + "0" * 34


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda document: document["metadata"].update(
                owner="Team-Platform-Demo-With-A-Long-Name"
            ),
            id="owner",
        ),
        pytest.param(
            lambda document: document["spec"]["security"].update(
                secretRefs=[
                    {
                        "name": "model-registry-token",
                        "provider": "kubernetes-secret",
                        "reference": CREDENTIAL_SHAPED_LOCATOR,
                        "owner": "team-platform-demo",
                        "rotation": "not-a-rotation-policy",
                    }
                ]
            ),
            id="secret-entry",
        ),
        pytest.param(
            lambda document: document["metadata"].update(
                annotations={CREDENTIAL_SHAPED_NAME: "value"}
            ),
            id="annotation-key",
        ),
        pytest.param(
            lambda document: document["spec"].update(
                **{CREDENTIAL_SHAPED_NAME: "value"}
            ),
            id="undefined-field-name",
        ),
    ],
)
def test_a_refusal_repeats_nothing_from_the_document(
    synchronous_document: dict[str, Any], mutate
) -> None:
    """The field most likely to be refused for looking wrong is the field most
    likely to hold a secret, and an error is the surface most likely to be logged,
    pasted into a ticket, and kept."""
    document = copy.deepcopy(synchronous_document)
    mutate(document)

    with pytest.raises(WorkloadContractError) as raised:
        parse_workload_contract(document)

    error = raised.value
    surfaces = [str(error), error.reason, error.field, json.dumps(error.as_dict())]
    for value in document_strings(document):
        if value in PUBLISHED_VOCABULARY:
            continue
        for surface in surfaces:
            assert value not in surface, (value, surface)


def test_a_refused_vocabulary_lists_what_is_permitted(
    synchronous_document: dict[str, Any],
) -> None:
    """The permitted set is this package's own published vocabulary, so printing
    it discloses nothing and saves the author a trip to the schema."""
    document = copy.deepcopy(synchronous_document)
    document["spec"]["environment"] = "preprod"

    with pytest.raises(MalformedWorkloadContractError) as raised:
        parse_workload_contract(document)

    for member in Environment:
        assert member.value in raised.value.reason


# --------------------------------------------------------------------------
# Request context, carried when there is one and never invented
# --------------------------------------------------------------------------


def test_a_refusal_carries_the_context_a_caller_supplied(
    synchronous_document: dict[str, Any],
) -> None:
    document = copy.deepcopy(synchronous_document)
    del document["metadata"]["owner"]
    context = RequestContext(
        request_id="00000000-0000-4000-8000-000000000001",
        correlation_id="00000000-0000-4000-8000-000000000002",
    )

    with pytest.raises(WorkloadContractError) as raised:
        parse_workload_contract(document, context=context)

    assert raised.value.context == context
    assert raised.value.as_dict()["requestId"] == context.request_id
    assert raised.value.as_dict()["correlationId"] == context.correlation_id


def test_a_refusal_with_no_context_invents_none(
    synchronous_document: dict[str, Any],
) -> None:
    """Nothing here runs at an edge, so nothing here may generate an identifier."""
    document = copy.deepcopy(synchronous_document)
    del document["metadata"]["owner"]

    with pytest.raises(WorkloadContractError) as raised:
        parse_workload_contract(document)

    assert raised.value.context == NO_REQUEST_CONTEXT
    assert raised.value.context.is_empty
    assert raised.value.as_dict() == {
        "field": "$.metadata.owner",
        "reason": raised.value.reason,
    }


def test_an_unsupported_version_carries_the_context_too(
    synchronous_document: dict[str, Any],
) -> None:
    document = copy.deepcopy(synchronous_document)
    document["apiVersion"] = "inferops.io/v1alpha2"
    context = RequestContext(correlation_id="00000000-0000-4000-8000-000000000003")

    with pytest.raises(UnsupportedContractVersionError) as raised:
        parse_workload_contract(document, context=context)

    assert raised.value.context == context
    assert "requestId" not in raised.value.as_dict()


# --------------------------------------------------------------------------
# Value objects refuse themselves
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["Team-Platform", "team_platform", "-team", "team-", "", "a" * 64, "team platform"],
)
def test_a_dns_label_refuses_a_value_that_is_not_one(value: str) -> None:
    with pytest.raises(InvalidValueError):
        DnsLabel(value)


@pytest.mark.parametrize("value", ["team-platform-demo", "a", "demo", "a" * 63])
def test_a_dns_label_accepts_the_values_the_contract_calls_dns_safe(
    value: str,
) -> None:
    assert str(DnsLabel(value)) == value


def test_a_value_object_refusal_names_the_constraint_and_not_the_value() -> None:
    secret_shaped = CREDENTIAL_SHAPED_LOCATOR
    with pytest.raises(InvalidValueError) as raised:
        DnsLabel(secret_shaped)
    assert secret_shaped not in raised.value.reason


@pytest.mark.parametrize(
    ("value", "digest_pinned"),
    [
        ("0.1.0", False),
        ("1.0.0-alpha.1", False),
        ("2.3.4+build.5", False),
        (
            "ghcr.io/ggml-org/llama.cpp@sha256:"
            "100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384",
            True,
        ),
    ],
)
def test_a_workload_version_keeps_which_of_the_two_forms_it_is(
    value: str, digest_pinned: bool
) -> None:
    version = WorkloadVersion.parse(value)
    assert str(version) == value
    assert version.is_digest_pinned is digest_pinned


@pytest.mark.parametrize(
    "value", ["1.0", "v1.0.0", "latest", "ghcr.io/ggml-org/llama.cpp:latest", ""]
)
def test_a_workload_version_refuses_anything_that_is_neither_form(value: str) -> None:
    with pytest.raises(InvalidValueError):
        WorkloadVersion.parse(value)


def test_a_workload_version_is_one_form_or_the_other_and_never_both() -> None:
    with pytest.raises(InvalidValueError):
        WorkloadVersion()


def test_a_description_is_bounded_but_has_no_format() -> None:
    assert str(Description("a" * 500)) == "a" * 500
    with pytest.raises(InvalidValueError):
        Description("a" * 501)


def test_two_value_objects_of_different_types_are_not_equal() -> None:
    """`DnsLabel` and `KebabCaseName` share a pattern and mean different things.

    An owner identifier and a cost centre are both DNS-safe strings, and putting
    one where the other belongs is exactly the mistake a value object exists to
    stop. The two are held as `object` here because the type checker is right that
    they never overlap - which is the property being asserted.
    """
    dns_label: object = DnsLabel("demo")
    kebab_name: object = KebabCaseName("demo")

    assert dns_label != kebab_name
    assert dns_label == DnsLabel("demo")
