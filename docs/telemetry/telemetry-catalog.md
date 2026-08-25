# The telemetry catalog

Status: **accepted in part**, in
[ADR 0006](../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md).
The catalog is committed as data and machine-checked. Nothing emits it: no
component in this repository writes a metric, a log record, or a span, and no
collector, store, or dashboard is selected.

The authoritative form is
[`telemetry-catalog.v1alpha1.json`](telemetry-catalog.v1alpha1.json). This document
and that file are compared in both directions by
[`tests/telemetry/`](../../tests/telemetry/): a signal cannot appear in one without
appearing in the other, and a name this document publishes that the data does not
have is a failing test.

## What this document decides

Three things, in order of how badly each is usually got wrong.

**Where a field is allowed to go.** Every field declares a sensitivity class and a
cardinality class, and its placement is the intersection of what those two classes
permit. Nobody decides case by case whether a tenant identifier belongs in a metric
label, because the classes decide it and a test enforces the derivation.

**What each signal is for.** Every attribute and every metric states the operational
or proof question it answers, and the suite refuses one that does not. A catalog
assembled from whatever a metrics library exposes is a running cost with no reader,
and the question is what makes a signal removable later.

**What it costs.** Every metric declares a maximum series count that the suite
recomputes from its labels and bucket count. Adding a label is then a visible number
rather than a line of code.

## 1. Correlation

| Rule | Decision |
|---|---|
| Standard | W3C Trace Context across synchronous boundaries |
| Assignment | The correlation identifier is assigned at the edge, by the first InferOps component to see the request, before anything downstream can fail |
| Retries | A retry reuses the correlation identifier and takes a new span |
| Asynchronous boundaries | Producer and consumer spans are linked rather than nested, and the identifier travels in the message envelope |
| Placement | Correlation, trace, and span identifiers are log fields and span attributes, and never metric labels |

Three headers carry it, and none of them is required of a caller:

| Header | Direction | Purpose |
|---|---|---|
| `traceparent` | inbound and outbound | The W3C trace context, when the caller already has one. Absent, the edge starts a new trace rather than refusing the request |
| `tracestate` | inbound and outbound | Vendor trace state, carried through unchanged. This project neither reads nor writes entries in it |
| `X-InferOps-Correlation-ID` | inbound and outbound | A business correlation identifier that survives retries and asynchronous transitions, which a span identifier deliberately does not. Echoed on every response, including a refusal |

Assignment at the edge is the part that earns its place. A request that is refused
before it reaches a handler is precisely the one nobody can find afterwards, and an
identifier minted inside the handler is an identifier the refusal never had.

**What is not decided:** no tracer, propagator, exporter, or SDK. Nothing reads or
writes any of these headers today.

## 2. Placement is derived, not chosen

Six places a value can end up, with what each one costs:

| Placement | What it costs |
|---|---|
| `resource-attribute` | Attached once per emitting process. Cheap, and never varied per request |
| `metric-label` | Every distinct combination of label values is a separate time series the store keeps for its whole retention window |
| `info-label` | A label on an identity metric, which emits exactly one series per process whatever its labels say |
| `log-field` | A field in a structured record, kept for the log store's retention window |
| `trace-attribute` | An attribute on a span |
| `evidence-field` | A field in a committed record under [`docs/proof/`](../proof/). Public, permanent, and not deletable in any useful sense |

Six sensitivity classes, and what each one may use:

| Class | Meaning | May be placed in |
|---|---|---|
| `operational` | A value this project generates about its own operation | anywhere |
| `caller-supplied-identifier` | An identifier that arrived through a validated workload document | anywhere |
| `tenant-attributable` | An identifier that attributes activity to a customer | logs and traces only |
| `request-scoped-identifier` | An identifier minted per request or per span | logs, traces, evidence |
| `user-content` | A prompt, a response, a chat history, a provider error body | nowhere |
| `secret` | Credential material, or a value read out of where credentials are kept | nowhere |

Six cardinality classes, and the bound each one carries:

| Class | Bound | May be placed in |
|---|---|---|
| `singleton` | One value per emitting process | anywhere |
| `bounded-small` | An enumeration fixed by a specification, at most 32 values | anywhere |
| `bounded-deployment` | Bounded by how many workloads, models, or runtimes are deployed, at most 128 | anywhere |
| `bounded-schema` | Bounded by the size of a published schema, at most 512 | logs, traces, evidence |
| `unbounded` | Grows without limit: per request, per restart, per release | resource attributes, identity labels, logs, traces, evidence |
| `measurement` | A number that is measured rather than chosen | logs, traces, evidence |

