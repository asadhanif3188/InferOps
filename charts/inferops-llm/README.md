# The `inferops-llm` chart

Status: **the chart is complete and has been installed.** `V1-S3-011` ran
[`scripts/environment/helm-lifecycle.sh`](../../scripts/environment/helm-lifecycle.sh)
on the `docker-desktop` reference provider with an API image built on the host and
loaded into the cluster: the release installed, became ready, served a real
completion through its own Service, passed `helm test`, took a controlled upgrade,
failed on an injected fault, rolled back, and uninstalled without residue —
[the paved road](../../docs/proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md)
and [the upgrade and rollback record](../../docs/proof/environment/v1-s3-011-pr2-upgrade-rollback.md).
That is one provider, one Windows host, CPU, and one replica of each tier; the
multi-replica profile was refused at the capacity gate there, and nothing has been
re-certified on `kind` since the ownership realignment. No InferOps API image is
published to a registry, so a run on another host must build and load one.

What is checked without a cluster is that the chart renders, that what it renders is
what the ownership inventory lets Helm own, that the probe mapping is the one the
accepted health records publish, and that a release cannot quietly be the wrong one.
Reading a chart still does not answer whether it installs; the record above does.

It packages two workloads as one release: the platform API, and — under the real
profile — the `llama.cpp` server
[ADR 0002](../../docs/architecture/decisions/ADR-0002-model-and-serving-runtime.md)
selected.

## What it installs, and what it refuses to

The [ownership inventory](../../docs/architecture/resource-ownership.md) decides
this, not the chart. Terraform owns what outlives a release; Helm owns the
release; neither may create what the other owns.

| Rendered | Kind | Profile |
|---|---|---|
| `workload-service-account` | `ServiceAccount`, one per workload | both |
| `workload-network-policy` | `NetworkPolicy`, four of them | both |
| `runtime-configuration` | `ConfigMap` | both |
| `platform-api-deployment` | `Deployment` | both |
| `platform-api-service` | `Service`, `ClusterIP` | both |
| `serving-runtime-deployment` | `Deployment` | real only |
| `serving-runtime-service` | `Service`, `ClusterIP` | real only |
| `telemetry-scrape-configuration` | `ConfigMap` | both |
| `workload-disruption-budget` | `PodDisruptionBudget`, one for each tier of two or more replicas | both for the API tier, real only for the runtime tier |

One Helm-owned row is deliberately absent, and the chart declares it in its own
`Chart.yaml` annotations so that the omission is a statement rather than an
oversight: `model-acquisition-job`. `workload-network-policy` was one of three
until `V1-S3-004` rendered it, and `telemetry-scrape-configuration` was one of two
until `V1-S3-007` rendered this one.

`model-acquisition-job` is the one to read twice, because `V1-S3-003` implemented
the rest of the model cache around it and left it where it was. It needs a
container image nobody has published and a 1.71 GiB transfer this repository has
never made from inside a cluster, so it arrives with the Kubernetes serving
integration. Everything about the claim that does not require filling it — the
revision-scoped mount, the read-only reference, and the integrity check below —
is implemented and rendered.

One more object appears in `helm template` output and is **not** in that table:
the `helm test` pod under [`templates/tests/`](templates/tests/). It is a hook.
Helm creates it when a test is run and deletes it when the test succeeds, so it
is not part of the installed release and it is not a row the inventory assigns
to anybody. The test suite tells the two apart by reading the `helm.sh/hook`
annotation rather than by counting objects.

Nothing Terraform owns is rendered. In particular **no `Namespace`**, and
**`--create-namespace` must never be passed**: it is one flag, it is the default
suggestion in most documentation, and it silently gives one resource two owners.
The namespace has to exist first, and its name has to begin `inferops-`, which
the chart refuses at render time.

The model cache is a `PersistentVolumeClaim` Terraform provisions. This chart
mounts it read only and never creates it. Referencing is not owning.

