# V2-S2-005-PR1 validation

Date: 2026-10-03

What this change publishes, what it leaves unchanged, and the checks run over the
repository. The change publishes one document set:
[the independent review of the second E01 static run](../experiments/v2-e01/reviews/20261003-e01-abc-1-review-1.md)
and [its machine-readable record](../experiments/v2-e01/reviews/20261003-e01-abc-1-review-1.v1alpha1.json).

The change executed no experiment part. It contacted no cluster, runtime, registry, or
model, and nothing was provisioned or published. It adds no evidence record and no claim.

## Why this change exists

The second collective review of Sprint 2 closed its two earlier findings and returned
*blocked* on one more, as reported to the author; no file in this repository records that
review. The finding: the independent review documented for `V2-S2-004-PR2` read a commit
that already held the register change, so the order "review, then register" is not
established for the second E01 run.

A first attempt at one corrective change began with a fresh independent review. That
review found the run without defect and found one claim-material defect in the register's
wording. The attempt stopped before it edited a file. The work was then divided in two:

1. **This change** publishes the review, with its finding, and corrects nothing.
2. **`V2-S2-005-PR2`** is to start after this change merges. It owns the additive
   correction of the claim.

If this change merges before the correction, Git history will show the review record on
`main` before the correction. It will not show a review before the original register
change, and this change does not say it does.

## Eligibility, checked before the change

- **What it builds on is merged.** `git pull origin main` left `main` at
  `3f08f4393167a0c49e63f4f1d968250d54f48017`, the merge of pull request 114, which is
  `V2-S2-004-PR2`. `a5b6a5db2011a68a3f27acdeaa8186c226bfedb4`, the merge of pull request
  113, which is `V2-S2-004-PR1`, is its first parent.
- **The checkout was clean.** `git status --porcelain --untracked-files=all` printed
  nothing. The branch was created at that commit.
- **The reviewed revision is the base.** The review read `3f08f439`. No commit separates
  the reviewed revision from this change's first commit.

## The state before the change

Each command ran at `3f08f439` before any file was written.

| Check | Result before the change |
|---|---|
| `tools.experiment_freeze --check` | Exit 0: 2 freeze records, every rule held |
| `tools.experiment_freeze --changes` on revision 2 | Exit 0: no material file differs |
| `tools.experiment_freeze --changes` on revision 1 | Exit 1: 4 files differ, the ones revision 2 classifies |
| `tools.experiment_e01 --check` | Exit 0: 2 runs, each agrees with its own evidence |
| `tools.evidence_index --check` | Exit 0: the index is what the register and ledgers produce |
| `tools.evidence_index --gate` | Exit 0: released set `1d40b33f…` and pack `652e9051…`; current set `0271ae27…` and pack `cc8e66ec…` |
| `tools.proof_dashboard --check` | Exit 0: the dashboard is what the register produces |
| `tools.generated_release --check` | Exit 0: the reference release is what its declared sources derive |
| Tag `v1.0.0` | Tag object `17c9bbd7…`, commit `718ad2e0…` |

**The identities, computed again.** The content digests of freeze revision 1
(`fcb19502…`), freeze revision 2 (`198f60b5…`), the registry (`6c357892…`), and each of the
ten files of both run directories were computed from the working tree. Each equals the
value the review reports, and the review page lists all 23.

**The claim wording, compared again.** E01-AC5 in freeze revision 2 says "no hand-written
string contains one of those generated values of eight characters or more". The second-run
claim's statement in the register says "no hand-written string that contains a generated
workload-intent value". The claim omits `of eight characters or more`. A search of the
hand-written values for every generated workload-intent string value found three matches
shorter than eight characters, and none of eight or more:

| Hand-written value | Generated value it contains |
|---|---|
| `api.image.repository`, `localhost/inferops-api` | `local`, from `telemetry.deploymentEnvironment` |
| `api.image.digest`, `sha256:7961c9f9…` | `6`, from `runtime.resources.limits.cpu` |
| `model.integrity.verifyOnStart`, `sha256` | `6`, from `runtime.resources.limits.cpu` |

## The review

The review ran once, read-only, at `3f08f439`, on 2026-10-03 from 06:49:45Z to 06:55:26Z as
the reviewer reported.
Its report was held outside the repository until this change. This change did not run it
again: `main` had not moved, and no reviewed file had changed. A second review, briefed
after the finding was known, would not have been independent of it.

**How the report was transcribed.** The review page restates the reviewer's report in this
repository's style. The author of this record kept every finding, verdict, digest, command,
and exit status. Two things were changed:

- The reviewer's scratch script names are replaced by what each script did.
- A local branch name and a scratch directory path are removed.