The two exclusions worth arguing for:

`tenant-attributable` is barred from metrics and from evidence records even though a
tenant identifier is neither secret nor content. A metrics store labelled by tenant
is a customer list with a retention window; a committed evidence record is public
and permanent. Neither consequence is what anybody intended when they added the
label.

`unbounded` covers more than it looks like it does. A pod name is unbounded, because
a restarted pod is a new name and nothing retires the old one — a pod label grows a
metric's series count once per restart, forever. A workload version is unbounded for
the same reason. Both are useful, and both are log fields.

## 3. Resource attributes

Attached once per emitting process, and never varied per request.

| Field | Question it answers | Sensitivity | Cardinality |
|---|---|---|---|
| `service.name` | Which component emitted this? | `operational` | `singleton` |
| `service.version` | Which build of that component, exactly? | `operational` | `unbounded` |
| `deployment.environment` | Is this a development host, and may a result from it be cited as anything else? | `operational` | `bounded-small` |
| `inferops.capability.id` | Which declared capability is this process serving? | `operational` | `singleton` |
| `inferops.release.id` | Which release installed this, so that a regression ties to the change that shipped it? | `operational` | `unbounded` |
| `k8s.pod.name` | Which replica produced this record, when one replica behaves differently? | `operational` | `unbounded` |
| `inferops.model.revision` | Which immutable model revision produced this? | `operational` | `bounded-small` |
| `inferops.runtime.image.digest` | Which runtime image, by digest rather than by a movable tag? | `operational` | `bounded-small` |

The last four of these are marked identity-only: they reach metrics through the
identity metric and never as an operational label. That distinction is what lets a
record pin immutable versions without multiplying every series by the release
history.

## 4. Request attributes

Vary per request. These are the fields a metric label may be drawn from, and most of
them still are not.

| Field | Question it answers | Sensitivity | Cardinality | Metric label? |
|---|---|---|---|---|
| `inferops.workload.id` | Which workload is this request for, and which one is failing? | `caller-supplied-identifier` | `bounded-deployment` | yes |
| `inferops.workload.version` | Which version of that document was in force? | `caller-supplied-identifier` | `unbounded` | no |
| `inferops.owner.id` | Who is accountable when this has to be turned off? | `caller-supplied-identifier` | `bounded-deployment` | no |
| `inferops.tenant.id` | Which tenant's activity was this? | `tenant-attributable` | `bounded-deployment` | no |
| `inferops.model.id` | Which model served this? | `caller-supplied-identifier` | `bounded-deployment` | yes |
| `inferops.runtime.id` | Which serving runtime answered? | `operational` | `bounded-deployment` | yes |
| `inferops.outcome` | Did this succeed, and if not, whose fault and what kind? | `operational` | `bounded-small` | yes |
| `inferops.error.code` | Which named failure was it, in the caller's vocabulary? | `operational` | `bounded-small` | yes |
| `inferops.rule.id` | Which validation rule is rejecting real documents? | `operational` | `bounded-small` | yes |
| `inferops.field.path` | Where in the document was the problem? | `operational` | `bounded-schema` | no |
| `inferops.component` | Which internal component failed a readiness check? | `operational` | `bounded-small` | yes |
| `inferops.token.direction` | Were these tokens read or written? | `operational` | `bounded-small` | yes |
| `inferops.finish.reason` | Did the caller get a whole answer or a truncated one? | `operational` | `bounded-small` | no |
| `inferops.correlation.id` | Which pieces of work belong to the same request? | `request-scoped-identifier` | `unbounded` | no |
| `trace.id` | Which trace was this span part of? | `request-scoped-identifier` | `unbounded` | no |
| `span.id` | Which attempt or operation was this? | `request-scoped-identifier` | `unbounded` | no |

Four of these are worth a sentence, because each is a label somebody will
reasonably propose:

- `inferops.owner.id` is bounded and safe and still not a label. Ownership is a
  property of the workload and joins to it; two labels that always vary together are
  one label and a lookup.
- `inferops.finish.reason` is carried by no metric at all. A rate of finish reasons
  answers no operational question anyone has asked yet, and a label that exists
  because it could exist is how a cardinality budget gets spent without a decision.
- `inferops.field.path` is a location in a schema, never the value found there. The
  contract validator already refuses to repeat a value read out of a document back
  to the caller; a log record is the same surface with a longer memory.
- `inferops.error.code` carries a canonical code and never a message. The inference
  error vocabulary is not published yet, so this field declares a budget rather than
  a value list — recorded below as a limitation rather than filled in with guesses.

