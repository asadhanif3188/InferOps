# V2-S2-005-PR2 validation

Date: 2026-10-03

What this change corrects, what it adds, what it leaves unchanged, and the checks run over
the repository. The change does two things:

1. It narrows one statement in the claim and evidence register, through
   [a ninth ledger of register changes](../testing/v2-s2-005-pr2-e01-claim-correction.v1alpha1.json).
2. It adds a gate to `tools/evidence_index`: a ledger whose changes bear on an experiment
   run must reference an independent-review artifact of that run.

No part of E01 ran. The change contacted no cluster, runtime, registry, or model, and
nothing was provisioned or published. It adds no claim and no evidence record.

## Why this change exists

[The independent review of the second E01 static run](../experiments/v2-e01/reviews/20261003-e01-abc-1-review-1.md),
published by `V2-S2-005-PR1`, found no defect in the run and one claim-material defect in
the register: one clause of the second-run claim omitted the qualifier that the frozen
criterion E01-AC5 carries. The review also recorded that no record establishes a review
before the register change for either E01 run. `V2-S2-005-PR1` corrected nothing and
assigned the correction to this change.

## Eligibility, checked before the change

- **The review is merged.** `git pull origin main` left `main` at
  `4023487e8dabe88ff9219c896056539d7ae499d0`, the merge of pull request 115, which is
  `V2-S2-005-PR1`. Its first parent is `3f08f4393167a0c49e63f4f1d968250d54f48017`, the
  merge of pull request 114.
- **The review artifact has a stable identity.**
  `docs/proof/experiments/v2-e01/reviews/20261003-e01-abc-1-review-1.v1alpha1.json` has
  the content digest `b8fd1f281f56301504cf91267121a1e9b1aab70e0755a6e14c86c9ab84cf8464`
  at that commit. The digest is the SHA-256 of the file's bytes with every CRLF replaced
  by LF.
- **The review records the finding.** Its finding F1 is claim-material and open, and it
  names this change as the owner. Its conclusion on the frozen run is `no-defect-found`,
  and it states that no rerun is justified.
- **The checkout was clean.** `git status --porcelain --untracked-files=all` printed
  nothing. The branch was created at that commit.

## The state before the change

Each command ran at `4023487e` before any file was written.

| Check | Result before the change |
|---|---|
| `tools.experiment_freeze --check` | Exit 0: 2 freeze records, every rule held |
| `tools.experiment_e01 --check` | Exit 0: 2 runs, each agrees with its own evidence |
| `tools.evidence_index --check` | Exit 0: the index is what the register and ledgers produce |
| `tools.evidence_index --gate` | Exit 0: released set `1d40b33f…` and pack `652e9051…`; current set `0271ae27…` and pack `cc8e66ec…`, after 14 post-release register changes |
| `tools.proof_dashboard --check` | Exit 0: the dashboard is what the register produces |
| `tools.generated_release --check` | Exit 0: the reference release is what its declared sources derive |
| Tag `v1.0.0` | Tag object `17c9bbd7…`, commit `718ad2e0…` |
| The default lane, `pytest -q` | 17,741 passed, none failed, 35 skipped, 14 deselected, in 11 minutes 53 seconds |

The Git blob name of each of 25 files was recorded: freeze revisions 1 and 2, the
registry, the ten files of each run directory, and the two files of the review.

## The correction

**The claim.**
`the-second-e01-static-run-recorded-its-frozen-path-identical-renders-and-every-registered-refusal`,
the claim the review read.

| | The clause in the claim's statement |
|---|---|
| Before | "no hand-written string that contains a generated workload-intent value;" |
| After | "no hand-written string that contains a generated workload-intent value of eight characters or more;" |
| E01-AC5, freeze revision 2 | "no hand-written string contains one of those generated values of eight characters or more" |

No other word of the statement changed. The statement is narrower than it was. The earlier
wording was false: the hand-written values contain the generated string values `local`
and `6`, and the digit of the generated replica count. No generated value of eight
characters or more occurs in a hand-written string; the new suite measures this again,
and it compares every generated value as text, numbers included.

