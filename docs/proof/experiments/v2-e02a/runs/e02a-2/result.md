# Run e02a-2: PASSED

Run `e02a-2` of [V2-E02A](../../freeze-r4.v1alpha1.json), under revision 4, on 2026-10-31 from
14:35:34Z to 15:35:58Z, at the commit
`ff45093b2a9bf2cdbcde5fee453fbc6b64f2e53b`, on the docker-desktop provider, with one node.

**State: PASSED.** Each of the seven criteria held. V2-E02A is a baseline characterization,
and all seven are validity criteria. So this state says that the run is valid evidence of
what the loss of the one runtime pod looks like. It is not a reliability pass. **Requests
failed in this run**, and that does not change the state. The intended evidence level is C2.

## What the run did

The control deleted the one runtime pod, `inferops-inferops-llm-runtime-6b4554dc64-4brfb`, once, while the RP-1 runner sent
requests. `fault-injection-started` was recorded at 14:47:01.042Z, and
`fault-injection-finished` at 14:47:01.816Z. The window is 14:46:01.042Z to 14:59:01.816Z.

## The criteria

The clock bound of this run is 979 ms, so the margin of a cross-clock order is
980 ms.

| Criterion | Kind | Verdict | Evidence |
|---|---|---|---|
| `E02A-AC1` | validity | Held | `commands.txt` holds one fault command. It names the pod that F1 in `control.json` selected, with the UID `2d243312-bafc-46bf-91e9-31c2b03aa953`. `operator-events.jsonl` names that pod. `pods.jsonl`, reading 56, finished at 14:47:05.526Z, is the first reading after the event that shows that UID deleting or absent. No other pod has a deletion timestamp. |
| `E02A-AC2` | validity | Held | Inside the window: endpoints 188 of 188 readings answered, largest time between two 3.626 s. Pods 188 of 188, 3.626 s. Deployments 188 of 188, 3.626 s. Argo 189 of 189, 3.969 s. The first and the last reading of each stream answered. |
| `E02A-AC3` | validity | Held | The runner collection accepted the record with the plan: mode `in-cluster`, end state `duration`. The record starts at 14:44:27.539Z and finishes at 15:09:33.188Z, so it covers the window by more than the margin. 1 completion(s) are inside the margin of the window start, so the last completion before the window is one of 2 request(s). Each of them succeeded, so the verdict needs no order of those instants. 340 requests complete inside the window after `fault-injection-finished`, by more than the margin. |
| `E02A-AC4` | validity | Held | A pod with a new UID, `inferops-inferops-llm-runtime-6b4554dc64-548cs`, is Ready in `pods.jsonl` from 14:47:23.782Z. The analysis states a stabilized recovery at 14:48:35.794Z, before the observation limit at 14:57:01.816Z by more than the margin. |
| `E02A-AC5` | validity | Held | 307 successful requests complete after `stabilizedAt` inside the window, and the last completes 624.813 s after it. |
| `E02A-AC6` | validity | Held | `pods.jsonl` states no restart of any container. The two API pods are the same two pods in each reading from before the fault to after the window. The one pod added is the runtime replacement. `control.json` records no abort. `transcript.txt` holds 22 reads of the node during the run, and each states Ready `True`. |
| `E02A-AC7` | validity | Held | Each file of the evidence paths is present and named by the manifest. The event log is closed. `tools.experiment_evidence check` accepts this directory, and `tools.analysis_replay verify` reproduces `analysis.json`. The validation record of the change states the commands. |

## What the files show

These are readings of this run. No criterion compares them with a bound, and this page
states no cause.

| Reading | Value |
|---|---:|
| Requests completed inside the window | 366 |
| Successful | 364 |
| Failed | 2 |
| Failure episodes | 1 |
| Caller failure episode, total | 3.7 s |
| Largest time between two successful completions | 30.4 s |
| Runtime tier at zero Ready endpoints, inner figure | 14.8 s |
| Runtime tier at zero Ready endpoints, outer figure | 23.8 s |
| Stabilized recovery after `fault-injection-started` | 94.8 s |
| First caller impact, the completion of the first failed request | 14:47:31.808Z |
| Failed requests since the fault | 2 |
| API tier at zero Ready endpoints | 0 intervals |

From the whole caller record, not the window alone:

| Reading | Value |
|---|---:|
| Requests started | 700 |
| Requests completed | 700 |
| HTTP status | 200: 698, 500: 2 |
| Canonical error code and condition | `internal-error`, `runtime-error-response`: 2 |
| Latency of the successful requests, nearest-rank p50 | 4,005 ms |
| Latency of the successful requests, nearest-rank p95 | 5,697 ms |
| Latency of the successful requests, nearest-rank p99 | 8,375 ms |
| Latency of the successful requests, minimum | 2,680 ms |
| Latency of the successful requests, maximum | 11,481 ms |
| Longest run of failed completions with no success between them | 2 |
| From `fault-injection-started` to the first successful completion after the first failure, an event on the host clock to a completion on the node clock | 34.448 s |

For the replacement pod, `createdAt` is 2026-10-31T14:47:01Z and `readyTransitionAt` is
2026-10-31T14:47:22Z, so its time from creation to its first Ready condition is 21 s,
to one second. Each signal of the declaration states its detection lag, its false-healthy time,
and its false-unavailable time in `analysis.json`.

- **The failed requests:** request 72 at 14:47:31.808Z, `http-error`, request 71 at 14:47:31.808Z, `http-error`.
- **The stabilized recovery is a rule of the analysis, not a measured recovery of the service.**
  It is the end of the first span of at least 10 successes over at least 60 s after the fault,
  with the conditions held. So it is at least 60 s later than the first success of its span.
- **The runtime readyReplicas count:** the API omits a count that is zero, so this count has no
  value in 6 readings, and the
  largest time between two readings with a value of this count is 22.4 s.
  E02A-AC2 states a limit for the readings of a stream, and the stream states other values in
  those readings. The classification of the set of runs reads this statement.
- **The net change of the clock offset** from the start reading to the end reading is
  +170.0 ms. No verdict reads it.

## What the review compared

The control leaves these comparisons to the review of the run.

| Comparison | Outcome |
|---|---|
| The stored declaration and the rule of the record | Equal. The rule, with the desired revision and the two fault events of this run, gives the stored document. |
| The freeze record of the manifest and the registry | Equal. The manifest names revision 4 with the digest that the registry pins. |
| A change that a person made | None. `operator-events.jsonl` holds the two fault events and no other event, and the analysis states no manual action. |
| The cleanup | `control.json` states that the removal exited 0, and that the namespaces and the custom resource definitions equal those read before P5. |
| **The model file of the replacement pod** | **Not compared directly.** The procedure read the model verification log of the first runtime pod alone, and the cluster was removed, so the digest that the replacement pod verified was not read. The indirect evidence is this: the chart verifies the byte count and the SHA-256 at each pod start, the Application sets `verifyOnStart: sha256`, `pods.jsonl` states that the `verify-model` init container of the replacement pod completed with 0 restarts, and 22 reads of the model cache claim state one UID, `Bound`. |

## What this establishes, and what it does not

For one run, on one provider, it shows what the caller, the endpoints, and the pods showed when
the one runtime pod was deleted while RP-1 ran.

It does not establish that one runtime replica is or is not acceptable for any service; node
failure, overload, sustained capacity, or production availability; the cause of a failure, of a
gap, or of a recovery; or anything about another provider, node, release, or caller workload. It
does not classify the set of runs, and it does not decide that the baseline is eligible for the
comparison with V2-E02B.
