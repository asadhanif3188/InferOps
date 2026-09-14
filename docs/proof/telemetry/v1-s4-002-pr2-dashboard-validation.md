# V1-S4-002-PR2 — the dashboard, asked of a real Prometheus and rendered by a real Grafana

Date captured: 2026-09-14

Classification: **local real evidence**, redacted. Evidence class `local-real-cpu`.
One InferOps release of the real profile was installed on `docker-desktop` with its
collector. Traffic, errors, an unavailable serving runtime, an API pod replacement,
and an API with no pod were produced on purpose. After each, every panel expression
in [the dashboard record](../../telemetry/inference-operations-dashboard.v1alpha1.json)
was asked of the release's own Prometheus. The generated Grafana JSON was imported
into a Grafana container and screenshotted shortly after six of those captures.

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
- at the `traffic` capture, each of the three latency quantiles lies in the same
  histogram bucket as the client-observed quantile. No other state was compared.

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
| `serving-runtime-restored` | 10:31:52 | Scaled back to 1, then 10 valid requests. `kubectl rollout status` returned 16 s after the scale command, by the operator's shell timestamps, which are not committed |
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
| Output tokens, read directly after `traffic` | 690 in responses | API counter `690`; `llamacpp:tokens_predicted_total` `690` |
| Input tokens, read directly after `traffic` | 4140 in responses | API counter `4140`; `llamacpp:prompt_tokens_total` `247` and `llamacpp:prompt_tokens_cached_total` `3893` |

The first five rows are committed panel readings. The two token rows are not: they
are instant queries of the raw counters, sent by hand at 10:26:59 once the recorded
runtime series had caught up, and committed as `directReads` in the readings record.
`3893` was read from llama-server's own cached-prompt counter, not derived; that it
equals 4140 - 247 corroborates the explanation. Every request sent the same 18-token
prompt, which is close to the most reuse a prompt cache can get, so how far the
runtime's input falls below the API's here is a property of this traffic. The
committed `traffic` rates agree on the ratio: runtime input over output is 0.358,
as 247 over 690 is.

### Percentiles fall in the right bucket, and interpolate coarsely

At the `traffic` capture, every request since start was inside the five-minute
window. Clients logged 230 durations, the successful ones: `29` at or under 0.5 s,
`31` at or under 1 s, all 230 at or under 2.5 s. The three refused probes were not
logged; two were printed at about 0.09 s and 0.07 s and one was sent by hand and not
timed, so if all three fell under 0.5 s the client counts are `32` and `34`. The
collector's since-start bucket counters, read by a direct query at the capture's
instant and committed as `directReads`, were `33` and `35`, with all 233 at or under
2.5 s. The client figures are committed per traffic entry as `clientSecondsAtOrUnder`;
individual durations are not. Client durations include a loopback port-forward the
API does not see.

| Quantile | Client-observed, 230 logged, nearest rank | Panel | Bucket both fall in |
|---|---:|---:|---|
| P50 | 1.350 s | 1.618 s | 1 s – 2.5 s |
| P95 | 1.543 s | 2.412 s | 1 s – 2.5 s |
| P99 | 1.684 s | 2.482 s | 1 s – 2.5 s |

`histogram_quantile` is correct for the selected metric. The metric's resolution is
its bucket. **A panel reading of 2.41 s says "between 1 and 2.5 seconds"**, and the
guide says so.

### What the real run showed

Findings 2 and 8 were already stated in the V1-S4-002-PR1 record as reasoning; this
run confirms them on a real collector. The others were not stated before.

1. **A rate misses every event before a series' first scrape, not only the first
   one.** In `serving-runtime-scaled-to-zero`, ten `capability-unavailable` failures
   happened before the error series was first scraped. The series appeared at `10`,
   and `errors-by-code` and the `server-error` outcome of `request-rate-by-outcome`
   read `0` while `errors-since-start` rose from 23 to 33. A rate needs two samples
   in its window and assumes no zero when a series is created, so a series scraped
   at `10` and again at `10` reads `0`. For the first scrape interval after a series
   appears, the panel has no row for it at all. The record said a series "first
   appears already at 1". That was a lower bound, and the five rate panels over
   labelled API counters now say so.
