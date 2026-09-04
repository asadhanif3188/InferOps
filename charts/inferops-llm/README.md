# The `inferops-llm` chart

Status: **the chart exists and nothing has installed it.** No InferOps API image
is published, no probe is configured, and no lifecycle test has been run against
a cluster. What is checked here is that the chart renders, that what it renders
is what the ownership inventory lets Helm own, and that a release cannot quietly
be the wrong one. Whether it installs, becomes ready, and uninstalls without
residue is `V1-S3-002-PR2`'s question, and reading a chart does not answer it.

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

Four more refusals hold the two profiles apart. Each is the same rule the
platform's own adapters enforce at start-up, moved to render time so that the
release is never built:

- a **real** release refuses a `mock-`labelled model identity;
- a **mock** release refuses anything that is not `mock-`labelled, and refuses a
  model revision, an alias, a container path, a cache claim, or a secret
  reference at all;
- `INFEROPS_SERVING_ADAPTER` is written in one template helper from `profile`
  and from nothing else, and `extraEnv` is **refused** rather than merged if it
  names any variable the chart derives — because a merge that lands last is
  exactly how a real release comes to publish `mock`;
- the serving capability is derived the same way and appears nowhere in the
  values contract, so a release cannot install one adapter and publish the
  other's capability.

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

## Telemetry, security, and what neither means

The chart configures the identity every emitted record carries — service version,
environment, capability, release, workload, owner, model revision, runtime image
digest — and supplies the pod name through the downward API. The tenant and cost
centre are **annotations rather than labels**, because a label is what a query
groups by and
[the redaction rules](../../docs/telemetry/redaction.md) keep a tenant identifier
out of exactly that. Nothing collects any of it: no scrape configuration is
rendered, and choosing one is `V1-S3-007`'s.

Every pod and container carries the six properties every workload manifest in
this repository carries — no service-account token, non-root with an explicit
uid, `RuntimeDefault` seccomp, no privilege escalation, a read-only root
filesystem, and every capability dropped. The service account is created and
**granted nothing**: no `Role` and no `RoleBinding` is rendered anywhere in this
chart. Least-privilege RBAC, admission policy, and the network policy are
`V1-S3-004`'s, and none of the above is enforced by a cluster — it is a property
of files, checked by
[`tests/architecture/test_helm_chart.py`](../../tests/architecture/test_helm_chart.py).

## No probes, deliberately

The feasibility trial recorded that the runtime's health endpoint returns `503`
while the model loads. That is correct readiness behaviour and wrong liveness
behaviour, so a liveness probe aimed at it restarts the pod mid-load and never
converges. Choosing the mapping is work with an argument attached, and it belongs
to `V1-S3-002-PR2`. A probe added here without that argument would reproduce a
defect the project has already paid to find, so the suite fails if one appears.

## Checking it

See the Helm chart section of [CONTRIBUTING](../../CONTRIBUTING.md) for the exact
commands, which values file each takes, and why a lint with no values file is
expected to fail.
