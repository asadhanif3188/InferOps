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

**A fifth layer was decided on 2026-10-03, and built the same day.**
[ADR 0017](decisions/ADR-0017-argocd-bootstrap-and-ownership.md) selects how V2
installs Argo CD, its GitOps controller, and gives that installation one owner:
`argocd-bootstrap`, with the `bootstrap` lifecycle. The inventory gains that owner
and six rows. Four of them are the objects the bootstrap creates in a cluster.
They were `planned` until a procedure existed. They are now `implemented`: a run
on the `docker-desktop` provider created and removed them, and
[the record of that run](../proof/environment/v2-s3-001-pr2-argocd-bootstrap-run.md) says what was observed. No run on
`kind` exists. The pins and the rules are in
[the Argo CD bootstrap record](../environment/argocd-bootstrap.md). This change
moves no existing row. Terraform keeps the prerequisites and Helm keeps the
release. Which objects Argo CD reconciles was not decided there, because no
Application existed.

**A sixth layer was decided on 2026-10-04, and built the same day.**
[ADR 0019](decisions/ADR-0019-argocd-application-and-sync-policy.md) decides one
Argo CD Application for one release path, and the project that holds it. They
have one owner: `argocd-application`, with the `reconciliation` lifecycle. The
inventory gains that owner and two rows. One row is the two committed manifests.
The other is the two objects in a cluster, and it is `implemented`: three runs on
the `docker-desktop` provider applied and removed them, and
[the record of those runs](../proof/environment/v2-s3-002-pr2-argocd-application-run.md)
says what was observed. No run on `kind` exists.

**The release rows keep their owner, and the inventory now describes two paths to
them.** `createdBy` and `destroyedBy` on a `release` row describe the operator's
Helm path. On a cluster where the Application is applied, Argo CD creates the
same objects from the same chart, and the Application procedure's removal deletes
them. The two paths do not run in one namespace at one time: the procedure
refuses while a Helm release of the same name is recorded there. That refusal is
executed against stubs and was observed once in each run on `docker-desktop`. Nothing stops
an operator who runs `helm install` after the Application is applied, and ADR
0019 records that as a risk.

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
| `argocd-bootstrap` | The Argo CD bootstrap procedure, run by an operator against a selected and verified cluster. Decided by ADR 0017 | `bootstrap` | `scripts/environment/argocd-bootstrap.sh install` | `scripts/environment/argocd-bootstrap.sh remove` |
| `argocd-application` | The Argo CD Application procedure, run by an operator against a selected and verified cluster. Decided by ADR 0019 | `reconciliation` | `scripts/environment/argocd-application.sh apply` | `scripts/environment/argocd-application.sh remove` |
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

### The Argo CD bootstrap

Added on 2026-10-03 by
[ADR 0017](decisions/ADR-0017-argocd-bootstrap-and-ownership.md). Every row is
`implemented` since the run on `docker-desktop` on 2026-10-03. The field is still
named `v1Status`; for these rows it records whether the row is built, and it does
not place the row in V1 scope.

> **The bootstrap owns the Argo CD installation. Terraform, Helm, and Argo CD
> itself do not create it and do not destroy it.**

| `resourceId` | Kind | Told apart from another owner by | Note |
|---|---|---|---|
| `argocd-namespace` | `v1/Namespace` | Name. Terraform owns the platform namespace; this one is `argocd` | The pinned manifest declares no Namespace, so the bootstrap creates it and labels it `inferops.io/lifecycle=bootstrap`. The name does not begin with `inferops-` |
| `argocd-custom-resource-definitions` | `apiextensions.k8s.io/v1 CustomResourceDefinition` | Kind. No other owner declares one | Three definitions. Deleting one deletes every object of its kind, so removal refuses while an Application, ApplicationSet, or AppProject object exists, and deletes the definitions only after the controllers have stopped |
| `argocd-cluster-rbac` | `rbac.authorization.k8s.io/v1 ClusterRole` and `ClusterRoleBinding` | Kind. No other owner declares one | One of each. The role grants every verb on every resource. It is the upstream default and is not narrowed |
| `argocd-controller-installation` | `platform service` | Namespace. A Helm release owns the same kinds in the platform namespace | Twenty-nine namespaced objects in `argocd`. One more was observed at run time, a Secret. A leader-election Lease is expected and was not observed. No container declares a resource request or a limit. One Application and its project are also in `argocd` and are not part of this row: they are `argocd-workload-application` |

