# Validation: the classification of V2-E02A (V2-S7-002-PR1)

Status: **C0 for this change, about C2 runs.** This change classifies the three runs of V2-E02A
under revision 4 of its freeze record, applies the eligibility rule, and registers one claim. It
executes no run, no fault, and no cluster command. The verdict is `eligible`, and it rests on the
failure episodes of the three runs. It states no comparison, and it authorizes nothing.

## What the change adds

- [The baseline report](../experiments/v2-e02a/baseline-report.md): each run, the classification,
  the eligibility, the permitted medians, the limitations, and the handoff of rule G3.
- [The classification record](../experiments/v2-e02a/classification.v1alpha1.json), which
  `tools/comparison_eligibility` builds from the run directories.
- [`tools/comparison_eligibility`](../../../tools/comparison_eligibility/core.py), with
  [its page](../../testing/comparison-eligibility.md) and
  [its suite](../../../tests/testing/test_comparison_eligibility.py).
- [The review of the three runs](../experiments/v2-e02a/reviews/e02a-runs-review-1.md), with one
  record of each run under [`reviews/`](../experiments/v2-e02a/reviews/e02a-1-review-1.v1alpha1.json).
- [The eleventh ledger](../testing/v2-s7-002-pr1-e02a-baseline-registration.v1alpha1.json), which adds one claim
  with one record at `C2` of each run.
- Statements in the documentation that said that the set is not classified are updated.

The change makes no GitOps switch and registers no freeze record. It edits no file of a run
directory, no correction, and no freeze record. It changes no criterion, bound, window, fault,
topology, profile, or exclusion. **It moves two pinned inputs**, and the section on the register
states which.

## The prerequisite

| Prerequisite | How it was checked | Outcome |
|---|---|---|
| `V2-S7-001-PR2` is merged | `git log origin/main` | Held: `6db8161`, pull request #160 |
| Every attempt of V2-E02A is retained | The run directories `e02a-1` to `e02a-3`. The tool refuses a gap in the identifiers. The operator read the work directory of the driver on the host, and it holds the same three identifiers. No committed file holds that read | Held |

## The frozen analysis version

Each run analysis names the commit `ff45093b2a9bf2cdbcde5fee453fbc6b64f2e53b` and the source digest
`97ce37b0e37c2ec3f67b85beaaca4f424f1264c08d3c60f8ea14a7cc5c3eb02e`. The replay ran in two places.

| Where | Command | Result |
|---|---|---|
| A clean checkout of `ff45093`, with the three run directories and their corrections copied in | `python -m tools.analysis_replay verify` on the three run directories | Each `analysis.json` replayed, code the same, revision held |
| The same checkout | `python -m tools.experiment_evidence check` on the three run directories | ok: 16 evidence files each, 14 raw, 1 correction |
| The same checkout | `python -m tools.experiment_freeze --changes` for revision 4 | `UNCHANGED` |
| The checkout of `main` at `6db8161` | `python -m tools.analysis_replay verify` on the three run directories | Each `analysis.json` replayed, code the same, revision held |

`git diff ff45093 6db8161` prints no line for the seven source packages of the analysis code, and
`git log ff45093..6db8161 -- gitops/` prints no commit.

## The decisions of this classification

Each decision is stated so that a reader can reject it.

**The verdict rests on the failure episodes.** The rule offers two conditions. The failure-episode
condition holds in 3 of 3 runs, by about 30 s, with a margin below 1 s.

**The zero-Ready condition has no single reading.** The record does not state which instant starts
an interval. The first read that gave zero started after the fault event in each run: 382 ms,
3,323 ms, and 2,588 ms after it. The read before that one, which the outer figure measures from,
started before the event in each run: 4,303 ms, 1,052 ms, and 1,676 ms before it. So the condition
holds in 3 of 3 on the first reading and in 0 of 3 on the outer start. The tool uses the outer start
for a verdict. The verdict does not depend on this decision, because the other condition holds.

**The clock margin is applied to a rule that it does not govern.** `definition.clockPolicy` governs
the instants of `definition.criterionClocks`, and those name no set rule. This classification
applies the margin anyway. It only removes a start from the count.

**The first draft read the wrong interval edge.** It took the finish of the bounding read as the
outer start. The analysis measures the outer figure from the start of that read. On the finish,
`e02a-2` would have counted, 19 ms after the event, and on the start it does not.

## The register, and the two moved pins

The story of this change owes a claim and evidence update. The register changes only through a
ledger, and the list of ledgers is in `tools/evidence_index/core.py`. That file and
`tools/evidence_index/__init__.py` are pinned inputs of each record of V2-E02A, V2-E02B, V2-E02C,
V2-E03, V2-E04, V2-E05, and V2-E06, and of the two Sprint 5 integration records, because the layout
check and the replay import them. So a ledger cannot be added without moving a pin, and the rule
of those records says that a change that moves a pin is a later revision. This change may register
no freeze record.

The repository owner was asked, with that cost stated, and chose on 2026-11-01 to register the
claim in this change. No tool reads that choice.

