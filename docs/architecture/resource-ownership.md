# V1 resource ownership

Status: **accepted as the V1 ownership boundary**, in
[ADR 0004](decisions/ADR-0004-component-and-ownership-boundaries.md). Both halves
are now written against: `V1-S3-002-PR1` added the Helm chart at
[`charts/inferops-llm/`](../../charts/inferops-llm/), `V1-S3-002-PR2` added the
release lifecycle procedure at
[`scripts/environment/helm-lifecycle.sh`](../../scripts/environment/helm-lifecycle.sh),
`V1-S3-003-PR1` wrote the reference side of the model cache handoff — a
revision-scoped read-only mount and an integrity check before the runtime starts,
described in
[the storage document](../environment/model-cache-storage.md) — and
`V1-S3-005-PR1` added the Terraform prerequisite layer at
[`infra/terraform/`](../../infra/terraform/), described in
[the prerequisite document](../environment/platform-prerequisites.md), and
`V1-S3-006-PR1` added a second release procedure at
[`scripts/environment/kubernetes-certification.sh`](../../scripts/environment/kubernetes-certification.sh),
described in
[the Kubernetes certification procedure](../serving/kubernetes-real-inference-certification.md),
and `V1-S3-006-PR2` added a third at
[`scripts/environment/kubernetes-multi-replica-certification.sh`](../../scripts/environment/kubernetes-multi-replica-certification.sh),
described in
[the multi-replica certification procedure](../serving/kubernetes-multi-replica-certification.md).

**The cluster itself changed hands on 2026-09-11.**
[ADR 0011](decisions/ADR-0011-external-local-cluster-provider-contract.md) moved
it out of InferOps: the operator provides an existing cluster through one of two
supported providers, `kind` or Docker Desktop, and InferOps selects, verifies, and
consumes it. The inventory now gives each provider's cluster its own row, owned by
`cluster-operator` with the `operator-provided` lifecycle, because the two have
different lifecycles and different evidence and one row had to average them. How
a cluster is selected and identified is in
[the provider contract](../environment/local-cluster-provider-contract.md).

**Three procedures now install and uninstall the same release in the same
namespace**, and the distinction is what each is for rather than what each
touches. `helm-lifecycle.sh` answers "does the chart install, upgrade, roll back,
and uninstall cleanly" and involves no model. `kubernetes-certification.sh`
answers "does a real model answer through the release's Service" and writes a
`C2` record. `kubernetes-multi-replica-certification.sh` answers "do requests
through that Service reach more than one replica" and writes a second one. All
three refuse to run over an existing release, so they interlock rather than
collide; all three apply the same rule about what a release may own, and both
certification workflows additionally count the model cache claim on both sides of
their own run.

The multi-replica workflow is the only one that creates an object in the
namespace which neither Terraform nor the chart owns: one `batch/v1 Job` that
sends the request set from inside the cluster, because a `kubectl port-forward`
is served against a single endpoint and cannot exercise a Service's distribution.
It is not a row in any table below, and deliberately so — it is transient in the
same sense the `helm test` hook pod is, created and removed inside one run rather
than installed. It carries the release's own labels so that the release's network
policy describes it, the workflow deletes it before the uninstall, and the
residue check that follows the uninstall names `jobs` explicitly, so a driver
that survived its own run is a failure rather than a leftover nobody looked
for.

**Most rows below are now `implemented`, and it is worth being exact about what
that means.** Until `V1-S3-011` every row in the release and prerequisite tables
was `planned`, and that was correct: a chart renders objects, a rendered object is
a file, and a Terraform configuration nobody has applied creates nothing. That is
no longer the state. Terraform has applied and re-applied the prerequisite layer,
Helm has installed, upgraded, rolled back and uninstalled the release, the
acquisition hook has filled the claim, the controllers have made the derived
objects, and each of those was observed in a cluster rather than in a render.

What `implemented` does **not** mean here:

- **not on every provider.** Every promotion below was observed on
  `docker-desktop`, the V1 reference provider, on one Windows host. `kind` has
  not executed any of it since the ownership realignment, and
  [ADR 0011](decisions/ADR-0011-external-local-cluster-provider-contract.md)
  forbids borrowing one provider's answer for the other;
- **not enforced, where enforcement is a separate question.**
  `workload-network-policy` is `implemented` because Helm creates and destroys
  the objects, which is what a row in this table is about. Whether the local
  network plugin *enforces* one is a different claim, it remains unproven, and
  [the enforcement record](../proof/security/v1-s3-004-pr1-network-policy-enforcement.md)
  is where that stands;
