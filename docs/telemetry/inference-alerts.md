# The V1 alerts, and the conditions nobody may be woken for

Status: **defined as code, checked, driven across fixtures, and replayed over two
real failure captures.** Six alerts are a committed record, every expression is held
to the correlation query policy under each profile it declares, and each one is driven
instant by instant across eight scenarios. Three of the six are then replayed over the
telemetry two failure experiments recorded on a real cluster; **one of them fires over
one capture, and nothing fires over the other.** Two Prometheus rule files are
generated from the record and compared against it byte for byte.

**Nothing routes any of this.** No receiver, no routing tree, no Alertmanager, no
on-call rotation. [ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
`D7` leaves alert routing with `telemetry-backend`, deferred, and this record does not
lift it. No Prometheus in any cluster has loaded these rules, no alert here has fired
anywhere but in this repository's own evaluator, and no alert has told anybody
anything. An alert file is a file.

The authoritative form is
[`inference-alerts.v1alpha1.json`](inference-alerts.v1alpha1.json). The rule files are
[`deploy/prometheus/inferops-inference-alerts.real.yaml`](../../deploy/prometheus/inferops-inference-alerts.real.yaml)
and
[`deploy/prometheus/inferops-inference-alerts.mock.yaml`](../../deploy/prometheus/inferops-inference-alerts.mock.yaml),
and [`tests/telemetry/test_inference_alerts.py`](../../tests/telemetry/test_inference_alerts.py)
regenerates both from the record and fails if a byte differs.

## The failure this is built against

It is not "we did not think of a condition". It is the alert set everybody has met:
thirty rules, written because thirty metrics existed, of which four ever fire, two of
those fire nightly for a reason nobody remembers, and the one that would have caught
the outage was silent because the metric it read is emitted by nothing.

So this record starts from the other end. **An alert exists only when there is
something to do about it**, and every one of the six carries the five things that make
that true:

| Field | Why it is required |
|---|---|
| `owner` | The role that acts. An alert nobody owns is a notification |
| `severity` | What acting means: now, or inside a working day |
| `condition` and `forSeconds` | What has been true, and for how long |
| `userImpact` | What a caller is experiencing while it fires |
| `evidenceQuery` | The query that shows *what* is wrong, once the alert has said *that* something is |
| `operatorAction` and `runbookRef` | What to do, and the section that says how |

And two fields that are less usual and matter more: `thresholdBasis`, which says where
the number came from, and `whatItCannotSee`, which says what the alert will be quiet
for. An alert that never states its blind spot is an alert whose silence gets read as
health.

**The evidence query is an accepted correlation query repeated verbatim**, named by
its `evidenceQueryRef` and refused if a byte differs. An operator following an alert
therefore lands on an expression [the query policy](telemetry-correlation-queries.md)
has already checked and the fixtures have already evaluated, rather than on one
somebody wrote into an annotation. It is never the condition restated: the condition
filters by a threshold and the evidence query does not, so the first says a component
is refusing and the second says which codes, which outcomes, or which tier.

| Alert | Evidence query |
|---|---|
| `InferOpsInferenceCallersRefused` | `error-rate-by-workload-and-code` — every code, including the `internal-error` this alert does not count |
| `InferOpsInferenceServingNothing` | `request-throughput-by-workload-model-and-outcome` — how much is arriving and how much is failing |
| `InferOpsReadinessRefusalsSustained` | `readiness-check-failures-by-component` — which half said no |
| `InferOpsInferenceLatencyPastHalfTheRequestBudget` | `request-latency-p95-by-workload-and-model` — the split the condition deliberately does not make |
| `InferOpsRuntimeDefersRequests` | `runtime-deferred-requests` — a count of requests, never a wait |
| `InferOpsPlatformApiScrapeJobAbsent` | `scrape-target-health-by-job` — which tier answers a scrape |

## The six alerts

| Alert | Severity | Fires when | Runbook |
|---|---|---|---|
| `InferOpsInferenceCallersRefused` | critical | The platform has been refusing completions with `capability-unavailable` for five minutes | [Service, network, and the policy that is not enforced](../environment/kubernetes-troubleshooting.md#service-network-and-the-policy-that-is-not-enforced) |
| `InferOpsInferenceServingNothing` | critical | Completions have been arriving for five minutes and none has succeeded | [reading the logs](../environment/kubernetes-troubleshooting.md#reading-the-apis-and-the-runtimes-logs) |
| `InferOpsReadinessRefusalsSustained` | critical | More than half a component's readiness probes have been refused for five minutes | [probes](../environment/kubernetes-troubleshooting.md#probes) |
| `InferOpsInferenceLatencyPastHalfTheRequestBudget` | warning | The 95th percentile of completion time has been past half the configured request timeout for ten minutes | [scheduling, resources, and out-of-memory](../environment/kubernetes-troubleshooting.md#scheduling-resources-and-out-of-memory) |
| `InferOpsRuntimeDefersRequests` | warning | The runtime has been holding requests it has no parallel slot for for ten minutes | [scheduling, resources, and out-of-memory](../environment/kubernetes-troubleshooting.md#scheduling-resources-and-out-of-memory) |
| `InferOpsPlatformApiScrapeJobAbsent` | warning | The collector's `platform-api` job has matched no target for ten minutes | [telemetry scrape](../environment/kubernetes-troubleshooting.md#telemetry-scrape) |

Five of them are about the workload. The sixth is about the collection and says so in
its own signal field, because it is the one that decides whether the other five mean
anything.

### Why the first three are not one alert

They fire together in an outage and they are not the same question.

`InferOpsReadinessRefusalsSustained` reads the API's own readiness answer, so **it
fires on a release nobody is sending traffic to**. In the recorded unready-model run
the readiness counter was already climbing two minutes before the first caller was
refused. It is the only one of the three that sees an outage before a user does.

`InferOpsInferenceCallersRefused` reads one canonical error code. It is the code both
recorded failure experiments produced and it is **not** the only one either produced:
the pod-loss run counted forty `capability-unavailable` and one `internal-error`, and
this alert would not have counted that one. What it says is that the serving
capability could not be reached at all, which is a different first step from any other
failure — and the one code it does not cover is what the next alert is for.

`InferOpsInferenceServingNothing` names no code. It is the backstop for a cause nobody
predicted: traffic is arriving and none of it is succeeding, whatever the reason. Its
threshold is zero rather than a share, for the reason in the next section.

## Where every number comes from

Every threshold is one of three things, and **none of them is a figure this project
measured.**

| Basis | Used by | The number |
|---|---|---|
| `zero-is-the-boundary` | callers refused, serving nothing, scrape job absent | Zero. Any occurrence at all is the condition, so there is nothing to tune |
| `declared-chart-configuration` | readiness refusals, runtime defers | Derived from a value the chart declares. It moves when that value moves |
| `declared-histogram-boundary` | latency | One of the request-duration histogram's own bucket boundaries |

The two derived ones, in full:

**Readiness, `> 0.05`.** The kubelet asks `/health/ready` every
`api.probes.readiness.periodSeconds`, which the chart defaults to `10`, and removes
the endpoint after `failureThreshold: 3` consecutive refusals. Every probe failing is
therefore 0.1 refusals a second, and 0.05 is half of that: more probes are being
refused than answered. An installation that changes the period changes the threshold
with it.

**Latency, `> 60`.** 60 seconds is half the chart's default
`api.requestTimeoutMs` of `120000`, and it is also one of the histogram's declared
bucket boundaries, so the quantile is interpolated *across* a boundary rather than
inside one. A request there has spent half the budget the adapter would abandon it at.

That second one is where a local threshold would have been easiest to publish as a
universal one. The slowest **client-measured** 95th percentile in the local
performance matrix was **8 614 ms**, on one host, on one day. (The phase-end panel
readings in the same record run higher — up to 9 526 ms — because a panel's window
spans a phase boundary; the findings record says the raw sets are the source for a
level's own distribution, which is why the client-measured figure is the one quoted.)
Turning either into an alert threshold would have made one machine's figure into
everybody's service-level objective, and both are named here only to say what the
threshold is not.

**And every window is at least as long as the range window its expression reads.** A
single scrape interval's worth of refusals keeps a five-minute rate above zero for
five minutes, so an alert with a shorter `for` pages for one event that has already
stopped. Every rate alert here failed that in an earlier draft; the
`one-scrape-of-trouble` scenario is what caught it and what stops it coming back.

## What is not alerted on, and why

Five deferred conditions. None of them is work that was skipped — each names a signal
that does not exist, and says what would have to.

| `deferredId` | Why |
|---|---|
| `container-restart-spike` | `kube_pod_container_status_restarts_total` is kube-state-metrics's. No chart here installs it, no ADR owns it, and the release's collector scrapes two InferOps jobs and nothing else. **Both failure experiments queried that metric against the real collector and both got an empty result** |
| `abnormal-model-load-duration` | `inferops_model_load_duration_seconds` is specified in the catalog and emitted by nothing. It belongs to the serving-runtime adapter, which is not instrumented |
| `model-not-ready` | `inferops_model_ready` is specified and emitted by nothing. The chart does render `inferops:model_ready_absent:platform_api`, and that series reads `1` in **every** release today — the unready-model run recorded it at 1 in the broken state and the corrected one alike. An alert on it would fire on every installation for ever |
| `error-share-above-a-budget` | No error budget or service-level objective is decided anywhere in this project, so any share between zero and everything would be chosen rather than derived |
| `api-process-resource-exhaustion` | `inferops_process_resident_memory_bytes` has no source this distribution may read. The catalog records why |

Each deferral also carries a `doNotApproximate` field, which is the one that does the
work: it names the nearby signal somebody would reach for and says why it would be a
different measurement wearing the missing one's name.

### The negative catalogue

Eight alerts that are *not* here, each with the rule that refuses it. They are not
hypothetical: the suite splices each one into a copy of the record and fails if the
policy accepts it.

| `refusedId` | Refused by |
|---|---|
| `up-as-inference-down` | `scrape-signal-presented-as-workload-health` |
| `model-ready-absence-as-model-health` | `alert-has-no-operator-action` |
| `in-flight-above-a-number` | `alert-threshold-has-no-declared-source` |
| `processor-time-rising` | `alert-has-no-operator-action` |
| `token-throughput-dropped` | `alert-threshold-has-no-declared-source` |
| `queue-duration-rising` | `alert-expression-refused-by-the-correlation-policy` |
| `scrape-job-named-in-the-expression` | `alert-names-a-job` |
| `refusals-without-a-window` | `alert-window-is-shorter-than-two-evaluations` |

## Scrape reachability is not workload health

`up` says a collector reached a process. It has been observed wrong in **both**
directions, in this repository, on real runs:

- [the recovery run](../proof/telemetry/v1-s3-011-pr2-telemetry-during-recovery.md)
  recorded a deleted serving pod still reading `1` for roughly fifty seconds;
- [the unready-model run](../proof/serving/v1-s4-007-pr1-unready-model-recovery.md)
  recorded a runtime whose process was alive and answering its own port reading `0`
  for the whole time its model was loading, because a loading `llama-server` answers
  its metrics endpoint with 503.

So one alert may read that signal, it is owned by whoever owns the collection, its
severity is a warning, and the policy refuses it if its name, condition, or user
impact describes the workload. The checker's word list is a list and has a list's
limit; the suite pins one synonym it still accepts, so the gap stays a committed fact
rather than an assumption that it was closed.

## The thirteen rules that refuse an alert

Every alert is first held to
[the correlation query policy](telemetry-correlation-queries.md) — the same parser,
the same catalog derivation, the same refusals — so an alert cannot be where a series
nothing emits, or a label the catalog bars, gets read. On top of that:

| Rule | What it refuses |
|---|---|
| `alert-condition-is-not-a-comparison` | An expression whose top level is not a comparison. A bare selector fires on a sample existing |
| `alert-expression-refused-by-the-correlation-policy` | Anything the query policy refuses, naming the rule |
| `alert-threshold-has-no-declared-source` | A `thresholdBasis` outside the record's closed list, and `measurement` always |
| `scrape-signal-presented-as-workload-health` | A scrape signal read as serving, or a scrape alert that describes itself as one |
| `alert-names-a-job` | A matcher on `job`. Job names are release-qualified, so such an alert is silent in every installation but one |
| `alert-has-no-operator-action` | A missing owner, severity, condition, impact, action, or runbook |
| `alert-runbook-does-not-resolve` | A runbook whose file is not committed, or whose fragment is not a heading in it |
| `alert-is-not-validated` | An alert with no scenario that fires it or none that keeps it silent |
| `alert-window-is-shorter-than-two-evaluations` | A `for` a single missed evaluation could satisfy |
| `alert-window-is-shorter-than-its-range-window` | A `for` shorter than the range window the expression reads |
| `alert-identifier-is-malformed-or-repeated` | An identifier that is not kebab-case, a name outside the `InferOps` + CamelCase convention, or either one twice |
| `alert-evidence-query-drifted-from-the-accepted-query` | A missing evidence query, or one that names an accepted correlation query and is not that query verbatim |
| `alert-record-is-malformed` | A record whose `alerts` is not a non-empty list of objects. A gate that answers with a traceback reads as a gate that passed |

Each of the thirteen is driven over a record corrupted to break it, and a rule with no
corruption behind it fails the suite.

## The eight scenarios

Each is a committed fixture: a synthetic store on a 60-second grid, evaluated instant
by instant so that `for` is a property the fixture establishes rather than a field
somebody wrote.

| Scenario | What it shows |
|---|---|
| `healthy-real-serving` | A release serving, with a non-zero fault rate on purpose. Nothing fires |
| `serving-pod-lost` | The shape [V1-S4-006-PR1](../proof/serving/v1-s4-006-pr1-inference-pod-recovery.md) recorded. Three alerts fire |
| `model-never-becomes-ready` | The shape [V1-S4-007-PR1](../proof/serving/v1-s4-007-pr1-unready-model-recovery.md) recorded. Two fire, and the third is silent for a reason worth knowing |
| `inference-slower-than-the-request-budget` | Everything served, slowly. Only the latency alert fires |
| `runtime-defers-requests` | Everything served promptly, and the runtime queueing. Only the saturation alert fires |
| `platform-api-not-discovered` | The API job matched no pod. Every workload alert is silent and the collection alert fires |
| `one-scrape-of-trouble` | One minute of refusals and failed probes. Nothing fires |
| `healthy-mock-serving` | A mock release serving. Nothing fires, and it certifies no provider |

**The fixtures are not the experiments.** They reproduce the *shape* of two recorded
runs and none of their durations: the pod-loss run's caller-visible outage was 31 960
ms and its fixture holds one for sixteen minutes, because a window shorter than a rate
window cannot exercise a `for`. No interval in any fixture is a recovery time, an
availability figure, or a service-level objective.

### The two results worth reading twice

**A release that has never served cannot fire `InferOpsInferenceServingNothing`.** The
success counter series does not exist until the first success, so a rate over it is
*empty* rather than zero, and `== 0` over an empty vector returns nothing. The unready
-model run recorded exactly that: its success series first appeared after the
correction. The condition is covered by the other two alerts, and the gap is written
into the alert's own `whatItCannotSee` rather than discovered during an incident.

**When the API is not discovered, every workload alert goes quiet.** Every one of the
five reads a series the API emits, so a job that matched no pod silences all of them
at once — not because the platform is well, but because nothing is being asked. That
is the whole reason the sixth alert exists, and the `platform-api-not-discovered`
fixture is what makes it a property rather than a claim.

## What they did over two real failures

The fixtures say what an alert does over telemetry somebody wrote. This says what
each one would have done over telemetry **a real Prometheus returned, on a real
cluster, while a real failure was happening** — which is the question the acceptance
criterion asks and the one a fixture cannot answer.

Both failure experiments committed the answers to a handful of range queries. Those
are query *results*, not the store they came from, so the replay in
[`tools/inference_alerts/replay.py`](../../tools/inference_alerts/replay.py) declares
its reconstruction — `sum(metric)` and `sum by (…) (metric)` are read back as the
metric, a bare selector as itself, and **anything else is refused and named**. Both
captures contain an expression it refuses (`a / b`), and one contains a second
(`count by (…)`).

| Alert | V1-S4-006-PR1, the pod lost under load | V1-S4-007-PR1, the model that never loaded |
|---|---|---|
| `InferOpsInferenceCallersRefused` | silent | silent, by one evaluation |
| `InferOpsInferenceServingNothing` | silent | silent |
| `InferOpsReadinessRefusalsSustained` | silent | **fires** |
| `InferOpsInferenceLatencyPastHalfTheRequestBudget` | not in the capture | not in the capture |
| `InferOpsRuntimeDefersRequests` | not in the capture | not in the capture |
| `InferOpsPlatformApiScrapeJobAbsent` | not in the capture | not in the capture |

**Not in the capture is not silence.** Three alerts read series neither experiment
asked for. Reporting those as quiet would have claimed they were quiet during a real
failure, which nothing here supports.

### Nothing fires for the pod that was lost, and that is the design

The caller-visible outage was 31 960 ms. Every window here is five or ten minutes,
and the Deployment controller had restored service before any of them could be
satisfied. An alert set that paged for that would be paging for something Kubernetes
fixed by itself — which is what most of the rules in this record exist to prevent.
The cost is stated as a gap: a short, repeated disruption is invisible here.

The caller-refusal alert is silent for a **second** reason, and it is the one worth
knowing. Its `capability-unavailable` series appears in that capture already reading
`40` and never increments again. The API creates a labelled counter series on its
first event, so the whole outage — forty refusals inside 32 seconds — is a series
*born at its value*, and a rate over it reads no increase at any instant. The
dashboard record documents the same property for panels; every rate alert here
inherits it, and nothing in this record closes it.

### One alert fires, and it is the readiness one

During the unready-model run the adapter refused every probe for the whole window:
the counter moved `2` → `41` across 435 seconds, a five-minute rate of up to
`0.129/s` against a threshold of `0.05/s`, and the condition held for 28 consecutive
evaluations against a window needing 21. That is the threshold derived from
`api.probes.readiness.periodSeconds` doing exactly what it was derived to do, against
a measurement rather than a fixture.

The caller-refusal alert missed the same run **by one evaluation** — 20 consecutive
against 21 — because the recording stopped one 15-second step early. Nothing there
says the condition ended, and publishing it as a plain silence would have hidden
which of the two stopped.

## Running the checks

```sh
python -m pytest tests/telemetry/test_inference_alerts.py -q
python -m tools.inference_alerts
python -m tools.inference_alerts --evaluate
python -m tools.inference_alerts --rules real
python -m tools.inference_alerts --replay
```

The first is the authoritative check and runs in the default lane. The second applies
the same policy to the committed record and is usable as a gate. The third drives
every alert across every scenario and prints what fires. The fourth prints the rule
file the committed one is compared against. The fifth replays every alert it can over
the two committed experiment captures.

All four read files in this repository. None contacts a cluster, starts a Prometheus,
loads a rule file, or knows what a receiver is.

[`tests/architecture/test_inference_alert_rules.py`](../../tests/architecture/test_inference_alert_rules.py)
carries a control that would run the pinned collector's own `promtool check rules`
over both committed files, where that image is available locally. **It has not run.**
On the host this change was made and validated the Docker engine was not running and
the image was not present, so both parametrisations skipped, loudly. Nothing here
establishes that a Prometheus accepts these files; what is established is that this
repository's own subset parser accepts every expression and that each file is a rule
group with the fields the format requires.

## What this does not establish

- That any Prometheus has ever evaluated these rules in a cluster. No alerting rule
  existed during either experiment, so the replay is this repository's own evaluator
  over a reconstruction it declares, not a rule a collector ran.
- That any alert has ever fired outside this repository's own evaluator.
- That the three alerts reported as `not-in-the-capture` would have been silent during
  either failure. Neither experiment asked for the series they read.
- That anybody would be told if one did. There is no receiver and no rotation.
- That the thresholds are right for an installation that is not this one. They are
  derived from this chart's declared defaults, and an installation that changed those
  has changed them.
- Anything about a store holding two releases at once. No expression filters by
  release, exactly as the dashboard record says of its panels.
- That a collector which is itself gone would be noticed. `absent()` is evaluated by
  the collector, so a collector that is not running evaluates nothing — including the
  alert about collection — and nothing here closes that.
