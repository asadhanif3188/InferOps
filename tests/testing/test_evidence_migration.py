"""The evidence migration from `v1alpha1` to `v1alpha2`, held to what it says it did.

`V1-S5-012-PR2` read every record the `v1alpha1` register cited against the current
evidence-level definitions and wrote the `v1alpha2` register from that reading. The
failure this module exists to prevent is the one ADR 0016 D8 names: a terminology
change that promotes a claim. So the checks here compare the two registers and the
committed audit record, and establish that no claim's identity, statement, or
citations moved on the way across; that every status, flag, and sentence that did
move is one the audit record names, with the text before and after; that every
record's outcome is the one the two registers imply rather than the one somebody
wrote down; that every level that moved carries a justification, and every level
that moved *up* is named here by identifier, so a later one has to be added on
purpose; that every quote the audit rests on is verbatim in the file it names; that
the superseded register is kept as it was; and that every number the migration
report publishes is recomputed from those files.

What it does not establish is that any reading was right. Whether a record is `C2`
or `C0` for its claim is a judgement the audit made and recorded, and the report
lists the places it could have gone the other way. This module checks that the
judgement is written down and consistent, not that it is correct.

**What it compares is the register as the migration left it.** `V1-S5-006-PR1`
changed the register afterwards -- it narrowed four statements, moved citations, and
added records -- and its normalization ledger names every one of those changes with
the value before and after. `V1-S5-006-PR2` changed it again, and its completeness
ledger does the same. This module undoes both ledgers, last change first, before it
compares anything, so it keeps checking the migration rather than the migration plus
everything since, and a later change neither ledger names makes the undo fail here
rather than pass unseen. What the later changes did is checked by
`tests/testing/test_evidence_index.py` and `tests/testing/test_evidence_completeness.py`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from tools.evidence_index import load_ledgers, restore_migrated_register
from tools.evidence_model import (
    CONTRACT_VERSION,
    LEGACY_CONTRACT_VERSION,
    LEGACY_REGISTER_PATH,
    REGISTER_PATH,
    load_legacy_register,
    load_register,
)

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = (
    REPO_ROOT / "docs" / "proof" / "testing" / "v1-s5-012-pr2-migration.v1alpha1.json"
)
REPORT_PATH = (
    REPO_ROOT / "docs" / "proof" / "testing" / "v1-s5-012-pr2-migration-report.md"
)

LEGACY = load_legacy_register()
CURRENT_REGISTER = load_register()
#: The register as `V1-S5-012-PR2` wrote it, recovered by undoing every change the
#: `V1-S5-006-PR1` and `V1-S5-006-PR2` ledgers name. The undo raises if the register
#: does not hold exactly what a ledger says was written.
REGISTER = restore_migrated_register(CURRENT_REGISTER, load_ledgers())
AUDIT: dict[str, Any] = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
REPORT = REPORT_PATH.read_text(encoding="utf-8")
REPORT_FLAT = " ".join(REPORT.split())

LEGACY_BY_ID = {row["claimId"]: row for row in LEGACY["claims"]}
REGISTER_BY_ID = {row["claimId"]: row for row in REGISTER["claims"]}
AUDIT_BY_ID = {row["claimId"]: row for row in AUDIT["claims"]}

#: The claim fields a migration may not touch at all. A claim's identity, what it
#: says, and what it cites are the claim; changing any of them in a migration would
#: make the before-and-after comparison meaningless.
UNTOUCHABLE = (
    "area",
    "statement",
    "strategyClaimIds",
    "implementationRefs",
    "automatedTestRefs",
    "recordedCoverageGaps",
    "ciGateIds",
    "readmeRefs",
)

#: The claim fields a migration may change, but only where the audit record names
#: the change with its text before and after.
CORRECTABLE = ("limitation", "doesNotEstablish", "assertsRealBehaviour")

#: Every record whose level sits above the level its claim carried. Pinned rather
#: than derived, because this is the direction ADR 0016 D8 guards: a migration that
#: raised a level has to say which, and a later change that raises another has to
#: add it here, in public, beside its justification in the audit record.
RAISED = frozenset(
    {
        "the-workload-domain-parses-a-contract-document-into-typed-objects-c2",
        "a-workload-scaffold-is-generated-without-overwriting-anything-c2",
        "the-developer-quick-start-runs-end-to-end-on-a-clean-checkout-real-smoke-c2",
    }
)

AUDIT_QUESTIONS = (
    "q1_claim",
    "q2_executed",
    "q3_substituted",
    "q4_workload",
    "q5_where",
    "q6_level",
    "q7_limits",
    "q8_metadata",
)

LEVEL_ORDER = ("C0", "C1", "C2", "C3", "C4")


def records(row: dict[str, Any]) -> list[dict[str, Any]]:
    return list(row.get("evidenceRecords") or [])


def outcome(legacy_row: dict[str, Any], record: dict[str, Any]) -> str:
    """What the two registers say happened to one record.

    A record is one the migration added when it cites nothing its claim's v1alpha1
    row cited. The first draft recognised it by an identifier suffix, and an
    independent review pointed out that a later added record named differently
    would have been counted as carried across.
    """
    legacy_level = legacy_row["certificationLevel"]
    if record["migrationState"] != "migrated":
        return "left-legacy-unmigrated"
    if not set(record["evidenceRefs"]) & set(legacy_row["evidenceRefs"]):
        return "added-by-the-migration"
    if legacy_level is None:
        return "classified-from-no-legacy-level"
    if record["evidenceLevel"] == legacy_level:
        return "retained-equivalent"
    return "reclassified"


def all_outcomes() -> dict[str, str]:
    return {
        record["recordId"]: outcome(LEGACY_BY_ID[row["claimId"]], record)
        for row in REGISTER["claims"]
        for record in records(row)
    }


def normalised(text: str) -> str:
    return " ".join(text.split())


# ------------------------------------------------------------ the two registers


def test_the_authoritative_register_is_v1alpha2() -> None:
    """The tripwire `V1-S5-011-PR2` left for this change, now a statement of fact."""
    assert CURRENT_REGISTER["contractVersion"] == CONTRACT_VERSION
    assert CURRENT_REGISTER["supersedes"] == LEGACY_CONTRACT_VERSION
    assert REGISTER_PATH.name == "claim-evidence-matrix.v1alpha2.json"


def test_the_superseded_register_is_kept_as_the_migrations_starting_point() -> None:
    """History is kept rather than rewritten, and it is still what it was.

    The v1alpha1 register still declares its version and still stores one level per
    claim, because that is what the migration read. It is not deleted: the reader in
    `tools/evidence_model` and this module both need it to show what changed.
    """
    assert LEGACY["contractVersion"] == LEGACY_CONTRACT_VERSION
    assert LEGACY_REGISTER_PATH.name == "claim-evidence-matrix.v1alpha1.json"
    assert all("certificationLevel" in row for row in LEGACY["claims"])
    assert not any("evidenceRecords" in row for row in LEGACY["claims"])


def test_no_consumer_reads_the_superseded_register_as_current() -> None:
    """Every tool and every register reference now points at v1alpha2.

    The superseded file may be named where history is being described, and by the
    reader and this module, which compare against it. It may not be what a tool
    loads as the register.
    """
    readers = [
        REPO_ROOT / "tools" / "proof_dashboard" / "core.py",
        REPO_ROOT / "docs" / "cost" / "cost-capacity-method.v1alpha1.json",
        REPO_ROOT / "docs" / "security" / "security-method.v1alpha1.json",
        REPO_ROOT / "docs" / "telemetry" / "observability-method.v1alpha1.json",
    ]
    for path in readers:
        text = path.read_text(encoding="utf-8")
        assert "claim-evidence-matrix.v1alpha1.json" not in text, path
    for path in readers[1:]:
        assert "claim-evidence-matrix.v1alpha2.json" in path.read_text(
            encoding="utf-8"
        ), path


def test_the_same_claims_in_the_same_order() -> None:
    assert [row["claimId"] for row in REGISTER["claims"]] == [
        row["claimId"] for row in LEGACY["claims"]
    ]


@pytest.mark.parametrize("claim_id", list(REGISTER_BY_ID))
def test_a_claims_identity_statement_and_citations_did_not_move(claim_id: str) -> None:
    before, after = LEGACY_BY_ID[claim_id], REGISTER_BY_ID[claim_id]
    for field in UNTOUCHABLE:
        assert after[field] == before[field], (claim_id, field)


@pytest.mark.parametrize("claim_id", list(REGISTER_BY_ID))
def test_the_carried_classification_is_the_v1alpha1_one_verbatim(claim_id: str) -> None:
    before = LEGACY_BY_ID[claim_id]
    carried = REGISTER_BY_ID[claim_id]["legacyClassification"]
    assert carried["sourceVersion"] == LEGACY_CONTRACT_VERSION
    for field in ("certificationLevel", "evidenceLabel", "provider", "environment"):
        assert carried[field] == before[field], (claim_id, field)


@pytest.mark.parametrize("claim_id", list(REGISTER_BY_ID))
def test_every_legacy_citation_is_carried_by_a_record_and_none_is_invented(
    claim_id: str,
) -> None:
    """The migration moves citations into records; it drops none and adds none.

    The one exception is a record the audit itself produced, which cites the
    migration's own report, and the audit record says so.
    """
    before = set(LEGACY_BY_ID[claim_id]["evidenceRefs"])
    cited = {
        reference
        for record in records(REGISTER_BY_ID[claim_id])
        if outcome(LEGACY_BY_ID[claim_id], record) != "added-by-the-migration"
        for reference in record["evidenceRefs"]
    }
    assert cited == before, (claim_id, sorted(cited ^ before))


# ------------------------------------------------------- what the audit names


@pytest.mark.parametrize("claim_id", list(REGISTER_BY_ID))
def test_every_changed_sentence_or_flag_is_a_named_correction(claim_id: str) -> None:
    """A claim's own prose moved only where the audit record says, and how."""
    before, after = LEGACY_BY_ID[claim_id], REGISTER_BY_ID[claim_id]
    corrections = AUDIT_BY_ID[claim_id]["corrections"]
    named = {entry["field"] for entry in corrections}
    for field in CORRECTABLE:
        if after[field] != before[field]:
            assert field in named, (claim_id, field)
    for entry in corrections:
        field = entry["field"]
        if isinstance(entry["before"], str):
            assert entry["before"] in before[field], (claim_id, field)
            assert entry["after"] in after[field], (claim_id, field)
        else:
            assert (before[field], after[field]) == (entry["before"], entry["after"])


