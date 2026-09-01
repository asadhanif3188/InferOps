# V1-S1-008-PR1 change validation

Date: 2026-08-31

Classification: **local static evidence for the change itself, plus `mock` evidence
for the signals it produced.** Every result below comes from reading files in this
repository and from running `pytest`, `ruff`, and `mypy` over them. The exposition
and the log records quoted here were produced by an application composed with the
**committed mock serving adapter**, driven through the ASGI interface it
implements. No cluster was created, no model was downloaded, no runtime was
started, no socket was opened, and no request left this process.

Claim boundary: the InferOps API emits the eight metrics the accepted telemetry
catalog assigns to the `inferops-api` emitter and writes the structured log records
that catalog specifies; every request to the inference endpoint is counted whether
it succeeded or failed; no request identifier, correlation identifier, workload
version, owner, or measured duration is a metric label; no prompt, completion, or
adapter message reaches a record or a series; a record carries the correlation
identifier the caller was given; and a mock deployment says so in three places in
its own telemetry.

**What this record does not establish.**

- **No claim changed status.** No row of
  [the claim and test matrix](../../testing/claim-test-matrix.md) moved, and no
  `evidenceRef` in [the strategy data](../../testing/test-strategy.v1alpha1.json)
  was edited. `no-prompt-response-or-secret-reaches-a-log-or-a-metric` stays
  `planned`: it requires the `security-scan` and `real-runtime-smoke` layers, and
  neither ran here. The two suites this change adds contribute to it and do not
  certify it.
- **Nothing collects any of it.** No exporter, collector, store, dashboard, or
  alert is selected. The endpoint answers when something scrapes it, and nothing
  in this repository scrapes it; log records go to the sink the composition point
  supplies, and no store has held one.
- **Every record and every series here came from a mock.** The mock replays a
  fixture. A real runtime's error text is the input the pass-through rule exists
  for, and it has not been through this code.
- **No figure here is a performance figure.** The latency histogram was exercised
  against a clock the suite controls and against a fixture replay. The one real
  measurement in the exposition below is a processor-time reading of the test
  process, which describes this process and nothing about serving.
- **Nothing crosses a socket.** This repository ships no ASGI server. The
  application was driven through its own interface.
- **`inferops_process_resident_memory_bytes` is not emitted.** It is assigned to
  this emitter and it has no source this distribution may read; the exposition
  names the absence rather than publishing a zero. This is recorded in the catalog
  and repeated here so a reader of the exposition is not left to notice it.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Python | `3.12.12` |
| `pytest` | `8.4.2` |
| `pytest-asyncio` | `0.24.0` |
| `jsonschema` | `4.26.0` |
| `PyYAML` | `6.0.3` |
| `ruff` | `0.16.4` |
| `mypy` | `2.3.1` |

No cluster, no runtime container, and no model artifact were involved.

## Commands and results

### The two suites this change adds

```text
python -m pytest tests/api/test_api_observability.py \
                 tests/telemetry/test_api_telemetry_agreement.py -q
155 passed
```

### The full default lane

```text
python -m pytest -q
5113 passed, 25 skipped, 14 deselected
```

On `main` at the base revision `aadf4c5` the same command reports `4875 passed, 25
skipped, 14 deselected`. Every one of the 238 added is accounted for, and only two
of the seven modules involved gained a check somebody wrote:

| Module | Before | After | Why |
|---|---|---|---|
| `tests/api/test_api_observability.py` | — | 36 | new |
| `tests/telemetry/test_api_telemetry_agreement.py` | — | 119 | new |
| `tests/telemetry/test_telemetry_catalog.py` | 408 | 457 | checks parametrised over every metric, and two metric fields added |
| `tests/testing/test_test_inventory.py` | 446 | 464 | checks parametrised over every inventoried module, and two modules added |
| `tests/architecture/test_domain_dependency_boundary.py` | 99 | 113 | checks parametrised over every module under `src/inferops`, and seven were added |
| `tests/api/test_api_health_models_and_metrics.py` | 32 | 33 | one endpoint check added, two rewritten |
| `tests/security/test_security_baseline.py` | 608 | 609 | a check parametrised over committed evidence records, and this record is one |

