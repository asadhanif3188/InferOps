"""Deterministic checks over the V1 claim and evidence register.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness.

Since `V1-S5-012-PR2` the register is `v1alpha2`: a claim carries a status and a
boundary, and the evidence records under it each carry their own level. What this
suite establishes is that the register cannot quietly say more than the repository
supports: that it passes its published schema and every evidence-level rule with
every cited file present; that every claim names a limitation and what it does not
establish; that a claim mapped to a claim in the test strategy never carries a
stronger status than that claim does; that a certified claim holds a classified
record, and a planned or deferred one holds none; that a claim asserting real
serving, performance, or reliability behaviour holds a record at `C2` or above, and
that a claim holding a record which ran a real runtime, model, or cluster declares
that it asserts real behaviour; that a record from a Kubernetes cluster names a
provider the cluster provider contract publishes, or says its source names none, so
Docker Desktop evidence cannot be read as `kind`; that no claim or record describes an
amount in the vocabulary reserved for an invoice; that a claim whose mapped strategy
claim the test inventory records as covered by no pytest module carries that gap;
that every rule names the control that has been watched refusing it; that the
published document and the README agree with the data; and that every public entry
point the README publishes is either claimed by a row or listed, with a reason, as a
surface that claims nothing.

What it does not establish is that any statement in the register is true. It checks
references, ranks, levels against executions, and vocabulary. Whether a record says
what the claim citing it says it says, and whether a claim declared the right
components material, are readings, and no test here performs one — which is why the
register carries that limitation in its own data rather than only here.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from tools.evidence_model import check_claim, check_register

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTING_DIR = REPO_ROOT / "docs" / "testing"
MATRIX_PATH = TESTING_DIR / "claim-evidence-matrix.v1alpha2.json"
DOCUMENT_PATH = TESTING_DIR / "claim-evidence-matrix.md"
STRATEGY_PATH = TESTING_DIR / "test-strategy.v1alpha1.json"
INVENTORY_PATH = TESTING_DIR / "test-inventory.v1alpha1.json"
GATE_MATRIX_PATH = TESTING_DIR / "ci-gate-matrix.v1alpha1.json"
PROVIDER_CONTRACT_PATH = (
    REPO_ROOT / "docs" / "environment" / "local-cluster-provider-contract.v1alpha1.json"
)
README_PATH = REPO_ROOT / "README.md"

EXPECTED_ID = "https://inferops.io/testing/claim-evidence-matrix.v1alpha2.json"
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha2"

SLUG = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")

# An identifier as the document publishes it: an inline code span in the first
# column of a Markdown table row. The same shape the strategy suite reads.
FIRST_TABLE_COLUMN = re.compile(
    r"^\|\s*`([A-Za-z0-9][A-Za-z0-9-]*)`\s*\|", flags=re.MULTILINE
)

REQUIRED_TOP_LEVEL = (
    "$id",
    "contractVersion",
    "supersedes",
    "title",
    "description",
    "schemaRef",
    "documentRef",
    "modelRef",
    "specificationRef",
    "decisionRef",
    "readmeRef",
    "strategyRef",
    "matrixRef",
    "inventoryRef",
    "ciGateMatrixRef",
    "certificationRef",
    "providerContractRef",
    "boundariesRef",
    "contributingRef",
    "evidenceRoot",
    "templateRoot",
    "claimStatuses",
    "evidenceLevels",
    "evidenceClasses",
    "areas",
    "claims",
    "nonClaimSurfaces",
    "prohibitions",
    "limitations",
)

REQUIRED_CLAIM_FIELDS = (
    "claimId",
    "area",
    "statement",
    "status",
    "notClaimedReason",
    "assertsRealBehaviour",
    "limitation",
    "doesNotEstablish",
    "evidenceRecords",
    "strategyClaimIds",
    "implementationRefs",
    "automatedTestRefs",
    "recordedCoverageGaps",
    "ciGateIds",
    "readmeRefs",
    "legacyClassification",
)

#: The vocabulary the cost method reserves for the ``actual`` basis, which V1
#: cannot reach. A register that described an estimate in these words would undo
#: the rule the cost row exists to state.
INVOICE_VOCABULARY = (
    "billing",
    "billed",
    "invoice",
    "invoiced",
    "chargeback",
    "spend",
    "a bill",
)

#: A reserved word may appear in a sentence that denies it — the register has to
#: be able to say the vocabulary is unreachable — and nowhere else. This is the
#: same shape the security baseline holds its own reserved terms to.
DENIALS = (
    "no ",
    "not ",
    "never",
    "cannot",
    "unreachable",
    "nothing",
    "none",
    "absent",
)

#: Words that mean the claim is about something real running, rather than about
#: files in this repository. A claim carrying one is expected to declare
#: ``assertsRealBehaviour``; this list is a floor, not a definition.
REAL_BEHAVIOUR_WORDS = ("serves a real completion", "real inference")

#: The component roles that make a record evidence about a real serving stack. A
#: claim holding a record at `C2` or above that executed one of these is a claim
#: about something real running, whatever its sentence happens to say.
REAL_ROLES = frozenset({"inference-runtime", "model", "cluster"})

#: What a cluster record says when its source file names no provider.
UNRECORDED = "unrecorded"

MATRIX: dict[str, Any] = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
STRATEGY: dict[str, Any] = json.loads(STRATEGY_PATH.read_text(encoding="utf-8"))
INVENTORY: dict[str, Any] = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
GATE_MATRIX: dict[str, Any] = json.loads(GATE_MATRIX_PATH.read_text(encoding="utf-8"))
PROVIDER_CONTRACT: dict[str, Any] = json.loads(
    PROVIDER_CONTRACT_PATH.read_text(encoding="utf-8")
)

CLAIMS: list[dict[str, Any]] = MATRIX["claims"]
STATUS_BY_ID = {row["statusId"]: row for row in MATRIX["claimStatuses"]}
CLASS_BY_ID = {row["classId"]: row for row in MATRIX["evidenceClasses"]}
LEVEL_IDS = {row["levelId"] for row in MATRIX["evidenceLevels"]}
AREA_IDS = {row["areaId"] for row in MATRIX["areas"]}

STRATEGY_CLAIMS = {row["claimId"]: row for row in STRATEGY["claims"]}
STRATEGY_ENVIRONMENTS = set(STRATEGY["environments"])
STRATEGY_LEVELS = {row["levelId"]: row for row in STRATEGY["certificationLevels"]}
STRATEGY_CLASSES = {row["classId"] for row in STRATEGY["evidenceClasses"]}
INVENTORY_MODULES = {row["module"] for row in INVENTORY["modules"]}
INVENTORY_COVERAGE_GAPS = {gap["claimId"] for gap in INVENTORY["coverageGaps"]}
GATE_IDS = {row["gateId"] for row in GATE_MATRIX["gates"]}
PROVIDER_IDS = {row["providerId"] for row in PROVIDER_CONTRACT["providers"]}

#: A row's status expressed as a number, so "never bolder than the strategy" is
#: an inequality rather than a table of permitted pairs.
RANK = {row["statusId"]: row["rank"] for row in MATRIX["claimStatuses"]}

#: The strategy's own status vocabulary, mapped onto this register's.
STRATEGY_STATUS_RANK = {"certified": 3, "planned": 2, "deferred": 1}


def ids(row: dict) -> str:
    """The pytest identifier for a row: its claim, so a failure names the claim."""
    return row["claimId"]


def records(row: dict) -> list[dict[str, Any]]:
    return list(row["evidenceRecords"])


def levels(row: dict) -> set[str]:
    return {held["evidenceLevel"] for held in records(row) if held.get("evidenceLevel")}


# ---------------------------------------------------------------- the file


def test_the_matrix_declares_its_identity() -> None:
    assert MATRIX["$id"] == EXPECTED_ID
    assert MATRIX["contractVersion"] == EXPECTED_CONTRACT_VERSION
    assert MATRIX["supersedes"] == "inferops.io/v1alpha1"


@pytest.mark.parametrize("field", REQUIRED_TOP_LEVEL)
def test_the_matrix_declares_every_required_section(field: str) -> None:
    assert field in MATRIX, field
    assert MATRIX[field] not in ("", [], {}), field


@pytest.mark.parametrize(
    "field",
    (
        "schemaRef",
        "documentRef",
        "modelRef",
        "specificationRef",
        "decisionRef",
        "readmeRef",
        "strategyRef",
        "matrixRef",
        "inventoryRef",
        "ciGateMatrixRef",
        "certificationRef",
        "providerContractRef",
        "costMethodRef",
        "boundariesRef",
        "contributingRef",
        "evidenceRoot",
        "templateRoot",
    ),
)
def test_every_reference_resolves(field: str) -> None:
    assert (REPO_ROOT / MATRIX[field]).exists(), (field, MATRIX[field])


def test_the_register_passes_its_schema_and_every_evidence_level_rule() -> None:
    """The check every other one here leans on.

    The schema holds the shape of each record at each level; the validator holds a
    record against its claim and the claim against the register; and with the
    repository given, every cited file has to exist. The register's own rules are
    not restated below where the validator already enforces them.
    """
    refusals = check_register(MATRIX, repo_root=REPO_ROOT)
    assert not refusals, [
        f"{refusal.rule} at {refusal.path}: {refusal.message}" for refusal in refusals
    ]


def test_the_matrix_holds_claims_in_every_declared_area() -> None:
    used = {row["area"] for row in CLAIMS}
    assert used == AREA_IDS, {"declared but unused": sorted(AREA_IDS - used)}


def test_every_status_in_the_vocabulary_is_used_by_at_least_one_row() -> None:
    """All four states are real, and a register showing only three hides one."""
    used = {row["status"] for row in CLAIMS}
    assert used == set(STATUS_BY_ID), {
        "declared but unused": sorted(set(STATUS_BY_ID) - used)
    }


def test_the_evidence_classes_agree_with_the_certification_document() -> None:
    """The class vocabulary is the strategy's classes plus the unreachable one.

    ``production-experience`` is deliberately absent from the strategy's class
    table — no layer can produce it — and deliberately present here, because a
    claim register has to be able to say that a class exists and is unreachable.
    """
    declared = set(CLASS_BY_ID)
    assert declared >= STRATEGY_CLASSES, {
        "class the strategy has and the register does not": sorted(
            STRATEGY_CLASSES - declared
        )
    }
    assert declared - STRATEGY_CLASSES == {"production-experience"}, sorted(
        declared - STRATEGY_CLASSES
    )
    assert CLASS_BY_ID["production-experience"]["reachedInV1"] is False


def test_the_synthetic_class_no_longer_covers_generated_input() -> None:
    """ADR 0016 D3, in the data: a workload's origin sets no ceiling.

    The class keeps its C1 ceiling for what it still names -- a simulated
    environment, which is a substitution -- and the register and the strategy
    say the same thing about it.
    """
    strategy = next(
        row for row in STRATEGY["evidenceClasses"] if row["classId"] == "synthetic"
    )
    for meaning in (CLASS_BY_ID["synthetic"]["meaning"], strategy["meaning"]):
        assert "simulated environment" in meaning
        assert "Generated input is not this class" in meaning
    assert strategy["maxCertification"] == "C1"
    assert CLASS_BY_ID["synthetic"]["legacyCeiling"] == "C1"


# ---------------------------------------------------------------- each row


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_row_declares_every_required_field(row: dict) -> None:
    for field in REQUIRED_CLAIM_FIELDS:
        assert field in row, (row["claimId"], field)


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_identifier_is_a_slug(row: dict) -> None:
    assert SLUG.match(row["claimId"]), row["claimId"]


def test_no_claim_identifier_appears_twice() -> None:
    seen = [row["claimId"] for row in CLAIMS]
    assert len(seen) == len(set(seen)), sorted(
        claim for claim in set(seen) if seen.count(claim) > 1
    )


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_row_names_a_known_area_status_and_carried_classification(
    row: dict,
) -> None:
    """The carried v1alpha1 classification is history, and it stays readable."""
    assert row["area"] in AREA_IDS, row["area"]
    assert row["status"] in STATUS_BY_ID, row["status"]
    carried = row["legacyClassification"]
    assert carried["evidenceLabel"] in CLASS_BY_ID, carried["evidenceLabel"]
    assert carried["environment"] in STRATEGY_ENVIRONMENTS, carried["environment"]
    assert carried["provider"] in PROVIDER_IDS | {"not-applicable"}, carried["provider"]
    assert "history" in carried["note"], row["claimId"]


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_row_states_a_limitation_and_what_it_does_not_establish(
    row: dict,
) -> None:
    """Whatever its status. A row without either is a row read at full strength."""
    assert len(row["limitation"]) > 40, (row["claimId"], row["limitation"])
    assert len(row["doesNotEstablish"]) > 10, (row["claimId"], row["doesNotEstablish"])


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_statement_is_a_sentence_rather_than_a_label(row: dict) -> None:
    assert len(row["statement"]) > 40, (row["claimId"], row["statement"])
    assert row["statement"].endswith("."), row["claimId"]


# ------------------------------------------------------- status and level


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_certified_row_holds_a_classified_record_in_v1_scope(row: dict) -> None:
    if row["status"] != "certified":
        return
    assert levels(row), row["claimId"]
    for level in levels(row):
        assert STRATEGY_LEVELS[level]["v1Scope"] is True, (row["claimId"], level)


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_no_record_anywhere_reaches_beyond_v1_scope(row: dict) -> None:
    """No V1 record is C3 or C4, whatever its claim's status."""
    for level in levels(row):
        assert STRATEGY_LEVELS[level]["v1Scope"] is True, (row["claimId"], level)


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_planned_or_deferred_row_cites_no_record(row: dict) -> None:
    """The rule the claim and test matrix already enforces, restated here.

    A planned claim holding a record is a failure rather than an optimism. The
    exception is ``not-claimed``: a claim this project has measured itself unable
    to make holds the record that measured it, which is the opposite failure mode.
    """
    if row["status"] not in ("planned", "deferred"):
        return
    assert not records(row), (row["claimId"], [r["recordId"] for r in records(row)])


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_not_claimed_row_says_why_it_is_not_claimed(row: dict) -> None:
    if row["status"] != "not-claimed":
        return
    assert row["notClaimedReason"], row["claimId"]
    assert len(row["notClaimedReason"]) > 60, row["claimId"]


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_only_a_not_claimed_row_carries_a_not_claimed_reason(row: dict) -> None:
    if row["status"] == "not-claimed":
        return
    assert row["notClaimedReason"] is None, row["claimId"]


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_record_is_held_to_the_evidence_level_rules(row: dict) -> None:
    """The replacement for the v1alpha1 ceiling rule, claim by claim.

    A mock-backed record cannot sit at C2, because its claim declares the runtime
    material and the validator holds the record to that declaration.
    """
    refusals = check_claim(row, evidence_classes=MATRIX["evidenceClasses"])
    assert not refusals, [
        f"{refusal.rule} at {refusal.path}: {refusal.message}" for refusal in refusals
    ]


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_real_behaviour_claim_rests_on_evidence_that_can_support_one(
    row: dict,
) -> None:
    """A mock, a simulation, or an estimate may never appear behind a real claim.

    Stricter than the validator's own rule, which also admits a carried legacy
    classification: every certified real-behaviour claim here holds a migrated
    record at C2 or above.
    """
    if not row["assertsRealBehaviour"] or row["status"] != "certified":
        return
    assert levels(row) & {"C2", "C3", "C4"}, {
        "claim": row["claimId"],
        "levels held": sorted(levels(row)),
    }


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_statement_about_real_serving_declares_that_it_is_one(row: dict) -> None:
    statement = row["statement"].lower()
    if not any(word in statement for word in REAL_BEHAVIOUR_WORDS):
        return
    assert row["assertsRealBehaviour"] is True, row["claimId"]


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_row_on_real_evidence_declares_that_it_asserts_real_behaviour(
    row: dict,
) -> None:
    """The word list above is a floor. This is the rule with teeth.

    A claim holding a record at C2 or above that ran a real runtime, model, or
    cluster is a claim about a real component, whatever its sentence happens to
    say, and it has to declare that so the real-evidence rule can reach it. The
    migration found one claim that did not and corrected its flag.
    """
    for held in records(row):
        if held.get("evidenceLevel") not in ("C2", "C3", "C4"):
            continue
        roles = {
            component["role"] for component in held["execution"]["executedComponents"]
        }
        if roles & REAL_ROLES:
            assert row["assertsRealBehaviour"] is True, (
                row["claimId"],
                held["recordId"],
            )


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_real_kubernetes_row_names_the_provider_it_ran_on(row: dict) -> None:
    """Runtime evidence records its provider, and certifies no other one.

    A record whose source file never named the provider says ``unrecorded`` rather
    than borrowing one from a neighbouring record.
    """
    for held in records(row):
        if held["environment"]["environmentId"] != "local-kubernetes":
            continue
        assert held["environment"]["provider"] in PROVIDER_IDS | {UNRECORDED}, (
            row["claimId"],
            held["recordId"],
            held["environment"]["provider"],
        )


