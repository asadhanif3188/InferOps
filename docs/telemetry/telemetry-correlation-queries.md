# Correlated platform telemetry: the queries, and what they answer

Status: verified against fixtures **and evaluated by a real Prometheus.** The
chart installs a release-scoped collector, it scrapes both InferOps endpoints, and
every expression on this page has been parsed, loaded, and evaluated by that
collector against a real scrape on the `docker-desktop` provider. That is recent
and the history matters: **until V1-S3-011-PR1 no Prometheus had parsed, loaded,
or evaluated any expression on this page**, and everything published here rested
on fixtures somebody wrote to look like a scrape. [`V1-S3-011-PR2`](../proof/telemetry/v1-s3-011-pr2-telemetry-during-recovery.md)
asked the same expressions before, during, and after a real serving pod was
replaced.

What is still **not** selected is a durable store, a dashboard, or an alerting
path — [ADR 0006](../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md)
D8 leaves that to the open question [ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
carries. The collector's series live in an `emptyDir` and go with its pod, so
nothing here is a store anything may depend on, and an expression being
answerable is not the same as anyone being told when its answer changes.

[The collection document](kubernetes-telemetry-collection.md) says what a collector
would find. This one says what an operator could then ask, in what vocabulary, and —
for six of the twenty-three questions here — what they would get instead of an
answer.

The authoritative form is
[`telemetry-correlation-queries.v1alpha1.json`](telemetry-correlation-queries.v1alpha1.json).
Every claim below is compared against it in both directions by
[`tests/telemetry/test_telemetry_correlation.py`](../../tests/telemetry/test_telemetry_correlation.py).

## Why a query catalogue exists at all

The failure this prevents is specific and it is not "somebody could not think of a
query". It is that **an empty result and a healthy system look identical**.

A dashboard panel showing nothing is what you get from a workload that is idle, from
a job whose label selector matched no pod, from a target that is up and publishing no
identity, from a metric nothing emits, from a query grouping by a label the collector
drops on the way in, and from a join whose key one side does not carry. Six causes,
one appearance. An operator who writes a query by hand meets all six and can
distinguish none of them.

So every query here carries the reason its result would be empty, four of them are
published *because* they are always empty, and two are published with no expression
at all because there is no series to select.

## Running the checks

```sh
python -m pytest tests/telemetry -q
python -m tools.telemetry_correlation
python -m tools.telemetry_correlation --evaluate
```

The first is the authoritative check and runs in the default lane. The second applies
the same policy to the committed record and is usable as a gate. The third runs every
query against every scenario fixture and prints what it returned.

All three read files in this repository. None of them contacts a cluster, starts a
Prometheus, or evaluates anything against a store that has ever held a sample.

## The vocabulary a query may use

Three sources, and no fourth.

1. **Attributes the telemetry catalog permits on a series** — every attribute whose
   declared placements include `metric-label` or `info-label`, written in the form a
   Prometheus exposition spells it: `inferops.workload.id` becomes
   `inferops_workload_id`.
2. **Target labels the collector attaches** — `job`, `instance`, `k8s_namespace`,
   `k8s_component`, and, on the runtime job only, `deployment_environment`,
   `inferops_workload_id`, `inferops_model_id`, and `inferops_runtime_id`. The
   collection record declares each one with its cardinality class.
3. **`le`**, which is Prometheus's own and is what makes a histogram a distribution
   rather than a set of counters.

A query naming anything else is refused. The list is **derived from the catalog on
every run** rather than copied, so a placement decision taken there reaches the
emitter, the collector's drop list, and this vocabulary without three separate edits.

**No published query names a job.** Job names are release-qualified — that is what
lets two releases' scrape fragments merge into one collector configuration — so a
query naming one would work in exactly one installation. Releases are told apart by
`k8s_namespace` and `k8s_component`, which are the same two labels everywhere. The
recording rules the chart renders *do* name their own release's jobs, because a rule
is rendered per release and an unscoped `absent()` would read 0 as soon as any release
published; a query reads the recorded name and never the job name.

## The declared PromQL subset

The expressions here are written in a subset of PromQL that this repository can read,
and **an expression outside it is refused rather than published unchecked**.

| | |
|---|---|
| Aggregations | `sum`, `count`, `avg`, `min`, `max` |
| Functions | `absent`, `rate`, `increase`, `histogram_quantile`, `label_replace` |
| Operators | arithmetic, comparison, `and`, `or`, `unless`, and explicit `on` / `ignoring` matching with `group_left` / `group_right` |
| Excluded | subqueries, `@`, `offset`, `topk`, `bottomk`, `quantile`, `count_values`, every function not listed, a `group_left`/`group_right` written with `ignoring` rather than `on`, a matcher regex using a group or a quantifier other than `.*`, and an expression nesting more than 100 levels deep |

`topk`, `bottomk`, and `quantile` select rather than summarise, so their answers
depend on tie-breaking the fixture evaluator does not model. `count_values` writes a
label out of a *value*, which is the one move the telemetry catalog exists to prevent.
A group modifier written with `ignoring` is refused because the rule that checks a
join key reads the `on` set, and a rule enforced for half a syntax reads as enforced
and is not. A regular expression that can backtrack into itself is refused because it
hangs whatever evaluates it, and the nesting bound is what makes a deep expression a
refusal rather than a `RecursionError` no caller was handling. The rest are absent
because no query here needs them.

**The evaluator is not Prometheus**, and the differences are declared rather than left
to be discovered:

- `rate()` and `increase()` take the plain delta over the samples inside the window
  divided by the interval between them, with counter resets added back. Prometheus
  extrapolates to the window edges. Every fixture places its samples on the
  boundaries, where the two agree.
- An instant selector takes the newest sample in the **half-open** window
  `(T - 300s, T]`: a sample exactly 300 seconds old is outside it. Which side
  Prometheus falls on at exactly that boundary has not been checked against the
  engine, so it is declared as an unverified difference rather than as agreement. No
  fixture sits on the boundary and a test pins the behaviour.
- Prometheus's stale markers do not exist here, because nothing writes one into a
  fixture.
- A matcher or `label_replace` regular expression must be inside a declared safe
  subset: a literal run, an escaped character, `|`, and at most four `.` or `.*`
  wildcards. Prometheus uses RE2, which accepts more and is linear; this accepts less
  and says so.
- A comparison without `bool` filters rather than computing, so it keeps the
  left-hand element unchanged, metric name included — the engine's rule, and one an
  earlier version of this evaluator got wrong for every operator.
- There is one evaluation instant per run, so nothing here is evaluated over a range.

## The workflow

1. **Ask whether anything is being scraped at all**, before reading any number.
   `scrape-target-health-by-job` reads 1 per job when every target answered. If a job
   is *missing from that result*, its discovery matched nothing —
   `platform-api-scrape-job-absent` and `serving-runtime-scrape-job-absent` are what
   say so, and each reads 1 in exactly that case.
2. **Ask whether the targets that answered are useful.**
   `identity-absent-on-a-target-that-answered` reads 1 when an API target answered a
   scrape and published no `inferops_build_info`. `up` alone cannot tell that from a
   target that is up and correct.
3. **Then read the operational questions** — `request-throughput-by-workload-model-and-outcome`,
   `error-rate-by-workload-and-code`, `request-latency-p95-by-workload-and-model`,
   `in-flight-requests-by-replica`, `tokens-by-direction-from-the-api`,
   `readiness-check-failures-by-component`, `api-process-cpu-by-replica`.
4. **Attach the identity when the answer has to name a build.**
   `throughput-joined-to-build-identity` is the join, and
   `build-identity-per-replica` is the series it joins to.
5. **Cross to the runtime when the API's view is not enough** —
   `tokens-by-direction-from-the-runtime`, `runtime-deferred-requests`,
   `api-and-runtime-in-flight-side-by-side`.
6. **Know which questions have no answer** before writing one by hand:
   `model-readiness-by-workload`, `model-load-duration-p95`, `queue-wait-p95`,
   `api-process-memory-by-replica`, `container-and-pod-resource-use`, and
   `pod-phase-restarts-and-container-readiness`.

## The correlation join, and why it is on `job` and `instance`

`inferops_build_info` is **one series per process**, always 1, and it carries the
immutable identity: `service_version`, `inferops_capability_id`,
`inferops_release_id`, `deployment_environment`, `inferops_adapter_kind`,
`inferops_model_id`, `inferops_model_revision`, `inferops_runtime_id`, and
`inferops_runtime_image_digest`. Putting those on every operational series instead
would multiply every series by nine labels that never change, which is what the
identity metric exists to avoid.

So `throughput-joined-to-build-identity` matches `on (job, instance)` — the process
both sides share — with `group_left`, because there are many operational series to one
identity series.

It is **not** joined on a workload or a model. `inferops_build_info` carries no
workload label at all, so a join on one matches nothing and returns nothing, which is
what `join-on-a-key-build-info-cannot-carry` in the refused set demonstrates and what
the `join-matches-on-a-key-one-side-cannot-carry` rule refuses.

One value is worth knowing before reading a result: **the chart's default leaves
`service_version` empty**, and an empty label value is indistinguishable from an
absent one in Prometheus. A release that has not set it will find `group_left` copying
nothing for that label rather than copying a blank.

## What a refused query looks like

Ten deliberately wrong queries are committed beside the good ones, each naming the
rule that refuses it. They are the negative half of the check, and they run in the
same suite.

| Refused query | Refused by |
|---|---|
| `group-by-request-id` | `query-names-a-label-the-catalog-bars-from-a-metric` |
| `filter-by-tenant` | `query-names-a-label-the-catalog-bars-from-a-metric` |
| `group-by-pod-name-attribute` | `query-names-a-label-the-catalog-bars-from-a-metric` |
| `group-by-http-status` | `query-names-a-label-the-catalog-bars-from-a-metric` |
| `read-a-metric-nothing-declares` | `query-reads-a-series-nothing-in-this-release-produces` |
| `group-by-a-label-nothing-carries` | `query-names-a-label-nothing-in-this-release-carries` |
| `claim-queue-latency-is-answerable` | `query-claims-an-answer-a-signal-nothing-emits-cannot-give` |
| `join-on-a-key-build-info-cannot-carry` | `join-matches-on-a-key-one-side-cannot-carry` |
| `subquery-outside-the-subset` | `query-expression-is-outside-the-verified-subset` |
| `topk-outside-the-subset` | `query-expression-is-outside-the-verified-subset` |

`group-by-pod-name-attribute` is the one worth dwelling on. `k8s.pod.name` is barred
from a metric as an **emitter** rule, and it stays barred here. The pod is available,
as `instance`, which the collector attaches and which the collection record declares
with its cost. Two names for one thing is how a barred attribute comes back.

`claim-queue-latency-is-answerable` is the other. Its expression is well formed and
its metric is in the catalog; what is wrong is the claim written beside it. The
catalog marks `inferops_inference_queue_duration_seconds` not emitted, so a collector
would not make it answerable — and `queue-wait-p95` publishes the same expression with
the honest class.

## The metrics with no query, and why

Every one of the eight metrics the catalog marks **emitted** is read by a query here.
Four of the eight it marks not emitted are not, and the reason differs in each case.

| Metric | Why there is no query |
|---|---|
| `inferops_workload_document_rejections_total` | Its emitter is the contract validator, which is a library and a command rather than a running service. There is no process to scrape, so no scrape job could discover an endpoint and no query could read it |
| `inferops_inference_time_to_first_token_seconds` | Deferred out of V1. There is no streaming path, so this is the same measurement as request duration; publishing it as a second signal would publish a fabrication |
| `inferops_inference_retries_total` | Deferred out of V1. There is no retry or fallback path, so the counter can only ever read zero, and a flat line reads as a healthy system rather than an absent feature |
| `inferops_cost_records_total` | Deferred out of V1. No component computes or emits a cost record, so a query over it would describe an absent capability as a quiet one |

The other four not-emitted metrics — `inferops_model_ready`,
`inferops_model_load_duration_seconds`, `inferops_inference_queue_duration_seconds`,
and `inferops_process_resident_memory_bytes` — *do* have queries, published with the
class that says they return nothing. The difference is that all four are specified for
V1 and would answer a question somebody will ask; a query that is missing is a query
somebody writes badly.

## The six scenarios

Every query is evaluated against six synthetic stores. Each store's series carry
exactly the labels the committed render's relabelling would attach, and every value in
them was written by hand.

| Scenario | What it shows |
|---|---|
| `healthy-real-two-replicas` | Two API and two runtime replicas, everything answering. The identity join carries the build labels onto both replicas' throughput |
| `serving-runtime-not-discovered` | The runtime job matched no pod, so there is no `up` series for it at all. Only `serving-runtime-scrape-job-absent` can say so |
| `api-target-up-without-identity` | A target that is up and useless. The identity join returns nothing; `identity-absent-on-a-target-that-answered` reads 1 |
| `every-target-down` | Four targets, none answering. The count stays at two per job and the `up` sum reads zero — the distinction a count over a filtered vector would have lost |
| `mock-single-replica` | The mock profile renders one job and no runtime. Runtime queries are *absent* from the result rather than empty in it |
| `forbidden-labels-on-the-exposition` | Series arriving with a request identifier, a tenant, a pod name, an HTTP status, and a correlation identifier on them. The rendered `labeldrop` removes every one before a query sees it |

What each one returned is recorded, query by query, in
[the query evaluation record](../proof/telemetry/v1-s3-007-pr2-query-evaluation.md).
That file is generated by `python -m tools.telemetry_correlation --evidence` and
compared against the committed copy by the suite, so it stays a record of what the
queries returned rather than a description of what somebody expected.

## Expected empty and error states

| You see | It means |
|---|---|
| A job missing from `scrape-target-health-by-job` | Its discovery matched no pod. Read the two absence queries |
| `platform-api-scrape-job-absent` or `serving-runtime-scrape-job-absent` reading 1 | That job has no targets at all |
| `identity-absent-on-a-target-that-answered` reading 1 | An API target answered a scrape and published no identity. Every identity join is empty until it does |
| `model-readiness-absent` reading 1 | Expected, today and until the serving-runtime adapter is instrumented |
| `throughput-joined-to-build-identity` empty while `request-throughput-by-workload-model-and-outcome` is not | The identity is missing, not the traffic. The join drops every element with no counterpart rather than returning a partial answer |
| Any query empty in a store with no collector | Everything. Nothing scrapes either endpoint, so nothing is in any store |
| A non-zero `api-and-runtime-in-flight-side-by-side` | Expected. The two count different boundaries and the collection record already says they are not expected to agree |
| A `histogram_quantile` returning `NaN` | The bucket set reaching it had no `+Inf` bucket, so there is no total to take a fraction of |
| A many-to-many match error | A join whose key both sides share on more than one series. `no-cross-tier-identity-join` below is the case this release has |

## What cannot be correlated

Four gaps, and each says what would close it.

- **`no-cross-tier-identity-join`.** A serving-runtime series cannot be joined to the
  API's identity series. `inferops_build_info` is one series per API process, and the
  labels a runtime series shares with it — `k8s_namespace` and `inferops_model_id` —
  are the same for every API replica, so the match is many-to-many the moment there is
  more than one. Prometheus refuses it and so does this evaluator. What is available
  instead is the operating identity the runtime job attaches directly:
  `inferops_runtime_id`, `inferops_model_id`, `inferops_workload_id`, and
  `deployment_environment`. The immutable identity — version, release, revision, image
  digest — stays on the API's `inferops_build_info` and is not reachable from a runtime
  series. Closing it would mean an identity series the serving runtime published, which
  means instrumenting the serving-runtime adapter.
- **`no-resource-correlation`.** Latency and throughput cannot be correlated with
  resource use. `api-process-cpu-by-replica` is the only resource series with a source;
  container and pod CPU and memory, declared requests and limits, restarts, and pod
  phase have none in the accepted local cluster, which is `kind` with no
  metrics-server, no kube-state-metrics, and no cAdvisor scrape.
- **`no-readiness-or-model-load-signal`.** Model readiness, model load duration, and
  queue wait are specified, assigned to the serving-runtime adapter, and emitted by
  nothing. Three queries here read them and are published with the class that says so.
  `inferops:model_ready_absent:platform_api` reads 1 and
  `inferops:inference_requests_deferred:runtime` shows that queueing happened and never
  how long.
- **`no-trace-correlation`.** No query here joins a metric to a trace or a log record.
  No tracer, propagator, or exporter is selected, and the correlation identifier is a
  log field that may never be a metric label — so the join from a slow request to the
  record of that request does not exist and is not being approximated.

## What this does not establish

- `no-engine-has-run-these`. No Prometheus has parsed, loaded, or evaluated any
  expression here. Every result came from the declared subset evaluator in this
  repository.
- `fixtures-are-synthetic`. Every series in every scenario was written by hand to have
  the label set the rendered relabelling would attach. Nothing was scraped and no value
  was measured.
- `the-subset-is-a-subset`. The evaluator implements a declared subset with declared
  differences from the engine. A query outside it is refused rather than approximated.
- `relabelling-is-modelled-not-executed`. The collector step a fixture goes through is
  `labeldrop` alone, read as the alternation the chart writes rather than executed as a
  regex. Discovery, `keep` filters, port selection, and target-label assignment are not
  simulated.
- `recording-rules-are-evaluated-here-and-nowhere-else`. The chart's recording rules are
  read from the committed render and evaluated by this repository at each fixture
  instant, in render order. No collector evaluates them and no group interval is
  honoured.
- `an-empty-result-is-the-common-answer`. Four queries return nothing however long
  anybody waits and two have no expression at all. That is the honest state of the
  collection, published rather than omitted: a question missing from a query catalogue
  is a question somebody writes badly.
- `the-evaluator-was-corrected-by-review-not-by-an-engine`. Independent review before
  push found seven defects here — three in the evaluator's semantics or its refusal
  contract, one rule that was not enforced for half the syntax it claimed to cover,
  and three miscounts in published prose. Every one was found by reading. A
  cross-check against `promtool` remains the first follow-up and remains not done.
