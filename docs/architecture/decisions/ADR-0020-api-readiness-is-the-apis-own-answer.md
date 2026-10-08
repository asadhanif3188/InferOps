# ADR 0020: API readiness is the API's own answer, and the adapter's answer is reported beside it

| Field | Value |
|---|---|
| Status | **Accepted** |
| Date proposed | 2026-10-08 |
| Date accepted | 2026-10-08 |
| Decision owner | [`repository-maintainer`](../../governance/decision-authority.md) |
| Supersedes | None |
| Amends | [ADR 0010](ADR-0010-inference-api-compatibility-surface.md) D2, in one sentence: what the status of `/health/ready` depends on. The five endpoints, their paths, and the error contract are not changed. ADR 0010 gains a dated note |
| Superseded by | None |

> [!IMPORTANT]
> This record changes what `GET /health/ready` answers.
>
> **The status is the API's own answer.** It is `200` while the API accepts work
> and `503` while the API is starting, draining, or stopped. The state of the
> selected adapter does not change the status.
>
> **The adapter's answer is reported beside it.** The API still asks the adapter
> on each readiness request, inside a budget. The body reports the answer in a
> separate member, `adapterStatus`, and the API counts each answer that is not
> `ready`.
>
> **The evidence is static.** Tests drive the application in process, with the
> real adapter type over a controlled transport. No API image was built from this
> change, no release was installed, and no cluster was contacted. No record shows
> what a Kubernetes Service does with an API pod under this rule.
>
> **A deployed release is not changed by merging this record.** The API image is
> built by an operator and pinned by digest. A release answers under this rule
> only after an image is built from a revision that contains it.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | The status of `/health/ready` is `200` if, and only if, the API lifecycle state is `serving` | **Accepted** | Tests read the status in each lifecycle state, with a ready adapter and with an adapter that is not ready |
| D2 | While the API accepts work, each readiness request asks the selected adapter. The body reports the answer in `adapterStatus`, which is one of `ready`, `not-ready`, and `not-asked` | **Accepted** | Tests read the body with a runtime that is ready, one that is unreachable, one that is loading, and one that does not answer |
| D3 | The ask is bounded by a budget. The default is 3,000 ms. An ask that does not finish inside the budget is cancelled and reported as `not-ready` | **Accepted**, with a stated limit | One test holds that a readiness request returns while the adapter never answers. One test compares the default with the chart's default probe timeout. The chart does not refuse a shorter probe timeout |
| D4 | `inferops_readiness_check_failures_total` keeps its name, its labels, and its two component values. A count for `serving-adapter` no longer means that the readiness status was `503` | **Accepted** | Tests read the counter and the status together. The catalog, the alert record, and the runbook state the new meaning |
| D5 | A consumer that needs to know whether inference can be served reads both `status` and `adapterStatus` | **Accepted** for two repository tools. **Not applied** to the V1 experiment tools that read the status only | Tests of the load generator and of the local composition. R4 lists the tools that were not changed |
| D6 | Liveness, the five routes, their paths, and the canonical error contract are not changed | **Accepted** | The existing suites of those surfaces pass without a change to what they assert about them |

## Context

[ADR 0010](ADR-0010-inference-api-compatibility-surface.md) D2 gave the API a
readiness endpoint and said that "only readiness is allowed to depend on the
runtime". The implementation used that permission in full. `/health/ready`
answered `200` only when the API accepted work **and** the selected adapter
reported itself ready. It answered `503` when either was false.

The chart points the API pod's readiness probe at that path. Kubernetes documents
that a pod whose readiness probe fails is not ready, and that a Service does not
send traffic to a pod that is not ready. Under the V1 rule, an API pod therefore
left its Service whenever its adapter was not ready, although the API process
could still answer.

That removes the answer the API was built to give. The API maps a runtime that
cannot be reached and a model that is still loading to two canonical errors, each
with a code, a condition, and a `retryable` flag. A caller can receive either
error only from an API endpoint that is still in the Service.

[The unready-model experiment](../../serving/unready-model-recovery.md) recorded
the V1 behaviour on one provider: while the model was not ready, the API's
readiness path answered `503` at every ask, and the API pod's `Ready` condition
agreed. That run read the canonical error through a forward to the API pod. It
did not send a request through the Service.

V2 declares two API replicas and plans experiments that remove pods and read what
a caller receives. Those experiments need the API's readiness and the runtime's
readiness to be two signals. With the V1 rule they are one signal: every API
replica follows the same runtime, so every API replica leaves the Service
together.

## Decision criteria

