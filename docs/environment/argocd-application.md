# The Argo CD Application

Status: **implemented, and executed on one provider.**
[ADR 0019](../architecture/decisions/ADR-0019-argocd-application-and-sync-policy.md)
decided one Argo CD Application, the project that holds it, and its sync policy.
On 2026-10-04 a procedure applied both on the `docker-desktop` provider. Argo CD
applied the generated release at the commit that `main` named, and one request
that a caller sent was answered.
[The record of that run](../proof/environment/v2-s3-002-pr2-argocd-application-run.md)
says what was observed. The procedure was not executed on `kind`.

> [!IMPORTANT]
> **What Argo CD reports is not a caller outcome.** The procedure prints a
> revision, a sync state, and a health state. They say what the controller did
> and what Kubernetes reports. The only evidence that the workload serves a
> request is a request that a caller sent.

| Property | Value |
|---|---|
| Application | `local-docker-desktop-support-assistant`, in [`infra/argocd/local-docker-desktop-support-assistant.yaml`](../../infra/argocd/local-docker-desktop-support-assistant.yaml) |
| Project | `inferops-workloads`, in [`infra/argocd/workloads-project.yaml`](../../infra/argocd/workloads-project.yaml) |
| Procedure | [`scripts/environment/argocd-application.sh`](../../scripts/environment/argocd-application.sh): `apply`, `verify`, `remove --confirm` |
| Source | The chart `charts/inferops-llm` of this repository, at the revision `main` names |
| Generated values | [`values.generated.yaml`](../../gitops/environments/local-docker-desktop/workloads/support-assistant/values.generated.yaml) of [the desired-state release](git-desired-state.md), read from Git |
| Destination | The namespace `inferops-release` on the cluster that Argo CD runs in |
| Sync policy | Automated, with self-heal. Pruning is disabled |
| Owner | `argocd-application`, in [the ownership inventory](../architecture/resource-ownership.md) |
| Requires | An Argo CD that [the bootstrap](argocd-bootstrap.md) installed, and the namespace and the claim that [the prerequisite layer](platform-prerequisites.md) creates |
| Tests | [`test_argocd_application.py`](../../tests/architecture/test_argocd_application.py), which reads files, and [`test_argocd_application_procedure.py`](../../tests/architecture/test_argocd_application_procedure.py), which executes the procedure against stubs |

## What a merge changes, and what it does not

```text
change a contract, a binding, or the platform defaults
        |
regenerate the release
        |
review the source change and the generated difference together
        |
the change is accepted into main        <- the promotion boundary
        |
Argo CD resolves main to the new commit, and applies it
```

On a cluster where the Application is applied:

- **A merge that changes the chart or the generated release changes the
  cluster.** Argo CD follows `main`. Review of that merge is the approval of a
  deployment. No second approval step exists.
- **A merge that changes one of the two manifests changes no cluster.** Argo CD
  does not read them from Git. An operator applies them with the procedure.