Three limits apply to this table:

- **The rows are built on one provider.** A row moved to `implemented` when a
  record of a run showed the bootstrap creating and removing the objects on a
  named provider. [That run](../proof/environment/v2-s3-001-pr2-argocd-bootstrap-run.md) was on `docker-desktop`. It
  certifies nothing about `kind`.
- **The role in `argocd-cluster-rbac` reaches every object in the cluster.** The
  inventory says who may create and destroy an object. It does not stop a
  controller that holds a wider grant. Since 2026-10-04 one Application exists
  in the repository, and its project admits one destination namespace, eight
  namespaced kinds, and no cluster-scoped kind. That restricts the one
  Application. It does not narrow the role.
- **The ApplicationSet controller is installed and unused.** The pinned manifest
  includes it and is applied unmodified. InferOps commits no ApplicationSet
  object.

### The Argo CD Application

Added on 2026-10-04 by
[ADR 0019](decisions/ADR-0019-argocd-application-and-sync-policy.md). The row is
`implemented` since the run on `docker-desktop` on 2026-10-04.

> **The Application procedure owns one Application and one project. The
> bootstrap, Terraform, Helm, and Argo CD itself do not create them and do not
> destroy them.**

| `resourceId` | Kind | Told apart from another owner by | Note |
|---|---|---|---|
| `argocd-workload-application` | `Argo CD custom resource (AppProject, Application)` | Kind and name. The bootstrap owns the namespace `argocd` and every object in it that is not of an `argoproj.io` kind | The project `inferops-workloads` and the Application `local-docker-desktop-support-assistant`. Each carries a label and a recorded manifest SHA-256. The procedure refuses beside any other Application, ApplicationSet, or AppProject object. The bootstrap removal refuses while either exists |

Three limits apply to this row:

- **It is built on one provider.** [The runs](../proof/environment/v2-s3-002-pr2-argocd-application-run.md)
  were on `docker-desktop`. They certify nothing about `kind`.
- **The marker prevents an accident and not an impersonation.** A person who can
  write an object in `argocd` can write the label and the annotation.
