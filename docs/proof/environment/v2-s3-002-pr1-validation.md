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
  `V2-S3-001` state, so this change moved none of them. The command was run after
  this change was written. It was not run on `main` in this session.
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
  register, the system architecture, the renderer document, the renderer input
  boundary document, the binding document, the release document, the contracts
  index, the binding examples' page, the Argo CD bootstrap document, the proof
  index, the contributor guide, the README, the test inventory, and the changelog. The
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

Two independent reviews read this change as it was staged for the first commit,
while the default lane ran. One read the tool and the suites, and executed the tool
against copies. The other read the documents and the data, and recomputed the digests
and the counts. Neither edited the repository. The first commit was made as it was
written, and the fixes below are the second commit.

Neither review found a check that passes a hand-written file in the tree, a wrong
digest, a wrong count, a broken link, or private text. They found the following.

**What the first commit got wrong in the tool.**

- **A regeneration wrote outside the root.** With a Windows directory junction at
  `gitops/environments/local-docker-desktop`, `regenerate_release` created the release
  in the junction's target. The module said that it writes only the declared
  directory. The write now refuses a link, or a file, at every path from the tree's
  root to the release.
- **A junction at a declared path was followed and not reported.** The check asked for
  a symbolic link, and Windows does not report a junction as one. A junction to a
  directory with the same files verified clean. The check now refuses both, at the
  root, at a directory, and at a file. The first commit's test planted a link at an
  undeclared name only.
- **The rule on revisions said more than it checks.** It said "a full Git revision
  that is not a placeholder". It checks 40 lowercase hexadecimal characters that are
  not one repeated character, so `abab…` passes. The rule now says what it checks, and
  a test pins that a made-up revision of that form is accepted.
- **A binding whose destination is `gitops/environments` itself was accepted.** The
  first commit tested the declared directory's prefix and not the binding's
  destination. The destination must now be beneath that directory.
- **A failed write printed the host's absolute path**, and advised a retry that could
  not succeed, when a file stood where a directory belongs. That case is now a refusal
  that names the path under the root.
- **Two assertions were weak.** One could not fail, and it is removed. One accepted
  either refusal branch of the command, and it now matches the branch it names.

**What the first commit got wrong in the documents.**

- **"A real commit" was not held by anything.** The decision record and the
  architecture index said that a release records a real commit. The check holds a
  form. The one test that reads history skips when the commit is absent, and the
  hosted default lane uses a shallow checkout, so that test never runs there. A
  revision that names no commit skips it too. The documents now say each of those
  things.
- **The documented workflow could not be followed for one case.** The documents said
  that a release records the commit its change was based on. For a change to the
  chart's `api` defaults that commit holds the old defaults, and the history test
  fails. Such a change needs two commits. The decision record, the document, and the
  contributor guide now say so.
- **The decision record described a freeze revision that does not exist.** It said
  that the freeze revision for the real-deployment part "names the exact path". No
  revision does. The risk is now open, and the text says that a later revision must
  name it.
- **"Accepted in part" stood beside "all eight decisions are accepted".** The index
  now says that seven are accepted and that D3 is open for an installed release.
- **Five living documents still described the repository before this change.** The
  release document said three times that the only committed generated release is a
  test's golden release. Two rows of the test inventory described assertions that
  this change replaced. The contracts index, the binding examples' page, the renderer
  document, and the contributor guide each kept one such sentence. All are corrected.
- **Smaller corrections**: "delivery step" for a commit that delivers nothing, a
  consequence that named `main` while the followed revision is undecided, a count of
  two tools where the test now reads three, and two inventory clauses that named the
  wrong subject.

**What was not changed.** The review asked whether the hosted lane should fetch full
history, so that the history test runs. It does not: a workflow change moves the gate
matrix, and it is outside this change. The limit is stated instead. The security
baseline gains no row. The review found that the existing threat and controls for the
controller's grant still describe the repository, and that no statement in them became
false.

| Check, after the fixes | Result |
|---|---|
| `ruff format --check`, `ruff check`, `mypy` | Clean: 629 files formatted, no lint finding, no type error in 344 source files |
| `tests/domain/test_gitops_desired_state.py` | 69 passed and 4 skipped. The four skips are the symbolic-link cases on a Windows host. The three junction cases ran and passed there. On the Linux runner the symbolic-link cases run and the junction cases skip, and that was not observed from this host |
| The six command checks in the table above | Each exited 0, and the five evidence values were unchanged |
| The default lane, `pytest -q -rs` | 18,326 passed, none failed, 36 skipped, 14 deselected, in 24 minutes 48 seconds, with every file of the change staged. The three skips more than the first commit are the three symbolic-link cases at a declared path |
| `git diff --check` | Clean |

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
