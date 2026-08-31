# What the InferOps API emits

Status: **emitting**, added by `V1-S1-008-PR1` under
[ADR 0006](../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md).
This is the first component in this repository that produces a signal.

[The catalog](telemetry-catalog.md) decides the names, the labels, the placements,
and the budget. This document is the operator-facing half of the same record: what
a scrape looks like, what a log line looks like, what a deployment has to state to
get its identity onto both, and — in the section that matters most for reading a
dashboard later — what is **not** there.

The authoritative form is still
[`telemetry-catalog.v1alpha1.json`](telemetry-catalog.v1alpha1.json), and
[`tests/telemetry/test_api_telemetry_agreement.py`](../../tests/telemetry/test_api_telemetry_agreement.py)
compares this implementation against it in both directions. Nothing here may drift
from that file without a failing build.

## The short version

| Question | Answer |
|---|---|
| What emits? | The InferOps API, and nothing else in this repository |
| How do metrics leave the process? | They do not. `GET /metrics` renders them when something scrapes it |
| How do log records leave the process? | One JSON object per line, to the stream the composition point supplies. In a deployment that is standard error |
| Is there a span? | No. No tracer, propagator, exporter, or SDK is selected |
| Is a prompt or a response ever captured? | No, and there is no flag that could turn it on |
| Has a store held any of this? | No. Nothing scrapes the endpoint and nothing collects the stream |

## Eight metrics, and what moves each one

| Metric | Moves when |
|---|---|
| `inferops_build_info` | Set once at construction and again on startup, when the adapter reports the model and runtime it is in front of. One series per process |
| `inferops_inference_requests_total` | Once per request to `/v1/chat/completions` that reached a matched route, labelled by outcome |
| `inferops_inference_errors_total` | Once per refusal of such a request, labelled by the canonical error code the caller was given |
| `inferops_inference_request_duration_seconds` | Once per closed request, measured on a monotonic clock across the whole handler |
| `inferops_inference_requests_in_flight` | Up when a request arrives, down when it closes — including when it closes by failing |
| `inferops_inference_tokens_total` | Only when the adapter reported a token count. Absent, not zero, when it did not |
| `inferops_readiness_check_failures_total` | Once per `/health/ready` that answered no, labelled by which half said so |
| `inferops_process_cpu_seconds_total` | Read from the process's own processor clock at scrape time |

Two decisions inside that table are worth stating rather than inferring.

**Only the inference endpoint is counted.** Liveness, readiness, the model list, and
the metrics scrape are not inference requests. Counting a readiness probe in
`inferops_inference_requests_total` would make the success rate a figure about a
probe loop, and a probe loop always succeeds. What readiness contributes instead is
its own counter, which names the component that refused.

**A failed request is still a request.** The close is in a `finally`, so a body
outside the frozen subset, a refusal from the adapter, a drain, and an unexpected
failure each increment the counter, decrement the in-flight gauge, and produce a
latency observation. A counter that only counts the paths somebody remembered is a
success rate that flatters the platform.

### Outcome, and why a timeout is not an error

`inferops.outcome` takes four values, and the fourth is the one that earns its place:

| Outcome | When |
|---|---|
| `success` | The caller received a completion |
| `client-error` | The refusal was the caller's fault: a body outside the subset, an unserved path, a body too large |
| `server-error` | The refusal was ours or the runtime's |
| `timeout` | A deadline elapsed — the caller's or the runtime's |

A timeout is separated from a server error because the two are operated
differently: one means add capacity or raise a deadline, the other means something
is broken, and averaging them hides both. The mapping is made from the **condition**
rather than the status, because a caller's deadline elapsing and a runtime's
deadline elapsing carry different statuses and are the same operational event.

## A scrape

Taken from a deployment serving the committed mock adapter, after one successful
completion, with the workload identity stated. It is `mock` evidence and it says so
in its own first line.

