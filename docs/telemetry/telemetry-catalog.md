# The telemetry catalog

Status: **accepted in part**, in
[ADR 0006](../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md).
The catalog is committed as data and machine-checked, and part of it is now
emitted. The InferOps API emits the eight metrics marked emitted in section 7 and
writes the records in section 10; the serving-runtime adapter's four metrics, the
contract validator's one, and one metric assigned to the API itself are not
emitted, and no component produces a span. No collector, store, dashboard, or
alert path is selected, and nothing scrapes the endpoint.

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

**And, since something emits, which rows are claims about a running process.** Every
metric carries an `emission` field, and an unemitted one that is not deferred states
why. A catalog whose reader has to scrape the endpoint to find out what is really
there has stopped being the record.
[The API instrumentation document](api-instrumentation.md) is where the emitted half
is described in the shape an operator reads it in: the exposition, a redacted record,
and the configuration a deployment states its identity in.

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
| `X-InferOps-Correlation-ID` | inbound and outbound | A business correlation identifier that survives retries and asynchronous transitions, which a span identifier deliberately does not. Read and echoed on every response, including a refusal, and validated rather than trusted |

Assignment at the edge is the part that earns its place. A request that is refused
before it reaches a handler is precisely the one nobody can find afterwards, and an
identifier minted inside the handler is an identifier the refusal never had. The API
does this: a well-formed `X-InferOps-Correlation-ID` is accepted, anything else is
replaced by a generated one rather than refusing the request, and the identifier the
API used is the one it echoes and the one every record it writes carries.

**Half of this propagates and half does not.** The correlation identifier and the
request identifier are assigned at the edge and written to every record. No tracer,
propagator, exporter, or SDK is selected and no span exists, so `traceparent` and
`tracestate` are neither read nor written, and `trace.id` and `span.id` are
specified fields nothing populates.

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

| Field | Question it answers | Sensitivity | Cardinality | Identity only? |
|---|---|---|---|---|
| `service.name` | Which component emitted this? | `operational` | `singleton` | no |
| `service.version` | Which build of that component, exactly? | `operational` | `unbounded` | yes |
| `deployment.environment` | Is this a development host, and may a result from it be cited as anything else? | `operational` | `bounded-small` | no |
| `inferops.capability.id` | Which declared capability is this process serving? | `operational` | `singleton` | yes |
| `inferops.release.id` | Which release installed this, so that a regression ties to the change that shipped it? | `operational` | `unbounded` | yes |
| `k8s.pod.name` | Which replica produced this record, when one replica behaves differently? | `operational` | `unbounded` | no |
| `inferops.model.revision` | Which immutable model revision produced this? | `operational` | `bounded-small` | yes |
| `inferops.runtime.image.digest` | Which runtime image, by digest rather than by a movable tag? | `operational` | `bounded-small` | yes |
| `inferops.adapter.kind` | Which kind of serving adapter was this deployment composed with? | `operational` | `bounded-small` | yes |

Six of these are identity-only: the service version, the capability, the release,
the model revision, the runtime image digest, and the adapter kind. They reach metrics through the
identity metric and never as an operational label, which is what lets a record pin
immutable versions without multiplying every series by the release history. That is a
property of the data rather than a description — an identity-only attribute may not
declare `metric-label` at all, and a test refuses one that does.

`inferops.adapter.kind` is identity for the same reason and earns one more sentence,
because it is the field that keeps a mock scrape visibly a mock scrape. It takes two
values, `mock` and `real`, it does not vary within a process, and it is **derived
from the adapter selection rather than configured beside it** — a second variable
carrying this label would be a way to compose a real adapter and publish `mock`, or
the reverse. It reaches operational series indirectly, through
`inferops.runtime.id`, which already carries the mock runtime's registered
identifier.

`k8s.pod.name` is **not** among them, and the difference is worth being exact about.
It is unbounded for the same reason the release identifier is — a restarted pod is a
new name and nothing retires the old one — but it is not identity: it varies between
replicas of the same build, so putting it on the identity metric would stop that
metric being one series per build. It is a log field, and it reaches no metric at
all. The column above is compared against the catalog data by a test, so this table
cannot say one thing while the data says another.

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
| `inferops.request.id` | Which single synchronous request was this, as the caller was told? | `request-scoped-identifier` | `unbounded` | no |
| `inferops.correlation.id` | Which pieces of work belong to the same request? | `request-scoped-identifier` | `unbounded` | no |
| `trace.id` | Which trace was this span part of? | `request-scoped-identifier` | `unbounded` | no |
| `span.id` | Which attempt or operation was this? | `request-scoped-identifier` | `unbounded` | no |