# ------------------------------------------------- agreement with the strategy


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_mapped_strategy_claim_exists(row: dict) -> None:
    for claim_id in row["strategyClaimIds"]:
        assert claim_id in STRATEGY_CLAIMS, (row["claimId"], claim_id)


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_row_never_outranks_the_strategy_claim_it_maps_to(row: dict) -> None:
    for claim_id in row["strategyClaimIds"]:
        strategy_status = STRATEGY_CLAIMS[claim_id]["v1Status"]
        assert RANK[row["status"]] <= STRATEGY_STATUS_RANK[strategy_status], {
            "claim": row["claimId"],
            "status here": row["status"],
            "strategy claim": claim_id,
            "status there": strategy_status,
        }


def test_every_strategy_claim_is_covered_by_at_least_one_row() -> None:
    """The completeness half. A claim the strategy carries and the public
    register does not is a claim nobody would notice going out of date."""
    mapped = {claim_id for row in CLAIMS for claim_id in row["strategyClaimIds"]}
    missing = sorted(set(STRATEGY_CLAIMS) - mapped)
    assert not missing, {"strategy claims no row maps": missing}


# --------------------------------------------------------- what a row cites


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_implementation_reference_resolves(row: dict) -> None:
    missing = [
        ref for ref in row["implementationRefs"] if not (REPO_ROOT / ref).exists()
    ]
    assert not missing, (row["claimId"], missing)


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_test_reference_is_a_module_the_inventory_knows(row: dict) -> None:
    for ref in row["automatedTestRefs"]:
        assert ref in INVENTORY_MODULES, (row["claimId"], ref)
        assert (REPO_ROOT / ref).exists(), (row["claimId"], ref)


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_row_records_the_coverage_gaps_the_inventory_records(row: dict) -> None:
    """Both directions, so neither list can drift from the other.

    Five rows name test modules for a claim the inventory records as covered by
    no module at all. The modules are adjacent — they check how the scripts are
    written, or the mechanics around the artifact — and citing them without the
    gap lets the register imply coverage the inventory denies.
    """
    expected = sorted(
        claim_id
        for claim_id in row["strategyClaimIds"]
        if claim_id in INVENTORY_COVERAGE_GAPS
    )
    assert row["recordedCoverageGaps"] == expected, {
        "claim": row["claimId"],
        "recorded here": row["recordedCoverageGaps"],
        "recorded by the inventory": expected,
    }


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_row_with_a_recorded_coverage_gap_says_so_in_its_limitation(
    row: dict,
) -> None:
    """A field nobody reads is not a disclosure."""
    if not row["recordedCoverageGaps"]:
        return
    assert "recorded coverage gap" in row["limitation"], row["claimId"]


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_gate_reference_is_a_gate_the_gate_matrix_declares(row: dict) -> None:
    for gate_id in row["ciGateIds"]:
        assert gate_id in GATE_IDS, (row["claimId"], gate_id)


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_evidence_reference_is_a_committed_record(row: dict) -> None:
    template_root = MATRIX["templateRoot"]
    for held in records(row):
        for ref in held["evidenceRefs"]:
            assert ref.startswith(MATRIX["evidenceRoot"] + "/"), (row["claimId"], ref)
            assert not ref.startswith(template_root + "/"), (row["claimId"], ref)
            assert (REPO_ROOT / ref).exists(), (row["claimId"], ref)


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_the_record_naming_the_versions_is_one_of_the_records_cited(row: dict) -> None:
    for held in records(row):
        if held.get("versionsRecordedIn"):
            assert held["versionsRecordedIn"] in held["evidenceRefs"], held["recordId"]


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_record_quotes_its_commands_and_identifiers_from_its_own_files(
    row: dict,
) -> None:
    """The control against a migrated record that invents what it cannot cite.

    Every command a record says repeats it, and every immutable identifier it pins,
    appears verbatim in one of the files that record cites. A record whose command
    or digest was written from memory, or copied from a neighbouring record, fails.
    """
    for held in records(row):
        text = "\n".join(
            (REPO_ROOT / ref).read_text(encoding="utf-8")
            for ref in held["evidenceRefs"]
        )
        for command in held.get("procedure", {}).get("commands", []):
            assert command in text, (held["recordId"], command)
        for version in held.get("versions", []):
            assert str(version["value"]) in text, (held["recordId"], version["value"])


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_readme_reference_resolves(row: dict) -> None:
    missing = [ref for ref in row["readmeRefs"] if not (REPO_ROOT / ref).exists()]
    assert not missing, (row["claimId"], missing)