The last five grow without a check being written by hand, which is the property
those suites exist for: adding a module, a metric, or an evidence record does not
let it escape the checks that already apply to its kind.

### The lane and marker grouping

```text
python -m pytest -m unit -q             398 passed, 18 skipped, 4736 deselected
python -m pytest -m contract -q         628 passed,  7 skipped, 4517 deselected
python -m pytest -m architecture -q     470 passed,             4682 deselected
python -m pytest -m adapter -q          578 passed,             4574 deselected
python -m pytest -m mockintegration -q  361 passed,             4791 deselected
python -m pytest -m docs -q            2678 passed,             2474 deselected
python -m pytest -m realruntime -q       14 skipped,            5138 deselected
```

The `realruntime` lane was **not** executed against a runtime. Its modules skip
when their runtime settings are unset, which is what the fourteen skips are.

### Formatting, linting, and typing

```text
python -m ruff check .          All checks passed!
python -m ruff format --check . 208 files already formatted
python -m mypy                  Success: no issues found in 117 source files
```

### Diff hygiene

```text
git diff --check                (no output)
```

The two accepted machine-readable records this change edits —
`docs/telemetry/telemetry-catalog.v1alpha1.json` and
`docs/serving/inference-api-surface.v1alpha1.json` — are hand-formatted, and
re-serializing them with a JSON library would have produced a 747-line and a
19-line diff of pure reformatting. Both were rewritten through a serializer that
reproduces the committed style exactly, verified by round-tripping each file
unchanged before any value was edited. The catalog diff is 142 insertions and 33
deletions; the surface diff is 4 and 4.

## The evidence this change produced

### A scrape

Produced by an application composed with the committed mock adapter, after one
successful completion, with the workload identity stated. It is the same
exposition published in
[the instrumentation document](../../telemetry/api-instrumentation.md), quoted
here in full so that the record does not depend on a document that may be edited.

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

The ten intermediate bucket lines between `le="0.5"` and `le="+Inf"` are elided
here and **only** here, because they are eleven identical lines differing in one
number; the instrumentation document carries them in full, and a test asserts
there are twelve bucket series and exactly one `+Inf`.

Four things the scrape establishes:

- the request counter `ADR 0002` `T7` records as missing from the runtime exists
  and reads 1 after one request, which is the compensating obligation discharged;
- the identity metric is **one** series carrying what the adapter reported, not
  one for the configured identity and a second for the resolved one;
- an identity nobody stated is an empty label rather than an invented value;
- the token counter has a `HELP` and a `TYPE` and no sample, because the mock
  reports no usage — absent rather than estimated.

### Two records

Produced by the same composition driven into `model-not-ready`. Each is one line;
they are wrapped here for reading.

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

The request that produced them carried the prompt
`canary-prompt-value-8f2a`, and the adapter raised its refusal with the message
`the model is still loading`. Neither string appears in either record, in any
other record the run wrote, or in the exposition. The timestamp is fixed because
the suites compose the application with a fixed clock; the duration is zero
because the monotonic clock the suite supplies does not advance.

## Negative validation

A suite that cannot fail proves nothing. Eleven properties were each broken on
purpose, the suite that should catch it was run, and the source was restored. The
counts are the ones a reader reproducing the corruption gets.

