# The controlled baseline of V2-E02A

Status: **C2, on one provider. The set is classified, and the baseline is eligible for the
comparison with V2-E02B.** `V2-S7-002-PR1` wrote this page. It reads the three runs of revision 4
of [the freeze record](freeze-r4.v1alpha1.json). No run executed in that change.

[The classification record](classification.v1alpha1.json) states each figure of this page, and
`python -m tools.comparison_eligibility --check` builds that record again from the run directories.
[The tool page](../../../testing/comparison-eligibility.md) states what the tool holds.

## The result

- **Three runs started, and three are counted.** Each is `PASSED`. No run is `REFUSED`,
  `INCONCLUSIVE`, `ABORTED`, or `FAILED`, so no run has an exclusion reason.
- **`PASSED` is not a reliability pass here.** V2-E02A is a characterization with validity
  criteria alone. The state says that a run is valid. Two requests failed in each run.
- **The baseline is eligible.** In each of the three runs, a failure episode starts about 30 s
  after the `fault-injection-started` event. The rule asks for two of the three.
- **This page states no comparison.** No run of V2-E02B exists. An eligibility verdict does not
  authorize a run of V2-E02B.

## Each run

Each run has one fault: the control deleted the one runtime pod once while RP-1 ran. Each run
executed under revision 4, at the commit `ff45093b2a9bf2cdbcde5fee453fbc6b64f2e53b`, with
2 API replicas and 1 runtime replica, on the docker-desktop provider with one node, on 2026-10-31.

| Run | State | Counted | Exclusion | Fault started | First failed request completed | Requests failed since the fault | Caller failure episode | Largest time between two successes | Stabilized recovery after the fault |
|---|---|---|---|---|---|---:|---:|---:|---:|
| [`e02a-1`](runs/e02a-1/result.md) | `PASSED` | Yes | None | 13:41:35.149Z | 13:42:05.876Z | 2 | 4,276 ms | 29,896 ms | 96,469 ms |
| [`e02a-2`](runs/e02a-2/result.md) | `PASSED` | Yes | None | 14:47:01.042Z | 14:47:31.808Z | 2 | 3,682 ms | 30,427 ms | 94,752 ms |
| [`e02a-3`](runs/e02a-3/result.md) | `PASSED` | Yes | None | 15:47:24.552Z | 15:47:55.243Z | 2 | 4,065 ms | 29,893 ms | 96,808 ms |

| Run | Requests started, whole record | Failed of completed, in the window | HTTP 500 | Runtime at zero Ready endpoints, inner and outer | API at zero Ready endpoints | Replacement pod, creation to first Ready, to one second | Clock bound |
|---|---:|---:|---:|---:|---:|---:|---:|
| `e02a-1` | 717 | 2 of 365 | 2 | 17,342 ms, 26,813 ms | 0 intervals | 21 s | 817 ms |
| `e02a-2` | 700 | 2 of 366 | 2 | 14,837 ms, 23,792 ms | 0 intervals | 21 s | 979 ms |
| `e02a-3` | 615 | 2 of 342 | 2 | 14,949 ms, 23,448 ms | 0 intervals | 20 s | 675 ms |

The two failed requests of each run have the code `internal-error` and the condition
`runtime-error-response`. The stabilized recovery is a rule of the analysis. It is not a measured
recovery of the service. This page states no cause of a failure, a gap, or a recovery, and no
cause of the differences between the runs.

## The classification

| Check | How it was done | Outcome |
|---|---|---|
| Each attempted run is retained | The run identifiers are 1 to 3 with no gap. The tool refuses a gap, because the driver spends one identifier for each start | Held: 3 of the 6 starts that one revision allows |
| Each run has a state that the outcome rules give | The result page of each run states each criterion. The review of the set is in [the validation record](../../environment/v2-s7-002-pr1-validation.md) | Held: `PASSED`, because each criterion is of kind validity and each held |
| Each run names revision 4 | The manifest names the record, the revision, and the digest. The tool refuses another record | Held: `3630fbf2…` |
| Each run analysis is reproduced with its frozen analysis version | `python -m tools.analysis_replay verify` ran on the three run directories in a clean checkout of `ff45093`, the commit that each run analysis names, and on this branch | Each is reproduced byte for byte. The source digest is `97ce37b0…` in both |
| The executing commit holds the 2+1 desired state | The check reads the objects of the clone at `ff45093`, not the working tree | Held: `f7eaab84…` and `e0b2507c…`, and the record has its digest there |
| Each correction names the manifest of its run | The tool compares the two | Held: one correction of each run |

No file of a run directory was edited for this classification. Each correction stays
[apart from its run](corrections/e02a-1/correction-1.v1alpha1.json), under `corrections/`.

## The comparison eligibility

Revision 4 states the rule in `definition.setRules`. At least 2 of the 3 runs must show one of
two conditions. The aggregate command states neither, so the tool reads them from the run
analysis of each run.

| Condition | `e02a-1` | `e02a-2` | `e02a-3` | Runs showing it | Held |
|---|---:|---:|---:|---:|---|
| A failure episode starts at or after the fault event: the start, after the event | 30,727 ms | 30,766 ms | 30,691 ms | 3 of 3 | **Yes** |
| The margin of that order: the clock bound plus 1 ms | 818 ms | 980 ms | 676 ms | | |
| A zero-Ready interval starts after the fault event, read at the first reading that gave zero: its start, after the event | 382 ms | 3,323 ms | 2,588 ms | 3 of 3 | Yes, on this reading |
| The same interval, read at its outer start: the outer start, after the event | -4,303 ms | -1,052 ms | -1,676 ms | 0 of 3 | No, on this reading |