# ------------------------------------------------------- reserved vocabulary


def _every_prose_field() -> list[tuple[str, str, str]]:
    fields: list[tuple[str, str, str]] = []
    for row in CLAIMS:
        for field in (
            "statement",
            "limitation",
            "doesNotEstablish",
            "notClaimedReason",
        ):
            value = row.get(field)
            if value:
                fields.append((row["claimId"], field, value))
        for held in records(row):
            fields.append((held["recordId"], "summary", held["summary"]))
            for field in ("limitations", "doesNotEstablish"):
                for index, sentence in enumerate(held.get(field, [])):
                    fields.append((held["recordId"], f"{field}[{index}]", sentence))
    for index, limitation in enumerate(MATRIX["limitations"]):
        fields.append(("<matrix>", f"limitations[{index}]", limitation))
    return fields


@pytest.mark.parametrize(
    "claim_id,field,value",
    _every_prose_field(),
    ids=lambda value: value if isinstance(value, str) and len(value) < 60 else "",
)
def test_no_row_describes_an_amount_in_an_invoices_vocabulary(
    claim_id: str, field: str, value: str
) -> None:
    """The ``actual`` basis is unreachable in V1 and owns these words.

    The cost prohibition ``no-estimate-is-a-bill`` is enforced over the cost
    method's own records. This applies the same refusal to the register that
    describes them, including every record's own summary and boundaries, because
    the sentence a reader remembers is the one in the register rather than the one
    in the record.

    A reserved word survives only inside a sentence that denies it. Banning the
    words outright was tried first and was wrong: it makes the rule itself
    unsayable, and a register that cannot name the vocabulary it refuses cannot
    tell a reader what the refusal is.
    """
    for sentence in re.split(r"(?<=[.;])\s+", value):
        lowered = sentence.lower()
        found = [
            word
            for word in INVOICE_VOCABULARY
            if re.search(rf"\b{re.escape(word)}\b", lowered)
        ]
        if not found:
            continue
        assert any(denial in lowered for denial in DENIALS), {
            "claim": claim_id,
            "field": field,
            "reserved words": found,
            "sentence": sentence,
        }