@pytest.mark.parametrize("claim_id", list(REGISTER_BY_ID))
def test_a_status_moved_only_where_the_audit_says_why(claim_id: str) -> None:
    before, after = LEGACY_BY_ID[claim_id], REGISTER_BY_ID[claim_id]
    audit = AUDIT_BY_ID[claim_id]
    assert (audit["statusBefore"], audit["statusAfter"]) == (
        before["status"],
        after["status"],
    )
    if before["status"] != after["status"]:
        assert audit.get("statusChangeReason"), claim_id
        assert after["notClaimedReason"] != before["notClaimedReason"], claim_id


def test_no_status_moved_upward() -> None:
    """A demotion is a finding; a promotion in a migration is the defect itself."""
    rank = {row["statusId"]: row["rank"] for row in REGISTER["claimStatuses"]}
    raised = [
        claim_id
        for claim_id, row in REGISTER_BY_ID.items()
        if rank[row["status"]] > rank[LEGACY_BY_ID[claim_id]["status"]]
    ]
    assert not raised, raised


def test_the_audit_record_holds_every_claim_once() -> None:
    assert [row["claimId"] for row in AUDIT["claims"]] == list(REGISTER_BY_ID)


@pytest.mark.parametrize("claim_id", list(REGISTER_BY_ID))
def test_every_record_outcome_is_the_one_the_registers_imply(claim_id: str) -> None:
    held = records(REGISTER_BY_ID[claim_id])
    audited = AUDIT_BY_ID[claim_id]["records"]
    assert [entry["recordId"] for entry in audited] == [r["recordId"] for r in held]
    derived = all_outcomes()
    for entry, record in zip(audited, held, strict=True):
        assert entry["evidenceLevel"] == record["evidenceLevel"], entry["recordId"]
        assert entry["outcome"] == derived[record["recordId"]], entry["recordId"]
        if entry["outcome"] != "retained-equivalent":
            assert len(entry.get("justification", "")) > 80, entry["recordId"]


