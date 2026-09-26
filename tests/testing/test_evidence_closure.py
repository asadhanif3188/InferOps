"""The closure of the V1 evidence blockers, held to what it rests on.

`V1-S5-006-PR2` left the V1 evidence pack unfrozen on five release blockers, and
`V1-S5-013-PR1` closed them in a third ledger, by reruns at a named revision and by
one claim decision. The failures this module exists to prevent are the ones that make
a closure look finished when it is not: a blocker that disappears instead of being
closed, a rerun that names no revision or ran on a dirty tree, a new record that
cannot be tied to the files it cites, an older record quietly edited, dropped, or
promoted, a status moved without the disposition that moved it, a gate that passes
while a blocker stands, and a report whose counts or digest have drifted from what the
ledger and the index produce.

What it does not establish is that a rerun behaved as its record says, or that a claim
decision was the right one. Those are recorded in the ledger and the report with their
reasons; this module checks that they are recorded, consistent, and carried to every
surface that publishes the claims.
"""

from __future__ import annotations

import copy
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tools.evidence_index import (
    BLOCKER_CLOSURES,
    CLOSURE_PATH,
    COMPLETENESS_PATH,
    INDEX_PATH,
    load_index,
    load_ledger,
    open_blockers,
    release_gate,
    restore_migrated_register,
)
from tools.evidence_index.__main__ import main as index_main
from tools.evidence_model import load_register

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER = load_register()
COMPLETENESS = load_ledger(COMPLETENESS_PATH)
CLOSURE = load_ledger(CLOSURE_PATH)
INDEX = load_index()
REPORT_PATH = REPO_ROOT / CLOSURE["reportRef"]
REVISION = CLOSURE["runRevision"]["revision"]

#: The register as `V1-S5-006-PR2` left it: the current one with the closure undone.
AT_PR2 = restore_migrated_register(REGISTER, CLOSURE)
CLAIMS = {claim["claimId"]: claim for claim in REGISTER["claims"]}
CLAIMS_AT_PR2 = {claim["claimId"]: claim for claim in AT_PR2["claims"]}
RECORDS = {
    record["recordId"]: record
    for claim in REGISTER["claims"]
    for record in claim["evidenceRecords"]
}
ADDED = [
    change["record"]
    for change in CLOSURE["registerChanges"]
    if change["operation"] == "add-record"
]
DISPOSITIONS = {row["blockerId"]: row for row in CLOSURE["blockerDispositions"]}
RAISED = {blocker["blockerId"]: blocker for blocker in COMPLETENESS["blockers"]}
CLOSED_SENTENCE = "closed by V1-S5-013-PR1"


def normalised(text: str) -> str:
    return " ".join(text.split())


def read(path: str | Path) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _git(*arguments: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *arguments], cwd=REPO_ROOT, capture_output=True, check=True
        ).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        return None


# ------------------------------------------------------------- every blocker


def test_the_ledger_publishes_the_three_closure_mechanisms_and_no_fourth() -> None:
    assert [row["mechanism"] for row in CLOSURE["closureMechanisms"]] == list(
        BLOCKER_CLOSURES
    )
    for row in CLOSURE["closureMechanisms"]:
        assert len(row["meaning"]) > 60, row["mechanism"]