1. An API that can answer with a canonical error is able to honor its contract.
2. An API that cannot honor its contract must not report itself ready.
3. A consumer that reads readiness must be able to tell the API's state from the
   dependency's state.
4. The API's readiness answer must not be late because a dependency is slow.
5. An existing signal that an operator uses must not go silent without a record.

## D1 — The status is the lifecycle

The status of `/health/ready` is `200` if, and only if, the lifecycle state is
`serving`.

| Lifecycle state | Status | `status` | Why the API cannot honor its contract |
|---|---|---|---|
| `starting` | `503` | `not-ready` | The adapter has not accepted its configuration. An inference request is refused |
| `serving` | `200` | `ready` | — |
| `draining` | `503` | `not-ready` | The API refuses new work with `deployment-draining` and is about to exit |
| `stopped` | `503` | `not-ready` | The adapter is released |

The API enters `serving` only after the adapter has accepted its configuration.
A startup in which the adapter refuses its configuration fails, as before.

In the `serving` state the API reads a request, validates it, calls the adapter,
and answers. If the adapter cannot serve, the API answers with the canonical
error for that condition. That is the contract
[the API document](../../serving/inference-api.md) publishes, and it is the
reason the status does not follow the adapter.

## D2 — The adapter is asked, and its answer is a separate member

The readiness body has four members.

| Member | Meaning |
|---|---|
| `status` | `ready` or `not-ready`. The API's own answer, as in D1 |
| `adapterKind` | The kind of adapter the deployment was composed with. Unchanged |
| `state` | The lifecycle state. Unchanged |
| `adapterStatus` | `ready`, `not-ready`, or `not-asked`. What the selected adapter said |

`adapterStatus` is `ready` when the adapter said it can accept an inference
request now. It is `not-ready` when the adapter said no, raised an error, or did
not answer inside the budget of D3. It is `not-asked` when the API does not
accept work: an API that is starting has an adapter that is not initialized, and
an API that is draining is about to release it.

**The ask is kept for a functional reason.** The real adapter refuses inference
until one of its own probes has seen the runtime ready, and it learns that the
runtime became ready from the same probe. In a deployed release the readiness
probe of the API pod is what makes that probe run. If the readiness endpoint
stopped asking, an adapter that first saw a loading model would refuse inference
after the model finished loading. A test holds this sequence.

**`adapterStatus` does not say why.** The adapter interface answers readiness
with a boolean. An unreachable runtime and a loading model are therefore one
value, `not-ready`, in the readiness body. The inference path distinguishes them:
an unreachable runtime is `capability-unavailable` with the condition
`runtime-unreachable`, and a loading model is `model-not-ready` with the
condition `model-loading`. A test holds both the one value and the two errors.

## D3 — The ask is bounded

The real adapter bounds its own probe by the inference request budget plus one
second. The chart's default request budget is 120 seconds. The chart's default
readiness probe timeout is 5 seconds. A runtime that accepts a connection and
does not answer would therefore make the readiness answer late, and Kubernetes
documents that a probe that times out has failed. The API would leave the
Service because of its dependency, which is the coupling D1 removes.

The API therefore gives the ask a budget of its own. The default is 3,000 ms. An
ask that does not finish inside the budget is cancelled, and the body reports
`not-ready`.

**Limits of D3.**

- The default is a declared number. No probe latency was measured.
- No environment variable sets the budget. A deployment that is composed from
  configuration uses the default.
- The chart does not refuse `api.probes.readiness.timeoutSeconds` of 3 or less.
  An installation that sets one makes a slow dependency a failed API probe again.
  A test compares the two default values and nothing else.
- A cancelled ask does not update the adapter's last observed state. The next
  readiness request asks again.

## D4 — The readiness counter

`inferops_readiness_check_failures_total` is still incremented once for each
readiness request in which a component said no, with the same two values of
`inferops_component`.

| Component | When it is counted | Readiness status of that request |
|---|---|---|
| `api` | The API does not accept work | `503` |
| `serving-adapter` | The API accepts work and the adapter did not say it is ready | `200` |

Before this record, both rows carried `503`. The counter's help text and the
catalog's question said the platform was refusing traffic. Both now say what the
counter counts.

The alert `InferOpsReadinessRefusalsSustained` keeps its expression. For the
component `serving-adapter` it now reports that the dependency has not been
ready for five minutes while the API pods stay in the Service. For the component
`api` it reports what it reported before.
[The alert record](../../telemetry/inference-alerts.md) states both meanings.

## D5 — Consumers read both members

A `200` from `/health/ready` no longer says that inference can be served. A
consumer that needs that answer reads `status` and `adapterStatus`.

Two repository tools needed that answer, and both were changed.