def test_every_level_that_moved_up_is_named_here() -> None:
    """The direction ADR 0016 D8 guards, pinned rather than derived."""
    raised = set()
    for row in REGISTER["claims"]:
        before = LEGACY_BY_ID[row["claimId"]]["certificationLevel"]
        if before is None:
            continue
        for record in records(row):
            level = record.get("evidenceLevel")
            if level and LEVEL_ORDER.index(level) > LEVEL_ORDER.index(before):
                raised.add(record["recordId"])
    assert raised == RAISED, {"not named": sorted(raised - RAISED)}


def test_no_record_is_c3_or_c4_and_nothing_was_mapped_there() -> None:
    """No mechanical mapping exists, because there was nothing to map and nothing moved there."""
    assert not any(
        row["certificationLevel"] in ("C3", "C4") for row in LEGACY["claims"]
    )
    assert not any(
        record.get("evidenceLevel") in ("C3", "C4")
        for row in REGISTER["claims"]
        for record in records(row)
    )


@pytest.mark.parametrize(
    "claim_id", [c for c in REGISTER_BY_ID if records(REGISTER_BY_ID[c])]
)
def test_every_claim_that_cites_a_record_answers_the_eight_questions(
    claim_id: str,
) -> None:
    audit = AUDIT_BY_ID[claim_id]["audit"]
    assert audit, claim_id
    for question in AUDIT_QUESTIONS:
        assert audit[question].strip(), (claim_id, question)
    assert audit["sources"], claim_id


