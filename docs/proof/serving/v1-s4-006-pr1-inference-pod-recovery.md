# V1-S4-006-PR1 — losing the inference pod while callers were waiting

Date captured: 2026-09-16

Classification: **local real evidence**, redacted. Evidence class `local-real-cpu`,
certification ceiling `C2`. One serving runtime pod was deleted in a real Kubernetes
cluster while the committed load profile was mid-flight, the Deployment controller
replaced it, and every request either side was recorded. Nothing here is mock,
synthetic, or estimated.

Produced by:

```text
INFEROPS_PROVIDER=docker-desktop \
  scripts/environment/inference-pod-recovery.sh run \
    --values charts/inferops-llm/ci/real-values.yaml \
    --values <host API image values> --values <host model seed values> \
    --confirm-real-kubernetes                                          exit 0
```

The machine-readable result is
[`v1-s4-006-pr1-recovery-record.v1alpha1.json`](v1-s4-006-pr1-recovery-record.v1alpha1.json).
It regenerates exactly from the six committed inputs beside it —
[environment](v1-s4-006-pr1-environment.v1alpha1.json),
[lifecycle](v1-s4-006-pr1-lifecycle.v1alpha1.json),
[readiness](v1-s4-006-pr1-readiness.v1alpha1.json),
[telemetry](v1-s4-006-pr1-telemetry.v1alpha1.json), and the two raw load record sets
[run 1](v1-s4-006-pr1-run-1-raw.jsonl) and [run 2](v1-s4-006-pr1-run-2-raw.jsonl):

```sh
python -m tools.inference_pod_recovery verify --dir docs/proof/serving --prefix v1-s4-006-pr1-
```

**What this record may not be read as.** Not an availability figure, not a
service-level objective, not an error budget, not a portable capacity figure, and not
a benchmark of Kubernetes, the model, the runtime, or any provider. The record carries
`productionBenchmark`, `portableCapacityClaim`, and `availabilityClaim` all `false`,
and
[ADR 0013](../../architecture/decisions/ADR-0013-bounded-local-performance-observations.md)
is what permits the figures it does publish.

## The gap this closes

[`V1-S3-003-PR2`](v1-s3-003-pr2-kubernetes-pod-restart.md) deleted a serving pod and
proved that the model artifact was still there afterwards. It sent one request before
and one after, and it stated its own limitation in as many words:

> **One replica.** The replacement window is an outage for any caller reaching that
> Service. Nothing here measures that outage from a caller's side and nothing here
> claims high availability.