**What the author added, marked as the author's on the page.** That the first run has the
same order of review and registration; that the claim's statement is also copied in the
evidence index and in the eighth ledger; and the disposition of each finding.

## What changed

- **The review record.** Two new files under
  [`docs/proof/experiments/v2-e01/reviews/`](../experiments/v2-e01/reviews/20261003-e01-abc-1-review-1.md):
  the page and the machine-readable record. The record's kind is `ExperimentResultReview`.
  No schema or tool reads that kind yet; the suite below is its only check.
- **A new suite.** [`tests/testing/test_experiment_review.py`](../../../tests/testing/test_experiment_review.py),
  58 tests in the default lane. It holds the record to the run's ten files, the manifest,
  the freeze record, and the registry, and it repeats the search behind the finding. It
  does not read the register.
- **The documents.** The experiments page gains a section on the review. The proof index,
  the test inventory, and the changelog name the new files. The test inventory's count of
  suites that defend no claim said sixty-three while the table held sixty-four rows; it now
  says sixty-five, with the drift recorded.

## What was not touched

`git diff --stat 3f08f439` lists only the files above and this record. In particular, each of these has
the Git blob it had at `3f08f439`:

- **The register:** `docs/testing/claim-evidence-matrix.v1alpha2.json` and
  `docs/testing/claim-evidence-matrix.md`. The second-run claim's statement, status, and
  record are as they were, so the statement still carries the clause the review found.
- **Every ledger** under `docs/proof/testing/`, the evidence index, its page, and the
  dashboard. This change adds no ledger.
- **Freeze revision 1, freeze revision 2, and the registry.**
- **Both run directories,** each of its ten files.
- **Every pinned input of revision 2.** `--changes` over revision 2 reports none after this
  change.
- **The validation records of `V2-S2-003-PR2` and `V2-S2-004-PR2`.** The review's finding
  about the opening sentence of the second one is recorded and not corrected: the evidence
  index binds that page by digest, and a change to it is a register change.
- **The released `v1.0.0` pack, the release notes, the tag, and every accepted decision.**

## Commands

```sh
uv run --locked --offline --no-sync ruff format --check .
uv run --locked --offline --no-sync ruff check .
uv run --locked --offline --no-sync python -m mypy
uv run --locked --offline --no-sync python -m tools.generated_release --check
uv run --locked --offline --no-sync python -m tools.experiment_freeze --check
uv run --locked --offline --no-sync python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json
uv run --locked --offline --no-sync python -m tools.experiment_e01 --check
uv run --locked --offline --no-sync python -B -m tools.evidence_index --check
uv run --locked --offline --no-sync python -B -m tools.evidence_index --gate
uv run --locked --offline --no-sync python -m tools.proof_dashboard --check
uv run --locked --offline --no-sync python -m pytest -q tests/testing/test_experiment_review.py
uv run --locked --offline --no-sync python -m pytest -q -rs
git diff --check
```

All ran from Git Bash on Windows.

## Results

| Check | Result |
|---|---|
| `ruff format --check`, `ruff check`, `mypy` | Clean: 613 files formatted, no lint finding, no type error in 337 source files |
| `tools.generated_release --check` | The reference release is what its declared sources derive |
| `tools.experiment_freeze --check` | 2 freeze records, every rule held |
| `tools.experiment_freeze --changes` on revision 2 | No material file differs from the record |
| `tools.experiment_e01 --check` | 2 runs, each agrees with its own evidence. No run was started |
| `tools.evidence_index --check` | The index is what the register and ledgers produce. The index was not written |
| `tools.evidence_index --gate` | Exit 0; released `v1.0.0` set `1d40b33f…` and pack `652e9051…`; current set `0271ae27…` and pack `cc8e66ec…`. All four equal the values before the change |
| `tools.proof_dashboard --check` | The dashboard is what the register produces. The dashboard was not written |
| `tests/testing/test_experiment_review.py` | 41 passed at the first commit, and 58 after the review's fixes |
| The default lane, `pytest -q -rs` | 17,724 passed, none failed, 35 skipped, 14 deselected, in 12 minutes 14 seconds. The 35 skips are the ones the lane had before this change: host symlink privileges, POSIX signals on Windows, an absent collector image, and fixtures a test does not apply to. The 14 deselected tests are the lanes that need a cluster or a runtime |
| The same gates and the default lane, after the review's fixes | Every gate above gave the same result. 17,741 passed, none failed, 35 skipped, 14 deselected, in 10 minutes 24 seconds |
| `git diff --check` | Clean |
| `git diff --quiet 3f08f439` over the register, the ledgers, the index, the dashboard, both freeze records, the registry, both run directories, the release records, the accepted decisions, `charts/`, `infra/`, `src/`, and `tools/` | Exit 0: no difference |
| `gitleaks` | Not run: it is not installed on this host. The hosted CI job runs it over the full history |
| Hosted CI | Not read: the hosted checks of this change's pull request cannot be read from this host |

