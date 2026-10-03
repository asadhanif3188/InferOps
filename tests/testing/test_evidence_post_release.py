"""The change after `v1.0.0`, held to the release it records and the pack it left alone.

`V1-S5-009-PR1` certified `a-v1-release-has-been-published`, at `C0`, on a record read
after the release, through a fifth ledger of register changes. The failures this module
exists to prevent are the ones that would let a change after a release rewrite what the
release was: a post-release ledger that changes more than the one claim and the two
surface reasons it names; a released pack identified by a digest a ledger copied rather
than one recomputed from `main`; a register, a cited file, or an earlier ledger edited
after the release, so that undoing the post-release ledger no longer gives the pack the
tag quotes; and a record that reads more into the release than it read.

`V2-S2-001-PR2` then wrote a second post-release ledger, correcting one planned
claim's limitation once Helm values were generated, and the evidence index undoes both.
This module holds that one too: it changes that limitation and one surface reason and
nothing else, states no release, leaves the claim planned with no record, and cannot be
skipped when the released register is rebuilt.

`V2-S2-003-PR2` and `V2-S2-004-PR2` wrote a third and a fourth, one for each run of the
static parts of V2-E01. Each adds one claim, certified at `C0` on the one record it
brings, and replaces one surface reason. The fourth also appends a dated audit
limitation to the first run's claim and writes one correction beside the first run's
result page; it moves no status and edits no dated record.

What it does not establish is that the release is still published as the record read
it, or that the private reporting setting still reads enabled: those are state on the
hosting service, and this module reads only files and, where the clone has it, the tag.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tools.evidence_index import (
    CLAIM_RECONCILIATION_PATH,
    E01_CORRECTED_PROOF_PATH,
    E01_STATIC_PROOF_PATH,
    INDEX_PATH,
    LEDGER_PATHS,
    POST_RELEASE_LEDGER_PATHS,
    POST_RELEASE_PATH,
    PUBLICATION_PATH,
    RELEASED_DIGESTS,
    RELEASED_LEDGER_PATHS,
    apply_register_changes,
    build_index,
    load_index,
    load_ledger,
    load_ledgers,
    released_pack,
    released_register,
    render_register,
    restore_migrated_register,
)
from tools.evidence_model import REGISTER_PATH, load_register

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER = load_ledger(POST_RELEASE_PATH)
RELEASE = LEDGER["release"]
REGISTER = load_register()
#: The second post-release ledger, written after this one.
LATER = load_ledger(CLAIM_RECONCILIATION_PATH)
#: The third post-release ledger, written after the second.
E01 = load_ledger(E01_STATIC_PROOF_PATH)
#: The fourth post-release ledger, written after the third.
CORRECTED = load_ledger(E01_CORRECTED_PROOF_PATH)
#: Every post-release ledger written after this one, in the order applied.
LATER_LEDGERS = [LATER, E01, CORRECTED]
AS_RELEASED = released_register(REGISTER, load_ledgers(POST_RELEASE_LEDGER_PATHS))
#: The register as this ledger left it, before the later ones.
AFTER_THIS_LEDGER = restore_migrated_register(REGISTER, LATER_LEDGERS)
INDEX = load_index()
SUMMARY = INDEX["summary"]
RELEASE_DATA: dict[str, Any] = json.loads(
    (REPO_ROOT / "docs" / "releases" / "v1.0.0.v1alpha1.json").read_text(
        encoding="utf-8"
    )
)
CLAIM_ID = "a-v1-release-has-been-published"
CHANGES = LEDGER["registerChanges"]
FINDINGS = {row["findingId"]: row for row in LEDGER["findings"]}
(ADDED,) = [
    change["record"] for change in CHANGES if change["operation"] == "add-record"
]
RECORD_PAGE = LEDGER["reportRef"]

#: The only fields a post-release change may touch. Recording that a release exists
#: needs the release claim's status and boundary, a record, and the two surface reasons
#: that described the repository before it; anything else fails here until argued for.
ALLOWED = {
    "set-claim-field": {
        "status",
        "notClaimedReason",
        "limitation",
        "doesNotEstablish",
        "automatedTestRefs",
    },
    "set-register-field": {"nonClaimSurfaces"},
}


def read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def normalised(text: str) -> str:
    return " ".join(text.split())


def _git(*arguments: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *arguments], cwd=REPO_ROOT, capture_output=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.decode("utf-8")


# ----------------------------------------------------------------- the ledger


def test_the_ledger_is_the_first_after_the_release_and_follows_the_publication() -> (
    None
):
    assert LEDGER["contractVersion"] == "inferops.io/v1alpha1"
    assert POST_RELEASE_LEDGER_PATHS[0] == POST_RELEASE_PATH
    assert (*RELEASED_LEDGER_PATHS, *POST_RELEASE_LEDGER_PATHS) == LEDGER_PATHS
    assert (
        LEDGER["priorLedgerRef"] == PUBLICATION_PATH.relative_to(REPO_ROOT).as_posix()
    )
    for key in ("registerRef", "priorLedgerRef", "reportRef", "indexRef"):
        assert (REPO_ROOT / LEDGER[key]).is_file(), key


def test_it_raises_no_blocker_declares_no_freeze_and_corrects_no_record() -> None:
    assert "blockers" not in LEDGER
    assert "blockerDispositions" not in LEDGER
    assert "freeze" not in LEDGER
    assert LEDGER["recordCorrections"] == []
    assert LEDGER["codeRevisions"] == []


@pytest.mark.parametrize("change", CHANGES, ids=lambda change: change["changeId"])
def test_every_change_is_to_the_release_claim_or_a_surface_reason(
    change: dict[str, Any],
) -> None:
    assert change["findingId"] in FINDINGS
    assert change["reason"]
    if change["operation"] == "add-record":
        assert change["claimId"] == CLAIM_ID
        return
    assert change["field"] in ALLOWED[change["operation"]], change["changeId"]
    if change["operation"] == "set-claim-field":
        assert change["claimId"] == CLAIM_ID


def test_every_finding_is_answered_by_changes_that_exist() -> None:
    change_ids = {change["changeId"] for change in CHANGES}
    answered = set()
    for finding in FINDINGS.values():
        assert set(finding["resolvedBy"]) <= change_ids, finding["findingId"]
        answered |= set(finding["resolvedBy"])
    assert answered == change_ids


def test_the_nonclaim_surface_change_moves_only_the_two_reasons_it_names() -> None:
    (change,) = [c for c in CHANGES if c.get("field") == "nonClaimSurfaces"]
    before = {row["path"]: row for row in change["before"]}
    after = {row["path"]: row for row in change["after"]}
    assert before.keys() == after.keys()
    moved = sorted(path for path in before if before[path] != after[path])
    assert moved == ["SECURITY.md", "docs/proof/v1-evidence-index.md"]
    assert "no private channel is published" in before["SECURITY.md"]["reason"]
    assert "no private channel is published" not in after["SECURITY.md"]["reason"]


def test_undoing_and_redoing_the_ledger_gives_the_register_back() -> None:
    assert apply_register_changes(AS_RELEASED, LEDGER) == AFTER_THIS_LEDGER
    assert restore_migrated_register(AFTER_THIS_LEDGER, LEDGER) == AS_RELEASED
    assert apply_register_changes(AFTER_THIS_LEDGER, LATER_LEDGERS) == REGISTER


# ----------------------------------------------------------- the released pack


def test_the_ledger_states_the_pair_written_once_for_the_tag() -> None:
    """The fixed reference a clone without tags still has.

    Every other copy of the released pair is a committed file that a find-and-replace
    would carry along; this one is in the tool, and the tool refuses a ledger that
    differs from it.
    """
    quoted = RELEASED_DIGESTS[RELEASE["tag"]]
    assert quoted == {
        "evidenceSetSha256": RELEASE["evidenceSetSha256"],
        "evidencePackSha256": RELEASE["evidencePackSha256"],
    }


def test_the_committed_register_is_its_own_rendering() -> None:
    """What lets the undone register be bound to the bytes it had."""
    committed = REGISTER_PATH.read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert render_register(REGISTER) == committed


def test_the_released_pack_is_recomputed_and_is_the_one_the_release_quotes() -> None:
    released = SUMMARY["releasedPack"]
    recomputed = released_pack(REGISTER, load_ledgers())
    assert recomputed == released
    evidence = RELEASE_DATA["evidence"]
    for name in ("evidenceSetSha256", "evidencePackSha256"):
        assert released[name] == RELEASE[name] == evidence[name], name
    assert released["freezeDecidedIn"] == evidence["freezeDecidedIn"]
    assert (released["tag"], released["commit"], released["tagObject"]) == (
        RELEASE["tag"],
        RELEASE["commit"],
        RELEASE["tagObject"],
    )


def test_main_holds_another_pack_and_says_so() -> None:
    released = SUMMARY["releasedPack"]
    assert SUMMARY["evidencePackSha256"] != released["evidencePackSha256"]
    assert SUMMARY["evidenceSetSha256"] != released["evidenceSetSha256"]
    assert SUMMARY["postReleaseRegisterChanges"] == len(CHANGES) + sum(
        len(ledger["registerChanges"]) for ledger in LATER_LEDGERS
    )
    rows = {
        line.split(" | ", 1)[0]: line
        for line in read("docs/proof/v1-evidence-index.md").splitlines()
        if line.startswith(("| **Released:**", "| **Current:**"))
    }
    (released_row,) = [row for label, row in rows.items() if "Released" in label]
    (current_row,) = [row for label, row in rows.items() if "Current" in label]
    assert released_row.endswith(
        f"| `{released['evidenceSetSha256']}` | `{released['evidencePackSha256']}` |"
    )
    assert current_row.endswith(
        f"| `{SUMMARY['evidenceSetSha256']}` | `{SUMMARY['evidencePackSha256']}` |"
    )


def test_the_released_counts_differ_from_main_by_the_three_records_added_since() -> (
    None
):
    """The release's own record, which moved one claim from not claimed, and the two
    E01 static runs', each of which came with a claim of its own. All three are C0,
    and nothing else moved a count."""
    released = SUMMARY["releasedPack"]
    assert released["records"] == SUMMARY["records"] - 3
    assert released["recordsByLevel"]["C0"] == SUMMARY["recordsByLevel"]["C0"] - 3
    assert released["claims"] == SUMMARY["claims"] - 2
    certified = SUMMARY["claimsByStatus"]["certified"]
    assert released["claimsByStatus"]["certified"] == certified - 3
    not_claimed = SUMMARY["claimsByStatus"]["not-claimed"]
    assert released["claimsByStatus"]["not-claimed"] == not_claimed + 1
    added_files = (
        set(ADDED["evidenceRefs"])
        | set(E01_RECORD["evidenceRefs"])
        | set(CORRECTED_RECORD["evidenceRefs"])
    )
    assert released["evidenceFiles"] == SUMMARY["evidenceFiles"] - len(added_files)


def test_the_undone_register_is_the_tagged_one_byte_for_byte() -> None:
    """Reads the tag; a clone without it, as in continuous integration, skips."""
    relative = REGISTER_PATH.relative_to(REPO_ROOT).as_posix()
    tagged = _git("show", f"{RELEASE['tag']}:{relative}")
    if tagged is None:
        pytest.skip("the release tag is not in this clone")
    assert render_register(AS_RELEASED) == tagged.replace("\r\n", "\n")


def test_the_tag_is_the_object_the_ledger_names_on_the_commit_it_names() -> None:
    """Reads the tag; a clone without it, as in continuous integration, skips."""
    tag_object = _git("rev-parse", "--verify", "--quiet", RELEASE["tag"])
    if tag_object is None:
        pytest.skip("the release tag is not in this clone")
    assert tag_object.strip() == RELEASE["tagObject"]
    assert _git("cat-file", "-t", RELEASE["tag"]) == "tag\n"
    commit = _git("rev-parse", f"{RELEASE['tag']}^{{commit}}")
    assert commit is not None and commit.strip() == RELEASE["commit"]
    annotation = _git("cat-file", "-p", RELEASE["tag"])
    assert annotation is not None
    assert f"Evidence pack sha256:{RELEASE['evidencePackSha256']}" in annotation
    quoted = RELEASED_DIGESTS[RELEASE["tag"]]["evidencePackSha256"]
    assert f"Evidence pack sha256:{quoted}" in annotation


def _mutated(mutate: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    register = copy.deepcopy(REGISTER)
    ledgers = copy.deepcopy(load_ledgers())
    mutate(register, ledgers)
    return register, ledgers


def _edit_another_claim(register: dict, ledgers: list) -> None:
    register["claims"][0]["limitation"] += " Edited after the release."


def _state_another_digest(register: dict, ledgers: list) -> None:
    ledgers[len(RELEASED_LEDGER_PATHS)]["release"]["evidencePackSha256"] = "0" * 64


def _edit_an_earlier_ledger(register: dict, ledgers: list) -> None:
    """Undoing still works; the earlier ledger is read from disk, so edit its text."""
    ledgers[-2]["title"] += " Edited after the release."


def _declare_a_freeze(register: dict, ledgers: list) -> None:
    ledgers[-1]["freeze"] = {"decision": "frozen"}


def _raise_a_blocker(register: dict, ledgers: list) -> None:
    ledgers[-1]["blockers"] = [{"blockerId": "b-x", "claimId": CLAIM_ID}]


def _state_a_release_later(register: dict, ledgers: list) -> None:
    ledgers[-1]["release"] = copy.deepcopy(RELEASE)


def _edit_the_reconciled_limitation(register: dict, ledgers: list) -> None:
    (claim,) = [c for c in register["claims"] if c["claimId"] == RENDERING_CLAIM_ID]
    claim["limitation"] += " Edited after the change."


def _edit_the_added_claim(register: dict, ledgers: list) -> None:
    (claim,) = [c for c in register["claims"] if c["claimId"] == E01_CLAIM_ID]
    claim["evidenceRecords"][0]["summary"] += " Edited after the change."


def _edit_the_corrected_claim(register: dict, ledgers: list) -> None:
    (claim,) = [c for c in register["claims"] if c["claimId"] == CORRECTED_CLAIM_ID]
    claim["evidenceRecords"][0]["summary"] += " Edited after the change."


def _edit_the_audit_limitation(register: dict, ledgers: list) -> None:
    (claim,) = [c for c in register["claims"] if c["claimId"] == E01_CLAIM_ID]
    claim["limitation"] += " Edited after the change."


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (_edit_another_claim, "and undoing it gives"),
        (_state_another_digest, "and v1.0.0 quoted"),
        (_declare_a_freeze, "declares a freeze"),
        (_raise_a_blocker, "raises or closes a blocker"),
        (_state_a_release_later, "only the first post-release ledger"),
        (_edit_the_reconciled_limitation, "c01-rendering-limitation"),
        (_edit_the_added_claim, "e01-static-claim"),
        (_edit_the_corrected_claim, "k01-corrected-run-claim"),
        (_edit_the_audit_limitation, "k02-first-run-audit-limitation"),
    ],
    ids=lambda value: value.__name__.strip("_") if callable(value) else "",
)
def test_a_released_pack_that_does_not_recompute_is_refused(
    mutate: Any, message: str
) -> None:
    register, ledgers = _mutated(mutate)
    with pytest.raises(ValueError, match=message):
        build_index(register, ledgers)


def test_an_earlier_ledger_edited_after_the_release_is_refused(tmp_path: Path) -> None:
    """The pack sources are read from disk, so the edit is made to a copy of the tree."""
    for path in (REGISTER_PATH, *LEDGER_PATHS):
        copied = tmp_path / path.relative_to(REPO_ROOT)
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes(path.read_bytes())
    for record in INDEX["records"]:
        for item in record["evidence"]:
            copied = tmp_path / item["path"]
            copied.parent.mkdir(parents=True, exist_ok=True)
            copied.write_bytes((REPO_ROOT / item["path"]).read_bytes())
    publication = tmp_path / PUBLICATION_PATH.relative_to(REPO_ROOT)
    publication.write_text(
        publication.read_text(encoding="utf-8") + " ", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="and undoing it gives"):
        build_index(repo_root=tmp_path)


def test_an_unchanged_register_and_ledgers_build_the_committed_index() -> None:
    produced = build_index()
    assert produced == json.loads(INDEX_PATH.read_text(encoding="utf-8"))


# -------------------------------------------------- the claim reconciliation ledger

RENDERING_CLAIM_ID = "deployment-values-derive-only-from-a-validated-document"
LATER_CHANGES = LATER["registerChanges"]
LATER_FINDINGS = {row["findingId"]: row for row in LATER["findings"]}


def _rendering_claim(register: dict[str, Any]) -> dict[str, Any]:
    (claim,) = [c for c in register["claims"] if c["claimId"] == RENDERING_CLAIM_ID]
    return claim


def test_the_reconciliation_ledger_follows_this_one_and_states_no_release() -> None:
    assert LATER["contractVersion"] == "inferops.io/v1alpha1"
    assert LATER["priorLedgerRef"] == (
        POST_RELEASE_PATH.relative_to(REPO_ROOT).as_posix()
    )
    for key in ("registerRef", "priorLedgerRef", "reportRef", "indexRef"):
        assert (REPO_ROOT / LATER[key]).is_file(), key
    for absent in ("release", "freeze", "blockers", "blockerDispositions"):
        assert absent not in LATER, absent
    assert LATER["recordCorrections"] == []
    assert LATER["codeRevisions"] == []


def test_it_changes_one_limitation_and_one_surface_reason_and_nothing_else() -> None:
    assert [
        (change["operation"], change.get("claimId"), change["field"])
        for change in LATER_CHANGES
    ] == [
        ("set-claim-field", RENDERING_CLAIM_ID, "limitation"),
        ("set-register-field", None, "nonClaimSurfaces"),
    ]
    (surfaces,) = [c for c in LATER_CHANGES if c["field"] == "nonClaimSurfaces"]
    before = {row["path"]: row for row in surfaces["before"]}
    after = {row["path"]: row for row in surfaces["after"]}
    assert before.keys() == after.keys()
    assert [path for path in before if before[path] != after[path]] == [
        "docs/proof/v1-evidence-index.md"
    ]
    assert "six ledgers" in after["docs/proof/v1-evidence-index.md"]["reason"]


def test_every_reconciliation_finding_is_answered_by_changes_that_exist() -> None:
    change_ids = {change["changeId"] for change in LATER_CHANGES}
    answered: set[str] = set()
    for change in LATER_CHANGES:
        assert change["findingId"] in LATER_FINDINGS
        assert change["reason"]
    for finding in LATER_FINDINGS.values():
        assert set(finding["resolvedBy"]) <= change_ids, finding["findingId"]
        answered |= set(finding["resolvedBy"])
    assert answered == change_ids


def test_the_rendering_claim_stays_planned_with_no_record_and_no_promotion() -> None:
    for register in (REGISTER, AS_RELEASED):
        claim = _rendering_claim(register)
        assert claim["status"] == "planned"
        assert claim["assertsRealBehaviour"] is False
        assert claim["evidenceRecords"] == []
        assert claim["notClaimedReason"] is None


def test_the_limitation_says_what_exists_and_what_still_does_not() -> None:
    """The current limitation: rendering exists at C0, deployment does not consume it,
    the defaults revision is asserted, and only supported hand-written files are checked."""
    current = normalised(_rendering_claim(REGISTER)["limitation"])
    for phrase in (
        "Deterministic deployment-value rendering exists, checked statically at C0",
        "No supported deployment or GitOps path consumes the generated files yet",
        "nothing yet reconstructs the defaults from a committed source bound to that "
        "revision",
        "changes the values and not the release identifier",
        "any other values file given to Helm is not checked",
    ):
        assert phrase in current, phrase
    assert "Deployment rendering does not exist" not in current
    released = _rendering_claim(AS_RELEASED)["limitation"]
    assert released.startswith("Deployment rendering does not exist.")


def test_the_released_register_cannot_be_rebuilt_without_the_later_ledgers() -> None:
    """Every post-release ledger touches the index surface's reason, so undoing fewer
    than all of them is refused at the first one whose value is not what it wrote."""
    with pytest.raises(ValueError, match="r07-surface-reasons"):
        released_register(REGISTER, LEDGER)
    with pytest.raises(ValueError, match="c02-index-surface-reason"):
        released_register(REGISTER, [LEDGER, LATER])
    with pytest.raises(ValueError, match="e01-index-surface-reason"):
        released_register(REGISTER, [LEDGER, LATER, E01])


# ------------------------------------------------------------------ the record


def test_the_record_is_c0_inspection_and_the_claim_s_only_record() -> None:
    (claim,) = [row for row in REGISTER["claims"] if row["claimId"] == CLAIM_ID]
    assert claim["status"] == "certified"
    assert claim["notClaimedReason"] is None
    assert claim["assertsRealBehaviour"] is False
    assert claim["evidenceRecords"] == [ADDED]
    assert ADDED["evidenceLevel"] == "C0"
    assert ADDED["execution"]["targetBehaviourExecuted"] is False
    assert ADDED["execution"]["substitutions"] == []
    assert ADDED["workload"]["source"] == "none"
    assert {row["role"] for row in ADDED["execution"]["executedComponents"]} <= {
        "tool",
        "validator",
    }
    assert ADDED["evidenceRefs"][0] == RECORD_PAGE
    assert claim["automatedTestRefs"] == [
        Path(__file__).relative_to(REPO_ROOT).as_posix()
    ]


def test_no_record_anywhere_is_above_c2() -> None:
    levels = {
        record["evidenceLevel"]
        for claim in REGISTER["claims"]
        for record in claim["evidenceRecords"]
    }
    assert levels <= {"C0", "C1", "C2"}


def test_the_record_says_what_it_read_and_that_it_is_not_in_the_released_pack() -> None:
    page = normalised(read(RECORD_PAGE))
    for value in (
        RELEASE["tagObject"],
        RELEASE["commit"],
        str(RELEASE["releaseId"]),
        RELEASE["publishedAt"],
        RELEASE["evidenceSetSha256"],
        RELEASE["evidencePackSha256"],
    ):
        assert value in page, value
    for phrase in (
        "it is not part of the pack `v1.0.0` was cut over",
        "This page cannot state them, because it is one of the files they cover.",
        "this record does not establish that it read enabled before the tag was created",
        "## What the evidence model cannot yet represent",
    ):
        assert phrase in page, phrase


def test_the_transcript_holds_every_value_the_record_states() -> None:
    raw = (REPO_ROOT / ADDED["evidenceRefs"][1]).read_bytes()
    assert b"\r" not in raw.replace(b"\r\n", b"\n"), "a lone carriage return"
    transcript = raw.decode("utf-8").replace("\r\n", "\n")
    for value in (
        f"object {RELEASE['commit']}",
        f"Evidence pack sha256:{RELEASE['evidencePackSha256']}",
        f"{RELEASE['tagObject']}\trefs/tags/{RELEASE['tag']}",
        f"id {RELEASE['releaseId']}",
        f'published_at "{RELEASE["publishedAt"]}"',
        "draft false",
        "prerelease false",
        "assets 0",
        "releases 1 ['v1.0.0']",
        "completed success",
        '"enabled": true',
        f"         evidence pack  {RELEASE['evidencePackSha256']}",
    ):
        assert value in transcript, value


def test_the_record_names_no_private_path_or_address() -> None:
    for relative in ADDED["evidenceRefs"]:
        text = read(relative)
        assert not re.search(
            r"(?i)(?<![a-z])[a-z]:[\\/]|/users/|scratchpad|planning[\\/]|/tmp/", text
        ), relative
        assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text), relative


# ----------------------------------------------------- the E01 static proof ledger

E01_CLAIM_ID = (
    "the-first-e01-static-run-recorded-identical-renders-and-every-registered-refusal"
)
E01_CHANGES = E01["registerChanges"]
E01_FINDINGS = {row["findingId"]: row for row in E01["findings"]}
(E01_ADDED,) = [c for c in E01_CHANGES if c["operation"] == "add-claim"]
(E01_RECORD,) = E01_ADDED["claim"]["evidenceRecords"]
E01_RUN = "docs/proof/experiments/v2-e01/runs/20261002-e01-abc-1"
#: The register as the E01 ledger left it, before the corrected one.
AFTER_THE_E01_LEDGER = restore_migrated_register(REGISTER, CORRECTED)
#: The register as the reconciliation ledger left it, before the E01 ledger.
AFTER_THIS_LEDGER_AND_RECONCILIATION = restore_migrated_register(
    REGISTER, [E01, CORRECTED]
)


def test_the_e01_ledger_follows_the_reconciliation_and_states_no_release() -> None:
    assert POST_RELEASE_LEDGER_PATHS[2] == E01_STATIC_PROOF_PATH
    assert E01["contractVersion"] == "inferops.io/v1alpha1"
    assert E01["priorLedgerRef"] == (
        CLAIM_RECONCILIATION_PATH.relative_to(REPO_ROOT).as_posix()
    )
    for key in ("registerRef", "priorLedgerRef", "reportRef", "indexRef"):
        assert (REPO_ROOT / E01[key]).is_file(), key
    for absent in ("release", "freeze", "blockers", "blockerDispositions"):
        assert absent not in E01, absent
    assert E01["recordCorrections"] == []
    assert E01["codeRevisions"] == []


def test_it_adds_one_claim_and_changes_one_surface_reason_and_nothing_else() -> None:
    assert [(change["operation"], change.get("field")) for change in E01_CHANGES] == [
        ("add-claim", None),
        ("set-register-field", "nonClaimSurfaces"),
    ]
    (surfaces,) = [c for c in E01_CHANGES if c.get("field") == "nonClaimSurfaces"]
    before = {row["path"]: row for row in surfaces["before"]}
    after = {row["path"]: row for row in surfaces["after"]}
    assert before.keys() == after.keys()
    assert [path for path in before if before[path] != after[path]] == [
        "docs/proof/v1-evidence-index.md"
    ]
    assert "seven ledgers" in after["docs/proof/v1-evidence-index.md"]["reason"]


def test_every_e01_finding_is_answered_by_changes_that_exist() -> None:
    change_ids = {change["changeId"] for change in E01_CHANGES}
    answered: set[str] = set()
    for change in E01_CHANGES:
        assert change["findingId"] in E01_FINDINGS
        assert len(change["reason"]) > 40
    for finding in E01_FINDINGS.values():
        assert set(finding["resolvedBy"]) <= change_ids, finding["findingId"]
        answered |= set(finding["resolvedBy"])
    assert answered == change_ids


def test_the_added_claim_is_the_one_in_the_register_and_not_in_the_released_one() -> (
    None
):
    claims = [row["claimId"] for row in REGISTER["claims"]]
    assert claims[E01_ADDED["position"]] == E01_CLAIM_ID
    # As the E01 ledger left it. The corrected ledger appended a dated audit
    # limitation since, and changed nothing else of the claim.
    assert AFTER_THE_E01_LEDGER["claims"][E01_ADDED["position"]] == (E01_ADDED["claim"])
    held = REGISTER["claims"][E01_ADDED["position"]]
    assert [key for key in held if held[key] != E01_ADDED["claim"][key]] == [
        "limitation"
    ]
    assert E01_CLAIM_ID not in {row["claimId"] for row in AS_RELEASED["claims"]}
    assert E01_CLAIM_ID not in {row["claimId"] for row in AFTER_THIS_LEDGER["claims"]}


def test_the_added_claim_is_certified_on_one_c0_record_of_the_run() -> None:
    """C0, as the freeze record registers the static parts: the renderer ran as a
    tool, its release input was inspected, and nothing deployed or served."""
    claim = E01_ADDED["claim"]
    assert claim["status"] == "certified"
    assert claim["notClaimedReason"] is None
    assert claim["assertsRealBehaviour"] is False
    assert claim["strategyClaimIds"] == []
    assert E01_RECORD["evidenceLevel"] == "C0"
    assert E01_RECORD["execution"]["targetBehaviourExecuted"] is False
    assert E01_RECORD["execution"]["substitutions"] == []
    assert E01_RECORD["workload"]["source"] == "none"
    assert E01_RECORD["environment"]["environmentId"] == "repository-only"
    assert {row["role"] for row in E01_RECORD["execution"]["executedComponents"]} <= {
        "tool",
        "validator",
    }
    for name in ("result.md", "run.v1alpha1.json", "refusals.json", "commands.txt"):
        assert f"{E01_RUN}/{name}" in E01_RECORD["evidenceRefs"], name
    assert E01["reportRef"] in E01_RECORD["evidenceRefs"]
    assert all(c["declaredBefore"] for c in E01_RECORD["acceptanceCriteria"])


def test_the_record_states_the_outcome_and_revision_the_run_recorded() -> None:
    manifest = json.loads(read(f"{E01_RUN}/run.v1alpha1.json"))
    assert set(manifest["outcomes"].values()) == {"PASSED"}
    outcomes = {
        c["criterionId"]: c["outcome"] for c in E01_RECORD["acceptanceCriteria"]
    }
    assert outcomes == {
        criterion["id"].lower(): "met" if criterion["holds"] else "not-met"
        for criterion in manifest["criteria"]
    }
    (commit,) = [v for v in E01_RECORD["versions"] if v["kind"] == "commit"]
    assert commit["value"] == manifest["executingRevision"]
    assert manifest["executingRevision"] in E01_RECORD["summary"]


def test_an_added_claim_already_in_the_register_is_refused() -> None:
    with pytest.raises(ValueError, match="already exists"):
        apply_register_changes(REGISTER, E01)


@pytest.mark.parametrize("position", [-1, 10_000])
def test_an_added_claim_outside_the_claims_is_refused(position: int) -> None:
    ledger = copy.deepcopy(E01)
    ledger["registerChanges"][0]["position"] = position
    with pytest.raises(ValueError, match="outside the claims"):
        apply_register_changes(AFTER_THIS_LEDGER_AND_RECONCILIATION, ledger)


# ------------------------------------------- the corrected E01 static proof ledger

CORRECTED_CLAIM_ID = (
    "the-second-e01-static-run-recorded-its-frozen-path-identical-renders-"
    "and-every-registered-refusal"
)
CORRECTED_CHANGES = CORRECTED["registerChanges"]
CORRECTED_FINDINGS = {row["findingId"]: row for row in CORRECTED["findings"]}
(CORRECTED_ADDED,) = [c for c in CORRECTED_CHANGES if c["operation"] == "add-claim"]
(CORRECTED_RECORD,) = CORRECTED_ADDED["claim"]["evidenceRecords"]
(AUDIT_CHANGE,) = [c for c in CORRECTED_CHANGES if c.get("field") == "limitation"]
(AUDIT_CORRECTION,) = CORRECTED["recordCorrections"]
CORRECTED_RUN = "docs/proof/experiments/v2-e01/runs/20261003-e01-abc-1"
FREEZE_R2 = "docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json"


def test_the_corrected_ledger_follows_the_e01_ledger_and_states_no_release() -> None:
    assert POST_RELEASE_LEDGER_PATHS[3] == E01_CORRECTED_PROOF_PATH
    assert CORRECTED["contractVersion"] == "inferops.io/v1alpha1"
    assert CORRECTED["priorLedgerRef"] == (
        E01_STATIC_PROOF_PATH.relative_to(REPO_ROOT).as_posix()
    )
    for key in ("registerRef", "priorLedgerRef", "reportRef", "indexRef"):
        assert (REPO_ROOT / CORRECTED[key]).is_file(), key
    for absent in ("release", "freeze", "blockers", "blockerDispositions"):
        assert absent not in CORRECTED, absent
    assert CORRECTED["codeRevisions"] == []


def test_it_adds_one_claim_appends_one_limitation_and_changes_one_reason() -> None:
    assert [
        (change["operation"], change.get("field")) for change in CORRECTED_CHANGES
    ] == [
        ("add-claim", None),
        ("set-claim-field", "limitation"),
        ("set-register-field", "nonClaimSurfaces"),
    ]
    (surfaces,) = [c for c in CORRECTED_CHANGES if c.get("field") == "nonClaimSurfaces"]
    before = {row["path"]: row for row in surfaces["before"]}
    after = {row["path"]: row for row in surfaces["after"]}
    assert before.keys() == after.keys()
    assert [path for path in before if before[path] != after[path]] == [
        "docs/proof/v1-evidence-index.md"
    ]
    assert "eight ledgers" in after["docs/proof/v1-evidence-index.md"]["reason"]


def test_every_corrected_finding_is_answered_by_changes_that_exist() -> None:
    change_ids = {change["changeId"] for change in CORRECTED_CHANGES}
    answered: set[str] = set()
    for change in CORRECTED_CHANGES:
        assert change["findingId"] in CORRECTED_FINDINGS
        assert len(change["reason"]) > 40
    for finding in CORRECTED_FINDINGS.values():
        assert set(finding["resolvedBy"]) <= change_ids, finding["findingId"]
        answered |= set(finding["resolvedBy"])
    assert answered == change_ids
    assert AUDIT_CORRECTION["findingId"] in CORRECTED_FINDINGS


def test_the_second_claim_is_appended_and_is_not_in_any_earlier_register() -> None:
    claims = [row["claimId"] for row in REGISTER["claims"]]
    assert CORRECTED_ADDED["position"] == len(claims) - 1
    assert claims[-1] == CORRECTED_CLAIM_ID
    assert REGISTER["claims"][-1] == CORRECTED_ADDED["claim"]
    for earlier in (AS_RELEASED, AFTER_THIS_LEDGER, AFTER_THE_E01_LEDGER):
        assert CORRECTED_CLAIM_ID not in {row["claimId"] for row in earlier["claims"]}


def test_the_second_claim_is_certified_on_one_c0_record_of_the_second_run() -> None:
    """C0, as freeze revision 2 registers the static parts: the renderer ran as a
    tool, its release input was inspected, and nothing deployed or served."""
    claim = CORRECTED_ADDED["claim"]
    assert claim["status"] == "certified"
    assert claim["notClaimedReason"] is None
    assert claim["assertsRealBehaviour"] is False
    assert claim["strategyClaimIds"] == []
    assert "legacyClassification" not in claim
    assert CORRECTED_RECORD["evidenceLevel"] == "C0"
    assert CORRECTED_RECORD["execution"]["targetBehaviourExecuted"] is False
    assert CORRECTED_RECORD["execution"]["substitutions"] == []
    assert CORRECTED_RECORD["workload"]["source"] == "none"
    assert CORRECTED_RECORD["environment"]["environmentId"] == "repository-only"
    roles = {row["role"] for row in CORRECTED_RECORD["execution"]["executedComponents"]}
    assert roles <= {"tool", "validator"}
    for name in ("result.md", "run.v1alpha1.json", "refusals.json", "commands.txt"):
        assert f"{CORRECTED_RUN}/{name}" in CORRECTED_RECORD["evidenceRefs"], name
    assert FREEZE_R2 in CORRECTED_RECORD["evidenceRefs"]
    assert CORRECTED["reportRef"] in CORRECTED_RECORD["evidenceRefs"]
    # It cites nothing of the first run: the two runs are separate evidence.
    assert not [ref for ref in CORRECTED_RECORD["evidenceRefs"] if E01_RUN in ref]
    assert all(c["declaredBefore"] for c in CORRECTED_RECORD["acceptanceCriteria"])


def test_the_second_record_states_what_the_second_run_recorded() -> None:
    manifest = json.loads(read(f"{CORRECTED_RUN}/run.v1alpha1.json"))
    freeze = json.loads(read(FREEZE_R2))
    assert manifest["metadata"]["freezeRecord"] == FREEZE_R2
    assert set(manifest["outcomes"].values()) == {"PASSED"}
    outcomes = {
        c["criterionId"]: c["outcome"] for c in CORRECTED_RECORD["acceptanceCriteria"]
    }
    assert outcomes == {
        criterion["id"].lower(): "met" if criterion["holds"] else "not-met"
        for criterion in manifest["criteria"]
    }
    # Every criterion is quoted from the freeze record the run names, word for word.
    frozen = {
        criterion["id"].lower(): criterion["statement"]
        for entry in freeze["fields"]["acceptanceCriteria"]
        for criterion in entry["value"]
    }
    for criterion in CORRECTED_RECORD["acceptanceCriteria"]:
        assert criterion["statement"] == frozen[criterion["criterionId"]]
    (commit,) = [v for v in CORRECTED_RECORD["versions"] if v["kind"] == "commit"]
    assert commit["value"] == manifest["executingRevision"]
    assert manifest["executingRevision"] in CORRECTED_RECORD["summary"]
    assert manifest["metadata"]["runId"] in CORRECTED_RECORD["procedure"]["commands"][0]


def test_the_second_claim_does_not_validate_the_first_runs_boundary() -> None:
    claim = CORRECTED_ADDED["claim"]
    assert "20261002-e01-abc-1" in claim["limitation"]
    assert "not evidence that the first run" in claim["limitation"]
    assert (
        "the first run's execution was governed by its freeze"
        in (claim["doesNotEstablish"])
    )
    assert any(
        "first run's execution was governed by its freeze" in line
        for line in CORRECTED_RECORD["doesNotEstablish"]
    )


def test_the_audit_limitation_is_appended_and_moves_nothing_else() -> None:
    """The first run's claim keeps every word it had, its status, and its record."""
    assert AUDIT_CHANGE["claimId"] == E01_CLAIM_ID
    assert AUDIT_CHANGE["before"] == E01_ADDED["claim"]["limitation"]
    assert AUDIT_CHANGE["after"].startswith(AUDIT_CHANGE["before"] + " Audit, ")
    appended = AUDIT_CHANGE["after"][len(AUDIT_CHANGE["before"]) :]
    assert "2026-10-03" in appended
    assert "not evidence that its execution was governed by its freeze" in appended
    (claim,) = [row for row in REGISTER["claims"] if row["claimId"] == E01_CLAIM_ID]
    assert claim["limitation"] == AUDIT_CHANGE["after"]
    assert claim["status"] == "certified"
    assert claim["evidenceRecords"] == E01_ADDED["claim"]["evidenceRecords"]


