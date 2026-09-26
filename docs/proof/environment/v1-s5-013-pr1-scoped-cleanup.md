# V1-S5-013-PR1 — scoped cleanup, and the cluster that outlived it, at a named revision

Date captured: 2026-09-26

Classification: **local real evidence**, `C2`. A real release was installed, tested,
upgraded, rolled back, and uninstalled by the repository's own lifecycle workflow,
which then asserted that nothing carrying the release's label was left and that the
Terraform-owned namespace and claim survived. The cluster was asked, through the
repository's own target guard, what it looked like before the release, after the
uninstall, and after the Terraform prerequisites were destroyed through the guarded
wrapper. It was still there each time, with its node Ready, its storage classes
unchanged, and every namespace InferOps does not own untouched. The repository code
that did it is named: a fresh clone of `main` at a named commit, with nothing
uncommitted before the first step or after the last. Nothing here is mock, synthetic,
or estimated.

This run exists to close release blocker
`b3-helm-uninstall-survival-clause-code-unidentified`. The survival of the cluster,
its node, and its storage class rested only on
[the 2026-09-12 scoped cleanup](v1-s3-011-pr2-scoped-cleanup.md), which names no
revision of this repository. That record stays exactly as it is and stays cited for
what it did. **This run does not recover what that one ran.** It is a second
execution, and it identifies its own code.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `bcad343133ba6fddfe38832a2694e71777cdd006`, the tip of `main` when this change began, in a fresh clone of the public repository; `git status --porcelain --untracked-files=all` printed nothing before the first step and after the last |
| Provider | `docker-desktop`, the V1 reference provider |
| Kubernetes | server `v1.34.3`, one node, `desktop-control-plane` |
| Node image | `kindest/node@sha256:08497ee19eace7b4b5348db5c6a1591d7752b164530a36f855cb0f2bdcbadd48`, Docker Desktop's choice and not an InferOps pin |
| Chart, lifecycle workflow, Terraform | `charts/inferops-llm`, `scripts/environment/helm-lifecycle.sh`, `infra/terraform`, and `scripts/environment/terraform-prerequisites.sh`, all at the revision above; chart version label `inferops-llm-0.3.0` |
| API image | `localhost/inferops-api@sha256:6d565a391412c74a9c0eb1bf31da216b7edb739a906bbd1827ee8a45b74d9b40`, built from the clone at the revision above |
| Model seed image | `localhost/inferops-model-seed@sha256:1ac37eb22072a7960c64002f13b28eaf81df091cb2d65ff8ebad066e94fb758d`, built from the clone |
| Serving runtime | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model | revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Helm, kubectl, Terraform | `v3.19.0+g3d8990f`, `v1.34.3`, `1.15.8` |
| Transcripts | [the preparation](v1-s5-013-pr1-cluster-prepare-transcript.txt), which also holds the first cluster reading, and [this stage](v1-s5-013-pr1-scoped-cleanup-transcript.txt), each with the revision and the status before and after |

## What was done

```text
cluster reading (before any work)
  ... two release experiments, each installing and uninstalling its own release ...
cluster reading (before the lifecycle)
scripts/environment/helm-lifecycle.sh --values <the clone's merged values file>
cluster reading (after the uninstall)
scripts/environment/terraform-prerequisites.sh destroy --confirm
cluster reading (after Terraform)
```

Every reading went through `inferops::resolve_target` in the clone's
`scripts/environment/lib.sh`, which re-verified the provider before each one, and every
`kubectl` call through `inferops::target_kubectl`, so no ambient context could redirect
it.

## Procedure

From the clone's root, with the clone's own locked environment first on `PATH`,
`INFEROPS_PROVIDER=docker-desktop`, and the values file the preparation merged from
`charts/inferops-llm/ci/real-values.yaml` and the two image overlays:

```text
git rev-parse HEAD && git status --porcelain --untracked-files=all
scripts/environment/helm-lifecycle.sh --values <merged values>
scripts/environment/terraform-prerequisites.sh destroy --confirm
git rev-parse HEAD && git status --porcelain --untracked-files=all
```

## 1. The release, and what its uninstall left

`helm-lifecycle.sh` installed revision 1, passed the release test, upgraded to revision
2, passed it again, rolled back to revision 1 as revision 3, passed it a third time,
and ran `helm uninstall`. Its own assertions, asked repeatedly inside the uninstall
budget rather than once:

| Assertion | Result |
|---|---|
| Objects carrying `app.kubernetes.io/instance=inferops` | none remain |
| A Helm release named `inferops` | none |
| Namespace `inferops-release` | survived, as a prerequisite must |
| Persistent volume claims | 1 before the release, 1 after |

