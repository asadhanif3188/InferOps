# The V1 operator runbook

Status: **published and machine-checked. The incident procedures have not been run
as drills.** This page is the one place an operator is sent from an alert, a failed
workflow, or a caller's complaint. Each procedure says how the incident is noticed,
what a caller is going through, what recovers without anybody, what a person has
to do, how to confirm it worked, and where the procedure stops being reliable.

What stands behind each part is labelled where it appears, using the evidence
labels the rest of this repository uses:

- **`local-real-cpu`**: an executed experiment on the `docker-desktop` provider,
  one Windows host, CPU only, one replica of each tier. Two incidents rest on one:
  [pod loss](#pod-loss) and [an unready model](#unready-model). The
  [bad release](#bad-release) procedure rests on the executed upgrade and rollback
  experiment.
- **`synthetic`**: the alert scenarios, whose every number was written by hand
  and evaluated by this repository's own evaluator, not by Prometheus.
- **`local-static`**: a command that reads committed files only. The offline
  checks on this page were executed for
  [this page's validation record](../proof/environment/v1-s5-005-pr1-validation.md).
- **described**: a procedure derived from the chart, the scripts, and the records,
  and never provoked. [Resource pressure](#resource-pressure-and-out-of-memory),
  [a telemetry gap](#telemetry-gap), [model and cache faults](#model-and-cache-faults),
  and [a cost anomaly](#cost-anomaly) are all at least partly described and not
  observed, and each says which part.

**Every result behind this page is docker-desktop's.** Nothing here has been run on
`kind`, on Linux or macOS, on more than one node, or with more than one replica,
and [ADR 0011](../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md)
forbids reading any of it as another provider's result.

**No installed release evaluates the alerts, and nothing pages anybody.** The six
alerts in [the alert record](../telemetry/inference-alerts.md) are rendered into
rule files under `deploy/prometheus/` for a Prometheus an installation provides.
The release's own collector loads the recording rules and not those files, and no
receiver, routing tree, or on-call rotation exists. Until an installation adds
them, "an alert fires" on this page means its condition holds. An operator can ask
the collector for the expression by hand; nothing asks it for them.

The machine-readable form of every incident, alert route, figure, and drill on this
page is [`operator-runbook.v1alpha1.json`](operator-runbook.v1alpha1.json).

## How to use this page

1. **Arriving from an alert:** go to [its section](#when-an-alert-fires). Each one
   starts with a read-only command and then names the incident to open.
2. **Arriving from a symptom:** find it in
   [the incident table](#automatic-and-human-recovery-at-a-glance), then open the
   procedure.
3. **Arriving from a failed workflow:** read its exit code first
   ([the vocabulary](kubernetes-troubleshooting.md#exit-codes)), then the
   workflow's own diagnostics under `.artifacts/`, then
   [the troubleshooting guide](kubernetes-troubleshooting.md), which is organised by
   what you observed.

This page tells you what to do. [The troubleshooting guide](kubernetes-troubleshooting.md)
explains how to read a symptom. Where the two overlap, this page links to the guide
rather than repeating it.

## Before anything else

These are the troubleshooting guide's
[rules](kubernetes-troubleshooting.md#before-anything-else) applied to the operator's
own cluster.

1. **Run everything from the repository root, in Git Bash.** Every path is
   repository-relative. On Windows, `bash` launched from PowerShell is usually the
   WSL launcher rather than Git Bash, and the scripts are not written for it.
2. **Never let `kubectl` or `helm` pick a context.** Every command on this page names
   `--kubeconfig .kube/inferops-target.config` and a context. That file is written
   by `inferops::resolve_target` in
   [`scripts/environment/lib.sh`](../../scripts/environment/lib.sh) every time a
   workflow verifies the target. It holds exactly one context, the one just
   verified, and the operator's own kubeconfig is never used for acting.
3. **Diagnose before you change anything.** Every fenced block on this page opens
   with a label. `# read-only` changes nothing in the cluster or the release,
   though it may write a local file under `.artifacts/` or `.cache/`. `# mutating`
   changes the release or the node's images and can be reversed. `# destructive` removes something, and each one is a
   separate decision.
4. **Never paste a prompt, a completion, a runtime response body, or a request log
   line into an issue.** [The redaction rules](../telemetry/redaction.md) apply to
   an incident report too. Object states, reasons, exit codes, revisions, counts, and
   durations are enough for everything below.
5. **Do not restart to find out what is wrong.** A restart removes the container
   whose log you needed and resets every since-start count on the dashboard.

### The target

| | Value | Defined in |
|---|---|---|
| Provider | `docker-desktop`, the V1 reference provider. `kind` is supported and uncertified | [the provider contract](local-cluster-provider-contract.md) |
| Context | `docker-desktop`. On `kind` it is `kind-` followed by the cluster name | `lib.sh` |
| Kubeconfig | `.kube/inferops-target.config`, git-ignored and a credential | `lib.sh` |
| Namespace | `inferops-release`, owned by Terraform | `lib.sh` |
| Release | `inferops` | `lib.sh` |
| Platform API | Deployment and Service `inferops-inferops-llm`, container `api`, port `8090` | the chart |
| Serving runtime | Deployment and Service `inferops-inferops-llm-runtime`, container `runtime`, init container `verify-model`, port `8080` | the chart |
| Collector | Deployment and Service `inferops-inferops-llm-collector`, container `collector`, port `9090` | the chart |
| Model cache claim | `inferops-model-cache` | Terraform |

Every command below is written for `docker-desktop`. On `kind`, change
`--context docker-desktop` to `--context kind-<your cluster name>` and nothing else.

To write a fresh target file without changing anything in the cluster:

```text
# read-only against the cluster. Verifies the target, rewrites the target file,
# and runs a Terraform plan that it does not apply.
INFEROPS_PROVIDER=docker-desktop scripts/environment/terraform-prerequisites.sh plan
```

`scripts/environment/target-detect.sh` reports which providers this host can see.
It selects none, and it writes no target file.

## Automatic and human recovery at a glance

"Automatic" means a controller already running in the cluster restores service
with nobody acting. It does not mean an operator is told.

| Incident | Recovers without anybody | What a person has to do | Evidence |
|---|---|---|---|
| [Pod loss](#pod-loss) | **Yes**, by the Deployment controller. Observed once | Nothing to restore it. Confirm it, and find out why the pod went | `local-real-cpu` |
| [Unready model](#unready-model) | **No.** The kubelet restarts the container into the same load, again and again | Correct the value that starves the load and upgrade, or roll back | `local-real-cpu` |
| [Latency and errors](#latency-and-errors) | **No** | Read the error code, then act on the component it names | `synthetic` alerts, `local-real-cpu` error codes |
| [Resource pressure and out-of-memory](#resource-pressure-and-out-of-memory) | **Partly.** The kubelet restarts a killed container. Never provoked here | Size the container or the engine. Never raise a probe budget to hide it | described |
| [Telemetry gap](#telemetry-gap) | **Partly.** The Deployment controller replaces a lost collector pod, and what it had collected is lost | Fix discovery. Nothing restores lost series | described, `synthetic` |
| [Bad release](#bad-release) | **No.** There is no automated rollback | Roll back to the last known-good revision | `local-real-cpu` |
| [Model and cache faults](#model-and-cache-faults) | **No.** The init container refuses and keeps refusing | Fix the values or the cache contents | described, one fault injected on purpose |
| [Cost anomaly](#cost-anomaly) | **No.** Nothing computes cost at run time | Find which input moved | `local-static` |

## Prerequisites

[The prerequisites page](../prerequisites.md) owns the host requirements and the
tool versions. Two of them decide most first-run failures:

- **A `kubectl` within one minor version of the server.** A container desktop
  application may ship its own `kubectl` that has moved further ahead, and every
  workflow refuses it with `client-outside-skew`. Put a supported one ahead of it on
  `PATH`.
- **The host checks:**

```text
# read-only
scripts/environment/preflight.sh
```

If the engine's storage is on a different volume from the system drive, the disk
check reads the wrong volume. Set `INFEROPS_DISK_VOLUME` to the right one, as
[the local cluster page](local-cluster.md) describes. Do not lower the floor.

The model artifact is about 1.71 GiB. It is acquired once, into the workspace cache,
and verified against its pinned byte count and SHA-256:

```text
# read-only
uv run --locked python -m tools.model_acquisition check
uv run --locked python -m tools.model_acquisition verify
```

`acquire` downloads, and it is a separate decision. See
[model acquisition](../serving/model-acquisition.md).

## Deploying a release that stays up

**No script in this repository leaves a release running.** Every workflow that
installs `inferops` removes it again: the lifecycle check, the certifications, the
experiments, and the clean-clone run. A release an operator can use, watch, and
send load to is installed by hand. The steps below are the ones
[the dashboard validation run](../proof/telemetry/v1-s4-002-pr2-dashboard-validation.md#method)
executed once, with the target flags written out.

1. **Build the API image and load it into the cluster's node.** It is published to
   no registry, so its digest is read from the build and written into an overlay:

```text
# mutating: builds a host image and imports it into the cluster's node
INFEROPS_PROVIDER=docker-desktop scripts/environment/api-image.sh build
INFEROPS_PROVIDER=docker-desktop scripts/environment/api-image.sh load
INFEROPS_PROVIDER=docker-desktop scripts/environment/api-image.sh values > .artifacts/api-image-values.yaml
```

2. **Seed the model from the workspace cache**, so the acquisition hook does not
   download 1.71 GiB again:

```text
# mutating: builds a host image and imports it into the cluster's node
INFEROPS_PROVIDER=docker-desktop scripts/environment/model-seed-image.sh build
INFEROPS_PROVIDER=docker-desktop scripts/environment/model-seed-image.sh load
INFEROPS_PROVIDER=docker-desktop scripts/environment/model-seed-image.sh values > .artifacts/model-seed-values.yaml
```

3. **Apply the prerequisites.** Terraform owns the namespace and the model cache
   claim, and nothing else:

```text
# mutating: creates one namespace and one persistent volume claim
INFEROPS_PROVIDER=docker-desktop scripts/environment/terraform-prerequisites.sh apply
```

4. **Install.** The timeout has to outlast a model load, which has been measured
   between 133,515 ms and 358,735 ms on the reference host outside Kubernetes. Never
   pass `--create-namespace`: it makes Helm an owner of Terraform's namespace, and
   the release's uninstall would then delete it.

```text
# mutating: installs the release
helm --kubeconfig .kube/inferops-target.config --kube-context docker-desktop \
  install inferops charts/inferops-llm --namespace inferops-release \
  -f charts/inferops-llm/ci/real-values.yaml \
  -f .artifacts/api-image-values.yaml -f .artifacts/model-seed-values.yaml \
  --wait --timeout 15m
```

`charts/inferops-llm/ci/real-values.yaml` is a render fixture. On its own it names
an API image digest that resolves to nothing, and the kubelet reports
`ErrImageNeverPull`. The two overlays are what make it installable.

## Verifying readiness and inference

A rollout that succeeded, a Service selecting nothing, and a runtime that loaded no
weights all look the same until something asks for a completion. Ask all three
questions.

```text
# read-only
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release rollout status deployment/inferops-inferops-llm-runtime --timeout=10m
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release rollout status deployment/inferops-inferops-llm --timeout=5m
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get pods,svc,endpointslice -o wide
```

The release's own in-cluster test is a pod that the hook creates and deletes when
it passes:

```text
# mutating, release-scoped: creates and removes the release's test pod
helm --kubeconfig .kube/inferops-target.config --kube-context docker-desktop \
  test inferops --namespace inferops-release
```

Then ask the API itself, through a loopback forward, in a second shell:

```text
# read-only. Leave the forward running in its own shell.
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release port-forward svc/inferops-inferops-llm 18091:8090
```

```text
# read-only
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18091/health/ready
curl -sS http://127.0.0.1:18091/v1/models
```

`/health/ready` answers `200` only when the API accepts work **and** its adapter
reports itself able to serve. `/v1/models` names the served model and the runtime.
A completion is the only proof that inference works. The certification workflow
sends one, checks for output tokens, and keeps no text, and that is the checked way
to ask. It installs and removes its own release, so it cannot be pointed at this
one:

```text
# mutating: installs its own release, sends one real completion, and uninstalls
INFEROPS_PROVIDER=docker-desktop scripts/environment/kubernetes-certification.sh certify \
  --values charts/inferops-llm/ci/real-values.yaml \
  --values .artifacts/api-image-values.yaml --values .artifacts/model-seed-values.yaml \
  --confirm-real-kubernetes
```

It refuses to start while `inferops` is installed.

## Telemetry

`telemetry.collection.collector.deploy` is on in the real values, so the release
brings its own collector. Its series live in an `emptyDir` that goes away with its
pod, and no durable store, dashboard server, or alert route is installed.

```text
# read-only. Leave the forward running in its own shell.
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release port-forward svc/inferops-inferops-llm-collector 19090:9090
```

With the forward open, the collector's own pages are at `http://127.0.0.1:19090`.
`/targets` shows discovery. The collector does not load the alert rule files, so to
check an alert's condition, paste its expression from
[the alert record](../telemetry/inference-alerts.md) into the query page. Read [the dashboard's thirty-second guide](../telemetry/inference-operations-dashboard-operator-guide.md)
before believing a panel. **A rate can read `0` all the way through a real failure,
and a since-start count is the reading that shows something happened.**

Whether the collector's configuration still matches the telemetry catalog is
checked without a cluster:

```text
# read-only
uv run --locked python -m tools.telemetry_collection charts/inferops-llm/ci/rendered
uv run --locked python -m tools.inference_alerts
```

## Load testing

Load is generated from one versioned profile by
[the load generator](../serving/llm-load-generation.md). Two paths exist, and only
one of them has been executed.

```text
# read-only
uv run --locked python -m tools.llm_load check
uv run --locked python -m tools.llm_load rehearse
scripts/environment/performance-scenarios.sh check
```

`rehearse` runs the whole tool against an in-process stub and writes a record
labelled `synthetic`. No latency it records describes serving.

**The executed path** installs its own release, runs the matrix, and uninstalls. It
refuses while `inferops` is installed:

```text
# mutating: installs its own release, sends real load, and uninstalls
INFEROPS_PROVIDER=docker-desktop scripts/environment/performance-scenarios.sh run \
  --values charts/inferops-llm/ci/real-values.yaml \
  --values .artifacts/api-image-values.yaml --values .artifacts/model-seed-values.yaml \
  --confirm-real-kubernetes
```

**Load against the release installed above** is `python -m tools.llm_load run`
through the API forward, with the environment facts file the
[load generator's guide](../serving/llm-load-generation.md#run-against-a-real-release-only-when-authorized)
describes. That guide states that those hand-run commands are documented and
unexecuted as written, and this page does not change that.

Load is not a health check. It is uncontrolled load on the same host. Do not run it
while an experiment is measuring, and do not run the test suite during one.

## When an alert fires

Each section below is the target of one alert's `runbook` annotation. The first
command in each is read-only. "Fires" means the alert's condition holds, whether or
not any Prometheus is evaluating it (see the status note at the top). Every alert
here reads a five-minute range and holds for five or ten minutes. **A disruption shorter than that fires nothing.** When the
recorded pod loss was replayed through the alerts, none of them fired: the outage
ended before any window could fill.

### InferOpsInferenceCallersRefused

Critical. Owner: the serving path. The API has been answering `503
capability-unavailable` for five minutes. It could not reach the serving runtime at
all.

```text
# read-only
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get svc,endpointslice
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get pods -l app.kubernetes.io/component=serving-runtime -o wide
```

Read the runtime Service's EndpointSlice before you read any pod. **Pod readiness is
not what a caller sees.** Throughout the recorded pod loss, the deleted pod kept
reporting `Ready: True` while the Service had no ready endpoint at all.

| What the listing shows | Open |
|---|---|
| No runtime pod, or one being replaced | [Pod loss](#pod-loss) |
| A runtime pod `Running` and not ready, restarts `0` | [Unready model](#unready-model) |
| A runtime pod stuck in `Init:` or `Init:CrashLoopBackOff` | [Model and cache faults](#model-and-cache-faults) |
| A runtime pod restarting, last state `OOMKilled` | [Resource pressure and out-of-memory](#resource-pressure-and-out-of-memory) |
| The alert began after an upgrade | [Bad release](#bad-release) |

### InferOpsInferenceServingNothing

Critical. Owner: the serving path. Requests have been arriving for five minutes and
none of them succeeded. This is the backstop alert: it reads the outcome, not a
code. **Do not restart anything until the code is known.**

```text
# read-only. The error body names the code; the API's structured records name it too.
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release logs deployment/inferops-inferops-llm -c api --tail=200
```

With the collector forward open, the counter by code is
`sum by (inferops_error_code) (inferops_inference_errors_total)`. Read the counter,
not the rate. Then open [latency and errors](#latency-and-errors), which maps each
code to an incident.

### InferOpsReadinessRefusalsSustained

Critical. Owner: the serving path. More than half of one component's readiness
probes have been refused for five minutes. **This is the only alert that fires
before a caller notices**, and it fires on a release nobody is sending traffic to.
Its `inferops_component` label says which half refused.

```text
# read-only
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release describe pods -l app.kubernetes.io/instance=inferops
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get events --sort-by=.lastTimestamp
```

| Component | Open |
|---|---|
| `serving-adapter`, runtime `Running` and loading | [Unready model](#unready-model) |
| `serving-adapter`, runtime init container failing | [Model and cache faults](#model-and-cache-faults) |
| `serving-adapter`, just after an upgrade | [Bad release](#bad-release) |
| `platform-api` | The API itself refuses. Read its log, as for the previous alert |

### InferOpsInferenceLatencyPastHalfTheRequestBudget

Warning. Owner: the serving path. The 95th percentile of completion time has been
over 60 seconds for ten minutes. That is half of `api.requestTimeoutMs`, which is
120000 by default. Nothing has been refused yet.

```text
# read-only
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get pods -o wide
docker info --format "{{.NCPU}} CPUs; {{.MemTotal}} bytes"
```

Find out whether the host is the cause before you change the release. **Raising the
timeout is the one change that hides this fault instead of fixing it.** Open
[latency and errors](#latency-and-errors), then
[resource pressure](#resource-pressure-and-out-of-memory).

### InferOpsRuntimeDefersRequests

Warning, real profile only. Owner: the serving path. For ten minutes the runtime has
held requests it had no free parallel slot for. `runtime.parallelSlots` is 1 by
default, so this is demand beyond what the release is configured to serve at once.

```text
# read-only
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get deployment inferops-inferops-llm-runtime \
  -o jsonpath='{.spec.replicas}{"\n"}'
```

The deferral count is a number of requests. It does not say how long any of them
waited. Choose between less demand and more capacity:
[resource pressure](#resource-pressure-and-out-of-memory) has the procedure.

### InferOpsPlatformApiScrapeJobAbsent

Warning. Owner: the collection. The collector's `platform-api` job has matched no
target for ten minutes. **While this fires, silence from the other five alerts means
nothing was asked. It does not mean nothing is wrong.**

```text
# read-only
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get pods -l app.kubernetes.io/instance=inferops --show-labels
```

Open [telemetry gap](#telemetry-gap).

## Incidents

Each procedure answers the same six questions in the same order. Where no alert
exists for an incident, the procedure says why, and what a person has to look at
instead.

### Pod loss

A serving runtime pod is deleted, evicted, or lost with its node.

| | |
|---|---|
| Detection | `InferOpsInferenceCallersRefused` if the outage lasts longer than its window. In the recorded run it did not, and nothing fired. There is no restart alert: the series it would read comes from kube-state-metrics, which nothing here installs. By hand, the runtime Service's EndpointSlice listing no ready endpoint |
| User impact | With one replica, an outage. In the recorded run, a request already in flight hung and came back `500 internal-error`. Requests sent while the Service had no ready endpoint came back `503 capability-unavailable` within tens of milliseconds: 40 of them in a 31,960 ms caller-visible outage |
| Automatic recovery | **Yes.** The Deployment controller creates a replacement, which reuses the model already in the claim and loads it again. The replacement reported Ready 33,665 ms after the delete, and the model reload took 32,304 ms of that. Nobody intervened |
| Human action | None to restore service. Find out why the pod went before it happens again. Do not delete the replacement to "help": it is the recovery |
| Validation | The EndpointSlice lists one ready endpoint, the replacement's own `Ready` condition is true, and a request comes back `200`. Not the Deployment's ready count, which still counted the deleted pod |
| Escalation and limits | If the replacement does not become ready, this is no longer pod loss: open [unready model](#unready-model) or [model and cache faults](#model-and-cache-faults). Every figure here comes from one pod lost once, on one host. None of them is an availability figure or a recovery-time objective |

```text
# read-only
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get endpointslice -l kubernetes.io/service-name=inferops-inferops-llm-runtime
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get pods -l app.kubernetes.io/component=serving-runtime \
  -o jsonpath='{range .items[*]}{.metadata.name} {.status.conditions[?(@.type=="Ready")].status} {.status.containerStatuses[*].restartCount}{"\n"}{end}'
```

Evidence: [the pod-loss experiment](../proof/serving/v1-s4-006-pr1-inference-pod-recovery.md),
`local-real-cpu`, and [its procedure](../serving/inference-pod-recovery.md).

### Unready model

The runtime process is alive and answering on its port, and the model behind it
never becomes servable.

| | |
|---|---|
| Detection | `InferOpsReadinessRefusalsSustained` with component `serving-adapter`, and `InferOpsInferenceCallersRefused`. The model-readiness gauge is specified and emitted by nothing, so no alert reads the model's own answer. By hand: the runtime pod is `Running`, not ready, and has restart count `0`, and the startup probe keeps failing with `503` |
| User impact | Every completion is refused. In the recorded run a caller was told `capability-unavailable`, condition `runtime-unreachable`, and not `model-not-ready`: both Services had dropped their only endpoint, so the API could not reach the runtime at all |
| Automatic recovery | **None.** No controller notices that a load cannot finish. At the end of the startup probe budget, `runtime.probes.startup.budgetMs` of 600000 ms, the kubelet restarts the container into the same load |
| Human action | Find what starves the load, correct that value, and upgrade. In the recorded run this was a processor limit, and one corrected upgrade brought the release back. If the cause cannot be found, [roll back](#bad-release) to the last revision that served |
| Validation | A completion comes back served with output tokens, from a pod that is **not** the one that was starved. During a rolling update the predecessor can finish its starved load and serve first, which would make the fix look effective when it was not |
| Escalation and limits | A load that is slow is not the same as one that cannot finish. The measured loads on the reference host took up to 358,735 ms outside Kubernetes. **Do not raise the probe budget to make a slow host look healthy.** In the recorded run the release was held unready for 179,755 ms. The first served completion came 36,687 ms after the corrected upgrade was issued, and that interval includes the workflow's own forwards and polling |

```text
# read-only
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release describe pods -l app.kubernetes.io/component=serving-runtime
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release logs deployment/inferops-inferops-llm-runtime -c runtime --tail=100
```

```text
# mutating: the corrected upgrade. VALUES is the file the release was installed
# with, after the value that starves the load has been fixed in it.
helm --kubeconfig .kube/inferops-target.config --kube-context docker-desktop \
  upgrade inferops charts/inferops-llm --namespace inferops-release \
  -f VALUES --wait --timeout 15m
```

Evidence: [the unready-model experiment](../proof/serving/v1-s4-007-pr1-unready-model-recovery.md),
`local-real-cpu`, and [its procedure](../serving/unready-model-recovery.md).

### Latency and errors

Callers are slow, or some of them are refused, and the release is otherwise up.

| | |
|---|---|
| Detection | `InferOpsInferenceLatencyPastHalfTheRequestBudget` for slowness, and `InferOpsInferenceServingNothing` when nothing succeeds. **No alert covers a partial error rate.** An alert on some share of requests failing needs an error budget, and none is decided anywhere in this project. By hand: the errors-since-start count on the dashboard, and the counter by code |
| User impact | Waiting, or a canonical error body with a code and a retryable flag. A request that runs past `api.requestTimeoutMs` is refused as `request-timeout` or `upstream-timeout` |
| Automatic recovery | **None.** Nothing retries on a caller's behalf, sheds load, or scales out |
| Human action | Read the code, then act on the component it names. See the table below |
| Validation | New requests come back `200`, and the errors-since-start count stops rising. Do not use a rate for this: a rate can read `0` while the count climbs |
| Escalation and limits | The latency threshold is half the configured timeout and a declared histogram boundary. It is not a service-level objective, and nothing this project measured sets it. The slowest client-measured 95th percentile in the local matrix was 8,614 ms, on one host |

| Code | What it says | Open |
|---|---|---|
| `capability-unavailable` | The runtime accepted no connection. Also returned when a caller asks for streaming | [Pod loss](#pod-loss), [unready model](#unready-model) |
| `model-not-ready` | The runtime answered `503` while it loads | [Unready model](#unready-model) |
| `upstream-timeout`, `request-timeout` | The runtime, or the caller's own deadline, ran out | [Resource pressure](#resource-pressure-and-out-of-memory) |
| `internal-error` | The runtime answered with a non-2xx status, or a body the adapter could not read. In the recorded pod loss, the request in flight when the pod went | [Pod loss](#pod-loss), then the runtime log |
| `contract-invalid`, `version-unsupported` | The caller sent something outside the accepted surface | The caller. The release is fine |

```text
# read-only
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release logs deployment/inferops-inferops-llm -c api --tail=200
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release logs deployment/inferops-inferops-llm-runtime -c runtime --tail=200
```

The API's records carry identifiers, codes, and durations, and never content. That
makes a tail of them safe to attach to an issue. The runtime's own log is not
covered by that guarantee, so do not attach it.

Evidence: the alert scenarios `inference-slower-than-the-request-budget` and
`serving-pod-lost` in [the alert record](../telemetry/inference-alerts.md),
`synthetic`. The error codes come from the two recorded failure experiments, which
are `local-real-cpu`.

### Resource pressure and out-of-memory

The runtime is starved of processor, or a container reaches its memory limit or the
engine's.

| | |
|---|---|
| Detection | `InferOpsRuntimeDefersRequests` for saturation, and `InferOpsInferenceLatencyPastHalfTheRequestBudget`. **No alert reads memory or restarts.** The API's memory metric has no source this distribution may read, container resource use needs an add-on nothing installs, and `kubectl top` needs a metrics-server that V1 does not ship. By hand: last state `OOMKilled`, restarts climbing, pods `Pending` with `Insufficient cpu` or `Insufficient memory` |
| User impact | Requests queue inside the runtime and wait. A killed runtime container is a [pod-loss](#pod-loss)-shaped outage, followed by a full model reload |
| Automatic recovery | **Partly.** The kubelet restarts a killed container, with back-off. That restores nothing if the same load hits the same limit again. **This was never provoked here** |
| Human action | Find out which ceiling was reached before changing anything: the pod's limit or the engine's. For saturation, reduce caller concurrency or raise `runtime.parallelSlots` or the replica count, then measure again. For memory, size from the worst-case charge and never from the private working set: the weights are memory-mapped |
| Validation | No restarts after the change, no `Pending` pods, and the deferral alert resolves. Then a load run, if one is authorised |
| Escalation and limits | The runtime's defaults are 1 CPU and `2Gi` requested, and a `6` CPU and `3Gi` limit. In the measured matrix the runtime used 99.1–99.9% of its CPU limit at every level, and throttling was not sampled. A multi-replica release was refused at the capacity gate on the reference host, so the replica count cannot be raised there |

```text
# read-only
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get pods -l app.kubernetes.io/instance=inferops \
  -o jsonpath='{range .items[*]}{.metadata.name} {.status.containerStatuses[*].restartCount} {.status.containerStatuses[*].lastState.terminated.reason}{"\n"}{end}'
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get events --sort-by=.lastTimestamp
docker info --format "{{.NCPU}} CPUs; {{.MemTotal}} bytes"
```

A change of size is an upgrade with a corrected values file, as in
[unready model](#unready-model). The two ceilings, the request and limit table, and
why a container killed partway through a load is usually the engine's ceiling are
in [the troubleshooting guide](kubernetes-troubleshooting.md#scheduling-resources-and-out-of-memory).

Evidence: described. The CPU figures come from
[the performance findings](../proof/serving/v1-s4-004-pr2-performance-findings.md),
`local-real-cpu`. No memory limit and no out-of-memory kill has ever been observed in
this project.

### Telemetry gap

The collector is gone, discovers nothing, or has lost what it collected.

| | |
|---|---|
| Detection | `InferOpsPlatformApiScrapeJobAbsent`. The collector computes the series it reads, `inferops:scrape_job_absent:platform_api`, which can be queried by hand. **A collector that is not running computes nothing, including that series.** By hand: the collector pod, and its `/targets` page |
| User impact | None directly. The release can be serving normally. What is lost is the ability to know: a silent alert means nothing was asked, and a dashboard panel shows *missing* instead of a value |
| Automatic recovery | **Partly.** The Deployment controller replaces a lost collector pod. The series it held were in an `emptyDir` and are gone. Nothing restores them, and a rate over a counter born after the gap reads no increase until the next event |
| Human action | Check discovery before touching the release. A job that matches nothing is usually a selector, a namespace, or a port name, and restarting fixes none of those. Compare the installed configuration with the catalog |
| Validation | Both tiers answer on the dashboard's first row, and `/targets` lists the `platform-api` job up. The scrape alert resolves |
| Escalation and limits | This alert has never been exercised against a real collector. No experiment has broken discovery on purpose, so it has only been evaluated over a synthetic fixture. In the dashboard validation, a scaled-to-zero serving runtime showed as a job that discovered no pod, and that is the closest real observation |

```text
# read-only
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get pods -l app.kubernetes.io/component=telemetry-collector -o wide
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release logs deployment/inferops-inferops-llm-collector -c collector --tail=100
helm --kubeconfig .kube/inferops-target.config --kube-context docker-desktop \
  get manifest inferops --namespace inferops-release > .artifacts/installed-manifest.yaml
uv run --locked python -m tools.telemetry_collection .artifacts/installed-manifest.yaml
```

`.artifacts/` is ignored by version control. The manifest is host state, and it is
not evidence.

Evidence: described. What stands behind it is the `platform-api-not-discovered`
scenario in [the alert record](../telemetry/inference-alerts.md), `synthetic`, and
[the dashboard validation](../proof/telemetry/v1-s4-002-pr2-dashboard-validation.md),
`local-real-cpu`. The collector is in the
[troubleshooting guide](kubernetes-troubleshooting.md#telemetry-scrape).

### Bad release

An upgrade produced a revision that does not work.

| | |
|---|---|
| Detection | Evidence, not a clock. The candidate pod's `verify-model` init container exits non-zero, or its runtime never becomes ready. **In the recorded shape no alert fires**: with one replica, the rollout surges, the old pod keeps serving, and the API stays ready. `progress deadline exceeded` is a deadline. It is not a detection |
| User impact | In the recorded run, none. Every readiness probe through the Service was answered while the candidate failed. A fault that makes the *running* pod unhealthy would look very different, and nobody has injected one |
| Automatic recovery | **None.** No GitOps controller, progressive delivery, or automated rollback trigger exists. A release stays on a failing candidate until a person acts |
| Human action | Read `helm history`, pick the last revision that served, and roll back to it. The rollback records a **new** revision |
| Validation | A zero exit from `helm rollback` only means a revision was recorded. Also check that both rollouts completed, that `helm test` passes, and that a request comes back `200`. Those are the checks in [verifying readiness and inference](#verifying-readiness-and-inference) |
| Escalation and limits | Only a rollback to a revision this cluster created minutes earlier has been executed. Rolling back across a chart version, a schema change, or a persisted-state migration has not |

```text
# read-only
helm --kubeconfig .kube/inferops-target.config --kube-context docker-desktop \
  history inferops --namespace inferops-release
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get pods -l app.kubernetes.io/component=serving-runtime \
  -o jsonpath='{range .items[*]}{.metadata.name} {.status.initContainerStatuses[*].lastState.terminated.exitCode} {.status.initContainerStatuses[*].state.terminated.exitCode}{"\n"}{end}'
```

```text
# mutating: rolls back to REVISION, which history showed as the last one that served
helm --kubeconfig .kube/inferops-target.config --kube-context docker-desktop \
  rollback inferops REVISION --namespace inferops-release --wait --timeout 15m
```

Evidence: [the upgrade and rollback experiment](../proof/environment/v1-s3-011-pr2-upgrade-rollback.md),
`local-real-cpu`, and [its procedure](helm-upgrade-rollback.md).

### Model and cache faults

The claim is empty, holds the wrong bytes, or holds bytes for a different revision.

| | |
|---|---|
| Detection | The runtime pod never leaves `Init:`, because `verify-model` refuses before the runtime container is started. `InferOpsReadinessRefusalsSustained` fires if the API is also up. The refusal says why: `REFUSED: the mounted model cache holds no artifact for the declared revision`, or `REFUSED: the mounted model artifact does not match the pinned byte count`, or a failure inside `sha256sum -c -` |
| User impact | No serving runtime, and therefore every completion refused. After an upgrade with one replica, none: the old pod keeps serving, as in [bad release](#bad-release) |
| Automatic recovery | **None.** The init container refuses again on every restart, by design. A serving pod mounts the claim read-only and cannot repair it |
| Human action | Read the init container's log. Wrong revision or repository in the values: correct them. An empty claim: the acquisition hook fills it on install and upgrade, so check the hook Job. Wrong bytes: reclaim the claim with the Terraform destroy in [cleanup](#cleanup), then install again |
| Validation | `verify-model` exits `0` and the runtime becomes ready. The workspace copy verifies with `tools.model_acquisition verify` |
| Escalation and limits | Deleting a cache costs a 1.71 GiB download. **Do not delete either cache to fix a problem you have not localised.** Only the byte-count refusal has been provoked, on purpose, in the rollback experiment. The others are read from the rendered init container |

```text
# read-only
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release logs deployment/inferops-inferops-llm-runtime -c verify-model
kubectl --kubeconfig .kube/inferops-target.config --context docker-desktop \
  -n inferops-release get pvc,jobs
uv run --locked python -m tools.model_acquisition verify
```

The claim, its layout, and what survives what are in
[model cache storage](model-cache-storage.md) and
[the troubleshooting guide](kubernetes-troubleshooting.md#model-cache-and-storage).

Evidence: described, from the rendered init container and
[model cache storage](model-cache-storage.md). The byte-count refusal was provoked
on purpose in [the upgrade and rollback experiment](../proof/environment/v1-s3-011-pr2-upgrade-rollback.md),
`local-real-cpu`.

### Cost anomaly

An estimated cost record came out different from the one before, or will not
regenerate.

| | |
|---|---|
| Detection | **Nothing detects this at run time.** No platform component computes or emits a cost record, and no alert, panel, or query reads cost. An anomaly is found offline: a committed baseline stops regenerating byte for byte, a calculation is refused, or a figure moves between two runs someone compares |
| User impact | None to a caller. The risk is a reader: an estimated figure mistaken for a bill. Every figure this project can produce has confidence `none`, because the only rate card is synthetic |
| Automatic recovery | **None**, and none is possible. A cost record is a document |
| Human action | Find which input moved: the measured usage, the synthetic rate card, or the method. Regenerate and compare. Never edit a figure to make it match |
| Validation | Both verifications below pass, and the cost suite passes |
| Escalation and limits | An estimate is not an invoice. No provider rate card and no bill has ever been read. A moved figure means an input changed, not that something cost more |

```text
# read-only
uv run --locked python -m tools.cost_baseline verify --record-dir docs/proof/serving --record-prefix v1-s4-004-pr1- --dir docs/proof/cost --prefix v1-s4-005-pr2-
uv run --locked python -m tools.cost_calculation verify --input tests/cost/fixtures/cost-calculation/estimate-closes.input.json --result tests/cost/fixtures/cost-calculation/estimate-closes.result.json
uv run --locked python -m pytest tests/cost -q
```

Evidence: [the cost baseline](../proof/cost/v1-s4-005-pr2-cost-baseline.md) and
[the cost method](../cost/cost-method.md), `local-static` as far as this page is
concerned: both verifications read committed files only.

## Cleanup

Four operations, with four different blast radii. **They are not a sequence, and
none of them implies the next.** Pick the smallest one that deals with your
problem. Each is explained in
[the troubleshooting guide's cleanup section](kubernetes-troubleshooting.md#cleanup).

1. **The release.** Removes every object the release owns. The namespace, the
   claim, and the model in it survive.

```text
# destructive, release-scoped
helm --kubeconfig .kube/inferops-target.config --kube-context docker-desktop \
  uninstall inferops --namespace inferops-release --wait
```

2. **The prerequisites.** Deletes the namespace, which cascades, and reclaims the
   model in the claim. It refuses without `--confirm`, and it refuses while a
   release is still installed. It will not uninstall one for you.

```text
# destructive, namespace-cascading. Reclaims about 1.71 GiB of model weights.
INFEROPS_PROVIDER=docker-desktop scripts/environment/terraform-prerequisites.sh destroy --confirm
```

3. **The workspace model cache**, on the host. It reaches nothing in any cluster:

```text
# destructive only with --confirm. Without it, prints what would be removed.
uv run --locked python -m tools.model_acquisition clean
uv run --locked python -m tools.model_acquisition clean --confirm
```

4. **The cluster.** On `docker-desktop`, the cluster belongs to the operator.
   InferOps never creates, resets, or deletes it, and the images loaded into its
   node stay there. On a `kind` cluster made by this repository's helper,
   `scripts/environment/cluster-down.sh` removes it. It is
   [step 4 of the troubleshooting guide's cleanup](kubernetes-troubleshooting.md#4-destroy-the-cluster).

**Nothing here prunes the container engine, deletes a namespace by hand, or touches
the operator's own kubeconfig.** A cleanup that reached further than the thing it
was cleaning up would be an incident of its own.

## What has been run, and what has not

| Procedure | Executed | Where |
|---|---|---|
| The offline checks on this page | Yes, for this change | [this page's validation record](../proof/environment/v1-s5-005-pr1-validation.md) |
| Deploying a release that stays up | Once, on `docker-desktop` | [the dashboard validation](../proof/telemetry/v1-s4-002-pr2-dashboard-validation.md#method) |
| Verification: rollout, `helm test`, a real completion | Yes, inside the certification and experiment workflows | [the reference-provider paved road](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md) |
| Pod loss, and its automatic recovery | Once, under load | [the pod-loss experiment](../proof/serving/v1-s4-006-pr1-inference-pod-recovery.md) |
| Unready model, and its human recovery | Once | [the unready-model experiment](../proof/serving/v1-s4-007-pr1-unready-model-recovery.md) |
| Bad release, detection, and rollback | Once | [the upgrade and rollback experiment](../proof/environment/v1-s3-011-pr2-upgrade-rollback.md) |
| Load through the scenario workflow | Twice in one run | [the performance scenarios validation](../proof/serving/v1-s4-004-pr1-validation.md) |
| The release-scoped and prerequisite cleanups | Yes | [the scoped cleanup result](../proof/environment/v1-s3-011-pr2-scoped-cleanup.md) |
| Resource pressure, out-of-memory, a telemetry gap, a cost anomaly | **No** | Described only |
| Any procedure on this page, run as a drill by someone following it | **No** | Not run |
| Any alert firing in a real collector | **No** | The alerts were replayed over three recorded experiments by this repository's own evaluator |

A procedure a workflow executed is not the same as one an operator followed from
this page. The commands are the same ones, scoped the same way, but nobody other
than the author has followed any of them from here.

## Known gaps

- **No release evaluates the alerts, and nobody is told.** The release's collector
  does not load the alert rule files, and no receiver, routing tree, or on-call
  rotation exists. The owners on each alert are roles an installation has to fill.
- **No restart, memory, or model-readiness alert.** The deferred alerts in
  [the alert record](../telemetry/inference-alerts.md) say what would have to exist
  first, and none of it does.
- **No partial-error alert**, because no error budget is decided.
- **A disruption shorter than an alert window is invisible**, by design. The
  recorded pod loss was one.
- **No automated rollback**, and no standing-release install script.
- **One replica.** Every outage recorded here was caused by that choice.
- **The collector's data dies with its pod.** No durable store is selected.

## What this page does not establish

- That an operator following it recovers from a fault the records did not produce.
  Three procedures rest on executed experiments. The rest are described.
- Anything about a provider other than `docker-desktop`, a host other than the one
  Windows host, a cluster with more than one node, or a release with more than one
  replica.
- Any availability figure, service-level objective, error budget, or recovery-time
  objective. Every duration quoted here is one observation, and
  [ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md)
  governs what such a figure may be used to say.
- That anybody would be told when an alert fires.

[`tests/architecture/test_operator_runbook.py`](../../tests/architecture/test_operator_runbook.py)
keeps this page consistent with the repository. It checks that every tool command
names a real module and subcommand, and every script and subcommand exists. Every
target, object name, port, and default is compared with the file that owns it, and
every `kubectl` and `helm` sample must be scoped to the target file, a context, and
the namespace. Every block must carry a safety label that its commands do not
contradict. Every alert must link to its own section here, every incident must
answer the six questions and state automatic or human recovery the way the record
does, every quoted figure must be read back from the record it came from, and every
relative link must resolve. It checks strings. It does not check a cluster.