That record stays exactly as it is, and this one does **not** re-prove what it proved:
the artifact's inode and modification time are not compared here, and no field of this
record reports an artifact identity. What is new is the caller's side.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `7a9ff83d96959671d1d2491d5d09228fe63bf6df`, with this change's own files uncommitted at run time (`trackedChangesPresent: true`, `untrackedFilesPresent: true`) |
| Experiment descriptor | [`inference-pod-recovery.v1.json`](../../../deploy/serving/experiments/inference-pod-recovery.v1.json), `sha256:62b30549c881dd4aae2b2f9b009e72a0f82e1e1222c6ed8e532c2f3dc8ecbf70` |
| Load profile | [`llm-load-profile.v1.json`](../../../deploy/serving/load/llm-load-profile.v1.json), `sha256:4dc0fe4a4217f035875fcddbdb99b75246f3a74188d5eca8b4dbbec8f57081c5` |
| Provider | `docker-desktop`, verified `2026-09-16T08:59:51Z` |
| Kubernetes | server `v1.34.3`, `kubectl` `v1.34.3`, one node `desktop-control-plane` |
| Node image | `sha256:08497ee19eace7b4b5348db5c6a1591d7752b164530a36f855cb0f2bdcbadd48` — Docker Desktop's choice, not an InferOps pin |
| Chart | `inferops-llm-0.3.0`, release `inferops` revision `1` in `inferops-release` |
| Helm | `v3.19.0+g3d8990f` |
| Platform API image | `localhost/inferops-api@sha256:9687e1bb11bd2b728bd61fd1338718a6816efa65958b9366cdf536fe8fdfc087` |
| Serving runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model | `qwen3-1-7b-q8-0`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077` |
| Collector | Prometheus `3.5.0`, scraping every 30 s |
| Container resources | Runtime: requests 1 CPU / 2Gi, limits 6 CPU / 3Gi. API and collector: requests 100m / 128Mi, limits 1 CPU / 512Mi |
| Deployed configuration | `INFEROPS_REQUEST_TIMEOUT_MS` 120000, `INFEROPS_MAX_OUTPUT_TOKENS` 128, `INFEROPS_LLAMA_SERVER_THREADS` 6, `INFEROPS_LLAMA_SERVER_CONTEXT_SIZE` 4096, read from the release's ConfigMap |
| Other workloads | 12 running pods in 3 other namespaces shared the node. They are counted in the record and not named |

## Environment

One node, 12 CPU and 10 188 024 Ki allocatable, containerd `2.2.0`, kernel
`5.15.146.1-microsoft-standard-WSL2`, Debian GNU/Linux 12. The container engine is
Docker Desktop `29.7.2` with 12 processors and 10 432 536 576 bytes. One replica of
each of the three tiers.

## Method

**Question.** While the committed load profile is mid-flight, one serving runtime pod
is deleted. What does a caller see, what does an operator see, how long until a real
completion comes back, and which of the signals this platform emits noticed?

**Procedure.** The workflow applied the Terraform prerequisites, installed the release,
took a 60 s idle baseline, started the committed load profile, issued one delete a
**registered 30 000 ms** after the load started, sampled readiness every 2 000 ms until
the replacement reported itself Ready, let that run finish, settled 30 s, ran the same
profile a second time, settled 90 s, asked the collector, uninstalled, and built the
record.

**Where each interval begins and ends**, restated because a reader will quote a figure
without the record:

- **Replacement** ends when the replacement pod reports **its own** `Ready` condition,
  not when the Deployment's aggregate rises — that still counts a deleted pod inside
  its termination grace period.
- **The caller-visible outage** begins at the completion of the first request after the
  delete that did **not** come back served, and ends at the completion of the first one
  dispatched from then on that did. It does **not** begin at the delete. Neither end is
  a forward accepting a connection.

**Window membership is by dispatch instant**, which has one consequence a reader must
have: a request a caller had *already sent* when the pod was deleted is counted in the
`before` window even though the disruption is what killed it. Exactly one request was
in that position here, and `inFlightAtDeletion` is the field that discloses it. See
[the first row of the results](#what-callers-saw) and the note under it.

## Results

Every figure below is **measured** — read from the raw load record sets, the cluster's
answers, and the operating script's own stamps — except the intervals, which are
**derived** by subtraction on the host's own clock.

### The pod was replaced, and nothing else changed

| | before | after |
|---|---|---|
| Serving runtime pod | `inferops-inferops-llm-runtime-56546cfdbd-jg7jl` | `inferops-inferops-llm-runtime-56546cfdbd-kgs9c` |
| Pod UID | `ce4ba1ee-6a6d-4a2c-9540-3fa10fead214` | `53ddb513-7ee6-46b3-b149-e1d4ccf8d3fc` |
| Owner | ReplicaSet `…-runtime-56546cfdbd` | the same ReplicaSet |
| Release revision | 1 | 1 |
| Acquisition Jobs | 0 | 0 |
| Model cache claims | 1 | 1 |
| Platform API pod | `…-llm-5c4bbb988c-sm7xt`, 0 restarts | the same pod, 0 restarts |
| Collector pod | `…-collector-55c95c4b8c-65vn8`, 0 restarts | the same pod, 0 restarts |
| Integrity init container | — | `verify-model`, exit `0` |

The selector matched **exactly one** running serving-runtime pod when the delete was
issued, and the delete named that pod. The delete landed inside phase `c1`, which is
the phase the descriptor registered before the run.

### What callers saw

Latency is nearest-rank over successful requests, in milliseconds.

| Window | Dispatched | Served | Not served | P50 | P95 | P99 |
|---|---:|---:|---:|---:|---:|---:|
| `before` — dispatched before the delete | 6 | 5 | **1** | 4 474 | 8 889 | 8 889 |
| `servedWhileDraining` — dispatched after the delete, before the first loss | 0 | 0 | 0 | — | — | — |
| `during` — the outage | 41 | 1 | **40** | 30 287 | 30 287 | 30 287 |
| `afterInTheDisruptedRun` | 84 | 84 | 0 | 8 584 | 56 328 | 120 077 |
| `afterRecovery` — the whole second run | 183 | 183 | 0 | 4 797 | 9 648 | 10 083 |

**The one unsuccessful request in `before` is the disruption's, not a pre-existing
fault.** It was dispatched before the delete, was still in flight when the pod went,
hung, and came back `500` `internal-error` with condition `runtime-error-response` —
the runtime answered with a non-2xx rather than being unreachable.
`inFlightAtDeletion` records exactly one request in that position, with outcome
`http-error`. Membership by dispatch instant is the rule the record states; attributing
an in-flight failure to the disruption rather than to the window it was dispatched in
is [left as follow-up work](#follow-up-this-run-earned).

**What the 40 losses were.** Every one was `503` with canonical code
`capability-unavailable` and condition `runtime-unreachable`, and they came back
**fast** — between 20 ms and 83 ms each. Once the Service had no ready endpoint, the
API refused immediately rather than waiting. That is why 41 requests fit inside a
32-second outage at concurrency 1.

### Timing — one pod, deleted once, on one host

| | ms |
|---|---:|
| Deletion to the replacement pod being first seen | 1 361 |
| Deletion to the replacement reporting **itself** Ready | 33 665 |
| The replacement from first sighting to its own Ready condition | 32 304 |
| Deletion to the first request that was **not** served | 31 764 |
| **Caller-visible outage** — first unserved completion to the next served one | **31 960** |
| Deletion to the service being restored to a caller | 63 724 |

The service was restored **in the disrupted run itself**: the load profile outlived the
outage and went on to serve 84 more requests.

**They are not a benchmark.** One pod, deleted once, on one Windows host, at one
moment, with one replica, one model, one runtime build, one load profile, and a host
file cache in whatever state the preceding run left it. They are not an availability
figure, a service-level objective, an error budget, or a number anything may be
compared against.

**Why `deletionToServiceRestoredMs` (63 724 ms) is nearly twice
`deletionToReplacementReadyMs` (33 665 ms).** The request that ended the outage was
dispatched while the service was still down and took 30 287 ms to come back — it waited
through the tail of the outage and was then served. The interval to a *restored
service* therefore includes one full request, and is an upper bound on what the
platform alone took rather than a measurement of it. The replacement figure is the one
that describes the platform.

### Readiness, from two places that disagree

Seven samples, every 2 000 ms of poll plus 1.7–5.4 s of `kubectl` answer time, from the
deletion to the replacement being Ready:

| Since the deletion | Runtime pods listed | Pods reporting `Ready: True` | **Service endpoints ready** |
|---:|---|---:|---:|
| 1.4 s – 28.6 s | both, the deleted one terminating | **1** | **0** |
| 33.7 s | the replacement only | 1 | 1 |

**Read the middle column carefully.** For the whole outage, one runtime pod was
reporting `Ready: True` — and it was the **deleted** one, still inside its termination
grace period. A reader watching pod readiness would have seen a healthy replica
throughout an outage in which forty consecutive requests were refused. The only signal
that tracked what a caller could reach was the number of endpoints the runtime Service
was willing to send traffic to, which was **zero** for the entire window. This is the
same trap [`V1-S3-011-PR2`](../telemetry/v1-s3-011-pr2-telemetry-during-recovery.md)
recorded for `up`, one layer further in: it is not only scrape health that lies during
a replacement, it is the pod's own readiness condition.

### What telemetry did and did not expose

The record states each expression's registered expectation and its readings either
side; it does not decide whether a signal exposed the event. This section does, and it
is a reviewed statement rather than a computed one.

| Signal | Registered as | Answered | What it did across the disruption | Exposed it? |
|---|---|---|---|---|
| `up{job=…serving-runtime}` | expected **not** to expose | yes, 2 series | the deleted pod's series went `1` → `0` and a new series appeared for the replacement | **partly** — it moved, but only because the *target set* changed, and never went to zero for the job |
| `inferops:scrape_targets_up:sum / …:count` | expected **not** to expose | yes, 2 series | `1` before, `1` after, unchanged | **no** |
| `sum by (inferops_outcome) (inferops_inference_requests_total)` | expected to expose | yes, 2 series | a new `inferops_outcome="server-error"` series appeared and reached `41` | **yes** |
| `sum by (inferops_error_code) (inferops_inference_errors_total)` | expected to expose | yes, 2 series | `capability-unavailable` appeared at `40`, `internal-error` at `1` | **yes, and most precisely** |
| `sum(inferops_readiness_check_failures_total)` | expected to expose | yes, 1 series | `2` → `4` | **yes** |
| `sum(inferops_inference_requests_in_flight)` | expected to expose | yes, 1 series | `1` → `0` | weakly; a gauge at a scrape boundary |
| `sum(llamacpp:requests_processing)` | expected to expose | yes, 1 series | `1` → `0` | weakly, for the same reason |
| `inferops_model_ready` | nothing emits | yes, **0 series** | nothing, as registered | **no — nothing emits it** |
| `kube_pod_container_status_restarts_total` | no source | yes, **0 series** | nothing, as registered | **no — no source** |

**The finding.** The signal that identified *what went wrong* was
`inferops_inference_errors_total` by canonical code: it named
`capability-unavailable` forty times and `internal-error` once, which is exactly the
two failure modes above and distinguishes them. The signals an operator would reach
for first — scrape health and target availability — said the job was up throughout.
Both registered absences were still absent, as they were in Sprint 3.

**What no expression gave.** None of them locates the disruption to better than a
scrape and a rule evaluation, so no figure published above is derived from telemetry.
Every timing comes from the raw load record sets and the operating script's stamps.

### The same phase, before and after

| `c1` successes | Observations | Min | P50 | P95 | Max |
|---|---:|---:|---:|---:|---:|
| Before the delete | 2 | 5 866 | 5 866 | 8 889 | 8 889 |
| After the service was restored (both runs) | 76 | 1 703 | 2 085 | 7 353 | 13 731 |

The comparison was available, and the after side is **faster**. That says more about
warm-up than about recovery: the before side is two requests taken within the first
thirty seconds of a release that had just loaded a 1.71 GiB model, and two
observations support no percentile worth the name. It is published because leaving it
out would be choosing which comparison to show.

### Required human action

| | |
|---|---|
| Authorisation before the run | **required**, and given |
| Values file supplied by the operator | **yes** |
| Interventions between the delete and the uninstall | **none** |

Nothing was restarted, rolled back, edited, or recreated. The Deployment controller did
the recovering. What that can and cannot establish: the operating script issues exactly
one mutating command after the delete — the `helm uninstall` that ends the run — and a
test reads the script to establish it. So "none" means nothing *in this workflow*
intervened; it does not establish that nothing outside it did.

### Commands that failed, and their output

None, in the run this record is built from. The workflow exited `0` and every one of
its twenty-three checks passed. An earlier attempt is described below, and it did not
fail either — it produced a record whose figures were wrong.

## What the first attempt got wrong, and why it was re-run

This experiment was executed twice on 2026-09-16. The first attempt is **not** the
record above and is not committed.

It stamped the recovery from the first request served after the delete. That attempt
happened to have one: a request dispatched 166 ms *after* the delete was answered by
the pod that was going away, in 4 984 ms, served. So "deletion to a served completion"
described the draining pod, and two published intervals came out **negative** —
`firstUnsuccessfulToFirstServedMs: -25842` and
`replacementReadyToFirstServedCompletionMs: -19654`. Every one of the twenty-two checks
it then had passed.

That is the same class of defect an independent review of `V1-S3-003-PR2` caught in
Sprint 3 — a figure stamped from the wrong end — and it contradicted this experiment's
own descriptor, which had registered `callerVisibleOutageFrom:
first-unsuccessful-request-after-deletion` before anything ran. The code had not
implemented its own pre-registration. The descriptor was not changed; the code was
brought into line with it, a `no-published-interval-is-negative` check was added so
that this cannot pass again, and the experiment was re-run. **Every figure in this
record is from the corrected code.**

Two other things the two attempts together establish, which one alone would not:

1. **The API has two distinct failure modes when its runtime disappears.** A request
   already in flight hangs for tens of seconds and returns `500`
   `internal-error` / `runtime-error-response` — 25.8 s in the first attempt, 35.4 s
   here. A request dispatched once the Service has no ready endpoint returns `503`
   `capability-unavailable` / `runtime-unreachable` in tens of **milliseconds**. The
   first attempt saw only the first mode, because its outage was short enough that no
   further request was dispatched into it.
2. **The descriptor's registered reason for two load runs is right in general and was
   not borne out by the first attempt.** It says a run "spends its whole remaining
   request budget within seconds of losing the pod and ends before anything is ready
   again". Here the disrupted run did burn 41 requests of its 60-request `c1` ceiling
   inside the outage and finished with 131 of the profile's 183 requests. In the first
   attempt it lost only one request and completed 174. The second run is what makes the
   like-for-like comparison reliable; whether the first run survives the outage depends
   on how long the outage is relative to the level's pacing, and the descriptor does not
   say that.

## Follow-up this run earned

None of these is implemented here, and each is stated rather than fixed:

1. **Attribute an in-flight failure to the disruption.** A request dispatched before
   the delete and killed by it is counted in `before`. The record discloses it through
   `inFlightAtDeletion`, but a window named `before` showing an unsuccessful request is
   a shape a reader can misread.
2. **Establish the mechanism of the hung in-flight request.** It came back
   `runtime-error-response`, meaning a runtime answered with a non-2xx — not that one
   was unreachable. Connection reuse keeping a terminating pod in play after the
   Service dropped it is a candidate and nothing here establishes it; the deleted pod's
   own logs are gone by the time the record is built.
3. **A pod's own `Ready` condition is not a caller's view.** Sprint 4's dashboard and
   `V1-S4-008`'s alerting should treat the Service's ready endpoint count as the
   caller-relevant readiness signal, not pod readiness and not `up`.

## Limitations

- **One provider, one host, one single-replica release, one model, one runtime build, one load profile, and one pod lost once.** Nothing here is portable to another provider, host, replica count, workload mix, or runtime configuration, and nothing here is an availability figure, a service-level objective, or an error budget.
- **One replica is the cause.** Every unsuccessful request recorded here is the consequence of running one serving replica rather than of Kubernetes. A second replica would have changed the result and this experiment says nothing about what it would have changed it to.
- **Two runs, not one continuous stream.** The requests after the recovery are a second run's as well as the first's, and where a restoration is seen in the second run the interval from the deletion would include this workflow's own readiness polling and the load generator's start-up. In this run it was seen in the first.
- **The forward is in every latency.** Load reaches the API through a loopback port-forward to one pod, held open across the disruption. The forward is to the platform API, which is not the tier being deleted, so what the load records is the API's answer while its upstream was gone rather than a connection that died.
- **A deleted pod is not a lost node.** Nothing here says anything about a node that goes away, a claim that fails to reattach, a corrupted volume, or a runtime that starts and answers wrongly.
- **The collector scrapes every 30 seconds**, so every telemetry row above locates the disruption to within a scrape and a rule evaluation, never to the request. No figure published here is derived from a telemetry series.
- **Persistence is not re-proven here.** That the model artifact survives a pod replacement was established by [`V1-S3-003-PR2`](v1-s3-003-pr2-kubernetes-pod-restart.md) by comparing the artifact's inode and modification time either side. This run recorded only that no acquisition Job appeared, that the integrity init container exited `0`, and that the replacement served real completions.
- **The readiness sampler is slow, and says so.** Each sample took 1.7–5.4 s of `kubectl` answer time on top of a 2 s poll, so the window boundaries in the readiness table are several seconds wide. Every published interval comes from the raw load records instead, which are not.
- **Background use was not controlled.** Twelve pods in three other namespaces shared the node, and the operator's own shell was on the same Windows host.

## Authorisation

Required: **yes**. The run applies Terraform prerequisites, installs a release into a
cluster the operator owns, loads a real model, sends 314 real inference requests, and
deletes a running pod.

Granted by: the host owner, in the session that ran it, for the `docker-desktop`
provider specifically, and for both attempts. The cluster was not created, reset,
reconfigured, or disabled, and no workload of another project was touched.

Cleanup verified: `helm uninstall` removed every object carrying the release's instance
label — 0 remaining — and the claim count was 1 either side. The Terraform-owned
namespace and the model cache claim both survived, which is the boundary
[the ownership inventory](../../architecture/resource-ownership.md) states. Reclaiming
them is `scripts/environment/terraform-prerequisites.sh destroy --confirm`, and nothing
in this workflow does it.

Sensitive values removed before committing: host name, user account, absolute
filesystem paths, the operator's kubeconfig and its path, and the API server address.
The two host values files are referred to by role rather than by path. Cluster-internal
pod names, the namespace, and image digests are reproduced as emitted. No prompt or
completion text was retained: the descriptor sets `retainGeneratedText: false`, and a
test asserts that no committed input carries the fixture's prompt or a `content` field.