# ----------------------------------------------- agreement with the README


def _readme_entry_point_targets() -> list[str]:
    """Every relative link target in the README's public entry-point table."""
    lines = README_PATH.read_text(encoding="utf-8").splitlines()
    start = lines.index("## Public entry points")
    end = next(
        index
        for index, line in enumerate(lines[start + 1 :], start=start + 1)
        if line.startswith("## ")
    )
    targets: list[str] = []
    for line in lines[start:end]:
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0] == "Topic":
            continue
        match = re.search(r"\]\(([^)]+)\)", cells[1])
        if match:
            targets.append(match.group(1).split("#", 1)[0])
    return targets


README_TARGETS = _readme_entry_point_targets()
NON_CLAIM_PATHS = {row["path"] for row in MATRIX["nonClaimSurfaces"]}
CLAIMED_PATHS = {ref for row in CLAIMS for ref in row["readmeRefs"]}


def test_the_readme_publishes_an_entry_point_table_to_check() -> None:
    assert len(README_TARGETS) > 40, len(README_TARGETS)


def test_every_readme_entry_point_is_claimed_or_declared_to_claim_nothing() -> None:
    """The completeness check this register exists to hold.

    Every planned public claim needs evidence and a limitation. The README is
    where V1's public claims are made, so the register is complete only when no
    entry point in it is unaccounted for.
    """
    ungoverned = sorted(set(README_TARGETS) - CLAIMED_PATHS - NON_CLAIM_PATHS)
    assert not ungoverned, {"README entry points no row governs": ungoverned}


