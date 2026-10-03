# ADR 0017: Argo CD is installed by a pinned bootstrap that has one owner

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-10-03 |
| Date accepted | 2026-10-03, for the decisions the table below marks accepted |
| Decision owner | [`repository-maintainer`](../../governance/decision-authority.md) |
| Supersedes | None |
| Amends | [ADR 0004](ADR-0004-component-and-ownership-boundaries.md) D3: the ownership inventory gains one owner, one lifecycle, and six rows. No existing row moves |
| Superseded by | None |

> [!IMPORTANT]
> This record decides how V2 installs Argo CD, its GitOps controller, and who owns
> that installation. **It installs nothing.** No bootstrap procedure exists, no
> cluster was contacted, and no Argo CD object is committed.
>
> It pins the inputs before anything reconciles: one Argo CD release by tag and
> commit, one install manifest by commit and SHA-256, and two images by digest. The
> pins were read from upstream on 2026-10-03. No signature was verified.
>
> It creates no workload Application. Which objects Argo CD reconciles, and what
> becomes of the rows Helm owns when it does, are not decided here.
>
> The pins, the object-to-owner map, the refusals, and the removal are committed
> as data,
> [`argocd-bootstrap.v1alpha1.json`](../../environment/argocd-bootstrap.v1alpha1.json),
> explained in [the Argo CD bootstrap record](../../environment/argocd-bootstrap.md),
> and checked by `tests/architecture/test_argocd_bootstrap.py`.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | Argo CD is the V2 GitOps controller, and it reads this repository | **Accepted** as a selection | Review alone. No alternative was executed |
| D2 | The installation has one owner, the bootstrap. Argo CD does not manage its own installation | **Accepted** | The ownership inventory, and a test that no Argo CD custom resource is committed |
| D3 | The bootstrap consumes an existing cluster that is explicitly selected and verified | **Accepted** as a rule | ADR 0011 and its guard exist. No bootstrap procedure calls the guard, because none exists |
| D4 | The release is `v3.5.3`, pinned by tag and commit | **Accepted** as a pin | The record, checked for form. Compatibility with a cluster is documented upstream and not observed here |
| D5 | The install manifest is `core-install.yaml`, pinned by commit and SHA-256, applied unmodified, and not copied into this repository | **Accepted** as a pin | The record, checked for form. The SHA-256 was computed once from two downloads |
| D6 | Every Argo CD container runs the pinned digest of its image | **Accepted** as a rule. The mechanism is **proposed** | The digests are recorded. Nothing checks a running container |
| D7 | The namespace is `argocd`, and the bootstrap owns it | **Accepted** | The inventory, and a test on the name |
| D8 | The bootstrap is a repository procedure that applies the verified manifest with server-side apply | **Proposed** | Nothing. The mechanism depends on runtime behaviour and was not executed |
| D9 | Terraform, Helm, and the bootstrap own disjoint objects, and Argo CD reconciles nothing the bootstrap or Terraform owns | **Accepted** for the three tools. **Accepted** as a rule for Argo CD | The inventory and two tests, for the tools. An absence test, for Argo CD |
| D10 | Argo CD is not on the inference request path | **Accepted** as a rule | A test that no serving component refers to Argo CD. No run measured a request with Argo CD absent |
| D11 | Removal is scoped to the bootstrap's objects, refuses while an Application exists, and refuses an installation it did not create | **Accepted** as a rule | Nothing. No removal procedure exists |
| D12 | The privileges the installation needs and grants are recorded, and the cluster-wide grant is not narrowed | **Accepted** as a recorded risk | The record. See R1 |
| D13 | App-of-apps, ApplicationSet objects, a second cluster, a service mesh, Argo Rollouts, and a high-availability installation are out of scope | **Accepted** as scope | The same absence test as D2 |

## Context

V1 installs a release with `helm install`, run by an operator through an
environment script. The values file is written by hand. Since V2 generates the
release from a validated contract, the next step is to make the generated release
the reviewed desired state in Git, and to have a controller reconcile the cluster
to it. The first V2 experiment's real-deployment part names Argo CD as that
controller.