**It is mounted at a revision-scoped subdirectory, not at its root.** The chart
derives `<repository>/<revision>` from `model.artifact.repository` and
`model.revision` — the same layout the workspace cache already uses — and no
values path reaches it. A release declaring one revision therefore cannot see
another revision's directory at all, which is what makes the declared revision
decide which bytes are read rather than merely being recorded beside them.
[The storage document](../../docs/environment/model-cache-storage.md) has the
layout, the integrity modes, and what each teardown operation does to the bytes.

## `profile` has no default, and that is the point

`profile` is `mock` or `real`. It must be stated. An omission renders nothing.

```sh
helm template inferops charts/inferops-llm --namespace inferops-platform
# Error: profile is required and has no default. ...
```

That refusal is
[rule 5 of the mock and real boundary](../../docs/serving/mock-and-real-boundary.md)
made structural: *a mock may never be the default in the mandatory path*. A chart
whose default were `mock` would hand out one per `helm install` rather than one
per test, and the difference is invisible from outside the pod.

More refusals hold the two profiles apart. The first two are the same rules the
platform's own adapters enforce at start-up, moved to render time so that the
release is never built:

- a **real** release refuses a `mock-`labelled model identity;
- a **mock** release refuses anything that is not `mock-`labelled, and refuses a
  model revision, an alias, an upstream artifact, a cache claim, or a secret
  reference at all — and has to state `model.integrity.verifyOnStart: none`
  rather than inherit the shipped `sha256`, because a mock mounts no artifact
  and a render describing a verification that could not have happened is the
  same defect as a mock transcript naming a real model;
- `INFEROPS_SERVING_ADAPTER` is written in one template helper from `profile`
  and from nothing else, and the serving capability is derived the same way and
  appears nowhere in the values contract, so a release cannot install one adapter
  and publish the other's capability;
- **every free-form map that reaches a rendered object is refused rather than
  merged if it collides with something the chart derives.** That is `extraEnv`,
  `secretRefs`, `commonLabels`, `commonAnnotations`, and the three per-object
  annotation maps. A merge that lands last is exactly how a real release comes to
  publish `mock` — and the label matters as much as the variable, because
  appending `inferops.io/profile` to a mapping that already has it produces the
  key twice and every parser keeps the appended one. The same refusal protects
  `app.kubernetes.io/part-of` and `inferops.io/lifecycle`, which are what a
  scoped teardown selects on: a release able to rewrite those could exempt itself
  from the sweep meant to remove it, or present itself as a Terraform-owned
  prerequisite. `INFEROPS_POD_NAME` is refused too, because the kubelet resolves
  a duplicate environment name last-one-wins, which would turn an identity the
  API server supplies into one an operator typed.

A map that collides with nothing is merged as written; `commonLabels.team` and an
`example.com/…` annotation both render.

## Configuring it

Every value is documented in [`values.yaml`](values.yaml) and constrained by
[`values.schema.json`](values.schema.json), which Helm applies to every
`install`, `upgrade`, `template`, and `lint`. Three constraints are worth naming
here because they are refusals rather than shapes:

- **Images are digests.** `repository` and `digest` are separate fields and the
  digest must be `sha256:` and sixty-four hexadecimal characters. A tag is
  refused, wherever it is written.
- **Resources state both halves.** A workload with no request is scheduled
  anywhere; a workload with no limit is bounded by nothing.
- **No field holds a secret.** `security.secretRefs` names a Kubernetes Secret
  and a key, and the schema forbids any other member. A chart that *could* carry
  a literal would carry it into the rendered manifest, the release history, and
  whatever reads either.

### The API tier's replicas and rollout

`api.replicaCount` is the number of API pods, and `api.rollout` holds the two bounds of
the API Deployment's rolling update, in whole pods:

| Value | Default | Meaning |
|---|---|---|
| `api.replicaCount` | `1` | API pods the Deployment runs |
| `api.rollout.maxUnavailable` | `0` | API pods a rollout may take away before their replacements are available |
| `api.rollout.maxSurge` | `1` | API pods a rollout may add above `replicaCount` |

The template states the strategy on the API Deployment. Until chart `0.4.0` it stated
none, and the Kubernetes default applied: 25% for both bounds, with `maxUnavailable`
rounded down and `maxSurge` rounded up. At one to three replicas that resolves to 0
and 1, the bounds this chart now states. From four replicas it resolves to other
numbers. So at the replica counts the two committed bindings state, one and two, the
stated bounds equal what the default resolved to, and chart `0.4.0` changes what the
Deployment says and not the bounds in effect. Whole pods keep the bounds fixed when
the count changes. The rounding rule is the one Kubernetes documents; it was not
observed on a cluster. The schema takes whole pods only and refuses a percentage. The
template refuses two zeros, which Kubernetes refuses.

Under the default bounds Kubernetes documents that a rollout adds one API pod and
removes an existing one only after the new one is available. No rollout was run. Such
a rollout needs room for one more API pod than `replicaCount`.
At the chart's API requests, 100m CPU and 128Mi each, two replicas request 200m and
256Mi, and a rollout requests 300m and 384Mi while it runs. These are sums of the
chart's values. No capacity check was run for them.

In a generated release neither value is written by hand. The EnvironmentBinding owns
the replica count, the platform defaults own the two bounds, and the
[renderer](../../docs/domain/helm-values-renderer.md) refuses a hand-written values
file that sets any of the three.

The schema is what refuses a bad bound. With `--skip-schema-validation` the template
turns a percentage into 0 and gives no refusal, as measured with `helm template`.