- **not multi-replica.** Every row was observed with one replica of each tier.
  The multi-replica profile was refused at the capacity gate on this host and no
  row here is evidence of anything else.

The lifecycle script records one thing this document had left implicit. Something
has to create the namespace a release installs into, and that something must not
be Helm. Until the prerequisite layer is applied the script creates it itself,
labels it `inferops.io/lifecycle=prerequisite`, and says it is standing in —
which keeps the prerequisite half of the boundary a stand-in rather than a second
owner. It is now standing in for a configuration that exists rather than for one
that does not, and it still creates nothing when the namespace is already there.

What did change is that both layers are now checked against this document.
`tests/architecture/test_helm_chart.py` reads the release table and refuses a
chart that renders something it does not name, or that renders a Terraform-owned
object, or that leaves a Helm-owned row neither rendered nor declared deferred.
`tests/architecture/test_terraform_prerequisites.py` does the same for the
prerequisite table: it refuses a configuration that declares something this
document does not give Terraform, that declares a release or derived object, that
implements a deferred row, or that leaves a prerequisite row undeclared. The last
paragraph of this document used to say that no such check could exist for
Terraform. It exists now, and what it cannot establish is written there instead.

The authoritative form of this document is data, not prose:
[`resource-ownership.v1alpha1.json`](resource-ownership.v1alpha1.json). The tables
here explain it, and a test compares the two in both directions: every identifier in
the data must appear in this document, and every identifier this document publishes
in a table's first column must exist in the data. A row added to one and forgotten
in the other is a build failure rather than something a reader has to notice.

What that comparison does not do is read the prose. A table row can carry a
description that has drifted from the `handoff` text in the data, and no test will
say so.

## What ownership means here

**Ownership is the right to create and destroy.** One resource, one owner, always.

Three corollaries, because each is a mistake this inventory is built to prevent:

- **Referencing is not owning.** A Helm chart that mounts a Terraform-owned claim
  does not own the claim. The inventory records references separately, and a
  resource may never list its own owner among its referrers.
- **Writing content is not owning the container.** The model acquisition job writes
  weights into a claim it does not own. That is the single sanctioned handoff in the
  design, and it is named in the claim's own row rather than left implicit.
- **A derived object has no tool owner at all.** Pods, replica sets, endpoint
  slices, and a bound volume are created by controllers from an owned object.
  Adopting one into a chart or into Terraform state means taking ownership of
  something a controller will keep rewriting.

## Owners

| `ownerId` | Who or what | Lifecycle | Creates with | Destroys with |
|---|---|---|---|---|
| `repository` | This repository and its review process | `repository` | A merged pull request | A merged pull request |
| `workload-owner` | The team that owns the workload | `out-of-band` | A documented manual step | A documented manual step |
| `external-publisher` | The upstream image and model publishers | `external` | Publishes upstream | Withdraws upstream |
| `contributor-host` | The contributor's machine, engine, and environment scripts | `host` | The environment scripts, or a host prerequisite | The environment scripts, or the contributor |
| `cluster-operator` | The operator who provides the local cluster, with a supported provider's own tooling | `operator-provided` | The `kind` CLI, or enabling Kubernetes in Docker Desktop | Cluster teardown, by the operator. Nothing on the platform path does it |
| `terraform` | The platform prerequisite layer | `prerequisite` | `terraform apply` | `terraform destroy` |
| `helm` | The workload release layer | `release` | `helm install` or `helm upgrade` | `helm uninstall` |
| `kubernetes-control-plane` | Kubernetes controllers | `derived` | Reconciliation | Garbage collection |
| `undecided` | Not selected | `undecided` | Nothing | Nothing |

`undecided` is a real entry, not a placeholder for laziness. A resource that carries
it must be deferred out of V1, and a test enforces that: an unowned resource inside
V1 scope is exactly the ambiguity this inventory exists to prevent, so the inventory
refuses to represent one.

## The Terraform and Helm boundary

The rule the parent story asks for, stated as a rule rather than a hope:

> **Terraform owns what outlives a release. Helm owns the release. Neither owns
> anything the other owns, and neither owns anything a controller creates.**