A GitOps controller is itself a set of cluster objects. Something must install it,
and that thing must have exactly one owner under
[the ownership inventory](../resource-ownership.md). Two arrangements make two
owners by accident. If Terraform installs the controller and the controller later
manages its own manifests, two tools reconcile the same objects. If the
controller's cluster-wide grant reaches a namespace that Terraform owns, the
controller is able to change it.

The cluster is not InferOps's to create.
[ADR 0011](ADR-0011-external-local-cluster-provider-contract.md) gave it to its
operator, and every mutating workflow selects a provider and verifies the cluster
before its first mutation. A bootstrap is a mutating workflow.

## Decision criteria

In order:

1. **One owner for every object.** The installation must not be owned by two
   tools, and the controller must not own its own installation.
2. **The bytes that are applied are identified before they are applied.** A tag
   or a branch is not an identity.
3. **The smallest installation that reconciles one Application.** A component
   that nothing needs is a surface that nothing watches.
4. **The serving path does not depend on the controller.**
5. **Removal deletes what the bootstrap created and nothing else.**

## D1 — Argo CD is the GitOps controller, and it reads this repository

**Accepted as a selection.**

V2 uses Argo CD. Desired state is kept in this repository, and no second
repository is introduced. This record selects the controller and decides its
installation. It does not decide the desired-state layout or the Application.

| Alternative | Assessment |
|---|---|
| **Argo CD** | **Selected.** One `Application` object carries the desired revision, the observed revision, the sync state, and the last operation. A record of a reconciliation needs those four facts, and one object is easier to read than several |
| Flux | Not selected. It spreads the same facts across a source object and a release or kustomization object. No defect was found in it; it was not executed, and neither was Argo CD |
| No controller: an operator runs `helm upgrade` from a checkout | Not selected. Nothing then detects or corrects a change made directly in the cluster |
| A second repository for desired state | Not selected. A change to the renderer and the desired state it produces could not be reviewed as one change |

## D2 — The installation has one owner

**Accepted.**

The ownership inventory gains the owner `argocd-bootstrap`, with the lifecycle
`bootstrap`. It owns four rows: `argocd-namespace`,
`argocd-custom-resource-definitions`, `argocd-cluster-rbac`, and
`argocd-controller-installation`. Terraform does not create or destroy them. Helm
does not. **Argo CD does not manage its own installation**: no Application
targets the Argo CD manifest or the namespace `argocd`.

Two more rows record what the bootstrap reads. `argocd-bootstrap-inputs` is the
committed record of the pins, owned by `repository`. `argocd-upstream-release` is
the upstream manifest and images, owned by `external-publisher`.

| Alternative | Assessment |
|---|---|
| **A bootstrap owner, separate from Terraform and Helm** | **Selected.** The installation outlives a release and is not a prerequisite of the platform namespace. Neither existing lifecycle describes it |
| Terraform owns the installation | Not selected. `terraform destroy` would delete the definitions and, with them, every Application. The prerequisite layer declares exactly two kinds today, and a test holds it to them |
| Helm owns it, through a community chart | Not selected. `helm` in the inventory means the workload release layer. A second chart from a second project is a second input to pin, and the upstream manifest is already one file |
| Argo CD manages its own manifests after a first install | Not selected. Two owners reconcile the same objects, and an error in desired state can remove the controller that would correct it |

## D3 — An existing, selected, and verified cluster

**Accepted as a rule.**

The bootstrap and the removal are mutating workflows under ADR 0011. Each takes
the provider from the operator, with no default. Each runs the selected
provider's identity checks before its first mutation. Neither creates, enables,
resets, reconfigures, or deletes a cluster.

The guard exists: `inferops::resolve_target` in `scripts/environment/lib.sh`. No
bootstrap procedure exists to call it, so this decision is a rule and not a
behaviour.

## D4 — The release

**Accepted as a pin.**

| Field | Value |
|---|---|
| Project | `argoproj/argo-cd` |
| Version | `v3.5.3` |
| Commit the tag names | `c9c369efcc5b2a0bd720803f8d14a1c3eaddf579` |
| Published | 2026-09-14 |
| License | Apache-2.0 |