def test_a_surface_is_not_both_claimed_and_declared_to_claim_nothing() -> None:
    both = sorted(CLAIMED_PATHS & NON_CLAIM_PATHS)
    assert not both, {"listed in both directions": both}


@pytest.mark.parametrize("row", MATRIX["nonClaimSurfaces"], ids=lambda row: row["path"])
def test_every_non_claim_surface_exists_and_says_why_it_claims_nothing(
    row: dict,
) -> None:
    assert (REPO_ROOT / row["path"]).exists(), row["path"]
    assert len(row["reason"]) > 40, row["path"]


def test_no_non_claim_surface_is_absent_from_the_readme() -> None:
    """A surface excused from claiming anything has to be one the README shows.

    Otherwise the exclusion list becomes somewhere to put a path so that nothing
    has to be said about it.
    """
    absent = sorted(NON_CLAIM_PATHS - set(README_TARGETS))
    assert not absent, {"excused but not a README entry point": absent}


def test_the_readme_links_the_evidence_level_specification_and_its_disclaimer() -> None:
    """The acceptance criterion that the disclaimer is discoverable from the README."""
    readme = " ".join(README_PATH.read_text(encoding="utf-8").split())
    assert "docs/testing/evidence-levels.md" in README_TARGETS
    assert "project-defined and not an ISO, NIST, regulatory, or industry" in readme