def test_every_blocker_raised_has_exactly_one_disposition_in_order() -> None:
    """No blocker may disappear: each is closed once, in the order it was raised."""
    assert [row["blockerId"] for row in CLOSURE["blockerDispositions"]] == list(RAISED)
    for blocker_id, row in DISPOSITIONS.items():
        assert row["claimId"] == RAISED[blocker_id]["claimId"], blocker_id
        assert row["mechanism"] in BLOCKER_CLOSURES, blocker_id
        assert row["statusBefore"] == "certified", blocker_id
        assert row["statusAfter"] == CLAIMS[row["claimId"]]["status"], blocker_id
        assert len(row["notRerun"]) > 40, blocker_id
    assert open_blockers(COMPLETENESS, CLOSURE) == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda ledger: ledger["blockerDispositions"].pop(),
        lambda ledger: ledger["blockerDispositions"].append(
            copy.deepcopy(ledger["blockerDispositions"][0])
        ),
        lambda ledger: ledger["blockerDispositions"][0].update(
            {"mechanism": "closed-by-assertion"}
        ),
        lambda ledger: ledger["blockers"].append(
            {"blockerId": ledger["blockerDispositions"][0]["blockerId"]}
        ),
    ],
    ids=["dropped", "twice", "unknown-mechanism", "both-open-and-closed"],
)
def test_a_closure_that_loses_or_doubles_a_blocker_is_refused(mutate: Any) -> None:
    ledger = copy.deepcopy(CLOSURE)
    mutate(ledger)
    with pytest.raises(ValueError):
        open_blockers(COMPLETENESS, ledger)


def test_the_stated_gate_is_the_one_the_closure_decides() -> None:
    assert CLOSURE["releaseGate"]["decision"] == release_gate(CLOSURE)
    assert CLOSURE["releaseGate"]["storyId"] == "V1-S5-013"
    summary = INDEX["summary"]
    assert summary["releaseGate"] == release_gate(CLOSURE)
    assert summary["releaseBlockers"] == len(open_blockers(COMPLETENESS, CLOSURE))
    assert summary["blockersRaised"] == len(RAISED)
    assert summary["blockersClosedBy"] == {
        name: sum(1 for row in DISPOSITIONS.values() if row["mechanism"] == name)
        for name in BLOCKER_CLOSURES
    }
    assert summary["closureRegisterChanges"] == len(CLOSURE["registerChanges"])


def test_an_open_blocker_fails_the_gate() -> None:
    """The rule, independent of today's closure."""
    reopened = copy.deepcopy(CLOSURE)
    blocker = reopened["blockerDispositions"].pop(0)
    reopened["blockers"].append(RAISED[blocker["blockerId"]])
    assert release_gate(reopened) == "incomplete"
    assert open_blockers(COMPLETENESS, reopened)


