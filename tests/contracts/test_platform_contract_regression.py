"""The three surfaces that read a WorkloadContract, held to the same verdict.

A workload document is read in three places in this repository, and each of them
was written by a different story. The published JSON Schema is the structural
half, and any draft 2020-12 validator in any language applies it. The offline
validator in ``tools.contract_validation`` applies that schema and the semantic
rules JSON Schema cannot express. The platform domain in
``inferops.domain.workload`` parses a document into typed objects and applies the
semantic rules against them, with no file system and no schema file.

Each of those three has a suite of its own, and each of those suites is correct
about its own surface. **None of them compares two surfaces**, which is where the
drift this story exists to prevent would actually appear: a rule tightened in the
schema and not in the domain, a rule identifier renamed on one side, a supported
version added in one constant and not the other. Every check here reads at least
two surfaces and fails when they disagree.

What this suite deliberately does *not* do is revalidate what a single-surface
suite already validates. ``tests/contracts/test_workload_contract_v1alpha1.py``
owns the schema, ``test_workload_contract_validation.py`` owns the published
refusal of every invalid fixture, ``tests/domain/test_workload_validation.py``
owns the domain's rules, and ``tests/scaffolding/`` owns the generated workload's
own validation. This module owns the agreement between them, and one thing none
of them covers: a *generated* mock workload edited into something that reads as
real serving.

Every check reads files from this repository and nothing else. No network, no
cluster, no model, no clock, no randomness. The evidence class is `local-static`
and it ceilings at `C0`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.domain.workload import (
    SUPPORTED_CONTRACT_VERSIONS,
    WORKLOAD_CONTRACT_KIND,
    UnsupportedContractVersionError,
    WorkloadContractError,
    parse_workload_contract,
    set_matrix_loader,
    validate_workload_contract,
)
from inferops.domain.workload.validation import CompatibilityMatrixLoader
from inferops.scaffolding import WorkloadTemplateParameters, render_workload
from tests.support.workload_template_cases import (
    MOCK_CASES,
    REPRESENTATIVE_CASES,
    case_id,
)
from tools.contract_validation import RULES
from tools.contract_validation.workload import (
    SUPPORTED_API_VERSION,
    semantic_findings,
    structural_findings,
    validate,
)

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "contracts" / "workload"
SCHEMA_PATH = CONTRACT_DIR / "workload-contract.v1alpha1.schema.json"
VALID_DIR = CONTRACT_DIR / "examples" / "valid"
INVALID_DIR = CONTRACT_DIR / "examples" / "invalid"
MANIFEST_PATH = INVALID_DIR / "expected-rejections.json"
MATRIX_PATH = (
    CONTRACT_DIR / "compatibility" / "runtime-model-compatibility.v1alpha1.json"
)

#: The invalid fixtures the platform domain does not refuse, with the reason each
#: one is here. It is a two-way assertion below rather than a note: a fixture
#: leaving this set means the domain gained a rule, a fixture arriving in it means
#: the domain lost one, and both are things a reader should be told about by a
#: failing build rather than by reading the domain.
#:
#: The contract document publishes the mock-and-real boundary as four *structural*
#: constraints, applied by the schema and therefore by every consumer in every
#: language. The domain's parsing layer applies single-field constraints and its
#: validation layer applies the published semantic rules; neither applies a
#: profile-conditional structural constraint, so this document reaches a typed
#: object. It is refused by the platform — the schema surface refuses it, and
#: `test_every_invalid_fixture_is_refused_by_the_platform` asserts exactly that —
#: and it is refused by one surface rather than by all three.
DOMAIN_DOES_NOT_REFUSE: dict[str, str] = {
    "mock-presented-as-real.yaml": (
        "the mock-and-real boundary is four profile-conditional structural "
        "constraints in the published schema; the domain applies single-field "
        "structural constraints and the published semantic rules, and neither "
        "reaches a constraint conditioned on spec.profile"
    ),
}


def load_document(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict), path.name
    return document


def load_matrix() -> dict[str, Any]:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert isinstance(matrix, dict)
    return matrix


MANIFEST: dict[str, Any] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
FIXTURE_LAYERS: dict[str, str] = {
    name: entry["layer"] for name, entry in MANIFEST["fixtures"].items()
}

VALID_FIXTURES = sorted(VALID_DIR.glob("*.yaml"))
INVALID_FIXTURES = sorted(INVALID_DIR.glob("*.yaml"))

SEMANTIC_FIXTURES = [
    path for path in INVALID_FIXTURES if FIXTURE_LAYERS[path.name] == "semantic"
]
STRUCTURAL_FIXTURES = [
    path for path in INVALID_FIXTURES if FIXTURE_LAYERS[path.name] == "structural"
]


def fixture_id(path: Path) -> str:
    return path.stem


# --------------------------------------------------------------------------
# The three surfaces, each reduced to one verdict
# --------------------------------------------------------------------------


def schema_refuses(document: dict[str, Any]) -> bool:
    """The published schema alone, which is what a bare consumer applies."""
    return bool(structural_findings(document))


def validator_refuses(document: dict[str, Any]) -> bool:
    """The offline validator: the schema and the semantic rules above it."""
    return bool(validate(document))


def domain_errors(document: dict[str, Any]) -> list[str]:
    """The platform domain's verdict, as the rule or error names it produced.

    A parse failure is reported under the exception's own class name because the
    parsing layer deliberately assigns no rule identifier; a semantic failure is
    reported under the published rule identifier it cites.
    """
    set_matrix_loader(CompatibilityMatrixLoader(load_matrix()))
    try:
        contract = parse_workload_contract(document)
    except WorkloadContractError as refusal:
        return [type(refusal).__name__]
    return [error.rule_id for error in validate_workload_contract(contract)]


def domain_refuses(document: dict[str, Any]) -> bool:
    return bool(domain_errors(document))


# --------------------------------------------------------------------------
# A document every surface accepts
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", VALID_FIXTURES, ids=fixture_id)
def test_every_valid_fixture_is_accepted_by_every_surface(path: Path) -> None:
    """One surface accepting and another refusing is the drift, in either direction.

    A committed valid fixture is the document the whole repository agrees is
    well formed. A surface that refuses one has either gained a rule the contract
    does not publish or applied a published rule where it was not published, and
    the contract document names both as defects rather than decisions.
    """
    document = load_document(path)
    assert not schema_refuses(document), structural_findings(document)
    assert not validator_refuses(document), validate(document)
    assert domain_errors(document) == [], domain_errors(document)


@pytest.mark.parametrize("path", VALID_FIXTURES, ids=fixture_id)
def test_every_valid_fixture_declares_the_kind_and_version_the_domain_implements(
    path: Path,
) -> None:
    document = load_document(path)
    assert document["kind"] == WORKLOAD_CONTRACT_KIND
    assert document["apiVersion"] in SUPPORTED_CONTRACT_VERSIONS


# --------------------------------------------------------------------------
# A document the platform refuses, and which surface refuses it
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", INVALID_FIXTURES, ids=fixture_id)
def test_every_invalid_fixture_is_refused_by_the_platform(path: Path) -> None:
    """No committed invalid fixture survives every surface this platform has.

    This is the weakest statement worth making and the one that must never
    become false. Which surface refuses is the next check; that *something* does
    is this one.
    """
    document = load_document(path)
    assert (
        schema_refuses(document)
        or validator_refuses(document)
        or domain_refuses(document)
    ), f"{path.name} is accepted by every surface in this repository"


@pytest.mark.parametrize("path", STRUCTURAL_FIXTURES, ids=fixture_id)
def test_a_structural_fixture_is_refused_by_the_schema_alone(path: Path) -> None:
    """The manifest's `structural` layer is a promise to a consumer in another language.

    It says the published schema is enough to reach this refusal. A fixture
    recorded as structural that only the semantic layer catches would make that
    promise false without any document changing.
    """
    assert schema_refuses(load_document(path)), (
        f"{path.name} is recorded as structural and the published schema accepts it"
    )


@pytest.mark.parametrize("path", SEMANTIC_FIXTURES, ids=fixture_id)
def test_a_semantic_fixture_is_accepted_by_the_schema_and_refused_above_it(
    path: Path,
) -> None:
    """The other half of the same promise, and the reason the layer exists.

    A semantic fixture is evidence that the layer above the schema is
    load-bearing. If the schema starts refusing one, the fixture stops being
    evidence of anything and the manifest's own description stops being true.
    """
    document = load_document(path)
    assert not schema_refuses(document), (
        f"{path.name} is recorded as semantic and the published schema refuses it"
    )
    assert semantic_findings(document), path.name


@pytest.mark.parametrize("path", SEMANTIC_FIXTURES, ids=fixture_id)
def test_the_domain_refuses_every_semantically_invalid_fixture(path: Path) -> None:
    """The domain applies the semantic rules, not a subset of them.

    The offline validator and the platform domain implement the same published
    rules against different inputs — a raw mapping and a typed object. This is
    the check that they reach the same conclusion about the same document.
    """
    document = load_document(path)
    assert domain_refuses(document), (
        f"{path.name} is refused by the offline validator and accepted by the domain"
    )


def test_the_invalid_fixtures_the_domain_accepts_are_exactly_the_recorded_ones() -> (
    None
):
    """A divergence between two surfaces is recorded here or it is a failure.

    Asserted as a set equality in both directions. A fixture the domain starts
    refusing has to leave :data:`DOMAIN_DOES_NOT_REFUSE`, and a fixture it stops
    refusing has to arrive in it with a reason — which is the point: the reason
    is written down while somebody knows it.
    """
    accepted = {
        path.name
        for path in INVALID_FIXTURES
        if not domain_refuses(load_document(path))
    }
    assert accepted == set(DOMAIN_DOES_NOT_REFUSE), {
        "accepted by the domain and not recorded": sorted(
            accepted - set(DOMAIN_DOES_NOT_REFUSE)
        ),
        "recorded and refused by the domain": sorted(
            set(DOMAIN_DOES_NOT_REFUSE) - accepted
        ),
    }


@pytest.mark.parametrize(
    "name", sorted(DOMAIN_DOES_NOT_REFUSE), ids=sorted(DOMAIN_DOES_NOT_REFUSE)
)
def test_a_fixture_the_domain_accepts_is_still_refused_by_the_schema(name: str) -> None:
    """A recorded divergence is a divergence, never a hole.

    Recording that one surface does not refuse a document is only acceptable
    while another one does. This is what stops the constant above from becoming
    a place to park an accepted invalid fixture.
    """
    assert schema_refuses(load_document(INVALID_DIR / name)), name


# --------------------------------------------------------------------------
# The vocabulary, on both sides of it
# --------------------------------------------------------------------------


def domain_rule_identifiers() -> set[str]:
    """Every rule identifier the domain cites over the committed fixtures."""
    cited: set[str] = set()
    for path in INVALID_FIXTURES:
        document = load_document(path)
        set_matrix_loader(CompatibilityMatrixLoader(load_matrix()))
        try:
            contract = parse_workload_contract(document)
        except WorkloadContractError:
            continue
        cited.update(error.rule_id for error in validate_workload_contract(contract))
    return cited


def test_every_rule_the_domain_cites_is_a_published_semantic_rule() -> None:
    """The domain does not invent a rule identifier, and does not misfile one.

    The rule identifier is the interface: the contract document publishes it, a
    reviewer quotes it, and a consumer looks it up in the rejection matrix. A
    domain citing an identifier that is not in the published matrix is citing
    something a reader cannot look up.
    """
    published_semantic = {name for name, rule in RULES.items() if rule.semantic}
    cited = domain_rule_identifiers()
    assert cited <= published_semantic, sorted(cited - published_semantic)


def test_every_published_semantic_rule_is_implemented_by_the_domain() -> None:
    """The other direction, which is the one that catches a rule going missing.

    The contract document's own rule is that a semantic rule must have an
    invalid fixture. Given that, every published semantic rule has a document
    that provokes it, and a rule the domain no longer applies shows up here as a
    rule nothing cited.
    """
    published_semantic = {name for name, rule in RULES.items() if rule.semantic}
    cited = domain_rule_identifiers()
    assert published_semantic <= cited, sorted(published_semantic - cited)


def test_the_domain_and_the_offline_validator_publish_the_same_field_locations() -> (
    None
):
    """One location, written two ways, and the difference is exactly the prefix.

    The manifest records a JSONPath (`$.spec.scaling`) and the domain reports a
    dotted path (`spec.scaling`). That is a presentation difference and it is
    fine; a *different location* is not, and this is what tells the two apart.
    """
    for path in SEMANTIC_FIXTURES:
        document = load_document(path)
        set_matrix_loader(CompatibilityMatrixLoader(load_matrix()))
        contract = parse_workload_contract(document)
        reported = {error.field for error in validate_workload_contract(contract)}
        expected = {
            entry["field"].removeprefix("$.")
            for entry in MANIFEST["fixtures"][path.name]["expected"]
        }
        assert expected <= reported, {
            "fixture": path.name,
            "recorded and not reported": sorted(expected - reported),
        }


# --------------------------------------------------------------------------
# The compatibility axis
# --------------------------------------------------------------------------


def test_every_surface_implements_the_same_contract_versions() -> None:
    """Three constants naming one thing, compared rather than trusted.

    The schema pins `apiVersion` with a `const`, the offline validator holds it
    in a module constant, and the domain holds a tuple so that a second version
    is an entry rather than a rewrite. A version supported in one place and not
    another is a document that validates for one consumer and not the next.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_version = schema["properties"]["apiVersion"]["const"]
    assert schema_version == SUPPORTED_API_VERSION
    assert schema_version in SUPPORTED_CONTRACT_VERSIONS
    assert set(SUPPORTED_CONTRACT_VERSIONS) == {SUPPORTED_API_VERSION}, (
        "the domain implements a contract version the published schema and the "
        "offline validator do not"
    )