def test_the_document_counts_the_excused_surfaces_correctly() -> None:
    """The count beside the exclusion list is a claim about the exclusion list.

    It was unchecked until `V1-S4-009-PR2` added the eighth surface and an
    independent review pointed out that the count beside it could have said
    anything. The inventory beside this document has drifted this exact way four
    times, which is a better argument than any reasoning about likelihood.
    """
    written = f"{len(MATRIX['nonClaimSurfaces'])} public entry points in the README"
    assert written in DOCUMENT_TEXT, {
        "surfaces in the data": len(MATRIX["nonClaimSurfaces"]),
        "the document should say": written,
    }


# --------------------------------------------------- agreement with the document


DOCUMENT_TEXT = DOCUMENT_PATH.read_text(encoding="utf-8")
DOCUMENT_IDENTIFIERS = set(FIRST_TABLE_COLUMN.findall(DOCUMENT_TEXT))


def test_the_document_publishes_every_claim_the_data_holds() -> None:
    missing = sorted({row["claimId"] for row in CLAIMS} - DOCUMENT_IDENTIFIERS)
    assert not missing, {"in the data, absent from the document": missing}


def test_the_document_publishes_no_claim_the_data_does_not_hold() -> None:
    known = (
        {row["claimId"] for row in CLAIMS}
        | set(STATUS_BY_ID)
        | set(CLASS_BY_ID)
        | LEVEL_IDS
        | AREA_IDS
        | {row["ruleId"] for row in MATRIX["prohibitions"]}
    )
    extra = sorted(DOCUMENT_IDENTIFIERS - known)
    assert not extra, {"in the document, absent from the data": extra}


def test_the_document_names_every_record_and_its_level() -> None:
    """A record is where a level lives now, so the document shows each one."""
    flat = " ".join(DOCUMENT_TEXT.split())
    for row in CLAIMS:
        for held in records(row):
            assert f"`{held['recordId']}`" in flat, held["recordId"]


@pytest.mark.parametrize("row", MATRIX["prohibitions"], ids=lambda row: row["ruleId"])
def test_every_prohibition_is_a_slug_with_a_statement(row: dict) -> None:
    assert SLUG.match(row["ruleId"]), row["ruleId"]
    assert len(row["statement"]) > 40, row["ruleId"]


@pytest.mark.parametrize("row", MATRIX["prohibitions"], ids=lambda row: row["ruleId"])
def test_every_prohibition_names_the_control_that_watches_it_fail(row: dict) -> None:
    """The document says each rule is driven over a row corrupted to break it.

    That sentence was true of nine of the ten when it was written, and an
    independent review found the tenth. Saying it and checking it are now the
    same thing: each rule names its control, and the control has to exist here.
    """
    control = row["controlledBy"]
    assert control, row["ruleId"]
    assert control in globals(), (row["ruleId"], control)
    assert callable(globals()[control]), (row["ruleId"], control)


def test_no_control_is_shared_by_two_rules() -> None:
    """A control watching two rules would leave one of them unwatched."""
    named = [row["controlledBy"] for row in MATRIX["prohibitions"]]
    assert len(named) == len(set(named)), sorted(
        control for control in set(named) if named.count(control) > 1
    )


def test_the_retired_ceiling_rule_is_not_a_prohibition_any_more() -> None:
    """The v1alpha1 register held a claim's level under its label's ceiling.

    A v1alpha2 record has no label and its level is decided by what it executed, so
    that rule would govern nothing. Its replacement names what does.
    """
    rules = {row["ruleId"] for row in MATRIX["prohibitions"]}
    assert "a-level-may-not-exceed-its-labels-ceiling" not in rules
    assert "a-record-is-held-to-the-evidence-level-rules" in rules


#: What an unrendered template expression looks like in Markdown. The document
#: is assembled once and then maintained by hand, and the first version of it
#: shipped a literal ``{len(DATA[...])}`` expression into the published file.
PLACEHOLDER = re.compile(r"\{(?:len\(|DATA\[|COUNTS\[|row\[)")


