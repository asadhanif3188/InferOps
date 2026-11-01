# Run e02a-1: PASSED

Run `e02a-1` of [V2-E02A](../../freeze-r4.v1alpha1.json), under revision 4, on 2026-10-31 from
13:27:58Z to 14:33:10Z, at the commit
`ff45093b2a9bf2cdbcde5fee453fbc6b64f2e53b`, on the docker-desktop provider, with one node.

**State: PASSED.** Each of the seven criteria held. V2-E02A is a baseline characterization,
and all seven are validity criteria. So this state says that the run is valid evidence of
what the loss of the one runtime pod looks like. It is not a reliability pass. **Requests
failed in this run**, and that does not change the state. The intended evidence level is C2.

## What the run did

The control deleted the one runtime pod, `inferops-inferops-llm-runtime-6b4554dc64-l7tth`, once, while the RP-1 runner sent
requests. `fault-injection-started` was recorded at 13:41:35.149Z, and
`fault-injection-finished` at 13:41:35.914Z. The window is 13:40:35.149Z to 13:53:35.914Z.

## The criteria

The clock bound of this run is 817 ms, so the margin of a cross-clock order is
818 ms.

| Criterion | Kind | Verdict | Evidence |
|---|---|---|---|
| `E02A-AC1` | validity | Held | `commands.txt` holds one fault command. It names the pod that F1 in `control.json` selected, with the UID `7620f545-f512-4a84-8641-db452fa53201`. `operator-events.jsonl` names that pod. `pods.jsonl`, reading 53, finished at 13:41:36.775Z, is the first reading after the event that shows that UID deleting or absent. No other pod has a deletion timestamp. |
| `E02A-AC2` | validity | Held | Inside the window: endpoints 166 of 166 readings answered, largest time between two 4.021 s. Pods 166 of 166, 4.021 s. Deployments 166 of 166, 4.021 s. Argo 166 of 166, 4.911 s. The first and the last reading of each stream answered. |
| `E02A-AC3` | validity | Held | The runner collection accepted the record with the plan: mode `in-cluster`, end state `duration`. The record starts at 13:39:01.892Z and finishes at 14:04:04.315Z, so it covers the window by more than the margin. 1 completion(s) are inside the margin of the window start, so the last completion before the window is one of 2 request(s). Each of them succeeded, so the verdict needs no order of those instants. 332 requests complete inside the window after `fault-injection-finished`, by more than the margin. |
| `E02A-AC4` | validity | Held | A pod with a new UID, `inferops-inferops-llm-runtime-6b4554dc64-lvqkp`, is Ready in `pods.jsonl` from 13:41:57.659Z. The analysis states a stabilized recovery at 13:43:11.618Z, before the observation limit at 13:51:35.914Z by more than the margin. |
| `E02A-AC5` | validity | Held | 295 successful requests complete after `stabilizedAt` inside the window, and the last completes 621.663 s after it. |
| `E02A-AC6` | validity | Held | `pods.jsonl` states no restart of any container. The two API pods are the same two pods in each reading from before the fault to after the window. The one pod added is the runtime replacement. `control.json` records no abort. `transcript.txt` holds 21 reads of the node during the run, and each states Ready `True`. |
| `E02A-AC7` | validity | Held | Each file of the evidence paths is present and named by the manifest. The event log is closed. `tools.experiment_evidence check` accepts this directory, and `tools.analysis_replay verify` reproduces `analysis.json`. The validation record of the change states the commands. |

## What the files show

These are readings of this run. No criterion compares them with a bound, and this page
states no cause.

| Reading | Value |
|---|---:|
| Requests completed inside the window | 365 |
| Successful | 363 |
| Failed | 2 |
| Failure episodes | 1 |
| Caller failure episode, total | 4.3 s |
| Largest time between two successful completions | 29.9 s |
| Runtime tier at zero Ready endpoints, inner figure | 17.3 s |
| Runtime tier at zero Ready endpoints, outer figure | 26.8 s |
| Stabilized recovery after `fault-injection-started` | 96.5 s |
| First caller impact, the completion of the first failed request | 13:42:05.876Z |
| Failed requests since the fault | 2 |
| API tier at zero Ready endpoints | 0 intervals |

From the whole caller record, not the window alone:

| Reading | Value |
|---|---:|
| Requests started | 717 |
| Requests completed | 717 |
| HTTP status | 200: 715, 500: 2 |
| Canonical error code and condition | `internal-error`, `runtime-error-response`: 2 |
| Latency of the successful requests, nearest-rank p50 | 3,872 ms |
| Latency of the successful requests, nearest-rank p95 | 5,804 ms |
| Latency of the successful requests, nearest-rank p99 | 7,454 ms |
| Latency of the successful requests, minimum | 3,235 ms |
| Latency of the successful requests, maximum | 8,050 ms |
| Longest run of failed completions with no success between them | 2 |
| From `fault-injection-started` to the first successful completion after the first failure, an event on the host clock to a completion on the node clock | 35.003 s |

For the replacement pod, `createdAt` is 2026-10-31T13:41:35Z and `readyTransitionAt` is
2026-10-31T13:41:56Z, so its time from creation to its first Ready condition is 21 s,
to one second. Each signal of the declaration states its detection lag, its false-healthy time,
and its false-unavailable time in `analysis.json`.

- **The failed requests:** request 86 at 13:42:05.876Z, `http-error`, request 85 at 13:42:05.878Z, `http-error`.
- **The stabilized recovery is a rule of the analysis, not a measured recovery of the service.**
  It is the end of the first span of at least 10 successes over at least 60 s after the fault,
  with the conditions held. So it is at least 60 s later than the first success of its span.
- **The runtime readyReplicas count:** the API omits a count that is zero, so this count has no
  value in 6 readings, and the
  largest time between two readings with a value of this count is 25.1 s.
  E02A-AC2 states a limit for the readings of a stream, and the stream states other values in
  those readings. The classification of the set of runs reads this statement.
- **The net change of the clock offset** from the start reading to the end reading is
  +6.5 ms. No verdict reads it.

## What the review compared

The control leaves these comparisons to the review of the run.

| Comparison | Outcome |
|---|---|
| The stored declaration and the rule of the record | Equal. The rule, with the desired revision and the two fault events of this run, gives the stored document. |
| The freeze record of the manifest and the registry | Equal. The manifest names revision 4 with the digest that the registry pins. |
| A change that a person made | None. `operator-events.jsonl` holds the two fault events and no other event, and the analysis states no manual action. |
| The cleanup | `control.json` states that the removal exited 0, and that the namespaces and the custom resource definitions equal those read before P5. |
| **The model file of the replacement pod** | **Not compared directly.** The procedure read the model verification log of the first runtime pod alone, and the cluster was removed, so the digest that the replacement pod verified was not read. The indirect evidence is this: the chart verifies the byte count and the SHA-256 at each pod start, the Application sets `verifyOnStart: sha256`, `pods.jsonl` states that the `verify-model` init container of the replacement pod completed with 0 restarts, and 21 reads of the model cache claim state one UID, `Bound`. |

## What this establishes, and what it does not

For one run, on one provider, it shows what the caller, the endpoints, and the pods showed when
the one runtime pod was deleted while RP-1 ran.

It does not establish that one runtime replica is or is not acceptable for any service; node
failure, overload, sustained capacity, or production availability; the cause of a failure, of a
gap, or of a recovery; or anything about another provider, node, release, or caller workload. It
does not classify the set of runs, and it does not decide that the baseline is eligible for the
comparison with V2-E02B.