| | Terraform | Helm |
|---|---|---|
| Owns | The namespace, its shared metadata, the model cache claim | Everything installed into that namespace as one release |
| Lifetime | Longer than any release | Exactly one release |
| Removed by | `terraform destroy` | `helm uninstall` |
| May reference the other's resources | Yes | Yes |
| May create the other's resources | **No** | **No** |

Two specific prohibitions, because these are the two ways the boundary is usually
crossed by accident rather than by argument:

1. **Helm is never invoked with `--create-namespace`.** It is one flag, it is the
   default suggestion in most documentation, and it silently makes both tools own
   the namespace. Everything else in this boundary is easy by comparison.
2. **Terraform never imports or adopts an object a release installed.** A resource
   that appears in Terraform state and in a chart will be reconciled by both, and
   the loser is whichever ran last.

### Prerequisites

| `resourceId` | Kind | Survives `helm uninstall` | Handoff |
|---|---|:---:|---|
| `platform-namespace` | `v1/Namespace` | Yes | Terraform creates it; Helm installs into it |
| `namespace-metadata` | Object metadata | Yes | Namespace-level metadata is Terraform's; per-object metadata inside a release is Helm's |
| `model-cache-volume-claim` | `v1/PersistentVolumeClaim` | Yes | Terraform provisions it empty; a Helm-owned job fills it; the serving deployment mounts it read-only, at a revision-scoped subdirectory rather than at its root |
| `platform-resource-quota` | `v1/ResourceQuota` | Yes | **Deferred out of V1.** Named so that if it is ever added it lands on the prerequisite side rather than inside a chart |

### The release

| `resourceId` | Kind | Note |
|---|---|---|
| `workload-service-account` | `v1/ServiceAccount` | Release-scoped. An identity that outlives what it identifies is a permission nobody is watching |
| `platform-api-deployment` | `apps/v1 Deployment` | The API, its probes, its requests and limits, its security context |
| `platform-api-service` | `v1/Service` | ClusterIP. External access is an explicit port-forward |
| `serving-runtime-deployment` | `apps/v1 Deployment` | Separate from the API for the reasons in [the system architecture](system-architecture.md) |
| `serving-runtime-service` | `v1/Service` | Internal to the release; not a public surface |
| `runtime-configuration` | `v1/ConfigMap` | Rendered from a validated contract. Holds no secret value |
| `model-acquisition-job` | `batch/v1 Job` | Verifies the artifact hash before the bytes are used; resumable, because a single streamed transfer was measured not to survive. Rendered since the Sprint 3 remediation as a `pre-install,pre-upgrade` hook, so it completes before the runtime's own integrity check runs. It writes through a temporary file and renames only after verification, so a failed acquisition leaves nothing that looks finished, and it replaces rather than reuses an artifact that does not verify — replaces, because `V1-S3-011-PR2` changed the ordering: it used to delete the mismatching artifact first, and a run that could then not acquire a replacement left the claim empty. `implemented`: a release has installed it and it has filled the claim |
| `model-acquisition-service-account` | `v1/ServiceAccount` | The identity the job above presents, created by the same hook phase at a lower weight and removed by the same delete policy. It exists because Helm applies a phase's hooks before the release manifest: the runtime account the job used to name does not exist yet when the hook is created, so the API server refuses the Job and the install fails reporting only a pre-install timeout. Granted nothing, and no pod mounts a token. `implemented`, along with the hook it identifies |
| `workload-network-policy` | `networking.k8s.io/v1 NetworkPolicy` | A declaration until a test proves the local cluster's network plugin enforces one |
| `telemetry-scrape-configuration` | `v1/ConfigMap` | A scrape configuration and recording rules for this release. Rendered since `V1-S3-007`; read since the Sprint 3 remediation by the collector below, which mounts it rather than carrying a second copy |
| `telemetry-collector` | `platform service` | A Deployment, Service, ConfigMap, ServiceAccount, Role and RoleBinding. Reads the row above. `ADR 0004` `D7` left this undecided for two sprints and the consequence was a configuration nothing consumed; the amendment made it Helm-owned and release-scoped. Its series are in an `emptyDir` and go with the pod, so it answers questions about the release running now and is not a store anything may depend on. `implemented`: a release installed it and a real Prometheus scraped both InferOps jobs through it |

### Derived, and owned by no tool

| `resourceId` | Kind | Created by |
|---|---|---|
| `replica-sets` | `apps/v1 ReplicaSet` | The deployment controller |
| `pods` | `v1/Pod` | The replica set controller |
| `endpoint-slices` | `discovery.k8s.io/v1 EndpointSlice` | The endpoint slice controller |
| `bound-persistent-volume` | `v1/PersistentVolume` | The storage provisioner, on binding the claim |

