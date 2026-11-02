# Validation: the current E02A eligibility and evidence claims (V2-S7-004-PR1)

Status: **C0 for the change, over C2 evidence that it does not alter.** This change corrects what
the repository currently says about the three runs of V2-E02A and about the G1 and G3 switches. It
reads committed files and Git objects. It executes no run, no fault, no GitOps switch, no cluster
command, and no image rotation.

**The current E02A eligibility verdict is `not-decided`.** The repository owner chose that on
2026-11-02, after an independent adjudication ruled that no source that predates the first fault
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
| The pages of past changes | Unchanged, but for the dated notes below. They state what was true when they were written |

## The pages that this change corrects

| Page | Change |
|---|---|
| [`README.md`](../../../README.md) | The paragraph of the runs and the sentence of the switches |
| [The experiments page](../experiments/README.md) | The adjudicated verdict, the moved-pin inventory, and a dated note on each switch |
| [The baseline report](../experiments/v2-e02a/baseline-report.md) | A dated correction, the two readings, and each statement of validity and eligibility. It also corrects one label: "The desired state on `main` now" had been stale since the G3 merge |
| [The tool page](../../testing/comparison-eligibility.md) | The adjudicated record, and what is enforced |
| [The G1 observation](v2-s7-001-pr2-g1-observation/observation.md) | A dated note on the authorization. No ledger cites this page, so no digest of a ledger moves |
| [The validation of the runs](v2-s7-001-pr2-validation.md) | A dated note on the prerequisite row. No ledger cites this page either |

## The decisions of this change

| Question | Decision |
|---|---|
| Where the verdict goes | A new record at a new path. The tool names revision 2 of V2-E02B as the target of the classification record, so the new record states its own target, revision 3 |
| How the reason enters | A committed file with exact members, read by `decide` as `adjudicated_reason`. The file states no verdict, and `not-settled` is the only ruling it can state, so it cannot make a set eligible |
| The status string | None added. The verdict is the existing `not-decided`. Neither record has a schema file, so `schema` is a name and the tool holds each member |
| A correction of each run | None. A new correction would change the classification record. The adjudicated record states that validity is not established |
| Later story identifiers | None on a public page. The moved-pin inventory names each owner as the next revision of the record |

## What this does not establish

- That any run is valid, or that any run is not valid.
- Which reading of `E02A-AC2` is right.
- That either switch was authorized before its merge.
- That the 2+2 desired state is delivered on a cluster.
- A comparison, an improvement, a reduction, or a percentage.
- An authorization of any merge, run, image rotation, or later sprint.
