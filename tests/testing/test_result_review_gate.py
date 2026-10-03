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
it. The gate reads one repository state. One test reads Git history for the one
correction this change made, and it skips in a clone that lacks the commit.

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

CLAIM_ID = (
    "the-second-e01-static-run-recorded-its-frozen-path-identical-renders-"
    "and-every-registered-refusal"
)
FIRST_CLAIM_ID = (
    "the-first-e01-static-run-recorded-identical-renders-and-every-registered-refusal"
)
FIRST_RUN = "docs/proof/experiments/v2-e01/runs/20261002-e01-abc-1"
SECOND_RUN = "docs/proof/experiments/v2-e01/runs/20261003-e01-abc-1"
FREEZE_R2 = "docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json"
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
    assert len(POST_RELEASE_LEDGER_PATHS) == 5
    assert len(LEDGER_PATHS) == 9
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
    """Status, level, record, and every other field are the eighth ledger's."""
    claim = _claim(REGISTER)
    assert [key for key in claim if claim[key] != ADDED["claim"][key]] == [
        "statement",
        "limitation",
    ]
    assert claim["status"] == "certified"
    assert [record["evidenceLevel"] for record in claim["evidenceRecords"]] == ["C0"]
    before_this_ledger = restore_migrated_register(REGISTER, LEDGER)
    assert _claim(before_this_ledger) == ADDED["claim"]
    assert [row["claimId"] for row in before_this_ledger["claims"]] == [
        row["claimId"] for row in REGISTER["claims"]
    ]
    for now, then in zip(REGISTER["claims"], before_this_ledger["claims"], strict=True):
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
    assert gate["reviewed"] == [{"ledger": LEDGER_NAME, **REVIEW_ROW}]


def test_the_two_earlier_e01_ledgers_are_listed_as_registered_before_the_gate() -> None:
    """Listed, not excused: neither names a review, and none preceded either."""
    assert PRE_GATE_LEDGER_PATHS == (E01_STATIC_PROOF_PATH, E01_CORRECTED_PROOF_PATH)
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
    assert bearing == [*PRE_GATE_LEDGER_PATHS, E01_CLAIM_CORRECTION_PATH]


def _tree(tmp_path: Path) -> Path:
    """A copy of the three things the gate reads: the review, the run, the freeze."""
    for relative in (REVIEW_REF, FREEZE_R2):
        copied = tmp_path / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes((REPO_ROOT / relative).read_bytes())
    shutil.copytree(REPO_ROOT / SECOND_RUN, tmp_path / SECOND_RUN)
    return tmp_path


def _ledgers(mutate: Callable[[dict[str, Any]], None]) -> list[dict[str, Any]]:
    ledgers = copy.deepcopy(LEDGERS)
    mutate(ledgers[-1])
    return ledgers


def _rewrite_review(root: Path, mutate: Callable[[dict[str, Any]], None]) -> str:
    """Edit the copied review artifact, and return the digest it then has."""
    review = copy.deepcopy(REVIEW)
    mutate(review)
    (root / REVIEW_REF).write_text(json.dumps(review, indent=2), encoding="utf-8")
    return content_sha256(root / REVIEW_REF)


def test_the_gate_passes_a_copy_of_what_it_reads(tmp_path: Path) -> None:
    """The control for every refusal below: the unedited copy is accepted."""
    assert review_gate(REGISTER, LEDGERS, _tree(tmp_path))["reviewed"] == [
        {"ledger": LEDGER_NAME, **REVIEW_ROW}
    ]


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
    ],
    ids=lambda change: change["operation"],
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


def test_ledgers_that_do_not_match_their_paths_are_refused() -> None:
    with pytest.raises(ValueError, match="ledgers were given"):
        review_gate(REGISTER, LEDGERS[:-1])


# ------------------------------------------------- what the pages say about it


def test_the_pages_state_the_correction_as_later_and_the_gates_limits() -> None:
    """The limits are the point: a page that drops them overclaims the gate."""
    experiments = normalised(read("docs/proof/experiments/README.md"))
    for phrase in (
        "The correction is additive and later.",
        "It does not show that a review was committed before the register change",
        "No record establishes that an independent review preceded the register "
        "change for either E01 run",
    ):
        assert phrase in experiments, phrase
    validation = normalised(read(LEDGER["reportRef"]))
    for phrase in (
        REVIEW_MERGE,
        content_sha256(REPO_ROOT / REVIEW_REF),
        "No part of E01 ran",
    ):
        assert phrase in validation, phrase
