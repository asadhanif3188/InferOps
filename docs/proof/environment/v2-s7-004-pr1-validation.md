# Validation: the current E02A eligibility and evidence claims (V2-S7-004-PR1)

Status: **C0 for the change, over C2 evidence that it does not alter.** This change corrects what
the repository currently says about the three runs of V2-E02A and about the G1 and G3 switches. It
reads committed files and Git objects. It executes no run, no fault, no GitOps switch, no cluster
command, and no image rotation.

**The current E02A eligibility verdict is `not-decided`.** The repository owner chose that on
2026-11-02, after an adjudication by a session with no role in any run ruled that no source that predates the first fault
settles the meaning of `E02A-AC2`. The validity of the three runs is not established.

## What the change adds

| Item | Path |
|---|---|
| The adjudication, a committed input of the tool | [`eligibility-adjudication.v1alpha1.json`](../experiments/v2-e02a/eligibility-adjudication.v1alpha1.json) |
| The adjudicated record, which states the current verdict | [`eligibility-adjudicated.v1alpha1.json`](../experiments/v2-e02a/eligibility-adjudicated.v1alpha1.json) |
| The statement of the two switch deviations | [`v2-s7-004-pr1-switch-deviations.md`](v2-s7-004-pr1-switch-deviations.md) |
| The tool | [`tools/comparison_eligibility`](../../../tools/comparison_eligibility/core.py), with [its page](../../testing/comparison-eligibility.md) and [its suite](../../../tests/testing/test_comparison_eligibility.py) |
| This record | This page |

## What the change keeps

| Item | How it is held |
|---|---|
| The classification record | Unchanged. Revision 3 of V2-E02B binds its digest and its verdict, and the tool refuses a copy with other bytes |
| Each freeze record, and each row of the registry | Unchanged |
| The three run directories | Unchanged. Each manifest keeps the state `PASSED` |
| The corrections of each run | Unchanged, and no correction is added: the classification record lists the corrections of each run, so a new one would change what the tool builds |
| Each existing ledger | Unchanged |
| The pages of past changes | Unchanged, but for the four pages with a dated note below. [The validation of the classification](v2-s7-002-pr1-validation.md) keeps its bytes as well. It still reports `eligible`, as a record of its date, and the adjudicated record and the baseline report state the current verdict |

## The pages that this change corrects

| Page | Change |
|---|---|
| [`README.md`](../../../README.md) | The paragraph of the runs and the sentence of the switches |
| [The proof index](../README.md) | The row of the experiments, the ledger paragraph, and a dated line on the switches |
| [The experiments page](../experiments/README.md) | The adjudicated verdict, the moved-pin inventory, a dated note on each switch, and each sentence that said a change merges only with an authorization |
| [The baseline report](../experiments/v2-e02a/baseline-report.md) | A dated correction, the two readings, and each statement of validity and eligibility. It also corrects one label: "The desired state on `main` now" had been stale since the G3 merge. A ledger cites this page, so its digest moves in the evidence index, and the digest of the released pack does not |
| [The tool page](../../testing/comparison-eligibility.md) | The adjudicated record, what is enforced, and a dated line on the switches |
| [The desired-state page](../../environment/git-desired-state.md) | The sentence of the G3 switch, which also said that `main` holds the baseline |
| [The baseline profile page](../../environment/single-runtime-baseline-profile.md) | Two table cells, and a dated line on the switches |
| Six further pages that mention a switch: [the Application](../../environment/argocd-application.md), [the capacity preflight](../../environment/capacity-preflight.md), [the environment qualification](../../environment/environment-qualification.md), [the model cache storage](../../environment/model-cache-storage.md), [the runtime model cache observation](../../environment/runtime-model-cache-observation.md), and [the E02A control](../../testing/experiment-e02a-control.md), and [the architecture index](../../architecture/README.md) | A dated line on the switches. A test holds each page |
| [The G1 observation](v2-s7-001-pr2-g1-observation/observation.md) | A dated note on the authorization. No ledger cites this page, so no digest of a ledger moves |
| [The validation of the runs](v2-s7-001-pr2-validation.md) | A dated note at the top. No ledger cites this page |
| [The validation of the G3 switch](v2-s7-003-pr2-validation.md) | A dated note at the top. No ledger cites this page |
| [The validation of the G1 switch](v2-s7-003-pr1-validation.md) | A dated note at the top. No ledger cites this page |
| [The changelog](../../../CHANGELOG.md), [the testing index](../../testing/README.md), and [the test inventory](../../testing/test-inventory.md) | One entry, one row and a dated line, and the statement of the suite. The test inventory holds a second file, its JSON form |
| [The evidence index](../v1-evidence-index.md) and its JSON form, [the dashboard](../dashboard.md), and [the claim matrix](../../testing/claim-evidence-matrix.md) and its JSON form | The digests of each cited file that moved and of the current pack, the corrected claim, and the note of the ledger |

