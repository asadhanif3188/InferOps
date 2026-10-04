# V2-S3-002-PR1 validation

Date: 2026-10-04

What this change checked before it was committed, and how. What it decides is in
[ADR 0018](../../architecture/decisions/ADR-0018-git-desired-state-layout.md), and
what it adds is described in
[the Git desired-state document](../../environment/git-desired-state.md). This page is
about the checks run over the repository after the tree, its tool, its suite, and the
documents were written.

**Nothing reconciles the tree, and nothing was installed.** No cluster was contacted.
No Application exists. Every check below is static, which is `C0` under
[the evidence levels](../../testing/evidence-levels.md). The change adds no record to
the evidence pack and moves no claim.

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `c056b97`, the merge of pull
  request 118, which implemented and ran the Argo CD bootstrap.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0
  with `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` at `718ad2e0…` with the set
  `1d40b33f…` and the pack `652e9051…`, and `CURRENT` with the set `0271ae27…` and
  the pack `222bc533…`. Those are the five values that the two records of
  `V2-S3-001` state. The command was run after this change was written. It was not
  run on `main` in this session: no file this change touches is cited by an
  evidence record.
- **The frozen experiment.** `python -m tools.experiment_freeze --check` exited 0
  for both freeze records, and `python -m tools.experiment_e01 --check` exited 0
  for both runs. The second freeze record pins the files of
  `tools/generated_release`, the reference contract, the `local-kind` binding, the
  chart, and the platform domain. This change edits none of them.

## What changed

- **[`gitops/`](../../../gitops/README.md)** — a new top-level directory. It holds
  one generated release, at
  `gitops/environments/local-docker-desktop/workloads/support-assistant/`, and one
  page that says what the tree is.
- **[`tools/gitops_desired_state`](../../../tools/gitops_desired_state/core.py)** — a
  new tool. It declares the release and its inputs, derives the path a release
  belongs at, calls the existing drift check, and reports every entry in the tree
  that no declared release accounts for. It regenerates a release named by key.
- **[`tests/domain/test_gitops_desired_state.py`](../../../tests/domain/test_gitops_desired_state.py)**
  — a new default-lane suite.
- **[ADR 0018](../../architecture/decisions/ADR-0018-git-desired-state-layout.md)**
  and [the desired-state document](../../environment/git-desired-state.md).
- **Three existing suites.** The suite of ADR 0017 no longer refuses a `gitops/`
  directory. It now requires that the tree's own check finds nothing, and it reads
  `gitops/` with the build directories. The drift suite accepts a tracked generated
  file in a desired-state release. The render-boundary suite lists the new tool
  beside the two repository checks.
- **`.gitattributes`** pins `gitops/**` to LF.
- **The ownership inventory** gains the row `git-desired-state`, owned by
  `repository`. No existing row moves.
- **Indexes and living documents**: the architecture index, the decision-authority
  register, the system architecture, the renderer document, the binding document,
  the contributor guide, the README, the test inventory, and the changelog. The
  comment of the `local-docker-desktop` binding fixture said that its destination
  was not a directory that exists, and it is corrected. A binding is hashed by its
  parsed value, so the comment moves no digest.

## The release that was generated

| Field | Value |
|---|---|
| Command | `python -m tools.gitops_desired_state --write local-docker-desktop/support-assistant` |
| Contract | `contracts/workload/examples/valid/synchronous-llm-local.yaml`, digest `56f73f78…709c0d` |
| Binding | `local-docker-desktop`, digest `afaabe71…4f1251` |
| Renderer and platform-defaults revision | `c056b9772a3de391fd61589649b1d3ed1c5ac7c4` |
| Release identifier | `eeda9493e0ffca2af499342e2850c63e30ff7254d094016c816d7fbe23fc01ae` |
| `values.generated.yaml`, SHA-256 | `1849af0c88c2ef646b4f6eddfb515ba5fd3f3cbc5ac44950a35b9bf8cec864ce` |
| `rendered-workload-release.yaml`, SHA-256 | `3e536096255fb920b37d077785de7350598bf482399a53a96027927f675ef406` |

The values file has the same SHA-256 as the values file of the reference release in
the test fixtures. The two local bindings render the same chart values.