def test_the_correction_is_beside_the_first_runs_page_and_cited_by_its_record() -> None:
    assert AUDIT_CORRECTION["path"] == f"{E01_RUN}/result.md"
    assert AUDIT_CORRECTION["path"] in E01_RECORD["evidenceRefs"]
    assert AUDIT_CORRECTION["correction"].startswith("Dated 2026-10-03.")
    assert {basis["kind"] for basis in AUDIT_CORRECTION["basis"]} == {"file"}
    entries = {entry["recordId"]: entry for entry in INDEX["records"]}
    (listed,) = [
        file
        for file in entries[E01_RECORD["recordId"]]["evidence"]
        if file["path"] == AUDIT_CORRECTION["path"]
    ]
    assert listed["corrections"] == [AUDIT_CORRECTION["correctionId"]]


def test_the_first_runs_files_are_the_ones_the_second_run_found() -> None:
    """Reads the revision the second run executed; a clone without it skips.

    Every file of the first run, and freeze revision 1, has the content it had at
    that revision: this change added beside them and edited none of them.
    """
    revision = json.loads(read(f"{CORRECTED_RUN}/run.v1alpha1.json"))[
        "executingRevision"
    ]
    if _git("cat-file", "-e", f"{revision}^{{commit}}") is None:
        pytest.skip("the clone does not hold the revision the second run executed")
    paths = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / E01_RUN).rglob("*")
        if path.is_file()
    )
    paths.append("docs/proof/experiments/v2-e01/freeze-r1.v1alpha1.json")
    assert len(paths) == 11
    for relative in paths:
        now = _git("hash-object", "--", relative)
        then = _git("rev-parse", f"{revision}:{relative}")
        assert now is not None and then is not None, relative
        assert now.strip() == then.strip(), relative


def test_an_added_second_claim_already_in_the_register_is_refused() -> None:
    with pytest.raises(ValueError, match="already exists"):
        apply_register_changes(REGISTER, CORRECTED)
