"""The E01 claim correction, and the gate that asks for a review before a register change.

`V2-S2-005-PR2` did two things, and this module holds both.

**The correction.** An independent review of the second E01 static run found one
clause of that run's claim broader than the frozen criterion it answers: the clause
omitted `of eight characters or more`. A ninth ledger of register changes, the fifth
after the release, adds the qualifier. The failures this module exists to prevent are
a correction that changes more than it says, one that widens the claim, one that
rewrites the ledger that first held the wording, and a current page that still
carries the earlier clause.

**The gate.** `tools.evidence_index.review_gate` refuses a ledger whose changes bear
on an experiment run unless the ledger references an independent-review artifact of
that run. Each refusal is planted here in a copy: no reference, an absent artifact,
an artifact with other content, an artifact about another run, and an artifact that
no longer describes the run's files or its freeze record.

What this module does not establish: that a review took place, who did it, or what it
concluded, and that a review artifact was committed before the ledger that references
it. The gate reads one repository state, and it does not bind a review to a change:
one artifact of a run satisfies every ledger that bears on that run. One test reads
Git history for the one correction this change made, and it skips in a clone that
lacks the commit.

**The first registration under the gate.** `V2-S3-005-PR1` wrote a tenth ledger, which
adds the claim of the E01-D run. It is the first ledger that adds a claim for a run
while the gate exists. This module holds that ledger to the gate: it references the
review record of the E01-D run and the review record of the static run that one E01-D
rule consumes, and each refusal is planted for the E01-D run too. It also holds the one
correction that ledger could not make: the gate refuses a change to the first static
run's claim, because no review record of that run exists.

Every check reads files from this repository and, in that one test, its Git history.
No network, no cluster, no model, no clock, no randomness.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.evidence_index import (
    E01_CLAIM_CORRECTION_PATH,
    E01_CORRECTED_PROOF_PATH,
    E01_D_REGISTRATION_PATH,
    E01_STATIC_PROOF_PATH,
    LEDGER_PATHS,
    POST_RELEASE_LEDGER_PATHS,
    PRE_GATE_LEDGER_PATHS,
    build_index,
    content_sha256,
    load_index,
    load_ledger,
    load_ledgers,
    restore_migrated_register,
    result_runs,
    review_gate,
)
from tools.evidence_index import (
    __main__ as cli,
)
from tools.evidence_index import core as index_core
from tools.evidence_model import REGISTER_PATH, load_register

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER = load_register()
LEDGERS = load_ledgers()
LEDGER = load_ledger(E01_CLAIM_CORRECTION_PATH)
LEDGER_NAME = E01_CLAIM_CORRECTION_PATH.relative_to(REPO_ROOT).as_posix()
CORRECTED = load_ledger(E01_CORRECTED_PROOF_PATH)
INDEX = load_index()
CHANGES = LEDGER["registerChanges"]
FINDINGS = {row["findingId"]: row for row in LEDGER["findings"]}
(STATEMENT_CHANGE,) = [c for c in CHANGES if c.get("field") == "statement"]
(NOTE_CHANGE,) = [c for c in CHANGES if c.get("field") == "limitation"]
(ADDED,) = [c for c in CORRECTED["registerChanges"] if c["operation"] == "add-claim"]
(REVIEW_ROW,) = LEDGER["resultReviews"]
#: The tenth ledger, which registers the E01-D run. It is written after this one.
REGISTRATION = load_ledger(E01_D_REGISTRATION_PATH)
REGISTRATION_NAME = E01_D_REGISTRATION_PATH.relative_to(REPO_ROOT).as_posix()
#: The ledgers that reference the review of the second static run, by position.
SECOND_RUN_REVIEW_LEDGERS = (
    LEDGER_PATHS.index(E01_CLAIM_CORRECTION_PATH),
    LEDGER_PATHS.index(E01_D_REGISTRATION_PATH),
)

CLAIM_ID = (
    "the-second-e01-static-run-recorded-its-frozen-path-identical-renders-"
    "and-every-registered-refusal"
)
FIRST_CLAIM_ID = (
    "the-first-e01-static-run-recorded-identical-renders-and-every-registered-refusal"
)
#: A claim whose one record names no file of any run.
RELEASE_CLAIM_ID = "a-v1-release-has-been-published"
FIRST_RUN = "docs/proof/experiments/v2-e01/runs/20261002-e01-abc-1"
SECOND_RUN = "docs/proof/experiments/v2-e01/runs/20261003-e01-abc-1"
E01_D_RUN = "docs/proof/experiments/v2-e01/runs/20261006-e01-d-1"
FREEZE_R2 = "docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json"
FREEZE_R3 = "docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json"
E01_D_REVIEW_REF = (
    "docs/proof/experiments/v2-e01/reviews/20261006-e01-d-1-review-1.v1alpha1.json"
)
E01_D_CLAIM_ID = (
    "the-e01-real-deployment-run-served-one-completion-from-the-release-"
    "reconciled-from-git"
)
#: What the gate reports for the committed ledgers: one row for each run that each
#: ledger written since the gate bears on, in the order of the ledgers.
REVIEWED = [
    {"ledger": LEDGER_NAME, **REVIEW_ROW},
    *({"ledger": REGISTRATION_NAME, **row} for row in REGISTRATION["resultReviews"]),
]
REVIEW_REF = (
    "docs/proof/experiments/v2-e01/reviews/20261003-e01-abc-1-review-1.v1alpha1.json"
)
REVIEW: dict[str, Any] = json.loads((REPO_ROOT / REVIEW_REF).read_text("utf-8"))
QUALIFIER = "of eight characters or more"
#: The clause as the claim first stated it, and as it is stated now.
EARLIER_CLAUSE = (
    "no hand-written string that contains a generated workload-intent value"
)
CLAUSE = f"{EARLIER_CLAUSE} {QUALIFIER}"
#: The merge of the change that published the review, on main.
REVIEW_MERGE = "4023487e8dabe88ff9219c896056539d7ae499d0"
#: The files a reader meets the claim in today. Each is current, not history.
CURRENT_SURFACES = (
    "docs/testing/claim-evidence-matrix.v1alpha2.json",
    "docs/testing/claim-evidence-matrix.md",
    "docs/proof/dashboard.md",
    "docs/proof/v1-evidence-index.v1alpha1.json",
)


def read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def normalised(text: str) -> str:
    return " ".join(text.split())


def _claim(register: dict[str, Any], claim_id: str = CLAIM_ID) -> dict[str, Any]:
    (claim,) = [row for row in register["claims"] if row["claimId"] == claim_id]
    return claim


def _git(*arguments: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *arguments], cwd=REPO_ROOT, capture_output=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.decode("utf-8")


# ------------------------------------------------------- the correction ledger


def test_the_ledger_is_the_fifth_after_the_release_and_follows_the_fourth() -> None:
    assert POST_RELEASE_LEDGER_PATHS[4] == E01_CLAIM_CORRECTION_PATH
    assert LEDGER_PATHS.index(E01_CLAIM_CORRECTION_PATH) == 8
    assert LEDGER["contractVersion"] == "inferops.io/v1alpha1"
    assert LEDGER["priorLedgerRef"] == (
        E01_CORRECTED_PROOF_PATH.relative_to(REPO_ROOT).as_posix()
    )
    for key in ("registerRef", "priorLedgerRef", "reportRef", "indexRef"):
        assert (REPO_ROOT / LEDGER[key]).is_file(), key
    for absent in ("release", "freeze", "blockers", "blockerDispositions"):
        assert absent not in LEDGER, absent
    assert LEDGER["recordCorrections"] == []
    assert LEDGER["codeRevisions"] == []


def test_it_changes_one_statement_one_limitation_and_one_reason() -> None:
    assert [
        (change["operation"], change.get("claimId"), change["field"])
        for change in CHANGES
    ] == [
        ("set-claim-field", CLAIM_ID, "statement"),
        ("set-claim-field", CLAIM_ID, "limitation"),
        ("set-register-field", None, "nonClaimSurfaces"),
    ]
    (surfaces,) = [c for c in CHANGES if c["field"] == "nonClaimSurfaces"]
    before = {row["path"]: row for row in surfaces["before"]}
    after = {row["path"]: row for row in surfaces["after"]}
    assert before.keys() == after.keys()
    assert [path for path in before if before[path] != after[path]] == [
        "docs/proof/v1-evidence-index.md"
    ]
    assert "nine ledgers" in after["docs/proof/v1-evidence-index.md"]["reason"]


def test_every_finding_is_answered_by_changes_that_exist() -> None:
    change_ids = {change["changeId"] for change in CHANGES}
    answered: set[str] = set()
    for change in CHANGES:
        assert change["findingId"] in FINDINGS
        assert len(change["reason"]) > 40
    for finding in FINDINGS.values():
        assert set(finding["resolvedBy"]) <= change_ids, finding["findingId"]
        answered |= set(finding["resolvedBy"])
    assert answered == change_ids


def test_the_statement_gains_the_qualifier_and_no_other_word_changes() -> None:
    before, after = STATEMENT_CHANGE["before"], STATEMENT_CHANGE["after"]
    assert before == ADDED["claim"]["statement"]
    assert before.count(EARLIER_CLAUSE + ";") == 1
    assert after == before.replace(EARLIER_CLAUSE + ";", CLAUSE + ";")
    assert _claim(REGISTER)["statement"] == after
    assert REVIEW["claimMaterialFinding"]["omittedQualifier"] == QUALIFIER
    assert REVIEW["claimMaterialFinding"]["claimClause"] == EARLIER_CLAUSE


def test_the_qualifier_is_the_frozen_criterions_own() -> None:
    """E01-AC5 as freeze revision 2 states it, and as the claim's record quotes it."""
    freeze = json.loads(read(FREEZE_R2))
    (frozen,) = [
        criterion["statement"]
        for entry in freeze["fields"]["acceptanceCriteria"]
        for criterion in entry["value"]
        if criterion["id"] == "E01-AC5"
    ]
    clause = REVIEW["claimMaterialFinding"]["criterionClause"]
    assert clause.endswith(QUALIFIER)
    assert clause in frozen
    (record,) = _claim(REGISTER)["evidenceRecords"]
    (quoted,) = [
        row["statement"]
        for row in record["acceptanceCriteria"]
        if row["criterionId"] == "e01-ac5"
    ]
    assert quoted == frozen