def test_the_gate_command_prints_every_closure_and_exits_on_the_decision(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = index_main(["--gate"])
    printed = capsys.readouterr().out
    if release_gate(CLOSURE) == "complete":
        assert code == 0
        assert printed.startswith("COMPLETE V1-S5-013")
        for row in CLOSURE["blockerDispositions"]:
            assert f"{row['blockerId']}  {row['mechanism']}" in printed
    else:
        assert code == 1


def test_the_freeze_is_labelled_a_candidate_and_names_who_freezes_next() -> None:
    gate = CLOSURE["releaseGate"]
    assert "V1-S5-013-PR2" in gate["freezeCandidate"]
    assert "V1-S5-008" in gate["freezeCandidate"]
    assert gate["consumersUnblocked"] == ["V1-S5-013-PR2"]


# ------------------------------------------------------------------ the reruns


def test_the_run_revision_is_a_commit_this_history_holds() -> None:
    assert re.fullmatch(r"[0-9a-f]{40}", REVISION)
    assert CLOSURE["runRevision"]["statusBefore"] == ""
    assert CLOSURE["runRevision"]["statusAfter"] == ""
    if _git("cat-file", "-e", f"{REVISION}^{{commit}}") is None:
        pytest.skip("the run's revision is not in this clone")
    assert _git("merge-base", "--is-ancestor", REVISION, "HEAD") is not None


def _identity_blocks(transcript: str) -> list[tuple[str, list[str]]]:
    """Each `=== identity` block: the revision printed and the status lines."""
    blocks = []
    lines = transcript.splitlines()
    for number, line in enumerate(lines):
        if not line.startswith("=== identity"):
            continue
        revision = lines[number + 1].strip()
        assert lines[number + 2].startswith("--- status"), line
        status = []
        for following in lines[number + 3 :]:
            if following.startswith("--- status end"):
                break
            status.append(following)
        blocks.append((revision, status))
    return blocks


@pytest.mark.parametrize("path", CLOSURE["runRevision"]["transcripts"])
def test_every_transcript_shows_the_revision_and_an_empty_status_both_sides(
    path: str,
) -> None:
    """What `V1-S5-006-PR2` said every rerun must record, read from the transcript."""
    blocks = _identity_blocks(read(path))
    assert len(blocks) >= 2, path
    for revision, status in blocks:
        assert revision == REVISION, path
        assert status == [], (path, status)


def test_every_rerun_disposition_names_the_records_it_added() -> None:
    added = {record["recordId"]: record for record in ADDED}
    closing = set()
    for row in DISPOSITIONS.values():
        if row["mechanism"] != "closed-by-rerun":
            assert row["closingRecordIds"] == [] and row["rerunRevision"] is None
            continue
        assert row["rerunRevision"] == REVISION, row["blockerId"]
        assert row["closingRecordIds"], row["blockerId"]
        for record_id in row["closingRecordIds"]:
            assert added[record_id]["claimId"] == row["claimId"], record_id
            closing.add(record_id)
    assert closing == set(added)


@pytest.mark.parametrize("record", ADDED, ids=lambda record: record["recordId"])
def test_every_added_record_names_the_run_revision_and_cites_its_transcript(
    record: dict[str, Any],
) -> None:
    assert record == RECORDS[record["recordId"]]
    assert {
        "component": "inferops repository",
        "kind": "commit",
        "value": REVISION,
    } in (record["versions"])
    assert record["execution"]["targetBehaviourExecuted"] is True
    assert record["execution"]["substitutions"] == []
    assert record["evidenceLevel"] == "C2"
    transcripts = set(CLOSURE["runRevision"]["transcripts"])
    assert transcripts & set(record["evidenceRefs"]), record["recordId"]
    cited = normalised("\n".join(read(path) for path in record["evidenceRefs"]))
    assert REVISION in cited
    reading = next(
        row for row in CLOSURE["codeRevisions"] if row["recordId"] == record["recordId"]
    )
    for entry in reading["entries"]:
        assert entry["relation"] == "stated-revision"
        assert entry["value"] == REVISION
        assert entry["path"] in record["evidenceRefs"]
        assert normalised(entry["quote"]) in normalised(read(entry["path"]))


# --------------------------------------------------------------- the history


def test_no_record_that_existed_was_edited_removed_or_given_another_level() -> None:
    for claim in AT_PR2["claims"]:
        for record in claim["evidenceRecords"]:
            assert RECORDS.get(record["recordId"]) == record, record["recordId"]


def test_no_record_reaches_c3_or_c4() -> None:
    assert {record["evidenceLevel"] for record in RECORDS.values()} <= {
        "C0",
        "C1",
        "C2",
    }


def test_only_a_claim_decision_moved_a_status_and_only_downwards() -> None:
    rank = {row["statusId"]: row["rank"] for row in REGISTER["claimStatuses"]}
    for claim_id, claim in CLAIMS.items():
        before = CLAIMS_AT_PR2[claim_id]["status"]
        decided = [
            row
            for row in DISPOSITIONS.values()
            if row["claimId"] == claim_id
            and row["mechanism"] == "closed-by-claim-decision"
        ]
        if claim["status"] != before:
            assert decided, claim_id
            assert rank[claim["status"]] < rank[before], claim_id


# ----------------------------------------------------- where the claims live


def test_every_closed_claim_says_how_where_it_is_published() -> None:
    """A closure the dashboard cannot show is a closure a reader never meets."""
    dashboard = normalised(read("docs/proof/dashboard.md"))
    for blocker_id, row in DISPOSITIONS.items():
        limitation = CLAIMS[row["claimId"]]["limitation"]
        sentence = f"Release blocker {blocker_id} {CLOSED_SENTENCE}"
        assert sentence in limitation, blocker_id
        tail = limitation[limitation.index(sentence) :]
        assert normalised(tail) in dashboard, blocker_id
    closed = {claim["claimId"]: claim["closedBlockers"] for claim in INDEX["claims"]}
    for blocker_id, row in DISPOSITIONS.items():
        assert closed[row["claimId"]] == [blocker_id]


def test_the_claim_decision_reached_the_test_strategy_too() -> None:
    """No current surface may still count a not-claimed row as certified."""
    strategy = {
        claim["claimId"]: claim
        for claim in load_ledger(
            REPO_ROOT / "docs/testing/test-strategy.v1alpha1.json"
        )["claims"]
    }
    for row in DISPOSITIONS.values():
        if row["mechanism"] != "closed-by-claim-decision":
            continue
        claim = CLAIMS[row["claimId"]]
        assert claim["status"] == "not-claimed"
        assert "V1-S5-013-PR1" in claim["notClaimedReason"]
        mapped = strategy[row["claimId"]]
        assert mapped["v1Status"] == "deferred"
        assert mapped["evidenceRef"] is None
        assert "V1-S5-013-PR1" in mapped["deferralReason"]


# ------------------------------------------------------------------ the report


def _table(report: str, label: str) -> str:
    line = next(line for line in report.splitlines() if line.startswith(f"| {label} |"))
    return line.split("|")[2].strip()


def test_the_report_states_what_the_ledger_and_the_index_produce() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    flat = normalised(report)
    changes = CLOSURE["registerChanges"]
    summary = INDEX["summary"]
    by = summary["blockersClosedBy"]
    expected = {
        "Blockers raised by `V1-S5-006-PR2`": len(RAISED),
        "Closed by a rerun": by["closed-by-rerun"],
        "Closed by re-anchoring to evidence that already existed": by[
            "closed-by-re-anchoring"
        ],
        "Closed by a claim decision": by["closed-by-claim-decision"],
        "Blockers still open": summary["releaseBlockers"],
        "Register changes named in the ledger": len(changes),
        "Evidence records added": len(ADDED),
        "Claim statuses changed": sum(
            1 for change in changes if change.get("field") == "status"
        ),
        "Claim statements changed": sum(
            1 for change in changes if change.get("field") == "statement"
        ),
        "Record levels changed": 0,
        "Records edited or removed": 0,
    }
    for label, count in expected.items():
        assert _table(report, label) == str(count), (label, count)
    statuses = summary["claimsByStatus"]
    levels = summary["recordsByLevel"]
    identities = summary["executedRecordsByCodeIdentity"]
    for phrase in (
        f"**{summary['claims']} claims** — {statuses['certified']} certified, "
        f"{statuses['planned']} planned, {statuses['deferred']} deferred, "
        f"{statuses['not-claimed']} not claimed",
        f"**{summary['records']} evidence records** — {levels['C0']} at `C0`, "
        f"{levels['C1']} at `C1`, {levels['C2']} at `C2`",
        f"Of the **{summary['executedRecords']} executed records**, "
        f"**{identities['stated-revision']}** name the revision that ran, "
        f"{identities['content-pinned']} are content-pinned, "
        f"{identities['no-repository-code']} run no repository code, and "
        f"{identities['unidentified']} leave their code unidentified",
        f"for each of the **{summary['evidenceFiles']} cited files**",
        f"`{summary['evidenceSetSha256']}`",
        f"The decision is **{summary['releaseGate'].upper()}**",
    ):
        assert phrase in flat, phrase
    for blocker_id, row in DISPOSITIONS.items():
        assert f"`{blocker_id}`" in report
        assert f"**`{row['mechanism']}`**" in report, blocker_id


def test_the_report_quotes_the_gate_it_ran(capsys: pytest.CaptureFixture[str]) -> None:
    index_main(["--gate"])
    printed = capsys.readouterr().out.strip()
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert printed in report


def test_the_closure_files_name_no_private_path() -> None:
    paths = [
        CLOSURE_PATH,
        INDEX_PATH,
        REPORT_PATH,
        *(REPO_ROOT / path for record in ADDED for path in record["evidenceRefs"]),
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert not re.search(
            r"(?i)(?<![a-z])[a-z]:[\\/]|/users/|scratchpad|planning[\\/]|/tmp/", text
        ), path
