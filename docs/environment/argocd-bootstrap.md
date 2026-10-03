# The Argo CD bootstrap record

Status: **decided, and not implemented**, in
[ADR 0017](../architecture/decisions/ADR-0017-argocd-bootstrap-and-ownership.md)
on 2026-10-03. The authoritative form is data,
[`argocd-bootstrap.v1alpha1.json`](argocd-bootstrap.v1alpha1.json), and
`tests/architecture/test_argocd_bootstrap.py` holds this page and
[the ownership inventory](../architecture/resource-ownership.md) to it.

> [!IMPORTANT]
> **Nothing here is installed.** No bootstrap procedure exists, and this
> repository has not installed Argo CD in any cluster. This page records the
> inputs a bootstrap will use and the rules it must follow. The record's
> `implementationState` is `decided-not-implemented`, and a test pins that value.
> The test fails when a tracked file under the build directories names Argo CD,
> so a change that implements the bootstrap must move the value. A procedure that
> never names the controller would pass it.

## What a reader can answer from this page

1. Which Argo CD release, manifest, and images are pinned, and how each pin was
   read?
2. Which objects does the installation consist of, and which ownership row holds
   each?
3. Which privileges does the bootstrap need, and which does Argo CD receive?
4. When must the bootstrap or the removal refuse?
5. What does removal delete, and what does it leave?
6. Which of these rules does a test enforce today?

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
above are the pins, and the rule `images-run-at-their-pinned-digests` is not yet
implemented. The rule covers the moment the bootstrap reports success. Four
containers set `imagePullPolicy: Always`, so a pod that restarts later resolves
the tag again.

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

At least two more objects are expected at run time: a Secret named
`argocd-redis`, which an init container of the Redis Deployment creates, and a
leader-election Lease of the ApplicationSet controller. Both are inferred from
the Roles that permit them, and neither was observed. The list is not complete.
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
manifest; no apply was attempted.

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

Each refusal happens before the first mutation. **None is implemented**; the
bootstrap procedure owes all six.

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
kinds and names the record lists, so it needs no download. **It was not executed,
and its order is a design.** Its steps, in order:

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
| `argocd-is-not-on-the-inference-request-path` | tested | It reads source for a reference. No run has measured a request with Argo CD absent or stopped. It says nothing about what a running controller can do to serving objects |
| `the-pins-are-immutable-identifiers` | tested | It checks the form of each pin. It contacts no network, so it does not establish that upstream still serves these bytes |
| `bootstrap-acts-only-on-a-selected-and-verified-cluster` | not implemented | Owed by the change that implements the bootstrap |
| `the-manifest-is-verified-before-it-is-used` | not implemented | Owed by the change that implements the bootstrap |
| `images-run-at-their-pinned-digests` | not implemented | Owed by the change that implements the bootstrap. The mechanism is not decided, and the rule covers the moment of the check only |
| `a-foreign-argocd-installation-is-refused` | not implemented | Owed by the change that implements the bootstrap. The marker is a label on the namespace; the five cluster-scoped objects carry none |
| `removal-is-scoped-and-refuses-while-an-application-exists` | not implemented | Owed by the change that implements the bootstrap |
| `security-baseline-rows-precede-the-first-install` | not implemented | Owed by the change that implements the bootstrap. The security baseline has no row for Argo CD today |
| `gitops-state-is-not-caller-health` | review | Nothing records Argo CD state yet |

Four rules are tested, two are tested only as an absence, six are not implemented, and one is held by review.

## Out of scope

The record lists what this decision excludes: a workload Application, an
AppProject, or a desired-state directory; an app-of-apps Application; an
ApplicationSet object; a second cluster or a cluster registered with Argo CD; a
service mesh; Argo Rollouts; the Argo CD API server, web interface, single
sign-on, and notifications; and a high-availability installation.

## What this record does not establish

- That Argo CD is installed, runs, or reconciles anything.
- That the pinned manifest applies to either supported provider's cluster.
- That upstream still serves the pinned bytes, or that a pinned image is free of
  known vulnerabilities. No image named here was scanned.
- That the pinned release or images are authentic. No signature was verified.
- That a request is served while Argo CD is absent or stopped.
- That the removal leaves no residue, or that its order avoids a stuck deletion.
- That a container runs the pinned image after a later restart.
- That the core profile reconciles an Application. By inference from upstream
  source, no project exists after a core installation.
- That the host has the capacity to run Argo CD beside a release.
