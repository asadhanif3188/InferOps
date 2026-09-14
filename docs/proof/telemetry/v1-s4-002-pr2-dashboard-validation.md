# V1-S4-002-PR2 — the dashboard, asked of a real Prometheus and rendered by a real Grafana

Date captured: 2026-09-14

Classification: **local real evidence**, redacted. Evidence class `local-real-cpu`.
One InferOps release of the real profile was installed on `docker-desktop` with its
collector. Traffic, errors, an unavailable serving runtime, an API pod replacement,
and an API with no pod were produced on purpose. After each, every panel expression
in [the dashboard record](../../telemetry/inference-operations-dashboard.v1alpha1.json)
was asked of the release's own Prometheus. The generated Grafana JSON was imported
into a Grafana container and screenshotted in six of those states.

The machine-readable result is
[`v1-s4-002-pr2-panel-readings.v1alpha1.json`](v1-s4-002-pr2-panel-readings.v1alpha1.json):
nine states, 30 expressions in each, 270 readings.
[The operator guide](../../telemetry/inference-operations-dashboard-operator-guide.md)
is written from them.

## Claim boundary

Established, on `docker-desktop`, for one single-replica release, on one host, at
one time:

- a real Prometheus (3.5.0) parsed and evaluated **all 30** panel expressions in
  every state, and refused none;
- Grafana 11.6.0 imported the generated JSON through file provisioning and rendered
  all 29 panels against that Prometheus;
- zero and missing come apart on a real collector as the record says. With no API
  pod, the three since-start counts are empty and both absence panels read `1`.
  With an API publishing and nothing counted, they read `0`;
- a not-emitted panel read the same in every state, including while the serving
  runtime had no pod;
- request, error, and output token counts reconcile **exactly** with what the
  clients sent and received;
- every latency quantile the panel returned lies in the same histogram bucket as
  the client-observed quantile.

**Not established:** anything about `kind`, two replicas, another host, or another
Grafana version. Not Grafana's own schema validation. Not a latency, throughput, or
capacity figure: every number below is one observation of this release, and the
durations include a loopback port-forward. Not any alert, because none exists.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `7dda44fad4eff8f85bf71b232956055fde6b755b` (the merge of V1-S4-002-PR1) |
| Chart | `inferops-llm-0.3.0`, release revision 1 |
| API image | `localhost/inferops-api@sha256:783685ad116d8c9dfeeb68771af2f70473123276cf8f6b296fe12bd552ecbc63`, built at that revision on this host, published to no registry |
| Serving runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Collector image | `prom/prometheus@sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996`, version `3.5.0` |
| Model | `Qwen/Qwen3-1.7B-GGUF` revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, delivered by the committed seed-image path |
| Grafana | `grafana/grafana@sha256:62d2b9d20a19714ebfe48d1bb405086081bc602aa053e28cf6d73c7537640dfb`, version `11.6.0` |
| Screenshot browser | Google Chrome `152.0.7977.83`, headless, 1600 by 2950 pixels |
| Kubernetes | Docker Desktop's cluster, server `v1.34.3`, one node; `kubectl` `v1.34.3` |
| Helm | `v3.19.0+g3d8990f` |
| Container engine | Docker Desktop, server `29.7.2`, 12 processors, 10 432 536 576 bytes |
| Python, in the locked environment | `3.12.12` |

Replicas: one API, one serving runtime. The screenshots were rendered from the
Grafana JSON at the revision above. This change regenerates that JSON, and the
regenerated file differs from it **only in description text**, which a screenshot
does not show: no query, title, missing text, unit, or layout changed. That was
checked by comparing both files with every `description` removed.

## Method

From Git Bash at the repository root, `INFEROPS_PROVIDER=docker-desktop`, target
verified by `inferops::resolve_target` before every cluster command:

```text
scripts/environment/api-image.sh build
scripts/environment/api-image.sh load
scripts/environment/api-image.sh values > .artifacts/api-image-values.yaml
scripts/environment/terraform-prerequisites.sh apply             2 added
helm install inferops charts/inferops-llm --namespace inferops-release \
  -f charts/inferops-llm/ci/real-values.yaml \
  -f .artifacts/api-image-values.yaml -f .artifacts/model-seed-values.yaml
kubectl rollout status deployment/{runtime,api,collector}         all ready
kubectl port-forward svc/inferops-inferops-llm-collector 19090:9090
kubectl port-forward svc/inferops-inferops-llm 18091:8090
python -m tools.inference_dashboard --capture http://127.0.0.1:19090   once per state
```

The API image was rebuilt because `src/` and the chart had changed since the image
the Sprint 3 run used. The model seed image and runtime image already resolved
inside the node and were not re-imported.