def test_the_corrected_clause_is_true_of_the_run_and_the_earlier_one_was_not() -> None:
    """The measurement behind the correction, repeated from committed files.

    Every scalar the run generated is compared as text, numbers included, so the
    check is at least as wide as the frozen analysis, which compares strings.
    """

    def scalars(value: Any) -> list[Any]:
        if isinstance(value, dict):
            return [leaf for item in value.values() for leaf in scalars(item)]
        if isinstance(value, list):
            return [leaf for item in value for leaf in scalars(item)]
        return [value]

    finding = REVIEW["claimMaterialFinding"]
    generated = scalars(yaml.safe_load(read(finding["generatedValues"])))
    written = [
        leaf
        for leaf in scalars(yaml.safe_load(read(finding["handWrittenValues"])))
        if isinstance(leaf, str)
    ]
    texts = {str(leaf) for leaf in generated if leaf is not None and leaf != ""}
    contained = {text for text in texts if any(text in held for held in written)}
    assert contained, "the earlier clause would have been true"
    assert [text for text in contained if len(text) >= 8] == []
    assert {row["generatedValue"] for row in finding["literalMatches"]} <= contained


def test_the_correction_note_is_appended_and_keeps_every_earlier_word() -> None:
    before, after = NOTE_CHANGE["before"], NOTE_CHANGE["after"]
    assert before == ADDED["claim"]["limitation"]
    assert after.startswith(before + " Correction, 2026-10-03: ")
    appended = after[len(before) :]
    for phrase in (
        "V2-S2-005-PR2",
        f"'{QUALIFIER}'",
        "E01-AC5",
        REVIEW_REF,
        "no record establishes that a review preceded the register change",
        "The run, its files, its outcomes, this claim's status, and its record are "
        "unchanged.",
    ):
        assert phrase in appended, phrase
    assert _claim(REGISTER)["limitation"] == after


