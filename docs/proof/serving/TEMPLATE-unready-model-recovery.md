# `<STORY-ID>` — a model that did not become ready, on `<provider>`

Date captured: `<YYYY-MM-DD>`

> **This is a template. Copy it; never edit it to hold a result.** Sections 1 to 4 are
> written **before** the run. Registering the method, the expected answers, and the
> failure condition in advance is what separates a measurement from a search for a
> number that supports what was already believed. If a section below was written after
> the results were seen, say so in that section rather than presenting it as
> pre-registered.
>
> It is a separate template from
> [`TEMPLATE-inference-pod-recovery.md`](TEMPLATE-inference-pod-recovery.md) rather
> than an edit of it. That one is the registered shape of a different experiment's
> result and is cited by that experiment's descriptor; this result has phases, request
> surfaces, diagnostics, and a canonical error code, and none of those has a row there.
>
> The versioned inputs a filled copy cites are produced by
> [`scripts/environment/unready-model-recovery.sh`](../../../scripts/environment/unready-model-recovery.sh)
> against
> [`deploy/serving/experiments/unready-model-recovery.v1.json`](../../../deploy/serving/experiments/unready-model-recovery.v1.json)
> and
> [`deploy/serving/experiments/unready-model-values.v1.yaml`](../../../deploy/serving/experiments/unready-model-values.v1.yaml),
> and the procedure is
> [`docs/serving/unready-model-recovery.md`](../../serving/unready-model-recovery.md).

## Classification

Classification: **`<local real evidence / …>`**, redacted. Evidence class
`<local-real-cpu>`, certification ceiling `<C2>`.

`<One sentence: what was installed, once, and what it did. Then the disclaimer that
applies — "Nothing here is mock, synthetic, or estimated", or the honest alternative.>`

The machine-readable result is `<…>`. It regenerates from its committed inputs:

```sh
python -m tools.unready_model_recovery verify \
  --dir docs/proof/serving --prefix <prefix->
```

**What this record may not be read as.** Not an availability figure, not a
service-level objective, not an error budget, not a recovery-time objective, and not a
benchmark of Kubernetes, the model, the runtime, or any provider. It is one release,
misconfigured once, on one host, under
[`ADR 0013`](../../architecture/decisions/ADR-0013-bounded-local-performance-observations.md).

## The gap this closes

`<One paragraph. Name the row of ADR 0010 D8 this is about, say what was previously
standing in for it, and say why that was not enough.>`

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `<…>` |
| Experiment descriptor | `sha256:<…>` |
| Values overlay | `sha256:<…>` |
| Provider | `<…>` |
| Kubernetes | `<…>` |
| Node | `<…>` |
| Chart | `<…>` |
| Helm | `<…>` |
| Platform API image | `<…>` |
| Serving runtime image | `<…>` |
| Model | `<…>` at revision `<…>` |
| Collector | `<…>` |
| Serving runtime processor, misconfigured | `<…>` |
| Serving runtime processor, corrected | `<…>` |
| Other workloads | `<…>` |

## Environment

`<One paragraph: what the cluster was, what else was on it, and what was not controlled.>`

## Method

**Question.** `<…>`

**Hypothesis.** `<…>`

**Procedure.**

```text
<the exact invocation, with host paths written as <placeholders>>
```

**Pre-registered expectations.** Each request surface carries one, written into the
descriptor before the run.

| Surface | Expected while unready | Expected after the fix | Rationale |
|---|---|---|---|
| `<probe-id>` | `<…>` | `<…>` | `<…>` |

**Failure condition.** `<…>`

**Stop condition.** `<…>`

**Where each interval begins and ends.** `<…>`

## Results

> Every value is labelled **measured** or **derived**. A number produced by calculation
> is derived however carefully it was calculated, and derived values cannot certify.

### The release installed, and the artifact was never in question

| | value |
|---|---|
| Chart validation | `<…>` |
| `verify-model` exit code, misconfigured pod | `<…>` |
| `verify-model` exit code, corrected pod | `<…>` |
| Release revision, before and after | `<…>` |

### Readiness, from four places that disagree

| Place | While unready | After the fix |
|---|---|---:|
| Serving runtime pod `Ready` | `<…>` | `<…>` |
| Serving runtime Service ready endpoints | `<…>` | `<…>` |
| Platform API pod `Ready` | `<…>` | `<…>` |
| Serving runtime container `restartCount` | `<…>` | `<…>` |

`<One paragraph on what the restart count does and does not establish, and the startup
probe budget it is bounded by.>`

### What a caller was told

| Surface | While unready | After the fix |
|---|---|---|
| `<probe-id>` | `<status>` `<code>` `<condition>` | `<status>` `<…>` |

`<One paragraph naming the canonical code that was actually observed, whether it is the
one ADR 0010 D8 would have been read as predicting, and why.>`

### Timing — one release, misconfigured once, on one host

| | ms |
|---|---:|
| Install to the runtime container running | `<…>` |
| Container running to the socket answering | `<…>` |
| Unready window held | `<…>` |
| Upgrade to the runtime reporting Ready | `<…>` |
| Upgrade to the API reporting Ready | `<…>` |
| Upgrade to a served completion | `<…>` |

**They are not a benchmark.** `<…>`

### What the diagnostics said

| Capture | Registered as naming the cause | Captured | What it showed |
|---|---|---|---|
| `<capture-id>` | `<yes / probable / partial / no>` | `<…>` | `<…>` |

`<One paragraph: whether an operator holding only these could have named the cause, and
whether anything in them would have been unsafe to publish.>`

### What telemetry did and did not expose

| Signal | Registered as | Answered | What it did across the two phases | Exposed it? |
|---|---|---|---|---|
| `<expr>` | `<expected-to-expose / expected-not-to-expose / nothing-emits / no-source>` | `<…>` | `<…>` | `<…>` |

`<The record states each expression's registered expectation and its readings either
side; it does not decide whether a signal exposed the state. This section does, and it
is a reviewed statement rather than a computed one.>`

### Required human action

`<…>`

### Commands that failed, and their output

```text
<paste, redacted. A failure that is omitted is the one the next person repeats.>
```

## Limitations

- `<…>`
- `<…>`
- `<…>`
- `<…>`
- `<…>`

## Authorisation

Required: `<…>`

Granted by: `<…>`

Cleanup verified: `<…>`

Sensitive values removed before committing: `<…>`
