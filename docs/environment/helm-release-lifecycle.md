# Installing, upgrading, rolling back, and removing the release

Status: **executed on the `docker-desktop` provider.**
[`scripts/environment/helm-lifecycle.sh`](../../scripts/environment/helm-lifecycle.sh)
exists, its safety properties are asserted by
[`tests/architecture/test_cluster_lifecycle_safety.py`](../../tests/architecture/test_cluster_lifecycle_safety.py),
and `V1-S3-011` put the chart through the whole of this procedure against the
Kubernetes cluster Docker Desktop provides: install, readiness, the release's own
in-cluster connection test, a real completion, upgrade, rollback, and uninstall
with no residue carrying the release's instance label.

The blocker this document used to state is gone. It was one line — **no InferOps
API image is published** — and
[`deploy/api/Dockerfile`](../../deploy/api/Dockerfile) now exists, the image is
built on the host and loaded into the selected cluster by that provider's own
image path, and a release whose API image resolves becomes ready.

What may be cited, and what may not. The records are
[the reference-provider paved road](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md),
[the upgrade and rollback experiment](../proof/environment/v1-s3-011-pr2-upgrade-rollback.md),
and [the pod-restart experiment](../proof/serving/v1-s3-003-pr2-kubernetes-pod-restart.md).
Each names `docker-desktop`, one Windows host, CPU only, and one replica of each
tier. None of them certifies `kind`, none of them is a multi-replica result — the
multi-replica profile was refused at the capacity gate on this host — and none of
them says anything about a production cluster.

## What it does, in order

```sh
scripts/environment/helm-lifecycle.sh --values path/to/your-values.yaml
```

1. **Refuses to act on a cluster this project does not own.** The same guard
   every other environment script uses: the API server's nodes have to be
   containers kind labelled for `inferops-dev`, and every `helm` and `kubectl`
   call names the project kubeconfig and context explicitly rather than
   inheriting one.
2. **Ensures the namespace, and says whose it is.** `inferops-release` is
   Terraform's under
   [the ownership boundary](../architecture/resource-ownership.md), and that
   Terraform now exists in
   [the prerequisite layer](platform-prerequisites.md) — applying it first is
   the ordered path. Where it has not been applied the script creates the
   namespace itself, labels it `inferops.io/lifecycle=prerequisite`, and prints
   that it is standing in; where the namespace is already there it is reused
   untouched, so the two never both create one. It does **not** pass
   `--create-namespace` — see below.
3. **Counts the persistent volume claims** in the namespace before anything is
   installed, so that the residue check afterwards is a comparison rather than an
   assumption.
4. **Refuses if the release already exists.** Silently upgrading would make the
   result mean something other than what the script reports.
5. **Installs**, with `--wait` and a fifteen-minute timeout. The timeout has to
   outlast a model load: the measured range on the reference host was 133,515 ms
   to 358,735 ms, and a shorter timeout would report a slow load as a failure.
   Helm's timeout is not the only clock involved — the Deployment's own
   `progressDeadlineSeconds` defaults to 600 seconds, which is inside the
   runtime's startup budget, so the chart sets it explicitly rather than
   inheriting a default that would fail the rollout underneath a wait that had
   not expired.
6. **Runs `helm test`**, which is the one check that separates a rollout
   Kubernetes called successful from a release that answers. A `Service`
   selecting nothing and a working one are indistinguishable until something
   asks.
7. **Upgrades**, changing `telemetry.serviceVersion` to a marker, and asserts
   that the marker reached the rendered `ConfigMap`. A revision Helm recorded and
   the cluster never applied is not an upgrade.
8. **Rolls back to revision 1** and asserts the marker is gone. This is the check
   that the chart is rollback-compatible at all: a `Deployment`'s selector is
   immutable after creation, so a chart whose selector varied with anything a
   values file can change would make revision 2 a new object rather than an
   update, and revision 1 unreachable. The chart's selectors are drawn from the
   release name, the chart name, and the component and from nothing else, and
   [the chart suite](../../tests/architecture/test_helm_chart.py) asserts that.
9. **Uninstalls**, with `--wait`.
10. **Asserts what is left.** No object carrying
    `app.kubernetes.io/instance=inferops` may remain; Helm must report no
    release; and the namespace and every claim must still be there. Both
    directions matter — an uninstall that left release objects behind is
    incomplete, and one that removed a prerequisite is a release that owned what
    it only referenced.

On failure the release is left in place and diagnostics are collected into
`.artifacts/helm-lifecycle/`. A teardown that removes the evidence of its own
failure is worse than none.

## `--create-namespace` must never be passed

It is one flag, it is the default suggestion in most Helm documentation, and it
silently gives one resource two owners. The namespace is Terraform's; a release
installed with that flag makes Helm an owner too, and the release's own
`helm uninstall` then deletes a prerequisite that other releases and the model
cache depend on.

The chart cannot defend against it — the flag creates the namespace the chart is
being installed into, before any template runs. So the refusal lives in two
places that can: the chart refuses a namespace not prefixed `inferops-`, and both
[the chart suite](../../tests/architecture/test_helm_chart.py) and
[the script suite](../../tests/architecture/test_cluster_lifecycle_safety.py)
fail if any command in this repository passes the flag.

## What a values file has to supply

The chart's shipped defaults select no serving profile and are refused on
purpose, so the script requires `--values` and assumes nothing. The two files
under [`charts/inferops-llm/ci/`](../../charts/inferops-llm/ci/) are render
fixtures and are **not** installable: both carry a placeholder API image digest
that resolves to no image.

An installable values file needs, at minimum:

- `profile`, `mock` or `real`;
- `api.image.repository` and `api.image.digest`, naming an image that exists in
  the cluster;
- under `real`, the model identity and `model.cache.claimName`, naming a
  `PersistentVolumeClaim` that already exists and already holds the artifact.

Under `real` that claim is Terraform's (`V1-S3-005`) and the job that fills it is
the chart's own `pre-install,pre-upgrade` hook (`V1-S3-003`). Both exist and both
have run: Terraform provisions the claim empty and the hook fills it with the
pinned artifact, verifying byte count and SHA-256 before the bytes are used.

## What is not here

- **A measured duration anyone may plan against.** Installs have been timed on one
host, on one provider, and those figures appear in the proof records above as
single observations rather than as a benchmark.
  The timeouts above are derived from model-load measurements taken outside
  Kubernetes and are budgets rather than expectations.
- **Upgrade and rollback *safety*.** This script proves a rollback is mechanically
  possible. What a failed candidate looks like, how it is detected, what a
  rollback restores, and what recovery costs are
  [the upgrade and rollback experiment](helm-upgrade-rollback.md)'s, which is
  written and blocked on the same missing API image as this one. What an upgrade
  does under load and to in-flight requests is still nobody's: no load is
  generated anywhere in V1.
- **Anything about a second host, a GPU, or a cluster larger than one node.**