def test_nothing_else_of_the_claim_moved_and_no_claim_was_added() -> None:
    """Status, level, record, and every other field are the eighth ledger's. The
    tenth ledger, written later, replaced one clause of what the claim does not
    establish; that ledger is undone first, so this reads the register as the ninth
    ledger left it."""
    claim = _claim(REGISTER)
    assert [key for key in claim if claim[key] != ADDED["claim"][key]] == [
        "statement",
        "limitation",
        "doesNotEstablish",
    ]
    assert claim["status"] == "certified"
    assert [record["evidenceLevel"] for record in claim["evidenceRecords"]] == ["C0"]
    after_this_ledger = restore_migrated_register(REGISTER, REGISTRATION)
    held = _claim(after_this_ledger)
    assert [key for key in held if held[key] != ADDED["claim"][key]] == [
        "statement",
        "limitation",
    ]
    before_this_ledger = restore_migrated_register(after_this_ledger, LEDGER)
    assert _claim(before_this_ledger) == ADDED["claim"]
    assert [row["claimId"] for row in before_this_ledger["claims"]] == [
        row["claimId"] for row in after_this_ledger["claims"]
    ]
    for now, then in zip(
        after_this_ledger["claims"], before_this_ledger["claims"], strict=True
    ):
        if now["claimId"] != CLAIM_ID:
            assert now == then, now["claimId"]


def test_the_earlier_wording_stays_in_the_ledger_that_added_the_claim() -> None:
    """History is not rewritten: the eighth ledger has the content the review read."""
    reviewed = REVIEW["review"]["registerAtReviewedRevision"]["ledger"]
    assert reviewed["path"] == (
        E01_CORRECTED_PROOF_PATH.relative_to(REPO_ROOT).as_posix()
    )
    assert content_sha256(E01_CORRECTED_PROOF_PATH) == reviewed["contentSha256"]
    assert EARLIER_CLAUSE + ";" in ADDED["claim"]["statement"]


@pytest.mark.parametrize("relative", CURRENT_SURFACES)
def test_no_current_surface_states_the_clause_without_its_qualifier(
    relative: str,
) -> None:
    text = normalised(read(relative))
    assert text.count(CLAUSE) >= 1, relative
    assert text.count(EARLIER_CLAUSE) == text.count(CLAUSE), relative


def test_the_review_was_on_main_before_the_correction_was_written() -> None:
    """Reads Git history; a clone without the review's merge commit skips.

    At the merge of the change that published the review, the review artifact had
    the content it has now, this ledger did not exist, and the register held the
    earlier clause. That is an order of commits. It is not a time, and it is not
    evidence that a review preceded the register change that added the claim.
    """
    if _git("cat-file", "-e", f"{REVIEW_MERGE}^{{commit}}") is None:
        pytest.skip("the clone does not hold the merge that published the review")
    # The merge is in this change's own history, not merely an object in the clone.
    assert _git("merge-base", "--is-ancestor", REVIEW_MERGE, "HEAD") is not None
    then = _git("rev-parse", f"{REVIEW_MERGE}:{REVIEW_REF}")
    now = _git("hash-object", "--", REVIEW_REF)
    assert then is not None and now is not None
    assert then.strip() == now.strip()
    assert _git("cat-file", "-e", f"{REVIEW_MERGE}:{LEDGER_NAME}") is None
    register = _git(
        "show", f"{REVIEW_MERGE}:{REGISTER_PATH.relative_to(REPO_ROOT).as_posix()}"
    )
    assert register is not None
    assert _claim(json.loads(register))["statement"] == STATEMENT_CHANGE["before"]


# ------------------------------------------------------------------ the gate


def test_the_ledger_references_the_merged_review_of_the_run_it_corrects() -> None:
    assert REVIEW_ROW["runPath"] == SECOND_RUN
    assert REVIEW_ROW["reviewRef"] == REVIEW_REF
    assert REVIEW_ROW["reviewSha256"] == content_sha256(REPO_ROOT / REVIEW_REF)
    assert set(REVIEW_ROW) == {"runPath", "reviewRef", "reviewSha256"}
    assert REVIEW["kind"] == "ExperimentResultReview"
    assert REVIEW["subject"]["runPath"] == SECOND_RUN
    assert result_runs(REGISTER, LEDGER) == [SECOND_RUN]


def test_the_gate_passes_the_committed_ledgers_and_the_index_states_its_result() -> (
    None
):
    gate = review_gate(REGISTER, LEDGERS)
    assert gate == INDEX["summary"]["resultReviews"]
    assert gate["reviewed"] == REVIEWED