Grafana ran as a container on the local engine, outside the cluster, owned by
nothing in this repository. It was bound to loopback, had anonymous viewer access,
reported no analytics, and was provisioned with one Prometheus data source and the
committed dashboard. It was removed at the end.

Every capture after `idle` waited for a condition read from Prometheus, never for a
fixed time. Examples: the in-flight gauge above zero, an absence series reading `1`, or one
identity series left. Every request went through the API's own Service. No prompt
or completion text was retained. Clients recorded status, canonical error code,
token usage, and duration only.

### The states, in order

| State | Captured (UTC) | What was done |
|---|---|---|
| `idle` | 10:22:41 | Every workload ready. No inference request. One request to a path the API does not serve, which the API did not count |
| `traffic-in-flight` | 10:25:18 | Three refused requests (see below), 30 sequential successful requests, then 200 successful requests from four concurrent clients, captured mid-burst |
| `traffic` | 10:27:21 | The burst finished and was scraped and recorded |
| `error` | 10:28:24 | 20 requests naming a model this release is not configured with |
| `serving-runtime-scaled-to-zero` | 10:30:23 | The runtime Deployment scaled to 0, then 10 valid requests |
| `serving-runtime-restored` | 10:31:52 | Scaled back to 1 (ready 16 s after scaling), then 10 valid requests |
| `api-pod-replaced-transition` | 10:32:39 | The API pod deleted by name. Captured once the replacement published an identity |
| `api-pod-replaced-settled` | 10:32:56 | Captured once only the replacement's identity was returned |
| `api-scaled-to-zero` | 10:34:55 | The API Deployment scaled to 0 |

**Three requests were refused before any traffic was sent.** They were sent while
confirming the request shape, and all three carried `max_tokens`, a member outside
the request subset the API accepts. They are counted in every figure below and not
subtracted from any of them.

Scaling and deleting objects the release owns changed nothing in the release's
values. Both Deployments were at their rendered replica counts, or uninstalled,
before this record was written.

## What the readings showed

Of 270 readings, 152 were a value, 81 empty, 37 zero, and none NaN or refused.

### Counts reconcile exactly

| Check | Clients | Dashboard |
|---|---:|---:|
| Requests finished, at `traffic` | 3 refused + 30 + 200 = 233 | `requests-since-start` `233` |
| Errors, at `error` | 3 + 20 = 23 | `errors-since-start` `23` |
| Share not successful, at `error` | 23 / 253 = 0.0909 | `unsuccessful-request-ratio` `0.0909` |
| Errors, at `serving-runtime-scaled-to-zero` | 23 + 10 = 33, the ten `503 capability-unavailable` | `errors-since-start` `33` |
| In flight, during the burst | four concurrent clients | `api-in-flight-by-replica` `4` |
| Output tokens, quiesced after `traffic` | 690 in responses | API counter `690`, runtime counter `690` |
| Input tokens, quiesced after `traffic` | 4140 in responses | API counter `4140`; runtime counter `247` plus `3893` served from its prompt cache |

The token rows were read from the counters directly once the recorded series had
caught up, not from a panel. The panels show rates.

### Percentiles fall in the right bucket, and interpolate coarsely

At the `traffic` capture, every request since start was inside the five-minute
window. Bucketing the 233 client-side durations by the catalog's boundaries gives
`32` at or under 0.5 s and `34` at or under 1 s. The collector's bucket counters read
`33` and `35`, and all 233 fell at or under 2.5 s in both. The one-request difference
is within the loopback forward's overhead, which the client measures and the API
does not, plus one refused request that was not timed.

| Quantile | Client-observed | Panel | Bucket both fall in |
|---|---:|---:|---|
| P50 | 1.347 s | 1.618 s | 1 s – 2.5 s |
| P95 | 1.543 s | 2.412 s | 1 s – 2.5 s |
| P99 | 1.684 s | 2.482 s | 1 s – 2.5 s |

`histogram_quantile` is correct for the selected metric. The metric's resolution is
its bucket. **A panel reading of 2.41 s says "between 1 and 2.5 seconds"**, and the
guide says so.

### What the real run showed that fixtures did not

1. **A rate misses every event before a series' first scrape, not only the first
   one.** In `serving-runtime-scaled-to-zero`, ten `capability-unavailable` failures
   happened before the error series was first scraped. The series appeared at `10`,
   and `errors-by-code` and the `server-error` outcome of `request-rate-by-outcome`
   read `0` while `errors-since-start` rose from 23 to 33. The record said a series
   "first appears already at 1". That was a lower bound, and every rate panel's
   description now says so.