def _sources() -> list[tuple[str, str, str]]:
    return [
        (row["claimId"], source["path"], source["quote"])
        for row in AUDIT["claims"]
        if row["audit"]
        for source in row["audit"]["sources"]
    ]


@pytest.mark.parametrize(
    ("claim_id", "path", "quote"),
    _sources(),
    ids=lambda value: value[:40] if isinstance(value, str) else "",
)
def test_every_quote_the_audit_rests_on_is_verbatim(
    claim_id: str, path: str, quote: str
) -> None:
    """A quote that is not in the file is a paraphrase wearing quotation marks."""
    text = normalised((REPO_ROOT / path).read_text(encoding="utf-8"))
    assert normalised(quote) in text, (claim_id, path, quote[:80])


def test_the_audit_record_names_no_private_path() -> None:
    text = AUDIT_PATH.read_text(encoding="utf-8")
    # A drive letter not preceded by another letter, so `https://` is not one.
    assert not re.search(r"(?i)(?<![a-z])[a-z]:[\\/]|/users/|scratchpad|planning", text)


# --------------------------------------------------- the measured absence


def _authorisation_count() -> tuple[int, int]:
    """Markdown records cited by claims v1alpha1 held as certified, and how many
    say nothing about authorisation at all."""
    cited = sorted(
        {
            reference
            for row in LEGACY["claims"]
            if row["status"] == "certified"
            for reference in row["evidenceRefs"]
            if reference.endswith(".md")
        }
    )
    silent = [
        reference
        for reference in cited
        if not re.search(
            r"authori[sz]", (REPO_ROOT / reference).read_text(encoding="utf-8"), re.I
        )
    ]
    return len(cited), len(silent)


def test_the_authorisation_count_is_what_the_records_say() -> None:
    total, silent = _authorisation_count()
    certified = sum(1 for row in LEGACY["claims"] if row["status"] == "certified")
    assert (
        f"Of the **{total}** Markdown records cited by the **{certified}** claims"
        in REPORT_FLAT
    )
    assert f"**{silent}** contain no statement about authorisation" in REPORT_FLAT
    claim = REGISTER_BY_ID[
        "every-certifying-record-lives-under-docs-proof-and-declares-its-own-boundary"
    ]
    measured = claim["evidenceRecords"][-1]
    assert f"Of the {total} Markdown records" in measured["results"][0]["statement"]
    assert f"{silent} contain no statement" in measured["results"][0]["statement"]


def test_the_claim_the_count_refutes_stays_uncertified_while_the_count_holds() -> None:
    """A tripwire in the direction that matters.

    The day every record carries an authorisation statement, the count reaches
    zero and this fails, so that restoring the claim is a decision somebody makes
    rather than a status that drifts back.
    """
    _, silent = _authorisation_count()
    claim = next(
        row
        for row in CURRENT_REGISTER["claims"]
        if row["claimId"]
        == "every-certifying-record-lives-under-docs-proof-and-declares-its-own-boundary"
    )
    assert silent > 0, "the count reached zero; revisit the not-claimed claim"
    assert claim["status"] == "not-claimed"


# ------------------------------------------------------- the published report


