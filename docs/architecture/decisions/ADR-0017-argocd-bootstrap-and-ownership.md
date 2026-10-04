# ADR 0017: Argo CD is installed by a pinned bootstrap that has one owner

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-10-03 |
| Date accepted | 2026-10-03, for the decisions the table below marks accepted |
| Amended | 2026-10-03, in place, by the change that implemented the bootstrap. Each amended decision says so, with the date. No decision was withdrawn. Amended again on 2026-10-04, by the change that added the first Application: D5, D9, R5, and R6 say so |
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

> [!NOTE]
> **Amended 2026-10-03: the bootstrap is implemented.** The block above describes
> this record as it was accepted, when nothing was installed. Later the same day,
> `scripts/environment/argocd-bootstrap.sh` implemented the decision, and it
> installed, verified, and removed Argo CD on the `docker-desktop` provider.
> [The record of that run](../../proof/environment/v2-s3-001-pr2-argocd-bootstrap-run.md) says what was observed.
>
> The procedure was not executed on `kind`. No Application exists, so Argo CD
> reconciles nothing. The amendments are marked in the status table, in D3, D5,
> D6, D8, D11, and D12, and in the consequences, the compatibility impact, the
> security considerations, the evidence, and the risks.

> [!NOTE]
> **Amended 2026-10-04: one Application exists.** [ADR 0019](ADR-0019-argocd-application-and-sync-policy.md)
> decided one Application, its project, and the procedure that applies them. It
> answers what D9, R5, and R6 left to the change that adds the first
> Application. On `docker-desktop` the core profile reconciled that Application,
> and a removal of the installation refused while it existed. The sentences of
> this record that say no Application exists describe the record as it was
> written.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | Argo CD is the V2 GitOps controller, and it reads this repository | **Accepted** as a selection | Review alone. No alternative was executed |
| D2 | The installation has one owner, the bootstrap. Argo CD does not manage its own installation | **Accepted** | The ownership inventory, and a test that no Argo CD custom resource is committed |
| D3 | The bootstrap consumes an existing cluster that is explicitly selected and verified | **Accepted** as a rule. **Amended 2026-10-03:** the procedure calls the guard before its first read of the cluster | ADR 0011 and its guard exist. Tests execute the procedure against stubs and find no mutation on an unselected or unverified target. A run repeated three of those refusals with the real tools: no provider, an unsupported provider, and `kind` with no cluster name. Each was refused before any cluster was contacted. No run refused a wrong cluster |
| D4 | The release is `v3.5.3`, pinned by tag and commit | **Accepted** as a pin | The record, checked for form. Compatibility with a cluster is documented upstream and not observed here. **Amended 2026-10-03:** observed on `docker-desktop` at server `v1.34.3`, and not on `kind` |
| D5 | The install manifest is `core-install.yaml`, pinned by commit and SHA-256, applied unmodified, and not copied into this repository | **Accepted** as a pin of the bytes. The choice of the core profile is **proposed** | The record, checked for form. The SHA-256 was computed once from two downloads. No run reconciled an Application with this profile; see R6 |
| D6 | When the bootstrap reports success, every Argo CD container runs the pinned digest of its image | **Accepted** as a rule for that moment. The mechanism was **proposed**. **Amended 2026-10-03:** the mechanism is the first of the two, and it is **accepted** for `docker-desktop` | The digests are recorded. The procedure compares the image identity each container reports with the pin, and a run did so. Nothing holds the digest after a restart |
| D7 | The namespace is `argocd`, and the bootstrap owns it | **Accepted** | The inventory, and a test on the name |
| D8 | The bootstrap is a repository procedure that applies the verified manifest with server-side apply | **Proposed**. **Amended 2026-10-03: accepted** for `docker-desktop`, and still proposed for `kind` | A run applied the manifest three times with server-side apply on `docker-desktop`. No run on `kind` |
| D9 | Terraform, Helm, and the bootstrap own disjoint objects, and Argo CD reconciles nothing the bootstrap or Terraform owns | **Accepted** for the three tools. **Accepted** as a rule for Argo CD | The inventory and two tests, for the tools. An absence test, for Argo CD |
| D10 | Argo CD is not on the inference request path | **Accepted** as a rule | A test that no serving component refers to Argo CD. No run measured a request with Argo CD absent |
| D11 | Removal is scoped to the bootstrap's objects, refuses while an Argo CD custom resource exists, and refuses an installation it did not create | **Accepted** as a rule. Its order was a design that no run had tried. **Amended 2026-10-03:** a run followed the order twice on `docker-desktop`, with no Application present | Two removals that left no listed object. The refusal for an existing Application is executed against stubs only |
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

