# Attempt integration-2: PASSED

The second attempt of the [Sprint 5 integration validation](../../freeze-r2.v1alpha1.json),
under revision 2, on 2026-10-14 from 10:16:23Z to 10:30:34Z, at the commit
`7089a53ac0a62933cfba74facfe998e73c5a4f97`, on the docker-desktop provider, against the
release that the first attempt used. It is not a run of E02, E03, E04, E05, or E06, and no
figure of it is compared with a bound.

**State: PASSED.** Each of the seven criteria held. The first attempt,
[integration-1](../integration-1/result.md), FAILED under revision 1 and is kept. Revision 2
differs from it in one material way: a run brings its own network policy, which admits the
runner of that run to the API pods.

## The criteria

| Criterion | Verdict | What the files of this directory show |
|---|---|---|
| `S5I-AC1` | Held | `transcript.txt`, step E0: a clean working tree, the freeze check passed, every material file of revision 2 matched its pin, and the chart, the desired-state tree, and the controller manifests were those of the remote main `2d43331`. Step E1b: the Application was Synced and Healthy at `2d43331`, and each Deployment reported 2 Ready replicas. |
| `S5I-AC2` | Held | `caller.jsonl`: the reader accepted it with the plan, in the mode `in-cluster`, with the target `http://inferops-inferops-llm.inferops-release.svc:8090` and the end state `duration`. 98 requests, each with the outcome `success`. 42 completed before `fault-injection-started` was recorded at 10:19:55.410Z. In `pods.jsonl` the first reading of a Ready platform-api pod with a UID that no reading before the deletion held, `inferops-inferops-llm-c66d85b99-ksnlw`, is reading 43, which finished at 10:20:28.415Z. 51 successes completed more than 0.902 s after it, the first being request 49 at 10:20:30.236Z. 0.902 s is the larger skew bound of the two node-clock readings in `attempt.txt`. |
| `S5I-AC3` | Held | `runner-pod-readings.txt`: the three readings name one pod, `inferops-reliability-integration-2-k8rds`, with one UID, `bfb7598e-ae08-4e01-ac35-cde966b89cf0`, and a restart count of 0: `Running` before and after the deletion, `Succeeded` at the end. `attempt.txt`: the Job stated `succeeded=1` and no failure. The deleted pod, `inferops-inferops-llm-c66d85b99-27s46`, is an API pod. |
| `S5I-AC4` | Held | `transcript.txt`, step E10: the four timeline streams (200 readings each, all answered), the two telemetry streams, and the closed event log each passed their own checker. The log holds one `fault-injection-started` and one `fault-injection-finished`, and both name `pod/inferops-inferops-llm-c66d85b99-27s46`. |
| `S5I-AC5` | Held | `telemetry.jsonl`: 288 query reads through the Service proxy of the API server, all answered: 249 with series and 39 with no series. `resources.jsonl`: 108 reads, 72 with series and 36 with no series. A read with no series is stated as `no-series`, and not as zero. |
| `S5I-AC6` | Held | The run directory passes the layout check, the manifest validates, and `analysis_replay verify` computes `analysis.json` again with the same bytes. The validation record of the change states the commands. |
| `S5I-AC7` | Held | `transcript.txt`, step E9: the cleanup deleted the Job, the ConfigMap, and the network policy of the run, exited 0, and the read of the jobs, ConfigMaps, pods, and network policies labelled `inferops.io/run-id=integration-2` printed nothing. The six network policies of the release were still present. |

## What the files show beside the criteria

These are readings of this attempt. None is compared with a bound, and none is a result of
an experiment.

- **The deletion took 25 s.** `fault-injection-started` was recorded at 10:19:55.410Z and
  `fault-injection-finished` at 10:20:20.251Z. The command waits for the pod to be gone.
- **No request failed.** `analysis.json` states no failure episode and no first impact
  after the deletion. The largest time between two successful completions inside the
  window is 24,037 ms, from request 42 at 10:19:45.776Z to request 43 at 10:20:09.813Z.
  It spans the start of the deletion. The longest request took 30,217 ms, and the shortest
  2,265 ms.
- **Ready endpoints of the API tier.** The signal `api-ready-endpoints` read fewer than 2
  Ready API endpoints in 5 of its 41 readings inside the window, and no reading had none.
  The signal `application-health` read the Application as not Healthy in 4 readings. The
  caller had no failure in the same window. The infrastructure readings and the caller
  record are separate sources: neither stands for the other.
- **The API's own counter is not the caller's count.** The last answered read of
  `api-requests-by-outcome` in `telemetry.jsonl` states 78 successful requests, summed over
  the series the collector held at that read. The caller recorded 98. This attempt does not
  explain the difference. One API pod and its counter were replaced during the attempt, and
  nothing here establishes how much of the difference that accounts for.
- **The timeline read less often than its pause.** Inside the window the largest time
  between two readings of the endpoints and of the Deployments is 9,411 ms, with a pause
  of 2 s between samples. This attempt does not establish why. The streams state the
  instants of each read.
- **The clocks.** The node's instant minus the host's two instants was +0.902 s and
  -0.220 s at the start, and +0.383 s and -0.073 s at the end.

## What this establishes, and what it does not

It shows, for one attempt on one provider, that the merged Sprint 5 evidence path works
together: the in-cluster RP-1 runner reaches the API Service and the real model, it keeps
running and recording while one API pod is replaced, the infrastructure, telemetry, and
operator-event streams are captured beside it on the host's UTC clock and pass their
checkers, and the run directory passes the layout check and the analysis replay.

It does not establish a recovery time, an availability, a service level, a capacity, or a
threshold; behaviour when a runtime pod is replaced, or under more than one deletion;
behaviour on another provider, node count, or network plugin; or that a caller loses no
request when an API pod is replaced. One replacement, with a second API pod Ready
throughout, is one observation.
