# Attempt integration-1: FAILED

The first attempt of the [Sprint 5 integration validation](../../freeze-r1.v1alpha1.json),
under revision 1, on 2026-10-14 from 08:57:57Z to 09:09:01Z, at the commit
`7f150c25af26f855a7390125be82dd44fba772a5`, on the docker-desktop provider. It is not a
run of E02, E03, E04, E05, or E06, and no figure of it is compared with a bound.

**State: FAILED.** Criterion `S5I-AC2` did not hold: no request of the runner reached the
API. Every other criterion held. The attempt is kept as it ran. It is not repeated under
revision 1.

## The criteria

| Criterion | Verdict | What the files of this directory show |
|---|---|---|
| `S5I-AC1` | Held | `transcript.txt`, step E0: a clean working tree, the freeze check passed, every material file matched its pin, and the chart, the desired-state tree, and the controller manifests were those of the remote main `2d43331`. Step E1b: the Application was Synced and Healthy at `2d43331`, and each Deployment reported 2 Ready replicas. |
| `S5I-AC2` | **Not held** | `caller.jsonl`: the reader accepted it with the plan, in the mode `in-cluster`, with the target `http://inferops-inferops-llm.inferops-release.svc:8090` and the end state `duration`. Its six requests each ended with the outcome `timeout` after the client deadline of 150,000 ms, and none with `success`. So no success came before the deletion, and none after the replacement pod was Ready. |
| `S5I-AC3` | Held | `runner-pod-readings.txt`: the three readings name one pod, `inferops-reliability-integration-1-8z7kn`, with one UID and a restart count of 0, `Running` before and after the deletion and `Succeeded` at the end. `attempt.txt`: the Job stated `succeeded=1` and no failure. The deleted pod is an API pod. |
| `S5I-AC4` | Held | `transcript.txt`, step E10: the four timeline streams (200 readings each, all answered), the two telemetry streams, and the closed event log each passed their own checker. The log holds one `fault-injection-started` and one `fault-injection-finished`, and both name `pod/inferops-inferops-llm-c66d85b99-p72ls`. |
| `S5I-AC5` | Held | `telemetry.jsonl`: 288 query reads through the Service proxy of the API server, all answered: 216 with series and 72 with no series. `resources.jsonl`: 108 reads, 72 with series and 36 with no series. A read with no series is stated as `no-series`, and not as zero. |
| `S5I-AC6` | Held | The run directory passes the layout check, the manifest validates, and `analysis_replay verify` computes `analysis.json` again with the same bytes. The validation record of the change states the commands. |
| `S5I-AC7` | Held | `transcript.txt`, step E9: the cleanup exited 0, and the read of the objects labelled `inferops.io/run-id=integration-1` printed nothing. |

## Why the requests did not reach the API

The release's network policies were applied, and the network plugin of this cluster runs a
policy controller. The API policy admits the pods of the release and the named collector on
port 8090. The runner carries no label of the release, by design, so no rule admits it.

Three readings agree with a drop of the runner's packets by that policy:

1. **The caller.** Six requests ended at the client deadline with no answer, and none with
   a refused connection.
2. **The API's own counter.** In `telemetry.jsonl`, the query `api-requests-by-outcome`
   answered `no-series` in each of its 36 reads, the first started at 08:58:32.887Z and the
   last at 09:07:01.918Z. The API
   recorded no completed request in that time.
3. **The logs of the API pods, read by the operator after the attempt.** This read is not in
   the transcript. The operator ran, after the driver ended:

   ```text
   kubectl --context docker-desktop -n inferops-release logs <pod> --since=30m | grep -c integration-1
   ```

   for each of the two API pods present then, `inferops-inferops-llm-c66d85b99-zgcgp` and the
   replacement `inferops-inferops-llm-c66d85b99-27s46`. Each printed `0`. The log of the
   deleted pod was not readable, because it went with the pod.

No reading states a verdict of the network plugin: its log, read by the operator after the
attempt with `kubectl logs ds/kindnet --since=20m`, held no line about a policy decision.
So the cause is an inference from the three readings, and it is not an observation of a
dropped packet.

The operator made one more read outside the procedure, during the attempt, at about
08:59:45Z: `kubectl logs job/inferops-reliability-integration-1 --container runner | head`.
It printed the header line of the record and no request line. It changed nothing, and the
driver did not read it.

## What the attempt did show

- **The runner survived the replacement of one API pod.** The runner pod kept one UID and
  no restart, and it ran to the end of its duration, while the API pod
  `inferops-inferops-llm-c66d85b99-p72ls` was deleted from 09:01:15.459Z and a replacement,
  `inferops-inferops-llm-c66d85b99-27s46`, read Ready in `pods.jsonl` from the reading that
  started at 09:01:22.532Z. The reading before it listed the replacement as not Ready. That shows the
  runner process continuing. It does not show that a caller kept getting answers, because
  no request was answered.
- **The collectors ran beside it on one host clock.** Both collectors answered every read
  through their supported paths, including the Service proxy of the telemetry collector.
- **The analysis computed its figures.** `analysis.json` states one open failure episode,
  no success gap, and no zero-ready interval of either tier inside the window.

The two readings of the node's clock in `attempt.txt` put the node within -0.09 s and
+0.46 s of the host's two instants at the start and at the end.

## What follows

Revision 2 of the record adds a network policy for each run that admits the runner of that
run, and nothing else, to the API pods on port 8090. The policy is created with the Job and
deleted by the cleanup. The release's own policies are not changed. A second attempt runs
under revision 2.