The cluster reading after the uninstall counted, kind by kind, 0 Deployments,
ReplicaSets, Services, ConfigMaps, ServiceAccounts, Pods, NetworkPolicies, Jobs,
EndpointSlices, Roles, RoleBindings, and Secrets carrying that label, and no Helm
release in the namespace.

## 2. What Terraform owned was still there, before Terraform was asked

```text
inferops-release  labels: app.kubernetes.io/component=platform-namespace,
                          app.kubernetes.io/managed-by=Terraform,
                          app.kubernetes.io/part-of=inferops,
                          inferops.io/lifecycle=prerequisite
inferops-model-cache   Bound   pvc-29b3d0cc-aca5-46a5-9cde-40e6aaa22a3c
```

The namespace's UID was the same after the uninstall as after the first
`terraform apply`, `70bf4dab-6e96-41f3-8c0f-8929cbf2963d`: the two experiments that
applied the prerequisites again changed nothing, and the lifecycle workflow reported
the namespace as already present and reused it.

## 3. `terraform destroy`, through the guarded wrapper

```text
INFEROPS_PROVIDER=docker-desktop \
  scripts/environment/terraform-prerequisites.sh destroy --confirm
```

The wrapper re-verified the target, printed its two warnings, and destroyed exactly two
resources, the claim and then the namespace. Afterwards the namespace was
`NotFound`.

## 4. The cluster survived

Asked of the cluster, not inferred from not having run a delete command. The same
facts before any work and after each teardown step:

| Question | Before any work | After `helm uninstall` | After `terraform destroy` |
|---|---|---|---|
| Target verification through the committed guard | `provider=docker-desktop cluster=docker-desktop context=docker-desktop` | the same | the same |
| API server | `v1.34.3` | `v1.34.3` | `v1.34.3` |
| `kube-system` namespace UID | `ba50c99a-…-7f29f07b7664` | the same | the same |
| Node | `desktop-control-plane`, Ready, kubelet `v1.34.3` | the same | the same |
| Node container on the engine | running | running | running |
| Default storage class | `standard`, `rancher.io/local-path`, UID `97b761a3-…-c9366a13e249` | the same | the same |
| Other storage class | `hostpath`, `rancher.io/local-path`, not default | the same | the same |
| Namespaces | seven, none of them `inferops-release` | the same seven, and `inferops-release` | the same seven, each with the UID it had before any work |

The unchanged `kube-system` UID is what says this is the same cluster rather than a
reset one. **Docker Desktop was never reset, disabled, or reconfigured**, and nothing
in this project can do any of those.

**Two lines the last reading did not print, and why.** The reading script asks for the
release namespace before it asks for claims and labelled objects in it, and the
repository's `lib.sh`, which it sources, stops a script at a failed command. After
`terraform destroy` the namespace lookup returned `NotFound`, so the claim and object
listings after it were not printed. The first reading, before any work, stopped at the
same line for the same reason. Nothing can be inside a namespace that does not exist,
and Terraform's own output records the claim's destruction.

## 5. One piece of InferOps residue this teardown does not remove

`inferops-serving-feasibility`, created by the Sprint 0 feasibility workflow, was
present before any work and after it, with the same UID. It has no owning teardown in
any committed workflow, as the 2026-09-12 record already says, and it was deliberately
not deleted here. The imported model seed image also stays in the node's container
store, as the image script warns.

## Limitations

- **One provider, one host, one teardown.** `docker-desktop`, on one Windows machine.
  Nothing here says what `kind` does, and ADR 0011 forbids borrowing the answer.
- **Survival was checked immediately afterwards.** Nothing here is about the cluster
  days later.
- **What a Docker Desktop reset would reclaim** was not observed.
- **`terraform destroy` reclaimed the model weights**, as its warning says.
- **It identifies its own code, not the 2026-09-12 run's.**
- The run was made by the author of this change, an AI coding agent, in the session
  that wrote this record; no second engineer has repeated it.

## Authorisation

Required: **yes**. The run installs a release into, upgrades, rolls back, and
uninstalls it from a cluster the operator owns, and removes a namespace from it.

Granted by: the host owner, in the session that ran it, for the `docker-desktop`
provider and not for `kind`.

Sensitive values removed before committing: the absolute path of the clone, the name
and identifier of one namespace belonging to unrelated work, and the engine's local
build-dashboard identifiers, each replaced by a marker in the transcripts. That
namespace is counted among the seven and its UID was compared, and it is not this
record's business beyond that.