**The verdict is `eligible`, and it rests on the failure episodes alone.** The start of each
episode is on the node clock, and the event is on the host clock. The clock policy of the record
does not declare the set rules. This classification applies its margin all the same, and each
start is after the event by more than the margin.

**The zero-Ready condition does not decide the verdict.** The record does not state which instant
starts an interval. A reading before the fault reported the Ready endpoint, and the first reading
after the fault reported none. The state changed between the two. In each run the first of those
two reads started before the event, so the readings do not exclude a change before the event. The
first reading that gave zero started after the event in each run. This classification states both
figures. It takes the stricter one for the verdict, and that one is not held.

**The baseline comparison record states another thing.** Its `experimentEligibility` stays
`not-established`. That record compares committed inputs, and it reads no run. It is pinned,
and this classification does not change it.

## The permitted statistics

`python -m tools.analysis_replay aggregate` states the median of three counted runs for its
registered metrics. This page states those medians and no other.

| Metric | Median of the three |
|---|---:|
| `requests-failed-since-fault` | 2 |
| `requests-failed-in-window` | 2 |
| `caller-failure-episode-ms` | 4,065 ms |
| `max-success-gap-ms` | 29,896 ms |
| `stabilized-since-fault-started-ms` | 96,469 ms |

The aggregate command does not state the zero-Ready intervals, so this page states no median of
them. Three runs do not support a confidence interval or a statistical significance, and this
page states neither. No figure here is compared with a bound.

## The figures that a later comparison reads

The record of V2-E02B names two medians of this baseline.

| Figure of the record of V2-E02B | Metric | Value | Basis |
|---|---|---:|---|
| `B_failures` | `requests-failed-since-fault` | 2 | Above zero |
| `B_episode` | `caller-failure-episode-ms` | 4,065 ms | Above zero |

**No percentage exists.** Neither figure is zero, so the rule that no percentage is computed over
a zero baseline does not apply to this set. The tool states that case for a zero median and for a
median that the aggregate does not state, and tests hold both. No percentage is stated here,
because no run of V2-E02B exists. V2-E02B computes an improvement after its own runs, under its
own record.

## The V1 pod-loss evidence stays apart

The record of V2-E02A keeps the controlled baseline apart from the V1 pod-loss evidence. No V1
figure is a value of V2-E02A, and no V1 figure is a denominator of V2-E02B.

Two V1 records state a caller-visible outage:
[31,960 ms](../../serving/v1-s4-006-pr1-recovery-record.v1alpha1.json) and
[2,832 ms](../../environment/v1-s5-001-pr2-recovery-record.v1alpha1.json). Each is one pod lost
once, under a V1 tool, a V1 load profile, and a V1 release with one replica of the API and of the
runtime. That tool measures the outage by another definition. The figures of this page are not
comparable with them, and this page draws no conclusion from any difference.

## Known limitations

- **The state of each run rests on a reading that the owner approved after the evidence was
  read.** `E02A-AC2` limits the time between readings of a stream that have a value. The record
  does not state whether a reading with one omitted field has a value. The repository owner
  approved the stream reading on 2026-10-31. No tool reads that approval. On the readings of the
  runtime `readyReplicas` count alone, each run would be `INCONCLUSIVE`, no run would be counted,
  and the verdict above would not exist. V2-E02B has the same criterion, so a later record states
  this reading or does not, and this page does not decide that.
- **The model file of a replacement pod was not compared directly.** The procedure read the model
  verification log of the first runtime pod alone. The evidence for each replacement pod is
  indirect, and each result page states it.
- **The host paged in each run.** The available physical memory was low, and the page file was
  in use. The operator read these figures, and no criterion reads them. The requests started
  differ between the runs: 717, 700, and 615. This page does not establish whether paging changed
  a figure.
- **Two digests of each manifest are of the wrong kind.** The correction of each run states the
  right values. No figure of this page reads them.
- **The clock bound applies between its two readings only under an assumption.** The offset stays
  inside the bound between them. No reading tests that.
- **One provider, one node, one Kubernetes version, one release, one model, one caller workload.**
  A result is bounded to that execution.

## The handoff of rule G3

The `handoff` member of [the classification record](classification.v1alpha1.json) states this
inventory for `V2-S7-003-PR2`.

| Item | Value |
|---|---|
| The last run | `e02a-3`, `PASSED`, finished at 2026-10-31T16:42:32Z |
| Its executing commit | `ff45093b2a9bf2cdbcde5fee453fbc6b64f2e53b`, the merge of the G1 switch |
| Its manifest and its run analysis | `9e1e8f12…` and `547bda5e…` |
| The governing record | Revision 4, `3630fbf2…`, which stays the authority for these three runs |
| The merge that holds the run evidence | `6db8161`, pull request #160 |
| The desired state on `main` now | 2 API + 1 runtime: `f7eaab84…` and `e0b2507c…` |
| The desired state that rule G3 restores | 2 API + 2 runtime, as revision 2 of V2-E02B states: `810b4b27…` and `6a1304a8…` |

Rule G3 restores the two files in one change merged into `main`, before the first V2-E02B run. That
change needs the explicit authorization of the repository owner. This page does not give it, and
this change makes no switch and registers no freeze record. No row of the classification record
changes when `main` returns to the target: it reads no desired state of the working tree.

## What this establishes, and what it does not

For three runs on one provider, this page states what the caller, the endpoints, and the pods
showed when the one runtime pod was deleted while RP-1 ran, and that the set meets the eligibility
rule of revision 4.

It does not establish:

- a comparison, an improvement, or a percentage;
- that one runtime replica is or is not acceptable for any service;
- that the desired state is restored;
- an authorization of a run of V2-E02B, of the G3 switch, or of a later sprint;
- node failure, overload, sustained capacity, or production availability;
- the cause of a failure, of a gap, or of a recovery;
- anything about another provider, node, release, or caller workload.