def test_an_unsupported_contract_version_is_refused_by_every_surface() -> None:
    document = load_document(INVALID_DIR / "unsupported-api-version.yaml")
    assert schema_refuses(document)
    assert validator_refuses(document)
    assert domain_refuses(document)


def test_an_unsupported_version_is_refused_before_any_field_below_it() -> None:
    """A refusal about `v1alpha2` may not complain about the shape of `v1alpha1`.

    Every field path either surface knows belongs to the version it implements.
    Applying them to a document declaring another version produces complaints
    about a shape neither surface has a claim over, and the domain module says
    so in as many words. Both are held to it here: exactly one finding, on
    `$.apiVersion`, carrying the canonical code for it.
    """
    document = load_document(INVALID_DIR / "unsupported-api-version.yaml")

    findings = validate(document)
    assert [finding.field for finding in findings] == ["$.apiVersion"], [
        found.as_dict() for found in findings
    ]
    assert findings[0].code == "version-unsupported"
    assert findings[0].rule == "contract-version-unsupported"

    with pytest.raises(UnsupportedContractVersionError) as refused:
        parse_workload_contract(document)
    assert refused.value.field == "$.apiVersion"


def test_the_unsupported_version_refusal_names_the_versions_that_exist() -> None:
    """A refusal a reader can act on names the vocabulary, never the value.

    Printing the supported versions is safe because they come from this
    repository. Printing the declared one is not, for the reason every message
    in this domain withholds a value read out of a document.
    """
    document = load_document(INVALID_DIR / "unsupported-api-version.yaml")
    with pytest.raises(UnsupportedContractVersionError) as refused:
        parse_workload_contract(document)
    reason = refused.value.reason
    for version in SUPPORTED_CONTRACT_VERSIONS:
        assert version in reason
    assert str(document["apiVersion"]) not in reason