**The ledger.** The ninth ledger of register changes is the fifth written after `v1.0.0`.
The number was read from the repository: the tool named eight ledgers before this change.
The ledger holds three changes:

| Change | Field | What it does |
|---|---|---|
| `q01-second-run-statement-qualifier` | The claim's `statement` | Adds the qualifier |
| `q02-second-run-correction-note` | The claim's `limitation` | Appends a dated correction after every earlier word: what the earlier wording omitted, why it was wrong, which review found it, and that no record establishes a review before the register change that added the claim |
| `q03-index-surface-reason` | The register's `nonClaimSurfaces` | Replaces the evidence index's reason, which named eight ledgers |

**Why no historical record was rewritten.** The eighth ledger added the claim with the
earlier wording. That ledger is not edited: its content digest is the one the review
recorded, `b7601323…`, and a test compares them. The ninth ledger records the earlier
wording as the value before the change. The evidence index applies the nine ledgers in
order and undoes them in reverse, so the register's history is the nine of them together,
and an edit to the earlier wording in either ledger makes the undo fail. The review page,
the review record, the validation record of `V2-S2-004-PR2`, both run directories, and
both freeze records are unchanged.

**What did not move.** The claim is `certified`, as it was. Its one record is at `C0`, as
it was, and is unchanged. The register holds 61 claims, 44 certified, and 67 evidence
records, as before. No status and no evidence level moved.

## The review gate

A register change *bears on* a run when the record it adds, or the claim or record it
changes, cites a file under the run's directory,
`docs/proof/experiments/<experiment>/runs/<run>/`. A ledger with such a change must name
one review artifact for each run in `resultReviews`. `review_gate` in
[`tools/evidence_index/core.py`](../../../tools/evidence_index/core.py) runs when the
index is built, after the released pack is recomputed. A refusal raises, so
`--check`, `--write`, and `--gate` print `MISMATCH` and exit 1.

The ninth ledger bears on run `20261003-e01-abc-1`. It references the review record by
path and by the digest `b8fd1f28…`, and the gate accepts the reference. The review record
is the one that merged: its Git blob name is the one recorded before the change.

Each refusal has a negative test in
[`tests/testing/test_result_review_gate.py`](../../../tests/testing/test_result_review_gate.py).
Each test edits a copy and asserts the refusal by its message. One control test passes
the unedited copy.

| Required refusal | Test | What is planted |
|---|---|---|
| A missing review artifact | `test_a_missing_review_artifact_is_refused` | The artifact is deleted from the copy |
| A review for another run or result | `test_a_review_of_another_run_is_refused` | The artifact's subject names the first run, and the ledger states the artifact's new digest |
| | `test_a_reference_that_names_another_run_is_refused` | The ledger's reference names the first run |
| A stale or mismatched review identity or digest | `test_a_review_artifact_with_other_content_is_refused` | The artifact is edited after the ledger named it; the ledger states another digest |
| | `test_a_review_that_no_longer_describes_the_run_is_refused` | A run file is edited, added, or removed after the review |
| | `test_a_review_of_another_freeze_record_is_refused` | The freeze record is edited |
| A result-bearing reconciliation with no review reference | `test_a_result_bearing_ledger_with_no_review_reference_is_refused` | `resultReviews` is removed, or is empty; the index is not built |
| | `test_a_later_result_bearing_ledger_with_no_review_is_refused` | A later ledger adds a claim, adds a record, sets a claim field, or sets a record field that bears on a run |

Further refusals, each with a test: an artifact of another kind, a reference outside the
experiment's `reviews/` directory, two references for one run, a reference for a run no
change bears on, and a review stated by a ledger written before the gate.

**What the gate cannot prove.** The gate reads one repository state. It does not show
that a review was committed before the register change: one commit can add both files.
It does not show that a review took place, who did it, whether it was independent, or
what it concluded. No timestamp is read, and none would be proof.

For this change only, Git history gives the order of commits. At `4023487e` the review
record has its present content, the ninth ledger does not exist, and the register holds
the earlier wording. `test_the_review_was_on_main_before_the_correction_was_written`
reads that. It skips in a clone without that commit, and a skip is not a pass. This order
is the order of the review and the correction. It is not the order of a review and the
original register change.