2. **A rate outlives the process it counts.** In `api-scaled-to-zero`, with no API
   pod, `request-rate-by-outcome` still read a success rate of `0.0476` per second,
   and both token panels still read values. The since-start counts were empty.
3. **Latency quantiles include refused requests, and they are fast.** In
   `serving-runtime-scaled-to-zero`, while every valid request failed, P50 read
   `0.25` s against `1.62` s under traffic. An outage reads as an improvement.
4. **The runtime's input tokens are not the API's.** llama-server does not count
   prompt tokens it serves from its prompt cache. Output tokens matched exactly.
5. **A since-start count sums a replaced process until its series go stale.** In
   `api-pod-replaced-transition`, `api-processes-publishing-identity` read `2` with
   one replica configured, and `requests-since-start` still read `273`. Seventeen
   seconds later the counts read `0`: errors went 33 → 0 and failed readiness checks
   20 → 0.
6. **A tier with no pod disappears from `scrape-targets-answering-by-tier`**, rather
   than reading `0`. `scrape-jobs-that-discovered-no-pod` is what says so, and it did,
   for each tier in turn.
7. **The runtime panels trail the API by a scrape and a rule evaluation.** During the
   burst the API read four in flight while `runtime-processing-and-deferred` read `0`.
   The raw `llamacpp:requests_processing` and `llamacpp:requests_deferred` read `1`
   and `3`, and the recorded series had not yet been evaluated.
8. **Readiness refusals during startup are real and invisible to the rate.** At
   `idle`, `readiness-checks-failed-since-start` read `3` from the minutes the runtime
   spent loading, while `readiness-refusals-by-component` read `0`.
9. **`model-readiness` read its recorded absence in all nine states**, including
   with no serving runtime. `api-identity-not-published` read `1` only in
   `api-scaled-to-zero`, where there was no API pod at all.

### What the real Grafana showed

The six screenshots are in [`v1-s4-002-pr2-screenshots/`](v1-s4-002-pr2-screenshots/).

- All 29 panels rendered. The data-source variable resolved to the provisioned
  collector, and every panel carried its title, legend, and unit.
- The four not-emitted and four not-answerable panels were distinguishable from
  every number in every screenshot.
- **Defect, not fixed here: a long missing text is unreadable.** Grafana's stat
  panel shrinks its no-value text to fit. At this viewport, a missing text longer
  than about one line is drawn too small to read, for example
  `requests-since-start`, `errors-since-start`,
  `readiness-checks-failed-since-start`, and `unsuccessful-request-ratio` in
  [06-api-scaled-to-zero.png](v1-s4-002-pr2-screenshots/06-api-scaled-to-zero.png).
  So are the not-emitted texts of `queue-wait-p95`, `model-load-duration-p95`, and
  `api-process-memory` in every screenshot. The panels still draw no number, and
  their titles still name their state or what they count, so zero and missing stay
  distinguishable. The explanation does not survive rendering. The fix is to the
  record's texts or the renderer, and it needs a new rendering to verify. It is
  reported as a follow-up and recorded as a limitation of the record.
- The two identity tables truncate their columns at a third of the width.

## What changed in the repository because of this run

- [The dashboard record](../../telemetry/inference-operations-dashboard.v1alpha1.json).
  - `verificationStatus` now says the record was imported into a Grafana and
    evaluated by a Prometheus, with evidence class `local-real-cpu`, and
    `realRunEvidenceRef` names this record.
  - Two limitations were rewritten: `never-imported` became
    `imported-into-one-grafana`, and `new-expressions-evaluated-by-fixtures-only`
    became `new-expressions-evaluated-on-one-provider`.
  - Two limitations were added: `a-since-start-count-includes-a-replaced-process` and
    `runtime-input-tokens-exclude-the-prompt-cache`.
  - Nine panel descriptions and the `zero` state were corrected for findings 1, 3,
    4, 6, and 7. No query, title, missing text, or unit changed.
- [The Grafana JSON](../../../deploy/grafana/inferops-inference-operations.json) was
  regenerated from the record.
- `python -m tools.inference_dashboard --capture URL` was added. It is the only mode
  of that command that contacts anything, and it asks only the URL it is given.
- [The operator guide](../../telemetry/inference-operations-dashboard-operator-guide.md)
  was added, with a suite that holds it, this record, and the readings to the
  dashboard record.

No product behaviour changed. The API, the chart, the recording rules, and the
catalog are untouched. The runtime token mapping in finding 4 and the recording lag
in finding 7 belong to the chart's recording rules. They are reported, not changed.

## Checks run on the change

Every command below ran from the repository root in Git Bash, inside the locked
environment (`uv run --locked`), after the cluster work above and with no cluster
reachable to any of them.

