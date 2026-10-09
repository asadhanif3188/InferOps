# The Argo CD Application

Status: **implemented, and executed on one provider.**
[ADR 0019](../architecture/decisions/ADR-0019-argocd-application-and-sync-policy.md)
decided one Argo CD Application, the project that holds it, and its sync policy.
On 2026-10-04, in three runs on the `docker-desktop` provider, a procedure applied
both, and Argo CD applied the generated release six times at one commit of
`main`. Five of six caller requests were answered. One returned no response, and
[the record of the runs](../proof/environment/v2-s3-002-pr2-argocd-application-run.md)
says what is known about it. The procedure was not executed on `kind`.

> [!IMPORTANT]
> **What Argo CD reports is not a caller outcome.** The procedure prints a
> revision, a sync state, and a health state. They say what the controller did
> and what Kubernetes reports. The only evidence that the workload serves a
> request is a request that a caller sent.

| Property | Value |
|---|---|
| Application | `local-docker-desktop-support-assistant`, in [`infra/argocd/local-docker-desktop-support-assistant.yaml`](../../infra/argocd/local-docker-desktop-support-assistant.yaml) |
| Project | `inferops-workloads`, in [`infra/argocd/workloads-project.yaml`](../../infra/argocd/workloads-project.yaml) |
| Procedure | [`scripts/environment/argocd-application.sh`](../../scripts/environment/argocd-application.sh): `apply`, `verify`, `observe`, `remove --confirm` |
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

No run observed a later commit of `main` being applied. Each run resolved `main`
to the same commit and applied it.

**The Application follows a name, and Argo CD reports a commit.** `main` is not an
identity. The commit that `verify` prints is one. Given that commit,
[the provenance tool](desired-state-provenance.md) prints the release identifier,
the recorded digests, and the chart version of the release that the commit holds.
It reads Git and no cluster. It does not cover the hand-written values or the API
image digest, because neither is read from that commit.

**The states that Argo CD reports can be collected.** Since `V2-S3-003-PR2` the
procedure has an `observe` operation. It reads the Application a bounded number
of times and changes nothing.
[The reconciliation evidence document](reconciliation-evidence.md) describes the
record that a tool builds from those reads. A field that was not reported stays
not reported in that record. On 2026-10-05 `observe` ran on the
`docker-desktop` provider, in two runs, beside an apply and beside a removal in
each, and beside one apply of an attempt that was aborted.
[The record of those runs](../proof/environment/v2-s3-003-pr2-reconciliation-observation-run.md)
says what Argo CD reported at each sample.

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

**The single-runtime baseline restates these inputs.** Since `V2-S4-005-PR1`,
[the baseline profile](single-runtime-baseline-profile.md) states a chart, a release
name, a namespace, and hand-written values in its own install description, and a
check compares them with the ones that this manifest states. A change to one of them
here is made in that description too, in the same change, or
`python -m tools.baseline_profile --check` refuses. The check reads the members of
`spec`, `spec.source`, `spec.source.helm`, and `spec.destination` that this manifest
states today. A new member there, such as a Helm parameter, refuses the comparison
until the tool reads it. No procedure reads the baseline's description, and it
installs nothing.

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
| Namespaced kinds | ConfigMap, Service, ServiceAccount, Deployment, Job, NetworkPolicy, PodDisruptionBudget, Role, RoleBinding |
| Cluster-scoped kinds | None |

Eight of the nine kinds are the kinds of the committed render of the chart's real
profile, without the `helm test` pod. That render has one replica for each tier.
The ninth kind is PodDisruptionBudget. Since chart `0.6.0` the chart renders one
for a tier of two or more replicas, and the desired-state release declares two
replicas for each tier. A test compares the sets.

The project is not desired state. A cluster where the project was applied before
it admitted PodDisruptionBudget keeps the eight kinds until an operator runs
`apply` again. Argo CD documents that a project restricts the kinds that an
Application may deploy. A sync of a render that holds another kind is expected to
fail as a whole, and not only for that kind. So on such a cluster, the Application
would apply neither a revision that renders a budget nor a later one, until the
project is applied again. **Apply the project before the revision reaches the
branch that the Application follows.** This was not observed. The one cluster that was asked
when the kind was added, `docker-desktop` on 2026-10-09, listed no `argocd`
namespace.

