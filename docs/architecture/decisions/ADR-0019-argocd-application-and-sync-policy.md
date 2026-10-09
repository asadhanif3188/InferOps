# ADR 0019: One Argo CD Application reconciles the generated release, with self-heal and without pruning

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-10-04 |
| Date accepted | 2026-10-04, for the decisions the table below marks accepted |
| Decision owner | [`repository-maintainer`](../../governance/decision-authority.md) |
| Supersedes | None |
| Amends | None. It decides what [ADR 0017](ADR-0017-argocd-bootstrap-and-ownership.md) R5, R6, and the second half of D9 left to the change that adds the first Application, and what [ADR 0018](ADR-0018-git-desired-state-layout.md) D3 and D8 left to it. Each of those records gains a dated note. The ownership inventory gains one owner, one lifecycle, and two rows |
| Superseded by | None |

> [!IMPORTANT]
> This record decides the one Argo CD Application of V2, the project that holds
> it, its sync policy, and the procedure that applies it.
>
> The Application reads the chart and the generated values of
> [the desired-state release](../../environment/git-desired-state.md) from this
> repository, at the revision that `main` names. Sync is automated, with
> self-heal. Pruning is disabled.
>
> **It was executed on one provider.** On 2026-10-04, in three runs on
> `docker-desktop`, Argo CD applied the release six times at one commit of
> `main`. Five of six caller requests were answered. One returned no response,
> and [the record of the runs](../../proof/environment/v2-s3-002-pr2-argocd-application-run.md)
> says what is known about it. The procedure was not executed on `kind`.
>
> **What Argo CD reports is not a caller outcome.** A sync state and a health
> state say what the controller did and what Kubernetes reports. Neither says
> that a request was answered.
>
> **One value is not in Git.** No InferOps API image is published. The API image
> digest names a build on the operator's host, and the operator gives it to the
> procedure. A merge to `main` therefore does not change the API image.
>
> The rules are explained in
> [the Argo CD Application document](../../environment/argocd-application.md).

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | One Application for one release path: the reference workload on the `local-docker-desktop` binding | **Accepted** | A test pins the one desired-state release and the one Application, and holds the Application's name and values path to that release |
| D2 | The Application and its project are two committed manifests under `infra/argocd/`. They are not desired state: a repository procedure applies them, and it has one owner | **Accepted** for `docker-desktop`. **Proposed** for `kind` | The ownership inventory. Three runs applied and removed both on `docker-desktop`. No run on `kind` |
| D3 | The project admits one source repository, one destination namespace, the eight namespaced kinds the chart's real profile renders, and no cluster-scoped kind | **Accepted** | A test compares the project with the committed render and with the kinds another owner holds. Each run synced the release inside these limits |
| D4 | The Application follows `main`. The accepted Git change is the promotion boundary | **Accepted**, with a stated limit | Each run resolved `main` to the same commit and applied it. No run observed a later revision of `main` being applied |
| D5 | The values are the generated values, read from Git by path, and hand-written values inside the Application. The hand-written values set nothing that the generated values hold. The API image digest is one Helm parameter that the operator supplies | **Accepted**, with a stated limit | Two tests on the hand-written values. The digest is outside Git, and R1 records it |
| D6 | Sync is automated, with self-heal. Pruning is disabled. No sync option, retry, or ignored difference is set | **Accepted** | A test compares the whole policy as one value. The procedure compares the whole live spec with the committed manifest. Each run observed one manual change being reverted |
| D7 | The committed Application carries no resource finalizer. The removal adds one, so that a removal deletes the workload objects and an accident does not | **Accepted** for `docker-desktop`. **Proposed** for `kind` | Each of three runs removed the Application twice, and no workload object remained. The namespace and the claim remained |
| D8 | A Helm release and the Application do not own the same objects at one time. The `release` rows of the inventory keep their owner | **Accepted** as a rule, held in one direction | The procedure refuses while a Helm release of the same name is recorded. Nothing stops `helm install` after the Application is applied |
| D9 | No InferOps record derives a caller outcome from a sync state or a health state | **Accepted** as a rule | The procedure prints the boundary with each report, and a test holds that. Review holds the rule for records |
| D10 | Argo Rollouts, automatic rollback, an ApplicationSet, an app-of-apps Application, a second source, a sync window, and notifications are out of scope | **Accepted** as scope | Tests refuse a rollout object, a second Argo CD custom resource, and any field of the Application beyond the four that were decided |

