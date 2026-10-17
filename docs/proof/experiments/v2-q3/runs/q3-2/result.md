# Q3 characterization `q3-2`: CHARACTERIZED, G = 10,113 ms

Status: **`CHARACTERIZED`. Each of the 14 rules of [freeze revision 2](../../freeze-r2.v1alpha1.json)
held. One RP-1 run of 362,958 ms completed 153 of 153 requests with the outcome
`success`, the same 4 API and runtime pods stayed Ready with no container restart, and G,
the nearest-rank p99 of the 152 gaps between successive successful requests, is 10,113
ms.** Evidence level C2, bounded to one environment: the docker-desktop provider with one
node, in the stable environment identity that [`q1-2`](../../../v2-q1/runs/q1-2/result.md)
states. It is a qualification and not a result of a reliability experiment. G is a gap
reference of a healthy topology under RP-1, not a latency figure, a throughput, or a
service level, and no claim cites it. It is the G of the Q4 bound record
[`bounds-r1`](../../../v2-q4/bounds-r1.v1alpha1.json).

| Property | Value |
|---|---|
| Record | [`record.v1alpha1.json`](record.v1alpha1.json), built by `tools/caller_characterization`; content SHA-256, with LF, `0a978396b5d7f15a4a6b507dda288d16dff5d937828cde2e2782a73d504ca99a` |
| Header | [`run.json`](run.json) |
| Transcript | [`transcript.txt`](transcript.txt): the phases `up`, `characterize`, and `down`, with the absolute path of the host replaced by `<repository>` |
| Freeze record | `docs/proof/experiments/v2-q3/freeze-r2.v1alpha1.json`, SHA-256 `f1ebcc296ebc81f0257e6b352f707dad6e635c46dbbd046dfc893eb8fc3f77ff` |
| Qualification | `q1-2`, content SHA-256 `1141cbd1c0acd7eff839395a89eba3fe116a060dafb3941128bf23c440ec1b3d` |
| Executing commit | `0dbea911050395b400a1c03bf76e0579bb1c152b`, for the phase `up` and the characterization: the commit that added the directory of `q2-2` |
| Desired revision | `ed892a4eac2ee505996f53b6d3e0da31b8e4e204`, the remote main. The delivery paths of the executing commit equal it |
| Release | `local-docker-desktop/support-assistant`, identifier `b5457f49092c578496738973a8786a95428517e7ddf755303b4f6842dcb8c9db`, the one of `q1-2` |
| Environment | `sha256:6a219b3ff959a0020d982d967abeed6696aa0f0d1b594bdf3ad86b9aeda8cd5c`, the stable identity of `q1-2`. The capacity reading of this run stated 10,429,972,480 bytes of memory, and the gate accepted it |
| Caller profile | RP-1, revision 1, SHA-256 `ff3cbab5a3bde8d4e25defe940cbcfb4ea3ff1ba028f1bc25c577636c261c1c3`; duration 360 s, ceiling 2,000 requests, concurrency 2 |
| API image | `sha256:bfb5c2b003f0f292594206bd85be5f5119fe5a9cc972a617d35f692ce9009aab`, the manifest-list digest that this phase `up` declared. The build printed the image manifest `bba83fa7…` and the config `cd65ca24…` |

## What ran

All instants are UTC, on 2026-10-17. The host instants are those that the driver printed.

1. **The phase `up`** of the Q1 driver ran without a change, from 15:31:12 to 15:43:11 (its
   start file holds 15:31:15), with the work directory `q3run-2`. Both capacity readings
   were `ACCEPTED`. The import of the model seed image into the node took 305.6 s. The
   controller reported the Application `Synced` and `Healthy` at the revision `ed892a4`.
2. **The characterization `q3-2`** ran from 15:43:20.778, its start instant, to
   15:51:05.641, the instant of its final header. Each of the 7 preconditions was held when
   the driver asked the tool. The watch of the API pods and the runtime pods started at
   15:43:35.482 and listed the 4 pods. The caller run was requested at 15:43:36.453; its
   first request in the runner pod started at 15:43:58.983, its first success completed at
   15:44:02.022, and its last at 15:50:01.874. The driver saw the Job succeeded at
   15:50:19.547, collected the record, and removed the objects of the run. The controller
   then reported the Application `Synced` and `Healthy` at `ed892a4`. The watch stopped at
   15:50:59.386.
3. **The phase `down`** of the Q1 driver removed the Application, the controller, and the
   prerequisite layer, and ended at 15:53:18. The namespaces and the custom resource
   definitions after it were those before the phase `up`, and no persistent volume
   remained.

## What the caller saw

| Figure | Value |
|---|---|
| Requests | 153, each `success`, each HTTP status 200 with the finish reason `stop`; no `timeout`, `http-error`, `transport-error`, `invalid-response`, or `identity-refused` |
| End | By its duration, after 362,958 ms, before its ceiling of 2,000 |
| Gaps between successive successes | 152: minimum 12 ms, nearest-rank p50 2,117 ms, p90 4,495 ms, p99 10,113 ms, maximum 11,417 ms |
| Latency of a success | minimum 1,739 ms, p50 4,338 ms, p90 6,841 ms, p99 12,804 ms, maximum 16,679 ms |

**G = 10,113 ms**, by the rule `p99`: 153 successes are at least the 100 that the freeze
record requires for the percentile, so G is the gap at rank ceil(0.99 × 152) = 151 of the
152 gaps in ascending order, not the maximum. A test computes it again from the committed
caller record.

## The topology while the caller ran

The watch holds 14 events: one `ADDED` event for each of the 4 pods, and 10 `MODIFIED`
events. Each `MODIFIED` event changed only the second host address of its pod, an IPv6
address of the node that the pod status listed and then dropped, and the time of its
managed fields. No Ready condition changed, no restart count changed, no pod was deleted,
and no other pod appeared. The rule `topology-held` reads the conditions and the counts,
so the events do not bear on it. This page does not establish why the kubelet reported the
second address intermittently.

## What this does not establish, and what to read with it

- **G is a gap reference of this healthy run, not an outage.** With two closed-loop
  workers and successes taking up to 16.7 s, a gap of 10 s between two successes needs no
  failure: no request failed. G measures the spacing of successes under RP-1 in this
  topology. It is not a latency, a throughput, or a capacity figure.
- **One run.** The freeze record runs Q3 once. The record does not establish G under
  another load, another duration, another release, or another environment, or the spread
  of G across runs.
- **The clock is the runner pod's.** Gaps are differences of the `finishedAt` instants of
  the runner pod, to one millisecond.
- No average, no availability, no service level, and no bound. The Q4 bound record derives
  its bounds from G; this record states none.

## Not committed

`capacity/pods.json`, the capacity gate's read of every pod of the cluster, is not
committed, for the reason given for `q1-1`. Its SHA-256, with LF, is
`90589714161b4e12a7b0e250138e5d9ee23b1058a3fa28e72b0fe595d15f8aa2`, and it held 267,826
bytes, as the operator measured them; no committed file corroborates either figure. The
Q3 record does not read the file.