# --------------------------------------------------------------------------
# A generated workload is held to the same contract as a committed one
# --------------------------------------------------------------------------


def rendered_contract(parameters: WorkloadTemplateParameters) -> dict[str, Any]:
    document = yaml.safe_load(render_workload(parameters).files["workload.yaml"])
    assert isinstance(document, dict)
    return document


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_a_generated_workload_is_accepted_by_every_surface(
    parameters: WorkloadTemplateParameters,
) -> None:
    """The scaffolding suite validates its output. This compares surfaces on it.

    ``tests/scaffolding/`` already puts a generated contract through the offline
    validator and through the domain pipeline. What it does not do is assert
    that the bare published schema — the only half a consumer in another language
    gets — reaches the same verdict, which is the property that makes a generated
    workload portable rather than merely acceptable here.
    """
    document = rendered_contract(parameters)
    assert not schema_refuses(document), structural_findings(document)
    assert not validator_refuses(document), validate(document)
    assert domain_errors(document) == [], domain_errors(document)


#: The four edits that turn a mock workload into something that reads as real
#: serving, from the contract document's own list. Each is applied on its own, so
#: a failure names the constraint that stopped holding rather than "one of four".
MOCK_BOUNDARY_EDITS: tuple[tuple[str, tuple[str, ...], object], ...] = (
    ("environment", ("spec", "environment"), "production"),
    (
        "serving-capability",
        ("spec", "model", "servingCapability"),
        "inferops-native-serving",
    ),
    (
        "accelerator-count",
        ("spec", "resources", "accelerator", "count"),
        1,
    ),
    (
        "real-runtime-proof",
        ("spec", "evidence", "proofRefs"),
        ["docs/proof/serving/v1-s0-003-pr2-runtime-feasibility.md"],
    ),
)


