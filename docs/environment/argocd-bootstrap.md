# The Argo CD bootstrap record

Status: **implemented, and executed on one provider**. Decided in
[ADR 0017](../architecture/decisions/ADR-0017-argocd-bootstrap-and-ownership.md)
on 2026-10-03. The authoritative form is data,
[`argocd-bootstrap.v1alpha1.json`](argocd-bootstrap.v1alpha1.json), and
`tests/architecture/test_argocd_bootstrap.py` holds this page,
[the ownership inventory](../architecture/resource-ownership.md), and
[the procedure](../../scripts/environment/argocd-bootstrap.sh) to it.

> [!IMPORTANT]
> **One provider, and no Application.** The procedure installed, verified, and
> removed Argo CD on the `docker-desktop` provider on 2026-10-03.
> [The record of that run](../proof/environment/v2-s3-001-pr2-argocd-bootstrap-run.md) says what was observed. The procedure was not
> executed on `kind`, and one provider's run certifies no other provider.
>
> No Application, AppProject, or ApplicationSet object exists. An installed
> Argo CD reconciles nothing. This page does not describe a deployment path.
>
> Until the procedure existed, this page said that nothing was installed and that
> no procedure existed. The record's `implementationState` was
> `decided-not-implemented`. It is now `implemented`, and a test pins that value
> and fails when a second build file names Argo CD.

## What a reader can answer from this page

1. Which Argo CD release, manifest, and images are pinned, and how each pin was
   read?
2. Which objects does the installation consist of, and which ownership row holds
   each?
3. Which privileges does the bootstrap need, and which does Argo CD receive?
4. When must the bootstrap or the removal refuse?
5. What does removal delete, and what does it leave?
6. Which of these rules does a test enforce today?
7. How is the bootstrap run, and where was it run?

## The pinned inputs

Read from upstream on 2026-10-03. The pins are identities. They are not
authenticated: no signature, attestation, or provenance statement was verified.

| Input | Pin |
|---|---|
| Project | `argoproj/argo-cd`, Apache-2.0 |
| Release | `v3.5.3`, published 2026-09-14, not a pre-release |
| Commit the tag names | `c9c369efcc5b2a0bd720803f8d14a1c3eaddf579` |
| Install manifest | `manifests/core-install.yaml` at that commit |
| Manifest SHA-256 | `1a87025d8eb2eae621653fd312fb9ca51df1b4b3b6992a030e3a9ef38e45c448` |
| Manifest size | 1,882,880 bytes, 34 objects |
| Argo CD image | `quay.io/argoproj/argocd@sha256:dd3f47d5a5e4da563a7a398506e892481b358a7cec50abdf320c71aa55904bfa` |
| Redis image | `public.ecr.aws/docker/library/redis@sha256:08ad0b1d280850169a790dba1393ff7a90aef951fc19632cf4d3ce4f78e679ba` |
| Kubernetes minors upstream lists as tested | 1.33, 1.34, 1.35, 1.36 |

How each pin was read:

- **The manifest** was downloaded twice, once by the tag and once by the commit.
  Both downloads have the SHA-256 above.
- **Each image digest** is the `Docker-Content-Digest` header the image's
  registry returned for the tag the manifest names. Each digest names a
  multi-platform index, not one platform's image.
- **The tested Kubernetes minors** are upstream's statement, in
  `docs/operator-manual/tested-kubernetes-versions.md` at the pinned commit. No
  supported provider has run this release.

The manifest is not copied into this repository. The source URL in the record
addresses it by commit:

```text
https://raw.githubusercontent.com/argoproj/argo-cd/c9c369efcc5b2a0bd720803f8d14a1c3eaddf579/manifests/core-install.yaml
```

The manifest names each image by tag: `quay.io/argoproj/argocd:v3.5.3` and
`public.ecr.aws/docker/library/redis:8.2.3-alpine`. A tag can be moved upstream,
so the manifest's SHA-256 does not identify the image bytes. The image digests
above are the pins. The procedure applies the manifest unmodified, so the apply
does not fix the image bytes. After the rollout it reads the image identity that
each container reports, init containers included, and compares it with the pin.
It reports success only when all six agree. This is the mechanism ADR 0017 D6
left open, and it keeps D5: the applied bytes are the verified bytes.