def test_the_two_earlier_e01_ledgers_are_listed_as_registered_before_the_gate() -> None:
    """Listed, not excused: neither names a review, and no record establishes one
    before either. The gate does not check these two ledgers, whatever they hold, so
    each is held here to the content it had when the gate was added."""
    assert PRE_GATE_LEDGER_PATHS == (E01_STATIC_PROOF_PATH, E01_CORRECTED_PROOF_PATH)
    assert [content_sha256(path) for path in PRE_GATE_LEDGER_PATHS] == [
        "6de763ea73fd1d2fc79b08f4bebb9e5ca6c427e3b2655efe309e63c48edc5c46",
        "b76013231571bfd52bf76eb2480688b78e3f328aed5a9d5f864142ca6a439259",
    ]
    assert review_gate(REGISTER, LEDGERS)["registeredBeforeTheGate"] == [
        {
            "ledger": E01_STATIC_PROOF_PATH.relative_to(REPO_ROOT).as_posix(),
            "runPaths": [FIRST_RUN],
        },
        {
            "ledger": E01_CORRECTED_PROOF_PATH.relative_to(REPO_ROOT).as_posix(),
            "runPaths": [FIRST_RUN, SECOND_RUN],
        },
    ]
    for path in PRE_GATE_LEDGER_PATHS:
        assert "resultReviews" not in load_ledger(path), path.name


def test_only_the_e01_ledgers_bear_on_a_run() -> None:
    bearing = [
        path
        for path, ledger in zip(LEDGER_PATHS, LEDGERS, strict=True)
        if result_runs(REGISTER, ledger)
    ]
    assert bearing == [
        *PRE_GATE_LEDGER_PATHS,
        E01_CLAIM_CORRECTION_PATH,
        E01_D_REGISTRATION_PATH,
    ]


def _tree(tmp_path: Path) -> Path:
    """A copy of the three things the gate reads for each reviewed run: the review,
    the run, and the freeze record."""
    for relative in (REVIEW_REF, FREEZE_R2, E01_D_REVIEW_REF, FREEZE_R3):
        copied = tmp_path / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes((REPO_ROOT / relative).read_bytes())
    for run in (SECOND_RUN, E01_D_RUN):
        shutil.copytree(REPO_ROOT / run, tmp_path / run)
    return tmp_path


def _ledgers(mutate: Callable[[dict[str, Any]], None]) -> list[dict[str, Any]]:
    """Every ledger, with the edit made to each ledger that references the review of
    the second static run. In each of them that reference is the first row. One
    artifact of a run satisfies every ledger that bears on the run, so a defect planted
    in the artifact, or in the reference to it, is stated the same way in each. The
    gate reads the ledgers in order and refuses at the first of them."""
    ledgers = copy.deepcopy(LEDGERS)
    for index in SECOND_RUN_REVIEW_LEDGERS:
        assert ledgers[index]["resultReviews"][0]["runPath"] == SECOND_RUN
        mutate(ledgers[index])
    return ledgers


def _registration(mutate: Callable[[dict[str, Any]], None]) -> list[dict[str, Any]]:
    """Every ledger, with the edit made to the E01-D registration ledger only."""
    ledgers = copy.deepcopy(LEDGERS)
    mutate(ledgers[LEDGER_PATHS.index(E01_D_REGISTRATION_PATH)])
    return ledgers


def _rewrite_review(root: Path, mutate: Callable[[dict[str, Any]], None]) -> str:
    """Edit the copied review artifact, and return the digest it then has."""
    review = copy.deepcopy(REVIEW)
    mutate(review)
    (root / REVIEW_REF).write_text(json.dumps(review, indent=2), encoding="utf-8")
    return content_sha256(root / REVIEW_REF)


def test_the_gate_passes_a_copy_of_what_it_reads(tmp_path: Path) -> None:
    """The control for every refusal below: the unedited copy is accepted."""
    assert review_gate(REGISTER, LEDGERS, _tree(tmp_path))["reviewed"] == REVIEWED


def test_a_result_bearing_ledger_with_no_review_reference_is_refused(
    tmp_path: Path,
) -> None:
    def drop(ledger: dict[str, Any]) -> None:
        del ledger["resultReviews"]

    def empty(ledger: dict[str, Any]) -> None:
        ledger["resultReviews"] = []

    for mutate in (drop, empty):
        with pytest.raises(ValueError, match="references no independent review"):
            review_gate(REGISTER, _ledgers(mutate), _tree(tmp_path / mutate.__name__))
    # The index is not built either, so --check, --write, and --gate all refuse.
    with pytest.raises(ValueError, match="references no independent review"):
        build_index(REGISTER, _ledgers(drop))


def test_a_missing_review_artifact_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / REVIEW_REF).unlink()
    with pytest.raises(ValueError, match="is absent"):
        review_gate(REGISTER, LEDGERS, root)


def test_a_review_of_another_run_is_refused(tmp_path: Path) -> None:
    """The artifact is present and has the digest the ledger states. It is about
    the first run, so it does not satisfy a change that bears on the second."""
    root = _tree(tmp_path)

    def other_run(review: dict[str, Any]) -> None:
        review["subject"]["runId"] = "20261002-e01-abc-1"
        review["subject"]["runPath"] = FIRST_RUN

    digest = _rewrite_review(root, other_run)

    def restate(ledger: dict[str, Any]) -> None:
        ledger["resultReviews"][0]["reviewSha256"] = digest

    with pytest.raises(ValueError, match="reviews the run"):
        review_gate(REGISTER, _ledgers(restate), root)