On 2026-10-03 it was the newest release that was not a pre-release. Upstream
lists Kubernetes v1.33 to v1.36 as tested with Argo CD 3.5. Both supported
providers' servers were last recorded at 1.34
([ADR 0011](ADR-0011-external-local-cluster-provider-contract.md) R3). That is a
documented match and not an observed one.

| Alternative | Assessment |
|---|---|
| **`v3.5.3`** | **Selected.** The newest patch of the newest minor, and 1.34 is in its tested list |
| `v3.4.9` | Not selected. 1.34 is in its tested list too. It is the older minor and gains nothing here |
| `v3.6.0-rc1` | Not selected. It is a pre-release |

The tag is a name and the commit is the identity. The source URL in the record
uses the commit.

## D5 — The install manifest

**Accepted as a pin.**

The manifest is `manifests/core-install.yaml` at the pinned commit. Its SHA-256 is
`1a87025d8eb2eae621653fd312fb9ca51df1b4b3b6992a030e3a9ef38e45c448`, over 1,882,880
bytes. It declares 34 objects of 12 kinds.

It is applied unmodified, so that one digest identifies what was applied. It is
not copied into this repository: the repository pins a model artifact and an
image the same way, by identity and not by copy.

| Alternative | Assessment |
|---|---|
| **`core-install.yaml`** | **Selected.** It installs the application controller, the repository server, and Redis. It installs no API server, no web interface, and no single sign-on, so no login credential exists and no Service is added for a person to reach |
| `install.yaml` | Not selected. It adds the API server, the web interface, Dex, and the notifications controller. Nothing in V2 needs them, and each one is an exposed surface |
| `namespace-install.yaml` | Not selected, and worth revisiting. It grants no cluster-wide role. It also ships no definitions, and the controller could then act in the platform namespace only through a Role created inside a namespace that Terraform owns. See R1 |
| The high-availability manifests | Not selected. V2 runs one small cluster, and the multi-replica profile was refused there on capacity |

Two consequences follow from applying the file unmodified:

- **The ApplicationSet controller is installed.** The core manifest includes it.
  InferOps commits no ApplicationSet object, so it has nothing to reconcile.
- **No container declares a resource request or a limit.** See R4.

## D6 — Images run at their pinned digests

**Accepted as a rule. The mechanism is proposed.**

| Image | Reference in the manifest | Pinned digest |
|---|---|---|
| Argo CD | `quay.io/argoproj/argocd:v3.5.3` | `sha256:dd3f47d5a5e4da563a7a398506e892481b358a7cec50abdf320c71aa55904bfa` |
| Redis | `public.ecr.aws/docker/library/redis:8.2.3-alpine` | `sha256:08ad0b1d280850169a790dba1393ff7a90aef951fc19632cf4d3ce4f78e679ba` |

The manifest names each image by tag. A tag can be moved upstream, so the
manifest's SHA-256 does not identify the image bytes. The rule is that the
bootstrap does not report success unless every Argo CD container runs the pinned
digest.

How that is done is not decided. Two mechanisms are possible: rewrite each image
reference to its digest before the apply, which changes the applied bytes; or
apply the file unmodified and compare each running container's image identity
with the pin. The change that implements the bootstrap chooses one and executes
it.

## D7 — The namespace

**Accepted.**

The namespace is `argocd`. The manifest declares no Namespace and writes no
namespace on its namespaced objects. Its one ClusterRoleBinding names a service
account in `argocd`. An unmodified manifest binds the application controller only
when it is applied there.

The bootstrap creates the namespace and labels it
`inferops.io/lifecycle=bootstrap`. The name does not begin with `inferops-`, and
every upstream object carries `app.kubernetes.io/part-of: argocd`. The accepted
scoped sweep selects `app.kubernetes.io/part-of=inferops` in `inferops-`
namespaces, so it matches nothing here. That is read from the selector and the
manifest; no sweep was run.

Terraform also owns a Namespace. The two are told apart by name: Terraform owns
the platform namespace, and the bootstrap owns `argocd`.

## D8 — The mechanism

**Proposed.**

The bootstrap is a procedure in this repository. It selects and verifies the
cluster, obtains the manifest, verifies its SHA-256, creates the namespace, and
applies the manifest with server-side apply through the project-scoped
kubeconfig.