```text
# This deployment serves the committed mock serving adapter. Every series below describes a fixture replay and certifies no serving runtime.
# Metric names, labels, and the cardinality budget: docs/telemetry/telemetry-catalog.v1alpha1.json
# inferops_process_resident_memory_bytes is specified and not emitted: the only per-process memory figure the standard library exposes is a file, and a module in this distribution may not read one.
# HELP inferops_build_info Exactly which build, model revision, and runtime image produced every other series on this endpoint.
# TYPE inferops_build_info gauge
inferops_build_info{service_version="0.0.0",inferops_capability_id="",inferops_release_id="",deployment_environment="dev",inferops_adapter_kind="mock",inferops_model_id="mock-fixed-fixture",inferops_model_revision="",inferops_runtime_id="inferops-mock-serving",inferops_runtime_image_digest=""} 1
# HELP inferops_inference_requests_total Is the platform serving requests, what fraction of them succeed, and how many complete per unit of time.
# TYPE inferops_inference_requests_total counter
inferops_inference_requests_total{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture",inferops_outcome="success"} 1
# HELP inferops_inference_errors_total Which named failure is responsible for the failures, and for which workload.
# TYPE inferops_inference_errors_total counter
# HELP inferops_inference_request_duration_seconds How long a request takes end to end, at the tail rather than on average.
# TYPE inferops_inference_request_duration_seconds histogram
inferops_inference_request_duration_seconds_bucket{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture",le="0.5"} 1
inferops_inference_request_duration_seconds_bucket{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture",le="1"} 1
inferops_inference_request_duration_seconds_bucket{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture",le="2.5"} 1
inferops_inference_request_duration_seconds_bucket{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture",le="5"} 1
inferops_inference_request_duration_seconds_bucket{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture",le="10"} 1
inferops_inference_request_duration_seconds_bucket{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture",le="20"} 1
inferops_inference_request_duration_seconds_bucket{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture",le="30"} 1
inferops_inference_request_duration_seconds_bucket{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture",le="45"} 1
inferops_inference_request_duration_seconds_bucket{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture",le="60"} 1
inferops_inference_request_duration_seconds_bucket{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture",le="120"} 1
inferops_inference_request_duration_seconds_bucket{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture",le="300"} 1
inferops_inference_request_duration_seconds_bucket{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture",le="+Inf"} 1
inferops_inference_request_duration_seconds_sum{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture"} 0
inferops_inference_request_duration_seconds_count{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture"} 1
# HELP inferops_inference_requests_in_flight How much work is in progress right now, and is it saturating.
# TYPE inferops_inference_requests_in_flight gauge
inferops_inference_requests_in_flight{inferops_workload_id="support-assistant",inferops_model_id="mock-fixed-fixture"} 0
# HELP inferops_inference_tokens_total How many tokens were read and written, where the runtime reports them.
# TYPE inferops_inference_tokens_total counter
# HELP inferops_readiness_check_failures_total Which component is failing its readiness check, when the platform is refusing traffic.
# TYPE inferops_readiness_check_failures_total counter
# HELP inferops_process_cpu_seconds_total How much processor time the emitting process is consuming.
# TYPE inferops_process_cpu_seconds_total counter
inferops_process_cpu_seconds_total 0.21875
```

Four things a reader should take from it, in order of how easily each is missed.

**The label names are underscored and the attribute names are dotted.** The
Prometheus text format admits only `[a-zA-Z0-9_]` in a label name, so every dot
becomes an underscore. The translation is mechanical and total, so a reader holding
`inferops.workload.id` can compute `inferops_workload_id` and the catalog stays the
one place the names are decided.

**An unstated identity is an empty label, not an invented one.** A
`service.version` of `unknown` sorts, groups, and reads like a release somebody
shipped. The empty string is what every store already treats as "not set".

**A metric with no samples still publishes its `HELP` and `TYPE`.** The error
counter above has no series because nothing failed, which is different from the
error counter not existing.