The sync policy does not prune. So a budget that leaves the render, when a tier
goes back to one replica, stays in the cluster until a person deletes it:
[the disruption budgets](disruption-budgets.md#under-the-argo-cd-application).

The project does not narrow the application controller. That controller holds a
cluster-wide grant, and a project or an Application that a person creates by hand
is not held by this file. The procedure refuses to run beside one.

The project admits Role and RoleBinding, because the chart's collector needs
them. Whoever can change `main` can therefore bind a role inside the destination
namespace, on a cluster where the Application is applied.

## The sync policy

| Setting | Value | Effect |
|---|---|---|
| Automated sync | On | Argo CD applies a new commit of `main` without a person starting a sync |
| Self-heal | On | Argo CD reverts a change that somebody makes to an object the Application manages |
| Pruning | Off | An object that leaves the rendered chart stays until a person deletes it |
| Sync options | None | The controller does not create the namespace. Terraform owns it |

The procedure compares the whole spec of the live Application and of the live
project with the committed manifests. A person who edits a live object is found
by `verify`.

Each run made one manual change: it scaled the API Deployment from one replica
to two. The Deployment declared one replica again within 2 to 4 seconds, read
once a second. That is a check of the setting and not the drift experiment.
The desired state declared one API replica at each of those runs. Since
`V2-S4-001-PR1` it declares two, so a scale to two is no longer a change, and the
same check needs another count. Since `V2-S4-002-PR1` it also declares two serving
runtime replicas. One run on 2026-10-08 applied the Application against the
two-replica state. It made no manual change, so that check was not repeated:
[the record](../proof/environment/v2-s4-002-pr2-validation.md).

## The procedure

```sh
export INFEROPS_PROVIDER=docker-desktop
scripts/environment/argocd-application.sh apply --api-image-digest "$(scripts/environment/api-image.sh digest)"
scripts/environment/argocd-application.sh verify
scripts/environment/argocd-application.sh remove --confirm
```

| Operation | What it does | What it changes |
|---|---|---|
| `apply` | Applies the project and then the Application, with server-side apply. Adds the pin annotation to both, and the digest parameter to the Application. Builds both documents before it applies either. Waits up to 1,200 seconds until Argo CD reports a succeeded sync at the commit it resolved, for the digest it was given. Compares the whole live spec of both objects with the committed manifests | The two objects in `argocd`. Argo CD then creates the release objects |
| `verify` | Checks the marker of both objects. Compares the whole live spec of each with the committed manifest, the SHA-256 that each records with the committed file, and the finalizers. Reads the digest from the live Application. Prints the revision and the states that Argo CD reports, and the workload objects by name | Nothing in the cluster |
| `observe` | Reads the Application as JSON, and the kind, name, and labels of the release objects, `--samples` times, with a wait of `--interval` seconds after each sample. Writes what each read returned, and records a read that did not answer as unanswered. Judges nothing. Does not require that the Application exists | Nothing in the cluster. A new directory under `.artifacts/` |
| `remove` | Deletes the Application with a cascade, waits until no release object remains, and deletes the project. Confirms that the claims are unchanged | The two objects, and the release objects that Argo CD applied |

`apply` on objects that this procedure created applies the same bytes again. A
change of the API image digest is a second `apply`.

The procedure prints the SHA-256 of itself, of `lib.sh`, and of the two
manifests. It records each manifest's SHA-256 on the object it applies.

## Refusals

Every refusal named here comes before the first mutation. The two refusals of
`observe` also come before the target is verified, with one exception: a
directory that another observation creates while this one starts is refused
after the verification. A query that did not
answer is not read as an absence.

| Refusal | Applies to | Condition |
|---|---|---|
| `target-not-selected-or-not-verified` | apply, verify, remove | No provider is selected, or the reachable cluster is not the selected one. [The provider contract](local-cluster-provider-contract.md) states the checks |
| `api-image-digest-not-given` | apply | No `--api-image-digest`, or a value that is not `sha256:` and 64 lowercase hexadecimal characters |
| `argocd-not-installed-by-the-bootstrap` | apply, verify, remove | No namespace `argocd` exists, or it does not carry the bootstrap marker and a recorded manifest SHA-256, or it is being deleted |
| `destination-not-prepared` | apply | The namespace `inferops-release` or the claim `inferops-model-cache` does not exist. The procedure creates neither |
| `helm-release-present` | apply | A Helm release named `inferops` is recorded in the destination namespace |
| `foreign-argocd-custom-resource` | apply, verify, remove | An Application, ApplicationSet, or AppProject object exists that this procedure did not create. An object with one of the two names and without the marker is not adopted |
| `application-controller-not-ready` | remove | The application controller reports no ready replica. It performs the cascade |
| `live-application-differs` | remove | The live Application names another project, destination server, or destination namespace. A cascade deletes what the live Application manages |
| `observation-bounds-not-given` | observe | No `--samples` from 1 to 120, no `--interval` from 1 to 30, or no `--into` name of up to 63 lowercase letters, digits, and hyphens. No default is applied |
| `observation-directory-exists` | observe | The directory that `--into` names exists, or another observation created it while this one started. An observation does not write into the directory of another one |

`verify` and `apply` also fail, without a refusal identifier, when a live object
differs from the committed manifest or records another SHA-256. `verify` fails
when the two objects do not both exist with the marker. `remove` stops at the
argument check without `--confirm`.

Each refusal is executed against stubs. Each run of 2026-10-05 executed the two
refusals of `observe` on the host, one case of each. The refusal of a directory
that is created during the start was executed nowhere. Each run of 2026-10-04
executed four of the others on the host: no provider and no digest, which stop before any cluster call, and no
Argo CD and a recorded Helm release, which read the cluster. Of
`argocd-not-installed-by-the-bootstrap`, only the case of no namespace ran.

## Removal

1. Refuse, as the table above states.
2. Add the resource finalizer to the Application, and delete it. Argo CD then
   deletes the objects it applied.
3. Wait up to 600 seconds until no object with the release label remains.
4. Delete the project.
5. Confirm that the claims in `inferops-release` are unchanged.

The removal does not delete the namespace, a claim, or the Argo CD installation.
[The bootstrap removal](argocd-bootstrap.md#removal) refuses while the Application
or the project exists, so a full removal runs this procedure first. Each run
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
- **Argo CD records no Helm release.** After an apply, the destination namespace
  held no Helm release record. `helm list` was not run. A rollback is a Git
  change that is accepted into `main`.
- **The chart's `pre-install` hook runs before the sync.** In each run, Argo CD
  reported the acquisition Job as a hook that succeeded, and the Job was not in
  the later listing of the release objects.
- **No pod from the chart's `helm test` hook was listed.**
- **The bootstrap procedure prints that no Application exists, and does not
  check.** The line can be false after an install over a live installation.

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
| A break-glass procedure | Self-heal reverts a manual change. [The boundary for a manual change](reconciliation-evidence.md#the-boundary-for-a-manual-change) is stated, and it decides no mechanism | A decision on how an operator suspends reconciliation |
| The acquisition job within its memory limit on Kubernetes v1.36.1 | On 2026-10-05, one preparation that copies the artifact from a seed image failed with `BackoffLimitExceeded`. The operator read the pod by hand and saw the container stopped as `OOMKilled` at the chart's limit of 128Mi. [The record of the runs](../proof/environment/v2-s3-003-pr2-reconciliation-observation-run.md) holds what was kept. The same preparation completed twice at a limit of 2Gi, and the Application's own job completed after it in both runs. The cause was not investigated | An investigation, and a chart change under a freeze revision |
| The first experiment's real-deployment part | It runs under its own frozen revision. Since 2026-10-06 [freeze revision 3](../proof/experiments/v2-e01/freeze-r3.v1alpha1.json) names this Application and the desired-state path. The part ran once under it on 2026-10-06, on `docker-desktop`, with one completion request, and PASSED: [run `20261006-e01-d-1`](../proof/experiments/v2-e01/runs/20261006-e01-d-1/result.md). The change that ran it registered no claim. Since `V2-S3-005-PR1`, dated 2026-10-07, one register claim holds that result, at `C2`, bounded to that one run. The register states what the claim does not establish | A later run, for each thing the claim does not establish |

## What this does not establish

- **That the workload serves requests.** Five of six requests were answered, one
  after each apply, in three runs. One returned no response. Each is one
  observation, with no load and no bound.
- **Anything a sync state or a health state appears to say about a caller.**
- **That Argo CD applies a later commit of `main`**, or how long it takes to
  notice one.
- **That self-heal holds under load or within a bound.** One manual change was
  reverted once in each run.
- **That a live object which differs from the committed one is found on a
  cluster.** Every comparison on a cluster found them equal.
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