Server-side apply is proposed because the `Application` definition is larger
than the annotation that client-side apply writes. That is upstream's documented
guidance and was not tried here. This decision stays proposed until
a run executes it on a supported provider.

## D9 — Disjoint ownership

**Accepted for Terraform, Helm, and the bootstrap. Accepted as a rule for
Argo CD.**

| Owner | Owns | Told apart by |
|---|---|---|
| `terraform` | The platform namespace, its metadata, the model cache claim | — |
| `helm` | The objects of one release, in the platform namespace | Namespace |
| `argocd-bootstrap` | The namespace `argocd`, three definitions, one cluster role and its binding, and the namespaced objects of the installation | Name, for the Namespace. Kind, for the cluster-scoped objects. Namespace, for the rest |

Three checks hold this for the tools. Every object the pinned manifest declares
maps to a row that `argocd-bootstrap` owns. The namespace is not the platform
namespace, not the smoke namespace, and not under the `inferops-` prefix. Neither
committed chart render and no Terraform file declares a definition, a cluster
role, or a cluster role binding, or names the namespace `argocd`.

For Argo CD the rule is: **Argo CD reconciles no object that the bootstrap or
Terraform owns.** Today that holds because no Application exists, and a test
refuses a committed Argo CD custom resource. The test establishes an absence. It
does not restrict what an Application may target. The change that adds the first
Application owes that restriction, and must replace the test.

## D10 — Argo CD is not on the request path

**Accepted as a rule.**

A caller's request goes to the InferOps API and from there to the serving
runtime. No serving component calls Argo CD, reads an Argo CD object, or waits
for a reconciliation. Argo CD acts when desired state changes or when the cluster
drifts from it. A stopped controller stops reconciliation and does not stop
serving.

A test reads the package source, the chart, and the deployment files and refuses
a reference to Argo CD. **No run has measured a request with Argo CD absent or
stopped**, and this record does not claim one.

A related rule is held by review alone: no InferOps record derives a caller
outcome from the sync state or the health state that Argo CD reports.

## D11 — Removal

**Accepted as a rule. Not implemented.**

Removal is the reverse of the bootstrap. It deletes the objects the verified
manifest declares, then the namespace `argocd`, and confirms that no definition,
cluster role, cluster role binding, or namespace remains.

It verifies the target first, as D3 requires. It then refuses in three more
cases, before any deletion:

- **An Application or an ApplicationSet object exists.** Deleting a definition
  deletes every object of its kind. An Application that carries a resource
  finalizer deletes the workload it manages when it is deleted. Removing the
  controller must not remove a workload.
- **The namespace `argocd` does not carry the bootstrap's marker.** An Argo CD
  that somebody else installed in a shared local cluster is refused and never
  adopted. The bootstrap refuses it for the same reason.
- **The manifest's SHA-256 is not the pinned value.**

Removal does not touch the cluster, the platform namespace, a release, or the
project kubeconfig. Images that the node pulled stay in the node's image store.

Removal is not one of the five teardown operations in the ownership inventory.
Those are ordered by what they remove, and removal does not fit the order: it and
`terraform destroy` each leave the other's objects in place.

## D12 — Privileges

**Accepted as a recorded risk.**

**To run the bootstrap**, the operator's credential must create a Namespace,
three definitions, one cluster role, and one cluster role binding. Kubernetes
refuses to create a role that grants more than its creator holds, and this role
grants everything. The credential therefore needs cluster-admin or an equivalent
grant. That is inferred from the manifest; no apply was attempted.

**Argo CD receives** one cluster role, `argocd-application-controller`, bound to
the application controller's service account. It grants every verb on every
resource and on every non-resource URL. Three Roles in `argocd` cover the
controllers' own namespace.

This record does not narrow the cluster role. See R1.

## D13 — Scope

**Accepted as scope.**

V2 has one cluster and one workload path. This record therefore excludes an
app-of-apps Application, any ApplicationSet object, a cluster registered with
Argo CD, a service mesh, Argo Rollouts, the Argo CD API server and web interface,
and a high-availability installation. Adding any of them is a new decision
record.

## Consequences

- **The inventory describes five layers and one of them is not built.** The four
  bootstrap rows are `planned`. A row moves when a record of a run shows the
  bootstrap creating and removing the objects on a named provider.