def _counts() -> dict[str, int]:
    claims = REGISTER["claims"]
    outcomes = list(all_outcomes().values())
    corrected = [
        row["claimId"]
        for row in AUDIT["claims"]
        if any(
            entry["field"] in ("limitation", "doesNotEstablish")
            for entry in row["corrections"]
        )
    ]
    flagged = [
        row["claimId"]
        for row in AUDIT["claims"]
        if any(entry["field"] == "assertsRealBehaviour" for entry in row["corrections"])
    ]
    return {
        "claims": len(claims),
        "holding": sum(1 for row in claims if records(row)),
        "multiple": sum(1 for row in claims if len(records(row)) > 1),
        "records": sum(len(records(row)) for row in claims),
        "unmigrated": outcomes.count("left-legacy-unmigrated"),
        "changed": outcomes.count("reclassified"),
        "statuses": sum(
            1
            for row in claims
            if row["status"] != LEGACY_BY_ID[row["claimId"]]["status"]
        ),
        "corrected": len(corrected),
        "flagged": len(flagged),
        "statements": sum(
            1
            for row in claims
            if row["statement"] != LEGACY_BY_ID[row["claimId"]]["statement"]
        ),
        "c3c4": sum(
            1
            for row in claims
            for record in records(row)
            if record.get("evidenceLevel") in ("C3", "C4")
        ),
    }


@pytest.mark.parametrize(
    ("label", "key"),
    [
        ("Claims in the register", "claims"),
        ("Claims holding at least one evidence record", "holding"),
        ("Claims holding more than one evidence record", "multiple"),
        ("Evidence records", "records"),
        ("Records left `legacy-unmigrated`", "unmigrated"),
        ("Records whose level changed from the one their claim carried", "changed"),
        ("Claim statuses changed", "statuses"),
        ("Claims whose own limitation or boundary text was corrected", "corrected"),
        ("Claims whose real-behaviour flag was corrected", "flagged"),
        ("Claim statements changed", "statements"),
        ("Records at `C3` or `C4`", "c3c4"),
    ],
)
def test_every_summary_count_is_recomputed(label: str, key: str) -> None:
    row = next(line for line in REPORT.splitlines() if line.startswith(f"| {label} |"))
    written = row.split("|")[2].strip().split(",")[0]
    assert written == str(_counts()[key]), (label, written, _counts()[key])


@pytest.mark.parametrize(
    "name",
    [
        "retained-equivalent",
        "reclassified",
        "classified-from-no-legacy-level",
        "added-by-the-migration",
        "left-legacy-unmigrated",
    ],
)
def test_every_outcome_count_is_recomputed(name: str) -> None:
    count = list(all_outcomes().values()).count(name)
    assert f"| `{name}` | {count} |" in REPORT, (name, count)


@pytest.mark.parametrize("level", LEVEL_ORDER)
def test_every_level_count_is_recomputed(level: str) -> None:
    count = sum(
        1
        for row in REGISTER["claims"]
        for record in records(row)
        if record.get("evidenceLevel") == level
    )
    assert f"| `{level}` | {count} |" in REPORT, (level, count)


def test_every_changed_level_is_listed_with_its_reason() -> None:
    outcomes = all_outcomes()
    changed = sorted(r for r, o in outcomes.items() if o == "reclassified")
    for record_id in changed:
        line = next(
            (line for line in REPORT.splitlines() if f"| `{record_id}` |" in line),
            None,
        )
        assert line, record_id
        assert len(line.split("|")[4].strip()) > 60, record_id


def test_the_report_names_every_status_that_moved_and_every_corrected_claim() -> None:
    for row in AUDIT["claims"]:
        if row["statusBefore"] != row["statusAfter"] or any(
            entry["field"] in ("limitation", "doesNotEstablish")
            for entry in row["corrections"]
        ):
            assert f"`{row['claimId']}`" in REPORT, row["claimId"]


def test_the_report_publishes_the_method_its_answers_cite() -> None:
    """The audit answers cite principles by number; the numbers have to resolve."""
    cited = {
        number
        for row in AUDIT["claims"]
        if row["audit"]
        for value in row["audit"].values()
        if isinstance(value, str)
        for number in re.findall(r"\bP(\d{1,2})\b", value)
    }
    for number in cited:
        assert f"**P{number}." in REPORT, number


def test_the_report_says_the_levels_are_project_defined() -> None:
    assert "project-defined" in REPORT_FLAT
    assert (
        "not an ISO, NIST, regulatory, or industry certification standard"
        in REPORT_FLAT
    )