**The two earlier ledgers.** The ledgers that added the two E01 claims predate the gate
and name no review. The tool lists them in `PRE_GATE_LEDGER_PATHS`, the index lists them
under `summary.resultReviews.registeredBeforeTheGate`, and the gate does not check them.
The list is a record of what happened. No independent review preceded either register
change, and this change does not say one did.

## What changed

- **The register.** One statement, one limitation, and one surface reason, through the
  ninth ledger.
- **The tool.** `tools/evidence_index` names the ninth ledger, adds `review_gate`,
  `result_runs`, and `PRE_GATE_LEDGER_PATHS`, and states the gate's result in the index
  under `summary.resultReviews`.
- **Generated files.** The evidence index and the proof dashboard are regenerated.
- **Tests.** One new suite, of 39 tests. The post-release suite undoes the ninth ledger
  where it rebuilds an earlier register.
- **Pages.** The experiments page, the evidence index page, the register page, the proof
  index, the contribution guide, the README, the test inventory, and the changelog.

## Results

| Check | Result |
|---|---|
| `ruff format --check`, `ruff check`, `mypy` | Clean: 614 files formatted, no lint finding, no type error in 338 source files |
| `tools.generated_release --check` | Exit 0: the reference release is what its declared sources derive |
| `tools.experiment_freeze --check` | Exit 0: 2 freeze records, every rule held |
| `tools.experiment_freeze --changes` on revision 2 | Exit 0: no material file differs from the record |
| `tools.experiment_e01 --check` | Exit 0: 2 runs, each agrees with its own evidence. No run was started |
| `tools.evidence_index --check` | Exit 0: the index is what the register and ledgers produce |
| `tools.evidence_index --gate` | Exit 0: released `v1.0.0` set `1d40b33f…` and pack `652e9051…`, recomputed by undoing the five post-release ledgers and unchanged. Current set `0271ae27…`, unchanged, because no cited file changed. Current pack `222bc533…`, after 17 post-release register changes |
| `tools.proof_dashboard --check` | Exit 0: the dashboard is what the register produces |
| `tests/testing/test_result_review_gate.py` | 39 passed |
| The default lane, `pytest -q -rs` | 17,794 passed, none failed, 35 skipped, 14 deselected, in 14 minutes 1 second. The 35 skips are the ones the lane had before this change: host symlink privileges, POSIX signals on Windows, an absent collector image, and fixtures a test does not apply to. The 14 deselected tests are the lanes that need a cluster or a runtime |
| `git diff --check` | Clean |
| The Git blob names of the 25 files recorded before the change | Each is unchanged: freeze revisions 1 and 2, the registry, both run directories, and both review files |
| Tag `v1.0.0` | Tag object `17c9bbd7…`, commit `718ad2e0…`, as before |
| `gitleaks` | Not run: it is not installed on this host. The hosted CI job runs it over the full history |
| Hosted CI | Not read: the hosted checks of this change's pull request cannot be read from this host |

## Gates that do not apply

- **Helm and Kubernetes schema.** Not applicable: this change touches no file under
  `charts/` or `deploy/`.
- **Terraform.** Not applicable: this change touches no file under `infra/`.
- **Argo CD.** Not applicable: the repository holds no Argo CD configuration yet.
- **A result-bearing run.** Not applicable, and forbidden for this change: `--run` was not
  invoked. No part of E01 ran.

## Privacy and publicability

The diff was read for private planning text, local paths, credentials, and story
identifiers that are not merged. Files are named by repository path. The one story
identifier that is not merged is this change's own.

## What this does not establish

- **That a review preceded the register change for either E01 run.** No record
  establishes one. The correction is additive and later.
- **That the gate proves an order in time.** It proves that a matching review artifact is
  in the repository state the index is built from.
- **That the review was done by a person, or by anyone outside the project.** The review
  record states the limits of its independence.
- **That the release input deploys or serves.** E01-D did not run.
- **Any evidence level above `C0` for the E01 claims.**
- **That Sprint 2 is approved.**
