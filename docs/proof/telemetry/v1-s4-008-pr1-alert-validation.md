# The V1 alert set, validated

Date: 2026-09-17

What this records: every alert in
[the committed alert record](../../telemetry/inference-alerts.v1alpha1.json) driven
across every committed scenario, instant by instant, with what fired, what stayed
silent, and what each result does and does not establish.

Classification: **local static.** Evidence class `local-static`, in two parts that
must not be read as one.

**The scenarios are synthetic.** Every number in the fixture matrix was produced by
this repository's own evaluator over stores written by hand. Two of the eight take
their *shape* from experiments this project ran on a real cluster and none of their
durations; a fixture interval is not a recovery time, an availability figure, an error
budget, or a service-level objective.

**The replay is over measurements.** The last section runs the alerts over the
telemetry [the pod-loss run](../serving/v1-s4-006-pr1-inference-pod-recovery.md) and
[the unready-model run](../serving/v1-s4-007-pr1-unready-model-recovery.md) actually
recorded, through a declared reconstruction. Those numbers were measured. What was
*not* measured is the alerting: no alerting rule existed during either experiment, no
Prometheus has ever loaded these rules, and no alert has been routed or delivered to
anybody — no receiver, routing tree, Alertmanager, or on-call rotation is selected.

## Environment

| Component | Version |
|---|---|
| Windows | 11 Enterprise 10.0.26200 |
| Python | 3.12.6 |
| `pytest` | 8.4.2 |
| `ruff` | as locked in `uv.lock` |

```text
uv run --locked python -m pytest tests/telemetry/test_inference_alerts.py -q
```

## The alert set

Six alerts, five deferred conditions, eight refusals in the negative catalogue.

| Alert | Severity | Owner | Threshold | Window |
|---|---|---|---|---|
| `InferOpsInferenceCallersRefused` | critical | serving | `> 0` on the `capability-unavailable` rate | 5m |
| `InferOpsInferenceServingNothing` | critical | serving | success rate `== 0` while total rate `> 0` | 5m |
| `InferOpsReadinessRefusalsSustained` | critical | serving | `> 0.05`, half the kubelet's readiness cadence | 5m |
| `InferOpsInferenceLatencyPastHalfTheRequestBudget` | warning | serving | `> 60`, half `api.requestTimeoutMs` and a bucket boundary | 10m |
| `InferOpsRuntimeDefersRequests` | warning | serving | `> 0`, because `runtime.parallelSlots` is 1 | 10m |
| `InferOpsPlatformApiScrapeJobAbsent` | warning | platform | `== 1` on the recorded absence | 10m |

**No threshold is a figure this project measured.** Three are zero, two are derived
from values the chart declares, and one is a declared histogram bucket boundary. The
slowest client-measured 95th percentile in the local performance matrix — 8 614 ms, on
one host — appears in the record only as a statement of what the latency threshold is
*not*. (The same record's phase-end panel readings reach 9 526 ms; its own findings
say the raw sets are the source for a level's distribution, which is why the
client-measured figure is the one quoted.)

The deferral threshold is the one to read twice. `runtime.parallelSlots` is 1, so any
deferral is demand past the configuration — and the measured matrix recorded deferrals
of **0, 1 and 3** at concurrency 1, 2 and 4, so the threshold alone was crossed in
four of its six measured phases. The ten-minute window, not the threshold, is what
keeps that alert quiet under a load the release handled.

## What fired, and where

Every cell is the fixture evaluator's answer, and the instant is the first at which
the alert would have been firing rather than pending.

| Alert | healthy-real-serving | serving-pod-lost | model-never-becomes-ready | inference-slower-than-the-request-budget | runtime-defers-requests | platform-api-not-discovered | one-scrape-of-trouble | healthy-mock-serving |
|---|---|---|---|---|---|---|---|---|
| `InferOpsInferenceCallersRefused` | silent | fires (960 s) | fires (600 s) | silent | silent | silent | silent | silent |
| `InferOpsInferenceServingNothing` | silent | fires (1200 s) | silent | silent | silent | silent | silent | silent |
| `InferOpsReadinessRefusalsSustained` | silent | fires (1080 s) | fires (600 s) | silent | silent | silent | silent | silent |
| `InferOpsInferenceLatencyPastHalfTheRequestBudget` | silent | silent | silent | fires (900 s) | silent | silent | silent | silent |
| `InferOpsRuntimeDefersRequests` | silent | silent | silent | silent | fires (960 s) | silent | silent | not rendered |
| `InferOpsPlatformApiScrapeJobAbsent` | silent | silent | silent | silent | silent | fires (900 s) | silent | silent |