## 5. Record fields

Fields of a log record or a span rather than properties of a request.

| Field | Question it answers | Sensitivity | Cardinality |
|---|---|---|---|
| `timestamp` | When did this happen? | `operational` | `measurement` |
| `level` | How urgent is this record? | `operational` | `bounded-small` |
| `inferops.event` | What kind of thing happened, in a form a query can match? | `operational` | `bounded-small` |
| `inferops.duration.ms` | How long did this operation take, for the one request being read about? | `operational` | `measurement` |
| `http.response.status_code` | What did the caller actually receive? | `operational` | `bounded-small` |

`inferops.duration.ms` is the clearest case for the `measurement` class. A duration
used as a metric label produces one series per distinct millisecond, which is the
fastest available way to make a metrics store unusable. It is a value; the histogram
is where it becomes a signal.

`http.response.status_code` is bounded and would be safe as a label, and is still
not one. `inferops.outcome` is the dimension the metrics are cut by, and two labels
that mean roughly the same thing get used inconsistently within a month.

## 6. Registered and deferred

Three fields are named and deliberately not used, so that the first code to need one
adopts the agreed name instead of coining a second:

| Field | Why it is deferred |
|---|---|
| `inferops.retry.count` | V1 has no retry and no fallback path |
| `inferops.cost.record.id` | No cost method is defined; naming the field would not make one exist |
| `inferops.evaluation.decision` | There is no evaluation capability here and none is in V1 scope |

## 7. Metrics

Thirteen active metrics, covering eight signal families. Every one names the
question it answers and the maximum number of series it can produce.

| Metric | Instrument | Labels | Max series | Answers |
|---|---|---|---|---|
| `inferops_build_info` | gauge | identity only | 25 | Which build, model revision, and runtime image produced everything else here? |
| `inferops_inference_requests_total` | counter | workload, model, outcome | 500 | Is the platform serving, and what fraction succeeds? |
| `inferops_inference_errors_total` | counter | workload, error code | 300 | Which named failure is responsible? |
| `inferops_inference_request_duration_seconds` | histogram | workload, model | 1750 | How long does a request take, at the tail? |
| `inferops_inference_queue_duration_seconds` | histogram | workload, model | 1500 | How much of that was waiting rather than working? |
| `inferops_inference_requests_in_flight` | gauge | workload, model | 125 | How much work is in progress right now? |
| `inferops_inference_tokens_total` | counter | workload, model, direction | 250 | How many tokens in and out, where reported? |
| `inferops_model_load_duration_seconds` | histogram | model, runtime, outcome | 720 | How long until a model is servable, and how often does that fail? |
| `inferops_model_ready` | gauge | workload, model | 125 | Is the model servable right now? |
| `inferops_readiness_check_failures_total` | counter | workload, component | 150 | Which component is refusing traffic? |
| `inferops_workload_document_rejections_total` | counter | rule | 24 | Which validation rule rejects real documents? |
| `inferops_process_resident_memory_bytes` | gauge | none | 25 | How much memory is this process holding? |
| `inferops_process_cpu_seconds_total` | counter | none | 25 | How much processor time is it consuming? |

Three of these carry a decision that is not obvious:

**Two counters rather than one.** `inferops_inference_requests_total` carries the
outcome and `inferops_inference_errors_total` carries the canonical error code.
Carrying both on one counter would multiply to tens of thousands of series to answer
two questions that are never asked at the same moment — first *how much is broken*,
then *what is broken*.

**No outcome label on the latency histogram.** The budget is better spent on bucket
resolution than on separating the latency of failures, which the error counter
already counts. A histogram's series count is its label product multiplied by the
number of buckets, and that multiplication is where a latency metric becomes the
most expensive thing on the endpoint.

**One identity metric instead of identity on everything.** `inferops_build_info` is
always 1 and exists only to carry its labels. Putting the version, model revision,
and image digest here rather than on every operational metric is the difference
between recording immutable versions and multiplying every series by them.

Three metrics are defined and deferred:

| Metric | Why it is deferred |
|---|---|
| `inferops_inference_time_to_first_token_seconds` | V1 has no streaming path, so this would be the same measurement as request duration under a different name |
| `inferops_inference_retries_total` | No retry or fallback path exists, and a counter that can only read zero looks like a healthy system rather than an absent feature |
| `inferops_cost_records_total` | No cost method is defined, so counting cost records would fix the wrong thing first |