**What this is not.** A replica count and a rollout policy are configuration. Chart
`0.4.0` has not been installed. One run of chart `0.5.0` on 2026-10-08 had two API pods
Ready on one node, after each was restarted once by its startup probe:
[the record](../../docs/proof/environment/v2-s4-002-pr2-validation.md). Nothing here
establishes that a
rollout leaves a caller served, or what a caller observes when an API pod is deleted
or a node is lost. A rollout policy bounds a template change. It does not bound a pod
deletion or an eviction. Since chart `0.6.0` a tier of two or more replicas renders a
PodDisruptionBudget, which bounds an eviction and not a deletion:
[the disruption budgets](#the-disruption-budgets). The runtime Deployment's strategy is
the next section's.

### The runtime tier's replicas and rollout

`runtime.replicaCount` is the number of runtime pods under the `real` profile, and
`runtime.rollout` holds the two bounds of the runtime Deployment's rolling update, in
whole pods:

| Value | Default | Meaning |
|---|---|---|
| `runtime.replicaCount` | `1` | Runtime pods the Deployment runs. Each loads the model |
| `runtime.rollout.maxUnavailable` | `1` | Runtime pods a rollout may take away before their replacements are available |
| `runtime.rollout.maxSurge` | `0` | Runtime pods a rollout may add above `replicaCount` |

The bounds are the opposite of the API tier's, on purpose. An API pod is small. A
runtime pod reserves the CPU and memory of a loaded model, so a surge pod is one more
loaded model than the tier runs. Under `maxSurge: 0` Kubernetes documents that a rollout
adds none. The cost it documents is that a rollout may run one runtime pod fewer than
`replicaCount` until each replacement is Ready, and a replacement loads the model before
it is Ready. At one replica, which is the chart's default, that is no Ready runtime pod
for the whole of that load, and a replacement that never becomes Ready leaves none. At
two replicas it is one. No rollout of a runtime pod was run under these bounds.

**This changes what the V1 procedures describe.** The
[upgrade and rollback experiment](../../docs/environment/helm-upgrade-rollback.md), the
[unready-model recovery](../../docs/serving/unready-model-recovery.md), and the
[operator runbook](../../docs/environment/operator-runbook.md) were recorded with chart
`0.3.0` and one runtime replica. Under the bounds that applied then, a failing candidate
was started beside the serving pod. Under the default bounds of chart `0.5.0` the serving
pod may be removed first. Each of those pages carries a dated note. No procedure was run
again.

Until chart `0.5.0` the template stated no strategy for the runtime, and the Kubernetes
default applied: 25% for both bounds, which resolves to 0 unavailable and 1 surge at one
to three replicas. So chart `0.5.0` changes the bounds in effect at the replica counts
the repository renders, and not only what the Deployment says: `0.4.0` added a runtime
pod first, and `0.5.0` removes one first. The rounding rule is the one Kubernetes
documents; it was not observed on a cluster. The schema takes whole pods only and
refuses a percentage, and the template refuses two zeros, under either profile.

The render holds one pod template for the runtime, whatever the replica count, and
Kubernetes documents that a Deployment creates each replica from it. The template names
the pinned image, mounts the claim read only at the revision directory, verifies the
pinned artifact in an init container before `llama-server` starts, and states startup,
readiness, and liveness probes. The runtime Service selects pods by the Deployment's
selector labels and names no replica. Kubernetes documents that a Service does not route
to a pod that is not Ready. That is read from the render and from the Kubernetes
documentation. It was not observed for two runtime pods when this was written. On
2026-10-08 one run on `docker-desktop` observed two runtime pods that each mounted the
claim read only, verified the artifact, and became Ready:
[the observation](../../docs/environment/runtime-model-cache-observation.md). That run
did not observe which pod a Service routes to.

The template states no node selector, no affinity, and no topology spread, so both
runtime pods may be placed on one node. The model cache claim the prerequisite layer
creates is `ReadWriteOnce`. Kubernetes documents that such a claim can be mounted by
several pods on one node and not by pods on two nodes. The acquisition hook mounts the
same claim on every install and upgrade.

At the chart's runtime requests, 1 CPU and 2Gi each, two replicas request 2 CPU and 4Gi.
At the limits a reference contract declares, 6 CPU and 3Gi each, two replicas may use 12
CPU and 6Gi. Each runtime pod runs `runtime.threads` inference threads, six by default,
so two pods run twelve. These are sums of values. This change ran no capacity check for
them, and nothing in the chart refuses an environment that cannot schedule two runtime
pods. Since `V2-S4-003-PR1` a check outside the chart compares stated figures:
[the capacity preflight](../../docs/environment/capacity-preflight.md) reads one cluster
before an install, and refuses it when the pod count, the processor requests, or the
memory limits of this chart's pods do not fit in what its one node allocates. It counts
one surge pod of the API, one of the collector, none of the runtime, the hook pod, the
test pod, and a reserve. It does not establish that a pod is scheduled. One
earlier record bears on it: the V1
[multi-replica certification](../../docs/serving/kubernetes-multi-replica-certification.md)
ran a capacity gate for two API replicas and two runtime replicas on `docker-desktop`,
and the gate refused that host. The startup budget and the rollout deadline were set
from loads of one runtime. Two concurrent model loads were not timed.

In a generated release none of the three values is written by hand. The WorkloadContract
owns the replica count: its `spec.scaling` range must be one number, because the chart
has no autoscaler. The platform defaults own the two bounds. The
[renderer](../../docs/domain/helm-values-renderer.md) refuses a hand-written values file
that sets any of the three.

**What this is not.** One run on `docker-desktop` on 2026-10-08 installed chart `0.5.0`
with two runtime replicas. Both runtime pods started on one node and mounted the one
model cache claim:
[the record of that run](../../docs/proof/environment/v2-s4-002-pr2-validation.md). It is
one run on one provider and one storage class. Nothing here establishes that two
runtime pods can be placed on two nodes, that a rollout leaves a caller served, or what
a caller observes when a runtime pod is deleted or a node is lost. The chart's schema does not compare a request with a
limit, so a values file given to Helm directly can state a runtime limit below the
runtime request. Kubernetes documents that it refuses such a pod; that was not observed.
The renderer refuses a contract that asks for it.

### The disruption budgets

Since chart `0.6.0` the chart renders one PodDisruptionBudget for a tier that declares
two or more replicas:

| Tier | Rendered when | The budget |
|---|---|---|
| Platform API | `api.replicaCount` is 2 or more | `minAvailable: 1`, over the pods the API Deployment selects |
| Serving runtime | `profile` is `real` and `runtime.replicaCount` is 2 or more | `minAvailable: 1`, over the pods the runtime Deployment selects |

No value sets `minAvailable`, and no value turns a budget off: the values contract
holds no member for it, and the schema refuses one. At one replica, which is the default
of both tiers, the chart renders no budget. A budget of one available pod over one pod
would refuse every eviction of it, so a tier of one replica is not bounded for an
eviction.

**A budget bounds a voluntary eviction, and nothing else.** Kubernetes documents that the
eviction API, which `kubectl drain` uses, refuses an eviction that would leave fewer
available pods than the budget states. Kubernetes also documents what a budget does not
bound:

- a direct pod deletion, which does not go through the eviction API;
- a Deployment's rolling update, whose bounds are `api.rollout` and `runtime.rollout`;
- a node that fails, or a pod that the kubelet evicts under node pressure.

**A budget can make a drain wait.** A drain marks the node unschedulable, so a
replacement pod must become Ready on another node before the budget admits the second
eviction. A cluster with one node has no other node. The two runtime pods also mount one
`ReadWriteOnce` claim, which Kubernetes documents is not mounted by pods on two nodes. In
both cases a drain evicts one pod of the tier and then does not end by itself. Helm
removes a tier's budget on an upgrade to one replica. A release path that does not
remove an object that leaves the render keeps it, over one pod, until a person deletes
it.

**What this is not.** A budget is configuration. No release that renders one was
installed, and no eviction was requested. A budget is not evidence that a caller is
served when a pod is deleted: a pod deletion is tested by deleting a pod under a caller.
[The disruption budgets page](../../docs/environment/disruption-budgets.md) states the
rule, the limits, and what follows for a release that a controller reconciles from Git.

Two committed values files under [`ci/`](ci/) are the render fixtures. Both carry
a **placeholder API image digest** that resolves to no image, for the reason
[`ci/real-values.yaml`](ci/real-values.yaml) states: no InferOps image is
published and no `Dockerfile` is committed anywhere in this repository.

## Probes, and the one that is not an HTTP GET

The mapping is not invented here. Both halves of it are already published in
accepted records, and the chart is compared against them by
[`tests/architecture/test_helm_chart.py`](../../tests/architecture/test_helm_chart.py):

| Container | Startup | Readiness | Liveness |
|---|---|---|---|
| API | `GET /health/live` | `GET /health/ready` | `GET /health/live` |
| Runtime | `GET /health` | `GET /health` | **TCP connect** |

The runtime's liveness probe is a TCP connect, and that is the one line in this
chart that would be wrong if somebody made it consistent. `llama-server` answers
`/health` with `503` for the whole of a model load. That is correct readiness
behaviour and fatal liveness behaviour: a liveness probe aimed at it fails
throughout the load, restarts the pod, and restarts it into the same load. The
[cold and warm start observation](../../docs/proof/serving/v1-s2-007-pr1-cold-warm-start.md)
recorded **2,753 samples across six starts** in which a healthy process was
loading a model and an HTTP liveness probe would have been failing, and
[`runtime-profile.local.v1.json`](../../docs/serving/runtime-profile.local.v1.json)
publishes `health.liveness.kind` as `tcp` for that reason.

The socket is accepted several seconds before the model is loaded — the same
observation never once caught the runtime before its port was bound — so the TCP
probe cannot serve as the startup gate either. The startup gate is the HTTP one,
and until it passes the kubelet runs neither of the other two.

**The startup budget is 600,000 ms and not the 300,000 ms `startupBudgetMs`
publishes.** The measured loads do not fit in the smaller number: 133,515 ms to
215,906 ms across the six starts in that observation, and 358,735 ms cold and
284,406 ms warm on the same host in
[the V1-S2-005 first attempt](../../docs/proof/serving/v1-s2-005-baseline-raw-results-first-attempt.md);
[its later recorded run](../../docs/proof/serving/v1-s2-005-baseline-raw-results.md)
loaded in 269,079 ms. A startup probe budgeted at 300,000 ms would have killed
the container mid-load in the slowest of those. The two numbers measure different things — one is how
long the adapter waits for the runtime, the other how long the kubelet waits for
the container — and the chart refuses a startup budget below the adapter's,
because a kubelet that gives up first makes the adapter's budget unreachable.
Neither figure is a performance claim; both are quoted only as the range a
probe budget has to cover on one host.

## Stopping

Shutdown follows the order
[`src/inferops/api/lifecycle.py`](../../src/inferops/api/lifecycle.py) fixes:
readiness goes false, what is in flight drains, the process exits. In front of
it is a `preStop` pause, because endpoint removal is asynchronous — the kubelet
sends `SIGTERM` and the `EndpointSlice` update races it, so without a pause a
pod can be handed work after it has stopped accepting any.

The pause is a `sleep` action rather than an `exec`. An `exec` needs a shell
inside the image, and no InferOps image exists to be asked whether it has one.
Kubernetes has accepted a sleep action natively since 1.30 and this chart's
floor is 1.34.

The grace period has to cover the pause and the drain together, and the chart
refuses a values file where it does not: a period that expires mid-drain ends in
`SIGKILL`, and a drain that ends in `SIGKILL` was decoration. The runtime does
not drain — `llama-server` is stopped rather than asked to finish, and stopping
it was measured at 1,234 ms to 1,672 ms — so it only has to outlast its own
pause.

There is a third timeout, and it is the one with a default that quietly
disagrees with the other two. `progressDeadlineSeconds` defaults to **600
seconds**, and the runtime's startup budget is 600 seconds as well. They are not
the same clock: the kubelet can still be patiently waiting for a container the
Deployment controller has already marked `ProgressDeadlineExceeded`, and an
`install --wait` on that rollout reports a failure that is a slow model load.
The chart sets it explicitly on both workloads and refuses a value inside the
startup budget.

## Telemetry, security, and what neither means

The chart configures the identity every emitted record carries — service version,
environment, capability, release, workload, owner, model revision, runtime image
digest — and supplies the pod name through the downward API. **That is the API
container only.** The runtime container receives no InferOps environment and no
secret reference at all: `llama.cpp` reads none, its configuration is its argument
vector, and giving it variables it ignores would suggest it emitted something it
does not. `security.secretRefs` therefore reaches the API and nothing else, which
is a limit of this chart rather than of the values contract. The tenant and cost
centre are **annotations rather than labels**, because a label is what a query
groups by and
[the redaction rules](../../docs/telemetry/redaction.md) keep a tenant identifier
out of exactly that.

`telemetry.scrapeAnnotations` adds `prometheus.io/scrape`, `prometheus.io/port`,
and `prometheus.io/path` to every pod. It is off by default and inert either
way: **nothing in this project collects anything.** The annotations are here
because they are the one form of scrape configuration that is a field on the
workload rather than a resource beside it, so a cluster-wide collector using that
convention can find these pods without this chart deciding what that collector is.
All three keys are refused in `commonAnnotations` and in every per-object map
whether or not they are switched on, because a hand-written `prometheus.io/port`
beside a derived one is the same duplicate-key hazard the other guards exist for.

`telemetry.collection` is the `telemetry-scrape-configuration` row, and it is
**on** by default while the annotations above are off. The difference is the blast
radius: an annotation on a pod is read by any cluster-wide collector using that
convention, so switching it on changes what something outside this release does,
while a ConfigMap is read by nothing unless somebody mounts it. What it holds is a
Prometheus scrape configuration for the API and, under the real profile, the
runtime, plus recording rules mapping the native runtime series and publishing the
absence of the signals nothing emits. **`telemetry.collection.collector.deploy`
installs the collector that reads it — off by default, on under the real profile.
With it off, nothing reads this ConfigMap and nothing scrapes either endpoint** —
[the collection document](../../docs/telemetry/kubernetes-telemetry-collection.md)
states what it finds and what each label costs. Discovery selects on the
Kubernetes labels this chart always sets rather than on the annotations above, so
it does not depend on a switch that is off by default.

`telemetry.collection.collector` names the collector the release's network policy
would let in: a namespace and a pod selector, required together, rendering one
ingress rule per workload policy. Both empty is the default and leaves the
default-deny whole, because with `deploy` off there is no collector to name; with it
on, the chart fills both selectors in from the collector it just rendered.

One caveat on the word *inert*, because it is a property of this environment and
not of the annotation. These three keys are the legacy Prometheus
auto-discovery convention, so a cluster-wide Prometheus configured that way —
deployed by anyone, not necessarily by this project — would begin scraping this
workload with no further InferOps-side configuration. `/metrics` is
unauthenticated and fingerprints the deployment, which
[`DR-01`](../../docs/security/deferred-risks.md) already accepts and records.
Switching these on is therefore a decision about who may reach the pod, not only
a decision about labels.

## The model artifact is verified before the runtime loads it

Under the real profile the serving pod runs an init container before
`llama-server`. It reads the mounted artifact and compares it against the byte
count and the SHA-256 that
[the model source record](../../docs/serving/model-source.v1.json) pins, and a
mismatch fails the pod rather than starting a runtime on it.

It runs on **every pod start**, which is what makes it a restart property rather
than an install-time one: a pod that comes back finds the artifact the previous
one left behind and re-establishes that it is the artifact this release declared
before anything serves from it. A verification performed once at install time
would say nothing about the pod that replaced the one it ran in.

`model.integrity.verifyOnStart` is `sha256` by default, and `size` and `none` are
explicit downgrades. All three keep the revision scoping, because that is the
mount rather than a check, and all three still refuse an absent artifact. The
costs and the limits of each are in
[the storage document](../../docs/environment/model-cache-storage.md).

The init container is **BusyBox**, for its `sha256sum` and its `wc`. It is the
same pin `helm test` already uses and the same one four committed manifests under
`deploy/` carry, so it is not a new dependency; a test compares all of them. It
is given no environment at all — everything it compares against is rendered into
its script from a pinned value — and it carries the same security context and the
same read-only mount as the runtime beside it. **It has never been scheduled.**

Every pod and container carries the six properties every workload manifest in
this repository carries — no service-account token, non-root with an explicit
uid, `RuntimeDefault` seccomp, no privilege escalation, a read-only root
filesystem, and every capability dropped.

`V1-S3-004` added three things beside them.

**One identity per workload.** The API and the serving runtime each get a
`ServiceAccount` of their own, and each is **granted nothing**: no `Role`, no
`ClusterRole`, and no binding of either is rendered anywhere in this chart, and no
pod mounts a token. Two names granted nothing are two names granted nothing, so
this establishes no privilege difference today. What it establishes is that the
first `RoleBinding` somebody writes for one workload cannot reach the other, which
is what a shared account produces the first time anything is granted at all.

**A network policy that starts from a denial.** Four objects: a deny of both
ingress and egress over every pod this release installs, and one rule each for the
API, the runtime, and the `helm test` pod. The API is reachable on its own port
from this release's own pods and may resolve DNS and reach the runtime; the
runtime is reachable on its own port and may reach **nothing** — `llama-server`
reads a mounted file and answers a socket, and an egress allowance it never uses
is a hole with no purpose. The deny selects this release's pods rather than the
namespace, because a `podSelector` of `{}` would also deny for Terraform-owned
prerequisites this chart does not own.

**A validator that refuses a render which dropped any of it.**
[`python -m tools.workload_policy`](../../docs/security/workload-policy.md) reads a
bundle of manifests and refuses one whose workloads have lost an identity, an
explicit resource envelope, a digest pin, a default-deny, or any of the six pod and
container properties — and nine committed fixtures, each dropping one control,
establish that it refuses rather than only passing.

**None of it is enforced by a cluster.** All three are properties of files, checked
by [`tests/architecture/test_helm_chart.py`](../../tests/architecture/test_helm_chart.py)
and [`tests/security/test_workload_policy.py`](../../tests/security/test_workload_policy.py).
No cluster has installed this chart.

The network policy is worse than unproven and the difference is worth reading. It is
applied by the cluster's network plugin rather than by the object, and
[an executed experiment](../../docs/proof/security/v1-s3-004-pr1-network-policy-enforcement.md)
established that `kindnetd` — the plugin the accepted local cluster ships — **does
not apply one**. A total deny was installed and pod-to-pod traffic, DNS, and a direct
CoreDNS query all kept working. So these four objects are a correct policy that
nothing applies, where this project runs. `DR-04` carries that and `EX-05` records
it. Admission control still does not exist either, which is what `DR-05` turns on.

## Installing, upgrading, rolling back, removing

Read [the lifecycle document](../../docs/environment/helm-release-lifecycle.md)
before running anything. Three properties of it are worth stating here because
they are what makes the ownership boundary hold at run time rather than only on
paper:

- **The namespace has to exist first, and `--create-namespace` must never be
  passed.** It is one flag, it is the default suggestion in most documentation,
  and it silently gives one resource two owners. Terraform owns the namespace,
  and that Terraform now exists in
  [the prerequisite layer](../../docs/environment/platform-prerequisites.md) --
  applying it first is the ordered path. Nothing has applied it, so where the
  namespace is absent the lifecycle script still creates it itself and says it is
  standing in.
- **`helm uninstall` is the whole of removal.** It removes this release and
  nothing else. The namespace and the model cache claim survive it by design —
  that is what makes them prerequisites — and the lifecycle script asserts both
  that no release object is left and that both prerequisites are still there.
- **Rollback works because nothing that changes between revisions is
  immutable.** A `Deployment`'s selector cannot be changed after creation, so
  the selector is drawn from the release name, the chart name, and the component
  and from nothing else — not the profile, not the chart version, not
  `commonLabels`. The `ConfigMap` name is stable for the same reason, and the
  configuration checksum rides on the pod template so that a rollback rolls the
  pods rather than leaving them on the configuration they were rolled back from.

`helm test` runs the hook pod described above. It is the one check that
distinguishes a rollout Kubernetes called successful from a release that
actually answers: a `Service` selecting nothing looks identical to a working one
until something asks.

The hook pod runs **BusyBox**, for its `wget`, pinned by digest like everything
else here. It is the only image in this chart that is neither the InferOps API
nor the runtime, and it is **not a new dependency**: it is the same
`busybox:1.37.0` index digest that
[`deploy/smoke/hello-world.yaml`](../../deploy/smoke/hello-world.yaml),
[`deploy/smoke/verify-job.yaml`](../../deploy/smoke/verify-job.yaml), and the two
feasibility manifests already pin. A test compares the chart's copy against
theirs, because two copies of one pin are one pin only until somebody edits one
of them.

## Checking it

See the Helm chart section of [CONTRIBUTING](../../CONTRIBUTING.md) for the exact
commands, which values file each takes, and why a lint with no values file is
expected to fail.