Five of these are worth a sentence, because each is a label somebody will
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
- `inferops.workload.id` is the one caller-shaped label there is, and it is **not**
  read off a request. It is deployment configuration, because one V1 deployment
  serves one workload and a value that is constant per process is bounded by
  construction. A workload identifier taken from a caller's header would be an
  unbounded label wearing a bounded one's name, and it is not read.

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
| `inferops.cost.record.id` | The cost method is defined, in [ADR 0007](../architecture/decisions/ADR-0007-inference-cost-method.md); nothing computes or emits a cost record, so there is no value to carry |
| `inferops.evaluation.decision` | There is no evaluation capability here and none is in V1 scope |

## 7. Metrics

Thirteen active metrics, covering eight signal families. Every one names the
question it answers, the maximum number of series it can produce, and whether
anything in this repository actually emits it.

| Metric | Instrument | Labels | Max series | Emitted? | Answers |
|---|---|---|---|---|---|
| `inferops_build_info` | gauge | identity only | 25 | yes | Which build, model revision, and runtime image produced everything else here? |
| `inferops_inference_requests_total` | counter | workload, model, outcome | 500 | yes | Is the platform serving, and what fraction succeeds? |
| `inferops_inference_errors_total` | counter | workload, error code | 300 | yes | Which named failure is responsible? |
| `inferops_inference_request_duration_seconds` | histogram | workload, model | 1750 | yes | How long does a request take, at the tail? |
| `inferops_inference_queue_duration_seconds` | histogram | workload, model | 1500 | no | How much of that was waiting rather than working? |
| `inferops_inference_requests_in_flight` | gauge | workload, model | 125 | yes | How much work is in progress right now? |
| `inferops_inference_tokens_total` | counter | workload, model, direction | 250 | yes | How many tokens in and out, where reported? |
| `inferops_model_load_duration_seconds` | histogram | model, runtime, outcome | 720 | no | How long until a model is servable, and how often does that fail? |
| `inferops_model_ready` | gauge | workload, model | 125 | no | Is the model servable right now? |
| `inferops_readiness_check_failures_total` | counter | workload, component | 150 | yes | Which component is refusing traffic? |
| `inferops_workload_document_rejections_total` | counter | rule | 24 | no | Which validation rule rejects real documents? |
| `inferops_process_resident_memory_bytes` | gauge | none | 25 | no | How much memory is this process holding? |
| `inferops_process_cpu_seconds_total` | counter | none | 25 | yes | How much processor time is it consuming? |

**Five active metrics are not emitted, and each says why in the data.** Four of them
belong to an emitter that is not instrumented: the queue histogram, the model-load
histogram, and the readiness gauge are the serving-runtime adapter's, because the
adapter is the only component that sees the boundary those three describe; the
document-rejection counter is the contract validator's, and the validator is a
library and a command invoked by a person or a test rather than a running service,
so it has no process to hold a counter for the life of.

The fifth is assigned to the API and still absent, which is the one worth reading
twice. `inferops_process_resident_memory_bytes` has no source this distribution may
use: the only per-process memory figure the standard library exposes is
`/proc/self/statm`, a module under `src/inferops` may not read a path — the property
`tests/architecture/test_domain_dependency_boundary.py` enforces so that the
distribution stays usable from a wheel — and every other source is a runtime
dependency this project does not declare. The endpoint names the absence in a
comment rather than publishing a zero, because a zero would be a measurement
claiming this process holds no memory.

Three of the emitted ones carry a decision that is not obvious:

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
image digest, and adapter kind here rather than on every operational metric is the
difference between recording immutable versions and multiplying every series by
them. It is one series per process however its labels are resolved: identity arrives
in two steps — what configuration stated, then what the adapter reported at startup
— and the second replaces the first rather than sitting beside it, because two
identity series for one process is worse than none.

