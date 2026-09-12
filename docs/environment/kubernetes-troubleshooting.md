# Kubernetes troubleshooting and cleanup

Status: **both halves have now been executed, on one provider.** Everything about
creating, verifying, scheduling into, and tearing down the `inferops-dev` `kind`
cluster was run on one Windows host and recorded in
[the cluster smoke evidence](../proof/environment/v1-s0-002-pr2-cluster-smoke.md)
and [the cluster lifecycle result](../proof/environment/v1-s3-001-pr1-cluster-lifecycle.md).
Everything about the `inferops-llm` release — install, model load, probes,
Service, telemetry scrape, upgrade, rollback, pod replacement, and uninstall —
has now been run on the Kubernetes cluster **Docker Desktop** provides, and is
recorded in
[the reference-provider paved road](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md),
[the upgrade and rollback experiment](../proof/environment/v1-s3-011-pr2-upgrade-rollback.md),
and [the pod-restart experiment](../proof/serving/v1-s3-003-pr2-kubernetes-pod-restart.md).

**What that does and does not make the entries below.** The symptoms this page
describes are still derived from the chart, the scripts, the descriptors, and the
tooling rather than from having each been *provoked* — a page of faults is not a
page of faults somebody caused on purpose. Several of them were provoked, by
accident or by design, during `V1-S3-011`, and those are called out where they
appear. The rest remain derived, and this page says which is which rather than
letting an executed release imply an executed symptom.

The blocker this page used to open with is gone. `platform-api-container-image`
is `implemented` in [the ownership inventory](../architecture/resource-ownership.md),
[`deploy/api/Dockerfile`](../../deploy/api/Dockerfile) is committed, and the image
is built on the host and made visible to the selected cluster by that provider's
own image path. A release whose API image resolves becomes ready, and one has.