- **The Application is not desired state.** Argo CD does not read the two
  manifests from Git. A merge that changes one changes no cluster until the
  procedure runs again.

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
| `workload-network-policy` | `networking.k8s.io/v1 NetworkPolicy` | `implemented` describes the objects, which Helm creates and destroys and `V1-S3-011` watched it do. It does not describe enforcement, and enforcement is not untested: [an executed experiment](../proof/security/v1-s3-004-pr1-network-policy-enforcement.md) established that `kindnetd` -- the plugin that experiment tested, and the one both providers' clusters were observed running -- does not apply one, so these objects are created and inert (`DR-04`, `EX-05`) |
| `telemetry-scrape-configuration` | `v1/ConfigMap` | A scrape configuration and recording rules for this release. Rendered since `V1-S3-007`; read since the Sprint 3 remediation by the collector below, which mounts it rather than carrying a second copy |
| `telemetry-collector` | `platform service` | A Deployment, Service, ConfigMap, ServiceAccount, Role and RoleBinding. Reads the row above. `ADR 0004` `D7` left this undecided for two sprints and the consequence was a configuration nothing consumed; the amendment made it Helm-owned and release-scoped. Its series are in an `emptyDir` and go with the pod, so it answers questions about the release running now and is not a store anything may depend on. `implemented`: a release installed it and a real Prometheus scraped both InferOps jobs through it |
| `workload-disruption-budget` | `policy/v1 PodDisruptionBudget` | `planned`. Added on 2026-10-09 with chart `0.6.0`. One budget for the API tier and one for the serving runtime tier, each rendered only when its tier declares two or more replicas, with `minAvailable: 1`. A budget bounds a voluntary eviction. It does not bound a direct pod deletion, a node loss, or a rolling update. The chart renders the objects and a test holds the render. A release that renders both was installed once, on the `docker-desktop` provider on 2026-10-09, for one reading of the Service endpoints, and no eviction was requested. See [the disruption budgets](../environment/disruption-budgets.md) |

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
| `evidence-records` | `repository` | Written by a reviewed change. Nothing in a cluster writes here, and a record is never regenerated by rerunning the thing it describes. The one exception is `proof-dashboard-page`, which is why it has a row of its own |
| `proof-dashboard-page` | `repository` | The generated V1 proof dashboard, the single derived page under `docs/proof/`. Regenerated from `claim-and-evidence-register` on every change and compared against it by a test, so it cannot say more than the register; not to be edited by hand. Added 2026-09-21 |
| `claim-and-evidence-register` | `repository` | Every published claim with its status, evidence class, reachable certification level, provider, environment and limitation. Produced by no run; a status is set only by a reviewed change. Added 2026-09-21 |
| `continuous-integration-workflow` | `repository` | The committed default-lane workflow and the gate matrix compared against it in both directions. The only committed artifact here that runs anything; it installs nothing and no job in it has reached a cluster. Added 2026-09-21, having acted since 2026-09-13 with no row |
| `inference-operations-dashboard` | `repository` | The dashboard's panels, queries and empty-state texts as a committed record, and the Grafana JSON generated from it. Split out of `telemetry-backend` by the `ADR 0004` `D7` amendment of 2026-09-13. `implemented` means the definition exists and is checked against the query policy and synthetic scenarios; one throwaway Grafana imported it once for the V1-S4-002-PR2 validation, and nothing here runs one |
| `inference-alert-definitions` | `repository` | The six V1 alerts -- expression, window, threshold source, owner, severity, caller impact, action, runbook -- as a committed record, and the Prometheus rule file per profile generated from it. Split out of `telemetry-backend` by the `ADR 0004` `D7` amendment of 2026-09-17. `implemented` means the definition exists and is checked against the query policy and eight committed scenarios; no Prometheus in a cluster has loaded it, nothing routes an alert, and nobody has ever been told about one |
| `argocd-bootstrap-inputs` | `repository` | The pinned Argo CD release, install manifest and images, the namespace, the object-to-row map, the refusals, and the scoped removal, as a committed record. `implemented` means that the record exists and is checked against this inventory. It does not mean that Argo CD is installed. Added 2026-10-03 |
| `git-desired-state` | `repository` | The directory `gitops/`: generated releases, one directory for one environment binding and one workload, and nothing written by hand except the page that describes it. Decided by [ADR 0018](decisions/ADR-0018-git-desired-state-layout.md). `implemented` means that the tree exists and that a check accounts for every entry in it. Since 2026-10-04 one Application reads the generated values of the one release from it, on a cluster where that Application is applied. It holds no cluster object. Added 2026-10-04 |
| `argocd-application-manifests` | `repository` | Two files under `infra/argocd/`: one project and one Application. Decided by [ADR 0019](decisions/ADR-0019-argocd-application-and-sync-policy.md). They are not desired state: Argo CD does not read them from Git, and the Application procedure applies them. The Application file holds no API image digest. `implemented` means that the files exist and that a suite holds them to the decision. Added 2026-10-04 |
| `workload-contract-document` | `workload-owner` | The platform reads it and never writes it back |
| `workload-secret-material` | `workload-owner` | Referenced by name. This project never creates, rotates, or reads it |
| `serving-runtime-container-image` | `external-publisher` | Pinned by digest. Availability is not this project's to guarantee |
| `model-artifact-upstream` | `external-publisher` | Pinned by revision and per-file hash, verified before use |
| `argocd-upstream-release` | `external-publisher` | The Argo CD install manifest, pinned by commit and SHA-256, and the two images it names, pinned by digest. Not copied into this repository. Availability is not this project's to keep. `implemented` since a run on `docker-desktop` downloaded the manifest, verified it, and ran containers at both pinned digests. Added 2026-10-03 |
| `container-engine` | `contributor-host` | No step changes host-wide engine settings |
| `kind-cluster` | `cluster-operator` | An existing `kind` cluster. Terraform and Helm act inside it and neither may create or delete it; since ADR 0011 nothing on the platform path may either. `implemented`, on `kind` evidence only |
| `docker-desktop-cluster` | `cluster-operator` | Docker Desktop's cluster. A release has now been installed and certified through it under the provider contract, and the guard binds each node to a container on this engine and to the API server port the verified kubeconfig dials. `implemented`, along with the whole release layer, by `V1-S3-011-PR2`'s reconciliation — the operator still owns its lifecycle, and nothing here creates, enables, resets, or deletes it |
| `project-kubeconfig` | `contributor-host` | Holds a client certificate and key; ignored by version control; removed on teardown. The `kind` helper writes its own fixed copy; `inferops::resolve_target` writes a second, provider-selected one fresh on every mutating workflow's run |
| `node-image-cache` | `cluster-operator` | `kind` only. Retained across teardown by design; reclaimed by an opt-in step |
| `platform-api-container-image` | `contributor-host` | Built locally and made visible to the cluster by the provider's own image path rather than pushed to a shared registry. For Docker Desktop that path is now established and is not `kind load`: the cluster does not share the engine's image store, and the mechanism is a `docker save` piped into the node's own containerd followed by an explicit `repository@digest` tag |
| `model-seed-container-image` | `contributor-host` | The second image this project builds locally: it carries the already-verified model artifact into the acquisition job so a clean-clone run does not repeat the download. Same provider-aware load path, never pushed. The job's hash comparison is unchanged -- the seed shortens the download, it does not replace the check. Added 2026-09-21 |