def test_a_reference_that_names_another_run_is_refused(tmp_path: Path) -> None:
    def other_run(ledger: dict[str, Any]) -> None:
        ledger["resultReviews"][0]["runPath"] = FIRST_RUN

    with pytest.raises(ValueError, match="references no independent review"):
        review_gate(REGISTER, _ledgers(other_run), _tree(tmp_path))


def test_a_review_artifact_with_other_content_is_refused(tmp_path: Path) -> None:
    """Edited after the ledger stated its digest, or stated with another digest."""
    root = _tree(tmp_path / "edited")
    _rewrite_review(root, lambda review: review["findings"].pop())
    with pytest.raises(ValueError, match="has the content digest"):
        review_gate(REGISTER, LEDGERS, root)

    def restate(ledger: dict[str, Any]) -> None:
        ledger["resultReviews"][0]["reviewSha256"] = "0" * 64

    with pytest.raises(ValueError, match="has the content digest"):
        review_gate(REGISTER, _ledgers(restate), _tree(tmp_path / "restated"))


def _edit_a_run_file(root: Path) -> None:
    with (root / SECOND_RUN / "result.md").open("a", encoding="utf-8") as handle:
        handle.write("\nEdited after the review.\n")


def _add_a_run_file(root: Path) -> None:
    (root / SECOND_RUN / "extra.txt").write_text("added\n", encoding="utf-8")


def _remove_a_run_file(root: Path) -> None:
    (root / SECOND_RUN / "refusals.json").unlink()


@pytest.mark.parametrize(
    ("mutate", "named"),
    [
        (_edit_a_run_file, "result.md"),
        (_add_a_run_file, "extra.txt"),
        (_remove_a_run_file, "refusals.json"),
    ],
    ids=lambda value: value.__name__.strip("_") if callable(value) else "",
)
def test_a_review_that_no_longer_describes_the_run_is_refused(
    tmp_path: Path, mutate: Callable[[Path], None], named: str
) -> None:
    """A stale review: the run's files are not the ones the review read."""
    root = _tree(tmp_path)
    mutate(root)
    with pytest.raises(ValueError, match="does not describe the files") as refusal:
        review_gate(REGISTER, LEDGERS, root)
    assert named in str(refusal.value)


def test_a_review_of_another_freeze_record_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    with (root / FREEZE_R2).open("a", encoding="utf-8") as handle:
        handle.write(" ")
    with pytest.raises(ValueError, match="names a freeze record"):
        review_gate(REGISTER, LEDGERS, root)


def test_an_artifact_that_is_not_a_result_review_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)

    def other_kind(review: dict[str, Any]) -> None:
        review["kind"] = "ExperimentFreeze"

    digest = _rewrite_review(root, other_kind)

    def restate(ledger: dict[str, Any]) -> None:
        ledger["resultReviews"][0]["reviewSha256"] = digest

    with pytest.raises(ValueError, match="is not an ExperimentResultReview"):
        review_gate(REGISTER, _ledgers(restate), root)


def test_a_reference_outside_the_experiments_reviews_is_refused(tmp_path: Path) -> None:
    def elsewhere(ledger: dict[str, Any]) -> None:
        ledger["resultReviews"][0]["reviewRef"] = FREEZE_R2

    with pytest.raises(ValueError, match="is not under"):
        review_gate(REGISTER, _ledgers(elsewhere), _tree(tmp_path))


def test_two_references_for_one_run_and_an_unrelated_reference_are_refused(
    tmp_path: Path,
) -> None:
    def twice(ledger: dict[str, Any]) -> None:
        ledger["resultReviews"].append(copy.deepcopy(ledger["resultReviews"][0]))

    with pytest.raises(ValueError, match="two reviews are referenced"):
        review_gate(REGISTER, _ledgers(twice), _tree(tmp_path / "twice"))

    def surface_only(ledger: dict[str, Any]) -> None:
        ledger["registerChanges"] = ledger["registerChanges"][2:]

    with pytest.raises(ValueError, match="no register change bears on it"):
        review_gate(REGISTER, _ledgers(surface_only), _tree(tmp_path / "unrelated"))


def test_a_ledger_written_before_the_gate_cannot_state_a_review_now() -> None:
    ledgers = copy.deepcopy(LEDGERS)
    ledgers[LEDGER_PATHS.index(E01_CORRECTED_PROOF_PATH)]["resultReviews"] = [
        copy.deepcopy(REVIEW_ROW)
    ]
    with pytest.raises(ValueError, match="written before the review gate"):
        review_gate(REGISTER, ledgers)


def _later_ledger(change: dict[str, Any]) -> dict[str, Any]:
    return {"registerChanges": [change]}


@pytest.mark.parametrize(
    "change",
    [
        {
            "changeId": "x-add-claim",
            "operation": "add-claim",
            "claim": {
                "claimId": "a-third-run",
                "evidenceRecords": [{"evidenceRefs": [f"{SECOND_RUN}/result.md"]}],
            },
        },
        {
            "changeId": "x-add-record",
            "operation": "add-record",
            "claimId": CLAIM_ID,
            "record": {"evidenceRefs": [f"{FIRST_RUN}/run.v1alpha1.json"]},
        },
        {
            "changeId": "x-set-claim-field",
            "operation": "set-claim-field",
            "claimId": FIRST_CLAIM_ID,
            "field": "statement",
        },
        {
            "changeId": "x-set-record-field",
            "operation": "set-record-field",
            "claimId": FIRST_CLAIM_ID,
            "recordId": f"{FIRST_CLAIM_ID}-c0",
            "field": "summary",
        },
        {
            "changeId": "x-cites-the-run-in-another-field",
            "operation": "add-record",
            "claimId": CLAIM_ID,
            "record": {"versionsRecordedIn": f"{FIRST_RUN}/run.v1alpha1.json"},
        },
        {
            "changeId": "x-removes-the-citation",
            "operation": "set-record-field",
            "claimId": RELEASE_CLAIM_ID,
            "recordId": f"{RELEASE_CLAIM_ID}-c0",
            "field": "evidenceRefs",
            "before": [f"{FIRST_RUN}/result.md"],
            "after": [],
        },
    ],
    ids=lambda change: change["changeId"],
)
def test_a_later_result_bearing_ledger_with_no_review_is_refused(
    change: dict[str, Any],
) -> None:
    """The gate is for the next ledger: every operation that bears on a run needs
    a review, and no review of the first run exists."""
    later = REPO_ROOT / "docs" / "proof" / "testing" / "a-later-ledger.json"
    with pytest.raises(ValueError, match=r"a-later-ledger.json: a register change"):
        review_gate(
            REGISTER,
            [*LEDGERS, _later_ledger(change)],
            ledger_paths=(*LEDGER_PATHS, later),
        )


