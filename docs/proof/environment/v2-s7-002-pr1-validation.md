# Validation: the classification of V2-E02A (V2-S7-002-PR1)

Status: **C0 for this change, about C2 runs.** This change classifies the three runs of V2-E02A
under revision 4 of its freeze record and applies the eligibility rule. It executes no run, no
fault, and no cluster command. The verdict is `eligible`, and it rests on the failure episodes of
the three runs. It states no comparison, and it authorizes nothing.

## What the change adds

- [The baseline report](../experiments/v2-e02a/baseline-report.md): each run, the classification,
  the eligibility, the permitted medians, the limitations, and the handoff of rule G3.
- [The classification record](../experiments/v2-e02a/classification.v1alpha1.json), which
  `tools/comparison_eligibility` builds from the run directories.
- [`tools/comparison_eligibility`](../../../tools/comparison_eligibility/core.py), with
  [its page](../../testing/comparison-eligibility.md) and
  [its suite](../../../tests/testing/test_comparison_eligibility.py).
- Statements in the documentation that said that the set is not classified are updated.

The change makes no GitOps switch and registers no freeze record. It edits no file of a run
directory, no correction, and no freeze record. It changes no criterion, bound, window, fault,
topology, profile, or exclusion.

## The prerequisite

| Prerequisite | How it was checked | Outcome |
|---|---|---|
| `V2-S7-001-PR2` is merged | `git log origin/main` | Held: `6db8161`, pull request #160 |
| Every attempt of V2-E02A is retained | The run directories `e02a-1` to `e02a-3`. The tool refuses a gap in the identifiers. The work directory `.artifacts/v2-e02a/runs` on the host holds the same three identifiers, and it is not committed | Held |

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

## Validation

| Command | Result |
|---|---|
| `python -m tools.comparison_eligibility --check` | PASSED: the record is what the runs give, and the commit `ff45093` holds the 2+1 desired state and revision 4 |
| `python -m pytest tests/testing/test_comparison_eligibility.py` | 68 passed |
| `python -m pytest tests/testing/test_test_inventory.py tests/testing/test_document_links.py tests/testing/test_experiment_freeze.py` | 1,989 passed, 1 skipped |
| `ruff check`, `ruff format --check`, and `mypy` on the new package and suite | No finding |

The first run of the inventory suite failed: its table of number words ended at ninety-nine, and
this change adds the hundredth suite with no claim. The table now holds one hundred.

## What this does not establish

- A comparison, an improvement, or a percentage. No run of V2-E02B exists.
- That the desired state is restored. It stays at the baseline until rule G3.
- An authorization of a run of V2-E02B, of the G3 switch, or of a later sprint.
- That one runtime replica is or is not acceptable for any service.
- The cause of a failure, of a gap, or of a recovery.
- Anything about another provider, node, release, or caller workload.