`endpoint-slices` is the row that turns a probe mapping from a manifest detail into
a correctness property: readiness decides membership, so a readiness probe pointed
at an endpoint that is healthy during model load will route requests to a model that
cannot answer them.

`pods` is the row that makes the model cache a prerequisite rather than an
`emptyDir`. A pod is disposable by definition, so nothing durable may live only
inside one.

### Outside the cluster entirely

| `resourceId` | Owner | Note |
|---|---|---|
| `workload-contract-schema` | `repository` | The input to every layer, produced by none of them |
| `evidence-records` | `repository` | Written by a reviewed change. Nothing in a cluster writes here |
| `workload-contract-document` | `workload-owner` | The platform reads it and never writes it back |
| `workload-secret-material` | `workload-owner` | Referenced by name. This project never creates, rotates, or reads it |
| `serving-runtime-container-image` | `external-publisher` | Pinned by digest. Availability is not this project's to guarantee |
| `model-artifact-upstream` | `external-publisher` | Pinned by revision and per-file hash, verified before use |
| `container-engine` | `contributor-host` | No step changes host-wide engine settings |
| `kind-cluster` | `cluster-operator` | An existing `kind` cluster. Terraform and Helm act inside it and neither may create or delete it; since ADR 0011 nothing on the platform path may either. `implemented`, on `kind` evidence only |
| `docker-desktop-cluster` | `cluster-operator` | Docker Desktop's cluster. A release has now been installed and certified through it under the provider contract, and the guard binds each node to a container on this engine and to the API server port the verified kubeconfig dials. `implemented`, along with the whole release layer, by `V1-S3-011-PR2`'s reconciliation — the operator still owns its lifecycle, and nothing here creates, enables, resets, or deletes it |
| `project-kubeconfig` | `contributor-host` | Holds a client certificate and key; ignored by version control; removed on teardown. The `kind` helper writes its own fixed copy; `inferops::resolve_target` writes a second, provider-selected one fresh on every mutating workflow's run |
| `node-image-cache` | `cluster-operator` | `kind` only. Retained across teardown by design; reclaimed by an opt-in step |
| `platform-api-container-image` | `contributor-host` | Built locally and made visible to the cluster by the provider's own image path rather than pushed to a shared registry. For Docker Desktop that path is now established and is not `kind load`: the cluster does not share the engine's image store, and the mechanism is a `docker save` piped into the node's own containerd followed by an explicit `repository@digest` tag |

### Not owned, and therefore not in V1

| `resourceId` | Why it has no owner |
|---|---|
| `telemetry-backend` | Dashboards and an alert routing path. Narrowed by the Sprint 3 remediation: this row used to cover the collector as well, and the collector is now decided and owned. What is left is genuinely open -- a dashboard needs somebody to read it, and an alert needs a receiver, a routing tree and somebody on the other end |
| `ingress-and-load-balancing` | `kind` ships neither, and installing them was recorded as an open cost; what Docker Desktop provides has not been examined here. Until one is chosen, every service is ClusterIP |

## Teardown, and why the order is not a preference

Five operations, ordered by how much they touch. Each subsumes the one before it.

```text
   pod restart             -> a pod goes and comes back. Nothing declared
                              is affected.

   helm uninstall          -> the release goes. The namespace, its
                              metadata, and the model cache survive.

   scoped object teardown  -> project-labelled objects in the project's
                              namespaces go. This is the sweep the
                              overlap below is about.

   terraform destroy       -> the prerequisites go. Deleting the namespace
                              cascades, so anything still installed dies
                              with it. This is not the routine uninstall
                              path.

   cluster teardown        -> the cluster goes or is reset, by its
                              operator with the provider's own tooling.
                              Nothing on InferOps's platform path does
                              this (ADR 0011), and neither tool may.
```

The inventory records, per resource, which of these it survives. Two tests read
those records: one refuses a row that claims to survive the operation that destroys
it, and one refuses a row whose survival list is not a prefix of the ordering above
— because a resource that survives a wider operation must survive every narrower
one.

## An overlap this design found, and specified a fix for

The accepted cleanup rules describe partial teardown as deleting *"only objects
matching the project label selector inside `inferops-` namespaces"*. Every object
this project creates carries `app.kubernetes.io/part-of: inferops`. Read together,
a broadened scoped sweep would delete Terraform-owned prerequisites, and two owners
would be destroying one resource — precisely what this document forbids.