**The revision is the commit this change was based on.** The renderer and the chart's
`api` defaults were read from the working tree of this branch. This change edits no
file of the renderer and no chart file, so both are the files at that commit. A test
compares the `api` defaults at that commit with the ones read today. Nothing compares
the renderer's source.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| A reference desired-state layout in this repository | Reached. One directory for one binding and one workload, derived from the binding's destination path and the contract's workload identifier |
| Bind the layout to generated release artifacts | Reached. The tree holds the generated values and the RenderedWorkloadRelease that names them, compared byte for byte with what their declared sources derive |
| No second hand-maintained values source | Reached for the tree: every entry that is not a generated file of a declared release is refused. **Not reached for an installed release**: the chart requires four values that no contract owns, and where that hand-written file lives is not decided |
| Validate the supported generated paths | Reached. A release at another path, a path outside `gitops/environments/`, and two declarations of one directory are refused |
| Promotion is a reviewed and accepted Git change | Documented as a rule. The suite fails a stale or hand-edited tree. Nothing verifies that a merge was reviewed |
| No `dev`, `staging`, `production` duplication | Reached. One path exists, and a test plants each of those directories and gets one refusal |

## Results

The figures in this table are from the first commit. The review's findings and the
figures after its fixes are in the next section.

| Check | Result |
|---|---|
| `ruff format --check`, `ruff check`, `mypy` | Clean: 629 files formatted, no lint finding, no type error in 344 source files |
| `tools.gitops_desired_state --check` | Exit 0: the one release is at its derived path and is what its sources derive, and the tree holds nothing else |
| `tools.generated_release --check` | Exit 0: the reference release is what its declared sources derive. This command does not read the desired-state release |
| `tests/domain/test_gitops_desired_state.py` | 57 passed and 1 skipped at the first commit. The skip is the symbolic-link case, on a Windows host that cannot create a link |
| `tools.experiment_freeze --check` | Exit 0: 2 freeze records, every rule held |
| `tools.experiment_e01 --check` | Exit 0: 2 runs, each agrees with its own evidence |
| `tools.evidence_index --check` | Exit 0: the index is what the register and ledgers produce |
| `tools.evidence_index --gate` | Exit 0, with the five values above |
| `tools.proof_dashboard --check` | Exit 0: the dashboard is what the register produces |
| `helm template` over the generated values alone, Helm `v3.19.0` | Fails, as documented: the chart's guard requires `api.image.repository`. With the reference hand-written fixture after the generated values it renders 23 objects |
| The default lane, `pytest -q -rs`, at the first commit | 18,314 passed, none failed, 33 skipped, 14 deselected, in 27 minutes 51 seconds, with every file of the change staged. The skips are host symlink privileges, POSIX signals on Windows, an absent collector image, and fixtures a test does not apply to. One of them is this change's symbolic-link case. The 14 deselected tests are the lanes that need a cluster or a runtime |
| `git diff --check` | Clean |
| Tag `v1.0.0` | Tag object `17c9bbd7…`, commit `718ad2e0…`, as before |
| `gitleaks` | Not run: it is not installed on this host. The hosted CI job runs it over the full history |
| Hosted CI | Not read: the hosted checks of this change's pull request cannot be read from this host |

## What the independent review found

Two independent reviews read this change as it was staged for the first commit, one over the tool and the suites and one over the documents and the data. This section is written in the commit that follows, with each finding and its fix.

## Gates that do not apply, and work not executed

- **A cluster run.** Not executed, and not asked of this change. No cluster was
  contacted, and no controller was installed.
- **An Argo CD static check.** Not applicable: the repository holds no Application
  and no project.
- **Helm render and Kubernetes schema of the chart.** No file under `charts/` or
  `deploy/` changed. The chart suite's renders of the reference values apply to this
  release's values file, because the two files are the same bytes.
- **Terraform format, validate, and lint.** Not applicable: no file under `infra/`
  changed.
- **A new freeze revision.** Not needed: no file that a freeze record pins changed,
  and the freeze check passed.

## Privacy and publicability

The diff was read for private planning text, local paths, credentials, account
identifiers, and story identifiers that are not merged. Files are named by repository
path. The generated files hold the names and pins of the committed reference contract
and binding, which were public already. The one story identifier that is not merged
is this change's own.

## What this does not establish

- **That a controller reconciles the tree.** No Application exists.
- **That the release installs or serves a request.** Nothing was installed, and the
  generated values alone fail the chart's guards.
- **That the recorded revision is the commit the release was rendered at.** It is a
  declaration, and only the platform defaults at that commit are compared.
- **That a merge to `main` is reviewed.**
- **Anything about `kind`**, or about any provider other than the one the binding
  names. A committed file is evidence about no provider at all.
