"""The V1 evidence index and the normalization ledger behind it, held to their sources.

`V1-S5-006-PR1` answered every finding the evidence migration left open, changed the
register to do it, and generated an index of every evidence record. The failures
this module exists to prevent are the ones that change could make quietly: an index
that says something the register does not, a file cited as evidence that is not a
committed file under `docs/proof/` or no longer has the content it was indexed with,
a register change nobody wrote down, a historical record rewritten while a
correction claims it was left alone, a quote that is a paraphrase, a revision
presented as the one that ran when the record says otherwise, and a current document
going back to describing the evidence model as unmigrated.

What it does not establish is that any disposition was the right one. Whether a
statement should have been narrowed rather than a claim downgraded is a judgement
the ledger records with its reason; this module checks that it is recorded,
consistent, and quoted from the files it rests on.
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from tools.evidence_index import (
    CODE_REVISION_RELATIONS,
    COMPLETENESS_PATH,
    DISPOSITIONS,
    INDEX_PATH,
    LEDGER_PATH,
    LEVEL_ORDER,
    apply_register_changes,
    build_index,
    content_sha256,
    entry_sha256,
    load_index,
    load_ledger,
    load_ledgers,
    recorded_date,
    render_index,
    restore_migrated_register,
    states_authorisation,
)
from tools.evidence_model import (
    CONTRACT_VERSION,
    REGISTER_PATH,
    check_register,
    load_register,
)
from tools.proof_dashboard import level_counts, status_counts

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER = load_register()
LEDGER = load_ledger()
#: Both ledgers, in the order applied: `V1-S5-006-PR1`'s normalization and
#: `V1-S5-006-PR2`'s completeness verification. Undoing the register takes both.
LEDGERS = load_ledgers()
INDEX = load_index()
INDEX_PAGE = REPO_ROOT / "docs" / "proof" / "v1-evidence-index.md"
REPORT_PATH = (
    REPO_ROOT / "docs" / "proof" / "testing" / "v1-s5-006-pr1-evidence-normalization.md"
)
AUDIT_REPORT_PATH = (
    REPO_ROOT / "docs" / "proof" / "testing" / "v1-s5-012-pr2-migration-report.md"
)
README_PATH = REPO_ROOT / "README.md"

RECORDS = [
    (claim, record)
    for claim in REGISTER["claims"]
    for record in claim["evidenceRecords"]
]
RECORD_BY_ID = {record["recordId"]: record for _, record in RECORDS}
INDEX_BY_ID = {entry["recordId"]: entry for entry in INDEX["records"]}

#: Every record that executed its target behaviour and names no repository revision
#: as the tree that ran. Pinned rather than derived: this is the gap the
#: normalization carried to `V1-S5-006-PR2`, and a record leaving the set -- or a new
#: one joining it -- has to be a decision somebody makes here, beside the finding.
#: `V1-S5-006-PR2` decided each of them in its completeness ledger, and
#: `tests/testing/test_evidence_completeness.py` derives how each identifies its code.
EXECUTED_WITHOUT_A_STATED_REVISION = frozenset(
    {
        "the-workload-domain-parses-a-contract-document-into-typed-objects-c2",
        "the-inference-api-serves-five-routes-with-explicit-adapter-selection-c1",
        "a-runtime-and-model-pair-was-selected-by-a-recorded-feasibility-procedure-c2",
        "the-model-artifact-matches-its-published-hash-c2-feasibility",
        "a-local-serving-baseline-was-measured-under-a-method-registered-first-c2",
        "the-model-lifecycle-states-were-measured-across-six-real-starts-c2",
        "a-local-cluster-is-created-and-removed-without-residue-c2",
        "the-selected-runtime-serves-a-real-completion-in-a-cluster-c1-feasibility",
        "a-helm-release-installs-and-uninstalls-without-residue-c2",
        "a-controlled-release-change-can-be-reversed-and-real-inference-restored-c2",
        "the-model-artifact-survives-a-pod-replacement-on-a-terraform-owned-claim-c2",
        "repeatable-llm-load-can-be-generated-from-a-versioned-profile-c1-stub-rehearsal",
        "repeatable-llm-load-can-be-generated-from-a-versioned-profile-c2-real-load",
        "a-bounded-local-performance-matrix-was-measured-and-a-degradation-point-observed-c2",
        "caller-visible-impact-of-losing-the-inference-pod-was-measured-under-load-c2",
        "an-unready-model-was-held-unready-and-recovered-by-an-operator-c2",
        "the-api-emits-catalog-metrics-and-structured-request-records-c1",
        "the-rendered-network-policy-is-enforced-by-the-cluster-c1",
    }
)

#: Sentences that described the evidence model as it was before the migration. A
#: current document may not say them again; a dated record may, which is why
#: `docs/proof/`, the changelog, and the decision records -- whose dated notes say
#: what changed -- are outside the scan.
RETIRED_STATEMENTS = (
    r"the proof dashboard still reads `?v1alpha1",
    r"nothing committed derives it yet",
    r"nothing is reclassified and nothing is enforced yet",
    r"migrating the register and the records, and moving those ceilings with it, is",
    r"no person intervened",
    r"nine of them have passed on the selected service",
)


def normalised(text: str) -> str:
    return " ".join(text.split())


def read(path: str | Path) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


@functools.cache
def _git_ls_files() -> frozenset[str] | None:
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return frozenset(path for path in listed.decode("utf-8").split("\0") if path)


def tracked_files() -> frozenset[str]:
    listed = _git_ls_files()
    if listed is None:
        pytest.skip("git is not available to list tracked files")
    return listed


# ------------------------------------------------------------------ the index


def test_the_committed_index_is_what_the_register_and_ledger_produce() -> None:
    """The index says nothing its two sources do not, byte for byte."""
    committed = INDEX_PATH.read_text(encoding="utf-8")
    assert committed == render_index(build_index()), (
        "regenerate with: python -m tools.evidence_index --write"
    )


def test_the_index_is_built_from_the_authoritative_register() -> None:
    assert INDEX["registerRef"] == REGISTER_PATH.relative_to(REPO_ROOT).as_posix()
    assert INDEX["registerContractVersion"] == CONTRACT_VERSION
    assert INDEX["ledgerRef"] == LEDGER_PATH.relative_to(REPO_ROOT).as_posix()
    assert (
        INDEX["completenessRef"] == COMPLETENESS_PATH.relative_to(REPO_ROOT).as_posix()
    )


def test_every_register_record_is_indexed_once_in_register_order() -> None:
    assert [entry["recordId"] for entry in INDEX["records"]] == [
        record["recordId"] for _, record in RECORDS
    ]
    assert [entry["claimId"] for entry in INDEX["claims"]] == [
        claim["claimId"] for claim in REGISTER["claims"]
    ]


@pytest.mark.parametrize("entry", INDEX["records"], ids=lambda entry: entry["recordId"])
def test_every_entry_points_at_its_register_record_and_hashes_it(
    entry: dict[str, Any],
) -> None:
    _, claims, claim_index, _, record_index = entry["registerPointer"].split("/")
    assert claims == "claims"
    record = REGISTER["claims"][int(claim_index)]["evidenceRecords"][int(record_index)]
    assert record["recordId"] == entry["recordId"]
    assert entry_sha256(record) == entry["registerEntrySha256"]


@pytest.mark.parametrize("entry", INDEX["records"], ids=lambda entry: entry["recordId"])
def test_every_entry_keeps_the_dimensions_apart_and_agrees_with_its_level(
    entry: dict[str, Any],
) -> None:
    """Level, substitution, workload source, environment, and status are separate.

    Each is its own field, and the only relation between them the index may show is
    the one the specification defines: a `C1` record names a claim-material
    substitution, and a `C2` record has none.
    """
    material = [
        item for item in entry["execution"]["substitutions"] if item["claimMaterial"]
    ]
    level = entry["evidenceLevel"]
    if level == "C1":
        assert material, entry["recordId"]
    if level in ("C2", "C3", "C4"):
        assert not material, entry["recordId"]
    if level == "C0":
        assert entry["execution"]["targetBehaviourExecuted"] is False
    assert entry["workload"]["source"]
    assert entry["environment"]["environmentId"]
    assert entry["claimStatus"] in {
        row["statusId"] for row in REGISTER["claimStatuses"]
    }


def test_no_record_is_c3_or_c4() -> None:
    """Nothing reached either, and normalization is not a way to get there."""
    assert INDEX["summary"]["recordsByLevel"]["C3"] == 0
    assert INDEX["summary"]["recordsByLevel"]["C4"] == 0


# --------------------------------------------------------- the evidence files


def _cited() -> list[tuple[str, str]]:
    return [
        (entry["recordId"], item["path"])
        for entry in INDEX["records"]
        for item in entry["evidence"]
    ]


@pytest.mark.parametrize(("record_id", "path"), _cited(), ids=lambda value: value[-50:])
def test_every_cited_file_is_committed_evidence_with_the_indexed_content(
    record_id: str, path: str
) -> None:
    """Repository-bound and immutable: under the evidence root, tracked, and unchanged.

    A file under an ignored directory, or held only on the host that ran something,
    cannot be cited here, because it is not under `docs/proof/` and git does not
    track it.
    """
    assert path.startswith("docs/proof/"), (record_id, path)
    assert "/templates/" not in path, (record_id, path)
    assert path in tracked_files(), (record_id, path)
    item = next(
        item for item in INDEX_BY_ID[record_id]["evidence"] if item["path"] == path
    )
    assert content_sha256(REPO_ROOT / path) == item["sha256"], (record_id, path)


def test_the_hash_ignores_the_checkout_line_ending_and_nothing_else(
    tmp_path: Path,
) -> None:
    lf = tmp_path / "record.md"
    crlf = tmp_path / "other.md"
    lf.write_bytes(b"one\ntwo\n")
    crlf.write_bytes(b"one\r\ntwo\r\n")
    assert content_sha256(lf) == content_sha256(crlf)
    changed = tmp_path / "changed.md"
    changed.write_bytes(b"one\ntwo!\n")
    assert content_sha256(changed) != content_sha256(lf)
    binary = tmp_path / "image.png"
    binary.write_bytes(b"\x89PNG\r\n")
    assert content_sha256(binary) != content_sha256(tmp_path / "record.md")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("# R\n\nDate: 2026-09-04\n", {"label": "Date", "value": "2026-09-04"}),
        (
            "# R\n\nDate captured: 2026-09-12\n",
            {"label": "Date captured", "value": "2026-09-12"},
        ),
        ("# R\n\n| Date | 2026-09-14 |\n", {"label": "Date", "value": "2026-09-14"}),
        ("# R\n\nExecuted 2026-09-06.\n", None),
    ],
)
def test_a_date_is_read_only_from_a_line_the_record_writes(
    text: str, expected: dict[str, str] | None
) -> None:
    assert recorded_date(text) == expected


def test_an_authorisation_section_is_a_heading_not_a_mention() -> None:
    assert states_authorisation("## Authorisation\n\nNot required.\n")
    assert states_authorisation("### Authorization boundary\n")
    assert not states_authorisation("It was authorised by the maintainer.\n")


# ------------------------------------------------------- the certified claims


@pytest.mark.parametrize(
    "claim",
    [claim for claim in INDEX["claims"] if claim["status"] == "certified"],
    ids=lambda claim: claim["claimId"],
)
def test_every_certified_claim_resolves_to_records_with_explicit_boundaries(
    claim: dict[str, Any],
) -> None:
    """The release criterion, applied to every certified claim.

    The repository marks no claim with a priority, so the criterion the story states
    for its most important claims is applied to all of them.
    """
    assert claim["recordIds"], claim["claimId"]
    assert claim["limitation"].strip() and claim["doesNotEstablish"].strip()
    for record_id in claim["recordIds"]:
        entry = INDEX_BY_ID[record_id]
        assert entry["migrationState"] == "migrated", record_id
        assert entry["evidenceLevel"] in LEVEL_ORDER, record_id
        assert entry["limitations"] and entry["doesNotEstablish"], record_id
        assert entry["evidence"], record_id


def test_the_register_still_passes_every_evidence_level_rule() -> None:
    assert check_register(REGISTER, repo_root=REPO_ROOT) == []


# ------------------------------------------------------------------ the counts


def test_the_summary_is_recomputed_from_the_register() -> None:
    summary = INDEX["summary"]
    assert summary["claims"] == len(REGISTER["claims"])
    assert summary["claimsByStatus"] == dict(
        sorted(Counter(claim["status"] for claim in REGISTER["claims"]).items())
    )
    assert summary["records"] == len(RECORDS)
    assert summary["recordsByLevel"] == {
        level: sum(1 for _, record in RECORDS if record.get("evidenceLevel") == level)
        for level in LEVEL_ORDER
    }


def test_the_dashboard_and_the_index_count_the_same_register() -> None:
    """Two projections of one register may not disagree about it."""
    summary = INDEX["summary"]
    statuses = status_counts(REGISTER)
    assert {status: count for status, count in statuses.items() if count} == {
        status: count for status, count in summary["claimsByStatus"].items() if count
    }
    levels = level_counts(REGISTER)
    assert {level: pair[0] for level, pair in levels.items()} == summary[
        "recordsByLevel"
    ]


def test_the_index_page_states_the_counts_the_index_produces() -> None:
    page = normalised(INDEX_PAGE.read_text(encoding="utf-8"))
    summary = INDEX["summary"]
    levels = summary["recordsByLevel"]
    files = {item["path"] for entry in INDEX["records"] for item in entry["evidence"]}
    corrected = {
        item["path"]
        for entry in INDEX["records"]
        for item in entry["evidence"]
        if item["corrections"]
    }
    certified = summary["claimsByStatus"]["certified"]
    for phrase in (
        f"For each of the **{summary['records']} evidence records**",
        f"**{summary['records']} evidence records** under {summary['claims']} claims",
        f"{levels['C0']} at `C0`, {levels['C1']} at `C1`, {levels['C2']} at `C2`",
        f"Every one of the **{certified} certified claims**",
        f"**{len(files)} distinct committed files**",
        f"**{summary['executedRecords']} records executed their target behaviour, and "
        f"{summary['executedRecordsNamingTheRevisionThatRan']} of them name",
        f"The other {summary['executedRecords'] - summary['executedRecordsNamingTheRevisionThatRan']} name",
        f"{summary['recordsByWorkloadSource'].get('synthetic', 0)} records use a",
        f"{summary['recordsWithAClaimMaterialSubstitution']} have a claim-material "
        f"substitution, and "
        f"{summary['recordsWithASubstitution'] - summary['recordsWithAClaimMaterialSubstitution']}"
        f" more has a substitution recorded as immaterial",
    ):
        assert phrase in page, phrase
    words = {9: "Nine"}
    assert f"{words[len(corrected)]} of them carry a correction" in page


def test_the_readme_row_states_the_revision_count() -> None:
    summary = INDEX["summary"]
    row = next(
        line
        for line in README_PATH.read_text(encoding="utf-8").splitlines()
        if line.startswith("| V1 evidence index |")
    )
    assert (
        f"{summary['executedRecordsNamingTheRevisionThatRan']} of the "
        f"{summary['executedRecords']} records that executed" in row
    )


# ------------------------------------------------------------------ the ledger


def test_the_ledger_restores_the_migration_and_reapplies_to_the_register() -> None:
    """Every change is named: undoing them all and redoing them is the identity."""
    migrated = restore_migrated_register(REGISTER, LEDGERS)
    assert apply_register_changes(migrated, LEDGERS) == REGISTER
    added = [
        change
        for ledger in LEDGERS
        for change in ledger["registerChanges"]
        if change["operation"] == "add-record"
    ]
    restored_records = sum(
        len(claim["evidenceRecords"]) for claim in migrated["claims"]
    )
    assert restored_records == len(RECORDS) - len(added)


def test_a_misdescribed_change_is_refused_rather_than_restored() -> None:
    ledger = json.loads(json.dumps(LEDGER))
    change = next(
        change
        for change in ledger["registerChanges"]
        if change["operation"] == "set-claim-field"
    )
    change["after"] = change["after"] + " An extra sentence."
    with pytest.raises(ValueError, match=change["changeId"]):
        restore_migrated_register(REGISTER, [ledger, *LEDGERS[1:]])


def test_every_finding_has_exactly_one_known_disposition() -> None:
    names = {row["dispositionId"] for row in LEDGER["dispositions"]}
    assert names == set(DISPOSITIONS)
    identifiers = [finding["findingId"] for finding in LEDGER["findings"]]
    assert len(identifiers) == len(set(identifiers))
    for finding in LEDGER["findings"]:
        assert finding["disposition"] in names, finding["findingId"]
        assert len(finding["resolution"]) > 60, finding["findingId"]


def _audit_section() -> str:
    text = AUDIT_REPORT_PATH.read_text(encoding="utf-8")
    start = text.index("## What the audit found and did not fix")
    end = text.index("\n## ", start + 1)
    return text[start:end]


def test_every_open_item_of_the_migration_audit_is_answered() -> None:
    """Each bullet the audit left open holds at least one quoted finding."""
    quotes = [
        normalised(finding["auditQuote"])
        for finding in LEDGER["findings"]
        if finding["source"] == "v1-s5-012-pr2-audit"
    ]
    bullets = [normalised(bullet) for bullet in re.split(r"\n- ", _audit_section())[1:]]
    assert len(bullets) == 7
    for bullet in bullets:
        assert any(quote in bullet for quote in quotes), bullet[:80]


@pytest.mark.parametrize(
    "finding", LEDGER["findings"], ids=lambda finding: finding["findingId"]
)
def test_every_audit_quote_is_verbatim_and_every_finding_says_what_it_is(
    finding: dict[str, Any],
) -> None:
    if finding["source"] == "v1-s5-012-pr2-audit":
        report = normalised(AUDIT_REPORT_PATH.read_text(encoding="utf-8"))
        assert normalised(finding["auditQuote"]) in report
        assert finding["observation"] is None
    else:
        assert finding["source"] == "this-normalization"
        assert finding["auditQuote"] is None
        assert len(finding["observation"]) > 60
    for record_id in finding["recordIds"]:
        assert record_id in RECORD_BY_ID, record_id
    known = {claim["claimId"] for claim in REGISTER["claims"]}
    assert set(finding["claimIds"]) <= known


def test_only_the_release_blocker_is_carried_and_it_is_carried_to_pr2() -> None:
    carried = [finding for finding in LEDGER["findings"] if finding["carriedTo"]]
    assert [finding["disposition"] for finding in carried] == [
        "carried-as-release-blocker"
    ]
    assert carried[0]["carriedTo"] == "V1-S5-006-PR2"


@pytest.mark.parametrize(
    "change",
    [change for ledger in LEDGERS for change in ledger["registerChanges"]],
    ids=lambda change: change["changeId"],
)
def test_every_register_change_names_its_reason_and_its_finding(
    change: dict[str, Any],
) -> None:
    findings = {
        finding["findingId"] for ledger in LEDGERS for finding in ledger["findings"]
    }
    assert len(change["reason"]) > 40, change["changeId"]
    if change["findingId"] is None:
        assert change["operation"] == "set-register-field", change["changeId"]
    else:
        assert change["findingId"] in findings, change["changeId"]


#: The identifiers and instants a record's free text can quote. Each one has to be
#: something a cited file says, not something the author knew from elsewhere.
_GROUNDED_TOKENS = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)?"
    r"|\b\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"
    r"|sha256:[0-9a-f]{64}"
    r"|\b[0-9a-f]{40}\b"
)


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


@pytest.mark.parametrize(
    "change",
    [
        change
        for ledger in LEDGERS
        for change in ledger["registerChanges"]
        if change["operation"] == "add-record"
    ],
    ids=lambda change: change["changeId"],
)
def test_every_date_time_and_identifier_in_an_added_record_is_in_a_file_it_cites(
    change: dict[str, Any],
) -> None:
    """An added record's notes may not carry a fact from a file it does not cite.

    The first commit of this change added a record whose environment note quoted step
    times from a ledger the record did not cite; an independent review found it, and
    nothing here checked free text until then.
    """
    record = change["record"]
    cited = normalised("\n".join(read(path) for path in record["evidenceRefs"]))
    tokens = {
        token for text in _strings(record) for token in _GROUNDED_TOKENS.findall(text)
    }
    assert tokens, record["recordId"]
    missing = sorted(token for token in tokens if token not in cited)
    assert not missing, (record["recordId"], missing)


def test_no_change_moved_a_status_or_an_existing_records_level() -> None:
    """Normalization and verification may narrow, correct, and add; not promote.

    The closure ledger is the one exception, and only downwards: a blocker closed by a
    claim decision may move its claim's status, to exactly the status its disposition
    names, and to a status that ranks lower. No ledger moves any record's level.
    """
    migrated = restore_migrated_register(REGISTER, LEDGERS)
    before = {claim["claimId"]: claim for claim in migrated["claims"]}
    closure = LEDGERS[-1]
    decided = {
        row["claimId"]: row
        for row in closure["blockerDispositions"]
        if row["mechanism"] == "closed-by-claim-decision"
    }
    rank = {row["statusId"]: row["rank"] for row in REGISTER["claimStatuses"]}
    for claim in REGISTER["claims"]:
        was = before[claim["claimId"]]["status"]
        if claim["claimId"] in decided:
            row = decided[claim["claimId"]]
            assert (was, claim["status"]) == (row["statusBefore"], row["statusAfter"])
            assert rank[claim["status"]] < rank[was], claim["claimId"]
        else:
            assert claim["status"] == was, claim["claimId"]
        levels = {
            record["recordId"]: record.get("evidenceLevel")
            for record in before[claim["claimId"]]["evidenceRecords"]
        }
        for record in claim["evidenceRecords"]:
            if record["recordId"] in levels:
                assert record.get("evidenceLevel") == levels[record["recordId"]]
    touched = {
        change["field"]
        for ledger in LEDGERS
        for change in ledger["registerChanges"]
        if change["operation"] != "add-record"
    }
    assert not touched & {"evidenceLevel", "assertsRealBehaviour", "claimId"}
    moved = {
        change["claimId"]
        for ledger in LEDGERS
        for change in ledger["registerChanges"]
        if change["operation"] != "add-record" and change["field"] == "status"
    }
    assert moved == set(decided)
    for ledger in LEDGERS[:-1]:
        assert not [
            change
            for change in ledger["registerChanges"]
            if change["operation"] != "add-record" and change["field"] == "status"
        ]


# --------------------------------------------------------- historical records


@pytest.mark.parametrize(
    "correction",
    LEDGER["recordCorrections"],
    ids=lambda correction: correction["correctionId"],
)
def test_every_corrected_record_is_unchanged_and_quoted_verbatim(
    correction: dict[str, Any],
) -> None:
    """The correction is beside the record; the record is what it was.

    The ledger stores the content hash of the record it corrects. A record edited
    after its correction was written no longer matches, and a correction that
    quotes a record for something the record does not say fails here.
    """
    path = correction["path"]
    assert path.startswith("docs/proof/")
    assert content_sha256(REPO_ROOT / path) == correction["sha256"], path
    assert normalised(correction["says"]) in normalised(read(path)), path
    assert len(correction["correction"]) > 60
    for basis in correction["basis"]:
        if basis["kind"] == "file":
            assert normalised(basis["quote"]) in normalised(read(basis["path"])), basis
        else:
            assert basis["kind"] == "git-commit"
            try:
                committed = subprocess.run(
                    ["git", "show", "-s", "--format=%cI", basis["commit"]],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
            except (OSError, subprocess.CalledProcessError):
                pytest.skip("git history is not available")
            assert committed == basis["committedAt"], basis


def test_every_correction_is_indexed_against_the_file_it_concerns() -> None:
    indexed = {
        (item["path"], correction)
        for entry in INDEX["records"]
        for item in entry["evidence"]
        for correction in item["corrections"]
    }
    for correction in LEDGER["recordCorrections"]:
        assert (correction["path"], correction["correctionId"]) in indexed


# ------------------------------------------------------------- code revisions


#: Every revision reading, from both ledgers: `V1-S5-006-PR1` read the records that
#: existed, and `V1-S5-006-PR2` reads the ones it added.
READINGS = [reading for ledger in LEDGERS for reading in ledger["codeRevisions"]]


def test_every_executed_record_has_exactly_one_revision_reading() -> None:
    executed = [
        record["recordId"]
        for _, record in RECORDS
        if record["execution"]["targetBehaviourExecuted"]
    ]
    read_ = [reading["recordId"] for reading in READINGS]
    assert sorted(read_) == sorted(executed)
    assert len(read_) == len(set(read_))


@pytest.mark.parametrize("reading", READINGS, ids=lambda reading: reading["recordId"])
def test_every_revision_is_quoted_from_a_file_the_record_cites(
    reading: dict[str, Any],
) -> None:
    record = RECORD_BY_ID[reading["recordId"]]
    relations = {row["relation"] for row in LEDGER["codeRevisionRelations"]}
    assert relations == set(CODE_REVISION_RELATIONS)
    for entry in reading["entries"]:
        assert entry["relation"] in relations
        assert entry["path"] in record["evidenceRefs"], entry
        assert entry["value"] in entry["quote"], entry
        assert normalised(entry["quote"]) in normalised(read(entry["path"])), entry
    if not reading["entries"]:
        assert reading["note"], reading["recordId"]


def test_the_records_without_a_stated_revision_are_the_ones_carried_to_pr2() -> None:
    derived = {
        entry["recordId"]
        for entry in INDEX["records"]
        if entry["codeRevision"] is not None
        and not entry["codeRevision"]["statedRevision"]
    }
    assert derived == EXECUTED_WITHOUT_A_STATED_REVISION, {
        "no longer missing": sorted(EXECUTED_WITHOUT_A_STATED_REVISION - derived),
        "newly missing": sorted(derived - EXECUTED_WITHOUT_A_STATED_REVISION),
    }
    blocker = next(
        finding
        for finding in LEDGER["findings"]
        if finding["disposition"] == "carried-as-release-blocker"
    )
    assert (
        blocker["findingId"] == "n04-executed-records-do-not-name-the-revision-that-ran"
    )


# ------------------------------------------------------------ the report page


def test_the_normalization_report_states_the_counts_the_ledger_produces() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    changes = LEDGER["registerChanges"]
    findings = LEDGER["findings"]
    expected = {
        "Findings answered": len(findings),
        "Findings from the migration audit": sum(
            1 for finding in findings if finding["source"] == "v1-s5-012-pr2-audit"
        ),
        "Findings this normalization made": sum(
            1 for finding in findings if finding["source"] == "this-normalization"
        ),
        "Register changes named in the ledger": len(changes),
        "Claims whose register entry changed": len(
            {change["claimId"] for change in changes if change.get("claimId")}
        ),
        "Claim statements narrowed": sum(
            1 for change in changes if change.get("field") == "statement"
        ),
        "Evidence records added": sum(
            1 for change in changes if change["operation"] == "add-record"
        ),
        "Corrections recorded beside historical records": len(
            LEDGER["recordCorrections"]
        ),
        "Findings carried to `V1-S5-006-PR2` as a release blocker": sum(
            1 for finding in findings if finding["carriedTo"]
        ),
    }
    for label, count in expected.items():
        line = next(
            line for line in report.splitlines() if line.startswith(f"| {label} |")
        )
        assert line.split("|")[2].strip() == str(count), (label, count)
    for finding in findings:
        assert f"`{finding['findingId']}`" in report, finding["findingId"]
    for correction in LEDGER["recordCorrections"]:
        assert f"`{correction['correctionId']}`" in report, correction["correctionId"]
    for change in changes:
        if change.get("field") == "statement":
            assert normalised(change["before"]) in normalised(report)
            assert normalised(change["after"]) in normalised(report)


def test_the_ledger_and_the_index_name_no_private_path() -> None:
    for path in (LEDGER_PATH, COMPLETENESS_PATH, INDEX_PATH):
        text = path.read_text(encoding="utf-8")
        # A drive letter not preceded by another letter, so `https://` is not one.
        # `planning` alone is an ordinary word in the register's statements; a path
        # into a planning directory is what may not appear.
        assert not re.search(
            r"(?i)(?<![a-z])[a-z]:[\\/]|/users/|scratchpad|planning[\\/]", text
        )


# -------------------------------------------------------- current documents


def _current_documents() -> list[str]:
    return sorted(
        path
        for path in tracked_files() | {"docs/proof/v1-evidence-index.md"}
        if path.endswith(".md")
        and not path.startswith("docs/proof/")
        and not path.startswith("docs/architecture/decisions/")
        and path != "CHANGELOG.md"
    )


def test_no_current_document_describes_the_evidence_model_as_unmigrated() -> None:
    """The sentences the normalization corrected do not come back.

    `docs/proof/` is dated evidence, the changelog is history, and a decision record
    keeps its accepted text beside dated notes that say what changed since, so all
    three may still carry them.
    """
    found = []
    for relative in _current_documents():
        text = normalised(read(relative)).lower()
        for pattern in RETIRED_STATEMENTS:
            if re.search(pattern, text):
                found.append((relative, pattern))
    assert not found, found


def test_the_register_and_the_index_publish_the_same_evidence_model_version() -> None:
    assert REGISTER["contractVersion"] == CONTRACT_VERSION
    model = normalised(read("docs/testing/evidence-record-model.md"))
    assert "the [proof dashboard](../proof/dashboard.md) reads `v1alpha2`" in model