def edited(document: dict[str, Any], path: tuple[str, ...], value: object) -> dict:
    """A copy of the document with one location replaced."""
    copy = json.loads(json.dumps(document))
    cursor: Any = copy
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    assert isinstance(copy, dict)
    return copy


@pytest.mark.parametrize("parameters", MOCK_CASES, ids=case_id)
@pytest.mark.parametrize(
    "edit", MOCK_BOUNDARY_EDITS, ids=[name for name, _, _ in MOCK_BOUNDARY_EDITS]
)
def test_a_generated_mock_workload_cannot_be_edited_into_real_serving(
    edit: tuple[str, tuple[str, ...], object],
    parameters: WorkloadTemplateParameters,
) -> None:
    """The boundary the committed mock fixture is held to, applied to a generated one.

    ``tests/contracts/test_workload_contract_v1alpha1.py`` holds the *committed*
    mock fixture to these four constraints. A generated workload is a document
    nobody reviewed, produced by somebody who did not write the platform, and it
    is the one most likely to be edited after generation — so the same four are
    asserted here against the scaffolder's own output rather than assumed to
    transfer.
    """
    _, location, value = edit
    document = edited(rendered_contract(parameters), location, value)
    assert schema_refuses(document), (
        f"a generated mock workload with {'.'.join(location)} edited to "
        f"{location[-1]!r}'s real-serving value is accepted by the published schema"
    )


@pytest.mark.parametrize("parameters", MOCK_CASES, ids=case_id)
def test_a_generated_mock_workload_declares_itself_a_mock(
    parameters: WorkloadTemplateParameters,
) -> None:
    """The label lives in the document, not in the directory it was written to."""
    document = rendered_contract(parameters)
    assert document["spec"]["profile"] == "mock-llm"
    assert document["spec"]["model"]["servingCapability"] == "inferops-mock-serving"
    assert document["spec"]["mockLlm"]["ciOnly"] is True
    assert document["spec"]["evidence"].get("proofRefs", []) == []