The comparison below was written after the choice. The first V2 experiment
already named Argo CD before this record existed, and this record states the
reasons instead of discovering them.

| Alternative | Assessment |
|---|---|
| **Argo CD** | **Selected.** One `Application` object carries the desired revision, the observed revision, the sync state, and the last operation. A record of a reconciliation needs those four facts, and one object is easier to read than several |
| Flux | Not selected. It spreads the same facts across a source object and a release or kustomization object. No defect was found in it; it was not executed, and neither was Argo CD. Its default controller also holds a cluster-wide grant, so R1 does not separate the two |
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

**Amended 2026-10-03.** The procedure calls the guard once, at its top level,
before any function that reads the cluster. A static test holds that order. An
executed suite runs the procedure against stubs for each of its three operations
and finds no mutation when no provider is selected, when the provider is
unsupported, when a `kind` target has no cluster name, and when the reachable
cluster is not the selected one. The guard's own limits are unchanged, and ADR
0011 records them.

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
| `namespace-install.yaml` | Not selected. It grants no cluster-wide role, which is why R1 names it. It is not a smaller core: it is the full profile without cluster-wide access, so it adds the API server, Dex, and the notifications controller. It ships no definitions, and the controller could then act in the platform namespace only through a Role created inside a namespace that Terraform owns |
| The high-availability manifests | Not selected. V2 runs one small cluster, and the multi-replica profile was refused there on capacity |

Two consequences follow from applying the file unmodified:

- **The ApplicationSet controller is installed.** The core manifest includes it.
  InferOps commits no ApplicationSet object, so it has nothing to reconcile.
- **No container declares a resource request or a limit.** See R4.

**The pin is accepted. The choice of the core profile is proposed.** The bytes are
identified, and that needs no run. Whether this profile reconciles an Application
is runtime behaviour, and no run tried it. Upstream source at the pinned commit
creates the `default` project in the API server, which this profile does not
install. By that inference, a core installation holds no project until something
creates one. See R6.

**Amended 2026-10-03.** The pinned bytes were downloaded, verified, and applied
unmodified on `docker-desktop`: 34 objects, as the pin says. The four workloads of
the core profile became ready. The choice of the profile **stays proposed**: the
run created no Application, so it did not show that this profile reconciles one.

**Amended 2026-10-04.** The choice of the core profile is **accepted for
`docker-desktop`**, and stays proposed for `kind`. A run of the Application
procedure found no project after the bootstrap, as R6 inferred. It applied a
committed project and one Application, and Argo CD applied the release.
[ADR 0019](ADR-0019-argocd-application-and-sync-policy.md) and
[the record of that run](../../proof/environment/v2-s3-002-pr2-argocd-application-run.md)
say what was observed.

## D6 — Images run at their pinned digests

**Accepted as a rule for the moment the bootstrap reports success. The mechanism
is proposed.**

| Image | Reference in the manifest | Pinned digest |
|---|---|---|
| Argo CD | `quay.io/argoproj/argocd:v3.5.3` | `sha256:dd3f47d5a5e4da563a7a398506e892481b358a7cec50abdf320c71aa55904bfa` |
| Redis | `public.ecr.aws/docker/library/redis:8.2.3-alpine` | `sha256:08ad0b1d280850169a790dba1393ff7a90aef951fc19632cf4d3ce4f78e679ba` |

The manifest names each image by tag. A tag can be moved upstream, so the
manifest's SHA-256 does not identify the image bytes. The rule is that the
bootstrap does not report success unless every Argo CD container, init
containers included, runs the pinned digest at that moment.

**The rule does not hold after that moment.** Four of the six containers set
`imagePullPolicy: Always` and name their image by tag. A pod that restarts later
resolves the tag again and can run other bytes. One init container sets
`IfNotPresent` and one sets no policy, so a node that already holds an image
under that tag uses it without asking the registry.

How the check is done is not decided, and the two mechanisms are not equal:

- **Apply the file unmodified and compare each running container's image identity
  with the pin.** This keeps D5. It covers the moment of the check only.
- **Replace each image reference with its digest before the apply.** This holds
  after a restart. It changes the applied bytes, so it amends D5: the SHA-256
  would be verified on the downloaded bytes, and the applied bytes would differ
  from them by the substitution.

The change that implements the bootstrap chooses one and executes it. If it
chooses the second, it amends D5 in the same change.