2. **A rate outlives the process it counts** (confirmed; stated in PR1). In `api-scaled-to-zero`, with no API
   pod, `request-rate-by-outcome` still read a success rate of `0.0476` per second,
   and both token panels still read values. The since-start counts were empty.
3. **Latency quantiles include refused requests, and they are fast.** In
   `serving-runtime-scaled-to-zero`, `successful-requests-per-second` read `0`: the
   burst had left the five-minute window, and the only requests in it were the 20
   wrong-model refusals and the 10 `503`s. P50, P95 and P99 read `0.25`, `0.475` and
   `0.495` s, a linear fill of the 0 - 0.5 s bucket, against `1.62`, `2.41` and
   `2.48` s under traffic. Refusals pull the quantiles down whatever caused them;
   this run does not show that the outage itself did, since the 20 client errors
   alone would have read the same.
4. **The runtime's input tokens are not the API's.** llama-server's
   `prompt_tokens_total` counts prompt tokens it evaluated, not those it served from
   its prompt cache. Output tokens matched exactly. How large the gap is depends on
   prompt reuse, and this run reused one prompt.
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
8. **The readiness rate read `0` beside three counted refusals** (confirmed; stated
   in PR1). At `idle`, `readiness-checks-failed-since-start` read `3` from while the
   runtime was loading, and `readiness-refusals-by-component` read `0`. When those
   refusals happened was not recorded, so this run cannot say whether the rate missed
   them as first events or whether they were already older than its window. The same
   rate did read `0.037` in `serving-runtime-scaled-to-zero`, over a series that
   already existed.
9. **`model-readiness` read its recorded absence in all nine states**, including
   with no serving runtime. `api-identity-not-published` read `1` only in
   `api-scaled-to-zero`, where there was no API pod at all.

### What the real Grafana showed

The six screenshots are in [`v1-s4-002-pr2-screenshots/`](v1-s4-002-pr2-screenshots/).

- All 29 panels rendered. The data-source variable resolved to the provisioned
  collector, every panel carried its title, and every timeseries panel its legend
  and unit.
- **Each screenshot was taken shortly after its capture, not at the same instant.**
  A figure on a screenshot can differ from the committed reading: the
  `serving-runtime-scaled-to-zero` screenshot shows 17 failed readiness checks where
  the reading is 13.
- The four not-emitted and four not-answerable panels were distinguishable from
  every number in every screenshot.
- **Defect, not fixed here: a long missing text is unreadable.** Grafana's stat
  panel shrinks its no-value text to fit. At this viewport, a missing text longer
  than about one line is drawn too small to read, for example
  `requests-since-start`, `readiness-checks-failed-since-start`, and
  `unsuccessful-request-ratio` in
  [06-api-scaled-to-zero.png](v1-s4-002-pr2-screenshots/06-api-scaled-to-zero.png).
  So are the not-emitted texts of `queue-wait-p95`, `model-load-duration-p95`, and
  `api-process-memory` in every screenshot. The panels still draw no number, and
  their titles still name their state or what they count, so zero and missing stay
  distinguishable. The explanation does not survive rendering. The fix is to the
  record's texts or the renderer, and it needs a new rendering to verify. It is
  reported as a follow-up and recorded as a limitation of the record.
- The two identity tables truncate their columns at a third of the width, and the
  `restarts-and-pod-phase` text panel is cut off mid-sentence in every screenshot.

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
  of that command that contacts anything: one POST per expression to the http or
  https URL it is given, with environment proxies ignored and redirects refused. It
  does not check that the URL is a loopback forward.
- [The operator guide](../../telemetry/inference-operations-dashboard-operator-guide.md)
  was added, with a suite that holds it, this record, and the readings to the
  dashboard record.

