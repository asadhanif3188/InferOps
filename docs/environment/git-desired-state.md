# Git desired state

Status: **the layout exists and is checked. Nothing reconciles it.** `V2-S3-002-PR1`
added the directory [`gitops/`](../../gitops/README.md), one generated release in it,
and a check that accounts for every entry in the tree.
[ADR 0018](../architecture/decisions/ADR-0018-git-desired-state-layout.md) records the
decisions. No Application exists, so no controller reads the tree. No cluster was
contacted, and nothing in the tree was installed. Every check behind this page is
static, at evidence level `C0`.

| Property | Value |
|---|---|
| Directory | [`gitops/`](../../gitops/README.md), at the repository root |
| Holds | Generated releases: `values.generated.yaml` and `rendered-workload-release.yaml` in each release directory. One page, `gitops/README.md`, is written by hand |
| Decision | [ADR 0018](../architecture/decisions/ADR-0018-git-desired-state-layout.md) |
| Check | [`tools/gitops_desired_state`](../../tools/gitops_desired_state/core.py): `python -m tools.gitops_desired_state --check`, and `--write KEY` to regenerate |
| Derivation | [`tools/generated_release`](../../tools/generated_release/core.py), the drift check described in [the renderer document](../domain/helm-values-renderer.md#verifying-a-committed-release) |
| Tests | [`tests/domain/test_gitops_desired_state.py`](../../tests/domain/test_gitops_desired_state.py) |
| Validation record | [`v2-s3-002-pr1-validation.md`](../proof/environment/v2-s3-002-pr1-validation.md) |

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
  its path, the check fails until the release is moved.
- **The contract owns the workload's name.** A renamed workload moves its directory.
- **A release directory holds the two generated files and nothing else.**
- **An environment directory exists only for a binding that a declared release
  names.** No `dev`, `staging`, or `production` directory exists, and the check
  refuses one that nobody declared.

## The release in the tree

One release is declared.

| Key | Directory | Contract | Binding | Platform defaults | Revisions |
|---|---|---|---|---|---|
| `local-docker-desktop/support-assistant` | `gitops/environments/local-docker-desktop/workloads/support-assistant` | `contracts/workload/examples/valid/synchronous-llm-local.yaml` | `local-docker-desktop`, the only binding offered | The `api` block of `charts/inferops-llm/values.yaml` | Both are `c056b9772a3de391fd61589649b1d3ed1c5ac7c4` |

Its release identifier is
`eeda9493e0ffca2af499342e2850c63e30ff7254d094016c816d7fbe23fc01ae`.

**Why this binding.** `local-docker-desktop` names the one provider on which the
Argo CD bootstrap was executed. No release is committed for `local-kind`.

**What the revisions are.** A release cannot name the commit that adds it. Both
revisions are the commit that the generating change was based on. The renderer and the
chart's `api` defaults were read at that commit.

**What the values are.** The values file is byte for byte the values file of the
reference release in the test fixtures. The two local bindings render the same chart
values, and a test asserts it. The two releases differ in the binding they name, the
binding's digest, the two revisions, and the release identifier.

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
a controller reads the new revision     NOT BUILT: no Application exists
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
| `desired-state-declaration-invalid` | A desired-state release selects one binding by name, and each of its two revisions is a full Git revision that is not a placeholder. |
| `desired-state-path-not-derived` | A desired-state release directory is the selected binding's destination path, under gitops/environments/, followed by workloads and the workload identifier the contract names. |
| `desired-state-entry-undeclared` | Every entry under gitops/ is a generated file of a declared release, a directory that leads to one, or the tree's README.md. |
| `desired-state-release-drifted` | Each desired-state release is, byte for byte, what its declared sources derive. |

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
  directory that nobody declared, an empty directory, and a symbolic link, which is not
  followed. The symbolic-link case skips on a host that cannot create a link.
- **A hand-edited value** is `desired-state-release-drifted`, with a diff.
- **A binding that moved its destination path**, or a contract that renamed its
  workload, is `desired-state-path-not-derived`, and the stale digest is drift.
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

Where the hand-written file for an installed release lives, and how an Application
reads it, is not decided. ADR 0018 leaves it to the change that adds the first
Application.

## Ownership

The tree is a repository artifact. It is the row `git-desired-state` of
[the ownership inventory](../architecture/resource-ownership.md), owned by
`repository`: a merged pull request creates it and changes it.

The tree holds no cluster object. A RenderedWorkloadRelease is a repository document,
not a cluster resource. The objects that a release creates in a cluster are the `helm`
rows of the inventory. What becomes of those rows when a controller applies the chart
is open, and ADR 0017 R5 carries it.

## Not applied yet

| Not applied | Why | What it needs |
|---|---|---|
| A controller reconciles the tree | No Application and no project is committed | The change that adds the first Application |
| A sync policy | Automated sync, self-heal, and pruning are settings of an Application | The same change |
| The hand-written values of an installed release | The chart requires four values that no contract owns, and the tree holds generated files only | A decision on where that file lives and how it is read |
| A published API image | The API image is a contributor's local build | A published image, or a procedure that loads one into the cluster |
| A desired-state path for `kind` | No bootstrap ran on `kind` | A run on `kind`, and a declared release for the `local-kind` binding |
| The renderer's source is compared at the recorded revision | The check reads no Git history | A check that reads the renderer at the recorded commit |
| A check that a merge was reviewed | Branch protection is not claimed as configured | A configured and verified branch rule |

## What this does not establish

- **That a controller reconciles the tree.** None reads it. The Argo CD bootstrap
  installs a controller, and no Application names this path.
- **That the release installs.** No cluster read these files. The generated values
  alone fail the chart's guards.
- **That the release serves a request.** Nothing was installed.
- **That the recorded revision is the commit the release was rendered at.** It is a
  declaration. A test compares the platform defaults at that commit with the defaults
  read today, and it skips in a checkout that does not hold the commit. The renderer's
  source at that commit is not compared.
- **That a merge to `main` was reviewed.**
- **Anything about `kind`.** The one path is for the `local-docker-desktop` binding.
- **That a file Git ignores is absent from another checkout.** The check reads the
  working tree, and a second test reads the files that Git tracks.

## Validation

```sh
uv run --locked python -m tools.gitops_desired_state --check
uv run --locked python -m tools.generated_release --check
uv run --locked python -m pytest tests/domain/test_gitops_desired_state.py tests/domain/test_generated_release_drift.py tests/architecture/test_argocd_bootstrap.py -q
uv run --locked ruff check . && uv run --locked ruff format --check . && uv run --locked mypy
```