**The histogram has eleven finite buckets and `+Inf`.** The boundaries run 0.5s to
300s, chosen for the runtime
[ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md)
selected, whose measured floor on the trial host is tens of seconds on CPU. A
default bucket set topping out at ten seconds would put every real request in the
overflow bucket and report a latency distribution with one bar. Twelve bucket
series is the number the catalog's budget for this metric was computed from, and a
test compares the two.

## A record

Two records from the same request, as they are written — one object per line, here
wrapped for reading:

```json
{"timestamp":"2023-11-14T22:13:20.000Z","level":"info",
 "inferops.event":"request.received","service.name":"inferops-api",
 "service.version":"0.0.0","deployment.environment":"dev",
 "inferops.adapter.kind":"mock","inferops.workload.id":"support-assistant",
 "inferops.workload.version":"1.4.0","inferops.owner.id":"team-platform-demo",
 "inferops.correlation.id":"trace-me-42",
 "inferops.request.id":"09f893a5-dcaa-4a5b-a8c7-4f99f33b7395",
 "inferops.runtime.id":"inferops-mock-serving"}
```

```json
{"timestamp":"2023-11-14T22:13:20.000Z","level":"warn",
 "inferops.event":"request.refused","service.name":"inferops-api",
 "service.version":"0.0.0","deployment.environment":"dev",
 "inferops.adapter.kind":"mock","inferops.workload.id":"support-assistant",
 "inferops.workload.version":"1.4.0","inferops.owner.id":"team-platform-demo",
 "inferops.correlation.id":"trace-me-42",
 "inferops.request.id":"09f893a5-dcaa-4a5b-a8c7-4f99f33b7395",
 "inferops.model.id":"mock-fixed-fixture","inferops.runtime.id":"inferops-mock-serving",
 "inferops.outcome":"server-error","inferops.error.code":"model-not-ready",
 "http.response.status_code":503,"inferops.duration.ms":0.0}
```

**There is no message field.** A record is identified by `inferops.event` and
carries named fields. That is
[ADR 0006](../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md)
`D5`, and the reason is that prose which varies per request is where an exception's
string representation goes, where a runtime's error text goes, and where
`"failed for prompt: ..."` is one formatting change away.

**The refusal record carries a canonical code and never the adapter's words.** The
adapter above raised `ModelNotReadyError` with a message of its own; the record
carries `model-not-ready` and nothing the adapter said. That rule was already true
of the response body, and a log store is the same surface with a longer memory.

**The `request.received` record is written before anything can fail.** A request
that is refused before it reaches a handler is precisely the one nobody can find
afterwards, and it is the case the correlation identifier's assignment rule exists
for.

**An unstated field is omitted, not written empty.** Where a metric label has to be
the empty string, a record simply has no key.

### The seven events

| Event | Level | When |
|---|---|---|
| `deployment.started` | info | The adapter is initialized and the deployment has begun accepting work |
| `deployment.draining` | info | The deployment has stopped accepting work and has begun its drain |
| `deployment.stopped` | info | The drain finished and the adapter was released |
| `request.received` | info | An inference request was routed |
| `request.completed` | info | An inference request closed with a success |
| `request.refused` | warn | An inference request closed with a canonical refusal |
| `readiness.failed` | warn | A readiness check answered no |

The set is closed. `inferops.event` is a `bounded-small` attribute, and a test
compares this list against both the catalog data and the constants in the
distribution, so an event invented at a call site is a failing build rather than a
label set that quietly stopped being bounded.

## What a deployment states about itself

All of these are optional. A deployment that states none of them still starts,
still serves, and still emits — with its identity empty and visibly so, which is
more useful than a process that refuses to start because nobody set a release
identifier. Every stated value is validated as a label value at composition, so a
newline or a quote in one is refused by the process that read it rather than
injected into an exposition.