## The decisions of this change

| Question | Decision |
|---|---|
| Where the verdict goes | A new record at a new path. The tool names revision 2 of V2-E02B as the target of the classification record, so the new record states its own target, revision 3 |
| How the reason enters | A committed file with exact members, read by `decide` as `adjudicated_reason`. The file states no verdict, and `not-settled` is the only ruling it can state, so it cannot make a set eligible |
| The status string | None added. The verdict is the existing `not-decided`. Neither record has a schema file, so `schema` is a name and the tool holds each member |
| A correction of each run | None. A new correction would change the classification record. The adjudicated record states that validity is not established |
| Later story identifiers | None on a public page. The moved-pin inventory names each owner as the next revision of the record |

## The register change

[The twelfth ledger](../testing/v2-s7-004-pr1-e02a-claim-correction.v1alpha1.json), the eighth after
the release, makes 19 changes to one claim, its three records, and one surface reason.

| Change | Effect |
|---|---|
| The statement | The sentences of validity and eligibility are withdrawn, and what executed and each measured figure stay word for word |
| The limitation | Two clauses that gave the old verdict are replaced, the sentence on the review names the first review, and a dated correction is appended |
| What the claim does not establish | It now names the validity of any run, and which reading is right |
| Each of the three records | The summary, three limitations, what the record does not establish, six more cited files, and `E02A-AC2` from `met` to `not-evaluated`, a value that the schema has. The six other outcomes stay |
| The reason of the evidence index | It names twelve ledgers |

The ledger adds no claim and no record, and it moves no status and no level. The claim stays
`certified`, which says that executed records support the narrowed statement. The repository owner
decided the narrowing, and no decision states the status, so this change keeps it and says so.
The counts stay 63 claims, 46 certified, and 71 records. The cited files move from 172 to 180. The
released pack does not move, and the current pack does.

## The moved pins

A ledger is listed in the two files `tools/evidence_index/core.py` and `__init__.py`, so this change
moves both. It edits no freeze record, and no revision classifies them yet.

| Record | `--changes` before this change | After |
|---|---|---:|
| V2-E02B, revision 3 | UNCHANGED | Both files |
| V2-E03, revision 5 | UNCHANGED | Both files |
| V2-E06, revision 4 | UNCHANGED | Both files |
| V2-E02A, revision 4, V2-E02C, revision 2, V2-E04, revision 3, V2-E05, revision 2, and the other records that pin them | Both files, among others | The same files, with a new digest |