- The load generator refuses a target unless the status is `200`, `status` is
  `ready`, and `adapterStatus` is `ready`. It refuses a body that has no
  `adapterStatus`. An API image built before this record therefore cannot be a
  load target for this revision of the tool.
- The local composition waits while the body reports `adapterStatus` as
  `not-ready`, and it reports itself ready only on the complete ready body.

## D6 — What is not changed

- `/health/live` answers `200` in every lifecycle state, as before.
- The five routes and their paths are the ones ADR 0010 D2 lists.
- The canonical error body, its codes, its conditions, and its statuses are not
  changed.
- The shutdown order is not changed: readiness becomes `503`, in-flight work
  drains, and the adapter is released last.
- The chart's rendered objects are not changed. The API probes ask the same
  paths with the same periods and thresholds.

## Alternatives that were rejected

| Alternative | Why it was rejected |
|---|---|
| Keep the conjunction and document it as a deviation | The API pod would still leave the Service with its dependency. The canonical dependency errors would stay unreachable through the Service in the condition they describe |
| Add a second readiness path for the kubelet and keep `/health/ready` as it was | The surface would have six endpoints, and the endpoint named "ready" would not be the one the readiness probe asks. The rendered chart would change |
| Change the status and leave the body with three members | A `200` whose `status` member says `not-ready` contradicts itself, and a `200` whose `status` says `ready` hides the dependency |
| Stop asking the adapter on a readiness request | The real adapter would not observe that a model finished loading. The readiness counter and its alert would go silent for the adapter |
| Ask the adapter without a budget | A dependency that does not answer would fail the API's readiness probe by timeout |

## Consequences

- **An API pod can be `Ready` before the runtime is.** `kubectl rollout status`
  for the API Deployment, and the API readiness ask of the chart's `helm test`
  pod, no longer say that a model is loaded. The runtime Deployment has its own
  readiness probe, which is not changed.
- **A caller can receive a canonical dependency error where V1 gave no API
  endpoint.** This is the intended effect. It is derived from the rule and from
  what Kubernetes documents. It was not observed.
- **Two API replicas no longer leave the Service together because of one
  runtime.** The same qualification applies.
- **The readiness status is not an inference health signal.** A caller outcome
  is the only evidence that inference works.

## Compatibility impact

The V1 release, its tag, its evidence pack, and its records are not changed.
Records that describe the V1 readiness rule describe API images built before
this record, and they stay as written. Living documents that described the V1
rule in the present tense were corrected or given a dated note.

The readiness body gains one member. A consumer that compared the whole body
with three members no longer matches.

## Security considerations

`adapterStatus` is one of three fixed strings. It carries no endpoint, no
credential, no path, and no runtime message, and a test holds that. It does tell
an unauthenticated reader of the readiness path whether the dependency is ready.
The V1 status told the same reader the same fact. ADR 0008 D4 accepts no
authentication on this surface in V1, and this record does not change that.

## Evidence

Evidence level: **C0, static.**
[The validation record](../../proof/serving/v2-s4-001-pr2-validation.md) lists
the commands and their results. No claim was added or changed.

## Risks, assumptions, and open questions

| ID | Item | Status | Note |
|---|---|---|---|
| R1 | No deployed release was observed under this rule | Open | What a Service does with an API pod, and what a caller receives, are not established. A later observation of a deployed release must establish them |
| R2 | The API image is built outside Git and pinned by digest | Open | Merging this record changes no running API. ADR 0019 R1 records the same gap for the image in general |
| R3 | The chart does not refuse a readiness probe timeout at or below the budget | Open | D3 states the limit. A chart rule is a chart change and was not made here |
| R4 | Three V1 experiment tools read the readiness status only: the Kubernetes certification, the pod-restart experiment, and the upgrade and rollback experiment | Accepted | Each waits for the runtime Deployment's own rollout and asserts a real completion. Against an image built from this record, their readiness step shows that the API accepts work, and no more |
| R5 | The descriptor of the unready-model experiment expects `503` on the API's readiness path and an API pod that is not `Ready` | Open | Against an image built from this record, those two expectations are not met. The descriptor and its tool are not changed here. A rerun needs a revised descriptor |
| R6 | The upgrade and rollback experiment records the readiness status as what a caller saw | Open | Against an image built from this record, that probe reads the API's own state. Its earlier records are not affected |
| R7 | The readiness body does not distinguish an unreachable runtime from a loading model | Accepted | D2. The adapter interface is not changed |
| R8 | A cancelled ask leaves the adapter's last observed state in place | Accepted | D3. An adapter that last saw the runtime ready attempts the next completion, and the inference path then reports what it finds |
