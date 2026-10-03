# V2-S2-005-PR2 validation

Date: 2026-10-03

What this change corrects, what it adds, what it leaves unchanged, and the checks run over
the repository. The change does two things:

1. It narrows one statement in the claim and evidence register, through
   [a ninth ledger of register changes](../testing/v2-s2-005-pr2-e01-claim-correction.v1alpha1.json).
2. It adds a gate to `tools/evidence_index`: a ledger whose changes bear on an experiment
   run must reference a review artifact of that run.

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

A register change *bears on* a run when the claim or record it adds, or the claim or
record it changes, names a file under the run's directory, in any field, before or after
the change. The directory is
`docs/proof/experiments/<experiment>/runs/<run>/`. A ledger with such a change must name
one review artifact for each run in `resultReviews`. `review_gate` in
[`tools/evidence_index/core.py`](../../../tools/evidence_index/core.py) runs when the
index is built, after the released pack is recomputed. A refusal raises, so `--check`
and `--write` print `MISMATCH` and exit 1, as does `--gate` where it reports a freeze.
`--gate` does not build the index where a blocker stands or no freeze is declared.

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
| | `test_a_review_that_names_a_file_other_than_the_runs_freeze_record_is_refused` | The artifact names another file as the freeze record, with that file's true digest |
| | `test_a_review_whose_run_identifier_or_path_alone_differs_is_refused` | Only the identifier, or only the path, names another run |
| A result-bearing reconciliation with no review reference | `test_a_result_bearing_ledger_with_no_review_reference_is_refused` | `resultReviews` is removed, or is empty; the index is not built |
| | `test_a_later_result_bearing_ledger_with_no_review_is_refused` | A later ledger adds a claim, adds a record, sets a claim field, or sets a record field that bears on a run; names the run in a field other than `evidenceRefs`; or removes the citation |
| | `test_a_register_change_of_an_unknown_operation_is_refused` | The claim changes are renamed to an operation the gate does not know, and the reference is removed |

Further refusals, each with a test: an artifact of another kind, an artifact that is not
JSON, a reference that is not a plain path under the experiment's `reviews/` directory,
a malformed reference row, two references for one run, a reference for a run no change
bears on, and a review stated by a ledger written before the gate. One test runs the
command and requires `MISMATCH` and exit 1.

**What the gate cannot prove.** The gate reads one repository state. It does not show
that a review was committed before the register change: one commit can add both files.
It does not show that a review took place, who did it, whether it was independent, or
what it concluded. No timestamp is read, and none would be proof.

The gate does not bind a review to a change. One review artifact of a run satisfies every
later ledger that bears on that run, including a change the review did not read. The
review this change references read the earlier wording, not the corrected one.

For this change only, Git history gives the order of commits. At `4023487e` the review
record has its present content, the ninth ledger does not exist, and the register holds
the earlier wording. `test_the_review_was_on_main_before_the_correction_was_written`
reads that. It skips in a clone without that commit, and a skip is not a pass. This order
is the order of the review and the correction. It is not the order of a review and the
original register change.

**The two earlier ledgers.** The ledgers that added the two E01 claims predate the gate
and name no review. The tool lists them in `PRE_GATE_LEDGER_PATHS`, the index lists them
under `summary.resultReviews.registeredBeforeTheGate`, and the gate does not check them.
The list is a record of what happened. No record establishes an independent review
before either register change, and this change does not say one preceded. The gate does
not check these two ledgers, whatever they hold. A test holds each to its content digest.

## What changed

- **The register.** One statement, one limitation, and one surface reason, through the
  ninth ledger.
- **The tool.** `tools/evidence_index` names the ninth ledger, adds `review_gate`,
  `result_runs`, and `PRE_GATE_LEDGER_PATHS`, and states the gate's result in the index
  under `summary.resultReviews`.
- **Generated files.** The evidence index and the proof dashboard are regenerated.
- **Tests.** One new suite, of 63 tests. The post-release suite undoes the ninth ledger
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
| `tests/testing/test_result_review_gate.py` | 39 passed at the first commit, and 63 after the review's fixes |
| The default lane, `pytest -q -rs`, at the first commit | 17,794 passed, none failed, 35 skipped, 14 deselected, in 14 minutes 1 second. The 35 skips are the ones the lane had before this change: host symlink privileges, POSIX signals on Windows, an absent collector image, and fixtures a test does not apply to. The 14 deselected tests are the lanes that need a cluster or a runtime |
| The same gates and the default lane, after the review's fixes | Every gate above gave the same result. 17,818 passed, none failed, 35 skipped, 14 deselected, in 13 minutes 59 seconds |
| `git diff --check` | Clean |
| The Git blob names of the 25 files recorded before the change | Each is unchanged: freeze revisions 1 and 2, the registry, both run directories, and both review files |
| Tag `v1.0.0` | Tag object `17c9bbd7…`, commit `718ad2e0…`, as before |
| `gitleaks` | Not run: it is not installed on this host. The hosted CI job runs it over the full history |
| Hosted CI | Not read: the hosted checks of this change's pull request cannot be read from this host |