[The experiments page](../experiments/README.md#the-adjudicated-verdict-of-the-v2-e02a-set) names who
classifies them. A run under one of these records refuses until a later revision does. Each successor
is the next unused registered revision at that time, read from the registry.

## The independent review

Rounds 1 to 4 came before the ledger on this branch. They are in the same change as the ledger,
so this is not the order that the contribution guide asks for, a review merged first in a change of
its own. [The page of the review](../experiments/v2-e02a/reviews/e02a-correction-review-2.md) states each round
and each finding, and one record of each run holds them.

| Round | Outcome | What it found |
|---|---|---|
| 1, the statements | Not fit to register | A current page that still said that the runs are valid, sentences that presupposed an authorization of G1, and an adjudication that misstated its limits |
| 2, the code and the tests | No critical finding | Uncaught exceptions on malformed input, a gap logic that assumed the order of time, a reuse guard that did not cover the bound record, and five surviving mutants |
| 3, the confirmation | Not fit to register | "No source selects those two counts" was false as worded: revision 4 predates the first fault and reads them. The earlier fix had written that sentence |
| 4, a narrow re-check | Fit to register | Low findings, and no leakage |
| 5, the ledger, after it was written | Not fit to push | Each ledger change replayed to the register, and no history moved. The limitation repeated the sentence of round 3, the deviation page had narrowed a rule of the owner, and the severities of the review page did not add up |
| 6, a read of the commit that answered round 5 | Not fit to push | The replay held again, and each figure. The limitation said that a review had read wording that was written after that review, two sentences contradicted this page, and a page that mentions a switch was missing |

Each reviewer is an automated session of the same assistant. Rounds 1 to 4 came before the ledger.
Rounds 5 and 6 read the ledger after it was written, and their findings changed its wording, so no
record establishes that a review of the wording of the ledger preceded the register change. The
review records state rounds 1 to 4. No review read the commit that closes round 6. It changes
wording, and a script of the author replayed the ledger on it.

## Validation

| Command | Result |
|---|---|
| `python -m tools.comparison_eligibility --check` | PASSED: the classification is what the runs give, and the adjudicated record states the current verdict |
| `python -m tools.experiment_freeze --check` | PASSED: 35 freeze records, every rule held |
| `python -m tools.experiment_freeze --changes` of each latest record | As [the table above](#the-moved-pins) states |
| `python -m tools.experiment_preregistration --check` | PASSED: 5 experiment records and 9 superseded revisions |
| `python -m tools.analysis_preregistration --check` | PASSED: 2 analysis experiments |
| `python -m tools.evidence_index --check`, `--gate`, and `tools.proof_dashboard --check` | OK. The released pack keeps the digests that the release notes state, and the current pack moves |
| A replay of each change of the ledger on the register of `a3ed812` | Each value before the change is the value held, and the result is the register of this change |
| `ruff check .`, `ruff format --check .`, and `python -m mypy` | Passed, 453 source files |
| `git diff --check a3ed812 HEAD` | No finding |

`uv run --locked pytest` ran on `a6154f9`: 24,051 passed, 39 skipped, and 14 deselected, in 1:41:17, on
Windows. The commit after it, `be470a1`, changes the ledger, the register, and pages, in their wording,
and two lists of a test. On that commit `pytest tests/testing tests/domain/test_baseline_profile.py
tests/architecture/test_decision_authority.py` gave 10,324 passed and 3 skipped. So the default lane
did not run on the last two commits as a whole. The commit that adds this section edits this page
and the digests of the evidence index. The hosted lane has not run: it starts when the pull request
opens.

Helm, Terraform, and the Kubernetes schema gates were not run: this change edits no file that they
read. Coverage was not measured.

**The check of the reviews.** Round 2 planted 33 mutations and 31 malformed inputs. Round 3 reported
each mutant that survived round 2 killed, and each planted guard of its own but one, which a test now
holds. These figures are the reports of the reviewers. The reports are not committed.

## What this does not establish

- That any run is valid, or that any run is not valid.
- Which reading of `E02A-AC2` is right.
- That either switch was authorized before its merge.
- That the 2+2 desired state is delivered on a cluster.
- A comparison, an improvement, a reduction, or a percentage.
- An authorization of any merge, run, image rotation, or later sprint.