Eight decisions are accepted. D2 and D7 are accepted for `docker-desktop` and
proposed for `kind`. That is why this record is accepted in part.

## Context

[ADR 0017](ADR-0017-argocd-bootstrap-and-ownership.md) selected Argo CD and
decided its installation. [ADR 0018](ADR-0018-git-desired-state-layout.md)
decided the directory that holds the generated release. Neither created an
Application, so an installed Argo CD reconciled nothing.

Both records left items to this change:

- **ADR 0017 D9.** A test held that no Argo CD custom resource was committed.
  It established an absence. The first Application owed a restriction on what
  it may target.
- **ADR 0017 R5.** Argo CD renders a chart and applies the result. It does not
  run `helm install`. The inventory's `release` rows name Helm as the tool that
  creates and destroys them.
- **ADR 0017 R6.** The pinned core installation holds no project, by inference,
  and an Application must name one.
- **ADR 0018 D3.** The generated values do not install the chart alone. The
  chart requires four values that no contract owns. Where those hand-written
  values live for an installed release was open.
- **ADR 0018 D8.** The sync policy and the followed revision were not decided.

## Decision criteria

In order:

1. **One owner for every object**, and no object that two tools reconcile.
2. **The accepted Git change is the approval.** No second approval step and no
   second copy of a generated value.
3. **The controller's report is not the caller's result.**
4. **The Application reaches only what one release needs.**
5. **A removal deletes what the Application applied and nothing else.**
6. **The smallest configuration that serves one release path.**

## D1 — One Application for one release path

**Accepted.**

The Application is `local-docker-desktop-support-assistant`. Its name is the
binding name and the workload identifier of the one desired-state release. It
reads that release and no other.

A second release path is a second declared release and a second Application,
each added on purpose. No ApplicationSet generates one, and no Application
manages another.

## D2 — Two manifests, applied by a procedure

**Accepted for `docker-desktop`. Proposed for `kind`.**

The two manifests are
[`infra/argocd/workloads-project.yaml`](../../../infra/argocd/workloads-project.yaml)
and
[`infra/argocd/local-docker-desktop-support-assistant.yaml`](../../../infra/argocd/local-docker-desktop-support-assistant.yaml).
[`scripts/environment/argocd-application.sh`](../../../scripts/environment/argocd-application.sh)
applies, verifies, and removes them.

**The manifests are not desired state.** Argo CD does not read them from Git. A
merge that changes one changes no cluster until an operator runs the procedure
again. The desired state that a merge changes is the chart and the tree under
`gitops/`.

The ownership inventory gains the owner `argocd-application`, with the lifecycle
`reconciliation`. It owns one row, `argocd-workload-application`: the two objects
in the namespace `argocd`. The bootstrap owns that namespace and does not own
these two objects. A second row, `argocd-application-manifests`, is the two
files, owned by `repository`.

The procedure is a mutating workflow under
[ADR 0011](ADR-0011-external-local-cluster-provider-contract.md). It selects and
verifies the cluster before its first read. It requires an Argo CD that the
bootstrap installed, and it refuses any other Application, ApplicationSet, or
AppProject object. It marks each object with a label and with the SHA-256 of the
committed manifest.

