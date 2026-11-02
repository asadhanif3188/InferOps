# The controlled baseline of V2-E02A

Status: **C2, on one provider. The set is classified, and the current eligibility verdict is
`not-decided`.** `V2-S7-002-PR1` wrote this page, and `V2-S7-004-PR1` corrected its statements
of validity and eligibility on 2026-11-02. It reads the three runs of revision 4 of
[the freeze record](freeze-r4.v1alpha1.json). No run executed in either change.

> **Correction, 2026-11-02.** Until `V2-S7-004-PR1` this page gave the verdict of the
> classification record as the current verdict, and it read each state as a statement of
> validity. An adjudication by a session with no role in any run ruled that no source that predates the first fault
> settles the meaning of `E02A-AC2`, and the repository owner chose the verdict `not-decided`.
> [The adjudicated record](eligibility-adjudicated.v1alpha1.json) states it, with what each
> reading of the criterion gives on the raw streams. The measured figures of this page stand.

[The classification record](classification.v1alpha1.json) states each figure of this page, and
`python -m tools.comparison_eligibility --check` builds that record again from the run directories.
[The tool page](../../../testing/comparison-eligibility.md) states what the tool holds, and
[one independent review](reviews/e02a-runs-review-1.md) recomputed each figure from the raw files.

## The result

- **Three runs started, and the classification record counts three.** Each manifest states
  `PASSED`. No manifest states `REFUSED`, `INCONCLUSIVE`, `ABORTED`, or `FAILED`, so no run has
  an exclusion reason.
- **`PASSED` is not a reliability pass here.** V2-E02A is a characterization with validity
  criteria alone. Each state is the judgment of the review of that run, on one reading of
  `E02A-AC2`, and the validity of each run is not established. Two requests failed in each run.
- **The current eligibility verdict is `not-decided`.** On the state of each manifest, the rule
  gives `eligible`: in each of the three runs, the analysis puts the start of a failure episode
  about 30 s after the `fault-injection-started` event. That start is the completion of the first
  failed request, and those requests were in flight from about the time of the fault. The rule
  asks for two of the three runs. It reads runs whose validity is not established, so that
  result is not the current verdict.
- **This page states no comparison.** No run of V2-E02B exists, and no before and after statement
  is permitted without a valid baseline. An eligibility verdict does not authorize a run of
  V2-E02B.

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

**The failed requests were in flight for most of the gap.** The caller record states this.

| Run | Two failed requests, sent after the fault | Time in flight | Largest time with no completion in the window |
|---|---:|---:|---:|
| `e02a-1` | 2,601 ms, 5,108 ms | 28,128 ms, 25,619 ms | 25,620 ms |
| `e02a-2` | -111 ms, 4,021 ms | 30,877 ms, 26,745 ms | 26,745 ms |
| `e02a-3` | 1,740 ms, 4,864 ms | 28,951 ms, 25,827 ms | 25,828 ms |

So the caller failure episode, about 4 s, does not hold the time in which no request completed.
The largest time between two successes, about 30 s, holds it.

## The classification

| Check | How it was done | Outcome |
|---|---|---|
| Each attempted run is retained | The run identifiers are 1 to 3 with no gap. The tool refuses a gap, because the driver spends one identifier for each start | Held: 3 of the 6 starts that one revision allows |
| Each run has a state that the outcome rules give | The result page of each run states each criterion. The review of the set is in [the validation record](../../environment/v2-s7-002-pr1-validation.md) | `PASSED` on the stream reading of `E02A-AC2`. No source settles that reading, so this row does not establish validity |
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

**The classification record states `eligible`, on the failure episodes alone, and that is not
the current verdict.** The rule reads counted runs, and the validity of these runs is not
established. The start of each episode is on the node clock, and the event is on the host clock.
The clock policy of the record does not declare the set rules. This classification applies its
margin all the same, and each start is after the event by more than the margin.

**The zero-Ready condition does not decide the verdict.** The record does not state which instant
starts an interval. A reading before the fault reported the Ready endpoint, and the first reading
after the fault reported none. The state changed between the two. In each run the first of those
two reads started before the event, so the readings do not exclude a change before the event. The
first reading that gave zero started after the event in each run. This classification states both
figures. Only the outer start can make a set eligible, and on the outer start this condition is
not held. The verdict rests on the other condition.

