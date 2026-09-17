# The inference operations dashboard

Status: **defined as code, checked, and validated once on one provider.** The
dashboard is a committed record whose 29 panels run 30 expressions, each held to the
correlation query policy and evaluated over the committed synthetic scenarios, and a
Grafana dashboard JSON generated from it. Nineteen of the expressions are accepted
correlation queries; eleven are new in this record. All 30 have been asked of a real
Prometheus — the collector of one single-replica release on `docker-desktop` — in
nine controlled states, and one Grafana has imported the JSON and rendered it. See
[the V1-S4-002-PR2 validation record](../proof/telemetry/v1-s4-002-pr2-dashboard-validation.md).

The authoritative form is
[`inference-operations-dashboard.v1alpha1.json`](inference-operations-dashboard.v1alpha1.json).
The Grafana JSON is
[`deploy/grafana/inferops-inference-operations.json`](../../deploy/grafana/inferops-inference-operations.json),
and [`tests/telemetry/test_inference_dashboard.py`](../../tests/telemetry/test_inference_dashboard.py)
regenerates it from the record and fails if a byte differs.

This document describes what the dashboard shows and why. How to read it in thirty
seconds, and which conclusions each panel cannot support, is
[the operator guide](inference-operations-dashboard-operator-guide.md).

## What it is for, and the failure it is built against

An operator opening a dashboard during an incident has one question before any other:
*is that number real?* The collector this release installs keeps its series in the
pod, several specified signals are emitted by nothing, and a Prometheus panel with no
data looks the same whether the system is idle, the target is gone, or the metric was
never emitted. [The correlation query document](telemetry-correlation-queries.md)
counts six causes with one appearance.

So every panel here says which of four states it is in, and the four look different:

| State | What the panel shows |
|---|---|
| `zero` | The number 0. Only a panel that declares what its zero means may fill one, and it fills it only from something that proves a reading happened: a since-start count while an API process is publishing its identity, a share where requests have been counted. Every zero fill is a count, never a rate — see below |
| `missing` | The panel's own no-value text, saying what an empty result from *that* expression can mean. Never a number |
| `not-emitted` | A title saying "not emitted", and a no-value text naming the component that is not instrumented |
| `not-answerable` | A text panel with no query, titled "not answerable", saying what would have to exist first |

And one signal is kept apart from all of them. **Scrape reachability is not
readiness.** `up` says the collector reached a process. [The recovery
run](../proof/telemetry/v1-s3-011-pr2-telemetry-during-recovery.md) recorded a
deleted serving pod still reading up for fifteen seconds, and a target can answer a
scrape while serving nothing. A panel reading `up` or an `inferops:scrape_` series
must say `scrape` in its title and may not use a word from the checker's readiness
and health list. That is a list, and a list misses synonyms it was not given: the
suite pins one it still accepts.

