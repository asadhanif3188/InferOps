# The `inferops-llm` chart

Status: **the chart is complete and nothing has installed it.** The probes, the
shutdown ordering, the release test, and the lifecycle script all exist; none of
them has been run against a cluster, because no InferOps API image is published
and no release can start without one. What is checked here is that the chart
renders, that what it renders is what the ownership inventory lets Helm own,
that the probe mapping is the one the accepted health records publish, and that
a release cannot quietly be the wrong one. Whether it installs, becomes ready,
and uninstalls without residue is answered by running
[`scripts/environment/helm-lifecycle.sh`](../../scripts/environment/helm-lifecycle.sh),
and it has not been run. Reading a chart does not answer it.

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
| `workload-service-account` | `ServiceAccount` | both |
| `runtime-configuration` | `ConfigMap` | both |
| `platform-api-deployment` | `Deployment` | both |
| `platform-api-service` | `Service`, `ClusterIP` | both |
| `serving-runtime-deployment` | `Deployment` | real only |
| `serving-runtime-service` | `Service`, `ClusterIP` | real only |

Three Helm-owned rows are deliberately absent, and the chart declares each in its
own `Chart.yaml` annotations so that the omission is a statement rather than an
oversight: `model-acquisition-job` (`V1-S3-003`), `workload-network-policy`
(`V1-S3-004`), and `telemetry-scrape-configuration` (`V1-S3-007`).

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
  model revision, an alias, a container path, a cache claim, or a secret
  reference at all;
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
way: **nothing in this project collects anything.** No scrape resource is
rendered, `telemetry-scrape-configuration` stays deferred to `V1-S3-007`, and
the annotations are here only because they are the one form of scrape
configuration that is a field on the workload rather than a resource beside it —
so a discovery mechanism that reads them can find these pods without this chart
deciding what that mechanism is. All three keys are refused in `commonAnnotations`
and in every per-object map whether or not they are switched on, because a
hand-written `prometheus.io/port` beside a derived one is the same duplicate-key
hazard the other guards exist for.

One caveat on the word *inert*, because it is a property of this environment and
not of the annotation. These three keys are the legacy Prometheus
auto-discovery convention, so a cluster-wide Prometheus configured that way —
deployed by anyone, not necessarily by this project — would begin scraping this
workload with no further InferOps-side configuration. `/metrics` is
unauthenticated and fingerprints the deployment, which
[`DR-01`](../../docs/security/deferred-risks.md) already accepts and records.
Switching these on is therefore a decision about who may reach the pod, not only
a decision about labels.

Every pod and container carries the six properties every workload manifest in
this repository carries — no service-account token, non-root with an explicit
uid, `RuntimeDefault` seccomp, no privilege escalation, a read-only root
filesystem, and every capability dropped. The service account is created and
**granted nothing**: no `Role` and no `RoleBinding` is rendered anywhere in this
chart. Least-privilege RBAC, admission policy, and the network policy are
`V1-S3-004`'s, and none of the above is enforced by a cluster — it is a property
of files, checked by
[`tests/architecture/test_helm_chart.py`](../../tests/architecture/test_helm_chart.py).

## Installing, upgrading, rolling back, removing

Read [the lifecycle document](../../docs/environment/helm-release-lifecycle.md)
before running anything. Three properties of it are worth stating here because
they are what makes the ownership boundary hold at run time rather than only on
paper:

- **The namespace has to exist first, and `--create-namespace` must never be
  passed.** It is one flag, it is the default suggestion in most documentation,
  and it silently gives one resource two owners. Terraform owns the namespace;
  `V1-S3-005` writes that Terraform, and until it does the lifecycle script
  creates the namespace itself and says so.
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