- **The field `v1Status` now also describes V2 rows.** Its name is kept so that
  the suites that read it do not change. For the rows this record adds, it says
  whether the row is built.
- **Reconciliation will need the cluster to reach the Git remote.** The
  repository server fetches this repository over the network. Serving does not
  need that; a change to desired state does.
- **Reading reconciliation state is done with `kubectl`.** No Argo CD API server
  exists to ask.
- **An upstream upgrade is a change to three pins together**: the commit, the
  manifest digest, and the image digests.
- **A merge to the branch Argo CD follows will change the cluster**, once an
  Application exists. Review of that merge becomes the approval of a deployment.

## Compatibility impact

No published contract, schema, or API changes. The ownership inventory is
repository data. It gains the owner `argocd-bootstrap`, the lifecycle `bootstrap`,
and six rows; no identifier is removed or renamed. No script, chart, Terraform
file, or workflow changes.

## Security considerations

This record asserts no new security property, and it adds a surface that is not
yet live.

- **The pins are unauthenticated.** The manifest's SHA-256 and the image digests
  were read over HTTPS from upstream. No signature, attestation, or provenance
  statement was verified. A digest establishes that later bytes are the same
  bytes, not who made them. This is the condition `DR-08` already carries for the
  images this project pins.
- **The controller's grant is cluster-wide.** See R1.
- **A Git remote becomes a path into the cluster**, once an Application exists.
  Whoever can change the followed branch can change what runs.
- **The upstream network policies are expected to be inert on the local
  providers.** The network plugin both providers were observed running does not
  apply one (`DR-04`, `EX-05`). The manifest's four policies describe intent and
  are not relied on.
- **The security baseline is not restated here.** No control, threat, or risk row
  is added, because the baseline describes what exists, and no installation
  exists. The change that first installs Argo CD must add the rows before it
  runs.

## Evidence

`C0`, static, on 2026-10-03, under
[the evidence levels](../../testing/evidence-levels.md). **No cluster was
contacted and nothing was installed.** Upstream was read and not written: the
release list and the tag, the manifest, the tested-versions page, the licence,
and two registry digests. The full record is
[the V2-S3-001-PR1 change validation](../../proof/architecture/v2-s3-001-pr1-validation.md).

What the suite establishes: that the record, the ownership inventory, the
Terraform defaults, and the committed renders agree; that every pin has the form
of an immutable identifier; and that no Argo CD custom resource and no reference
from a serving component is committed. What it establishes about whether Argo CD
installs, reconciles, or can be removed: **nothing**. That needs a cluster.

## Risks, assumptions, and open questions

| ID | Item | Status | Impact |
|---|---|---|---|
| R1 | The application controller holds every verb on every resource | Open | The inventory says who may create and destroy an object. It does not stop a controller that holds a wider grant. A namespace-scoped installation, or a project that limits destinations and kinds, would narrow it. Neither is decided |
| R2 | The pinned bytes are identified and not authenticated | Open | A compromised upstream release would be pinned as faithfully as a sound one |
| R3 | Upstream may withdraw the manifest or an image | Accepted | The bootstrap then fails closed at the digest check or the pull. Nothing is copied here to prevent it |
| R4 | No Argo CD container declares a resource request or a limit | Open | The reference host refused the multi-replica profile on capacity. Whether it runs four more pods beside a release is not known |
| R5 | What becomes of the `helm` rows when Argo CD applies the chart | Open | Argo CD renders a chart and applies the result; it does not run `helm install`. The rows' `createdBy` and `destroyedBy`, and the chart's `pre-install` hook, are then described by the wrong tool. The change that adds the first Application owes the answer |
| R6 | The `default` project is not created by any manifest object | Open | Whether one exists after a core installation was not observed. An Application names a project |
| R7 | The bootstrap's marker is a label | Accepted | A person who can label a namespace can set it. It prevents an accident and not an impersonation, as `EX-02` and `EX-06` already record for the cluster guard |
| R8 | The tested Kubernetes list is upstream's statement | Accepted | No supported provider has run this release |
| R9 | Server-side apply was not tried | Open | D8 stays proposed until a run |