The check covers the moment it runs. Four containers set
`imagePullPolicy: Always`, so a pod that restarts later resolves the tag again,
and nothing reads its identity then.

## The procedure

One script, three operations. Each takes the provider from the operator, with no
default, and verifies the cluster before it reads it.

```text
INFEROPS_PROVIDER=docker-desktop scripts/environment/argocd-bootstrap.sh install
INFEROPS_PROVIDER=docker-desktop scripts/environment/argocd-bootstrap.sh verify
INFEROPS_PROVIDER=docker-desktop scripts/environment/argocd-bootstrap.sh remove --confirm
```

For `kind`, also set `INFEROPS_KIND_CLUSTER_NAME`.

| Operation | What it does | What it changes |
|---|---|---|
| Install | Refuses as the table below says. Downloads the manifest, or reads the file named with `--manifest PATH`, and verifies its SHA-256. Creates the namespace with its marker in one request. Applies the manifest with server-side apply. Waits at most 900 seconds for the four workloads. Checks the 34 objects and the six image identities | The namespace `argocd` and the 34 objects |
| Verify | Checks the marker, the recorded pin, the 5 cluster-scoped and 29 namespaced objects, the four workloads, and the six image identities. Lists the Secrets, Leases, and ConfigMaps by name, and any Application, ApplicationSet, or AppProject | Nothing in the cluster |
| Remove | Refuses as the table below says. Follows [the removal steps](#removal). Each wait is at most 300 seconds | Deletes the namespace `argocd` and the five cluster-scoped objects |

Facts about the procedure that a reader needs before running it:

- **A second `install` on an installation the procedure created applies the same
  bytes again.** It uses the same field manager,
  `inferops-argocd-bootstrap`. It does not create or relabel the namespace.
- **The downloaded manifest is kept in `.artifacts/argocd-bootstrap/`**, which
  Git ignores. A kept copy is used again only when its SHA-256 is the pin. The
  file is hashed a second time immediately before the apply.
- **The procedure reads no Secret value and runs nothing inside a container.** It
  therefore verifies the version as an image digest, and does not ask the
  Argo CD binary.
- **A failed install leaves the installation in place**, and writes diagnostics
  to `.artifacts/argocd-bootstrap/`. `remove --confirm` removes it.
- **`kubectl` must be within one minor version of the server.** The target guard
  refuses otherwise.

Where it was run:

| Provider | Result | Record |
|---|---|---|
| Docker Desktop | Passed twice on 2026-10-03, server `v1.34.3`: in each run three installs and two removals. An earlier attempt failed at the download and changed nothing | [The run](../proof/environment/v2-s3-001-pr2-argocd-bootstrap-run.md) |
| kind | Not executed | — |

## The namespace

The namespace is `argocd`. The bootstrap creates it and labels it
`inferops.io/lifecycle=bootstrap`.

The name is not a preference. The manifest declares no Namespace and writes no
namespace on its namespaced objects, and its one ClusterRoleBinding names a
service account in `argocd`. An unmodified manifest binds the application
controller only when it is applied there.

The name is not `inferops-release` or `inferops-smoke`, and it does not begin with
`inferops-`. A test checks all three.

## The objects, and the row that holds each

The manifest declares 34 objects. Each maps to one row of the ownership
inventory, and every row belongs to the `argocd-bootstrap` owner.

| Kind | Scope | Count | Ownership row |
|---|---|---:|---|
| `CustomResourceDefinition` | cluster | 3 | `argocd-custom-resource-definitions` |
| `ClusterRole` | cluster | 1 | `argocd-cluster-rbac` |
| `ClusterRoleBinding` | cluster | 1 | `argocd-cluster-rbac` |
| `ServiceAccount` | namespace | 4 | `argocd-controller-installation` |
| `Role` | namespace | 3 | `argocd-controller-installation` |
| `RoleBinding` | namespace | 3 | `argocd-controller-installation` |
| `ConfigMap` | namespace | 6 | `argocd-controller-installation` |
| `Secret` | namespace | 1 | `argocd-controller-installation` |
| `Service` | namespace | 4 | `argocd-controller-installation` |
| `Deployment` | namespace | 3 | `argocd-controller-installation` |
| `StatefulSet` | namespace | 1 | `argocd-controller-installation` |
| `NetworkPolicy` | namespace | 4 | `argocd-controller-installation` |

The Namespace is not in the manifest. The bootstrap creates it, and the row
`argocd-namespace` holds it.

Two more objects were expected at run time. A Secret named `argocd-redis` was
observed in the runs on `docker-desktop`. That an init container of the Redis
Deployment creates it is still an inference from the Role. A leader-election Lease of the ApplicationSet controller is
inferred from the Role that permits it, and the run did not observe it. The run
also listed `kube-root-ca.crt`, which Kubernetes creates in every namespace. The
list is not complete.
Pods and replica sets belong to the Kubernetes control plane, as they do for a
release.

What the installation contains, and what it does not:

| Component | Installed | Note |
|---|:---:|---|
| Application controller | Yes | One StatefulSet replica |
| Repository server | Yes | Fetches desired state from the Git remote |
| Redis | Yes | A cache for the two above |
| ApplicationSet controller | Yes, and unused | The core manifest includes it. InferOps commits no ApplicationSet object |
| API server and web interface | No | No login credential exists. Reconciliation state is read from the Application objects with `kubectl` |
| Dex | No | No single sign-on connector exists |
| Notifications controller | No | Argo CD sends no notification |

## Where another owner holds the same kind

Two kinds of object are shared with another owner. The record names how each is
told apart, and a test refuses a shared kind that has no named boundary.

| Shared | Other owner | Told apart by |
|---|---|---|
| `Namespace` | `terraform` | Name. Terraform owns the platform namespace. The bootstrap owns `argocd` |
| The namespaced kinds | `helm` | Namespace. A release installs into the platform namespace and never into `argocd`. The boundary does not cover an object of an `argoproj.io` kind: an Application or an AppProject would also be in `argocd`, and the bootstrap does not own it |

The three cluster-scoped kinds — `CustomResourceDefinition`, `ClusterRole`, and
`ClusterRoleBinding` — are shared with no owner. Neither committed chart render
and no Terraform file declares one.

## Privileges

**To run the bootstrap.** The operator's credential must create a Namespace,
three CustomResourceDefinitions, one ClusterRole, and one ClusterRoleBinding, and
the namespaced objects. Kubernetes refuses to create a role that grants more than
its creator holds, and the ClusterRole grants everything. The credential
therefore needs cluster-admin or an equivalent grant. This is inferred from the
manifest. The run on `docker-desktop` used that provider's administrator
credential, and the apply succeeded. No run tried a narrower credential.

**What Argo CD receives.**

| Grant | Bound to | Reach |
|---|---|---|
| ClusterRole `argocd-application-controller` | The application controller's service account | Every verb on every resource in every API group, and every verb on every non-resource URL |
| Role `argocd-application-controller` | The same service account | The namespace `argocd` |
| Role `argocd-applicationset-controller` | The ApplicationSet controller's service account | The namespace `argocd` |
| Role `argocd-redis` | The Redis service account | The namespace `argocd` |

The ClusterRole is the upstream default and is not narrowed. The application
controller is therefore able to change an object that Terraform owns, or one of
its own. No Application exists, so it reconciles nothing today. ADR 0017 records
this as R1.

## Refusals

The procedure implements all six, and states the `refusalId` in the message. The
first is stated by the provider contract's guard, with that contract's own
identifiers. Each refusal happens before the first mutation, with one exception
that the removal steps below decide: the removal checks for a custom resource a
second time after it deletes the four workloads, and before it deletes a
definition. Until 2026-10-03 this paragraph said that every refusal precedes the
first mutation, which the removal steps on this same page contradicted.

The marker is the label and a recorded manifest SHA-256 together. The procedure
writes both in one request, so it refuses a namespace that carries the label
alone. It also refuses a namespace `argocd` that is being deleted, and it does
not read an unanswered query as an absence.

One gap is not a refusal. When a marked namespace exists, the install does not
check whose the five cluster-scoped objects are, because they carry no marker.
Server-side apply then takes over one that another party replaced.

| `refusalId` | Applies to | Condition |
|---|---|---|
| `target-not-selected-or-not-verified` | bootstrap, removal | No provider is selected, or the selected cluster does not pass the provider's identity checks |
| `manifest-digest-mismatch` | bootstrap | The SHA-256 of the manifest bytes is not the pinned SHA-256 |
| `kubernetes-minor-not-tested` | bootstrap | The minor version the cluster's server reports is not one of the pinned tested minors |
| `foreign-argocd-present` | bootstrap, removal | A namespace named `argocd` exists without the bootstrap marker. Or no marked namespace exists while an Argo CD definition, or a cluster role or binding named `argocd-application-controller`, does. Removal also refuses when no namespace named `argocd` exists |
| `installed-pin-differs` | bootstrap | A marked namespace records a manifest SHA-256 that is not the pinned SHA-256. An upgrade in place is not decided |
| `argocd-custom-resources-present` | removal | An Application, ApplicationSet, or AppProject object exists in any namespace |

The first refusal is the one
[the provider contract](local-cluster-provider-contract.md) already defines for
every mutating workflow. The cluster is the operator's. The bootstrap selects it,
verifies it, and installs into it, and it does not create, enable, reset,
reconfigure, or delete it.

The bootstrap records the manifest SHA-256 it applied in the annotation
`inferops.io/argocd-manifest-sha256` on the namespace. `installed-pin-differs`
reads it.

## Removal

Removal deletes what the bootstrap created, and nothing else. It deletes by the
kinds and names the record lists, so it needs no download. It was executed four
times on `docker-desktop`, in two runs, with no Application present, and each time
no listed object remained. The refusal for an existing Application was executed against stubs
only. Its steps, in order:

1. Select and verify the target cluster, as for every mutation.
2. Refuse unless a namespace named `argocd` exists and carries the bootstrap
   lifecycle marker.
3. Refuse when an Application, ApplicationSet, or AppProject object exists.
4. Delete the StatefulSet and the three Deployments in the namespace `argocd`,
   and wait until no Argo CD pod remains.
5. Refuse again when an Application, ApplicationSet, or AppProject object exists.
6. Delete the three CustomResourceDefinitions, the ClusterRole, and the
   ClusterRoleBinding, by the names this record lists.
7. Delete the namespace `argocd`, which removes the remaining namespaced objects.
8. Confirm that no Argo CD CustomResourceDefinition, ClusterRole,
   ClusterRoleBinding, or namespace remains.

Steps 3 and 5 exist because deleting a CustomResourceDefinition deletes every
object of its kind, and an Application that carries a resource finalizer deletes
the workload it manages when it is deleted while the controller runs. Removing
the controller must not remove a workload. The controllers are stopped before the
definitions are deleted, and the check is repeated between the two.

Four gaps in this order are known:

- The two checks and the deletions are not atomic. An object created after the
  second check is deleted with its definition.
- An object that carries a finalizer and is created after the controllers stop
  keeps its definition and the namespace in a terminating state. No recovery is
  decided.
- A second Argo CD in another namespace uses the same definitions. Removal does
  not detect it when it holds no Application.
- When a person deletes the namespace `argocd` by hand, the bootstrap and the
  removal both refuse. The recovery is manual and is not decided.

Removal does not touch:

- the cluster;
- the platform namespace, its metadata, and the model cache claim;
- a Helm release, or any object in the platform namespace;
- the project kubeconfig;
- images that the node's container runtime pulled.

Removal is not one of the five teardown operations in the ownership inventory,
and [the ownership document](../architecture/resource-ownership.md#teardown-and-why-the-order-is-not-a-preference)
says why.

## The rules, and what enforces each

| `ruleId` | Enforcement | What the check does not establish |
|---|---|---|
| `bootstrap-owns-nothing-another-tool-owns` | tested | It compares kinds and not objects, and it reads files and no cluster |
| `no-other-tool-declares-a-bootstrap-object` | tested | It reads the two committed renders and the Terraform files. It does not read a values file or a namespace flag that a caller supplies at install time, or a template branch the renders do not take |
| `argocd-does-not-manage-its-own-installation` | tested, as an absence | No Argo CD custom resource is in a tracked file, so Argo CD has nothing to reconcile. The test does not restrict what a future Application may target, and it does not match a manifest that a template assembles from parts |
| `no-application-set-and-no-second-cluster` | tested, as an absence | The same test, which also matches a cluster registration secret |
| `argocd-is-not-on-the-inference-request-path` | tested | It reads source for a reference, and refuses a second build file that names Argo CD beside the procedure. No run has measured a request with Argo CD absent or stopped. It says nothing about what a running controller can do to serving objects |
| `the-pins-are-immutable-identifiers` | tested | It checks the form of each pin. It contacts no network, so it does not establish that upstream still serves these bytes |
| `bootstrap-acts-only-on-a-selected-and-verified-cluster` | tested | The procedure is executed against stub tools. The runs repeated three target refusals with the real tools; each was refused before any cluster was contacted, and no run refused a wrong cluster. The guard's own limits are the provider contract's |
| `the-manifest-is-verified-before-it-is-used` | tested | Executed against stub tools. The stub download did not reproduce the path defect the first run on Windows exposed. A SHA-256 identifies bytes and does not authenticate them |
| `images-run-at-their-pinned-digests` | tested | Executed against stub tools, through `verify` and through `install` with `sha256sum` also replaced. The runs executed the passing comparison only. The check keys on the container name. The rule covers the moment of the check and nothing after it |
| `a-foreign-argocd-installation-is-refused` | tested | Executed against stub tools. No run met a foreign installation in a cluster. The marker is a label and an annotation on the namespace; the five cluster-scoped objects carry none, and the install does not check whose they are when a marked namespace exists |
| `removal-is-scoped-and-refuses-while-an-application-exists` | tested | Executed against stub tools, for each of the three kinds. Every removal in the runs had no Application present, so the refusal was never executed against one in a cluster. No test reaches a time limit |
| `security-baseline-rows-precede-the-first-install` | tested | It establishes that the rows exist. It cannot establish that they were written before the first install; the record of the run states that order |
| `gitops-state-is-not-caller-health` | review | Nothing records Argo CD state yet |

Ten rules are tested, two are tested only as an absence, zero are not implemented, and one is held by review.

"Tested" has two meanings in this table, and the third column says which. Five
rules are held by tests that read files. Five are held by tests that execute the
procedure with every external tool replaced by a stub. Neither is a run on a
cluster.

## Out of scope

The record lists what this decision excludes: a workload Application, an
AppProject, or a desired-state directory; an app-of-apps Application; an
ApplicationSet object; a second cluster or a cluster registered with Argo CD; a
service mesh; Argo Rollouts; the Argo CD API server, web interface, single
sign-on, and notifications; and a high-availability installation.

**Added 2026-10-04.** The list above is what this record excludes, and it is
unchanged. [ADR 0018](../architecture/decisions/ADR-0018-git-desired-state-layout.md)
has since decided the desired-state directory, and
[the desired-state document](git-desired-state.md) describes it. The directory
holds generated releases and no Argo CD object. No Application names it, so the
two rules above that hold as an absence still hold.

## What this record does not establish

- That Argo CD reconciles anything. No Application exists.
- That the procedure installs or removes Argo CD on `kind`. It was executed on
  `docker-desktop` only.
- That upstream still serves the pinned bytes after the run, or that a pinned
  image is free of known vulnerabilities. No image named here was scanned.
- That the pinned release or images are authentic. No signature was verified.
- That a request is served while Argo CD is absent or stopped. No release was
  installed during the run.
- That a removal refuses on a cluster when an Application exists, or that its
  order avoids a stuck deletion. Both removals ran with no Application.
- That a container runs the pinned image after a later restart.
- That the core profile reconciles an Application. By inference from upstream
  source, no project exists after a core installation.
- That the host has the capacity to run Argo CD beside a release. The run
  installed no release.
- That a credential narrower than cluster-admin can run the bootstrap.