```text
python -m pytest tests/telemetry/test_inference_dashboard_validation.py -q
38 passed

python -m pytest tests/telemetry/test_inference_dashboard.py tests/telemetry/test_inference_dashboard_validation.py -q
106 passed

python -m pytest tests/telemetry tests/testing tests/architecture -q
4915 passed, 3 skipped

python -m pytest -q
8658 passed, 30 skipped, 14 deselected

ruff format --check .                                  380 files already formatted
ruff check .                                           All checks passed!
python -m mypy                                         Success: no issues found in 209 source files
python -m tools.inference_dashboard                    ok  29 panel(s) satisfy the dashboard policy
python -m tools.telemetry_correlation                  ok  23 quer(ies) satisfy the correlation query policy
python -m tools.telemetry_collection charts/inferops-llm/ci/rendered   ok  2 file(s)
git diff --check                                       (no output)
```

The V1-S4-002-PR1 record's full lane skipped 31. This one skipped 30: the
collector's `promtool` check in `tests/architecture/test_telemetry_collector.py` ran
and passed on this host, where the collector image is now present locally.

## What was not run, and why

| Not run | Why |
|---|---|
| `kind` | Not the V1 reference provider, and ADR 0011 forbids borrowing this answer for it |
| Two replicas per tier | The multi-replica profile was refused at capacity on this host in V1-S3-011-PR1, and nothing here changes that |
| A model that is loaded but unready | Nothing emits model readiness. An unready model is V1-S4-007's experiment |
| An idle latency window after traffic (NaN) | Every capture after the first request had a request inside its five-minute window, so no NaN was observed. The record's statement that an idle window draws gaps is unverified here |
| Every target down while pods exist | Scaling to zero removes targets rather than making them fail a scrape. The fixture `every-target-down` remains the only evidence for a tier reading a present `0` |
| Grafana's schema validation, other Grafana versions | No validator is a dependency of this repository |
| Alerts | Out of scope. No alert exists and alert routing is undecided |

## Acceptance criteria

| Criterion | Status |
|---|---|
| Dashboard answers the V1 operational questions | **Met, with the guide.** Each question has panels that read on a real collector. The guide says for every panel what it answers and what it cannot support |
| Model, runtime, workload, and environment are visible | **Met** for the API tier (build identity) and the runtime tier (operating identity), both observed. Provider is **not answerable** from telemetry, shown so, and recorded here |
| P50, P95, P99, and throughput are correct for the selected metrics | **Met at bucket resolution.** Quantiles fall in the client-observed bucket and interpolate coarsely inside it. Request counts and output tokens reconcile exactly. Refused requests are inside the quantiles, and runtime input tokens exclude the prompt cache. Both are stated on the panels |
| Zero, missing, not emitted, and not answerable are distinguishable | **Met on a real collector and a real Grafana**, with the unreadable-text defect above. The states stay distinguishable, but the missing text's explanation does not render legibly |
| Scrape `up` is not presented as workload or model health | **Met.** The API tier's scrape panel read 100% in `api-pod-replaced-transition`, a moment when its identity count read two processes for one replica, and it reads nothing about readiness in any state. The guide names that conclusion as unsafe |
| No sensitive or high-cardinality content is shown | **Met.** No prompt or completion was retained or shown. The pod name appears only in the five per-replica panels, and the suite checks every committed reading against the catalog's barred labels |
| Screenshots, operator guide, validation against a running release | **Met** on `docker-desktop` |
| Alerts | **Not in scope** |

## Limitations

- One provider, one host, one single-replica release, one Grafana version, and one
  run of about twelve minutes. Nothing here is repeatable to the second: the
  captures waited on conditions, but scrape and evaluation phase decide exactly what
  a rate reads.
- The client durations include a loopback port-forward. The percentile comparison
  is at bucket resolution for that reason, not only because of the histogram.
- Three requests were refused before traffic began and stay in every count.
- The screenshots were rendered at one viewport. The unreadable-text defect depends
  on panel size.

## Authorisation

Required: **yes**. The run installed a release into a cluster the host owner owns,
loaded a real model, sent real inference requests, scaled and deleted release-owned
workloads, and pulled a Grafana image.

Granted by: the host owner, in the session that ran it, for `docker-desktop` with
Grafana screenshots. The cluster was not created, reset, or reconfigured, and no
workload of another project was touched. `helm uninstall` removed every object with
the release's instance label, and a repeated check found none left. The Grafana
container and both port-forwards were removed. The Terraform-owned namespace and
model cache claim remain, as after every earlier run.

Sensitive values removed before committing: host name, user account, absolute
filesystem paths, the kubeconfig and its path, and the API server address. Pod
names, the namespace, and image digests inside the cluster are reproduced as
emitted.