**Amended 2026-10-03.** The change chose the first mechanism, so D5 is not
amended. After the rollout, the procedure reads the image identity that each
container status reports, init containers included, and compares it with the
pin. A container that the record does not list, or that reports no identity,
fails the check. On `docker-desktop`, with containerd, all six containers
reported the pinned digests, which are the digests of the multi-platform
indexes.

The limit in this section still holds, and the choice does not remove it: the
check covers its own moment. The second mechanism was not chosen because it
changes the applied bytes. The deferred risk `DR-13` carries what the first
mechanism does not reach.

## D7 — The namespace

**Accepted.**

The namespace is `argocd`. The manifest declares no Namespace and writes no
namespace on its namespaced objects. Its one ClusterRoleBinding names a service
account in `argocd`. An unmodified manifest binds the application controller only
when it is applied there.

The bootstrap creates the namespace and labels it
`inferops.io/lifecycle=bootstrap`. The name does not begin with `inferops-`, and
every upstream object carries `app.kubernetes.io/part-of: argocd`. The implemented
scoped sweep selects `app.kubernetes.io/part-of=inferops` in the one namespace
`inferops-smoke`, and the accepted wording for a wider sweep names `inferops-`
namespaces. Neither matches anything here. That is read from the selector and the
manifest; no sweep was run.

Terraform also owns a Namespace. The two are told apart by name: Terraform owns
the platform namespace, and the bootstrap owns `argocd`.

## D8 — The mechanism

**Proposed.**

The bootstrap is a procedure in this repository. It selects and verifies the
cluster, obtains the manifest, verifies its SHA-256, creates the namespace, and
applies the manifest with server-side apply through the project-scoped
kubeconfig.

Server-side apply is proposed because upstream documents that some of the
definitions, the `ApplicationSet` one among them, exceed the 262,144-byte limit
on the annotation that client-side apply writes. That is upstream's guidance and
was not tried here. Upstream pairs it with `--force-conflicts`, which takes over
a field another manager holds. That flag is why the refusal of a foreign
installation in D11 also covers the cluster role and its binding by name. This
decision stays proposed until a run executes it on a supported provider.

**Amended 2026-10-03: accepted for `docker-desktop`.** A run executed it there.
The procedure obtained the manifest, verified its SHA-256, created the namespace
with its marker in one request, and applied the manifest with
`kubectl apply --server-side --force-conflicts` and the field manager
`inferops-argocd-bootstrap`. All 34 objects were applied, with no conflict and no
size error, on a first install, on a second install over a live installation, and
on an install after a removal. The decision stays proposed for `kind`, where no
run exists.

Two details were decided by the implementation and are recorded here. The
manifest is kept in an ignored directory after the download, and a kept copy is
used again only when its SHA-256 is the pin. An operator may supply the file
with `--manifest`, and it is verified the same way.

## D9 — Disjoint ownership

**Accepted for Terraform, Helm, and the bootstrap. Accepted as a rule for
Argo CD.**

| Owner | Owns | Told apart by |
|---|---|---|
| `terraform` | The platform namespace, its metadata, the model cache claim | — |
| `helm` | The objects of one release, in the platform namespace | Namespace |
| `argocd-bootstrap` | The namespace `argocd`, three definitions, one cluster role and its binding, and the namespaced objects of the installation | Name, for the Namespace. Kind, for the cluster-scoped objects. Namespace, for the rest, except an object of an `argoproj.io` kind |

Three checks hold this for the tools. Every object the pinned manifest declares
maps to a row that `argocd-bootstrap` owns. The namespace is not the platform
namespace, not the smoke namespace, and not under the `inferops-` prefix. Neither
committed chart render and no Terraform file declares a definition, a cluster
role, or a cluster role binding, or names the namespace `argocd`.

**The namespace boundary has one exception, and it is open.** An Application or
an AppProject must also be in `argocd`, because the pinned manifest does not let
the controller read one elsewhere. The bootstrap does not own such an object.
Who does is not decided, and R5 carries it.

For Argo CD the rule is: **Argo CD reconciles no object that the bootstrap or
Terraform owns.** Today that holds because no Application exists, and a test
refuses a committed Argo CD custom resource. The test establishes an absence. It
does not restrict what an Application may target. The change that adds the first
Application owes that restriction, and must replace the test.