**The committed real values still carry a placeholder digest for it**, and that
has not changed: the image is built on a contributor's own machine and published
to no registry, so no digest this repository could commit would resolve anywhere
else. An executed run supplies the host's own digest as an overlay, which the
image script prints. Following this page with the committed values alone still
reaches an image that does not resolve, and **which failure the kubelet reports
depends on the pull policy** — the two are different words: see
[the scheduling table](#scheduling-resources-and-out-of-memory).

**Every result behind this page is `docker-desktop`'s**, on one Windows host, on
CPU, with one replica of each tier.
[ADR 0011](../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md)
forbids reading any of it as a `kind` result.

This page is organised by **what you observed**, because the observation is the
only thing you have when you arrive. Its host-local sibling —
[local runtime troubleshooting](../serving/local-runtime-troubleshooting.md) —
covers the same faults outside Kubernetes and says Kubernetes is out of its
scope. This is the page that scope was waiting for. When the fault is a model
that will not load or a container the engine killed, read both: the Kubernetes
layer usually only tells you *which pod* the host-local page is about.

## Before anything else

Five rules. Each one is the difference between a diagnosis and a second
incident.

1. **Run everything from the repository root.** Every path on this page is
   repository-relative — the kubeconfig, the scripts, the rendered manifests — and
   a command run from elsewhere reads a different file or none at all.
2. **Never let `kubectl` or `helm` pick a context.** Both read an ambient
   `KUBECONFIG` and both act on whatever the current context names. Every
   invocation in this repository goes through `inferops::kubectl` or
   `inferops::helm` in
   [`scripts/environment/lib.sh`](../../scripts/environment/lib.sh), which pass
   `--kubeconfig` and `--context`/`--kube-context` explicitly, and
   [`tests/architecture/test_cluster_lifecycle_safety.py`](../../tests/architecture/test_cluster_lifecycle_safety.py)
   fails the build if one stops doing so. When you run a command by hand, name
   them yourself — see [the two exports](#cluster-and-context) below.
3. **A diagnostic must not change anything.** Every command in a `diagnose`
   block on this page is read-only. The ones that install, delete, or reclaim are
   marked **destructive** and are each a separate deliberate decision.
4. **Never paste a prompt, a completion, a runtime response body, or a request
   log line into an issue.** [The redaction rules](../telemetry/redaction.md)
   forbid content capture and a troubleshooting report is not an exemption.
   Object states, phases, reasons, exit codes, revision numbers, byte counts, and
   durations are sufficient for everything below, and they are what the tooling
   prints.
5. **Read the exit code before the message.** A refusal and a failure are
   different events here, and the number tells you which one you have before you
   read a word.

Nothing on this page accepts a token, a header, a password, or an alternate API
server URL, and this repository holds none. If a step appears to need a
credential, that is itself the finding: stop and report it.

## The checks that localise almost everything

Run them in this order. The first four need no cluster at all, which is the
point — a fault in a rendered manifest, a descriptor, or a Terraform
configuration is cheaper to find before anything is installed.

```text
uv run --locked python -m tools.workload_policy charts/inferops-llm/ci/rendered
uv run --locked python -m tools.telemetry_collection charts/inferops-llm/ci/rendered
uv run --locked python -m tools.helm_upgrade_rollback check
scripts/environment/terraform-prerequisites.sh check
```

| Command | Answers | Needs |
|---|---|---|
| `workload_policy` | Does the rendered workload still satisfy the V1 security policy, default-deny included | a checkout |
| `telemetry_collection` | Does the rendered scrape configuration still agree with the accepted telemetry catalog | a checkout |
| `helm_upgrade_rollback check` | Is the upgrade/rollback descriptor internally consistent and consistent with the certification it shares targets with | a checkout |
| `terraform-prerequisites.sh check` | Is the prerequisite configuration formatted, initialisable, and valid | `terraform` on `PATH` |

Then the three that need the cluster **tooling** — `kind`, `kubectl`, and a
running engine. Only the middle one needs a cluster to exist:

```text
scripts/environment/preflight.sh        # can this host hold a cluster; changes nothing
scripts/environment/cluster-verify.sh   # is the cluster present, ours, pinned, healthy
scripts/environment/verify-clean.sh     # is anything left behind; deletes nothing
```

**Run `preflight.sh` first when you have no working cluster**, not last. It is the
pre-cluster check — host capacity, tool presence, version skew — and it reports a
cluster's existence only in passing. `verify-clean.sh` is its mirror: it asserts
that *nothing* is there, so it needs the engine rather than a cluster.

`cluster-verify.sh` answers five questions and runs all five before reporting, so
a cluster that is wrong in three ways tells you all three at once. It is
described in full in [the local cluster page](local-cluster.md#verifying-a-cluster-you-already-have).

## Exit codes

The workflows here share one vocabulary, and both Python tools use it.

| Code | Meaning |
|---|---|
| `0` | Succeeded |
| `3` | **Refused** — a precondition was not met and nothing was attempted |
| `4` | Ran and **failed** |
| `5` | **Inconclusive** — the run could not observe what it came to observe. `tools.helm_upgrade_rollback` only |
| `130` | Interrupted with Ctrl-C |

**A refusal is not a bug.** Every `3` is a guard doing its job: an unowned
cluster, a descriptor that disagrees with the record that decides it, a forward
that is not loopback, a destroy without `--confirm`. The recovery is to satisfy
the precondition, never to bypass the guard, and **no tool under `tools/` has a
force flag**. The scripts have exactly one bypass — `cluster-up.sh --recreate` —
and it is destructive, named on this page where it applies, and not a way past
any of the refusals above.

`5` is the one worth reading carefully. A candidate pod the host could not
schedule never ran the fault it was supposed to run, so the upgrade/rollback
workflow reports `INCONCLUSIVE` rather than claiming a detection it did not make.
The remedy for a `5` is capacity, not a retry.

The shell scripts do not use that vocabulary. They exit non-zero on any failure
and print one of two prefixes, and the difference is worth knowing before you
read one: `[inferops] WARNING:` accumulates a problem and keeps checking, so a
cluster wrong in three ways reports all three; `[inferops] FAILED:` is a
precondition that stopped the run, and it exits immediately. A missing `kind` or
`kubectl` produces the second.

## Cluster and context

Two values, and everything on this page is scoped to them:

| | Value | Set in |
|---|---|---|
| Cluster | `inferops-dev` | `lib.sh` |
| Context | `kind-inferops-dev` | `lib.sh`, derived from the cluster name |
| Kubeconfig | `.kube/inferops-dev.config`, git-ignored | `lib.sh` |
| Smoke namespace | `inferops-smoke` | `lib.sh` |
| Release namespace | `inferops-release` | `lib.sh`, and Terraform's default |
| Release name | `inferops` | `lib.sh` |

To run a `kubectl` by hand without inheriting anything, export both for the
command and nothing wider:

```text
KUBECONFIG=.kube/inferops-dev.config kubectl --context kind-inferops-dev get pods -A
```

| Symptom | What it means | Next step |
|---|---|---|
| `the connection to the server ... was refused` | The cluster is not running, or the engine is not | `docker version --format "{{.Server.Version}}"`, then `scripts/environment/cluster-verify.sh` |
| A script exits with `refusing to act:` and a reason | The reachable API server is not this project's cluster | Do not override it. The check reads kind's own container labels; a matching context name is deliberately not accepted as proof |
| `cluster-up.sh` refuses because a cluster exists | A previous run was interrupted, or the cluster is simply already there | `cluster-verify.sh` first. `cluster-up.sh --recreate` is **destructive** and deletes what is there |
| `kubectl` is two minors from the server | A container desktop application shipped its own and moved it forward | Put a kubectl inside the window — 1.33, 1.34, or 1.35 — ahead of the bundled one on `PATH`. Moving the node image pin forward instead **does not work on a cgroup v1 host** and [the local cluster page](local-cluster.md#when-something-fails) records the attempt |
| `kind` is not on `PATH` | Every script here needs it | Install `v0.32.0` and verify its published checksum before running it |

The node is pinned by digest to
`kindest/node:v1.34.8@sha256:02722c2dedddcfc00febf5d27fbeb9b7b2c14294c82109ff4a85d89ac9ba3256`.
A node running anything else is reported by `cluster-verify.sh` as a mismatch
rather than tolerated.

## Scheduling, resources, and out-of-memory

Read the request before reading the node. The release asks for more than most
people expect from a laptop cluster, and almost every `Pending` here is
arithmetic rather than a fault.

| Container | CPU request | Memory request | CPU limit | Memory limit |
|---|---:|---:|---:|---:|
| `runtime` | `1` | `2Gi` | `6` | `3Gi` |
| `api` | `100m` | `128Mi` | `1` | `512Mi` |
| `verify-model` (init) | `50m` | `16Mi` | `1` | `64Mi` |

The host floor the environment scripts enforce is separate and lower — 4 logical
CPUs, 6,442,450,944 bytes reaching the engine, and 20,000,000,000 bytes free on
one volume — because it sizes the *cluster*, not the release. A host that passes
preflight can still fail to schedule the runtime.

```text
# diagnose — read-only
kubectl --kubeconfig .kube/inferops-dev.config --context kind-inferops-dev \
  get pods -n inferops-release -o wide
kubectl --kubeconfig .kube/inferops-dev.config --context kind-inferops-dev \
  describe pod -n inferops-release -l app.kubernetes.io/instance=inferops
kubectl --kubeconfig .kube/inferops-dev.config --context kind-inferops-dev \
  get events -n inferops-release --sort-by=.lastTimestamp
```

| Symptom | Reading |
|---|---|
| `Pending`, event `Insufficient cpu` or `Insufficient memory` | The single kind node cannot satisfy the request. This is capacity, not configuration |
| `Pending` with no scheduling event at all | Usually an unbound volume rather than capacity — see [storage](#model-cache-and-storage) |
| `ContainerCreating` for minutes | An image pull, or a volume mount that has not completed. `describe` names which |
| `ErrImageNeverPull` on the API container | **The expected state today**, for the committed [`real-values.yaml`](../../charts/inferops-llm/ci/real-values.yaml): it sets `api.image.pullPolicy: Never`, so the kubelet never attempts a pull and says the image is not present. An InferOps API image is built by `scripts/environment/api-image.sh` and loaded by the provider's own image path |
| `ErrImagePull` / `ImagePullBackOff` on the API container | The same absent image, seen through the chart's shipped `IfNotPresent` default instead. Same cause, same non-fix |
| `ErrImagePull` on the runtime or `verify-model` | The digest-pinned image is not in the node. `kind load docker-image <image> --name inferops-dev` puts one there — **name the cluster**, or kind loads into its own default `kind` cluster instead. Nothing here pulls implicitly |
| `OOMKilled` on `runtime` | The `3Gi` limit was reached, or the engine's own ceiling was. The two are different and the recovery differs |
| Container killed partway through the model load | Almost always the engine's memory ceiling rather than the pod's limit |

Distinguish the two ceilings before changing anything:

```text
# diagnose — read-only. What the engine believes it has, which on Windows and
# macOS is the virtual machine's allocation and not the host's installed memory.
docker info --format "{{.NCPU}} CPUs; {{.MemTotal}} bytes"
```

**Do not size the runtime from its private working set.** The weights are
memory-mapped; the measured private set on the reference host was 531 MiB against
a 2.167 GiB worst-case charge, and a limit derived from the first number kills
the process. [The prerequisites](../prerequisites.md#serving-and-model-prerequisites)
own those figures.

## Model cache and storage

The claim is a **prerequisite**, not part of the release. Terraform owns it, the
chart mounts it read-only, and the chart's own `pre-install,pre-upgrade`
acquisition hook fills it — the single sanctioned place where a release writes
into a prerequisite. That division is the whole of
[the ownership boundary](../architecture/resource-ownership.md), and most storage
symptoms here are one half of it acting without the other.

| | Owner | Created by | Removed by |
|---|---|---|---|
| The claim `inferops-model-cache` | `terraform` | `terraform apply` | `terraform destroy` |
| The bytes inside it | `helm`, through the acquisition hook | — | **Nothing in a release.** They outlive it |
| The mount | `helm` | `helm install` | `helm uninstall` |

```text
# diagnose — read-only
kubectl --kubeconfig .kube/inferops-dev.config --context kind-inferops-dev \
  get pvc -n inferops-release
kubectl --kubeconfig .kube/inferops-dev.config --context kind-inferops-dev \
  describe pvc inferops-model-cache -n inferops-release
```

| Symptom | Reading |
|---|---|
| The claim is `Pending` and nothing mounts it | **Correct, not a fault.** The local provisioner binds on first consumer, which is why `wait_until_bound` defaults to `false`; a Terraform apply that waited would time out on a healthy prerequisite |
| The claim is `Pending` and a pod is `Pending` on it | Now it matters. Read the claim's events: no storage class, or no capacity |
| `verify-model` exits 1 with `REFUSED: the mounted model cache holds no artifact for the declared revision` | **Less likely than it was**, because the acquisition hook now fills the claim as part of the install rather than leaving it to be filled out of band. There is no file at the revision-scoped path: either nothing filled the claim, or `model.revision` and `model.artifact.repository` do not match the bytes that are in it |
| `verify-model` exits 1 with `REFUSED: the mounted model artifact does not match the pinned byte count` | A file is there and is the wrong size — truncated, or a different artifact. The check compares the count **before** the SHA-256 read, so it fails fast and says why |
| `verify-model` fails inside `sha256sum -c -` | The bytes are the right length and the wrong content |
| `verify-model` reports `model artifact present; content not verified` | `model.integrity.verifyOnStart` is `none`. The file-exists check still ran; nothing else did |
| The pod mounts the claim but finds nothing | The claim is empty. It is filled by the release's own acquisition hook, and an empty claim is refused rather than served from |

The path inside the claim is derived, never typed:

```text
<claim>/<repository, separator written as two hyphens>/<revision>/<file>
Qwen--Qwen3-1.7B-GGUF/90862c4b9d2787eaed51d12237eafdfe7c5f6077/Qwen3-1.7B-Q8_0.gguf
```

There is deliberately no `subPath` value. A free-form one was the hole: the
revision was required, checked against nothing, and had no bearing on which bytes
the container read. It now decides the mount, so a release declaring one revision
cannot be handed the bytes of another — and a mount that resolves to nothing is
usually a `revision` or `artifact.repository` that does not match what is in the
claim, rather than a storage fault.

The artifact is 1,834,426,016 bytes — about 1.71 GiB. The claim defaults to `4Gi`
and refuses anything below `2Gi`, so it holds two pinned revisions rather than
one. **The serving replicas are readers and never writers**: the chart refuses
`model.cache.readOnly: false` at render time, so a serving pod cannot be the
thing that corrupted the cache.

## Slow or failed model load

This is the section most likely to be misread as a hang, and the numbers are the
reason.

**Measured model loads on the one host this project has evidence from**, all
outside Kubernetes:

| Run | Model load |
|---|---|
| [`V1-S2-005` first attempt](../proof/serving/v1-s2-005-baseline-raw-results-first-attempt.md) | 358,735 ms |
| [`V1-S2-005` recorded run](../proof/serving/v1-s2-005-baseline-raw-results.md) | 269,079 ms |
| [`V1-S2-007` cold arm](../proof/serving/v1-s2-007-pr1-cold-warm-start.md) | 133,515–215,672 ms |

Two budgets bound that load, they measure different things, and confusing them is
how a slow start gets "fixed" in the wrong place:

| Budget | Value | What it bounds |
|---|---:|---|
| `runtime.startupBudgetMs` | 300,000 ms | How long the **adapter** waits for the runtime |
| `runtime.probes.startup.budgetMs` | 600,000 ms | How long the **kubelet** waits for the container |

The kubelet's is twice the adapter's on purpose, and the chart refuses a startup
probe budget below the adapter's: a kubelet that gives up first restarts the
container into the same load and makes the adapter's budget unreachable. At a
10-second period that is a `failureThreshold` the template derives rather than a
number anyone typed, so the arithmetic cannot drift from the intent.

`runtime.lifecycle.progressDeadlineSeconds` is 900 rather than the 600-second
Kubernetes default, because a rollout still pulling an image has made no progress
the Deployment controller can see while the kubelet is waiting patiently. The
API's is 300 against a 60,000 ms startup budget.

| Symptom | Reading |
|---|---|
| The runtime pod is `Running`, not ready, and the startup probe is still failing | The model is loading. Wait. This is correct |
| The pod restarts at roughly ten minutes, repeatedly | The startup probe budget elapsed. On this evidence that is a statement about the host, not about the container |
| `progress deadline exceeded` on the Deployment | A deadline, and **not a statement about health**. The upgrade/rollback tooling refuses to read it as a detection for exactly this reason |
| `helm install --wait` fails while the pod is still loading | The install timeout is shorter than the load. Raise the Helm timeout, not the probe budget |

**Do not raise a probe budget to make a slow host look healthy.** The budget is a
published bound, and a deployment that needs a larger one has told you something
about the hardware.

## Probes

Three probes on the API, three on the runtime, and one deliberate disagreement
between two of them.

| Workload | Startup | Readiness | Liveness |
|---|---|---|---|
| `api` | `GET /health/live`, 5 s period, threshold 12 | `GET /health/ready`, 10 s, threshold 3 | `GET /health/live`, 10 s, threshold 3 |
| `runtime` | `GET /health`, 10 s period, threshold 60 | `GET /health`, 10 s, threshold 3 | **TCP** on the container port, 10 s, threshold 3 |

Both startup thresholds are derived from a budget and a period rather than
typed — 60,000 ms over 5 s and 600,000 ms over 10 s — so the arithmetic cannot
drift from the intent.

**The runtime's liveness is a TCP connect and never an HTTP GET**, and it is the
only probe in the release that is. `llama-server` answers `503` on `/health`
throughout the model load: that is correct readiness reporting and wrong liveness
reporting, and pointing liveness at it restarts a container that is doing exactly
what it should. Its startup probe asks the same `/health` — a startup probe is
allowed to fail for ten minutes, which is precisely what it is for. The chart
refuses `api.readinessPath` equal to `api.livenessPath` for the same underlying
reason.

Until a startup probe succeeds the kubelet runs neither of the other two. That is
what stops a slow start being read as a failure, and it is why a pod that looks
stuck at `0/1 Running` for four minutes has usually not been probed for liveness
at all yet.

| Symptom | Reading |
|---|---|
| `Startup probe failed: HTTP probe failed with statuscode: 503` on the runtime | The model is loading. Expected, up to sixty times |
| `Readiness probe failed: HTTP probe failed with statuscode: 503` on the runtime | The model is loading, or has been unloaded. Not a fault by itself |
| `Liveness probe failed: dial tcp ... connect: connection refused` on the runtime | The process is not listening. This *is* a fault — check the container's exit and the init container before it |
| The API is ready and the runtime is not | Expected during a load. The API binds its port as soon as the process is up and asks the adapter per request rather than at start-up |
| Readiness was true and is now false | Correct. A ready runtime that answers `503` again becomes not-ready rather than latching |
| A pod cycles `Running` → `CrashLoopBackOff` without ever becoming ready | Read the previous container's log, not the current one: `kubectl logs --previous` |

## Service, network, and the policy that is not enforced

Both Services are `ClusterIP`. V1 installs no ingress controller and no load
balancer, so **every access from outside the cluster is an explicit
port-forward** and there is nothing else to check.

| Service | Port |
|---|---:|
| `inferops-inferops-llm` (the API) | `8090` |
| `inferops-inferops-llm-runtime` | `8080` |

Both names are release-qualified, so a second release installed beside this one
renders a second pair rather than colliding with it.

```text
# diagnose — read-only
kubectl --kubeconfig .kube/inferops-dev.config --context kind-inferops-dev \
  get svc,endpointslice -n inferops-release
```

**A Service with no endpoints is the failure that looks like success.** `helm
install` reports a rollout, and a rollout Kubernetes reports as successful, a
Service selecting nothing, and a runtime that loaded no weights are
indistinguishable from outside until something asks for a completion. That is why
both certification workflows send a real request rather than reading a status.

| Symptom | Reading |
|---|---|
| The Service exists and its EndpointSlice is empty | No ready pod matches the selector. Go back to [probes](#probes); the Service is not the fault |
| `port-forward` exits immediately | No pod is ready to forward to. The certification script treats this as a failure and keeps its output in `.artifacts/kubernetes-certification/forward.log` |
| `port-forward` binds but the response never comes | The forward is served against **one selected endpoint** and never traverses the Service's virtual IP, so it cannot tell you anything about distribution — that is what [the multi-replica workflow](../serving/kubernetes-multi-replica-certification.md) exists for |
| The default loopback port `18090` is taken | Something else holds it, commonly the host-local composition on `8090`. The certification script moves to another loopback port rather than failing |

**Do not spend time on the NetworkPolicy on this cluster.** The chart renders six
policy objects, starting from a default deny on both ingress and egress, and on
`kindnetd` — the network plugin a `kind` cluster ships — **none of them was
enforced in the build tested**. Re-confirm that before relying on it if the node
image pin moves, because the answer is a property of the plugin build rather than
of the policy. That was measured on 2026-09-06 against the same plugin
implementation and is recorded in
[the enforcement result](../proof/security/v1-s3-004-pr1-network-policy-enforcement.md):
a policy denying all ingress and all egress was applied, and pod-to-pod traffic,
DNS resolution, and a direct query to CoreDNS all continued to work. The objects
are correct, they validate, and nothing applies them. So a connection that fails
here is a Service, a selector, a probe, or a port — it is not the policy.

The one thing the policy still costs you is at render time rather than at run
time: `telemetry.collection.collector` names a collector *only* so the policy can
admit it, and the chart refuses a collector named while
`security.networkPolicy.enabled` is false, refuses a namespace with no pod
selector, and refuses an empty selector — an empty `matchLabels` selects
everything, which is the opposite of what somebody emptying it intended.

## Reading the API's and the runtime's logs

```text
# diagnose — read-only
kubectl --kubeconfig .kube/inferops-dev.config --context kind-inferops-dev \
  logs -n inferops-release -l app.kubernetes.io/instance=inferops \
  --all-containers --tail=200
kubectl --kubeconfig .kube/inferops-dev.config --context kind-inferops-dev \
  logs -n inferops-release <pod> -c verify-model
```

`--all-containers` is the flag that matters: the init container's output is where
an integrity refusal is printed, and it is not in the runtime's log. A pod that
never started its main container has said everything it is going to say in
`verify-model`.

| Symptom | Reading |
|---|---|
| `logs` returns nothing at all | The container has not started. Its reason is in `describe pod`, not in a log that does not exist yet |
| `Error from server (BadRequest): container "runtime" in pod ... is waiting to start` | The same thing, said explicitly. Read the init container instead |
| The log ends mid-load with no error | The container was killed rather than exiting. `--previous` is the only copy that survives, and `describe pod` carries the reason |
| A restarted pod's log looks healthy | You are reading the new container. `--previous` is the one that failed |
| A `helm test` pod's log is the only failing one | The release installed and a Service did not answer. That is the hook doing its job |

Every script here collects the same set into `.artifacts/` on failure and leaves
the release in place for inspection rather than tearing down the evidence of its
own failure:

| Workflow | Directory |
|---|---|
| `smoke.sh` | `.artifacts/smoke/` |
| `helm-lifecycle.sh` | `.artifacts/helm-lifecycle/` |
| `kubernetes-certification.sh` | `.artifacts/kubernetes-certification/` |
| `helm-upgrade-rollback.sh` | `.artifacts/helm-upgrade-rollback/` |

`.artifacts/` is git-ignored. It is local host state, it can contain object
listings and log tails, and it must not be committed.

The API's own records are bounded and structured, and carry operational
identifiers and outcomes — never prompts, completions, runtime response bodies,
or credentials. That is what makes a tail of them safe to attach to a report, and
it is enforced at the sink rather than promised.

## Telemetry scrape

**Whether anything scrapes depends on one switch.** The chart renders a ConfigMap
holding a Prometheus scrape configuration and a set of recording rules, and —
when `telemetry.collection.collector.deploy` is on — a release-scoped collector
that reads it. With it off, nothing reads that ConfigMap and there is no collector
to restart. With it on, the collector is an ordinary pod: restart it like any
other, and note that its series live in an `emptyDir`, so a restart discards what
it collected. No durable store, dashboard, or alerting path is selected either
way, so a missing dashboard is not a fault.

What can be wrong is the configuration itself, and it is checkable without a
cluster:

```text
uv run --locked python -m tools.telemetry_collection charts/inferops-llm/ci/rendered
```

| Symptom | Reading |
|---|---|
| Two rendered fragments cannot be merged into one Prometheus configuration | Two releases installed beside each other. The `job_name` is release-qualified precisely so this does not happen — check that both releases really have different names |
| A target is permanently down on a pod that is up | Pod discovery yields one target per declared container port, and the second port answers nothing on the metrics path. The configuration keeps the port explicitly for this reason |
| A second release's series are attributed here | The `keep` filter selects on the release instance, escaped. An unescaped release name containing a dot would match more than itself |
| The collector finds no pods at all | Discovery selects on the three Kubernetes labels the chart always sets, **not** on `prometheus.io/*`. Those annotations are off by default and switching them on changes nothing about this configuration |
| The runtime job is absent | It renders under the `real` profile only. A `mock` release installs no runtime to scrape |

[The collection document](../telemetry/kubernetes-telemetry-collection.md) is the
authority on which labels the collector attaches and which it drops.

## The Helm release

One release, `inferops`, in `inferops-release`, from `charts/inferops-llm`.
**Three procedures install it and all three refuse to run over an existing
release**, so they interlock rather than collide.

```text
# diagnose — read-only
helm --kubeconfig .kube/inferops-dev.config --kube-context kind-inferops-dev \
  list --namespace inferops-release
helm --kubeconfig .kube/inferops-dev.config --kube-context kind-inferops-dev \
  history inferops --namespace inferops-release
```

| Symptom | Reading |
|---|---|
| A template refusal naming a value | The chart's own validation. It refuses before anything reaches a cluster, and each message names the value and why |
| `the release namespace must be prefixed 'inferops-' ... and it must already exist` | Terraform owns the namespace. Apply the prerequisites first; the lifecycle script stands in for them when they are absent and says so |
| `api.image.repository is required` | The blocker at the top of this page. There is no default that would resolve |
| A release stuck in `pending-install` or `pending-upgrade` | An interrupted Helm operation. Its history is the record; do not delete the release secret to "clean up" without reading it |
| `helm uninstall` succeeded and the namespace is still there | **Correct.** The namespace and the claim are prerequisites and outlive the release by design |
| A `helm test` pod that stays behind | The hook is deleted on success. One that survived is a failed test worth reading, not residue to sweep |

The chart never passes `--create-namespace`. That flag is one flag and it is the
default suggestion in most documentation, and it hands the namespace to Helm —
which means the release's uninstall deletes the prerequisite. It is refused in
the scripts, in `CONTRIBUTING`, and in the Terraform configuration.

## Terraform state and ownership

The prerequisite layer owns exactly two objects: the namespace `inferops-release`
and the claim `inferops-model-cache`. It owns no release object, creates no
cluster, and provisions nothing that costs money.

```text
scripts/environment/terraform-prerequisites.sh check    # no cluster needed
scripts/environment/terraform-prerequisites.sh plan
```

| Symptom | Reading |
|---|---|
| The wrapper refuses before Terraform runs | The reachable cluster is not this project's. Terraform's own validation can check a context *name*; it cannot check which cluster that context reaches, and that is the accident this wrapper exists to prevent |
| `terraform apply` hangs waiting for the claim | `wait_until_bound` was set to `true`. The claim binds on first consumer; waiting turns a correct prerequisite into a reported failure |
| A `-var` for the kubeconfig fails to parse on Windows | A Windows path contains backslashes and `-var` values are HCL, where `\8` is an invalid escape. The wrapper passes `TF_VAR_kubeconfig_path` and `TF_VAR_kube_context` as environment variables instead |
| The state file is gone | Two `terraform import` calls, and no data loss: the weights are in the claim, and the claim is a cluster object rather than a state entry |
| A plan shows the namespace being **replaced** | A namespace's name is its identity. This is not a rename — Terraform destroys the old namespace, cascading over everything in it |
| Two contributors disagree about what exists | There is no remote backend. Two clusters, two unrelated state files, and neither knows about the other. That is correct for one cluster per contributor and stops being correct the moment a shared cluster appears |

`apply` plans to a file and applies that file, so what is applied is what was
shown. The saved plan goes to `.artifacts/terraform/`: a plan embeds the prior
state, which makes it host state rather than evidence, and version control
ignores it.

## Upgrading and rolling back

[The upgrade and rollback procedure](helm-upgrade-rollback.md) owns this in full.
What belongs on a troubleshooting page is the three readings that are most often
made wrong.

| Observation | Wrong reading | Right reading |
|---|---|---|
| `helm rollback` returned zero | The release is back | A revision was recorded. Whether the rendered configuration went back, whether the workload followed, and whether a real completion comes back are three further questions |
| `progress deadline exceeded` during the failing upgrade | The fault was detected | A deadline elapsed. A timeout cannot distinguish a broken container from a model load this project has measured between 133,515 ms and 358,735 ms |
| The candidate pod never scheduled | The candidate failed | The candidate never ran. That is `INCONCLUSIVE`, exit `5`, and the remedy is capacity |

Detection is evidence: an init container that ran and exited non-zero, read off
the workload the fault was injected into. Only pods that are **not** ready are
inspected, because the pod still serving has a succeeded init container of the
same name.

If a run is interrupted mid-experiment, the release is left installed on purpose.
Recover with `helm uninstall`, in the [workload](#1-uninstall-the-workload) step
below — not with a `terraform destroy`, which is a wider cascade than the
situation calls for.

## Cleanup

Four operations, four different blast radii. **They are not a sequence and none
of them implies the next.** Pick the smallest one that reaches your problem.

One ordering constraint exists, and it is a refusal rather than a sequence: step 2
will not run while a release is still installed, so reaching it means doing step 1
first. Nothing else here requires anything else here.

### 1. Uninstall the workload

```text
# destructive, release-scoped
helm --kubeconfig .kube/inferops-dev.config --kube-context kind-inferops-dev \
  uninstall inferops --namespace inferops-release
```

Removes the release and nothing else. **The namespace, its metadata, and the
model cache survive** — that is the entire reason the claim is a prerequisite —
and asserting that they survived is one of the checks the lifecycle script makes.
Every certification workflow ends here.

For the smoke workload rather than the release:

```text
# destructive, namespace-scoped
scripts/environment/cluster-down.sh --workload
```

That deletes objects carrying `app.kubernetes.io/part-of=inferops` inside
`inferops-smoke`, then the namespace itself, and leaves the cluster running. It
is a scoped delete: no bare namespace deletion of anything unprefixed and no
all-namespaces sweep.

### 2. Remove the Terraform prerequisites

```text
# destructive, namespace-cascading. Reclaims ~1.71 GiB of model weights.
scripts/environment/terraform-prerequisites.sh destroy --confirm
```

**This is not the routine uninstall path.** Deleting the namespace cascades, so
anything still installed dies with it, and this is the only operation that
reclaims the model weights **without destroying the cluster** — which the next
release re-downloads. The cluster teardown in step 4 reclaims them as well, and
for a reason worth knowing: the accepted `kind` node declares no `extraMounts`
and the claim takes the cluster's default storage class, so the weights live
inside the node container rather than on the host.

The wrapper refuses two things outright, and both refusals are the point:

- **a destroy without `--confirm`**, because the cascade is wider than the command
  reads;
- **a destroy while a release is still installed**, because the cascade would take
  the release with it and leave Helm's own record claiming it exists. It refuses
  rather than uninstalling for you: removing somebody's release is not a decision
  a prerequisite teardown gets to take.

### 3. Delete the model cache

There is no separate command, and that is deliberate. In the cluster the weights
live inside the Terraform-owned claim, so reclaiming them **is** step 2 above.
Outside the cluster, the workspace cache is its own guarded operation on the
host-local path and reaches nothing in Kubernetes:

```text
uv run --locked python -m tools.model_acquisition clean            # prints what would go
uv run --locked python -m tools.model_acquisition clean --confirm  # destructive
```

That command refuses a target outside `.cache/inferops/models`, refuses a path
resolving outside the checkout, refuses a symbolic link in or above the managed
tree, and has no path override. It does not remove images, cluster volumes, or
anything in a cluster. **Do not delete either cache to fix a problem you have not
localised**: a miss costs a 1.71 GiB transfer.

### 4. Destroy the cluster

```text
# destructive, whole-cluster
scripts/environment/cluster-down.sh                     # cluster, kubeconfig, context
scripts/environment/cluster-down.sh --purge-node-image  # and the ~1 GB cached node image
```

Neither Terraform nor Helm may delete a cluster; the contributor's host owns it.
`cluster-down.sh` deletes the kind cluster named `inferops-dev`, the project
kubeconfig, and the context inside it, then **runs `verify-clean.sh` itself** —
so there is no need to run it again afterwards, and its output at the end of a
teardown is that check rather than a second one.

Two consequences this step does not announce and you should read before running
it:

- **It reclaims the model weights too**, for the reason in step 2 — they are
  inside the node container. Recreating the cluster costs the same 1.71 GiB the
  Terraform destroy costs.
- **A Terraform state file survives the cluster it described.** It will still
  claim a namespace and a claim exist, in a cluster that does not. That is the
  inverse of the "state file is gone" row above, and the recovery is the same
  kind of thing: the state is a record, not the resource.

Two things survive a full teardown by design, and they are stated in ADR 0001
(D6) rather than being oversights: the shared `kind` container network, because
other clusters may use it, and the cached node image, because reclaiming it is
opt-in and costs a re-download.

**Nothing here prunes the container engine, deletes all namespaces, removes a
context this project did not create, or touches the contributor's default
kubeconfig.** A cleanup that reached further than the thing it was cleaning up
would be the incident.

### If a cleanup reports it removed nothing

`verify-clean.sh` fails loudly when the engine is unreachable rather than
reporting "no clusters". A query that cannot run must never be mistaken for a
query that ran and found nothing: that reading turns a stopped engine into a
false all-clear, and the cleanup evidence depends on the answer. If it refuses,
start the engine and run it again — do not read the refusal as a clean teardown.

### If you interrupt a run

Nothing traps Ctrl-C, on purpose: being interrupted halfway through deleting
things is worse than being left with something to delete. An interrupted
`cluster-up.sh` or `proof.sh` can leave the cluster running, and the next
`cluster-up.sh` then refuses rather than silently reusing it.
`scripts/environment/cluster-down.sh` recovers from that in one step.

An interrupted release workflow leaves the release installed. That is step 1
above, and it is a smaller operation than it feels like at the time.

## What this page is evidence of

- `local-static` — every command in this repository that this change executed:
  the four offline checks, `helm lint`, `helm template`, and the repository's own
  formatting, linting, typing, and test lanes. Recorded in
  [the validation record](../proof/environment/v1-s3-009-pr1-validation.md).
- `local-real`, from prior authorised runs — the cluster lifecycle figures, the
  smoke result, the NetworkPolicy enforcement answer, and every model-load
  measurement quoted here. Each links to the record that produced it. None is a
  benchmark, and none may be published as one.
- `local-real`, from `V1-S3-011` on the `docker-desktop` provider — every
  `helm install`, `helm upgrade`, `helm rollback`, `helm uninstall`,
  `terraform apply`, `terraform destroy`, `kubectl port-forward`, probe, scrape,
  and completion this page describes has now been executed at least once there.
  Executing a command is not the same as provoking the symptom an entry
  describes, and this page does not claim otherwise.

[`tests/architecture/test_kubernetes_troubleshooting.py`](../../tests/architecture/test_kubernetes_troubleshooting.py)
holds this page to the repository: every tool command it prints must name a real
module and a real subcommand, every script it names must exist, every cluster
name, namespace, release name, port, budget, resource figure, byte count, and
digest must match the file that owns it, every relative link must resolve, no
fenced block may carry a credential-shaped flag or an unscoped `kubectl`, and the
never-installed limitation must stay stated. A guide whose commands have drifted
is worse than no guide, because it is read at three in the morning by someone who
trusts it.

## What this page does not establish

- **That the symptoms above were provoked.** The commands have been executed and
  the release has been installed, upgraded, broken on purpose, rolled back, had a
  pod deleted under it, and uninstalled — on `docker-desktop` only. Most
  individual symptom entries remain derived from the chart, the scripts, the
  descriptors, and the tooling rather than observed, and a reader may not read an
  executed release as an executed fault.
- **That the recoveries recover.** A described recovery and an executed one are
  different kinds of statement, and [the certification levels](../testing/certification.md)
  are where that distinction is defined.
- **Anything about Linux or macOS.** The executed evidence behind this page is
  from one Windows host, with a container desktop application providing the
  engine.
- **Anything about a network policy being enforced.** It is not, on this plugin,
  and the measurement that says so was taken on a cluster that is near to the
  accepted one rather than the accepted one itself.
- **Anything about a cluster with more than one node.** Every measurement and
  every capacity statement here is about a single-node `kind` cluster.