def test_the_document_carries_no_unrendered_placeholder() -> None:
    """Found by an independent review, in the published document, after a green suite.

    The suite compared the document's identifiers and its counts with the data
    and had nothing to say about a sentence that was neither. This is the cheap
    general check that was missing.
    """
    found = [
        (number, line)
        for number, line in enumerate(DOCUMENT_TEXT.splitlines(), start=1)
        if PLACEHOLDER.search(line)
    ]
    assert not found, {"unrendered expressions": found}


def test_the_placeholder_check_would_catch_the_defect_it_was_written_for() -> None:
    assert PLACEHOLDER.search('{len(DATA["prohibitions"])} rules hold this register')
    assert not PLACEHOLDER.search("10 rules hold this register to its own vocabulary.")


def test_the_document_states_the_counts_the_data_produces() -> None:
    """A count in prose is a number somebody typed unless something checks it."""
    counts = {
        status: sum(1 for row in CLAIMS if row["status"] == status)
        for status in STATUS_BY_ID
    }
    assert f"{len(CLAIMS)} claims" in DOCUMENT_TEXT, len(CLAIMS)
    total = sum(len(records(row)) for row in CLAIMS)
    assert f"{total} evidence records" in DOCUMENT_TEXT, total
    assert f"{len(MATRIX['prohibitions'])} rules" in DOCUMENT_TEXT, len(
        MATRIX["prohibitions"]
    )
    for status, count in counts.items():
        # The document spells a status readably — "not claimed" rather than the
        # identifier — so both forms count.
        spellings = {f"{count} {status}", f"{count} {status.replace('-', ' ')}"}
        assert any(spelling in DOCUMENT_TEXT for spelling in spellings), (
            status,
            count,
        )


def test_the_readme_states_the_counts_the_data_produces() -> None:
    """The README repeats the counts, so the README is checked against them too.

    A count published on the first screen of a repository is the one a reader
    quotes. Leaving it unchecked is how the inventory's per-layer counts drifted
    three times, which that document now records against itself.
    """
    readme = README_PATH.read_text(encoding="utf-8")
    assert f"{len(CLAIMS)} claims" in readme, len(CLAIMS)
    for status in STATUS_BY_ID:
        count = sum(1 for row in CLAIMS if row["status"] == status)
        spellings = {f"{count} {status}", f"{count} {status.replace('-', ' ')}"}
        assert any(spelling in readme for spelling in spellings), (status, count)


def test_every_register_count_the_readme_writes_is_the_current_one() -> None:
    """The check above passes if the right number appears anywhere.

    It passed for a whole sprint while the README's own entry-point row for this
    register said "58 claims: 42 certified" beside a paragraph saying 59 and 43.
    The evidence migration found it. Every "N claims: N certified" phrase the
    README writes now has to be the current one.
    """
    readme = " ".join(README_PATH.read_text(encoding="utf-8").split())
    certified = sum(1 for row in CLAIMS if row["status"] == "certified")
    written = re.findall(r"(\d+) claims: (\d+) certified", readme)
    assert written, "the README no longer states the register's counts"
    for claims, certified_written in written:
        assert (int(claims), int(certified_written)) == (len(CLAIMS), certified), (
            claims,
            certified_written,
        )


# ------------------------------------------------------------ negative controls
#
# Each rule above is driven over a row corrupted to break it. A rule nobody has
# watched fail is a rule that may already be unreachable.


def _first(predicate) -> dict:
    return copy.deepcopy(next(row for row in CLAIMS if predicate(row)))


def _mock_the_runtime(row: dict, flag_material: bool) -> dict:
    """Replace the runtime in a claim's first real record with the labelled mock."""
    held = row["evidenceRecords"][0]
    held["execution"]["executedComponents"] = [
        component
        for component in held["execution"]["executedComponents"]
        if component["role"] != "inference-runtime"
    ]
    held["execution"]["substitutions"] = [
        {
            "componentId": "llama-cpp-server",
            "role": "inference-runtime",
            "substituteKind": "mock",
            "claimMaterial": flag_material,
            "rationale": "The labelled mock stood in for the pinned runtime.",
        }
    ]
    return row


def test_the_evidence_level_rule_refuses_a_mock_record_at_c2() -> None:
    """The replacement for the v1alpha1 ceiling control.

    A mock at C2 is refused whether the record calls the mock material -- the
    schema refuses a material substitution at C2 -- or immaterial -- the validator
    holds it to the claim's declaration.
    """
    for flag in (True, False):
        row = _mock_the_runtime(
            _first(
                lambda row: (
                    row["claimId"]
                    == "the-selected-model-serves-a-real-completion-through-the-inferops-api"
                )
            ),
            flag_material=flag,
        )
        with pytest.raises(AssertionError):
            test_every_record_is_held_to_the_evidence_level_rules(row)


def test_the_real_behaviour_rule_refuses_a_serving_claim_backed_by_a_mock() -> None:
    row = _first(
        lambda row: (
            row["claimId"]
            == "the-selected-model-serves-a-real-completion-through-the-inferops-api"
        )
    )
    for held in row["evidenceRecords"]:
        held["evidenceLevel"] = "C1"
    with pytest.raises(AssertionError):
        test_a_real_behaviour_claim_rests_on_evidence_that_can_support_one(row)