| Variable | Becomes | Notes |
|---|---|---|
| `INFEROPS_SERVICE_VERSION` | `service.version` | Identity. Reaches metrics only through `inferops_build_info` |
| `INFEROPS_DEPLOYMENT_ENVIRONMENT` | `deployment.environment` | One of `local`, `dev`, `staging`, `production`. Defaults to `dev` |
| `INFEROPS_CAPABILITY_ID` | `inferops.capability.id` | Identity |
| `INFEROPS_RELEASE_ID` | `inferops.release.id` | Identity |
| `INFEROPS_POD_NAME` | `k8s.pod.name` | A log field and never a label: a restarted pod is a new name |
| `INFEROPS_MODEL_REVISION` | `inferops.model.revision` | Identity. What the adapter reports wins over this |
| `INFEROPS_RUNTIME_IMAGE_DIGEST` | `inferops.runtime.image.digest` | Identity |
| `INFEROPS_WORKLOAD_ID` | `inferops.workload.id` | A metric label |
| `INFEROPS_WORKLOAD_VERSION` | `inferops.workload.version` | A log field, deliberately not a label |
| `INFEROPS_OWNER_ID` | `inferops.owner.id` | A log field, deliberately not a label |

Three of these carry a decision rather than a value.

**`deployment.environment` defaults to `dev` and is a closed set.** The failure it
prevents is a figure from a laptop being read as a figure from somewhere else, so
the conservative default is the one that never claims production, and a fifth
environment is a catalog change rather than a string.

**The adapter kind is not in the table, and that is the point.** It is derived from
`INFEROPS_SERVING_ADAPTER` — the variable that selects the adapter — and never
configured beside it. A second variable carrying this label would be a way to
compose a real adapter and publish `mock`, or the reverse, which is what
[the mock and real boundary](../serving/mock-and-real-boundary.md) rule 5 exists to
prevent.

**The workload identity is configuration and not a header.** The integration
specification lists `X-InferOps-Workload-ID` among the headers an integration
*should* propagate. This API does not read it, and the reason is arithmetic: the
catalog bounds `inferops.workload.id` at a deployment ceiling of twenty-five, and a
value read off a caller's request has no ceiling at all. One V1 deployment serves
one workload, so a value that is constant per process is bounded by construction.
The same specification says a security-sensitive value is validated or injected by
a trusted component rather than believed because a client sent a header, and this
is that rule applied to a metric label.

## What a mock deployment says about itself

Three places, because a scrape is the surface most likely to be copied into a
dashboard nobody labels afterwards:

1. the exposition opens with a comment naming the mock and saying it certifies no
   serving runtime;
2. `inferops_build_info` carries `inferops_adapter_kind="mock"`;
3. every operational series carries `inferops_runtime_id="inferops-mock-serving"`,
   the registered identifier the compatibility matrix already uses.

That is [the mock and real boundary](../serving/mock-and-real-boundary.md) rule 1 —
a label in the contents rather than in the directory name — applied to telemetry.

## What is not here

Read this section before quoting anything above.

**Nothing collects any of it.** No exporter, collector, store, dashboard, or alert
is selected. The endpoint answers when something scrapes it and nothing scrapes it;
records go to a stream and no store has held one. No retention window, shipper, or
access rule exists.

**No span exists.** `traceparent` and `tracestate` are neither read nor written,
and `trace.id` and `span.id` are specified fields nothing populates. The
correlation identifier and the request identifier are assigned at the edge and do
propagate — into the response headers, the response body's extension member, and
every record.

**Five active metrics are not emitted.** Four belong to the serving-runtime adapter
or the contract validator, neither of which is instrumented.
`inferops_process_resident_memory_bytes` is assigned to this API and still absent:
the only per-process memory source the standard library exposes is a file, a module
under `src/inferops` may not read a path, and the distribution declares no runtime
dependency that could supply another. The exposition names the absence rather than
publishing a zero.

**No figure derived from any of this may be published.** The latency, throughput,
and capacity signals exist to operate the platform.
[The project boundaries](../architecture/project-boundaries.md) forbid V1
publishing a performance figure, and a series existing is not a figure that may be
quoted. A dashboard screenshot is a publication.

**Every record inspected so far came from a mock.** The suites drive a deployment
serving the committed mock adapter, whose responses are a fixture. A real runtime's
error text is the input the pass-through rule exists for, and it has not been
through this code.