**Amended 2026-10-04.** That change replaced the test.
[ADR 0019](ADR-0019-argocd-application-and-sync-policy.md) D3 decides the
restriction: the one Application is in a project that admits one destination
namespace, which is not `argocd`, eight namespaced kinds, and no cluster-scoped
kind. A test reads the project and the kinds each other owner holds. The rule
now holds by a restriction on one committed Application. It does not narrow the
controller's grant, and R1 stays open.

## D10 — Argo CD is not on the request path

**Accepted as a rule.**

A caller's request goes to the InferOps API and from there to the serving
runtime. No serving component calls Argo CD, reads an Argo CD object, or waits
for a reconciliation. Argo CD acts when desired state changes or when the cluster
drifts from it. A stopped controller stops reconciliation and does not stop
serving.

A test reads every tracked file under the build directories and refuses a
reference to Argo CD. **No run has measured a request with Argo CD absent or
stopped**, and this record does not claim one.

**Not being on the request path is not the same as being unable to affect
serving.** Once an Application exists, a running controller can change, restart,
or delete serving objects: it reverts a manual change, it rolls out a new
revision, and it holds the grant in R1. Its four pods also compete for the node
with the serving runtime, without a request or a limit (R4). This record bounds
neither.

A related rule is held by review alone: no InferOps record derives a caller
outcome from the sync state or the health state that Argo CD reports.

## D11 — Removal

**Accepted as a rule. Not implemented, and its order is a design that no run
tried.**

Removal deletes what the bootstrap created and nothing else. It deletes by the
kinds and names the record lists, so it needs no download and does not depend on
upstream still serving the manifest.

Every refusal comes before the first deletion:

- **The target is not selected or not verified** (D3).
- **No namespace `argocd` carries the bootstrap's marker.** An Argo CD that
  somebody else installed in a shared local cluster is refused and never adopted.
  The bootstrap refuses it for the same reason, and also when a definition, or a
  cluster role or binding named `argocd-application-controller`, exists while no
  marked namespace does.
- **An Application, ApplicationSet, or AppProject object exists.** Deleting a
  definition deletes every object of its kind. An Application that carries a
  resource finalizer deletes the workload it manages when it is deleted while the
  controller runs. Removing the controller must not remove a workload.

The order of the deletions matters, and the first draft of this record had it
wrong. The manifest lists the definitions first, so deleting "the objects the
manifest declares" deletes them while the controllers still run. The decided
order is:

1. stop the controllers, and wait until no Argo CD pod remains;
2. check again that no Argo CD custom resource exists;
3. delete the three definitions, the cluster role, and its binding;
4. delete the namespace `argocd`, which removes the rest;
5. confirm that none of them remains.

The bootstrap also refuses a marked namespace that records a different manifest
SHA-256. An upgrade in place is not decided.

Removal does not touch the cluster, the platform namespace, a release, or the
project kubeconfig. Images that the node pulled stay in the node's image store.

**Amended 2026-10-03.** `argocd-bootstrap.sh remove --confirm` implements the
steps in the decided order. On `docker-desktop` it ran twice. Each time no
Application existed, the four workloads were deleted, no pod remained, the
second check found nothing, and no definition, cluster role, binding, or
namespace remained. `kubectl`, asked directly afterwards, agreed. An install
after a removal succeeded.

The run did not try the refusals in a cluster, except one: a removal with no
namespace was refused. The refusal for an existing Application, the second
check, and the refusal of an unmarked namespace are executed against stubs. The
implementation adds three refusals that this section did not list: it refuses a
namespace that is being deleted, it refuses a namespace that carries the label
and records no manifest SHA-256, and it refuses to continue on a query that did
not answer.

One gap is added to the four above. When a marked namespace exists, the
install does not check whose the five cluster-scoped objects are, because they
carry no marker (R11). Server-side apply with `--force-conflicts` then takes
over one that another party replaced.

Four gaps are known and recorded with the steps. The checks and the deletions are
not atomic. An object with a finalizer that appears after the controllers stop
keeps its definition and the namespace terminating. A second Argo CD in another
namespace shares the definitions and is not detected when it holds no
Application. And when a person deletes the namespace by hand, the bootstrap and
the removal both refuse, and the recovery is manual.

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

**Amended 2026-10-03.** An apply was attempted and succeeded, with the
administrator credential that `docker-desktop` provides. No run tried a narrower
credential, so the lower bound is still an inference.

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
  **Amended 2026-10-03:** a run did, on `docker-desktop`, and the four rows are
  `implemented`. The condition did not name how many providers, and one was
  taken as enough. The rows say which provider.
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