**The failure-episode condition also holds on the send instants.** The rule reads the start of an
episode from the analysis. If a reader took the send of the first failed request instead, two runs
hold by more than the margin. In `e02a-2` that request was sent 111 ms before the event, inside
the margin of 980 ms, so no order is stated. Two of three still hold.

**The baseline comparison record states another thing.** Its `experimentEligibility` stays
`not-established`. That record compares committed inputs, and it reads no run. It is pinned,
and this classification does not change it.

**Revision 3 of V2-E02B still says `eligible`.** It binds the digest and the verdict of the
classification record, so that record keeps its bytes and that revision says this until a
successor revision. That binding is not the current verdict. The adjudicated record states its
own target, revision 3, and the classification record keeps revision 2 as its target.

## The two readings of `E02A-AC2`

The criterion says that each stream "states a value in its first and its last reading inside the
window" and "has at most 10 s between two consecutive readings with a value". Each figure below
is computed from the raw streams, over the readings wholly inside the window, from the start of
one reading to the start of the next. From the finish of one reading to the start of the next, the
measure of [the result page of each run](runs/e02a-1/result.md), the largest gap is 5,796 ms on the
reading scope and 22,043 ms to 25,104 ms on the two runtime counts.
[The adjudicated record](eligibility-adjudicated.v1alpha1.json) holds each stream and each field.

| Run | Readings of the deployments stream | Reading scope, largest gap of the four streams | Runtime `readyReplicas` and `availableReplicas`: readings with a value | The two runtime counts, largest gap | Limit |
|---|---:|---:|---:|---:|---:|
| `e02a-1` | 166 | 6,001 ms | 160 | 26,304 ms | 10,000 ms |
| `e02a-2` | 188 | 5,036 ms | 182 | 23,488 ms | 10,000 ms |
| `e02a-3` | 178 | 7,057 ms | 172 | 23,115 ms | 10,000 ms |

The reading scope holds in 3 of 3 runs, with its three variants together: the read answered,
with no fault, no null member, and no refused tier. The two runtime counts hold in 0 of 3. The
review chose those two after the evidence was read, and no source selects them for `E02A-AC2`.
Revision 4 predates the first fault: it names the signal `runtime-ready-replicas`, it reads
`readyReplicas` in P6, in the stable window, and in the cleanup, and it lists both counts among
its measurements. Those uses name no criterion, and the adjudication cites none of them. A reading
omits a count of zero, and it states that count as missing, not as zero. Each
other count but `unavailableReplicas` is reported in each reading of each window, so a field
reading of one of those counts would give another outcome. No reading in the three windows reports
each of the eight Deployment counts of both tiers, because the count `unavailableReplicas` of the
API tier is omitted in each of them.

The first draft of the criterion, at commit `9a9f064`, said "states a Ready endpoint count of both
tiers" for the endpoints stream, and commit `28351f8` replaced it before any run. That is context
and not authority. This page does not state which reading is right.

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

## The figures that the record of V2-E02B names

The record of V2-E02B names two medians of this baseline. It computes an improvement only when
V2-E02A is eligible, and the current verdict is `not-decided`, so neither figure is usable as a
baseline today.

| Figure of the record of V2-E02B | Metric | Value | Basis |
|---|---|---:|---|
| `B_failures` | `requests-failed-since-fault` | 2 | Above zero |
| `B_episode` | `caller-failure-episode-ms` | 4,065 ms | Above zero |

**No percentage exists.** Neither figure is zero, so the rule that no percentage is computed over
a zero baseline does not apply to this set. The tool states that case for a zero median and for a
median that the aggregate does not state, and tests hold both. No percentage is stated here,
because no run of V2-E02B exists and the verdict is not eligible. In the adjudicated record `percentageOverThisBasisPossible` is false for both figures,
because the set is not decided.

**Two limits of these figures.** Each stands as a statement of what was measured.

- `B_episode` does not hold the time in which no request completed. The section on each run
  states that time. The record of V2-E02B names this metric, and this page does not change it.
- `B_failures` is 2 in each run, and the caller profile has 2 workers. This page does not
  establish that the count can exceed the number of workers. It is not a measure of the length of
  the failure.

## The V1 pod-loss evidence stays apart

The record of V2-E02A keeps the controlled baseline apart from the V1 pod-loss evidence, and it
states that no V1 figure is a value of V2-E02A. The record of V2-E02B reads its two figures from
V2-E02A, so no V1 figure enters that comparison.

