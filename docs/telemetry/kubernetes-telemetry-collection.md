# Collecting telemetry in Kubernetes

Status: **configuration rendered, nothing collected.** The `inferops-llm` chart now
renders the `telemetry-scrape-configuration` row of
[the ownership inventory](../architecture/resource-ownership.md) as a ConfigMap
holding a Prometheus scrape configuration and a set of recording rules. No
collector, store, dashboard, or alerting path is selected — that is an open question
in [ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
that [ADR 0006](../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md)
D8 deliberately does not answer, and this document does not answer it either.
**Nothing reads this ConfigMap, nothing scrapes either endpoint, and this chart has
never been installed.**

The authoritative form is
[`kubernetes-telemetry-collection.v1alpha1.json`](kubernetes-telemetry-collection.v1alpha1.json).
This document and that file are compared in both directions by
[`tests/telemetry/test_kubernetes_telemetry_collection.py`](../../tests/telemetry/test_kubernetes_telemetry_collection.py),
which also reads the committed chart renders and
[the telemetry catalog](telemetry-catalog.v1alpha1.json), so a job, a label, or a
rule cannot appear in one of the four without appearing in the others.

## What this document decides

**Which pods a collector finds, and how it fails to find them.** Discovery selects
on the three Kubernetes labels this chart sets on every pod it installs, not on the
`prometheus.io/*` annotations — those are optional and off by default, so a
configuration keyed on them would select nothing in the default installation.

**Which labels the collector attaches, and which it deliberately does not.** The
rule is short: the collector never attaches a label the emitter already publishes.

**What a label costs.** One collector-attached label here is unbounded, it is
`instance`, and the reason it cannot be avoided is stated rather than glossed.

**Which native runtime series mean something in InferOps terms**, and which of the
signals the catalog specifies have no source at all.

## 1. Two jobs

| Job | Profiles | Emitter | Port | Path |
|---|---|---|---|---|
| `inferops-platform-api` | `mock`, `real` | the InferOps API | `api.containerPort` | `telemetry.metricsPath` |
| `inferops-serving-runtime` | `real` | `llama-server` | `runtime.containerPort` | `telemetry.collection.runtimeMetricsPath` |

Both use `kubernetes_sd_configs` with `role: pod`, scoped to the release namespace
by name rather than by `own_namespace` — the collector is not expected to run in the
release's namespace, and `own_namespace` would silently mean the collector's own.

Three details in the selection are load-bearing:

- **The release instance is in the selector.** A job matching `part-of: inferops`
  alone would scrape a second release installed beside this one and attribute its
  series here.
- **The port is kept explicitly.** Pod discovery yields one target per declared
  container port, so a pod with two ports produces two targets and the second
  answers nothing on the metrics path. That is a permanently failing target that
  reads like a broken endpoint.
- **Unready pods are not filtered out.** A pod that never becomes ready is exactly
  the one worth scraping: it is up, it answers, and it is serving nothing. Filtering
  on readiness would make that pod disappear from the collection at the moment it
  became interesting.

## 2. The collector never attaches a label the emitter publishes

`honor_labels` is `false`, stated in the configuration rather than left to the
default, because it is the whole reason for the rule. With `honor_labels: false` a
target label wins a collision and Prometheus renames the emitter's to
`exported_<name>` — so a target label duplicating one the API already sets does not
add information, it renames a label every existing query uses.

| Job | Attached | Deliberately not attached |
|---|---|---|
| `inferops-platform-api` | `k8s_namespace`, `k8s_component`, `instance` | workload, model, environment, and every identity attribute |
| `inferops-serving-runtime` | `k8s_namespace`, `k8s_component`, `instance`, `deployment_environment`, `inferops_workload_id`, `inferops_model_id`, `inferops_runtime_id` | every identity attribute |

Prometheus sets `job` itself, from `job_name`, and `instance` is discussed in
section 3. Neither is relabelled here, and both are declared in the record with the
same cardinality class every other label declares.

**The API job attaches Kubernetes context and nothing else**, because the API already
publishes the rest: the operational dimensions on its own series, and the immutable
identity — service version, capability, release, model revision, runtime image
digest, adapter kind — on `inferops_build_info`, which is one series per process.
Attaching those to every series is exactly what ADR 0006 D3 built the identity metric
to avoid, and doing it from the collector rather than from the emitter does not make
it a different decision.

**The runtime job is the opposite case.** `llama-server` publishes bare series with
no labels at all — [the feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md)
measured exactly that — so there is nothing to collide with, and the collector is the
only thing positioned to say which workload, model, runtime, and environment those
numbers belong to. It supplies the four the catalog permits as metric labels and
none of the identity ones, for the same reason as above. Runtime series join to the
release's identity through `k8s_namespace` and `inferops_runtime_id`, which
`inferops_build_info` also carries.

`inferops_runtime_id` is **derived from the profile** in the chart, not configured
beside it — the same rule the capability identifier and the adapter kind follow. A
value carrying this label would be a way to compose a mock adapter and publish the
real runtime's identifier, or the reverse.

### The `k8s_` prefix

`k8s_namespace` and `k8s_component` carry a prefix so that a label the collector
attached is never read as an attribute an emitter placed. `k8s_component` is the
workload tier — `platform-api` or `serving-runtime` — and it is a different thing
from `inferops.component`, which is the readiness component the API names when it
refuses traffic. Two labels that mean roughly the same thing get used
inconsistently within a month; two labels that mean different things and are spelled
the same get used wrongly on the first day.

## 3. `instance` is unbounded, and it is not an accident

Prometheus requires the targets of one job to differ in their label sets. With two
replicas that difference has to be the pod, so a per-target identity is not
optional — the only question is what it holds.

It holds the pod name. The default would be `<podIP>:<port>`, which is equally
unbounded, changes on every reschedule, and names nothing a person can look up.

**The cost, stated rather than discovered.** Every series from a job is multiplied by
the number of distinct pods inside the store's retention window: by the replica count
while nothing restarts, and by the pod churn once anything does. For the API job the
per-target ceiling is 3,125 series — the sum of `maxSeries` over the eight metrics
the catalog marks emitted — so two replicas is a ceiling of 6,250. That is arithmetic
over declared bounds multiplied by a replica count. It is not a measurement, and no
store has held one of these series.

**The alternative, and why it was refused.** Collapsing `instance` to a constant per
component removes the multiplier entirely. It also makes two replicas
indistinguishable, which is the one question
[the multi-replica certification](../serving/kubernetes-multi-replica-certification.md)
exists to answer, and it makes a single failing replica invisible behind five healthy
ones.

**The catalog's rule is untouched.** `k8s.pod.name` is still not a metric label, and
no InferOps process labels a series with its pod — the metric registry refuses one at
construction. That is an *emitter* rule about what a process puts on its own series.
`instance` is a target label the data model requires, and it is declared here with
its cost rather than smuggled in as an emitter attribute.

## 4. What is dropped on the way in

Every job carries one `labeldrop` in `metric_relabel_configs`. Its list is **derived
from the catalog**: every attribute whose declared placements include neither
`metric-label` nor `info-label`, written in the form a Prometheus exposition spells
it. A test recomputes the list and fails if the chart and the catalog disagree, so a
placement decision taken in the catalog reaches the collector without anybody
remembering to come here.

```text
http_response_status_code  inferops_correlation_id     inferops_cost_record_id
inferops_duration_ms       inferops_evaluation_decision inferops_event
inferops_field_path        inferops_finish_reason      inferops_owner_id
inferops_request_id        inferops_retry_count        inferops_tenant_id
inferops_workload_version  k8s_pod_name                level
service_name               span_id                     timestamp
trace_id
```

**Nothing in this repository emits any of them as a label.** The registry refuses one
at construction, and a test proves it. This is the second line, for a series that
arrives from a component this project did not write, or from one it writes later. A
correlation identifier, a tenant, a pod name, or a duration that reached a label is
dropped before it is stored, rather than after somebody reads the bill.

**There is no name in this list for a prompt, a completion, a provider error body, a
secret, or an authorization header**, and that is not an omission. Those fields have
empty placement lists in the catalog: there is no attribute for them, so there is no
label name a drop rule could match. The exclusion is the absence of a name, and
[the redaction rules](redaction.md) are where that is argued.

## 5. What the native runtime series map to

Three recording rules, from the mapping
[the catalog](telemetry-catalog.md) publishes in section 9 and
[the feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md)
measured.

| Recorded | From | InferOps concept | Complete? |
|---|---|---|---|
| `inferops:inference_tokens:runtime_total` | `llamacpp:prompt_tokens_total`, `llamacpp:tokens_predicted_total` | `inferops_inference_tokens_total` | yes |
| `inferops:inference_requests_in_flight:runtime` | `llamacpp:requests_processing` | `inferops_inference_requests_in_flight` | yes |
| `inferops:inference_requests_deferred:runtime` | `llamacpp:requests_deferred` | `inferops_inference_queue_duration_seconds` | **no** |

Every recorded name is `inferops:` with a **colon** — the Prometheus recording-rule
convention — and never `inferops_` with an underscore. A derived series can then
neither be confused with nor collide with one the API emits, which matters most for
the token counter, where a derived name spelled `inferops_inference_tokens_total`
would land on top of a metric the API already publishes.

The direction label on the token rule is added with `label_replace` rather than as a
target label, because it varies per series and a target label cannot.

**The deferred-request mapping is partial, and the gap is the point.**
`llamacpp:requests_deferred` shows that queueing happened and never how long any
request waited. The wait is the serving-runtime adapter's measurement, and the
adapter is not instrumented — so the rule is named so that it cannot be read as the
histogram it is not.

**Eleven native series map to nothing and are still collected**: the prompt cache
counter, prefill and decode times, decode steps, the largest context observed, two
derived rates, slot occupancy, and three speculative-decoding counters. They are
cheap, they are already on the endpoint, and dropping them would make a runtime
tuning question unanswerable to save a series count the budget does not need. What
they are not is an InferOps concept, and no recording rule pretends otherwise.

## 6. Making absence readable

`up == 0` catches a target that exists and fails. It catches nothing else, and the
two failures it misses are the ones that look like health.

| Recorded | Catches |
|---|---|
| `inferops:scrape_targets:count` | how many targets each job has |
| `inferops:scrape_targets_up:sum` | how many of them answered |
| `inferops:scrape_job_absent:platform_api` | a job whose discovery matched no pod |
| `inferops:scrape_job_absent:serving_runtime` | the same, for the runtime job |
| `inferops:build_info_absent:platform_api` | a target that is up and published no identity |
| `inferops:model_ready_absent:platform_api` | model readiness, which nothing emits |

**`sum` rather than a count of a filtered vector.** A job whose every target is down
must read zero. `count(up == 1)` over an all-down job reads *nothing*, and nothing
looks like a healthy quiet system.

**`absent()` rather than a threshold.** A job whose discovery matched no pod produces
no `up` series at all, so every query that groups by job returns an empty result. A
selector typo, a renamed label, and a namespace that was never installed all look
identical to a dashboard, and all three look like silence.

**`inferops:model_ready_absent:platform_api` reads 1 today**, and will until the
serving-runtime adapter is instrumented. `inferops_model_ready` is declared in the
catalog, assigned to the adapter, and marked not emitted. A rule that averaged a
metric nothing produces would have published an empty series, which reads as a
healthy system rather than an absent one — so this publishes the absence instead.

**No alerting rule is written.** An alert needs a receiver, a routing tree, and
somebody on the other end, and none of the three is decided. A recorded absence that
nobody is paged for is a query, not a control.

## 7. What has no source at all

| Signal | Why | What would provide it |
|---|---|---|
| `inferops_model_ready` | the serving-runtime adapter emits nothing | instrumenting the adapter |
| `inferops_inference_queue_duration_seconds` | same emitter, same absence | instrumenting the adapter |
| `inferops_model_load_duration_seconds` | same emitter; `llama-server` publishes no load duration either | instrumenting the adapter |
| `inferops_process_resident_memory_bytes` | the only per-process figure the standard library exposes is a file, and a module under `src/inferops` may not read one | a dependency this project does not declare |
| container, pod, and node CPU and memory use | the accepted local cluster runs no metrics-server, no kube-state-metrics, and no kubelet cAdvisor scrape | a cluster add-on this chart does not own |
| pod phase, restart count, container readiness | kube-state-metrics series, and no kube-state-metrics runs | kube-state-metrics |
| declared requests and limits as series | the same; the declared figures are in the chart's own resource blocks | kube-state-metrics |
| traces | no tracer, propagator, exporter, or SDK is selected | ADR 0006 D1's undecided implementation half |
| log collection | no log store, shipper, retention window, or access rule is selected | a decision this catalog requires before content of any kind is written |

The row worth reading twice is the resource one. **The Kubernetes context this
configuration attaches is identity — namespace, tier, pod — and never consumption.**
Nothing here can tell you what a pod used, and the one recorded measurement of a
pod's memory in this repository was read from its cgroup by hand.

## 8. The network path

A collector in another namespace is **denied** by the policy this release already
renders. The default-deny selects every pod this chart installs and denies ingress
from everything outside the release.

`telemetry.collection.collector` is the allowance: a namespace and a pod selector,
required together, rendering one ingress rule per workload policy. Naming neither is
the default and leaves the denial whole — there is no collector to name.

The namespace selector and the pod selector are **one `from` item**, which means "a
pod in that namespace with those labels". Written as two items they would mean "any
pod in that namespace, **or** any pod anywhere with those labels", which is the
mistake this object is most often written with, and which reads identically in a
`kubectl get networkpolicy -o yaml`.

**None of this is enforced where this project runs.** Whether a NetworkPolicy is
applied at all is the cluster network plugin's decision, and the accepted local
cluster's plugin was tested and does not enforce one — see
[the enforcement experiment](../proof/security/v1-s3-004-pr1-network-policy-enforcement.md),
`DR-04`, and `EX-05`. On a cluster that does not enforce policy the allowance changes
nothing, because nothing was denied. On one that does, it is the whole of the access
control on an endpoint that carries **no authentication at all**
([deferred risks](../security/deferred-risks.md), `DR-01`).

## 9. What this does not establish

- **Nothing collects.** No collector, store, dashboard, or alerting path is selected.
  This ConfigMap is read by nothing, and nothing scrapes either endpoint.
- **Nothing has been installed.** No InferOps API image is published, this chart has
  never been installed, and no Prometheus has ever loaded this configuration. Every
  job, label, and rule here has been rendered, parsed, and compared against committed
  records; none has been pointed at a running pod.
- **The multiplier is arithmetic.** Series ceilings are declared bounds multiplied by
  a replica count, not a measurement of a store.
- **The runtime mapping was measured once**, on one host, on one day, from one image
  digest. A different build of `llama-server` may expose a different set, and nothing
  here would notice.
- **A recorded absence is not an alert.** The rules in section 6 record values that
  nothing evaluates and nobody is paged for.

## Running the checks

```sh
python -m pytest tests/telemetry -q
python -m pytest tests/architecture/test_helm_chart.py -q
python -m tools.telemetry_collection charts/inferops-llm/ci/rendered
```

The first two read only files in this repository. The third reads the committed
renders and refuses a scrape configuration that attaches a label the catalog bars,
maps a native series the feasibility record never observed, or records a name that
would collide with a metric the API emits.
