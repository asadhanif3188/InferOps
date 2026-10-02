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
AS_RELEASED = released_register(REGISTER, load_ledgers(POST_RELEASE_LEDGER_PATHS))
#: The register as this ledger left it, before the later one.
AFTER_THIS_LEDGER = restore_migrated_register(REGISTER, LATER)
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
    assert apply_register_changes(AFTER_THIS_LEDGER, LATER) == REGISTER


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
    assert SUMMARY["postReleaseRegisterChanges"] == len(CHANGES) + len(
        LATER["registerChanges"]
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


def test_the_released_counts_differ_from_main_by_the_one_record_and_claim() -> None:
    released = SUMMARY["releasedPack"]
    assert released["records"] == SUMMARY["records"] - 1
    assert released["recordsByLevel"]["C0"] == SUMMARY["recordsByLevel"]["C0"] - 1
    certified = SUMMARY["claimsByStatus"]["certified"]
    assert released["claimsByStatus"]["certified"] == certified - 1
    not_claimed = SUMMARY["claimsByStatus"]["not-claimed"]
    assert released["claimsByStatus"]["not-claimed"] == not_claimed + 1
    assert released["evidenceFiles"] == SUMMARY["evidenceFiles"] - len(
        ADDED["evidenceRefs"]
    )


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


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (_edit_another_claim, "and undoing it gives"),
        (_state_another_digest, "and v1.0.0 quoted"),
        (_declare_a_freeze, "declares a freeze"),
        (_raise_a_blocker, "raises or closes a blocker"),
        (_state_a_release_later, "only the first post-release ledger"),
        (_edit_the_reconciled_limitation, "c01-rendering-limitation"),
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


def test_the_released_register_cannot_be_rebuilt_without_the_later_ledger() -> None:
    """Both ledgers touch the index surface's reason, so undoing one alone is refused."""
    with pytest.raises(ValueError, match="r07-surface-reasons"):
        released_register(REGISTER, LEDGER)


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