| # | Corruption | Result |
|---|---|---|
| 1 | A metric declaration names the correlation identifier as a label | `1 error` — the module fails to import, because the declaration is refused at construction |
| 2 | The record allowlist gains a field the catalog does not publish | `2 failed, 118 passed` in the agreement module |
| 3 | The latency histogram declares one more finite bucket than its budget allows | `1 failed, 118 passed` |
| 4 | A metric the catalog marks emitted is dropped from the declarations | `4 failed, 115 passed` |
| 5 | A catalog row claims a metric is emitted and nothing emits it | `3 failed, 118 passed` |
| 6 | The completed-request record carries the prompt | `24 failed, 12 passed` in the observability module |
| 7 | A refused request is not closed, so it is never counted | `5 failed, 31 passed` |
| 8 | The in-flight gauge is not decremented when a request closes | `1 failed, 35 passed` |
| 9 | The identity metric adds a series instead of replacing one | `1 failed, 35 passed` |
| 10 | The exposition stops naming the mock behind the deployment | `1 failed, 32 passed` in the endpoint module |
| 11 | The catalog says nothing emits while its own rows say otherwise | `1 failed, 456 passed` in the catalog module |

Two corruptions were attempted first in a form that **did not** fail, and both are
recorded because the reason is instructive rather than reassuring:

- returning early from inside the `try` of the instrumented request path does not
  skip the close, because a `finally` runs on the way out of a `return`. The
  corruption that does skip it is a guard inside the `finally` itself, which is
  number 7 above;
- inserting a second `"emission": "emitted"` earlier in a catalog metric object
  changes nothing, because a JSON parser takes the last of two duplicate keys. The
  corruption that works replaces the value in place, which is number 5.

A corruption that does not fail is not evidence of a gap until it is understood.
Both of these were the corruption being wrong rather than the suite being weak,
and both are stated so that a reader repeating this exercise does not conclude
otherwise.

## Findings

### One defect found by writing the evidence, not by a test

The identity metric emitted **two** series. `inferops_build_info` is resolved in
two steps — the identity a deployment configured at construction, then what the
adapter reported on startup — and the first implementation set both, producing one
series for an empty identity and a second for the resolved one. The catalog
declares `seriesModel: one-per-process`, and two contradictory identity series for
one process is worse than none.

It was found by scraping the endpoint to produce the sample above and reading the
output, which is the argument for producing a sample at all. The fix is structural
rather than a call-site rule: setting an identity metric replaces its series
rather than adding one beside it, in
[`inferops.telemetry.registry`](../../../src/inferops/telemetry/registry.py).
Corruption 9 is the demonstration.

### One metric assigned to this emitter and not emitted

`inferops_process_resident_memory_bytes` is the API's in the catalog and is not
emitted. The only per-process memory figure the standard library exposes is
`/proc/self/statm`, and
[`tests/architecture/test_domain_dependency_boundary.py`](../../../tests/architecture/test_domain_dependency_boundary.py)
refuses any module under `src/inferops` that reads a path, so that the
distribution stays usable from a wheel with no file system around it. Every other
source is a runtime dependency the distribution does not declare.

The first implementation read the file and was caught by that suite. The rule was
kept rather than amended: this is a metric worth having and it is not worth an
architecture exception, so the metric stays specified, the catalog records
`emission: not-emitted` with the reason, and the exposition names the absence in a
comment. A zero would have been the easy option and would have been a measurement
claiming this process holds no memory.

### Two attributes the catalog did not have

The catalog was written before the API existed, and instrumenting the API needed
two names it did not publish.

`inferops.request.id` — the API mints or validates a request identifier at the
edge and echoes it in `X-InferOps-Request-ID` and in every response body's
extension member, and the catalog had no attribute for it. A record that cannot be
joined to the response a caller is holding is the gap. It is added with the same
classes as the correlation identifier — request-scoped and unbounded — so it is a
log field and never a label.

`inferops.adapter.kind` — the acceptance criteria require the adapter type to be
available safely and mock telemetry to be labelled as mock. It is added as a
`bounded-small` resource attribute marked identity-only, so it appears on the
identity metric and on every record and multiplies no operational series.

Neither addition changes the cardinality budget: the request identifier is a log
field, and the adapter kind is a label on a metric whose series model is
one-per-process.

### The workload identity is configuration, and that is a decision

