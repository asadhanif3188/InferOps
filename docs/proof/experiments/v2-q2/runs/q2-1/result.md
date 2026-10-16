# Q2 characterization `q2-1`: CHARACTERIZED, S = 11,000 ms

Status: **`CHARACTERIZED`. Each of the 16 rules of [freeze revision 2](../../freeze-r2.v1alpha1.json)
held. S, the maximum interval from the creation of a replacement runtime pod to its first
Ready condition, is 11,000 ms, at a resolution of 1,000 ms.** Evidence level C2, bounded
to one environment: the docker-desktop provider with one node, the environment that
[`q1-1`](../../../v2-q1/runs/q1-1/result.md) selected. It is a qualification and not a
result of a reliability experiment. S is not a startup benchmark, and no claim cites it.

| Property | Value |
|---|---|
| Record | [`record.v1alpha1.json`](record.v1alpha1.json), built by `tools/runtime_startup` |
| Header | [`run.json`](run.json) |
| Transcript | [`transcript.txt`](transcript.txt): the phases `up`, `characterize`, and `down`, with the absolute path of the host replaced by `<repository>` |
| Freeze record | `docs/proof/experiments/v2-q2/freeze-r2.v1alpha1.json`, SHA-256 `32e58c7984ad74ef229e5a2d3411e7de78971b17a554124a7fbe3acfe5bcaecd` |
| Executing commit | `65bd9bb0629e047cdf23242754dc37179f420439`, for the phase `up` and the characterization |
| Desired revision | `486ca49ae99ed7257a503e291d5710be88f7ce26`, the remote main |
| Release | `local-docker-desktop/support-assistant`, identifier `b5457f49092c578496738973a8786a95428517e7ddf755303b4f6842dcb8c9db`, the one of `q1-1` |
| Environment | `sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461`, the one of `q1-1`: Kubernetes `v1.36.1`, one node `desktop-control-plane` |
| Runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384`, the one of `q1-1` |
| API image | `sha256:218cc858ad7788c7b309140e8255d558100ca5ef06fe15cd7b48d059241dff9b`, the manifest-list digest that the phase `up` declared. It is not the manifest-list digest of `q1-1`; the image manifest and the config that the build printed are those of `q1-1`: see below |

## What ran

All instants are UTC, on 2026-10-15. The host instants are those that the driver printed.

1. **The phase `up`** of the Q1 driver ran without a change, from 12:55:43, the first instant it printed, to 13:05:14 (its start file, which the header states as `upStartedAt`, holds 12:55:45),
   with the work directory `q2run-2`. The images and the model seed were
   already in the engine. The controller reported the Application `Synced` and
   `Healthy` at the revision `486ca49`, with 2 API pods and 2 runtime pods Running.
2. **The characterization `q2-1`** ran from 13:05:33.485, its start instant, to 13:08:07.558, the instant of its final header; the driver printed its last instant, 13:08:09.049, after it built the record. Each of the 7
   preconditions was held when the driver asked the tool, before the first restart. It
   then ran three restarts:

   | Restart | Requested | Rolled out | Watch stopped | Events in the stream |
   |---|---|---|---|---|
   | `r1` | 13:05:52.389 | 13:06:15.018 | 13:06:25.642 | 33 |
   | `r2` | 13:06:40.216 | 13:07:02.341 | 13:07:12.754 | 34 |
   | `r3` | 13:07:24.836 | 13:07:46.679 | 13:07:57.087 | 32 |

   After each restart the controller reported the Application `Synced` and `Healthy` at
   the revision `486ca49`. Each replacement answered its one completion with HTTP status
   200, and each completion ended by its limit of 16 tokens.
3. **The phase `down`** of the Q1 driver removed the Application, the controller, and the
   prerequisite layer, and ended at 13:09:53. The namespaces and the custom resource
   definitions after it were those before the phase `up`.

## The observations

Cluster timestamps, whole seconds. The two parts are from creation to the Initialized
condition, which includes the verification of the model by the `verify-model` init
container, and from Initialized to Ready.

| Restart | Order | Pod | Created | Initialized | Ready | Start to Ready | Created to Initialized | Initialized to Ready |
|---|---|---|---|---|---|---|---|---|
| `r1` | 1 | `inferops-inferops-llm-runtime-c9fcd6cd8-rfhsh` | 13:05:52 | 13:05:56 | 13:06:03 | 11,000 ms | 4,000 ms | 7,000 ms |
| `r1` | 2 | `inferops-inferops-llm-runtime-c9fcd6cd8-qfxz7` | 13:06:03 | 13:06:06 | 13:06:14 | 11,000 ms | 3,000 ms | 8,000 ms |
| `r2` | 1 | `inferops-inferops-llm-runtime-b8c4486d-pp9wj` | 13:06:40 | 13:06:45 | 13:06:51 | 11,000 ms | 5,000 ms | 6,000 ms |
| `r2` | 2 | `inferops-inferops-llm-runtime-b8c4486d-zp7cg` | 13:06:51 | 13:06:55 | 13:07:02 | 11,000 ms | 4,000 ms | 7,000 ms |
| `r3` | 1 | `inferops-inferops-llm-runtime-5968885f85-glfcb` | 13:07:25 | 13:07:29 | 13:07:35 | 10,000 ms | 4,000 ms | 6,000 ms |
| `r3` | 2 | `inferops-inferops-llm-runtime-5968885f85-bm9n8` | 13:07:35 | 13:07:41 | 13:07:46 | 11,000 ms | 6,000 ms | 5,000 ms |

**S = 11,000 ms**, first observed for the first replacement of `r1`. Five of the six
observations have that value.

## What this does not establish, and what to read with it

- **S is of this run's restarts only.** Each replacement started while the other runtime
  pod was Running and Ready, and while the pod it replaced was terminating. The interval
  from creation to Initialized took 3 s to 6 s, and from Initialized to Ready 5 s to 8 s.
  The two first runtime pods of the same phase `up`, which the watch of `r1` lists, were
  created at 13:04:41, Initialized at 13:04:47, and Ready at 13:05:02: 21 s, outside the
  restarts and not an observation of Q2. For comparison only, each of the two first
  runtime pods of `q1-1` took 23 s from creation to Initialized and 28 s from Initialized
  to Ready, 51 s in all, by the same conditions of its pod. S does not use either reading.
  This record does not establish why the starts differ, or the start of a pod on a node
  that has not loaded the model, after a restart of the node, or under caller traffic.
- **The interval is close to the probe period.** The readiness and startup probes run
  every 10 s, and every interval is 10 s or 11 s. The record does not establish at what
  instant within the interval the runtime could first answer.
- **One second of resolution.** In each of the three restarts the second replacement was
  created in the same second as the first became Ready: 13:06:03, 13:06:51, and 13:07:35.
  The rule `one-at-a-time` holds for an equal second, so it held by an equal second each
  time, and the order within that second is not established in any restart.
- **What two rules hold is narrower than their statements.** `ready-serves` reads the
  content of each completion file; it does not read when the completion was sent or
  through which port-forward. That the completions followed each rollout is shown by the
  order of the driver's steps and by the transcript, not by the rule. `environment-qualified`
  does not compare when the capacity reading was taken with the apply; the order is the
  order of the phase `up`.
- **The detail of `release-qualified` overstates.** It reads "release … with the images of
  q1-1". Under revision 2 the API image is the manifest-list digest that the phase `up`
  declared, which is not the one of `q1-1`; the runtime image is the one of `q1-1`. The
  rule's statement is right. The detail string is a defect of the tool, kept as the
  record states it because the tool is a pinned input of revision 2.
- **The API image digest that the build reports is another one at each build.** Three
  builds of the same inputs reported three manifest-list digests: `5b4be2da…` for `q1-1`,
  `cf30eac7…` for the work directory `q2run-1` at the first commit of this change, and
  `218cc858…` here. Each of the three builds printed the same image manifest,
  `sha256:bba83fa7119d827f3a7c9f5e7803f8db430797f9dabdd2326b338283e005a5e5`, and the same
  config, `sha256:cd65ca24f46a237b862b68b47e1f605a146ae52e875c8e6ca8118024c27cccd2`; the
  attestation manifest differed. That is what the build printed. No tool compares those
  lines, and the record does not hold the API image to them. This is why revision 1 was
  superseded before any characterization.
- **Two values are in the host's local time.** The annotation
  `kubectl.kubernetes.io/restartedAt`, which `kubectl rollout restart` writes into the
  pod template, states the host's local time with its offset, `+05:00`, in the watch
  streams and the readings of `r2` and `r3`. The Helm output in the transcript states
  `LAST DEPLOYED` in local time. Every other instant of this page is UTC. The record does
  not read either value.
- No startup benchmark, no average, no percentile, no recovery time, no availability, and
  no bound derived from S.

## Not committed

`capacity/pods.json`, the capacity gate's read of every pod of the cluster, is not
committed: it holds container paths under a home directory in the controller's pods, as
for `q1-1`. That statement cannot be checked from the committed files. Its SHA-256, with
CRLF read as LF, is `1ea86633b30fcc61790b3d5b586753529178309da6d5ede237c6629913ec61ba`,
and it held 267,725 bytes; no committed file corroborates either figure. The capacity
record of this directory therefore cannot be built again from the directory, and the
Q2 record does not read the file. The work directory `q2run-1` of the first commit,
whose phase `up` ran and whose characterization did not, is not committed either; [the
validation record](../../../../environment/v2-s6-002-pr1-validation.md) states what it
showed.