| What moved | Effect |
|---|---|
| `tools/evidence_index/core.py` and `__init__.py` | `python -m tools.experiment_freeze --changes` for revision 4 of V2-E02A lists these two files, and no revision classifies them. It printed `UNCHANGED` before this change |
| The three runs | None. Each run names the commit `ff45093`, each run analysis names the digest of its seven source packages, and `tools/evidence_index` is not one of them. No file of a run changed |
| A further run of V2-E02A | It refuses at P1 until a later revision classifies the two files. No further run is planned: three runs are counted |
| V2-E02B | Its revision 2 already differs from its pins, in seven files. The change of rule G3 registers revision 3 and inventories these two with the others |
| The checks | `python -m tools.experiment_freeze --check`, `tools.experiment_preregistration --check`, and `tools.analysis_preregistration --check` each pass. None reads a moved pin |

The claim is `the-e02a-baseline-runs-recorded-the-loss-of-the-one-runtime-pod`. It is certified at `C2`, on one record of each
run, and it states that requests failed. The status is a claim status and not a reliability result.
The index builds with the review gate satisfied by the three review records. The gate reads one
repository state. Those records entered the branch one commit before the ledger, and the gate does
not show that.

## Validation

| Command | Result |
|---|---|
| `python -m tools.comparison_eligibility --check` | PASSED: the record is what the runs give, and the commit `ff45093` holds the 2+1 desired state and revision 4 |
| `python -m pytest tests/testing/test_comparison_eligibility.py` | 68 passed |
| `python -m pytest tests/testing/test_test_inventory.py tests/testing/test_document_links.py tests/testing/test_experiment_freeze.py` | 1,989 passed, 1 skipped |
| `ruff check`, `ruff format --check`, and `mypy` on the new package and suite | No finding |

The first run of the inventory suite failed: its table of number words ended at ninety-nine, and
this change adds the hundredth suite with no claim. The table now holds one hundred.

## Independent review of the first commit

Two automated sessions read the commit `6abac97`. Each is another session of the assistant that
wrote it. One reviewed the result: with code of its own, importing nothing from this repository, it
judged each criterion and computed each figure from the raw files. [Its review
page](../experiments/v2-e02a/reviews/e02a-runs-review-1.md) states what it did, what it found, and
what it could not verify. It found no value that disagrees with the raw files. The other reviewed the
code, the tests, and the documents.

| Finding | Severity | What the first draft got wrong | Disposition |
|---|---|---|---|
| A figure that was not judged became a negative result | High | `decide` counted only a start after the fault, so three runs inside the margin, or with no clock bound, gave `not-eligible` and the sentence that narrows the claim of V2-E02B. The tests held that wrong result. It does not change the committed verdict | A figure that is not judged is neither held nor failed. A set is `not-decided` when such a figure could reach two runs. The record states `runsNotJudged` |
| A run document with a null member did not refuse | Medium | A null fault instant ended in an assertion, a null instant could enter the record, and an absent `environment.txt` raised an uncaught error | `_facts` refuses a null instant and a count that is not a whole number. A missing file gives no clock bound |
| Tests missed mutations | Medium | No test built a run with two episodes or two intervals, two `held` flags were not held on fewer than three runs, the limit of six starts was not enforced, the test of the medians could not fail, and the V1 test named five strings | Each is added or replaced. The V1 test reads each timing of both V1 records. The tool refuses a seventh start, and it refuses a run that two rules count differently |
| A sentence read as a statement of the records | Medium | The report said that no V1 figure is a denominator of V2-E02B, beside a statement of the record. Neither record says it | Reworded as what follows from the records |
| The start of an episode read as the start of the caller impact | Non-material | The report said that an episode starts about 30 s after the fault. The failed requests were in flight from about the fault, and the 4 s figure does not hold that time | The report states the send instants and the time in flight, and it states the limit of `B_episode` |
| The failure count equals the number of workers | Non-material | The report did not state it | The report and the record state it as a limit of `B_failures` |
| A sentence on the zero-Ready condition | Non-material | It could be read as saying that the verdict took a figure that is not held | Reworded |
| The limitation named one count | Non-material | `availableReplicas` has the same gaps | Both name it, and they state that the record does not say which fields a reading has to hold |
| The V1 definition was not named, and three statements were stale or unverifiable | Low | The report said "another definition". The inventory and one docstring still said that no run exists. The validation record named a work directory as if a reader could check it | The definition is named, and the stale text is corrected. The read is stated as an operator read |

The reviewer of the code also reported that the earlier entry of `CHANGELOG.md` says that the set
is not classified. That entry is dated by its change and stays as written.

Neither review read the commit that fixes these findings. The tests, the check, and the full lane ran
on it.

## What this does not establish

- A comparison, an improvement, or a percentage. No run of V2-E02B exists.
- That the desired state is restored. It stays at the baseline until rule G3.
- An authorization of a run of V2-E02B, of the G3 switch, or of a later sprint.
- That one runtime replica is or is not acceptable for any service.
- The cause of a failure, of a gap, or of a recovery.
- Anything about another provider, node, release, or caller workload.