- **Left stale, on purpose:** risk `R5` in
  [ADR 0004](../../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
  still says a dashboard definition exists "and nothing has imported it". This run
  makes that false. It is an accepted ADR, so the wording is left for a governed
  amendment rather than edited here.

No product behaviour changed. The API, the chart, the recording rules, and the
catalog are untouched. The runtime token mapping in finding 4 and the recording lag
in finding 7 belong to the chart's recording rules. They are reported, not changed.

## Independent review, and what it changed

The first commit was reviewed before push by three independent reviewers: one for the
capture tool's code, one for every number and claim against the readings, the raw
captures and the screenshots, and one for Prometheus and Grafana semantics, scope, and
leakage. Each finding below was checked before it was acted on.

**What the first commit got wrong in this record.**

- **The bucket comparison rested on figures nobody could check.** It said 233 client
  durations bucketed to `32` and `34`. Clients logged 230; those bucket to `29` and
  `31`, and `32` and `34` came from adding two printed but unlogged probe durations and
  one guess. The collector's `33` and `35` were read by hand and committed nowhere. The
  client P50 was published as `1.347` s, which includes the guessed values; the 230
  logged durations give `1.350` s. All of it is now committed or labelled.
- **The token figures were uncommitted.** `4140`, `690`, `247` and `3893` were direct
  counter reads that appeared in no committed file, and a reviewer reasonably read
  `3893` as 4140 - 247. It was read from `llamacpp:prompt_tokens_cached_total`; it is
  now committed with its read time and method, with the note that the run reused one
  prompt.
- **"An outage reads as an improvement" was not shown.** When the quantiles dropped,
  the only requests in the window were refusals, 20 of them client errors the outage
  did not cause. The finding now says refusals pull the quantiles down, not that the
  outage did.
- **"Every latency quantile" was one state.** Only `traffic` was compared.
- **"Every rate panel's description"** was five of them.
- **Two findings were presented as new** that PR1 had already reasoned: a rate
  outliving an outage, and a readiness rate reading `0` beside counted refusals.
- **The startup refusals were said to be invisible to the rate.** Their times were
  not recorded; they may simply have been older than the window.
- **Screenshot timing was not disclosed**, and one screenshot shows 17 failed checks
  against a reading of 13.
- **`errors-since-start` was listed as unreadable** in one screenshot where it can be
  read; the truncated `restarts-and-pod-phase` text panel was not mentioned.
- **"Ready 16 s after scaling"** had no source a reader could see; it now names one.

**What the first commit got wrong elsewhere.**

- **The capture tool crashed instead of refusing.** A proxy's HTML error page or an
  unreachable collector raised a raw exception, and `--capture ""` silently ran the
  policy check instead. The tool also followed redirects and honoured environment
  proxies while its docstring said it contacted only the URL given. A failure to reach
  Prometheus now stops the capture with a named refusal and exit 1, never a reading;
  only http and https are accepted; proxies are ignored and redirects refused. Eight
  tests drive those paths against a local stub.
- **The operator guide told an operator that a tier with no pod "says nothing about
  the tier's health."** A tier with no pod cannot serve; what it cannot say is why.
- **The rate panels' shared sentence** said a burst of refusals had been observed
  reading `0` on panels, including the token and readiness rates, where that was not
  what was observed. Each now names where it was.
- **"The since-start counts disappear at once"** is true of a target that fails a
  scrape and false of a deleted pod, which this run showed lingering.
- **The repository README** still said the dashboard definition "has never been
  imported"; the first commit's search used other wording and missed it.
- **The first commit's message** credited all nine description changes to the
  first-scrape finding; five were. The message stays as written, and this is the
  correction.

**Not changed.** The PR1 validation record still says a counter series is born at 1;
it is a dated record, and a note now points from it to this one. ADR 0004 `R5` is
left as above.

## Checks run on the change

Every command below ran from the repository root in Git Bash, inside the locked
environment (`uv run --locked`), after the review fixes above and with no cluster
reachable to any of them. The first commit's own runs recorded 38, 106, 4915 and
8658; the twelve added since are the review's failure-path and binding tests.

```text
python -m pytest tests/telemetry/test_inference_dashboard_validation.py -q
48 passed

python -m pytest tests/telemetry/test_inference_dashboard.py tests/telemetry/test_inference_dashboard_validation.py -q
116 passed

python -m pytest tests/telemetry tests/testing tests/architecture -q
4927 passed, 3 skipped

python -m pytest -q
8670 passed, 30 skipped, 14 deselected

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
| P50, P95, P99, and throughput are correct for the selected metrics | **Met at bucket resolution, in one state.** At the `traffic` capture the quantiles fall in the client-observed bucket and interpolate coarsely inside it. Request counts and output tokens reconcile exactly. Refused requests are inside the quantiles, and runtime input tokens exclude the prompt cache. Both are stated on the panels |
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