It is not a live defect. The implemented teardown is bound to a single smoke-test
namespace and does not sweep across `inferops-` namespaces at all, so nothing today
can reach a prerequisite that does not yet exist. It becomes one the moment either
the sweep is generalised to match the accepted wording or Terraform is written.

The resolution is a second label. Prerequisites carry a lifecycle marker that a
scoped sweep must exclude; release objects carry the marker that a sweep may match.
`namespace-metadata` is where the prerequisite marker is set, and
[the Terraform prerequisite layer](../../infra/terraform/modules/platform-prerequisites/)
now sets it: `inferops.io/lifecycle: prerequisite` on the namespace and on the
claim, checked by `tests/architecture/test_terraform_prerequisites.py`. **Half of
the resolution is therefore implemented and half is not.** Setting a marker is
not the same as excluding it, and the scripts are still unchanged:

- the environment scripts' scoped teardown must exclude the prerequisite marker
  before it is ever generalised beyond the smoke namespace. **This is still not
  implemented**, and it is still not a live defect for the same reason as before:
  the implemented teardown is bound to one smoke-test namespace and sweeps
  nothing else;
- the platform namespace must be distinct from the smoke-test namespace the
  environment scripts already own and delete outright. **This is implemented.**
  The prerequisite configuration defaults to the release namespace and refuses
  the smoke namespace by name, in a variable validation and in a test.

## What a reviewer should check

The mechanical parts are tested; the judgement parts are not. Both are listed in
[the boundary review checklist](boundary-review-checklist.md).

Checked by `tests/architecture/test_resource_ownership.py`: single ownership,
Terraform and Helm disjointness, lifecycle agreement between a resource and its
owner, survival claims drawn from the declared operations and forming a prefix of
the blast-radius ordering above, no resource surviving its own destruction,
prerequisites outliving releases, release objects not outliving prerequisites,
derived resources having no tool owner, an unowned resource being deferred,
evidence cited only by implemented rows, and the document and the data publishing
the same identifiers in both directions.

The blast-radius check is the one worth understanding, because it is what catches a
plausible-looking survival claim rather than a malformed one. The operations above
escalate: an uninstall removes what a restart would have left, destroying the
namespace cascades over what an uninstall removed, and deleting the cluster takes
all of it. So a resource that survives a wider operation survives every narrower
one, and a survival list that skips an operation and claims a larger one is
refused.

Checked by `tests/architecture/test_local_cluster_provider_contract.py`, for the
cluster rows only: that each supported provider's cluster has its own row, that
both belong to `cluster-operator` and neither survives the operation that removes
it, that no tool or script owns one, and that the Docker Desktop row stays
`planned` while nothing can identify that cluster.

Checked by `tests/architecture/test_helm_chart.py`, for the release layer only:
that the committed chart renders every row the release table gives it or declares
the row deferred, that it renders no Terraform-owned object and no `Namespace`,
that it mounts the model cache claim without creating it — read-only, and at a
subdirectory derived from the declared revision rather than at the claim's root —
and that every rendered object carries the isolation label and the release
lifecycle marker.

Checked by `tests/architecture/test_terraform_prerequisites.py`, for the
prerequisite layer only: that every resource the committed configuration declares
maps to a Terraform-owned row here and every Terraform-owned row in scope is
declared, that the declared kinds are exactly the two expected ones — an
allowlist as well as a denylist, so a new kind cannot arrive unnoticed — that no
release object, derived object, deferred row, second provider, or
cluster-creating resource appears, that the namespace and the claim carry the
project label and the prerequisite lifecycle marker, that the namespace is the
one a release installs into and is not the one another script deletes outright,
that the claim name is the one the chart mounts and the claim is large enough for
the artifact this project pins, that the provider pin is exact and identical in
every place it is written, and that the provider names its kubeconfig and context
rather than inheriting them.

**What the two suites still do not check: that either configuration does what it
says when it runs.** They read files, and a file is not a cluster. That gap is
now closed by execution rather than by testing — Terraform has been applied and
re-applied and the chart has been installed, upgraded, rolled back and
uninstalled on `docker-desktop`, and the records are cited row by row above. What
the suites establish remains what they establish: the two halves of this
document are a commitment about behaviour and a verification about text, and it
is a record of a run — not either suite — that moves a row to `implemented`.