Forty-seven of the forty-eight cells are the record's own declared expectation, and
the forty-eighth is `not rendered`: the deferral alert reads a recorded series the
chart renders only under the real profile, so it is absent from the mock rule file
rather than present and permanently silent.

## Four results from the scenarios

### A single scrape interval of trouble pages nobody

`one-scrape-of-trouble` carries six refusals and eighteen failed readiness probes
inside one minute, and nothing either side. **The condition is true** — a five-minute
rate reads that single step for five minutes — and the evaluator confirms it is true
at exactly five fixture instants, 900 s through 1140 s. Both alerts need six
consecutive, because their `for` is the range window.

An earlier draft of every rate alert used a two-minute window and fired here. The
rule `alert-window-is-shorter-than-its-range-window` and this scenario are what
remain of that draft. The suite also re-runs the availability alert with its window
shortened to 120 s and asserts that it *does* fire, so a fixture that stopped
exercising the window would fail rather than pass quietly.

### A release that has never served cannot fire `InferOpsInferenceServingNothing`

The success counter series does not exist until the first success. A rate over a
series that is not there is **empty**, not zero, and `== 0` over an empty vector
returns nothing.

This is not a hypothesis about Prometheus. The V1-S4-007-PR1 run's committed
telemetry shows `sum by (inferops_outcome) (inferops_inference_requests_total)`
returning a `success` series for the first time at 1789575525 — after the correction
— while the `server-error` series had been climbing since 1789575315. The scenario
reproduces it, the alert stays silent, and the gap is written into the alert's own
`whatItCannotSee` field rather than discovered during an incident. The condition is
covered by the other two availability alerts, both of which fire there.

### When the API is not discovered, every workload alert goes quiet

All five workload alerts read a series the platform API emits. A scrape job that
matched no pod silences all five at once — not because the platform is well, but
because nothing is being asked. `platform-api-not-discovered` is the only scenario in
which the collection alert fires, and it fires alone.

That is the whole argument for the sixth alert, and the suite holds it as a property:
every alert whose `signal` is `workload` must be silent in that scenario, and the one
whose signal is `scrape-reachability` must fire.

### Readiness sees the outage first

In `model-never-becomes-ready` the readiness alert and the availability alert both
fire at 600 s, the earliest instant either could. In the recorded run they did not
arrive together: the readiness counter was already at `2` at the capture's first
sample, `1789575195`, and first observed to increment at `1789575225`, while the first
caller error was counted at `1789575315` — 120 seconds later. The replay below shows
the consequence: over that capture the readiness alert fires and the caller-refusal
alert does not. The readiness alert is the only one of the six that fires on a release
nobody is sending traffic to, which is why it is not folded into the availability
alert.

## Replayed over what two real failures recorded

Same six alerts, over telemetry a real Prometheus returned on the `docker-desktop`
provider while a real failure was happening. The captures are query *results*, so the
replay declares its reconstruction: `sum(metric)` and `sum by (…) (metric)` are read
back as the metric, a bare selector as itself, and anything else is refused and named.
`v1-s4-006-pr1` refuses one expression (`inferops:scrape_targets_up:sum /
inferops:scrape_targets:count`); `v1-s4-007-pr1` refuses that and `count by
(k8s_component) (inferops_build_info)`.

```text
uv run --locked python -m tools.inference_alerts --replay
```

| Alert | `v1-s4-006-pr1` (1 220 s at 15 s) | `v1-s4-007-pr1` (462 s at 15 s) |
|---|---|---|
| `InferOpsInferenceCallersRefused` | silent, held 0 of 21 needed | silent, held **20** of 21 needed |
| `InferOpsInferenceServingNothing` | silent, held 0 | silent, held 1 |
| `InferOpsReadinessRefusalsSustained` | silent, held 0 | **fires**, held 28 |
| `InferOpsInferenceLatencyPastHalfTheRequestBudget` | not in the capture | not in the capture |
| `InferOpsRuntimeDefersRequests` | not in the capture | not in the capture |
| `InferOpsPlatformApiScrapeJobAbsent` | not in the capture | not in the capture |

**`not in the capture` is not silence.** Those three read series neither experiment
asked for. Reporting them as quiet would have claimed they were quiet during a real
failure, which nothing here supports.

### Nothing fires for the pod that was lost

The caller-visible outage was 31 960 ms against windows of five and ten minutes, and
the Deployment controller restored service with no human action. An alert set that
paged for that would be paging for something Kubernetes fixed by itself, which is what
most of the rules in this record exist to prevent. It is recorded as the gap
`a-disruption-shorter-than-the-window-is-not-alerted` rather than left implied.