> [!IMPORTANT]
> Latency, throughput, and capacity signals exist to operate the platform. V1
> publishes no figure derived from any of them — that restriction comes from
> [the project boundaries](../architecture/project-boundaries.md) and this catalog
> does not lift it. A dashboard screenshot is a publication.

## 8. The cardinality budget

| Ceiling | Value |
|---|---|
| Per metric | 2,000 series |
| Total, across active metrics | 10,000 series |
| Currently declared | 5,519 series |

The budget is arithmetic over the declared bounds, recomputed by the suite from each
metric's labels and buckets. It establishes that the catalog is internally
affordable on the single-node environment this project targets. It is not a
measurement, and no store has been tested with it.

## 9. What the selected runtime already emits

Measured once, on one host, on 2026-08-24, from one runtime image digest, and
recorded in
[the runtime feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md).
Every series below appears in that record; a test compares the two, because a
mapping table is the easiest place in a repository to publish a series that does not
exist.

| Runtime series | Instrument | Maps to |
|---|---|---|
| `llamacpp:prompt_tokens_total` | counter | `inferops_inference_tokens_total`, input |
| `llamacpp:tokens_predicted_total` | counter | `inferops_inference_tokens_total`, output |
| `llamacpp:prompt_tokens_cached_total` | counter | nothing; a runtime tuning question, not a platform operating one |
| `llamacpp:prompt_seconds_total` | counter | nothing; prefill time, related to latency and not the same measurement |
| `llamacpp:tokens_predicted_seconds_total` | counter | nothing; decode time |
| `llamacpp:n_decode_total` | counter | nothing; decode steps |
| `llamacpp:n_tokens_max` | gauge | nothing; largest context observed |
| `llamacpp:prompt_tokens_seconds` | gauge | nothing; a derived rate V1 may not publish |
| `llamacpp:predicted_tokens_seconds` | gauge | nothing; a derived rate V1 may not publish |
| `llamacpp:requests_processing` | gauge | `inferops_inference_requests_in_flight` |
| `llamacpp:requests_deferred` | gauge | `inferops_inference_queue_duration_seconds`, partially |
| `llamacpp:n_busy_slots_per_decode` | gauge | nothing; slot occupancy |
| `llamacpp:spec_decode_num_draft_tokens_total` | counter | nothing; speculative decoding, unused in the trial |
| `llamacpp:spec_decode_num_accepted_tokens_total` | counter | nothing; speculative decoding, unused |
| `llamacpp:spec_decode_num_drafts_total` | counter | nothing; speculative decoding, unused |

**One required series is absent: a cumulative request counter.** The runtime exposes
two gauges with `requests` in the name and no counter, and a gauge reading zero
between requests cannot be summed, rated, or alerted on. This is the threshold
[ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md) records
as failed. The platform counts the requests it receives itself, which needs no
exporter, no sidecar, and no change to the runtime — and that is a plan, not a fix.

`llamacpp:requests_deferred` maps only partially, and the gap matters: it shows that
queueing happened and never how long any request waited. The queue histogram is the
adapter's measurement, not the runtime's.

## 10. Logs

| Rule | Decision |
|---|---|
| Format | One JSON object per line, UTF-8. A stack trace is a single escaped field, not a run of lines a collector will split into unrelated records |
| Levels | debug, info, warn, error, fatal |
| Always present | `timestamp`, `level`, `inferops.event`, `service.name`, `inferops.correlation.id` |
| Free-form message | None |

There is no message field, and its absence is the point. A record is identified by
its event value and carries named fields. Prose that varies per request is the field
into which a caller's data eventually arrives, and it is also the field no query can
match on reliably.

The conditional fields — workload, owner, tenant, model, runtime, outcome, error
code, rule, field location, status, duration, trace, span, finish reason, and pod —
are listed with the condition each one applies under in the catalog data.

What is excluded, and the reasoning behind each exclusion, is in
[the redaction rules](redaction.md).

## 11. Limitations

Ten of them are recorded in the data. These are the ones that change how this
document should be read:

- **Nothing emits any of this.** Every metric, attribute, and log rule specifies
  behaviour for components that do not exist.
- **No collector, store, dashboard, or alert path is selected.** Who would own one is
  an open question in
  [ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
  that this record deliberately does not answer.
- **Redaction is a rule, not a mechanism.** There is no redacting logger, no field
  allowlist in code, and no test that inspects a real log line, because there are no
  log lines.
- **Container and node resource use has no source.** The local cluster runs no
  metrics server; the one recorded measurement of a pod's memory was read from its
  cgroup by hand.
- **The error-code budget is an estimate.** The canonical error vocabulary for
  inference is not published; only the contract validator's is.