Two V1 records state `callerVisibleOutageMs`:
[31,960 ms](../../serving/v1-s4-006-pr1-recovery-record.v1alpha1.json) and
[2,832 ms](../../environment/v1-s5-001-pr2-recovery-record.v1alpha1.json). Each is one pod lost
once, under a V1 tool, a V1 load profile, and a V1 release with one API replica and one runtime
replica. That field measures from the first request after the delete that was not served. The
caller failure episode of this page measures from the completion of the first failed request.
The figures of this page are not comparable with those two, and this page draws no conclusion
from any difference.

## Known limitations

- **The state of each run rests on a reading that the owner approved after the evidence was
  read.** `E02A-AC2` limits the time between readings of a stream that have a value. The record
  does not state whether a reading with one omitted field has a value. The repository owner
  approved the stream reading on 2026-10-31. No tool reads that approval. On the readings of the
  runtime `readyReplicas` count alone, each run would be `INCONCLUSIVE`, no run would be counted,
  and the classification record would decide nothing. The `availableReplicas` count has the same gaps. The record
  does not state which fields a reading has to hold. V2-E02B has the same criterion, so a later
  record states this reading or does not, and this page does not decide that. That approval
  is a post-result choice, and a later approval does not make it preregistered.
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
| Its executing commit | `ff45093b2a9bf2cdbcde5fee453fbc6b64f2e53b`, the merge of the G1 switch, with [no authorization found before it](../../environment/v2-s7-004-pr1-switch-deviations.md) |
| Its manifest and its run analysis | `9e1e8f12…` and `547bda5e…` |
| The governing record | Revision 4, `3630fbf2…`, which stays the authority for these three runs |
| The merge that holds the run evidence | `6db8161`, pull request #160 |
| The desired state on `main` when the runs executed | 2 API + 1 runtime: `f7eaab84…` and `e0b2507c…` |
| The desired state that rule G3 restores | 2 API + 2 runtime, as revision 2 of V2-E02B states: `810b4b27…` and `6a1304a8…` |
| Pinned inputs that this change moves | `tools/evidence_index/__init__.py` and `core.py`. Each record that pins them differs from its pin. No revision classifies them yet, so `V2-S7-003-PR2` inventories them for revision 3 of V2-E02B |

Rule G3 restored the two files in one change merged into `main`, `a3ed812`. Rule G4 asks for the
explicit authorization of the repository owner for that merge, and
[none was found before it](../../environment/v2-s7-004-pr1-switch-deviations.md). This page gives
none. No row of the classification record changed when `main` returned to the target: it reads no
desired state of the working tree.

## The claim

The register holds one claim of these runs, `the-e02a-baseline-runs-recorded-the-loss-of-the-one-runtime-pod`, with one record at `C2` of
each run. Its status is `certified`, which says that executed records support the statement inside
the boundary that its limitation states. That is a claim status. It is not a reliability result:
the statement says that requests failed. The repository owner chose on 2026-11-01 to register it
in this change, and no tool reads that choice. See
[the ledger](../../testing/v2-s7-002-pr1-e02a-baseline-registration.v1alpha1.json).
`V2-S7-004-PR1` narrows it to what executed and to the measured figures, and it withdraws the
statements of validity and eligibility, through
[a twelfth ledger](../../testing/v2-s7-004-pr1-e02a-claim-correction.v1alpha1.json), which rests on
[a later review](reviews/e02a-correction-review-2.md). `E02A-AC2` becomes
`not-evaluated` in each record. The status stays `certified`, which says that executed records
support the narrowed statement.

## What this establishes, and what it does not

For three runs on one provider, this page states what the caller, the endpoints, and the pods
showed when the one runtime pod was deleted while RP-1 ran, and what each reading of `E02A-AC2`
gives on the raw streams.

It does not establish:

- that any run is valid, or that any run is not valid;
- that the eligibility rule of revision 4 holds or fails for this set;
- a comparison, an improvement, or a percentage;
- that one runtime replica is or is not acceptable for any service;
- that the desired state is restored;
- an authorization of a run of V2-E02B, of the G3 switch, or of a later sprint;
- node failure, overload, sustained capacity, or production availability;
- the cause of a failure, of a gap, or of a recovery;
- anything about another provider, node, release, or caller workload.
