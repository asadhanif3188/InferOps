# V1 resource ownership

Status: **accepted as the V1 ownership boundary**, in
[ADR 0004](decisions/ADR-0004-component-and-ownership-boundaries.md). Half of it is
now written against: `V1-S3-002-PR1` added the Helm chart at
[`charts/inferops-llm/`](../../charts/inferops-llm/), `V1-S3-002-PR2` added the
release lifecycle procedure at
[`scripts/environment/helm-lifecycle.sh`](../../scripts/environment/helm-lifecycle.sh),
`V1-S3-003-PR1` wrote the reference side of the model cache handoff — a
revision-scoped read-only mount and an integrity check before the runtime starts,
described in
[the storage document](../environment/model-cache-storage.md) — and there is
still no Terraform configuration. **Every row below is still
`planned` or `deferred`, and that is correct**: a chart renders objects, a
rendered object is a file, and a procedure nobody has executed changes nothing in
a cluster. None of the resources in the release table exists in a cluster,
because nothing here has installed one — and the lifecycle script cannot be run
until an InferOps API image exists.

The script does record one thing this document had left implicit. Until Terraform
is written, something has to create the namespace a release installs into, and
that something must not be Helm. The script creates it, labels it
`inferops.io/lifecycle=prerequisite`, and says it is standing in for `V1-S3-005`
— which keeps the prerequisite half of the boundary a stand-in rather than a
second owner.

What did change is that the chart is now checked against this document.
`tests/architecture/test_helm_chart.py` reads the release table and refuses a
chart that renders something it does not name, or that renders a Terraform-owned
object, or that leaves a Helm-owned row neither rendered nor declared deferred.
The last paragraph of this document used to say that no such check could exist.
It exists for the release layer; it does not exist for Terraform.

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
| `contributor-host` | The contributor's machine, engine, and environment scripts | `host` | `scripts/environment/cluster-up.sh`, or a host prerequisite | Cluster teardown |
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
| `model-acquisition-job` | `batch/v1 Job` | Verifies the artifact hash before the bytes are used; resumable, because a single streamed transfer was measured not to survive. Still `planned`: `V1-S3-003` implemented the reference side of the handoff and left the writing side, which needs an unpublished image and a 1.71 GiB transfer, to the Kubernetes serving integration |
| `workload-network-policy` | `networking.k8s.io/v1 NetworkPolicy` | A declaration until a test proves the local cluster's network plugin enforces one |
| `telemetry-scrape-configuration` | Release configuration | Inert until a collector exists |

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
| `local-kubernetes-cluster` | `contributor-host` | Terraform and Helm act inside a cluster neither may create or delete |
| `project-kubeconfig` | `contributor-host` | Holds a client certificate and key; ignored by version control; removed on teardown |
| `node-image-cache` | `contributor-host` | Retained across teardown by design; reclaimed by an opt-in step |
| `platform-api-container-image` | `contributor-host` | Built locally and loaded into the cluster rather than pushed to a shared registry |

### Not owned, and therefore not in V1

| `resourceId` | Why it has no owner |
|---|---|
| `telemetry-backend` | Components will expose metrics; nothing collects them. Whether a collector is a prerequisite or part of a release is unresolved, and this row exists so that the question is answered deliberately rather than by whoever adds the first scrape target |
| `ingress-and-load-balancing` | The accepted local Kubernetes distribution ships neither, and installing them was recorded as an open cost. Until one is chosen, every service is ClusterIP |

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

   cluster teardown        -> the cluster goes, by the environment
                              scripts. Neither tool may do this.
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
`namespace-metadata` is where the prerequisite marker is set. **Nothing here
implements it.** The scripts are unchanged by this document, and the two constraints
below are recorded as constraints on work that has not started:

- the environment scripts' scoped teardown must exclude the prerequisite marker
  before it is ever generalised beyond the smoke namespace;
- the platform namespace must be distinct from the smoke-test namespace the
  environment scripts already own and delete outright.

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

Checked by `tests/architecture/test_helm_chart.py`, for the release layer only:
that the committed chart renders every row the release table gives it or declares
the row deferred, that it renders no Terraform-owned object and no `Namespace`,
that it mounts the model cache claim without creating it — read-only, and at a
subdirectory derived from the declared revision rather than at the claim's root —
and that every rendered object carries the isolation label and the release
lifecycle marker.

Not checked by anything, because there is nothing to check it against: that the
inventory describes the **Terraform** that gets written. That check arrives with
the implementation, and until then the prerequisite half of this file is a
commitment rather than a verification.