**Amended 2026-10-03.** The implementation adds one script,
`scripts/environment/argocd-bootstrap.sh`. It changes no chart, no Terraform
file, no workflow, and no line of `lib.sh`. No published contract, schema, or
API changes.

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
  runs. Nothing enforces that obligation: it is the rule
  `security-baseline-rows-precede-the-first-install` in the record, marked not
  implemented, and [the deferred-risk register](../../security/deferred-risks.md)
  points at R1 and R2 below.
  **Amended 2026-10-03:** the rows were added before the first install: three
  threats, six controls, one asset, and the deferred risks `DR-13` and `DR-14`.
  A test holds that the rows exist. Nothing checks the order.

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

**Amended 2026-10-03.** A cluster was used. Three kinds of evidence now exist,
and they are not interchangeable:

- `C0`: the static suite above, which now also reads the procedure as text.
- `C1`: `tests/architecture/test_argocd_bootstrap_procedure.py`, which executes
  the procedure with every external tool replaced by a stub.
- `C2`: [one run on the `docker-desktop` provider](../../proof/environment/v2-s3-001-pr2-argocd-bootstrap-run.md). A first attempt
  failed at the download and changed nothing. A second attempt installed three
  times, removed twice, and left the cluster as it found it.

The run establishes that the procedure installs and removes the pinned Argo CD
on that provider, on that day. It establishes nothing about `kind`, about
reconciliation, or about serving. No claim is registered.

## Risks, assumptions, and open questions

| ID | Item | Status | Impact |
|---|---|---|---|
| R1 | The application controller holds every verb on every resource | Open | The inventory says who may create and destroy an object. It does not stop a controller that holds a wider grant. A namespace-scoped installation, or a project that limits destinations and kinds, would narrow it. Neither is decided |
| R2 | The pinned bytes are identified and not authenticated, and the image pin does not hold after a restart | Open | A compromised upstream release would be pinned as faithfully as a sound one. Under the unmodified manifest, a restarted pod resolves its image tag again (D6) |
| R3 | Upstream may withdraw the manifest or an image | Accepted | The bootstrap then fails closed at the digest check or the pull. Nothing is copied here to prevent it. Removal does not need the manifest: it deletes by the names the record lists |
| R4 | No Argo CD container declares a resource request or a limit | Open | The reference host refused the multi-replica profile on capacity. Whether it runs four more pods beside a release is not known, and neither is their effect on the latency of the serving runtime they share a node with |
| R5 | What becomes of the `helm` rows when Argo CD applies the chart | Open | Argo CD renders a chart and applies the result; it does not run `helm install`. The rows' `createdBy` and `destroyedBy`, and the chart's `pre-install` hook, are then described by the wrong tool. An Application and its project would also be objects in `argocd` that the bootstrap does not own. The change that adds the first Application owes both answers. **Amended 2026-10-04: answered** by ADR 0019. The Application and its project have their own owner and row (D2). The `release` rows keep `helm`, and the two delivery paths do not run in one namespace at one time (D8). In a run, Argo CD ran the chart's `pre-install` hook before the sync |
| R6 | A core installation probably holds no project | Open | Inferred, not observed: upstream source at the pinned commit creates the `default` project in the API server (`initializeDefaultProject` in `server/server.go`), and the core profile installs no API server. An Application names a project, so the first Application needs a committed AppProject and an owner for it. This is why the choice of profile in D5 is proposed. **Amended 2026-10-04: closed for `docker-desktop`.** A run found no project after the bootstrap. ADR 0019 commits one, with an owner, and the Application synced in it |
| R7 | The bootstrap's marker is a label | Accepted | A person who can label a namespace can set it. It prevents an accident and not an impersonation, as `EX-02` and `EX-06` already record for the cluster guard |
| R8 | The tested Kubernetes list is upstream's statement | Accepted | No supported provider has run this release. **Amended 2026-10-03:** `docker-desktop` ran it at server `v1.34.3`. `kind` has not |
| R9 | Server-side apply was not tried | Open. **Amended 2026-10-03: closed for `docker-desktop`**, open for `kind` | D8 stays proposed until a run. A run on `docker-desktop` applied all 34 objects three times |
| R10 | The removal order was not tried, and four gaps in it are known | Open. **Amended 2026-10-03:** the order was tried twice on `docker-desktop` with no Application present. The four gaps stay open | D11 lists them. A stuck deletion has no decided recovery. No run met one |
| R11 | The marker is on the namespace only | Accepted | The five cluster-scoped objects carry upstream labels and no marker. The refusal reads their names |