def test_a_later_ledger_that_bears_on_no_run_needs_no_review() -> None:
    later = REPO_ROOT / "docs" / "proof" / "testing" / "a-later-ledger.json"
    change = {"operation": "set-register-field", "field": "nonClaimSurfaces"}
    gate = review_gate(
        REGISTER,
        [*LEDGERS, _later_ledger(change)],
        ledger_paths=(*LEDGER_PATHS, later),
    )
    assert gate == review_gate(REGISTER, LEDGERS)


def test_a_register_change_of_an_unknown_operation_is_refused() -> None:
    """The register tools apply any other operation as a claim-field change, so an
    operation the gate ignored would change a claim and need no review."""

    def rename(ledger: dict[str, Any]) -> None:
        del ledger["resultReviews"]
        for change in ledger["registerChanges"]:
            if change["operation"] == "set-claim-field":
                change["operation"] = "amend-claim-field"

    ledgers = _ledgers(rename)
    with pytest.raises(ValueError, match="does not know the operation"):
        review_gate(REGISTER, ledgers)
    with pytest.raises(ValueError, match="does not know the operation"):
        build_index(REGISTER, ledgers)


def _no_run_path(row: dict[str, Any]) -> None:
    del row["runPath"]


def _no_digest(row: dict[str, Any]) -> None:
    del row["reviewSha256"]


def _an_extra_member(row: dict[str, Any]) -> None:
    row["reviewedBy"] = "someone"


def _a_number(row: dict[str, Any]) -> None:
    row["reviewRef"] = 1