| Alternative | Assessment |
|---|---|
| **Under `infra/argocd/`, applied by a procedure** | **Selected.** The two objects are platform configuration for one cluster, with one owner, as the prerequisite layer is |
| Under `gitops/` | Not selected. That tree holds what a merge changes in a cluster, and ADR 0018 D3 keeps hand-written files out of it. An Application there would read as reconciled from Git, and it is not |
| An Application that applies the two manifests from Git | Not selected. It is an app-of-apps Application, which ADR 0017 D13 excludes |
| Under `deploy/` | Not selected. A test holds that no file under a directory a request is served from names the controller |
| `kubectl apply` by hand | Not selected. Nothing would verify the target, refuse a foreign object, or supply the digest |

## D3 — The project

**Accepted.**

The project is `inferops-workloads`. It admits:

- one source repository, `https://github.com/asadhanif3188/InferOps.git`;
- one destination: the namespace `inferops-release` on the cluster that Argo CD
  runs in;
- eight namespaced kinds: ConfigMap, Service, ServiceAccount, Deployment, Job,
  NetworkPolicy, Role, and RoleBinding;
- no cluster-scoped kind.

The eight kinds are the kinds of the committed render of the chart's real
profile, without the `helm test` pod. A test compares the two sets, so a chart
change that adds a kind fails the suite until the project is changed on purpose.

> **Amended 2026-10-09 (`V2-S4-004-PR1`).** The project now admits nine namespaced
> kinds: the eight above, and PodDisruptionBudget in the group `policy`. Chart
> `0.6.0` renders one budget for a tier of two or more replicas, and the
> desired-state release declares two replicas for each tier. The committed render
> of the chart's real profile has one replica for each tier and still holds the
> eight kinds. So the test now compares the project with those eight kinds and
> the one budget kind. The rule of this decision is not changed: the project
> admits the kinds that the release renders, and it was changed on purpose. The
> other limits of the project are not changed. The one cluster that was asked
> when the kind was added, `docker-desktop`, listed no `argocd` namespace. The text above is this record's accepted text, and "eight"
> in the rest of this record describes the project as it was accepted.

**This is the restriction that ADR 0017 D9 left open.** Terraform owns a
Namespace and a claim. The bootstrap owns a Namespace, three definitions, a
cluster role and its binding, and the objects in `argocd`. The project admits no
cluster-scoped kind, no claim, and no destination in `argocd`. The one
Application is therefore refused each of those objects.

**The restriction holds for an Application in this project. It does not narrow
the controller.** The application controller keeps the cluster-wide grant that
ADR 0017 R1 records. A person who can write an object in `argocd` can create a
second project that admits everything. The project also admits Role and
RoleBinding, because the chart's collector needs them. The Application is
therefore able to bind a role inside the destination namespace, a cluster-wide
role included, and whoever can change `main` can make it do so.

The test compares the project with the committed render of the real profile. It
does not render the chart with the Application's own values. A chart change that
adds a kind only under those values would pass the test and fail the sync.

The project also answers ADR 0017 R6. The run found no project after the
bootstrap, as that record inferred, and the Application synced in this one.

## D4 — The followed revision

**Accepted, with a stated limit.**

The Application follows `main`. Argo CD resolves `main` to a commit, and applies
the chart and the generated values of that commit.

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

The accepted Git change is the approval. Nobody approves a second time, and no
second promotion stage exists.

| Alternative | Assessment |
|---|---|
| **`main`** | **Selected.** The desired state is the content of `main`, as ADR 0018 D5 decided |
| A pinned commit | Not selected. Each promotion would then need a second change, to the Application, that an operator applies by hand. That second step would become the real approval |
| A tag | Not selected. No release process creates one for a desired-state change |

**The limit.** Each run resolved `main` to the same commit and applied it. No run observed
`main` moving to a later commit and Argo CD applying that commit. How long Argo CD
takes to notice a new commit was not measured. The repository server reads the
remote without a credential, and no commit signature is verified.

## D5 — The values

**Accepted, with a stated limit.**

The Application gives the chart three things, in this order of precedence, lowest
first:

1. **The generated values**, by path:
   `/gitops/environments/local-docker-desktop/workloads/support-assistant/values.generated.yaml`.
   Argo CD reads the file from Git at the followed revision. A test derives the
   path from the declared release.
