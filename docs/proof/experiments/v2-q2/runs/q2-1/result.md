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
| API image | `sha256:218cc858ad7788c7b309140e8255d558100ca5ef06fe15cd7b48d059241dff9b`, the digest that the phase `up` declared. It is not the digest of `q1-1`: see below |

## What ran

All instants are UTC, on 2026-10-15. The host instants are those that the driver printed.

1. **The phase `up`** of the Q1 driver ran without a change, from 12:55:43 to 13:05:14,
   with the work directory `q2run-2`. The images and the model seed were
   already in the engine. The controller reported the Application `Synced` and
   `Healthy` at the revision `486ca49`, with 2 API pods and 2 runtime pods Running.
2. **The characterization `q2-1`** ran from 13:05:33.485 to 13:08:07.558. Each of the 7
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

- **These are warm restarts.** Each replacement started while the other runtime pod ran
  and held the model, on a node that had loaded the model for the pods before it. The
  interval from creation to Initialized took 3 s to 6 s, and from Initialized to Ready
  5 s to 8 s. For comparison only, each of the two first runtime pods of `q1-1`, which
  started after the model cache claim was filled, took 23 s from creation to Initialized
  and 28 s from Initialized to Ready, 51 s in all, by the same conditions of its pod. That reading is not a Q2 observation, and S does not use it. S does not establish
  the start time of a pod on a node that has not loaded the model, of a pod after a
  restart of the node, or of a pod under caller traffic. This record does not establish
  why these starts were shorter.
- **The interval is close to the probe period.** The readiness and startup probes run
  every 10 s, and every interval is 10 s or 11 s. The record does not establish at what
  instant within the interval the runtime could first answer.
- **One second of resolution.** In `r1` the second replacement was created in the same
  second, 13:06:03, as the first became Ready. The rule `one-at-a-time` holds for an
  equal second, so it does not establish the order within that second.
- **The detail of `release-qualified` overstates.** It reads "release … with the images of
  q1-1". Under revision 2 the API image is the digest that the phase `up` declared, which
  is not the digest of `q1-1`; the runtime image is the one of `q1-1`. The statement of
  the rule is right; its detail string is a defect of the tool, kept as the record
  states it because the tool is a pinned input of revision 2.
- **The API image digest is another one at each build.** Three builds of the same inputs
  reported three digests: `5b4be2da…` for `q1-1`, `cf30eac7…` for the work directory
  `q2run-1` at the first commit of this change, and `218cc858…` here. This is why
  revision 1 was superseded before any characterization. This record does not establish
  that the API image content is the content that `q1-1` ran.
- No startup benchmark, no average, no percentile, no recovery time, no availability, and
  no bound derived from S.

## Not committed

`capacity/pods.json`, the capacity gate's read of every pod of the cluster, is not
committed: it holds container paths under a home directory in the controller's pods, as
for `q1-1`. Its SHA-256, with CRLF read as LF, is
`1ea86633b30fcc61790b3d5b586753529178309da6d5ede237c6629913ec61ba`. The record does not
read it. The work directory `q2run-1` of the first commit, whose phase `up` ran and whose
characterization did not, is not committed either; [the validation
record](../../../../environment/v2-s6-002-pr1-validation.md) states what it showed.