**Why the zeros are counts and not rates.** The API creates a labelled counter series
on its first event, so the series first appears at whatever it has counted by its
first scrape — at least 1. A rate never sees those events: the recovery run's single
readiness refusal would have read `0` per second, and in the validation run ten
refused requests did. A zero filled over a rate would therefore read `0` beside a real failure. So
the four panels that fill a zero are counts since the API processes started, which do
see the first event and disappear at once when a target fails its scrape (a deleted
pod's series linger until they go stale). The rate
timeseries remain, and each says what a rate cannot see.

## Where it reads from

One data source: the release's own collector, chosen through a single Grafana
data-source variable. The collector is release-scoped, so choosing it chooses the
release, and no panel names a job or filters by namespace. A store holding two
releases' series at once is **not supported** — the totals would add them together.

The format is Grafana dashboard JSON, schema version 39, and that is a format rather
than a service. [ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
`D7` was amended to make the dashboard *definition* a repository artifact,
`inference-operations-dashboard` in [the ownership inventory](../architecture/resource-ownership.md).
Which Grafana runs it, who owns that server, and where it is exposed stay undecided
under `telemetry-backend`, together with alert routing.

## The panels

Rows follow the questions an operator asks, in the order they ask them. The first row
comes first on purpose: until it reads, every other panel is missing.

| Panel | Question | Signal | What it reads |
|---|---|---|---|
| `scrape-targets-answering-by-tier` | is-anything-collected | scrape-reachability | accepted `scrape-target-health-by-job` |
| `scrape-jobs-that-discovered-no-pod` | is-anything-collected | scrape-reachability | accepted `platform-api-scrape-job-absent`, `serving-runtime-scrape-job-absent` |
| `api-identity-not-published` | is-anything-collected | value | accepted `identity-absent-on-a-target-that-answered` |
| `readiness-checks-failed-since-start` | is-it-ready | value | new: failed readiness checks since start, summed, zero-filled from a published identity |
| `readiness-refusals-by-component` | is-it-ready | value | accepted `readiness-check-failures-by-component` |
| `model-readiness` | is-it-ready | not-emitted, per replica | accepted `model-readiness-by-workload`, `model-readiness-absent` |
| `pod-container-and-runtime-readiness` | is-it-ready | not-answerable | nothing: needs kube-state-metrics and an instrumented adapter |
| `requests-since-start` | what-traffic | value | new: requests since start, summed, zero-filled from a published identity |
| `request-rate-by-outcome` | what-traffic | value | accepted `request-throughput-by-workload-model-and-outcome` |
| `api-in-flight-by-replica` | what-traffic | value, per replica | accepted `in-flight-requests-by-replica` |
| `runtime-processing-and-deferred` | what-traffic | value | new: runtime in-flight by workload and model; accepted `runtime-deferred-requests` |
| `request-latency-quantiles` | latency-and-throughput | value | new: P50 and P99; accepted `request-latency-p95-by-workload-and-model` |
| `successful-requests-per-second` | latency-and-throughput | value | new: requests with outcome success, by workload and model |
| `queue-wait-p95` | latency-and-throughput | not-emitted | accepted `queue-wait-p95` |
| `errors-since-start` | what-errors | value | new: errors since start, summed, zero-filled from a published identity |
| `unsuccessful-request-ratio` | what-errors | value | new: non-success over all requests since start, zero-filled only where requests were counted |
| `errors-by-code` | what-errors | value | accepted `error-rate-by-workload-and-code` |
| `model-load-duration-p95` | model-load-and-recovery | not-emitted | accepted `model-load-duration-p95` |
| `api-processes-publishing-identity` | model-load-and-recovery | value | new: identity series counted by tier |
| `restarts-and-pod-phase` | model-load-and-recovery | not-answerable | nothing: needs kube-state-metrics |
| `api-process-cpu-by-replica` | resources-and-replicas | value, per replica | accepted `api-process-cpu-by-replica` |
| `api-process-memory` | resources-and-replicas | not-emitted, per replica | accepted `api-process-memory-by-replica` |
| `container-and-pod-resource-use` | resources-and-replicas | not-answerable | nothing: needs cAdvisor, metrics-server, or kube-state-metrics |
| `scrape-targets-discovered-by-tier` | resources-and-replicas | scrape-reachability | new: the recorded target count |
| `build-identity-per-replica` | what-is-running | value, per replica | accepted `build-identity-per-replica` |
| `runtime-operating-identity` | what-is-running | value | new: runtime series counted by environment, workload, model, and runtime |
| `cluster-provider` | what-is-running | not-answerable | nothing: no telemetry attribute names a provider |
| `tokens-per-second-at-the-api` | what-tokens | value | accepted `tokens-by-direction-from-the-api` |
| `tokens-per-second-at-the-runtime` | what-tokens | value | accepted `tokens-by-direction-from-the-runtime` |

Three things in that table are worth reading twice.

**The identity-absence panel does not say a target answered.** It repeats the
accepted query `identity-absent-on-a-target-that-answered`, whose recorded absence
does not read `up`: it reads `1` when a target answered without an identity, and
equally when every API target is down or none was discovered. The first draft of this
dashboard titled it as though a target had answered. It is now titled for what it
reads, and it is meant to be read beside the two scrape panels. The accepted query's
name, and the chart's rule comment, still say more than the expression does.

**There is no readiness panel that reads a number about the model.** The platform
emits one readiness signal — the API's own refusals — and the model's readiness is
specified, assigned to the serving-runtime adapter, and emitted by nothing. The panel
reads the recorded absence, which is `1`, and shows *not emitted*.

**The replica figures are not replica counts.** `scrape-targets-discovered-by-tier` is
the pods the collector found with a metrics port, and `api-processes-publishing-identity`
is the API processes it has read. Neither is the desired count or the ready count, and
both follow discovery and scrape timing, so both can lag a deletion.

**Provider is not answerable from telemetry.** The provider a run used is verified and
recorded in its evidence record. No series carries it, and a label set from
configuration would be a claim nobody verified.

### What is deliberately not a panel

| Metric | Why |
|---|---|
| `inferops_inference_time_to_first_token_seconds` | Deferred out of V1. No streaming path, so it would be request duration again under another name |
| `inferops_inference_retries_total` | Deferred out of V1. No retry path, and a panel that can only read zero reads as health |
| `inferops_cost_records_total` | Deferred out of V1. Nothing emits a cost record |
| `inferops_workload_document_rejections_total` | Its emitter is a library and a command, not a running service, so nothing scrapes it |

The eleven native `llama-server` series that map to no InferOps concept are collected
and not panelled, for the reason [the collection document](kubernetes-telemetry-collection.md)
gives: they answer runtime tuning questions, not the operational ones here.

## What is refused

`python -m tools.inference_dashboard` applies nine rules, and the suite drives each
one over a record corrupted to break it.

| Rule | Refuses |
|---|---|
| `panel-query-refused-by-the-correlation-policy` | An expression any correlation rule refuses — a barred or uncarried label, a series nothing produces, a claim a signal nothing emits cannot give, a join key one side lacks, a form outside the subset |
| `panel-query-drifted-from-the-accepted-query` | A query naming an accepted correlation query that is not its expression and answerability, verbatim |
| `scrape-signal-presented-as-readiness` | A panel reading a scrape signal, by name or through `__name__`, without declaring scrape reachability, or declaring it under a word from the readiness and health list |
| `panel-state-contradicts-its-queries` | A value panel reading a metric nothing emits, a not-emitted panel that does not or that carries anything but that metric and its recorded absence, a not-answerable panel with a query or no requirement, a title that does not say its state, a zero fill with no stated meaning — found with constant operands folded, so `* -0` is one — and a record whose shape the rules cannot read |
| `panel-shows-missing-as-a-number` | A query panel with no missing text, or one that reads as a number |
| `panel-reads-a-per-replica-label-without-declaring-it` | `instance` — the pod name, unbounded over retention — named, shown in a legend, or carried by a result whose labels can be derived, in a panel not declared per replica. Where a result's labels cannot be derived, the suite checks what every scenario returned instead |
| `legend-names-a-label-outside-the-query-vocabulary` | A legend placeholder naming a label no published query may name |
| `operational-question-has-no-panel` | A declared question with no panel, or a panel naming an undeclared one |
| `panel-identifier-is-malformed-or-repeated` | A non-kebab-case or repeated identifier, a malformed query reference, or a panel list that is not a list of objects |

Sensitive content has no rule of its own because it has nowhere to come from: every
label a panel may name is derived from the catalog on every run, and a prompt, a
completion, a secret, and a tenant identifier have no permitted metric placement.

## What the scenarios show

Every panel expression is evaluated over the six scenarios the correlation record
commits. The suite asserts the separations the states promise, not merely that
queries parse:

- **zero** — in `mock-single-replica` the API publishes an identity and no error
  series exists, and `errors-since-start` reads `0`;
- **missing** — in `every-target-down` the same panel is empty, and so is
  `requests-since-start`, while `scrape-targets-answering-by-tier` reads a present
  `0` for both tiers;
- **missing while no identity is published** — in `api-target-up-without-identity`
  requests are counted and `errors-since-start` is still empty. The requests prove
  the API was read; the count's zero fill is keyed to a published identity and
  nothing else, and it does not guess;
- **not emitted** — every not-emitted query is empty in every scenario, and
  `model-readiness` reads its recorded absence in every one;
- **not run under a profile** — under the mock profile the fixture evaluator does not
  run the runtime queries. That is the evaluator's profile filter: the Grafana JSON
  sends every query whatever the profile, and a runtime query against a mock
  release returns an empty result.

`python -m tools.inference_dashboard --evaluate` prints every result.

## Running the checks

```sh
python -m pytest tests/telemetry/test_inference_dashboard.py -q
python -m tools.inference_dashboard
python -m tools.inference_dashboard --evaluate
python -m tools.inference_dashboard --grafana
python -m tools.inference_dashboard --capture http://127.0.0.1:19090
```

The first four read files in this repository. None of them starts Grafana, contacts a
cluster, or queries a Prometheus. `--capture` asks the Prometheus at the URL it is
given every panel expression as an instant query and prints how each reads — empty,
zero, value, NaN, or refused. It sends no inference request and changes nothing. It
accepts only an http or https URL, ignores environment proxies, refuses redirects,
and stops with exit 1 if it cannot reach Prometheus. It does not check that the URL
is a loopback forward to a release's collector; the operator names it.

## What this does not establish

- **One Grafana, one provider, one release.** The JSON was imported into Grafana
  11.6.0 and rendered against one single-replica release on `docker-desktop`. It has
  not been checked against Grafana's own schema validation, another Grafana version,
  `kind`, or two replicas. Its structure is otherwise checked against the fields this
  repository writes.
- **A long missing text does not render legibly.** Grafana's stat panel shrinks its
  no-value text to fit, and a text longer than about a line was unreadable in the
  validation screenshots. The panel still draws no number and its title still says
  what it counts, so zero and missing stay apart; the explanation does not survive.
- **Rates miss events before a first scrape and outlive an outage.** Observed, not
  only reasoned: ten refused requests read `0` per second while the since-start count
  rose by ten, and with no API pod the request rate still read a success rate.
- **Latency quantiles include refused requests and interpolate inside a bucket.** A
  window of mostly refusals reads faster, whatever caused them, and a quantile says
  which bucket, not a figure.
- **The runtime's input tokens exclude its prompt cache**, so the two token panels
  cannot be compared on input; how far apart they are depends on prompt reuse.
- **An idle latency window is NaN, not missing.** Once the bucket series exist, a
  window with no request draws gaps rather than the missing text. The validation run
  did not observe one.
- **A zero is only as good as what it rests on.** Neither zero fill is per replica, a
  since-start count starts again when a process restarts — observed going from 33
  errors to 0 on a pod replacement — and until a replaced process's series go stale a
  count also includes it. The share of unsuccessful requests does not depend on
  identity at all. Nothing checks what a fill is keyed to — only that a panel filling
  one says what its zero means.
- **Scrape state and identity counts lag.** Both follow discovery and scrape timing.
- **A panel does not tell anybody anything.** Six alerts are defined, in
  [the alert record](inference-alerts.md), and nothing evaluates or routes one; alert
  routing is still undecided. Four of the six read expressions this dashboard also
  panels, and the panel is what an operator opens *after* being told, not instead.