def test_the_rank_rule_refuses_a_row_certified_above_a_planned_strategy_claim() -> None:
    row = _first(lambda row: row["strategyClaimIds"] and row["status"] == "planned")
    row["status"] = "certified"
    with pytest.raises(AssertionError):
        test_a_row_never_outranks_the_strategy_claim_it_maps_to(row)


def test_the_citation_rule_refuses_a_planned_row_that_cites_a_record() -> None:
    row = _first(lambda row: row["status"] == "planned")
    row["evidenceRecords"] = copy.deepcopy(
        _first(lambda row: row["status"] == "certified")["evidenceRecords"]
    )
    with pytest.raises(AssertionError):
        test_a_planned_or_deferred_row_cites_no_record(row)


def test_the_evidence_rule_refuses_a_template_cited_as_a_record() -> None:
    row = _first(lambda row: row["status"] == "certified")
    row["evidenceRecords"][0]["evidenceRefs"] = [
        "docs/proof/templates/TEMPLATE-claim-evidence.md"
    ]
    with pytest.raises(AssertionError):
        test_every_evidence_reference_is_a_committed_record(row)


def test_the_vocabulary_rule_refuses_an_estimate_described_as_a_bill() -> None:
    with pytest.raises(AssertionError):
        test_no_row_describes_an_amount_in_an_invoices_vocabulary(
            "under-test",
            "limitation",
            "The estimated amount is taken from the invoice.",
        )


def test_the_vocabulary_rule_admits_the_sentence_that_denies_the_word() -> None:
    """Otherwise the rule refuses the register's own statement of the rule."""
    test_no_row_describes_an_amount_in_an_invoices_vocabulary(
        "under-test", "limitation", "No amount here is an invoice, and none ever was."
    )


def test_the_provider_rule_refuses_a_real_kubernetes_row_with_no_provider() -> None:
    row = _first(
        lambda row: any(
            held["environment"]["environmentId"] == "local-kubernetes"
            for held in row["evidenceRecords"]
        )
    )
    for held in row["evidenceRecords"]:
        if held["environment"]["environmentId"] == "local-kubernetes":
            held["environment"]["provider"] = "not-applicable"
    with pytest.raises(AssertionError):
        test_a_real_kubernetes_row_names_the_provider_it_ran_on(row)


def test_the_coverage_gap_rule_refuses_a_row_that_drops_a_recorded_gap() -> None:
    row = _first(lambda row: row["recordedCoverageGaps"])
    row["recordedCoverageGaps"] = []
    with pytest.raises(AssertionError):
        test_a_row_records_the_coverage_gaps_the_inventory_records(row)


def test_the_coverage_gap_rule_refuses_a_gap_the_limitation_hides() -> None:
    row = _first(lambda row: row["recordedCoverageGaps"])
    row["limitation"] = "One host, one day, and nothing else worth saying about it."
    with pytest.raises(AssertionError):
        test_a_row_with_a_recorded_coverage_gap_says_so_in_its_limitation(row)


def test_the_real_evidence_rule_refuses_a_real_row_that_does_not_declare_it() -> None:
    row = _first(lambda row: row["assertsRealBehaviour"] and "C2" in levels(row))
    row["assertsRealBehaviour"] = False
    with pytest.raises(AssertionError):
        test_a_row_on_real_evidence_declares_that_it_asserts_real_behaviour(row)


def test_the_limitation_rule_refuses_a_row_that_states_none() -> None:
    row = _first(lambda row: True)
    row["limitation"] = ""
    with pytest.raises(AssertionError):
        test_every_row_states_a_limitation_and_what_it_does_not_establish(row)


def test_the_quotation_rule_refuses_a_command_the_record_does_not_contain() -> None:
    row = _first(
        lambda row: any(
            held.get("procedure", {}).get("commands") for held in row["evidenceRecords"]
        )
    )
    held = next(
        held for held in row["evidenceRecords"] if held["procedure"].get("commands")
    )
    held["procedure"]["commands"] = ["uv run --locked python -m a_tool_nobody_ran"]
    with pytest.raises(AssertionError):
        test_every_record_quotes_its_commands_and_identifiers_from_its_own_files(row)


def test_the_completeness_rule_refuses_an_ungoverned_readme_entry_point() -> None:
    """The rule this suite shipped without a control, added after a review.

    It is the rule the register rests on — a README entry point that no row
    claims and no exclusion excuses — and it was the only one of the ten never
    watched failing. An independent review found that, which is the thing the
    suite's own docstring says a control exists to prevent.
    """
    ungoverned = "docs/a-surface-nobody-registered.md"
    assert ungoverned not in CLAIMED_PATHS
    assert ungoverned not in NON_CLAIM_PATHS
    remaining = {*README_TARGETS, ungoverned} - CLAIMED_PATHS - NON_CLAIM_PATHS
    assert remaining == {ungoverned}, remaining


def test_the_completeness_rule_refuses_an_excuse_the_readme_does_not_show() -> None:
    """The other direction, so the exclusion list cannot become a parking space."""
    invented = "docs/a-surface-the-readme-does-not-show.md"
    absent = (NON_CLAIM_PATHS | {invented}) - set(README_TARGETS)
    assert absent == {invented}, absent