Three metrics are defined and deferred:

| Metric | Why it is deferred |
|---|---|
| `inferops_inference_time_to_first_token_seconds` | V1 has no streaming path, so this would be the same measurement as request duration under a different name |
| `inferops_inference_retries_total` | No retry or fallback path exists, and a counter that can only read zero looks like a healthy system rather than an absent feature |
| `inferops_cost_records_total` | The cost method is defined and no component computes or emits a cost record, so this counter could only ever read zero |

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
measurement, and no store has been tested with it — nothing scrapes the endpoint,
so no store has held a single one of these series.

What a running process actually holds is far below the declared bound and for an
uninteresting reason: one deployment serves one workload and one model, so the
label products that the budget bounds at twenty-five workloads and five models
resolve to one of each. The budget is a ceiling for a deployment this project does
not yet run, and the ceiling is what the suite checks.

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
as failed. The platform now counts the requests it receives itself, in
`inferops_inference_requests_total`, which needed no exporter, no sidecar, and no
change to the runtime. That closes the compensating obligation and fixes nothing
about the runtime, which still exposes no counter.

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
| Field rule | An allowlist of the attribute names this catalog publishes. A field outside it is refused rather than written |
| Destination | The stream the composition point supplies. No log store, shipper, retention window, or access rule is selected |

Seven events are written, and they are the whole value set of `inferops.event`:

| Event | Level | When |
|---|---|---|
| `deployment.started` | info | The adapter has been initialized and the deployment has begun accepting work |
| `deployment.draining` | info | The deployment has stopped accepting work and has begun its drain |
| `deployment.stopped` | info | The drain has finished and the adapter has been released |
| `request.received` | info | An inference request has been routed, written before anything can fail |
| `request.completed` | info | An inference request closed with a success |
| `request.refused` | warn | An inference request closed with a canonical refusal |
| `readiness.failed` | warn | A readiness check answered no, naming the component that answered it |

There is no message field, and its absence is the point. A record is identified by
its event value and carries named fields. Prose that varies per request is the field
into which a caller's data eventually arrives, and it is also the field no query can
match on reliably.

The conditional fields — workload, workload version, owner, tenant, model, runtime,
outcome, error code, rule, field location, status, duration, request, trace, span,
finish reason, and pod — are listed with the condition each one applies under in the
catalog data. Not all of them are ever written: `inferops.tenant.id` has no producer,
`inferops.rule.id` and `inferops.field.path` belong to the validator, and `trace.id`
and `span.id` need a tracer that does not exist.

The allowlist is what makes the exclusions structural rather than remembered. There
is no name in it for a prompt, a completion, a provider error body, a secret, an
authorization header, or a value read out of a submitted document, and there is no
message field, no `extra` mapping, and no pass-through to the encoder — so a
forbidden field is not something a reviewer has to catch, it is a key that does not
exist. A rejected field name is reported and its value never is.

What is excluded, and the reasoning behind each exclusion, is in
[the redaction rules](redaction.md).

## 11. Limitations

Thirteen of them are recorded in the data. These are the ones that change how this
document should be read:

- **Only part of this emits.** The API emits eight metrics and writes seven kinds of
  record. The adapter's four metrics, the validator's one, and one of the API's own
  are specifications for behaviour that does not exist, and nothing produces a span.
- **No collector, store, dashboard, or alert path is selected.** Who would own one is
  an open question in
  [ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
  that this record deliberately does not answer. The endpoint answers when something
  scrapes it, and nothing scrapes it.
- **Records go to a stream and no further.** No log store, shipper, retention window,
  or access rule is selected, so the retention this catalog requires to be stated
  before content of any kind is written is still unstated.
- **The workload identity is configuration, not a document.** Nothing here deploys a
  workload, so the workload, version, and owner on every series and record are what a
  deployment was told to say, not values read out of a validated WorkloadContract.
- **Container and node resource use has no source, and neither does process memory.**
  The local cluster runs no metrics server; the one recorded measurement of a pod's
  memory was read from its cgroup by hand; and the process's own memory has no source
  this distribution is permitted to read.
- **The error-code budget is an estimate.** The canonical error vocabulary for
  inference is not published; only the contract validator's is.