### Not owned, and therefore not in V1

| `resourceId` | Why it has no owner |
|---|---|
| `telemetry-backend` | A dashboard server and an alert routing path. Narrowed three times: the Sprint 3 remediation took the collector out of it, the `ADR 0004` `D7` amendment of 2026-09-13 took the dashboard *definition* out of it, as `inference-operations-dashboard`, and the amendment of 2026-09-17 took the alert *definition* out of it, as `inference-alert-definitions`. What is left is genuinely open -- a Grafana server needs an owner, somewhere to run and an exposure decision, and an alert needs a receiver, a routing tree and somebody on the other end |
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

**The Argo CD bootstrap removal is not one of the five.** The five are ordered
because each one removes what the one before it removes. The bootstrap removal
does not fit that order: it deletes the namespace `argocd` and five
cluster-scoped objects, and it does not touch the platform namespace. A
`terraform destroy` does the opposite. The four bootstrap rows therefore survive
every operation above except cluster teardown, and their `destroyedBy` names a
procedure that is not in the list. The test that refuses a row which survives
its own destruction compares against the list, so it cannot fail for these rows.
The removal steps and their refusals are in
[the Argo CD bootstrap record](../environment/argocd-bootstrap.md#removal).

**The Application removal is not one of the five either.** It deletes the
Application with a cascade, so Argo CD deletes the release objects it applied,
and then it deletes the project. It does not touch the platform namespace, a
claim, or the Argo CD installation. The row `argocd-workload-application`
survives every operation above except cluster teardown, for the same reason as
the bootstrap rows. The steps are in
[the Argo CD Application document](../environment/argocd-application.md#removal).

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
it, that no tool or script owns one, and that each provider's row cites only
evidence made on its own provider.

Checked by `tests/architecture/test_argocd_bootstrap.py`, for the bootstrap rows
only: that every object the pinned manifest declares maps to a row the
`argocd-bootstrap` owner holds, and every such row is named by the record; that
the namespace is not the platform namespace, not the smoke namespace, and not
under the `inferops-` prefix; that neither committed chart render and no
Terraform file declares a cluster-scoped kind the bootstrap owns or names the
namespace `argocd`; that the two manifests of ADR 0019 are the only tracked
files that declare an Argo CD custom resource, and that none registers a
cluster; that removal refuses before it deletes, and deletes the
definitions after the controllers; and that every bootstrap row is `implemented`,
names the procedure, and cites the record of a run. Until the procedure existed
the last check pinned `planned`, and the change that implemented the bootstrap
moved it.

Checked by `tests/architecture/test_argocd_application.py`, for the Application
rows only: that the `argocd-application` owner holds one row and names the
procedure; that the project admits one repository, one destination, the kinds
the chart's real profile renders, and no cluster-scoped kind; that no admitted
kind is one Terraform owns; and that the Application reads the generated values
of the declared release and prunes nothing.

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

**What the bootstrap suite does not check: anything in a cluster.** It reads a
record that was written from one download of an upstream file. It does not
establish that the manifest applies, that the namespace boundary holds at run
time, or that a removal leaves nothing behind.

**What the two suites still do not check: that either configuration does what it
says when it runs.** They read files, and a file is not a cluster. That gap is
now closed by execution rather than by testing — Terraform has been applied and
re-applied and the chart has been installed, upgraded, rolled back and
uninstalled on `docker-desktop`, and the records are cited row by row above. What
the suites establish remains what they establish: the two halves of this
document are a commitment about behaviour and a verification about text, and it
is a record of a run — not either suite — that moves a row to `implemented`.