The caller-refusal alert is silent for a second reason, and it is the finding of this
replay. Its `capability-unavailable` series appears in that capture at `1789549405`
**already reading 40**, and never increments again. The API creates a labelled counter
series on its first event, so the whole outage — forty refusals inside 32 seconds — is
a series *born at its value*, and a rate over it reads no increase at any instant. The
dashboard record documents the same property for panels. Every rate alert here
inherits it; the gap `a-counter-series-born-at-its-value-feeds-no-rate` says so, and
the alert's own `whatItCannotSee` carries it.

Readiness was silent there too, and correctly: the counter moved `2` → `4` across
1 185 seconds, a five-minute rate of at most `0.0067/s` against `0.05/s`.

### One alert fires, and the threshold that fired it was derived from the chart

During the unready-model run the adapter refused every probe for the whole window:
`2` → `41` across 435 seconds, a five-minute rate reaching `0.129/s` against a
threshold of `0.05/s` — which is half the kubelet's own cadence at
`api.probes.readiness.periodSeconds: 10`. The condition held for 28 consecutive
evaluations against a window needing 21.

The caller-refusal alert missed the same run **by one evaluation**: 20 consecutive
against 21, with the condition still true at the last sample. The recording stopped one
15-second step before the alert would have fired. Publishing that as a plain silence
would have hidden which of the two stopped, so the record carries the count.

`InferOpsInferenceServingNothing` was silent there for the reason predicted before the
replay was written: the release had never served, so no success counter series existed
until the correction, and a rate over a series that is not there is empty rather than
zero.

## What is deferred, and what was measured about it

| Condition | Why there is no alert | How the absence is known |
|---|---|---|
| Container restart spike | `kube_pod_container_status_restarts_total` is kube-state-metrics's; no chart here installs it and no ADR owns it | **Both failure experiments queried it against the real collector and both returned no series.** The absence is measured, not assumed |
| Abnormal model-load duration | `inferops_model_load_duration_seconds` is specified in the catalog and emitted by nothing | V1-S4-007-PR1 held a release for 179 755 ms with a model that had not finished loading -- it loaded once the release was corrected -- and no load-duration series existed to record any part of it |
| Model not ready | `inferops_model_ready` is specified and emitted by nothing | Both experiments queried it directly and both returned no series. The recorded absence rule `inferops:model_ready_absent:platform_api` read `1` for the whole of V1-S4-007-PR1 — in the broken state and in the corrected one alike — so an alert on it would fire for ever and mean nothing |
| Error share above a budget | No error budget or service-level objective is decided anywhere in this project | The measured performance matrix recorded 360 requests with 0 unsuccessful, so there is no observation of a partial failure rate either |
| API process resource exhaustion | `inferops_process_resident_memory_bytes` has no source this distribution may read | The telemetry catalog records why, and the endpoint names the absence rather than publishing a zero |

## What this does not establish

- That any Prometheus has evaluated these rules, in a cluster or during either
  experiment. No alerting rule existed when either was run. The replay is this
  repository's own evaluator over a reconstruction it declares.
- That the three alerts reported `not-in-the-capture` would have been silent during
  either failure.
- That any Prometheus has loaded these rules. The `promtool check rules` control
  in `tests/architecture/test_inference_alert_rules.py` establishes that the rendered
  files *load*, and it **did not run** for this record: the pinned collector image is
  not present on this host and the check skipped, loudly, as it is written to.
- That any alert has fired outside this repository's own evaluator.
- That anybody would be told if one did.
- That any threshold is right for an installation other than this chart's defaults.
- Anything about a store holding two releases at once.
- That a collector which is itself gone would be noticed. `absent()` is evaluated by
  the collector.

## Limitations

- The fixtures step at 60 seconds and a release would evaluate every 30. A `for`
  satisfied here is satisfied at the instants the fixture carries; a condition that
  flickered between two of them would be invisible.
- The evaluator is not Prometheus.
  [The correlation query document](../../telemetry/telemetry-correlation-queries.md)
  declares the differences, and they apply unchanged here because it is the same
  evaluator.
- The `capability-unavailable` selector is the code both recorded experiments
  produced, and not the only one either produced: the pod-loss run also counted one
  `internal-error`, which this alert would not have counted. A failure mode producing
  a different code reaches `InferOpsInferenceServingNothing` only once *nothing* is
  succeeding.
- Six of the eight scenarios are constructed. The saturation one constructs a
  *duration* rather than a value: the measured matrix reached a deferral of 3 and
  never held one for ten minutes.