`inferops.workload.id` is the one caller-shaped metric label the catalog permits,
and this API does **not** read it from a header. The integration specification
lists `X-InferOps-Workload-ID` among the headers an integration should propagate;
it also says a security-sensitive value is validated or injected by a trusted
component rather than believed because a client sent it. A workload identifier
read off a request has no ceiling, and the catalog bounds this label at
twenty-five. One V1 deployment serves one workload, so reading it from
configuration makes the label bounded by construction rather than by hoping
callers behave. This is recorded as a limitation, `no-workload-identity-from-a-document`,
because the honest description is that nothing here deploys a workload and so
there is no validated document for the value to come from either.

### Three living documents carried statements this change made false

Each was corrected, and none is an ADR.

- [`CONTRIBUTING.md`](../../../CONTRIBUTING.md) said nothing in this repository
  emits a metric, a log record, or a span, and that no log line had ever been
  inspected.
- [`docs/security/deferred-risks.md`](../../security/deferred-risks.md) `DR-12`
  said no logger, formatter, or sink exists. It is **narrowed rather than closed**:
  a logger and a redacting sink now exist and real records are inspected; no store,
  retention window, or access rule does, so nothing is reconstructible and no
  auditability property is claimed.
- [`docs/serving/inference-api.md`](../../serving/inference-api.md) and
  [`docs/serving/inference-api-surface.md`](../../serving/inference-api-surface.md)
  said `/metrics` publishes no series.

### Statements left alone, and why

[ADR 0006](../../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md)
says in `D5` and in its security considerations that there is no logger, no
formatter, and no redacting sink, and that a test inspecting a real log line is
future work. All three are now false, and the record is **not edited**. An ADR is
a decision at a date, and this repository's convention is that a later record
supersedes one rather than rewriting it — `ADR 0009` supersedes two of `ADR 0001`'s
decisions in exactly that way. What changed here is the catalog's `emissionStatus`
and its limitations, which is where that record itself said the question would be
settled. `ADR 0006`'s `D7` and `D8` are untouched and still hold: content capture
is not decided and has no flag, and no SDK, exporter, collector, or store is
selected.

## Acceptance criteria

| Criterion | Status | Where |
|---|---|---|
| Request, success/error, latency, active request, and readiness metrics exist | met | `inferops_inference_requests_total`, `inferops_inference_errors_total`, `inferops_inference_request_duration_seconds`, `inferops_inference_requests_in_flight`, `inferops_readiness_check_failures_total`, all in the scrape above |
| Workload, version, environment, adapter type, and model/runtime identity are available safely | met | Workload and version on every record, workload as a label; environment, adapter kind, model, model revision, runtime, and image digest on `inferops_build_info`; version and owner are log fields and deliberately not labels |
| Request/trace IDs are not metric labels | met | Refused at declaration by the registry, and asserted against a real scrape: the identifiers the response carried appear nowhere in the exposition |
| Prompt/response content is not logged by default | met | The record allowlist has no name for either, there is no message field and no pass-through, and a real prompt and a real adapter message were checked against every record written |
| Mock telemetry is labelled as mock | met | A comment in the exposition, `inferops_adapter_kind="mock"` on the identity metric, and `inferops-mock-serving` on every operational series and record |

## Parent story

`V1-S1-008` is complete for the API and not for the adapter. Its outcome — emit the
minimum safe telemetry required to operate and correlate inference requests — is
met for the component that receives a request. The four metrics assigned to the
serving-runtime adapter (queue duration, model-load duration, model readiness) and
the one assigned to the contract validator (document rejections) are recorded as
`not-emitted` with a reason, and instrumenting the adapter is separate work.

The two open questions this story depended on are **not** answered. No telemetry
SDK, exporter, collector, or store is selected, and
[ADR 0004](../../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
still records that nobody owns a collector. Instrumenting the API was possible
without answering either, because a pull endpoint needs no exporter and a stream
needs no shipper — which is a way of building inside the constraint rather than a
way of lifting it. Anything that would require a collector, a store, a retention
window, or a dashboard is still blocked on the same two questions.
