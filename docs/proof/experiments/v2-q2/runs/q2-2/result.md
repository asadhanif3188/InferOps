# Q2 characterization `q2-2`: CHARACTERIZED, S = 11,000 ms

Status: **`CHARACTERIZED`. Each of the 16 rules of [freeze revision 3](../../freeze-r3.v1alpha1.json)
held. S, the maximum interval from the creation of a replacement runtime pod to its first
Ready condition, is 11,000 ms, at a resolution of 1,000 ms.** Evidence level C2, bounded
to one environment: the docker-desktop provider with one node, in the stable environment
identity that [`q1-2`](../../../v2-q1/runs/q1-2/result.md) states. It is a qualification and
not a result of a reliability experiment. S is not a startup benchmark, and no claim cites
it. It is the S of the Q4 bound record [`bounds-r1`](../../../v2-q4/bounds-r1.v1alpha1.json).

| Property | Value |
|---|---|
| Record | [`record.v1alpha1.json`](record.v1alpha1.json), built by `tools/runtime_startup`; content SHA-256, with LF, `db0bd1579cdb93e0e8ede69e5c441006b54ed7ae7f7eee8d1f3c43ad34444531` |
| Header | [`run.json`](run.json) |
| Transcript | [`transcript.txt`](transcript.txt): the phases `up`, `characterize`, and `down`, with the absolute path of the host replaced by `<repository>` |
| Freeze record | `docs/proof/experiments/v2-q2/freeze-r3.v1alpha1.json`, SHA-256 `421628933641f8b7c064913c7af0b82d5f8663582e3dd1155a4ac2d8a6dc19af` |
| Qualification | `q1-2`, `docs/proof/experiments/v2-q1/runs/q1-2/record.v1alpha1.json`, content SHA-256 `1141cbd1c0acd7eff839395a89eba3fe116a060dafb3941128bf23c440ec1b3d` |
| Executing commit | `28d253439d1a4cff6fe6db579ffbbab77b256a54`, for the phase `up` and the characterization: the commit that added the directory of `q1-2` to the branch, so that the tool read its record from a clean tree |
| Desired revision | `ed892a4eac2ee505996f53b6d3e0da31b8e4e204`, the remote main. The delivery paths of the executing commit equal it |
| Release | `local-docker-desktop/support-assistant`, identifier `b5457f49092c578496738973a8786a95428517e7ddf755303b4f6842dcb8c9db`, the one of `q1-2` |
| Environment | `sha256:6a219b3ff959a0020d982d967abeed6696aa0f0d1b594bdf3ad86b9aeda8cd5c`, the stable identity of `q1-2`. The capacity reading of this run stated 10,429,972,480 bytes of memory, and the gate accepted it |
| Runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384`, the one of `q1-2` |
| API image | `sha256:54f748844b71c6f563775678439ec44e5b59da9a27af8b5e36acac266c235c0f`, the manifest-list digest that this phase `up` declared. The build printed the image manifest `sha256:bba83fa7…` and the config `sha256:cd65ca24…`, those of `q1-2` |

## What ran

All instants are UTC, on 2026-10-17. The host instants are those that the driver printed.

1. **The phase `up`** of the Q1 driver ran without a change, from 15:14:32 to 15:25:40 (its
   start file, which the header states as `upStartedAt`, holds 15:14:35), with the work
   directory `q2run-3`. Both capacity readings were `ACCEPTED`. The import of the model seed
   image into the node took 236.6 s. The controller reported the Application `Synced` and
   `Healthy` at the revision `ed892a4`, with 2 API pods and 2 runtime pods Running.
2. **The characterization `q2-2`** ran from 15:25:49.516, its start instant, to
   15:28:43.265, the instant of its final header. Each of the 7 preconditions was held when
   the driver asked the tool, before the first restart. It then ran three restarts:

   | Restart | Requested | Rolled out | Watch stopped | Events in the stream |
   |---|---|---|---|---|
   | `r1` | 15:26:18.327 | 15:26:40.678 | 15:26:51.292 | 33 |
   | `r2` | 15:27:04.922 | 15:27:28.180 | 15:27:39.109 | 33 |
   | `r3` | 15:27:54.761 | 15:28:17.492 | 15:28:28.513 | 33 |

   Before each restart exactly 2 runtime pods existed at the first reading. After each
   restart the controller reported the Application `Synced` and `Healthy` at the revision
   `ed892a4`. Each replacement answered its one completion with HTTP status 200, and each
   completion ended by its limit of 16 tokens.
3. **The phase `down`** of the Q1 driver removed the Application, the controller, and the
   prerequisite layer, and ended at 15:30:32. The namespaces and the custom resource
   definitions after it were those before the phase `up`, and no persistent volume
   remained.

## The observations

Cluster timestamps, whole seconds. The two parts are from creation to the Initialized
condition, which includes the verification of the model by the `verify-model` init
container, and from Initialized to Ready.

| Restart | Order | Pod | Created | Initialized | Ready | Start to Ready | Created to Initialized | Initialized to Ready |
|---|---|---|---|---|---|---|---|---|
| `r1` | 1 | `inferops-inferops-llm-runtime-6dbbd68d5d-jd2vl` | 15:26:18 | 15:26:23 | 15:26:29 | 11,000 ms | 5,000 ms | 6,000 ms |
| `r1` | 2 | `inferops-inferops-llm-runtime-6dbbd68d5d-cl9gn` | 15:26:29 | 15:26:33 | 15:26:40 | 11,000 ms | 4,000 ms | 7,000 ms |
| `r2` | 1 | `inferops-inferops-llm-runtime-699f68c679-rbh5r` | 15:27:05 | 15:27:10 | 15:27:16 | 11,000 ms | 5,000 ms | 6,000 ms |
| `r2` | 2 | `inferops-inferops-llm-runtime-699f68c679-vjrjs` | 15:27:16 | 15:27:22 | 15:27:27 | 11,000 ms | 6,000 ms | 5,000 ms |
| `r3` | 1 | `inferops-inferops-llm-runtime-5884f795b4-qrvfl` | 15:27:55 | 15:27:59 | 15:28:06 | 11,000 ms | 4,000 ms | 7,000 ms |
| `r3` | 2 | `inferops-inferops-llm-runtime-5884f795b4-zdjg8` | 15:28:06 | 15:28:11 | 15:28:17 | 11,000 ms | 5,000 ms | 6,000 ms |

**S = 11,000 ms**, first observed for the first replacement of `r1`. All six observations
have that value. `q2-1`, of the earlier lineage, also stated S = 11,000 ms, from five
observations of 11,000 ms and one of 10,000 ms; the two records are of different
qualifications and are not combined.

## What this does not establish, and what to read with it

- **S is of this run's restarts only.** Each replacement started while the other runtime
  pod was Running and Ready, and while the pod it replaced was terminating, on a node that
  had loaded the model. This record does not establish the start of a pod on a node that
  has not loaded the model, after a restart of the node, or under caller traffic.
- **The interval is close to the probe period.** The readiness and startup probes run
  every 10 s, and every interval is 11 s. The record does not establish at what instant
  within the interval the runtime could first answer.
- **One second of resolution.** In each of the three restarts the second replacement was
  created in the same second as the first became Ready: 15:26:29, 15:27:16, and 15:28:06.
  The rule `one-at-a-time` holds for an equal second, so it held by an equal second each
  time, and the order within that second is not established.
- **What two rules hold is narrower than their statements**, as the page of `q2-1` states:
  `ready-serves` reads the content of each completion file, not when it was sent, and
  `environment-qualified` does not compare when the capacity reading was taken with the
  apply.
- **The API image digest that the build reports is another one at each build**, as for
  `q2-1`. The record holds the API Deployment to the digest that this phase `up` declared,
  not to the one of `q1-2`.
- **Two values are in the host's local time.** The annotation
  `kubectl.kubernetes.io/restartedAt` in the watch streams and the readings states the
  host's local time with its offset, `+05:00`, and the Helm output in the transcript states
  `LAST DEPLOYED` in local time. Every other instant of this page is UTC. The record reads
  neither value.
- No startup benchmark, no average, no percentile, no recovery time, and no availability.
  The Q4 bound record derives its bounds from S; this record states none.

## Not committed

`capacity/pods.json`, the capacity gate's read of every pod of the cluster, is not
committed: it holds container paths under a home directory in the controller's pods, as
for `q1-1`. Its SHA-256, with LF, is
`f8a0d16c80e11f40086981accdaab7466a984f517ce57167977d9a1526d65b7f`, and it held 267,727
bytes, as the operator measured them; no committed file corroborates either figure. The
capacity record of this directory therefore cannot be built again from the directory, and
the Q2 record does not read the file.