2. **Hand-written values**, inside the Application. They are the values that no
   contract, binding, or platform default owns: the API image repository, the
   model alias, the licence identifier, how the claim is filled and verified,
   and whether the collector runs.
3. **One Helm parameter**, `api.image.digest`, which the procedure adds when it
   applies the Application.

**No hand-written value sets a generated value.** A test runs the admission
check of [the renderer document](../../domain/helm-values-renderer.md#hand-written-values)
over the hand-written values, and a second test compares their paths with the
paths of the committed generated file. The hand-written values are also equal to
the admitted test fixture without its digest, so one shape exists and not two.

This closes the open part of ADR 0018 D3. The hand-written values are in the
Application. The tree under `gitops/` still holds generated files only.

**The limit: the API image digest is not in Git.** No InferOps API image is
published. The digest names an image that the operator built and loaded into the
node. A merge to `main` does not change it, and a change of the API image is a
second run of the procedure. The Application file without the parameter does not
render: the chart refuses a release with no API image digest.

**On an empty claim, the acquisition hook downloads the model.** The
hand-written values select the download source. When the claim already holds the
pinned artifact, the hook verifies it and downloads nothing. Each run used a claim
that was filled from a local image. The hook's log, read once in each run, said
that it acquired nothing.

| Alternative | Assessment |
|---|---|
| **Hand-written values inside the Application, and the digest as a parameter** | **Selected.** One file holds every hand-written value, and the host-specific one is supplied by the operator who built the image |
| A hand-written values file in Git, read by path | Not selected. It would need a digest that names one host's build, or a placeholder that does not install |
| The digest written into the generated values | Not selected. No contract owns it, and the renderer does not read a host |

## D6 — The sync policy

**Accepted.**

```yaml
syncPolicy:
  automated:
    prune: false
    selfHeal: true
```

- **Automated sync.** Argo CD applies a new commit of `main` without a person
  starting a sync.
- **Self-heal.** Argo CD reverts a change that somebody makes to an object the
  Application manages. The later drift experiment needs this setting.
- **No pruning.** An object that leaves the rendered chart stays in the cluster
  until a person deletes it. A reconciliation therefore deletes no object.

Nothing else is set. No `CreateNamespace` option exists, so the controller does
not create the namespace that Terraform owns. No retry, sync window, or ignored
difference exists.

The procedure compares the whole spec of the live Application and of the live
project with the committed manifests after it applies them, and `verify`
compares them again. It also compares the SHA-256 that each object records with
the committed file. A person who edits a live object, to enable pruning or to
admit another kind, is found by `verify`. That finding is executed against
stubs. On a cluster, every comparison found the objects equal.

**One manual change was observed in each run.** The driver scaled the API
Deployment from one replica to two. The Deployment declared one replica again
within 2 to 4 seconds, read once a second, and the last operation that Argo CD
reported was an automated one that succeeded. This is a check of the setting.
It is not the drift experiment: it sent no request, applied no bound, and has one
observation in each run.

## D7 — Removal

**Accepted for `docker-desktop`.**

The committed Application carries no resource finalizer. A person who deletes the
Application object, or a bootstrap removal that deleted its definition, deletes
no workload object.

`argocd-application.sh remove --confirm` does the opposite on purpose:

1. Refuse when the target is not selected and verified, when the bootstrap did
   not install Argo CD, when another Argo CD custom resource exists, when the
   application controller reports no ready replica, and when the live Application
   names another project or destination.
2. Add the resource finalizer to the Application, and delete it. Argo CD then
   deletes the objects it applied.
3. Wait until no object that carries the release label remains.
4. Delete the project.
5. Confirm that the claims in the namespace are unchanged.

It does not delete the namespace, a claim, or the Argo CD installation. The
bootstrap removal refuses while the Application or the project exists, so the
order of a full removal is this procedure first.

**Known gaps.** The cascade deletes what Argo CD tracks at that moment. An object
that left the chart earlier, and stayed because pruning is disabled, is found
only when it carries the release label. A cascade that does not finish keeps the
Application, and no recovery is decided.

## D8 — Helm and the Application

**Accepted as a rule, held in one direction.**

The same chart has two delivery paths: an operator runs `helm install`, or Argo
CD renders and applies it. They create the same objects in the same namespace.

**The two paths do not run in one namespace at one time.** The procedure reads
the Helm release records in the destination namespace, by name, and refuses
while one names this release. Each run observed that refusal. Nothing stops an
operator who runs `helm install` after the Application is applied, and R4
records that.

**The `release` rows keep `helm` as their owner.** Their `createdBy` and
`destroyedBy` describe the Helm path. On a cluster where the Application is
applied, Argo CD creates the objects and the procedure's removal deletes them.
The inventory's description and the ownership document say so. The rows are not
split, because the objects are the same objects.

Two details of ADR 0017 R5 were observed in the runs:

- **The chart's `pre-install` hook runs.** Argo CD reported the acquisition Job
  and its ServiceAccount as hooks that succeeded before the sync. Neither was in
  the later listing of the release objects.
- **No pod from the chart's `helm test` hook was listed.** The project does not
  admit Pod.

Argo CD records no Helm release. After an apply, the destination namespace held
no Helm release record. `helm list` was not run. By upstream's description,
`helm rollback` does not apply to an Application.

## D9 — Reconciliation state is not caller truth

**Accepted as a rule.**

Argo CD reports a revision, a sync state, and a health state. The sync state says
whether the live objects match the rendered chart. The health state is computed
from what Kubernetes reports. Neither is evidence that a request was answered.

- The procedure prints each report with the sentence that it is not a caller
  outcome, and a test holds that.
- The procedure waits for a succeeded sync operation. It does not wait for a
  health state, and no result of it depends on one.
- In the runs, each caller request was sent through a port-forward to the API
  Service, by a command that reads nothing from Argo CD.
- No serving component reads Argo CD. The test of ADR 0017 D10 still holds, and
  now names the four build files that may name the controller.

Review holds the rule for records: no InferOps record states a caller outcome on
the strength of a sync state or a health state.

## D10 — Scope

**Accepted as scope.**

This record adds no Argo Rollouts object, no analysis, and no automatic rollback.
A rollback is a Git change that is accepted into `main`. It adds no
ApplicationSet, no app-of-apps Application, no second source, no sync window, no
notification, and no cluster registration. It adds no release path for `kind`.

## Consequences

- **A merge to `main` that changes the chart or the generated release changes a
  cluster on which the Application is applied.** Review of that change is the
  approval of a deployment. ADR 0017 and ADR 0018 stated this as a consequence
  to come. It now applies.
- **A manual change to a managed object is reverted.** An operator who must
  change an object by hand removes the Application first. A break-glass
  procedure is not decided here.
- **Reconciliation needs the cluster to reach the Git remote.** Serving does not.
- **The absence test of ADR 0017 is replaced.** It now holds that the two
  manifests are the only Argo CD custom resources in the repository.
- **A change to the chart that adds a kind fails the suite** until the project
  admits it.
- **The security baseline changes one control.** The control that held an
  absence is replaced by one that holds the restriction, and the threat and the
  deferred risk that named the absence are reworded. No row is added.

## Compatibility impact

No published contract, schema, or API changes. No chart file, Terraform file, or
workflow changes. `lib.sh` and the bootstrap procedure do not change. No file
that the first experiment's freeze record pins changes. The ownership inventory
gains one owner, one lifecycle, and two rows, and loses none. Two manifests, one
script, and two test modules are added.

## Security considerations

This record asserts no new security property.

- **A Git remote is now a path into a cluster**, on a cluster where the
  Application is applied. Whoever can change `main` can change what runs in the
  destination namespace, within the eight kinds. The repository server reads the
  remote without a credential and verifies no signature. This repository does
  not claim that branch protection is configured.
- **The project restricts one Application and not the controller.** See D3 and
  R3.
- **The marker is a label and an annotation.** A person who can write an object
  in `argocd` can write both. It prevents an accident and not an impersonation.
- **The procedure reads no Secret value.** It lists Helm release records by
  name.
- **The generated values are public**, as ADR 0018 states, and so are the
  hand-written values in the Application.

## Evidence

Three kinds of evidence exist, under
[the evidence levels](../../testing/evidence-levels.md), and they are not
interchangeable:

- `C0`: `tests/architecture/test_argocd_application.py` reads the two manifests
  and the procedure as text.
- `C1`: `tests/architecture/test_argocd_application_procedure.py` executes the
  procedure with `kubectl`, `kind`, `docker`, and `sleep` replaced by stubs.
- `C2`: [three runs on the `docker-desktop` provider](../../proof/environment/v2-s3-002-pr2-argocd-application-run.md),
  on 2026-10-04. The third ran the committed procedure.

The runs establish that, on that provider and on that day, Argo CD applied the
generated release at the commit `main` named, six times. Five of six caller
requests were answered afterwards, and one returned no response. One manual
change was reverted in each run, and each removal left no workload object and
kept the prerequisites. The runs establish nothing about `kind`, about a later
commit of `main`, about latency, capacity, or availability, and nothing about
the first experiment: that experiment's real-deployment part runs under its own
frozen revision, and no run here is a run of it. **No claim is registered.**

## Risks, assumptions, and open questions

| ID | Item | Status | Impact |
|---|---|---|---|
| R1 | The API image digest is not in Git | Open | The promotion boundary does not cover the API image. Two clusters at the same commit can run two API images. A published image, pinned in a contract or a platform default, would close it |
| R2 | The Application follows a branch, and nothing verifies that a merge was reviewed | Open | ADR 0018 R3 carries the review half. A merge to `main` is a deployment on a cluster where the Application is applied |
| R3 | The project restricts one Application, and the controller's grant is cluster-wide | Open | ADR 0017 R1 is not narrowed. A second project or Application created by hand is held by nothing. The procedure refuses to run beside one, and does not remove it |
| R4 | Nothing stops `helm install` after the Application is applied | Open | Helm refuses to adopt an object that carries no Helm ownership metadata, by upstream's description. That was not tried here |
| R5 | With pruning disabled, an object that leaves the chart stays | Accepted | The removal finds it only by the release label. A later decision may enable pruning for a bounded experiment |
| R6 | No run observed a later commit of `main` being applied | Open | D4 is accepted on the resolution of one commit. The time Argo CD takes to notice a commit was not measured |
| R7 | The procedure was not executed on `kind` | Open | D2 and D7 stay proposed there. No release is declared for the `local-kind` binding |
| R8 | A cascade that does not finish has no decided recovery | Open | The removal refuses when the controller reports no ready replica. It cannot refuse a controller that stops afterwards |
| R9 | Self-heal reverts a break-glass change | Accepted | A manual change needs the Application removed first. The break-glass boundary is not decided here |
| R10 | The first experiment's freeze record names no Application | Open | A later freeze revision for the real-deployment part must name the Application, the project, and the desired-state path before a result-bearing run. ADR 0018 R4 carries the path. **Added 2026-10-06:** [freeze revision 3](../../proof/experiments/v2-e01/freeze-r3.v1alpha1.json) names all three. It also changes one clause of that experiment's criterion E01-AC10, which said that the release takes no parameter override: D5 supplies the API image digest as one parameter, and the revision records the change and its reason |
| R11 | The Argo CD pods run beside the release with no resource request or limit | Open | ADR 0017 R4. Each run held one release beside them and measured nothing |
| R12 | The bootstrap procedure prints that no Application exists, and does not check | Accepted | The line is true after a first install. It can be false after an install over a live installation. The bootstrap procedure is unchanged, so that its recorded runs still name its bytes |