- **A merge does not change the API image.** The API image digest is not in Git.
  See [the values](#the-values).

No run observed a later commit of `main` being applied. The run resolved `main`
to one commit and applied it.

## The values

The Application gives the chart three things. A later one overrides an earlier
one, and a test holds that no two of them set the same value.

| Order | What | Where it comes from |
|---|---|---|
| 1 | The generated values | Git, at the followed revision, by the path of the desired-state release |
| 2 | Hand-written values | The Application manifest |
| 3 | The parameter `api.image.digest` | The operator, through `apply --api-image-digest` |

**The hand-written values set nothing that the generated values hold.** They
are the API image repository, the model alias, the licence identifier, how the
claim is filled and verified, and whether the collector runs. A test runs the
admission check of
[the renderer document](../domain/helm-values-renderer.md#hand-written-values)
over them.

**The API image digest is not in Git.** No InferOps API image is published. The
digest names an image that the operator built and loaded into the node, and
`scripts/environment/api-image.sh digest` prints it. Without the parameter the
chart refuses to render, and the Application reconciles nothing.

**On a claim that does not hold the model, the acquisition hook downloads it.**
The hand-written values select the download source, and the generated values
name the address. When the claim already holds the pinned artifact, the hook
verifies it and downloads nothing.

## The project

The project limits what an Application in it may read and change.

| Limit | Value |
|---|---|
| Source repositories | `https://github.com/asadhanif3188/InferOps.git` |
| Destinations | The namespace `inferops-release`, on the cluster that Argo CD runs in |
| Namespaced kinds | ConfigMap, Service, ServiceAccount, Deployment, Job, NetworkPolicy, Role, RoleBinding |
| Cluster-scoped kinds | None |

The eight kinds are the kinds of the committed render of the chart's real
profile, without the `helm test` pod. A test compares the two sets.

The project does not narrow the application controller. That controller holds a
cluster-wide grant, and a project or an Application that a person creates by hand
is not held by this file. The procedure refuses to run beside one.

## The sync policy

| Setting | Value | Effect |
|---|---|---|
| Automated sync | On | Argo CD applies a new commit of `main` without a person starting a sync |
| Self-heal | On | Argo CD reverts a change that somebody makes to an object the Application manages |
| Pruning | Off | An object that leaves the rendered chart stays until a person deletes it |
| Sync options | None | The controller does not create the namespace. Terraform owns it |

The procedure compares the live Application with these settings. A person who
edits the live object is found by `verify`.

The run made one manual change: it scaled the API Deployment from one replica to
two. Two seconds later the Deployment declared one replica again. That is a check
of the setting and not the drift experiment.

## The procedure

```sh
export INFEROPS_PROVIDER=docker-desktop
scripts/environment/argocd-application.sh apply --api-image-digest "$(scripts/environment/api-image.sh digest)"
scripts/environment/argocd-application.sh verify
scripts/environment/argocd-application.sh remove --confirm
```

| Operation | What it does | What it changes |
|---|---|---|
| `apply` | Applies the project and then the Application, with server-side apply. Adds the pin annotation to both, and the digest parameter to the Application. Waits up to 1,200 seconds until Argo CD reports a succeeded sync at the commit it resolved. Compares the live Application with the decision | The two objects in `argocd`. Argo CD then creates the release objects |
| `verify` | Checks the marker of both objects. Compares the live source, destination, sync policy, and finalizers with the decision. Prints the revision and the states that Argo CD reports, and the workload objects by name | Nothing in the cluster |
| `remove` | Deletes the Application with a cascade, waits until no release object remains, and deletes the project. Confirms that the claims are unchanged | The two objects, and the release objects that Argo CD applied |

`apply` on objects that this procedure created applies the same bytes again. A
change of the API image digest is a second `apply`.

The procedure prints the SHA-256 of itself, of `lib.sh`, and of the two
manifests. It records each manifest's SHA-256 on the object it applies.

## Refusals

Every refusal comes before the first mutation. A query that did not answer is
not read as an absence.

| Refusal | Applies to | Condition |
|---|---|---|
| `target-not-selected-or-not-verified` | apply, verify, remove | No provider is selected, or the reachable cluster is not the selected one. [The provider contract](local-cluster-provider-contract.md) states the checks |
| `api-image-digest-not-given` | apply | No `--api-image-digest`, or a value that is not `sha256:` and 64 lowercase hexadecimal characters |
| `argocd-not-installed-by-the-bootstrap` | apply, verify, remove | No namespace `argocd` exists, or it does not carry the bootstrap marker and a recorded manifest SHA-256, or it is being deleted |
| `destination-not-prepared` | apply | The namespace `inferops-release` or the claim `inferops-model-cache` does not exist. The procedure creates neither |
| `helm-release-present` | apply | A Helm release named `inferops` is recorded in the destination namespace |
| `foreign-argocd-custom-resource` | apply, remove | An Application, ApplicationSet, or AppProject object exists that this procedure did not create. An object with one of the two names and without the marker is not adopted |
| `application-controller-not-ready` | remove | The application controller reports no ready replica. It performs the cascade |

`verify` also fails, without a refusal identifier, when the two objects do not
both exist with the marker, or when the live Application differs from the
decision.

Each refusal is executed against stubs. The run executed four of them with the
real tools: no provider, no digest, no Argo CD, and a recorded Helm release.

## Removal

1. Refuse, as the table above states.
2. Add the resource finalizer to the Application, and delete it. Argo CD then
   deletes the objects it applied.
3. Wait up to 600 seconds until no object with the release label remains.
4. Delete the project.
5. Confirm that the claims in `inferops-release` are unchanged.

The removal does not delete the namespace, a claim, or the Argo CD installation.
[The bootstrap removal](argocd-bootstrap.md#removal) refuses while the Application
or the project exists, so a full removal runs this procedure first. The run
observed that refusal.

The committed Application carries no resource finalizer. Deleting the Application
object by hand deletes no workload object.

Known gaps:

- The cascade deletes what Argo CD tracks at that moment. An object that left
  the chart earlier is found only when it carries the release label.
- A cascade that does not finish keeps the Application. No recovery is decided.
- The checks and the deletions are not atomic.

## Helm and Argo CD

The same chart has two delivery paths. An operator runs `helm install` through
[the release lifecycle](helm-release-lifecycle.md), or Argo CD renders the chart
and applies the result.

- **They do not run in one namespace at one time.** `apply` refuses while a Helm
  release of the same name is recorded. Nothing stops `helm install` after the
  Application is applied.
- **Argo CD records no Helm release.** `helm list` shows nothing for an applied
  Application, and `helm rollback` does not apply to it. A rollback is a Git
  change that is accepted into `main`.
- **The chart's `pre-install` hook runs before the sync.** In the run, Argo CD
  ran the acquisition Job and deleted it when it succeeded.
- **The chart's `helm test` pod is not created.**

## Ownership

| Row of [the inventory](../architecture/resource-ownership.md) | Owner | What it is |
|---|---|---|
| `argocd-application-manifests` | `repository` | The two files under `infra/argocd/` |
| `argocd-workload-application` | `argocd-application` | The project and the Application, in the namespace `argocd` |

The bootstrap owns the namespace `argocd` and does not own these two objects.
Terraform owns the destination namespace and the claim. The release objects are
the `release` rows of the inventory, and ADR 0019 D8 says how the two delivery
paths share them.

## Not applied yet

| Not applied | Why | What it needs |
|---|---|---|
| A release path for `kind` | No bootstrap and no Application ran there | A run on `kind`, and a declared release for the `local-kind` binding |
| A published API image | The API image is a contributor's local build | A published image, pinned where a contract or a platform default owns it |
| An observation of a later commit of `main` being applied | The run applied one commit | A run that merges a change while the Application is applied |
| Pruning | Disabled by decision | A bounded experiment that needs deletion to be reconciled |
| A break-glass procedure | Self-heal reverts a manual change | A decision on how an operator suspends reconciliation |
| The first experiment's real-deployment part | It runs under its own frozen revision | A freeze revision that names this Application and the desired-state path |

## What this does not establish

- **That the workload serves requests.** One request was answered after each of
  two applies. That is one observation each, with no load and no bound.
- **Anything a sync state or a health state appears to say about a caller.**
- **That Argo CD applies a later commit of `main`**, or how long it takes to
  notice one.
- **That self-heal holds under load or within a bound.** One manual change was
  reverted once.
- **Anything about `kind`.**
- **That the API image is the one a commit describes.** The digest is not in Git.
- **That a merge to `main` was reviewed.**
- **That the project limits the controller.** It limits one Application.
- **Availability, latency, capacity, or cost.** Nothing was measured.
- **A result of the first experiment.** This run is not a run of it.

## Validation

```sh
uv run --locked python -m pytest tests/architecture/test_argocd_application.py tests/architecture/test_argocd_application_procedure.py tests/architecture/test_argocd_bootstrap.py -q
uv run --locked python -m tools.gitops_desired_state --check
bash -n scripts/environment/argocd-application.sh
```
