# V1-S0-003-PR2 runtime and model feasibility

Date: 2026-08-24

Classification: **local real runtime**, redacted. A model was downloaded and hash-
verified, a serving runtime was started in a Kubernetes cluster, and it answered
inference requests from inside that cluster. Nothing in the verdict table below is
mock, synthetic, or estimated; every figure is labelled measured, derived, or
documented at the point it appears.

Authorisation: the host owner authorised the download and workload stages on
2026-08-24, in the session that ran them, and directed that the trial use the
Kubernetes cluster the container desktop distribution already runs rather than
create a second one. That direction is honoured and its consequences are recorded
in [claim boundary](#claim-boundary) and [limitations](#limitations).

## Claim boundary

This record establishes that **one** runtime image digest can serve **one** model
revision on **one** host, inside a real Kubernetes cluster, reached through cluster
DNS and a Service, and that the result meets all but one of the thresholds
[ADR 0002](../../architecture/decisions/ADR-0002-model-and-serving-runtime.md) fixed
before the trial began.

It does not establish anything about throughput, concurrency, model quality, any
other host, any other model, or production behaviour. Every request in it is
single, sequential, and small.

Two departures from
[the feasibility workflow](../../serving/feasibility-workflow.md) as it was written
before this run are material, and neither is buried:

1. **The cluster is not the project's own.** The trial ran in the single-node
   cluster the container desktop distribution provides, not in `inferops-dev`. The
   isolation ADR 0001 D5 asks for was delivered by a dedicated `inferops-`
   namespace, which was created and deleted by the trial. The cost is real and
   appears in exactly one place: any measurement of *total* host memory is
   contaminated by unrelated workloads that cluster already hosted, so the
   whole-VM half of `T3` is reported as an upper bound rather than as this
   candidate's footprint. The per-pod half is unaffected, because a cgroup does not
   care what else is running.
2. **`T7` is not met as written.** That is a blocking threshold. It is discussed at
   [T7](#t7-metrics-the-one-threshold-that-failed) rather than smoothed over, and
   it is the reason ADR 0002 is accepted with a named exception rather than
   accepted outright.

## Verdict

| Threshold | Verdict | Measured or observed | Note |
|---|---|---|---|
| T1 licence | **Met** | Runtime MIT; model Apache-2.0. Both licence texts read in full on 2026-08-24 | No acceptable-use policy, field-of-use limit, user-count clause, or download gate in either |
| T2 immutable pins | **Met** | Image `sha256:100de626…`, read back from the running pod; model revision `90862c4b…`; weight SHA-256 verified after download | The pin was verified against what ran, not against what was requested |
| T3 memory fit | **Met** | Pod 2.167 GiB against a 3.0 GiB limit; container VM ~3.75 GiB of 7.60 GiB | Only 555 MiB of the pod figure is anonymous. See [the memory reading](#the-memory-figure-is-not-what-it-looks-like) |
| T4 disk fit | **Met** | 1.71 GiB weights + 293.0 MiB image = ~2.0 GiB added, against an 8 GB budget | Host free space did not fall below the 5 GB floor at any point |
| T5 API shape | **Met** | `choices[0].message.content`, `model`, and `usage` token counts all present | `GET /v1/models` reports the pinned model |
| T6 readiness semantics | **Met** | Kubelet recorded `Startup probe failed: HTTP probe failed with statuscode: 503` during load; 0 restarts across 7 starts | The three-probe mapping ADR 0002 proposed works as proposed |
| T7 metrics | **Not met as written** | Token counters present; **no cumulative request counter** — only `requests_processing` and `requests_deferred` gauges | Blocking. See [T7](#t7-metrics-the-one-threshold-that-failed) |
| T8 startup | **Met** | Worst case 14 s; best 5 s, across seven process-fresh starts | Targets were 180 s and 90 s. A page-cache-cold start could not be produced on this host; see [failures](#failures-surprises-and-corrections) |
| T9 latency floor | **Met** | 128-token completion, worst case 14.52 s, decode 8.81 tokens/s | Targets were 120 s and 2 tokens/s |
| T10 packaging and cleanup | **Met** | Non-root uid 65534, no privilege escalation, all capabilities dropped, read-only root, no host mount; scoped teardown left no residue | Writable layer used 12,288 bytes across the whole run |
| T11 no credential required | **Met** | Every artifact fetched anonymously; no account, key, or licence acceptance at any point | |
| T12 CPU path complete | **Met** | AVX2 without AVX-512; no accelerator of any kind involved | No GPU path is described, so none is claimed |

**Overall: candidate accepted with one recorded exception.** Eleven thresholds are
met, including every step-down threshold with substantial margin. One blocking
threshold, `T7`, is not met as written. ADR 0002 records that failure, argues why it
does not disqualify the pair, and narrows the threshold for future trials. The
argument is in the ADR so that a reader who disagrees with it can find and attack
it in one place.

## Environment

Repeated here even though other records state it, because a record that cannot be
read on its own is not evidence.

| Component | Version or value | Source |
|---|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` | Measured |
| Container engine server | `29.3.1`, API `1.54`, `linux/amd64` | Measured |
| Engine storage driver | `overlayfs` | Measured |
| Engine cgroup version | 1 | Measured |
| Engine kernel | `5.15.146.1-microsoft-standard-WSL2` | Measured |
| Cluster | The container desktop distribution's own single-node cluster | Measured |
| Node OS image | Debian GNU/Linux 12 (bookworm) | Measured, reported by the node |
| Node container runtime | `containerd://2.2.0` | Measured, reported by the node |
| kubectl client / server | `v1.34.1` / `v1.34.3`; skew 0 | Measured |
| Memory reaching the container VM | **7.60 GiB** (`8158400512` bytes) | Measured |
| Processors reaching the container VM | 20 | Measured |
| Processor | 13th Gen Intel Core i7-13700H | Measured |
| CPU instruction set | AVX2, F16C, FMA present; **no AVX-512** | Measured, read from the VM's own processor information |
| Accelerator | None discrete; none used | Measured |
| Free space on target volume, before | ~24 GB on the volume holding the engine's virtual disk | Measured |

Host name, user account, filesystem paths, and network addresses are excluded, the
same way [the cluster smoke proof](../environment/v1-s0-002-pr2-cluster-smoke.md)
excludes them.

The engine reports **cgroup v1**, and containerd emits a deprecation warning on
every operation:

```text
DEPRECATION: The support for cgroup v1 is deprecated since containerd v2.2 and
will be removed by no later than May 2029. Upgrade the host to use cgroup v2.
```

Everything below worked on cgroup v1. Recorded as a dated risk, not a defect —
and it is the same warning ADR 0001's evidence already carries.

## Pins

| Artifact | Identifier | Verified how |
|---|---|---|
| Runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` | Resolved from tag `server` on 2026-08-24; **read back from the running pod's `imageID`** |
| Runtime image, amd64 child | `sha256:fa09617a8e077f327dbf823fc1bafecc82c1bff6503a53416d8c2197d86c85ba` | Read from the OCI index |
| Runtime build | `b10588`, source revision `70adb1b4cea5ee39f867792c78dc59320921eda7`, image created `2026-08-23T04:32:14Z` | Read from the image's own OCI labels |
| Runtime version, self-reported | `0.2.0-dev (build 10588, commit 70adb1b4c)`, built with GNU 14.2.0 for Linux x86_64 | Measured, by running the binary |
| Runtime licence | MIT | Read in full at revision `70adb1b4c…` on 2026-08-24 |
| Model repository | `Qwen/Qwen3-1.7B-GGUF` | |
| Model revision | `90862c4b9d2787eaed51d12237eafdfe7c5f6077` | Resolved on 2026-08-24; every fetch used the revision, never a branch name |
| Weight file | `Qwen3-1.7B-Q8_0.gguf`, `1834426016` bytes, SHA-256 `061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` | **Hash verified after download**, in the cluster, before the file was ever mounted for serving |
| Model licence | Apache-2.0 | Read in full at that revision on 2026-08-24 |

The image was deployed **by digest**, and the digest the cluster reported for the
running container was compared against the digest the manifest asked for. They
match. A pin that is never read back is a hope, not a pin.

### Licence checks, in full rather than by summary

`T1` requires reading the licence text rather than a badge. Both were read.

- **Runtime**: MIT, 21 lines, no additional terms, no acceptable-use policy.
- **Model**: the Apache License 2.0, 201 lines. Searched for the clause shapes that
  disqualify a licence under `T1` — acceptable-use policy, field-of-use limit,
  monthly-active-user threshold, naming obligation. The only phrase matched was
  `you may not use this file except in compliance with the License`, which is line
  193 of the standard Apache appendix and is not a restriction of that kind.
- The model repository reports `gated: false`, and an anonymous request for the
  weight file returned `200` with the full content length. No account, token, or
  click-through exists on this path.

## Commands and results

Every command below was run against the cluster named in the environment table.
Output is reproduced as the tools emitted it, with host-specific values removed and
each removal marked.

### Stage 1 — resolve the pins

The tag was resolved to an index digest through the registry's own manifest
endpoint, and the model revision and file hash through the publisher's metadata:

```text
docker manifest inspect ghcr.io/ggml-org/llama.cpp:server
  -> index with linux/amd64, linux/arm64, linux/s390x children
docker-content-digest: sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384

model revision: 90862c4b9d2787eaed51d12237eafdfe7c5f6077
Qwen3-1.7B-Q8_0.gguf  1834426016  061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a
```

### Stage 2 — acquire the weights

```text
kubectl apply -f deploy/serving/feasibility/weights.yaml
kubectl -n inferops-serving-feasibility logs job/fetch-weights
```

```text
wget: note: TLS certificate validation not implemented
wget: connection closed prematurely
attempt 1 interrupted; resuming
attempt 1: 353249411/1834426016 bytes
wget: note: TLS certificate validation not implemented
attempt 2: 1834426016/1834426016 bytes
transfer elapsed: 1150s over 2 attempt(s)
expected bytes: 1834426016
actual bytes:   1834426016
hashing /models/Qwen3-1.7B-Q8_0.gguf (this reads the whole file)
expected sha256: 061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a
actual sha256:   061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a
WEIGHTS_VERIFIED_OK
```

Elapsed 1150 s over two attempts. Bytes transferred 1,834,426,016. Two things in
that transcript are findings rather than noise, and both are covered under
[failures](#failures-surprises-and-corrections).

### Stage 3 — deploy

```text
kubectl apply -f deploy/serving/feasibility/llama-server.yaml
```

Resolved image digest **as the cluster reports it**, not as the manifest asked:

```text
imageID: ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384
```

Security context as applied:

```text
pod:       runAsNonRoot=true runAsUser=65534 runAsGroup=65534 fsGroup=65534
           seccompProfile=RuntimeDefault
container: allowPrivilegeEscalation=false readOnlyRootFilesystem=true
           capabilities.drop=[ALL]
```

Requests and limits as applied: `requests cpu=1 memory=2Gi`,
`limits cpu=6 memory=3Gi`.

The container's writable layer used **12,288 bytes** across the entire run. The
read-only root filesystem is doing what it claims to.

### Stage 4 — load and readiness

The workflow defines a cold run as *weights present, process fresh*. Every row
below satisfies that: the pod is deleted and the Deployment replaces it, so the
process is new and the weight file is already on the volume.

| Run | Kind | Container start to first ready | Not-ready observed during load | Restarts during load |
|---:|---|---:|---|---:|
| 1 | First start after acquisition | **14 s** | **Yes** — kubelet recorded a 503 from the startup probe | 0 |
| 2 | Process-fresh | 5 s | Not observed; the first probe at 5 s already succeeded | 0 |
| 3 | Process-fresh | 5 s | Not observed, same reason | 0 |
| 4 | Process-fresh | 5 s | Not observed, same reason | 0 |

Worst case: **14 s**, against a `T8` target of 180 s. Best case 5 s, against a warm
target of 90 s. Both with a wide margin, and the margin is the point: the startup
probe budget of 300 s configured in the manifest is roughly twenty times the worst
observed load, which is the right direction for a probe budget to be wrong in.

**Zero restarts across all four starts, and across the three further starts made
during resource measurement — seven in total.** That is the `T6` result that
matters most: the probe mapping ADR 0002 proposed keeps a slow load from
restarting the pod.

The not-ready transition was captured directly from the control plane rather than
by polling:

```text
Warning  Unhealthy  pod/llama-server-<suffix redacted>
  Startup probe failed: HTTP probe failed with statuscode: 503
```

That single line is the whole of `T6`'s first half: the endpoint reported 503 while
the model loaded, the startup probe absorbed it, the liveness probe — pointed at
the TCP socket rather than at `/health` — never fired, and the pod was never
restarted. Runs 2 to 4 do not reproduce the 503 because a 5 s load finishes before
the probe's first 5 s tick. Their absence of a 503 is a timing artifact and is not
evidence that the endpoint stopped reporting one.

Model identity as the runtime reports it, from `GET /v1/models`:

```text
id: qwen3-1.7b-q8_0        n_ctx: 4096        n_ctx_train: 40960
n_params: 1720574976       size: 1828474880   ftype: Q8_0
n_vocab: 151936
```

and from `GET /props`:

```text
model_path: /models/Qwen3-1.7B-Q8_0.gguf
model_ftype: Q8_0        total_slots: 4        build_info: b10588-70adb1b4c
```

**Does it match the pinned revision?** Partly, and the distinction matters. The
`id` is the alias this trial passed on the command line, so the runtime echoing it
proves the flag was accepted and nothing more. What does tie the running process to
the pinned bytes is the combination of: the SHA-256 verified on the file before it
was mounted, the file being mounted read-only from the same volume, and the
runtime's self-reported parameter count and quantisation matching the published
model. The runtime exposes no hash of the file it loaded, so there is no single
check that closes this — which is itself worth knowing.

### Stage 5 — one real inference

Requested from inside the cluster, through cluster DNS and the Service:
**yes**. Every request below went to
`http://llama-server.inferops-serving-feasibility.svc.cluster.local:80`. No
port-forward was used, because a port-forward would have proven that `kubectl` can
tunnel to a pod rather than that the platform's own path works.

Request, verbatim:

```json
{"model":"qwen3-1.7b-q8_0",
 "messages":[{"role":"user","content":"In one sentence, what is Kubernetes?"}],
 "temperature":0,"max_tokens":128,
 "chat_template_kwargs":{"enable_thinking":false}}
```

Response, verbatim, from the first run:

```json
{"choices":[{"finish_reason":"stop","index":0,"message":{"role":"assistant",
 "content":"Kubernetes is an open-source platform for automating the deployment, scaling, and management of containerized applications."}}],
 "created":1787552435,"model":"qwen3-1.7b-q8_0",
 "system_fingerprint":"b10588-70adb1b4c","object":"chat.completion",
 "usage":{"completion_tokens":23,"prompt_tokens":20,"total_tokens":43,
 "prompt_tokens_details":{"cached_tokens":0}},
 "id":"chatcmpl-<redacted>",
 "timings":{"cache_n":0,"prompt_n":20,"prompt_ms":771.268,
 "predicted_n":23,"predicted_ms":3211.39,"predicted_per_second":6.850616088360492}}
```

The prompt is fixed, neutral, and contains no host detail and no personal data.
The response is a plain factual sentence. Both are safe to publish, which is why
they were chosen. Only the generated completion identifier is redacted.

At temperature 0 the three runs returned **byte-identical content**, which is the
determinism the setting is supposed to give and is worth recording as observed
rather than assumed.

| Run | Wall clock | Completion tokens reported | Derived decode rate |
|---:|---:|---:|---:|
| 1 | 4.00 s | 23 | 6.85 tokens/s (derived) |
| 2 | 3.28 s | 23 | 7.20 tokens/s (derived) |
| 3 | 2.56 s | 23 | 9.03 tokens/s (derived) |

Those three stopped naturally at 23 tokens, so they do **not** exercise the
"128-token completion" that `T9` is written against. Rather than report a
128-token threshold as met on a 23-token sample, the threshold was tested
directly, by setting `ignore_eos` so the runtime must emit the full budget:

| Run | Wall clock | Completion tokens reported | Derived decode rate |
|---:|---:|---:|---:|
| 1 | 14.01 s | 128 | 9.21 tokens/s (derived) |
| 2 | 13.73 s | 128 | 9.35 tokens/s (derived) |
| 3 | 14.52 s | 128 | 8.81 tokens/s (derived) |

Worst case **14.52 s** against a 120 s limit, and **8.81 tokens/s** against a
2 tokens/s floor. `T9` is met on the measurement it was written for.

The decode rate is derived from the runtime's reported token counts and the
measured wall clock. It describes one model, one quantisation, one host, one
thread count, and one day. **It is not a benchmark and must not be published as
one.**

Response shape against `T5`: `choices[0].message.content` **present** and
non-empty; `model` **present**; `usage` token counts **present**, carrying
`prompt_tokens`, `completion_tokens`, and `total_tokens`.

### Stage 6 — metrics

Scraped from `GET /metrics` on the same endpoint, in Prometheus text format, with
no exporter and no sidecar. The complete set of series, by name:

```text
llamacpp:prompt_tokens_total                   22
llamacpp:prompt_tokens_cached_total            38
llamacpp:prompt_seconds_total                  1.03879
llamacpp:tokens_predicted_total                69
llamacpp:tokens_predicted_seconds_total        8.70398
llamacpp:n_decode_total                        69
llamacpp:n_tokens_max                          42
llamacpp:spec_decode_num_draft_tokens_total    0
llamacpp:spec_decode_num_accepted_tokens_total 0
llamacpp:spec_decode_num_drafts_total          0
llamacpp:prompt_tokens_seconds                 21.1784
llamacpp:predicted_tokens_seconds              7.58274
llamacpp:requests_processing                   0
llamacpp:requests_deferred                     0
llamacpp:n_busy_slots_per_decode               1
```

| Required series | Present | Exact name |
|---|---|---|
| Request counter | **No** | None. `requests_processing` and `requests_deferred` are gauges of instantaneous state, not cumulative counts |
| Prompt token counter | Yes | `llamacpp:prompt_tokens_total` |
| Completion token counter | Yes | `llamacpp:tokens_predicted_total` |

Series required but absent: **a cumulative request counter.**

#### T7 metrics: the one threshold that failed

`T7` asks for "at least request and token counters". The token counters are there
and are real counters. There is no request counter of any kind — the two series
with `requests` in the name are gauges, and a gauge that reads 0 between requests
cannot be summed, rated, or alerted on the way a counter can.

This is a **blocking** threshold, and it is recorded as failed. What follows is an
argument about the consequence, not about the finding:

- The rationale ADR 0002 gave for `T7` was that "a metric that needs a third-party
  exporter is that exporter's evidence, not the runtime's". That concern is fully
  satisfied — these series come from the runtime itself.
- The missing series is a count of requests. InferOps is the component that will
  sit in front of this runtime and receive those requests, so it is the natural and
  correct place to count them. Closing this gap needs no exporter, no sidecar, and
  no change to the runtime.
- Rejecting the pair on this would send the trial to vLLM, whose own documentation
  places its CPU path on a degraded footing on a host without AVX-512, in exchange
  for a counter the platform can emit itself.

The threshold as written was therefore too broad: it bundled "the runtime exposes
native metrics" with "the runtime counts requests", and only the first is properly
the runtime's job. ADR 0002 narrows it and records that it was narrowed **after**
seeing the measurement, which is the honest but weaker position. A reader who
thinks the original threshold should have been enforced as written has everything
needed here to say so.

### Stage 7 — resources

#### The memory figure is not what it looks like

The pod's memory was read from its own cgroup on the node, because this cluster
runs no metrics server and `crictl stats` reports no memory on cgroup v1. Two pods
running the identical image, arguments, and weight file produced figures four times
apart, and the difference is the most useful thing this stage found.

| Measurement | First pod | A later, process-fresh pod |
|---|---:|---:|
| `memory.usage_in_bytes` | 2,326,966,272 (**2.167 GiB**) | 556,961,792 (**531 MiB**) |
| `memory.max_usage_in_bytes` | 2,327,216,128 | 561,078,272 |
| `total_rss` | 582,205,440 (555 MiB) | 551,153,664 (526 MiB) |
| `total_cache` | 1,737,183,232 (1.618 GiB) | 8,192 |
| `total_mapped_file` | 1,716,146,176 (1.598 GiB) | 0 |
| Limit applied | 3,221,225,472 (3.0 GiB) | 3,221,225,472 (3.0 GiB) |

Both pods served correctly. The explanation is that the runtime **memory-maps** the
weight file rather than reading it into anonymous memory, and under cgroup v1 a
page of file cache is charged to whichever cgroup first faults it in. The first pod
faulted 1.6 GiB of weight pages and was charged for them. Later pods found those
pages already resident and were charged nothing for them.

So the honest reading of `T3` is two numbers, not one:

- **The runtime's private memory is about 531 MiB**, idle and immediately after
  serving a 128-token completion — the two readings differ by 344 KiB.
- **The worst-case charge against a pod's limit is 2.167 GiB**, when that pod is
  the one that faults the weights in.

Both are under the 3.0 GiB target, so `T3` is met either way, and **2.167 GiB is
the figure to size a limit against**, because a pod must survive being the one that
pays. The consequence for anyone setting `limits.memory` is not obvious and is
worth stating: set it too close to the private figure and the kernel will not
OOM-kill the pod, it will evict the model's own pages and re-read them from disk,
turning a memory limit into a silent latency problem.

Whole-VM memory, with the cluster and the serving pod running:

| Measurement | Value |
|---|---|
| Total in the container VM | 7,780 MiB (7.60 GiB) |
| Available | 3,853 MiB |
| Consumed, derived as total minus available | ~3,927 MiB (**~3.83 GiB**) |

Against the `T3` ceiling of 6.0 GiB, that passes — but this figure **includes
unrelated workloads** already running in the shared cluster, so it is an upper
bound on this candidate's contribution and not a measurement of it. It is reported
because an upper bound that passes is still informative; it is labelled because an
upper bound presented as a measurement would not be.

#### Disk

| Item | Value | Source |
|---|---|---|
| Runtime image, as containerd stores it | 293.0 MiB | Measured |
| Weight file on disk | 1,834,426,016 bytes (1.71 GiB) | Measured |
| Container writable layer, whole run | 12,288 bytes | Measured |
| Total added | **~2.0 GiB** | Derived |
| `T4` budget | 8 GB | ADR 0002 |
| Free space on the host volume, before and after | ~24 GB, never approaching the 5 GB floor | Measured |

`df` **inside** the cluster reported 861.1 GB free before acquisition and 859.6 GB
after. Those numbers are worthless for `T4` and are recorded only to warn the next
person: the container VM's filesystem is a sparse virtual disk whose apparent size
has no relationship to the space actually available on the host volume backing it.
The workflow's free-space bound now says so explicitly.

### Stage 8 — teardown and residue

Teardown was scoped to the one namespace the trial created:

```text
kubectl delete namespace inferops-serving-feasibility --wait=true
namespace "inferops-serving-feasibility" deleted
```

Residue was then verified rather than assumed, the way ADR 0001 D6 requires:

```text
kubectl get ns
  -> inferops-serving-feasibility absent; the pre-existing namespaces are untouched

kubectl get all,pvc,pv -A -l app.kubernetes.io/part-of=inferops
  -> No resources found

kubectl get pv
  -> the trial's PersistentVolume is gone; only volumes belonging to
     workloads that predate this trial remain

ls -d /var/local-path-provisioner/*model-weights*   (on the node)
  -> NO RESIDUE: provisioner directory removed
```

**Residue found: none.** No object carrying the project label survives anywhere in
the cluster, and nothing the trial created outlived its namespace.

| State after teardown | Value |
|---|---|
| Container VM memory in use | 3,172 MiB, against a 3,279 MiB reading taken before the trial began |
| Runtime image, still cached | 293.0 MiB — survives by design, like the node image cache |
| Weight file | **Gone.** Deleted with the namespace |
| Free space on the host volume | ~24 GB, unchanged at the granularity the tool reports |

**Surviving by design:** the runtime image only.

**Not surviving, and this is a correction to the workflow rather than a
result:** the workflow stated that cached weights survive teardown the way the
cached node image does. They did not. This trial put the weights in a
PersistentVolumeClaim inside the trial's own namespace, whose storage class
reclaims on delete, so scoped teardown destroyed 1.71 GiB that cost 19 minutes to
fetch. Anyone re-running this pays that cost again. The workflow's prerequisite has
been corrected to say that the cache location decides this, and that a cache inside
the namespace is a cache the teardown eats.

## Step-down

Did any step-down threshold fail? **No.**

`T3`, `T4`, `T8`, and `T9` all passed on the first candidate, so the step-down to
Qwen3-0.6B was never triggered and Qwen3-0.6B remains untested by this project. The
margins were wide enough — 14 s against 180 s, 14.52 s against 120 s, 2.167 GiB
against 3.0 GiB, ~2.0 GiB against 8 GB — that the proposed primary was never in
difficulty on resources. The only threshold that gave trouble was the one nobody
expected to, `T7`.

## Failures, surprises, and corrections

A record with nothing in this section is usually incomplete rather than perfect.
Six things went wrong or came out differently than the plan assumed.

1. **The weight transfer did not survive one request.** The first attempt closed
   prematurely at 353,249,411 of 1,834,426,016 bytes. The fetch was made resumable
   and bounded, and completed on the second attempt: 1150 s in total. The original
   manifest, which issued a single unresumable `GET`, is not in this change — it
   never worked.
2. **The 30-minute stage bound was the wrong tool for a download.** It was written
   for an unbounded wait on a state change and would have failed a 1.71 GiB
   transfer for being slow on a domestic connection, which measures the
   contributor rather than the candidate. The workflow now bounds bulk transfer by
   size and retry count instead.
3. **`df` inside the cluster is not a disk measurement.** It reported 861.1 GB
   free on a sparse virtual disk whose backing host volume had roughly 24 GB. Had
   `T4` been evaluated on the in-container figure it would have passed for entirely
   fictional reasons.
4. **The downloader does not validate TLS certificates**, and says so:
   `wget: note: TLS certificate validation not implemented`. The transport is
   therefore unauthenticated and the published SHA-256 is carrying the whole
   integrity argument. That is exactly the job `T2`'s per-file hash requirement was
   written for, and it is the reason the hash is verified before the file is ever
   mounted for serving rather than after.
5. **Pod memory is not a stable number for this runtime.** Two identical pods
   reported 2.167 GiB and 531 MiB. Neither reading is wrong; see
   [the memory reading](#the-memory-figure-is-not-what-it-looks-like). A record
   that had measured only one pod would have published a confident figure that the
   next measurement would have contradicted.
6. **A page-cache-cold start could not be produced on this host.** Dropping the
   VM's page cache was attempted with a 240 s bound and did not return
   (`rc=124`); `buff/cache` was unchanged afterwards. Every start time in this
   record is therefore a process-fresh start with the weight file's pages possibly
   still resident, which is the workflow's definition of cold but not the
   strictest reading of it. A genuinely cold-cache figure is **not measured**, and
   `T8`'s 14 s worst case should be read as a floor rather than as the worst a
   first-ever start can do.

One further correction belongs here because it was caught in review of this record
rather than in the run: an earlier draft of the verdict table carried a cold-start
figure that had been written before the measurement existed. It was replaced with
the measured values above. The check that caught it is the reason the template
forbids leaving placeholders in a filled record.

## Limitations

- **One host, one architecture, one point in time.** One runtime digest, one model
  revision, one quantisation, one thread count, one context length.
- **Single-request throughout.** Nothing here establishes anything about
  throughput, concurrency, queueing, or behaviour under load. The runtime reported
  four slots; one was ever used.
- **Nothing about model quality.** Three identical correct sentences at
  temperature 0 show the path works. They say nothing about whether the model is
  good, and 23 tokens of output is not an evaluation.
- **Not the project's own cluster.** The trial ran in the cluster the container
  desktop distribution provides, at the host owner's direction. The per-pod
  measurements are unaffected; the whole-VM figure is an upper bound contaminated
  by unrelated workloads.
- **A local cluster is not a production environment**, and a passing trial is not
  a production readiness claim.
- **Third-party facts age.** Every licence, digest, and revision here was read on
  2026-08-24. The runtime publishes from a branch tip with no versioned tag
  scheme, so the tag this digest came from has very likely moved already.

## What remains unproven

| Item | Status | What would close it |
|---|---|---|
| A cumulative request counter from the runtime | Absent; `T7` failed as written | InferOps emitting it from the component that receives the requests |
| A genuinely page-cache-cold start | Not measured | A host where the page cache can be dropped, or a VM restart between runs |
| Behaviour under concurrency or sustained load | Not attempted | A load profile, and thresholds written for it |
| Any host other than this one | Not attempted | A second host; Linux and macOS remain untested for the whole project |
| Any GPU path | Not attempted, and none is claimed | Hardware this project does not have |
| The step-down model, Qwen3-0.6B | Never triggered, so never tested | Only relevant if a future host fails `T3` or `T9` |
| That the runtime loaded exactly the pinned bytes | Established indirectly | A runtime that reports a hash of the weight file it opened |
