# `<STORY-ID>` — losing the inference pod under load, on `<provider>`

Date captured: `<YYYY-MM-DD>`

> **This is a template. Copy it; never edit it to hold a result.** Sections 1 to 4 are
> written **before** the run. Registering the method and the failure condition in
> advance is what separates a measurement from a search for a number that supports
> what was already believed. If a section below was written after the results were
> seen, say so in that section rather than presenting it as pre-registered.
>
> The versioned inputs a filled copy cites are produced by
> [`scripts/environment/inference-pod-recovery.sh`](../../../scripts/environment/inference-pod-recovery.sh)
> against
> [`deploy/serving/experiments/inference-pod-recovery.v1.json`](../../../deploy/serving/experiments/inference-pod-recovery.v1.json),
> and the procedure is
> [`docs/serving/inference-pod-recovery.md`](../../serving/inference-pod-recovery.md).

## Classification

Classification: **`<local real evidence / …>`**, redacted. Evidence class
`<local-real-cpu>`, certification ceiling `<C2>`.

`<One sentence: what was done, once, to what. Then the disclaimer that applies —
"Nothing here is mock, synthetic, or estimated", or the honest alternative.>`

The machine-readable result is `<…-recovery-record.v1alpha1.json>`. It regenerates
exactly from the four committed inputs beside it — `<environment>`, `<lifecycle>`,
`<readiness>`, `<telemetry>` — and the raw load record set `<…-raw.jsonl>`:

```sh
python -m tools.inference_pod_recovery verify --dir docs/proof/serving --prefix <prefix->
```

**What this record may not be read as.** Not an availability figure, not a
service-level objective, not an error budget, not a portable capacity figure, and not
a benchmark of Kubernetes, the model, the runtime, or any provider. The record carries
`productionBenchmark`, `portableCapacityClaim`, and `availabilityClaim` all false, and
[ADR 0013](../../architecture/decisions/ADR-0013-bounded-local-performance-observations.md)
is what permits the figures it does publish.

## The gap this closes

`<Which earlier record this extends, quoted where it states the limitation this run
answers. Say explicitly that the earlier record stays as it is.>`

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `<revision, and whether the tree was clean>` |
| Experiment descriptor | `<path>`, `sha256:<…>` |
| Load profile | `<path>`, `sha256:<…>` |
| Provider | `<provider>` |
| Kubernetes | server `<…>`, kubectl `<…>` |
| Node | `<name>`, image digest `<…>` |
| Chart | `<name-version>` |
| Helm | `<…>` |
| Platform API image | `<repository@sha256:…>` |
| Serving runtime image | `<repository@sha256:…>` |
| Model | `<identifier>`, revision `<…>` |
| Collector | `<version>` |
| Container resources | `<requests and limits that shape the measurement>` |
| Other workloads | `<how many running pods outside the release, counted not named>` |

## Environment

`<Everything the record's environment block carries that a reader needs beside a
figure: node capacity and allocatable, engine version and capacity, the release
configuration keys that shape a measurement.>`

## Method

**Question.** `<One question, answerable by this run.>`

**Hypothesis.** `<In a form that could turn out to be wrong.>`

**Procedure.** `<The exact commands, in order.>`

```text
INFEROPS_PROVIDER=<provider> \
  scripts/environment/inference-pod-recovery.sh run \
    --values <host values file> --confirm-real-kubernetes
```

**Pre-registered thresholds.**

| ID | Threshold | Blocking? | Rationale |
|---|---|---|---|
| `<T1>` | `<…>` | `<yes/no>` | `<…>` |

**Failure condition.** `<Stated so that it cannot be reinterpreted afterwards.>`

**Stop condition.** `<A budget, a timeout, a hazard.>`

**Where each interval begins and ends.** `<Restate it, because a reader will quote a
figure without the record. The replacement ends at the replacement pod's own Ready
condition, not the Deployment's aggregate. The caller-visible outage begins at the
first request after the delete that was not served and ends at the next one that was —
not at the delete, because the draining pod goes on serving. Neither end is a forward
accepting a connection.>`

## Results

> Every value is labelled **measured** or **derived**. A number produced by calculation
> is derived however carefully it was calculated, and derived values cannot certify.

### The pod was replaced

| | before | after |
|---|---|---|
| Pod name | `<…>` | `<…>` |
| Pod UID | `<…>` | `<…>` |
| Owner | `<…>` | `<…>` |
| Release revision | `<…>` | `<…>` |
| Acquisition Jobs | `<…>` | `<…>` |

### What callers saw

| Window | Dispatched | Served | Not served | P50 | P95 | P99 |
|---|---:|---:|---:|---:|---:|---:|
| Before the delete | `<…>` | `<…>` | `<…>` | `<…>` | `<…>` | `<…>` |
| Between the delete and the first served completion | `<…>` | `<…>` | `<…>` | `<…>` | `<…>` | `<…>` |
| After it | `<…>` | `<…>` | `<…>` | `<…>` | `<…>` | `<…>` |

`<The statuses and canonical error codes the unsuccessful requests carried. Whether a
same-phase comparison was available, and if it was, what it showed.>`

### Timing — one pod, once, on one host

| | ms |
|---|---:|
| Deletion to the replacement being observed | `<…>` |
| Deletion to the replacement reporting itself Ready | `<…>` |
| Last completion the draining pod still served, after the deletion | `<…>` |
| Deletion to the first request that was **not** served | `<…>` |
| Caller-visible outage, first unserved completion to the next served one | `<…>` |
| Deletion to the service being restored to a caller | `<…>` |

**They are not a benchmark.** `<Say it in the record's own words, naming what varies.>`

### Readiness, from three places that disagree

`<The endpoint count the runtime Service reported, sampled; what the pod list showed
while the deleted pod was terminating; and why those two differ.>`

### What telemetry did and did not expose

| Signal | Registered as | Answered | What it did across the disruption |
|---|---|---|---|
| `<seriesId>` | `<expected-to-expose / expected-not-to-expose / nothing-emits / no-source>` | `<…>` | `<…>` |

`<The record does not decide whether a signal exposed the event. This section does, and
it is a reviewed statement rather than a computed one.>`

### Required human action

`<What a person had to do: the authorisations before the run, and whether anything
intervened between the delete and the uninstall. Say what the record can and cannot
establish about that.>`

### Commands that failed, and their output

```text
<paste, redacted. A failure that is omitted is the one the next person repeats.>
```

## Limitations

- `<One provider, one host, one replica, one moment — and what each of those means.>`
- `<What a deleted pod is not.>`
- `<What the forward contributes to every figure.>`
- `<What the scrape interval means for every telemetry row above.>`
- `<What this record does not re-prove, and which record proves it instead.>`

## Authorisation

Required: `<yes / no>`, because `<cost, artifact size, a running workload, or a
resource outside the contributor's own machine>`.

Granted by: `<who, and when — or "not obtained", with the stages that were therefore
not run>`.

Cleanup verified: `<how, and what was left behind. Name what survives a release by
design.>`

Sensitive values removed before committing: `<host name, user account, absolute
filesystem paths, the kubeconfig and its path, the API server address, and any
certificate, key, or token. Say whether generated text was retained.>`