@pytest.mark.parametrize(
    "mutate",
    [_no_run_path, _no_digest, _an_extra_member, _a_number],
    ids=lambda mutate: mutate.__name__.strip("_"),
)
def test_a_malformed_review_row_is_refused_and_not_a_traceback(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    def edit(ledger: dict[str, Any]) -> None:
        mutate(ledger["resultReviews"][0])

    with pytest.raises(ValueError, match="a resultReviews row is not exactly"):
        review_gate(REGISTER, _ledgers(edit))


@pytest.mark.parametrize("stated", [None, {}, "a review", [REVIEW_REF]])
def test_review_references_that_are_not_a_list_of_rows_are_refused(
    stated: Any,
) -> None:
    def edit(ledger: dict[str, Any]) -> None:
        ledger["resultReviews"] = stated

    with pytest.raises(ValueError, match="resultReviews"):
        review_gate(REGISTER, _ledgers(edit))


@pytest.mark.parametrize(
    "reference",
    [
        "docs/proof/experiments/v2-e01/reviews/../freeze-r2.v1alpha1.json",
        "docs/proof/experiments/v2-e01/reviews/..\\freeze-r2.v1alpha1.json",
        "docs/proof/experiments/v2-e01/reviews/./" + REVIEW_REF.rsplit("/", 1)[1],
    ],
    ids=["parent", "backslash", "dot"],
)
def test_a_reference_that_is_not_a_plain_path_is_refused(
    tmp_path: Path, reference: str
) -> None:
    def elsewhere(ledger: dict[str, Any]) -> None:
        ledger["resultReviews"][0]["reviewRef"] = reference

    with pytest.raises(ValueError, match="is not under"):
        review_gate(REGISTER, _ledgers(elsewhere), _tree(tmp_path))


@pytest.mark.parametrize("member", ["runId", "runPath"])
def test_a_review_whose_run_identifier_or_path_alone_differs_is_refused(
    tmp_path: Path, member: str
) -> None:
    root = _tree(tmp_path)

    def other(review: dict[str, Any]) -> None:
        review["subject"][member] = review["subject"][member].replace(
            "20261003", "20261002"
        )

    digest = _rewrite_review(root, other)

    def restate(ledger: dict[str, Any]) -> None:
        ledger["resultReviews"][0]["reviewSha256"] = digest

    with pytest.raises(ValueError, match="reviews the run"):
        review_gate(REGISTER, _ledgers(restate), root)


def test_an_artifact_that_is_not_json_is_refused(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    (root / REVIEW_REF).write_text("not a review\n", encoding="utf-8")
    digest = content_sha256(root / REVIEW_REF)

    def restate(ledger: dict[str, Any]) -> None:
        ledger["resultReviews"][0]["reviewSha256"] = digest

    with pytest.raises(ValueError, match="is not an ExperimentResultReview"):
        review_gate(REGISTER, _ledgers(restate), root)


@pytest.mark.parametrize(
    "named",
    [
        "docs/proof/experiments/v2-e01/freeze-r1.v1alpha1.json",
        f"{SECOND_RUN}/result.md",
        "README.md",
        "../outside.json",
    ],
    ids=["another-revision", "a-run-file", "another-file", "outside-the-root"],
)
def test_a_review_that_names_a_file_other_than_the_runs_freeze_record_is_refused(
    tmp_path: Path, named: str
) -> None:
    """The file exists and the artifact gives its true digest. It is not the freeze
    record the run's manifest names, so the review did not read the run's freeze."""
    root = _tree(tmp_path / "root")
    target = root / named
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text("{}\n", encoding="utf-8")

    def other_freeze(review: dict[str, Any]) -> None:
        review["subject"]["freeze"]["path"] = named
        review["subject"]["freeze"]["contentSha256"] = content_sha256(target)

    digest = _rewrite_review(root, other_freeze)

    def restate(ledger: dict[str, Any]) -> None:
        ledger["resultReviews"][0]["reviewSha256"] = digest

    with pytest.raises(ValueError, match="names a freeze record"):
        review_gate(REGISTER, _ledgers(restate), root)


@pytest.mark.parametrize("mode", [["--check"], ["--print"], []])
def test_the_command_reports_a_refusal_as_a_mismatch_and_exits_1(
    mode: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The command, not only the library: no index, no traceback, exit 1."""

    def drop(ledger: dict[str, Any]) -> None:
        del ledger["resultReviews"]

    ledgers = _ledgers(drop)
    monkeypatch.setattr(index_core, "load_ledgers", lambda *_: ledgers)
    assert cli.main(mode) == 1
    printed = capsys.readouterr().out
    assert printed.startswith("MISMATCH ")
    assert "references no independent review" in printed


def test_ledgers_that_do_not_match_their_paths_are_refused() -> None:
    with pytest.raises(ValueError, match="ledgers were given"):
        review_gate(REGISTER, LEDGERS[:-1])


# ---------------------------------------- the E01-D registration under the gate


def test_the_registration_ledger_is_the_sixth_after_the_release() -> None:
    assert POST_RELEASE_LEDGER_PATHS[5] == E01_D_REGISTRATION_PATH
    assert LEDGER_PATHS.index(E01_D_REGISTRATION_PATH) == 9
    assert len(POST_RELEASE_LEDGER_PATHS) == 6
    assert len(LEDGER_PATHS) == 10
    assert REGISTRATION["contractVersion"] == "inferops.io/v1alpha1"
    assert REGISTRATION["priorLedgerRef"] == LEDGER_NAME
    for key in ("registerRef", "priorLedgerRef", "reportRef", "indexRef"):
        assert (REPO_ROOT / REGISTRATION[key]).is_file(), key
    for absent in ("release", "freeze", "blockers", "blockerDispositions"):
        assert absent not in REGISTRATION, absent
    assert REGISTRATION["recordCorrections"] == []


def test_the_registration_references_the_review_of_each_run_it_bears_on() -> None:
    """Two runs: the E01-D run the new claim is about, and the second static run,
    which the new record cites for one rule and whose claim the ledger changes."""
    assert result_runs(REGISTER, REGISTRATION) == [SECOND_RUN, E01_D_RUN]
    static_row, run_row = REGISTRATION["resultReviews"]
    assert static_row == REVIEW_ROW
    assert run_row == {
        "runPath": E01_D_RUN,
        "reviewRef": E01_D_REVIEW_REF,
        "reviewSha256": content_sha256(REPO_ROOT / E01_D_REVIEW_REF),
    }
    review = json.loads(read(E01_D_REVIEW_REF))
    assert review["kind"] == "ExperimentResultReview"
    assert review["subject"]["runPath"] == E01_D_RUN
    manifest = json.loads(read(f"{E01_D_RUN}/run.v1alpha1.json"))
    assert review["subject"]["freeze"]["path"] == manifest["metadata"]["freezeRecord"]
    assert review["subject"]["freeze"]["path"] == FREEZE_R3
    assert review["subject"]["outcomes"] == manifest["outcomes"]


def test_the_review_of_the_real_deployment_run_merged_before_the_registration() -> None:
    """Reads Git history; skips in a clone that lacks the commit. The gate cannot
    show this order. History can: the review record has had its present content since
    the merge of the change that ran E01-D, and the ledger is not in that commit."""
    merge = "2c84793802bd14b5237e15dc6f6a2f1b6515d716"
    then = _git("rev-parse", f"{merge}:{E01_D_REVIEW_REF}")
    if then is None:
        pytest.skip("the merge of the change that ran E01-D is not in this clone")
    now = _git("hash-object", "--", E01_D_REVIEW_REF)
    assert now is not None and now.strip() == then.strip()
    assert _git("rev-parse", f"{merge}:{REGISTRATION_NAME}") is None
    tracked = _git("ls-tree", "-r", "--name-only", merge, "--", E01_D_RUN)
    assert tracked is not None
    for relative in tracked.split():
        was = _git("rev-parse", f"{merge}:{relative}")
        held = _git("hash-object", "--", relative)
        assert was is not None and held is not None, relative
        assert held.strip() == was.strip(), relative


def test_the_registration_without_the_review_of_the_real_deployment_run_is_refused(
    tmp_path: Path,
) -> None:
    def drop(ledger: dict[str, Any]) -> None:
        del ledger["resultReviews"][1]

    with pytest.raises(ValueError, match="references no independent review") as refusal:
        review_gate(REGISTER, _registration(drop), _tree(tmp_path / "dropped"))
    assert REGISTRATION_NAME in str(refusal.value)
    assert E01_D_RUN in str(refusal.value)
    with pytest.raises(ValueError, match="references no independent review"):
        build_index(REGISTER, _registration(drop))
    root = _tree(tmp_path / "absent")
    (root / E01_D_REVIEW_REF).unlink()
    with pytest.raises(ValueError, match="is absent"):
        review_gate(REGISTER, LEDGERS, root)


def test_the_review_of_the_static_run_does_not_stand_for_the_real_deployment_run(
    tmp_path: Path,
) -> None:
    """The review record of another run of the same experiment, stated with its true
    digest, is refused for the E01-D run."""

    def reuse(ledger: dict[str, Any]) -> None:
        ledger["resultReviews"][1]["reviewRef"] = REVIEW_REF
        ledger["resultReviews"][1]["reviewSha256"] = REVIEW_ROW["reviewSha256"]

    with pytest.raises(ValueError, match="reviews the run") as refusal:
        review_gate(REGISTER, _registration(reuse), _tree(tmp_path))
    assert REGISTRATION_NAME in str(refusal.value)


def _edit_a_real_deployment_file(root: Path) -> None:
    with (root / E01_D_RUN / "completion.json").open("a", encoding="utf-8") as handle:
        handle.write(" ")


def _add_a_real_deployment_file(root: Path) -> None:
    (root / E01_D_RUN / "second-attempt.json").write_text("{}\n", encoding="utf-8")


def _remove_a_real_deployment_file(root: Path) -> None:
    (root / E01_D_RUN / "transcript.txt").unlink()


@pytest.mark.parametrize(
    ("mutate", "named"),
    [
        (_edit_a_real_deployment_file, "completion.json"),
        (_add_a_real_deployment_file, "second-attempt.json"),
        (_remove_a_real_deployment_file, "transcript.txt"),
    ],
    ids=lambda value: value.__name__.strip("_") if callable(value) else "",
)
def test_a_changed_real_deployment_run_is_refused_by_the_gate(
    tmp_path: Path, mutate: Callable[[Path], None], named: str
) -> None:
    """The registration rests on the run as the review read it. A run file that is
    edited, added, or removed afterwards makes the review stale, and the index is not
    built."""
    root = _tree(tmp_path)
    mutate(root)
    with pytest.raises(ValueError, match="does not describe the files") as refusal:
        review_gate(REGISTER, LEDGERS, root)
    assert REGISTRATION_NAME in str(refusal.value)
    assert named in str(refusal.value)


def test_a_changed_freeze_revision_three_is_refused_by_the_gate(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    with (root / FREEZE_R3).open("a", encoding="utf-8") as handle:
        handle.write(" ")
    with pytest.raises(ValueError, match="names a freeze record") as refusal:
        review_gate(REGISTER, LEDGERS, root)
    assert REGISTRATION_NAME in str(refusal.value)


def test_the_first_static_claim_cannot_change_without_a_review_of_its_run() -> None:
    """The registration ledger replaced the clause that says E01-D 'has not run' in
    the second static run's claim. It could not replace the same clause in the first
    static run's claim: that change bears on the first run, no review record of that
    run exists, and the gate refuses it. So the first claim still carries the clause,
    as a statement of 2026-10-02. A later change that corrects it fails here until
    this test changes with it."""
    stale = "which E01-D owns and has not run"
    assert stale in _claim(REGISTER, FIRST_CLAIM_ID)["doesNotEstablish"]
    assert stale not in _claim(REGISTER)["doesNotEstablish"]
    assert stale in ADDED["claim"]["doesNotEstablish"]

    def also_the_first_claim(ledger: dict[str, Any]) -> None:
        before = _claim(REGISTER, FIRST_CLAIM_ID)["doesNotEstablish"]
        ledger["registerChanges"].append(
            {
                "changeId": "x-first-static-claim-clause",
                "operation": "set-claim-field",
                "claimId": FIRST_CLAIM_ID,
                "field": "doesNotEstablish",
                "before": before,
                "after": before.replace(stale, "which E01-D owns"),
            }
        )

    with pytest.raises(ValueError, match="references no independent review") as refusal:
        review_gate(REGISTER, _registration(also_the_first_claim))
    assert FIRST_RUN in str(refusal.value)
    reviews = REPO_ROOT / "docs/proof/experiments/v2-e01/reviews"
    assert not list(reviews.glob("20261002-e01-abc-1-review-*"))


def test_the_added_claim_is_the_only_claim_that_cites_the_real_deployment_run() -> None:
    citing = [
        row["claimId"]
        for row in REGISTER["claims"]
        if any(
            ref.startswith(f"{E01_D_RUN}/")
            for record in row["evidenceRecords"]
            for ref in record["evidenceRefs"]
        )
    ]
    assert citing == [E01_D_CLAIM_ID]
    (added,) = [
        change
        for change in REGISTRATION["registerChanges"]
        if change["operation"] == "add-claim"
    ]
    assert added["position"] == len(REGISTER["claims"]) - 1
    assert _claim(REGISTER, E01_D_CLAIM_ID) == added["claim"]


# ------------------------------------------------- what the pages say about it


def test_the_pages_state_the_correction_as_later_and_the_gates_limits() -> None:
    """The limits are the point: a page that drops them overclaims the gate."""
    experiments = normalised(read("docs/proof/experiments/README.md"))
    for phrase in (
        "The correction is additive and later.",
        "It does not show that a review was committed before the register change",
        "No record establishes that an independent review preceded the register "
        "change for either E01 run",
        "It does not bind a review to a change.",
    ):
        assert phrase in experiments, phrase
    validation = normalised(read(LEDGER["reportRef"]))
    for phrase in (
        REVIEW_MERGE,
        content_sha256(REPO_ROOT / REVIEW_REF),
        "No part of E01 ran",
    ):
        assert phrase in validation, phrase
