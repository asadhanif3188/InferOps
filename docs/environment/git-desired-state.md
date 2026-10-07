# Git desired state

Status: **the layout exists and is checked, and one Application reads it.**
`V2-S3-002-PR1` added the directory [`gitops/`](../../gitops/README.md), one generated
release in it, and a check that accounts for every entry in the tree.
[ADR 0018](../architecture/decisions/ADR-0018-git-desired-state-layout.md) records
those decisions. Every check of the tree is static, at evidence level `C0`.

`V2-S3-002-PR2` added one Argo CD Application that reads the generated values of that
release. [ADR 0019](../architecture/decisions/ADR-0019-argocd-application-and-sync-policy.md)
records those decisions, and
[the Argo CD Application document](argocd-application.md) describes the Application.
On 2026-10-04, in three runs on the `docker-desktop` provider, Argo CD applied the
release, and each run removed it afterwards. **This page describes the tree. It
establishes nothing about a cluster.**

| Property | Value |
|---|---|
| Directory | [`gitops/`](../../gitops/README.md), at the repository root |
| Holds | Generated releases: `values.generated.yaml` and `rendered-workload-release.yaml` in each release directory. One page, `gitops/README.md`, is written by hand |
| Decision | [ADR 0018](../architecture/decisions/ADR-0018-git-desired-state-layout.md) |
| Check | [`tools/gitops_desired_state`](../../tools/gitops_desired_state/core.py): `python -m tools.gitops_desired_state --check`, and `--write KEY` to regenerate |
| Derivation | [`tools/generated_release`](../../tools/generated_release/core.py), the drift check described in [the renderer document](../domain/helm-values-renderer.md#verifying-a-committed-release) |
| Tests | [`tests/domain/test_gitops_desired_state.py`](../../tests/domain/test_gitops_desired_state.py) |
| Validation record | [`v2-s3-002-pr1-validation.md`](../proof/environment/v2-s3-002-pr1-validation.md) |
| Read by | One [Argo CD Application](argocd-application.md), on a cluster where an operator applied it. It reads `values.generated.yaml` and not the release document |
| Read at a commit by | [`tools/desired_state_provenance`](desired-state-provenance.md), which prints the identities of a release as one Git commit holds it. It reads no cluster |

## The layout

```text
gitops/
├── README.md
└── environments/
    └── local-docker-desktop/                  the binding's spec.gitops.destinationPath
        └── workloads/
            └── support-assistant/             the contract's metadata.name
                ├── rendered-workload-release.yaml
                └── values.generated.yaml
```

A release directory is the selected EnvironmentBinding's destination path, followed by
`workloads` and the workload identifier that the WorkloadContract names. The check
derives that path from the two documents. It does not read the path from the
directory.

- **The binding owns the environment's path.** `spec.gitops.destinationPath` is
  declared in [the binding](../contracts/environment-binding.md). If a binding changes
  its path, the check fails until the declaration and the release are both moved. The
  path must be beneath `gitops/environments/`. Nothing ties the directory's name to the
  binding's name.
- **The contract owns the workload's name.** A renamed workload moves its directory.
- **A release directory holds the two generated files and nothing else.**
- **An environment directory exists only for a binding that a declared release
  names.** No `dev`, `staging`, or `production` directory exists, and the check
  refuses one that nobody declared.

## The release in the tree

One release is declared.

| Key | Directory | Contract | Binding | Platform defaults | Revisions |
|---|---|---|---|---|---|
| `local-docker-desktop/support-assistant` | `gitops/environments/local-docker-desktop/workloads/support-assistant` | `contracts/workload/examples/valid/synchronous-llm-local.yaml` | `local-docker-desktop`, the only binding offered | The `api` block of `charts/inferops-llm/values.yaml` | Both are `9bc07a57ca112f5e578914d2265c8e7ab2ae4fb0` |

Its release identifier is
`f23c37d81fbb297643af9e6005cffd805ac05bc98847a6360894fdd238b41d8c`.

**Why this binding.** `local-docker-desktop` names the one provider on which the
Argo CD bootstrap was executed. No release is committed for `local-kind`.

**What the revisions are.** A release cannot name the commit that adds it. A change
that edits the renderer or the chart's `api` defaults must record a commit of its own
that already holds the new files, which takes two commits and a merge that keeps them.
`V2-S4-001-PR1` is such a change: its first commit edited the renderer, the chart's
`api` defaults, and the binding, and regenerated the values. Its second commit recorded
the first commit as both revisions, which moved the release identifier. At the first
commit itself the tree holds a release,
`901c4a5ae968d135624c21c8cf118512df8dc3bfa77ece5bffa3cfb87f7f762f`, whose two revisions
still name the earlier commit; that statement is false for that one commit. The change
must be merged with a merge commit: a squash or a rebase would leave the first commit
off `main`, and the release would name a commit that `main` does not hold. A later commit of the same change may edit the
renderer's source without moving a rendered byte; no test compares the renderer's
source at the recorded revision.

**The release this one replaced.** Until `V2-S4-001-PR1` the tree held the release
`eeda9493e0ffca2af499342e2850c63e30ff7254d094016c816d7fbe23fc01ae`, rendered at
`c056b9772a3de391fd61589649b1d3ed1c5ac7c4` for chart `0.3.0`, with one API replica. That
release is the one every recorded Argo CD run reconciled, the real-deployment run of
the first experiment included. It is in Git history at the commits those runs
recorded. **No run reconciled the release that the tree holds now.**

**What the values are.** The values file differs from the values file of the reference
release in the test fixtures in one value: `api.replicaCount` is 2 here and 1 there.
The `local-docker-desktop` binding states two API replicas and the `local-kind`
binding states one. Both files carry the same two rollout bounds, which the platform
defaults own: `api.rollout.maxUnavailable` 0 and `api.rollout.maxSurge` 1. A test
asserts each of these facts. The two releases differ in the binding they name, the
binding's digest, the values digest, the two revisions, and the release identifier.

**What two replicas establishes.** A declared count and a rendered Deployment. Chart
`0.4.0` was installed nowhere, and no release with two API replicas was installed from
this tree. The count does not establish that two API pods run, that a rollout leaves a
caller served, or what a caller observes when an API pod is deleted or a node is lost.
On a cluster where the Application is applied, a merge of this release changes the
live release. The pod template of each Deployment carries the chart version label, and
that label changes with chart `0.4.0`, so the render gives every Deployment a new pod
template. That is read from the render. It was not observed on a cluster.

## The promotion boundary

```text
change a contract, a binding, or the platform defaults
        |
regenerate the release
        |
review the source change and the generated difference together
        |
the change is accepted into main        <- the promotion boundary
        |
Argo CD applies the new revision        on a cluster where the Application is applied
```

**The desired state is the content of `gitops/` on `main`.** It changes when a
reviewed change is accepted into `main`, and by no other step. One environment has one
path. No second promotion stage exists.

- A regeneration on a contributor's machine changes nothing until the change that
  contains it is accepted.
- The default-lane suite runs the check. A change whose release is stale, edited by
  hand, or at the wrong path fails the build.
- The suite does not establish that a person reviewed the change. Review holds that
  part of the rule. This repository does not claim that branch protection is
  configured.
- `main` is a name that moves. The identity of an accepted change is its commit.
  [The provenance tool](desired-state-provenance.md) reads the release that one
  commit holds, and it refuses a branch name.

## The workflow

```sh
# Verify the whole tree. Writes nothing.
uv run --locked python -m tools.gitops_desired_state --check
# After a deliberate change to an input: read the findings, then regenerate by key.
uv run --locked python -m tools.gitops_desired_state --write local-docker-desktop/support-assistant
# Print every desired-state release and its inputs.
uv run --locked python -m tools.gitops_desired_state --list
```

`--check` exits 0 when the tree breaks no rule, and 1 when it breaks one. It reports
each finding with its rule and, for a drifted file, a unified diff from the committed
file to the derived one. It writes nothing and repairs nothing.

`--write` regenerates only the releases it is given by key. A key is
`<binding name>/<workload>`. It refuses a release whose declaration or path breaks a
rule, a directory that holds something the platform did not write, and sources that no
longer render. It creates the directories that lead to a release when they are absent.
Regeneration replaces a hand edit without asking, so read the findings first.

**A new desired-state release** is declared in `DESIRED_STATE_RELEASES` in
`tools/gitops_desired_state/core.py`, with a binding that declares its destination
path. It is then written with `--write`. A second path is a decision, and a test pins
the list of declarations.

## The rules

The check applies four rules, in this order:

| Rule | Statement |
|---|---|
| `desired-state-declaration-invalid` | A desired-state release selects one binding by name, and each of its two revisions is 40 lowercase hexadecimal characters and not one repeated character. |
| `desired-state-path-not-derived` | A desired-state release directory is the selected binding's destination path, under gitops/environments/, followed by workloads and the workload identifier the contract names. |
| `desired-state-entry-undeclared` | Every entry under gitops/ is a generated file of a declared release, a directory that leads to one, or the tree's README.md. |
| `desired-state-release-drifted` | Each desired-state release is, byte for byte, what its declared sources derive. |

A placeholder is a revision of one repeated character, which is the shape the test
fixtures use. Any other 40 lowercase hexadecimal characters pass the first rule,
whether or not they name a commit, and a test pins that limit.

The last rule is the drift check's. Each of its eight rules is reported under
`desired-state-release-drifted`, with the drift check's own rule in the detail.

**What each defect is reported as.** The suite plants each of these in a copy of the
tree and its inputs:

- **A hand-written values file beside a release** is `desired-state-entry-undeclared`,
  and the drift check also refuses it as an entry the platform did not write.
- **A file anywhere else in the tree**, whatever its name, is
  `desired-state-entry-undeclared`.
- **A copy of a release under another environment name** is one
  `desired-state-entry-undeclared` finding, at the directory. So are a second workload
  directory that nobody declared, an empty directory, a left-over staging directory,
  and a symbolic link or a Windows directory junction, which is not followed. A link at
  a declared path is refused too, and a regeneration does not write through one. The
  symbolic-link cases skip on a host that cannot create a link, and the junction cases
  skip off Windows.
- **A hand-edited value** is `desired-state-release-drifted`, with a diff.
- **A binding that moved its destination path**, or a contract that renamed its
  workload, is `desired-state-path-not-derived`, and the stale digest is drift. So is a
  binding whose destination is `gitops/environments` itself.
- **A binding that the declaration cannot resolve** gives no path to compare. The
  drift check then refuses the sources, and the release is reported under
  `desired-state-release-drifted`.
- **A placeholder revision or a short revision in a declaration** is
  `desired-state-declaration-invalid`. A committed release edited to name a placeholder
  is drift.

## Hand-written values

**The tree holds none.** A hand-written values file in `gitops/` is refused, whatever
its name.

**The generated values do not install the chart alone.** The chart's guards require
four values that no WorkloadContract owns: `api.image.repository`, `api.image.digest`,
`model.alias`, and `model.license.spdx`.
[A test in the chart suite](../../tests/architecture/test_helm_chart.py) measures that
list. `helm template` over the generated values alone fails at the first of them.

For the reference workload those values are in
[a hand-written test fixture](../../tests/domain/fixtures/helm-values/support-assistant-local.manual-values.yaml).
[The renderer document](../domain/helm-values-renderer.md#hand-written-values) says
what such a file may set: no value that the generated file holds. The fixture's API
image digest is a placeholder, because no InferOps API image is published.

ADR 0018 left open where the hand-written values of an installed release live.
[ADR 0019](../architecture/decisions/ADR-0019-argocd-application-and-sync-policy.md)
decided it: they are inside the Application, and not in this tree. The API image
digest is not in Git at all. The operator gives it to the procedure that applies
the Application, because no InferOps API image is published.

## Ownership

The tree is a repository artifact. It is the row `git-desired-state` of
[the ownership inventory](../architecture/resource-ownership.md), owned by
`repository`: a merged pull request creates it and changes it.

The tree holds no cluster object. A RenderedWorkloadRelease is a repository document,
not a cluster resource. The objects that a release creates in a cluster are the
`release` rows of the inventory. ADR 0019 D8 says how those rows are shared when
Argo CD applies the chart.

## Not applied yet

| Not applied | Why | What it needs |
|---|---|---|
| A cluster that is continuously reconciled to the tree | The Application is applied by an operator, on one cluster at a time. Each recorded run removed it | An environment that keeps the Application applied |
| An observation of a later commit being applied | Each recorded run applied the same commit of `main` | A run that merges a change while the Application is applied |
| The API image identity in Git | The API image is a contributor's local build, and its digest is given to the procedure | A published image, pinned where a contract or a platform default owns it |
| A published API image | The API image is a contributor's local build | A published image, or a procedure that loads one into the cluster |
| A desired-state path for `kind` | No bootstrap ran on `kind` | A run on `kind`, and a declared release for the `local-kind` binding |
| The renderer's source is compared at the recorded revision | The check reads no Git history | A check that reads the renderer at the recorded commit |
| A check that a merge was reviewed | Branch protection is not claimed as configured | A configured and verified branch rule |

## What this does not establish

- **That a cluster is reconciled to the tree now.** One Application reads the
  tree where an operator applied it. Three runs applied and removed it on
  `docker-desktop`, and [their record](../proof/environment/v2-s3-002-pr2-argocd-application-run.md)
  is the evidence. No check on this page reads a cluster.
- **That the release installs from the generated values alone.** They fail the
  chart's guards. The Application adds hand-written values and one parameter.
- **That the release serves requests.** Each run sent one request after each of
  its two applies. Five of the six were answered. This page's checks send none.
- **That the recorded revision is the commit the release was rendered at, or that it
  names a commit.** It is a declaration, and the check holds its form only. A test
  compares the platform defaults at that commit with the defaults read today, and it
  skips in a checkout that does not hold the commit. The hosted default lane uses a
  shallow checkout, so the test skips there and runs only in a full clone. A revision
  that names no commit skips the test and does not fail it. The renderer's source at
  that commit is not compared.
- **That a merge to `main` was reviewed.**
- **Anything about `kind`.** The one path is for the `local-docker-desktop` binding.
- **That a file Git ignores is absent from another checkout.** The check reads the
  working tree, and a second test reads the files that Git tracks. On a file system
  that ignores case, a root named `GitOps` passes the working-tree check and not the
  test that reads the index.

## Validation

```sh
uv run --locked python -m tools.gitops_desired_state --check
uv run --locked python -m tools.generated_release --check
uv run --locked python -m pytest tests/domain/test_gitops_desired_state.py tests/domain/test_generated_release_drift.py tests/architecture/test_argocd_bootstrap.py -q
uv run --locked ruff check . && uv run --locked ruff format --check . && uv run --locked mypy
```