## What the independent review found

A reviewing session read the first commit of this change, `22d3211`, against the files
and Git, read-only. It is a session of the same automated assistant that wrote the
change, given a brief and nothing else; it is not a person and not anyone outside the
project. The brief is not committed. It found the correction exact: the statement gained
only the qualifier, the corrected clause is true of the committed run, no earlier
ledger, freeze record, run directory, or review file changed, and the counts did not
move. It found these, and each is what the first commit got wrong:

| Finding | What the first commit did or said | Correction |
|---|---|---|
| A renamed operation escaped the gate | The gate read four operation names and ignored any other. The register tools apply any other name as a claim-field change, so a claim could change with no review | The gate refuses an operation it does not know. A test renames the operations and requires the refusal |
| A change that removed the run citation escaped the gate | The gate read a changed claim or record from the final register only | The gate also reads the values before and after the change |
| Only `evidenceRefs` was read | A record that named a run in another field did not bear on it | The gate reads every string of the claim or record |
| The freeze check accepted any file | Any existing file with a matching digest passed as the freeze record, a path outside the repository included. The pages said "the committed freeze record" | The artifact must name the freeze record the run's manifest names, as a plain path under the experiment's directory |
| A malformed reference row gave a traceback | A missing member raised `KeyError`, and the command printed no `MISMATCH` | A row that is not exactly the three strings is refused with `ValueError`. A test runs the command |
| A reference path with a backslash was accepted | Only `/`-separated `..` segments were checked | A reference with a backslash, or with an empty, `.`, or `..` segment, is refused |
| The review is bound to the run, not to the change | No page said that one review satisfies every later ledger for the run | The experiments page, this page, and the tool say so |
| The two earlier ledgers are exempt as a whole | The first E01 ledger's content was not pinned by the new suite | The suite pins the content digest of both |
| The command's description was not true of every mode | "Every mode but `--gate` over an open gate builds the index" | `--gate` builds the index only where it reports a freeze. The tool and the pages say so |
| "States every refusal and every limit" was not true | The experiments page's table omitted four refusals | The table has the rows, and the other pages say "lists" |
| A negative was asserted | "No review preceded" either earlier register change, in the tool, the index, two pages, and the changelog | "No record establishes a review before either" |
| "Proves" was used without a definition | "It proves that a matching review artifact is in the repository state" | "It shows that a review artifact of that run, with the digest the ledger states and the run's present file digests, is in the repository state" |
| Predictions were stated as facts | "until this correction merged", and "the gate refuses it for E01-D" | "until this correction merges", and "would refuse it for a record that names a file under another run directory" |
| A count was true for string values only | The changelog said three hand-written strings contain a shorter generated value | "a shorter generated string value". The replica count's digit occurs in two strings as well |
| Two headings implied an order | The changelog entry's title, and the first commit's subject, said a review is required "before" a register change | The changelog title says a register change must reference a review artifact. The commit message of `22d3211` is not rewritten |
| One test did less than its name said | The Git-history test read the merge commit and did not check that it is in this change's history | It checks that the merge is an ancestor of `HEAD` |

Limits the review named that remain, each stated on the experiments page: the gate
matches a path in the repository's normal form only, it follows a symbolic link, and a
path in another letter case resolves on a host whose file system ignores case.

The review could not verify, from the repository: the lane figures and the linter and
type-checker counts on this page, the table of the state before the change apart from
the earlier pack digest, that the checkout was clean, and the 25 recorded blob names. It
did not run the freeze, E01, or generated-release checks. Each is a statement of the
author.

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
- **That the gate shows an order in time.** It shows that a review artifact of that run,
  with the digest the ledger states and the run's present file digests, is in the
  repository state the index is built from.
- **That a review read the change it supports.** The gate binds a review to a run.
- **That the review was done by a person, or by anyone outside the project.** The review
  record states the limits of its independence.
- **That the release input deploys or serves.** E01-D did not run.
- **Any evidence level above `C0` for the E01 claims.**
- **That Sprint 2 is approved.**
