"""Deterministic checks over the V1 claim and evidence matrix.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness.

What this suite establishes is that the matrix cannot quietly say more than the
repository supports: that every row names a limitation and what it does not
establish; that a row mapped to a claim in the test strategy never carries a
stronger status than that claim does; that a certified row cites a record that
exists under ``docs/proof/`` and is not a template, and that an uncertified one
cites none; that a row's certification level fits the ceiling its evidence label
carries; that a row asserting real serving, performance, or reliability behaviour
rests on an evidence label that may support one, so a mock can never appear behind
a serving claim; that a real Kubernetes row names a provider the cluster provider
contract publishes, so Docker Desktop evidence cannot be read as `kind`; that no
row describes an amount in the vocabulary reserved for an invoice; and that every
public entry point the README publishes is either claimed by a row or listed, with
a reason, as a surface that claims nothing.

What it does not establish is that any statement in the matrix is true. It checks
references, ranks, ceilings, and vocabulary. Whether a record says what the row
citing it says it says is a reading, and no test here performs one — which is why
the matrix carries that limitation in its own data rather than only here.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTING_DIR = REPO_ROOT / "docs" / "testing"
MATRIX_PATH = TESTING_DIR / "claim-evidence-matrix.v1alpha1.json"
DOCUMENT_PATH = TESTING_DIR / "claim-evidence-matrix.md"
STRATEGY_PATH = TESTING_DIR / "test-strategy.v1alpha1.json"
INVENTORY_PATH = TESTING_DIR / "test-inventory.v1alpha1.json"
GATE_MATRIX_PATH = TESTING_DIR / "ci-gate-matrix.v1alpha1.json"
PROVIDER_CONTRACT_PATH = (
    REPO_ROOT / "docs" / "environment" / "local-cluster-provider-contract.v1alpha1.json"
)
README_PATH = REPO_ROOT / "README.md"

EXPECTED_ID = "https://inferops.io/testing/claim-evidence-matrix.v1alpha1.json"
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha1"

SLUG = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
LEVEL_ID = re.compile(r"^C[0-9]$")

# An identifier as the document publishes it: an inline code span in the first
# column of a Markdown table row. The same shape the strategy suite reads.
FIRST_TABLE_COLUMN = re.compile(
    r"^\|\s*`([A-Za-z0-9][A-Za-z0-9-]*)`\s*\|", flags=re.MULTILINE
)

REQUIRED_TOP_LEVEL = (
    "$id",
    "contractVersion",
    "title",
    "description",
    "documentRef",
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
    "evidenceLabels",
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
    "certificationLevel",
    "evidenceLabel",
    "assertsRealBehaviour",
    "provider",
    "environment",
    "strategyClaimIds",
    "implementationRefs",
    "automatedTestRefs",
    "ciGateIds",
    "evidenceRefs",
    "versionsRecordedIn",
    "limitation",
    "doesNotEstablish",
    "readmeRefs",
    "notClaimedReason",
)

#: The vocabulary the cost method reserves for the ``actual`` basis, which V1
#: cannot reach. A matrix that described an estimate in these words would undo
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
#: files in this repository. A row carrying one is expected to declare
#: ``assertsRealBehaviour``; this list is a floor, not a definition.
REAL_BEHAVIOUR_WORDS = ("serves a real completion", "real inference")

MATRIX: dict[str, Any] = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
STRATEGY: dict[str, Any] = json.loads(STRATEGY_PATH.read_text(encoding="utf-8"))
INVENTORY: dict[str, Any] = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
GATE_MATRIX: dict[str, Any] = json.loads(GATE_MATRIX_PATH.read_text(encoding="utf-8"))
PROVIDER_CONTRACT: dict[str, Any] = json.loads(
    PROVIDER_CONTRACT_PATH.read_text(encoding="utf-8")
)

CLAIMS: list[dict[str, Any]] = MATRIX["claims"]
STATUS_BY_ID = {row["statusId"]: row for row in MATRIX["claimStatuses"]}
LABEL_BY_ID = {row["labelId"]: row for row in MATRIX["evidenceLabels"]}
AREA_IDS = {row["areaId"] for row in MATRIX["areas"]}

STRATEGY_CLAIMS = {row["claimId"]: row for row in STRATEGY["claims"]}
STRATEGY_ENVIRONMENTS = set(STRATEGY["environments"])
STRATEGY_LEVELS = {row["levelId"]: row for row in STRATEGY["certificationLevels"]}
STRATEGY_CLASSES = {row["classId"] for row in STRATEGY["evidenceClasses"]}
INVENTORY_MODULES = {row["module"] for row in INVENTORY["modules"]}
GATE_IDS = {row["gateId"] for row in GATE_MATRIX["gates"]}
PROVIDER_IDS = {row["providerId"] for row in PROVIDER_CONTRACT["providers"]}

#: A row's status expressed as a number, so "never bolder than the strategy" is
#: an inequality rather than a table of permitted pairs.
RANK = {row["statusId"]: row["rank"] for row in MATRIX["claimStatuses"]}

#: ``none`` is not a level; it is the absence of one, and it sorts below C0.
CEILING_RANK = {"none": -1, "C0": 0, "C1": 1, "C2": 2, "C3": 3, "C4": 4}

#: The strategy's own status vocabulary, mapped onto this matrix's.
STRATEGY_STATUS_RANK = {"certified": 3, "planned": 2, "deferred": 1}


def ids(row: dict) -> str:
    """The pytest identifier for a row: its claim, so a failure names the claim."""
    return row["claimId"]


# ---------------------------------------------------------------- the file


def test_the_matrix_declares_its_identity() -> None:
    assert MATRIX["$id"] == EXPECTED_ID
    assert MATRIX["contractVersion"] == EXPECTED_CONTRACT_VERSION


@pytest.mark.parametrize("field", REQUIRED_TOP_LEVEL)
def test_the_matrix_declares_every_required_section(field: str) -> None:
    assert field in MATRIX, field
    assert MATRIX[field] not in ("", [], {}), field


@pytest.mark.parametrize(
    "field",
    (
        "documentRef",
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


def test_the_matrix_holds_claims_in_every_declared_area() -> None:
    used = {row["area"] for row in CLAIMS}
    assert used == AREA_IDS, {"declared but unused": sorted(AREA_IDS - used)}


def test_every_status_in_the_vocabulary_is_used_by_at_least_one_row() -> None:
    """All four states are real, and a register showing only three hides one."""
    used = {row["status"] for row in CLAIMS}
    assert used == set(STATUS_BY_ID), {
        "declared but unused": sorted(set(STATUS_BY_ID) - used)
    }


def test_the_evidence_labels_agree_with_the_certification_document() -> None:
    """The label vocabulary is the strategy's classes plus the unreachable one.

    ``production-experience`` is deliberately absent from the strategy's class
    table — no layer can produce it — and deliberately present here, because a
    claim register has to be able to say that a label exists and is unreachable.
    """
    declared = set(LABEL_BY_ID)
    assert declared >= STRATEGY_CLASSES, {
        "class the strategy has and the matrix does not": sorted(
            STRATEGY_CLASSES - declared
        )
    }
    assert declared - STRATEGY_CLASSES == {"production-experience"}, sorted(
        declared - STRATEGY_CLASSES
    )
    assert LABEL_BY_ID["production-experience"]["reachedInV1"] is False


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
def test_every_row_names_a_known_area_status_label_and_environment(row: dict) -> None:
    assert row["area"] in AREA_IDS, row["area"]
    assert row["status"] in STATUS_BY_ID, row["status"]
    assert row["evidenceLabel"] in LABEL_BY_ID, row["evidenceLabel"]
    assert row["environment"] in STRATEGY_ENVIRONMENTS, row["environment"]
    assert row["provider"] in PROVIDER_IDS | {"not-applicable"}, row["provider"]


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


# ------------------------------------------------------- status and ceiling


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_certified_row_cites_a_record_and_names_its_level(row: dict) -> None:
    if row["status"] != "certified":
        return
    assert row["evidenceRefs"], row["claimId"]
    assert row["certificationLevel"] is not None, row["claimId"]
    assert LEVEL_ID.match(row["certificationLevel"]), row["certificationLevel"]
    assert STRATEGY_LEVELS[row["certificationLevel"]]["v1Scope"] is True, row["claimId"]


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_an_uncertified_row_carries_no_level(row: dict) -> None:
    if row["status"] == "certified":
        return
    assert row["certificationLevel"] is None, (row["claimId"], row["status"])


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_planned_or_deferred_row_cites_no_record(row: dict) -> None:
    """The rule the claim and test matrix already enforces, restated here.

    A planned claim citing a record is a failure rather than an optimism. The
    exception is ``not-claimed``: a claim this project has measured itself unable
    to make cites the record that measured it, which is the opposite failure mode.
    """
    if row["status"] not in ("planned", "deferred"):
        return
    assert not row["evidenceRefs"], (row["claimId"], row["evidenceRefs"])
    assert row["versionsRecordedIn"] is None, row["claimId"]


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
def test_a_level_never_exceeds_the_ceiling_its_label_carries(row: dict) -> None:
    if row["certificationLevel"] is None:
        return
    ceiling = LABEL_BY_ID[row["evidenceLabel"]]["ceiling"]
    assert CEILING_RANK[row["certificationLevel"]] <= CEILING_RANK[ceiling], {
        "claim": row["claimId"],
        "label": row["evidenceLabel"],
        "ceiling": ceiling,
        "level claimed": row["certificationLevel"],
    }


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_real_behaviour_claim_rests_on_evidence_that_can_support_one(
    row: dict,
) -> None:
    """A mock, a simulation, or an estimate may never appear behind a real claim.

    This is the ceiling rule applied to the public register rather than to the
    strategy: it is easy to write a serving sentence and cite the suite that
    drives the mock, and that is exactly the row this refuses.
    """
    if not row["assertsRealBehaviour"] or row["status"] != "certified":
        return
    label = LABEL_BY_ID[row["evidenceLabel"]]
    assert label["maySupportRealBehaviour"], {
        "claim": row["claimId"],
        "label": row["evidenceLabel"],
    }
    assert row["evidenceRefs"], row["claimId"]


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_statement_about_real_serving_declares_that_it_is_one(row: dict) -> None:
    statement = row["statement"].lower()
    if not any(word in statement for word in REAL_BEHAVIOUR_WORDS):
        return
    assert row["assertsRealBehaviour"] is True, row["claimId"]


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_real_kubernetes_row_names_the_provider_it_ran_on(row: dict) -> None:
    """Runtime evidence records its provider, and certifies no other one."""
    if row["evidenceLabel"] != "local-real-cpu":
        return
    if row["environment"] != "local-kubernetes":
        return
    assert row["provider"] in PROVIDER_IDS, (row["claimId"], row["provider"])


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
def test_every_gate_reference_is_a_gate_the_gate_matrix_declares(row: dict) -> None:
    for gate_id in row["ciGateIds"]:
        assert gate_id in GATE_IDS, (row["claimId"], gate_id)


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_every_evidence_reference_is_a_committed_record(row: dict) -> None:
    template_root = MATRIX["templateRoot"]
    for ref in row["evidenceRefs"]:
        assert ref.startswith(MATRIX["evidenceRoot"] + "/"), (row["claimId"], ref)
        assert not ref.startswith(template_root + "/"), (row["claimId"], ref)
        assert (REPO_ROOT / ref).exists(), (row["claimId"], ref)


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_the_record_naming_the_versions_is_one_of_the_records_cited(row: dict) -> None:
    if row["versionsRecordedIn"] is None:
        return
    assert row["versionsRecordedIn"] in row["evidenceRefs"], row["claimId"]


@pytest.mark.parametrize("row", CLAIMS, ids=ids)
def test_a_certified_row_names_where_its_immutable_versions_are_recorded(
    row: dict,
) -> None:
    if row["status"] != "certified":
        return
    assert row["versionsRecordedIn"], row["claimId"]


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
    describes them, because the sentence a reader remembers is the one in the
    matrix rather than the one in the record.

    A reserved word survives only inside a sentence that denies it. Banning the
    words outright was tried first and was wrong: it makes the rule itself
    unsayable, and a register that cannot name the vocabulary it refuses cannot
    tell a reader what the refusal is.
    """
    for sentence in re.split(r"(?<=[.;])\s+", value):
        lowered = sentence.lower()
        found = [word for word in INVOICE_VOCABULARY if word in lowered]
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
    """The completeness check this PR exists to add.

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
        | set(LABEL_BY_ID)
        | AREA_IDS
        | {row["ruleId"] for row in MATRIX["prohibitions"]}
    )
    extra = sorted(DOCUMENT_IDENTIFIERS - known)
    assert not extra, {"in the document, absent from the data": extra}


@pytest.mark.parametrize("row", MATRIX["prohibitions"], ids=lambda row: row["ruleId"])
def test_every_prohibition_is_a_slug_with_a_statement(row: dict) -> None:
    assert SLUG.match(row["ruleId"]), row["ruleId"]
    assert len(row["statement"]) > 40, row["ruleId"]


def test_the_document_states_the_counts_the_data_produces() -> None:
    """A count in prose is a number somebody typed unless something checks it."""
    counts = {
        status: sum(1 for row in CLAIMS if row["status"] == status)
        for status in STATUS_BY_ID
    }
    assert f"{len(CLAIMS)} claims" in DOCUMENT_TEXT, len(CLAIMS)
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


# ------------------------------------------------------------ negative controls
#
# Each rule above is driven over a row corrupted to break it. A rule nobody has
# watched fail is a rule that may already be unreachable.


def _first(predicate) -> dict:
    return copy.deepcopy(next(row for row in CLAIMS if predicate(row)))


def test_the_ceiling_rule_refuses_a_mock_certified_at_c2() -> None:
    row = _first(lambda row: row["status"] == "certified")
    row["evidenceLabel"] = "mock"
    row["certificationLevel"] = "C2"
    with pytest.raises(AssertionError):
        test_a_level_never_exceeds_the_ceiling_its_label_carries(row)


def test_the_real_behaviour_rule_refuses_a_serving_claim_backed_by_a_mock() -> None:
    row = _first(
        lambda row: row["assertsRealBehaviour"] and row["status"] == "certified"
    )
    row["evidenceLabel"] = "mock"
    with pytest.raises(AssertionError):
        test_a_real_behaviour_claim_rests_on_evidence_that_can_support_one(row)


def test_the_rank_rule_refuses_a_row_certified_above_a_planned_strategy_claim() -> None:
    row = _first(lambda row: row["strategyClaimIds"] and row["status"] == "planned")
    row["status"] = "certified"
    with pytest.raises(AssertionError):
        test_a_row_never_outranks_the_strategy_claim_it_maps_to(row)


def test_the_citation_rule_refuses_a_planned_row_that_cites_a_record() -> None:
    row = _first(lambda row: row["status"] == "planned")
    row["evidenceRefs"] = ["docs/proof/README.md"]
    with pytest.raises(AssertionError):
        test_a_planned_or_deferred_row_cites_no_record(row)


def test_the_evidence_rule_refuses_a_template_cited_as_a_record() -> None:
    row = _first(lambda row: row["status"] == "certified")
    row["evidenceRefs"] = ["docs/proof/templates/TEMPLATE-claim-evidence.md"]
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
        lambda row: (
            row["evidenceLabel"] == "local-real-cpu"
            and row["environment"] == "local-kubernetes"
        )
    )
    row["provider"] = "not-applicable"
    with pytest.raises(AssertionError):
        test_a_real_kubernetes_row_names_the_provider_it_ran_on(row)


def test_the_limitation_rule_refuses_a_row_that_states_none() -> None:
    row = _first(lambda row: True)
    row["limitation"] = ""
    with pytest.raises(AssertionError):
        test_every_row_states_a_limitation_and_what_it_does_not_establish(row)