The checks ran with `uv run --locked --offline --no-sync`, so `uv` did not change the
environment.

## What the independent review found

A second reviewing session read the first commit of this change, `b20a815`, against the
files and Git, read-only. It is a session of the same automated assistant, given a brief
and nothing else; it is not a person and not anyone outside the project. It found no
change to the register, a ledger, the index, the dashboard, a freeze record, the registry,
or a run directory, and it confirmed every digest, commit, timestamp, line number, and
count it could check. It found these, and each is what the first commit got wrong:

| Finding | What the first commit said | Correction |
|---|---|---|
| The run's E01-AC5 verdict was stated as a fact | "E01-AC5, as frozen, held", and "the run's verdict on E01-AC5 is right" | The review confirmed E01-AC5 only in part. The page and the record now say the review found nothing against the verdict, and repeated the eight-character search |
| A prediction was stated as a fact | "A new run would write the same evidence" | A new run would record other times. The texts now say a new run would answer the same frozen criteria |
| "Three matches" was true for string values only | Three matches under a literal reading of the claim | The replica count is the integer `1`, and the digit occurs in two hand-written strings, one of them not in the table. The page and the record name the case and say who found it. The texts say "string value" |
| The reviewer's relation to the author was not stated | "One automated reviewing session, started by the maintainer" | The reviewer is a separate session of the same automated assistant that co-authored the run's change and this one, and the session that prepared this change started it. The page and the record say so |
| A negative was asserted | "That a review preceded the register change for this run. It did not." | "No record establishes one." |
| Future events were in the present tense | "`V2-S2-005-PR2` narrows the claim", "Git history then shows" | "is to narrow", "will show, if this change merges before the correction" |
| Reported times read as proven | The review's times without a source, on this page and in the first commit's message | "as the reviewer reported". The commit message of `b20a815` is not rewritten; it still gives the times without that qualifier |
| Statements about things outside the repository had no marker | The experiment procedure, the second collective review, and the brief | Each now says that no file in this repository records it |
| "That review preceded the merge" was unhedged | A statement about the review `V2-S2-004-PR2` documents | "By the same account" |
| "Sound" is an evaluative word with no definition | "Is the frozen run sound?", and the record's key `frozenRunSoundness` | "Did the review find a defect in the frozen run?", and `frozenRun` |
| The record and the page disagreed on one list | Five items in the record's `doesNotEstablish`, six on the page | Six in both, and a test compares the counts |
| This page's list of changed files omitted itself | "lists only the files above" | "the files above and this record" |
| Two sentences in other documents read wrongly | A misplaced "and" in the proof index, and a sentence in the test inventory placed before an older one | Both moved |
| One test checked less than its name said | The three digests of the register, the ledger, and the index were checked for form only | The ledger's digest and its copy of the clause are now compared with the file. The register's and the index's are still form-checked only, because both files change when the clause is corrected; the suite and the inventory say so |
| Cheap checks were missing | The first run's digests on the page, and each finding's severity on the page, had no test | Both have one. The suite has 58 tests, not 41 |

The second review could not verify, from the repository: that the first review took
place, its times, its commands, and its brief; the second collective review; the lane
figures and the mypy count on this page; and that each check before the change ran before
any file was written. Each is a statement of the author or of the reviewer, and this page
or the review page marks it so.

One incident: a search command of the second review crashed and left a dump file in the
repository root. The reviewing session deleted it. It was never tracked.

## Gates that do not apply

- **Helm and Kubernetes schema.** Not applicable: this change touches no file under
  `charts/` or `deploy/`.
- **Terraform.** Not applicable: this change touches no file under `infra/`.
- **Argo CD.** Not applicable: the repository holds no Argo CD configuration yet.
- **A result-bearing run.** Not applicable, and forbidden for this change: `--run` was not
  invoked.

## Privacy and publicability

The diff was read for private planning text, local paths, credentials, and later story
identifiers. The review page names files by repository path. The one story identifier that
is not merged is `V2-S2-005-PR2`, the second change of this story.

## What this does not establish

- **That a review preceded the register change for either E01 run.**
- **That the second-run claim's statement is correct.** One clause is not, and it is
  unchanged.
- **That the review was done by a person outside the project.** It was not.
- **That a register change now requires a review record.** No check enforces that.
- **That the release input deploys or serves.** E01-D did not run.
- **That Sprint 2 is approved.**
