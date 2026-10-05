# V2-S3-003-PR1 validation

Date: 2026-10-05

What this change checked before it was committed, and how. What it adds is described
in [the desired-state provenance document](../../environment/desired-state-provenance.md).
This page is about the checks run over the repository after the tool, its suite, and
the documents were written.

**No cluster was contacted, and no label was added.** The tool reads Git objects of
this repository. Every check below is static, which is `C0` under
[the evidence levels](../../testing/evidence-levels.md). The change adds no record to
the evidence pack and moves no claim.

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `b2be70b`, the merge of pull
  request 120, which added the Argo CD Application and its three recorded runs.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0
  with `RELEASED v1.0.0` at `718ad2e0…` with the set `1d40b33f…` and the pack
  `652e9051…`, and `CURRENT` with the set `0271ae27…` and the pack `222bc533…`.
  The command was run after this change was written. It was not run on `main` in
  this session.
- **The frozen experiment.** `python -m tools.experiment_freeze --check` exited 0
  for both freeze records, before the first edit and after the last one.
  `python -m tools.experiment_e01 --check` exited 0 for both runs. Among the files
  that the second freeze record pins are the chart, the platform domain, and the
  files of `tools/generated_release`. This change edits no pinned file.

## What changed

- **[`tools/desired_state_provenance`](../../../tools/desired_state_provenance/core.py)**
  — a new tool. Given a full commit identifier, it reads the desired-state release
  as that commit holds it and prints one record. It refuses a branch name. It
  writes nothing.
- **[`tests/domain/test_desired_state_provenance.py`](../../../tests/domain/test_desired_state_provenance.py)**
  — a new default-lane suite.
- **[The desired-state provenance document](../../environment/desired-state-provenance.md)**
  — a new document.
- **One existing suite.** The render-boundary suite lists the new tool beside the
  three repository checks, because the tool names two of them.
- **Indexes and living documents**: the architecture index, the system
  architecture, the Git desired-state document, the Argo CD Application document,
  the renderer input boundary document, the proof index, the contributor guide,
  the README, the test inventory, and the changelog.

**What did not change.** No file under `charts/`, `src/`, `gitops/`, `infra/`,
`scripts/`, `contracts/`, or `.github/`. No decision record. No ownership row. No
security control. No claim.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| The desired Git revision as an immutable identity | Reached as tooling. The tool takes one full commit identifier and refuses a branch name, a tag name, and an abbreviated commit before it runs Git |
| The rendered-release identity and digests | Reached as tooling. The record holds the release identifier and the values, contract, and binding digests, read from the release document at the commit and checked there |
| The workload identity | Reached as tooling. The record holds the workload identifier and version, and the tool checks that the values at the commit name both |
| The chart and application version | Reached as tooling. The record holds the chart name, version, and application version, read from `Chart.yaml` at the commit |
| No secret | The record is built from identifiers and digests. A test applies the release domain's credential-prefix heuristic to every value. That is a heuristic |
| No unbounded metric label | No label is added. A test holds that no scrape job of the chart reads one of the three labels that the record derives |
| Consistency between the generated desired state, the Argo CD revision, and the evidence metadata | Reached on committed files. The record agrees with the committed Application's source, with the commit that the three recorded runs reported, and with the labels of a render. No value was read from a cluster |
| A label or an annotation on an applied object | **Not added.** [The document](../../environment/desired-state-provenance.md#why-no-label-was-added) records why |

## The commit that the recorded runs reported

Each transcript of
[the three runs of 2026-10-04](v2-s3-002-pr2-argocd-application-run.md) reports
that Argo CD resolved `main` to `293767b6c27d858e911e5e43104ad74fbfac4b02`.

```sh
uv run --locked python -m tools.desired_state_provenance --revision 293767b6c27d858e911e5e43104ad74fbfac4b02
```

The command exited 0. The record names the release identifier
`eeda9493e0ffca2af499342e2850c63e30ff7254d094016c816d7fbe23fc01ae`, the values
digest `1849af0c88c2ef646b4f6eddfb515ba5fd3f3cbc5ac44950a35b9bf8cec864ce`, and the
chart `inferops-llm` at version `0.3.0`.

**This is a reading of committed files.** It establishes which release that commit
holds. It is not a new observation of a cluster, and the transcripts hold no label
of an applied object.

Four other revisions were given to the command:

| Revision | Result |
|---|---|
| `b2be70b391ebeaab089935982e1843cd6b275223`, the base of this change | Exit 0. The same release identifier |
| `c056b9772a3de391fd61589649b1d3ed1c5ac7c4`, a commit before the tree existed | Exit 1, `desired-state-absent-at-revision`, for both generated files |
| `main` | Exit 1, `revision-not-immutable`. The tool checks the form before its first Git call |
| `17c9bbd71ffaeaf286f7949a1c91624bbcfe3e04`, the tag object of `v1.0.0` | Exit 1, `revision-not-readable`: the object is not a commit. Run after the review's correction. At the first commit this identifier passed that check |

## Results

The figures in this table are from the first commit. The review's findings and the
figures after its fixes are in the next section.

| Check | Result |
|---|---|
| `ruff format --check`, `ruff check`, `mypy` | Clean: 640 files formatted, no lint finding, no type error in 350 source files |
| `tests/domain/test_desired_state_provenance.py` | 65 passed and none skipped at the first commit. Helm and the commit of the recorded runs were both present on this host |
| `tools.gitops_desired_state --check` | Exit 0: the one release is at its derived path and is what its sources derive |
| `tools.generated_release --check` | Exit 0 |
| `tools.experiment_freeze --check` | Exit 0: 2 freeze records, every rule held |
| `tools.experiment_e01 --check` | Exit 0: 2 runs, each agrees with its own evidence |
| `tools.evidence_index --check` | Exit 0: the index is what the register and ledgers produce |
| `tools.evidence_index --gate` | Exit 0, with the four values above |
| `tools.proof_dashboard --check` | Exit 0: the dashboard is what the register produces |
| The default lane, `pytest -q -rs`, at the first commit | 18,596 passed, none failed, 39 skipped, 14 deselected, in 32 minutes 28 seconds, with every file of the change staged. The skips are host symlink privileges, POSIX signals on Windows, an absent collector image, and fixtures a test does not apply to. None is a test of this change. The 14 deselected tests are the lanes that need a cluster or a runtime |
| `git diff --check` | Clean |
| Tag `v1.0.0` | Tag object `17c9bbd7…`, commit `718ad2e0…`, as before |
| `gitleaks` | Not run: it is not installed on this host. The hosted CI job runs it over the full history |
| Hosted CI | Not read: the hosted checks of this change's pull request cannot be read from this host |

## What the independent review found

Two independent reviews read the staged tree of the first commit while the default
lane ran. One read the tool and its suite, and reproduced its findings in temporary
repositories. One read the documents against the code and the repository. Neither
ran the suite. The second commit of this change holds the corrections.

**What the first commit got wrong.**

- **The identifier of a tag object was accepted as a commit.** Both reviews found
  it and reproduced it. The tool asked Git whether the identifier names a commit
  after peeling, and Git peels a tag object. In a temporary repository the record
  printed a tag object's identifier as `git.revision`. The rule and two documents
  said that the revision is a commit. The tool now asks for the type of the object
  and refuses any type but a commit. A test plants an annotated tag.
- **One input made the tool raise an error that is not a refusal.** A contract
  whose size is a 401-digit integer parses, and then has no canonical form. The
  comparison with the release raised `CanonicalFormError`, and the command printed
  a traceback and no rule. Both calls into the release rules are now guarded, and a
  planted case holds it.
- **The tool inherited the caller's `GIT_*` variables.** With `GIT_DIR` set, as a
  hook sets it, Git read another repository than the one the tool was given. The
  tool and the suite's own Git helper now remove those variables. The tool also
  disables lazy fetching, so "contacts no network" holds in a partial clone. That
  last part was not executed in a partial clone.
- **A second value file was accepted.** The source comparison required the values
  file once and allowed other files, and a later file overrides the generated
  values. The comparison now requires the values file as the one value file, and
  compares paths in their normal form.
- **A false sentence about metric labels.** The document said that no metric label
  carries a release identifier. The build-information series carries a label named
  `inferops.release.id`, whose value is the Helm release name. The document now
  says what this change adds, which is no metric label, and names that series.
- **A wrong count.** The document said that the tool reads four kinds of file. It
  reads five.
- **An unstated limit.** The documents said that everything is read from the
  commit. The paths that are read and the rules that are applied come from the
  checked-out code. Both documents now say so.
- **"Two read-only subcommands"** was one subcommand, `cat-file`, in two forms.
- **Wording that bound more than the tool binds.** The tool's docstring said that
  the identities "bind an applied workload to its source", and two limits said
  that the record "binds" a controller's report to a release. The tool is given a
  commit and relates it to the release that the commit holds.
- **A sentence no test held.** The document said that a line-ending conversion of
  the checkout changes nothing. It follows from the design, and no test planted
  it. The sentence was removed.
- **Smaller corrections.** The chart label is now formed as the chart's helper
  forms it, for a version with build metadata. An object without labels is three
  findings and not an error. A repeated key prints one record. The detail of a
  failed Git call no longer states one cause for three. The rule
  `release-not-accepted` now states the two other things it refuses. The document
  names the two Deployments whose pod templates carry the common annotations, the
  placeholder API image digest of the render test, the exit status 2, and the
  checkout of the third recorded run. The inventory row named a document that the
  test does not read and omitted several things that the suite holds.
- **Two stale sentences from earlier changes**, found by the sweep and corrected:
  the docstring of the desired-state suite said that no Application names the tree,
  and a comment of the render-boundary suite said "either" beside four tools.

**What the reviews found clean.** Every added link resolves. The diff holds no
local path, credential, or private text. No file under `charts/`, `src/`,
`gitops/`, `infra/`, `scripts/`, `contracts/`, or `.github/` changed. The count
phrases of the inventory and the boundary document agree with the data. The
four-revision table reproduced.

**Not changed.** The test that reads the tool's source for its Git calls pins a
shape and observes no process; its docstring now says so. A blob is read whole into
memory, without a size limit. A repository that uses 64-character object
identifiers is refused by the form of the revision.

| Check, after the corrections | Result |
|---|---|
| `ruff format --check`, `ruff check`, `mypy` | Clean: 640 files formatted, no lint finding, no type error in 350 source files |
| `tests/domain/test_desired_state_provenance.py` | 80 passed and none skipped |
| The default lane, `pytest -q -rs` | 18,611 passed, none failed, 39 skipped, 14 deselected, in 26 minutes 30 seconds, with every correction staged. The skips are the same 39 kinds as at the first commit, and none is a test of this change |
| `tools.experiment_freeze --check`, `tools.experiment_e01 --check` | Exit 0 for both |
| `tools.evidence_index --gate`, `--check`, `tools.proof_dashboard --check` | Exit 0, with the same four values |
| `tools.gitops_desired_state --check`, `tools.generated_release --check` | Exit 0 for both |
| `git diff --check` | Clean |

## Gates that do not apply, and work not executed

- **A cluster run.** Not executed. The change is static, and no observation of a
  cluster was asked of it. A later change collects the Argo CD state.
- **An Argo CD static check.** No manifest under `infra/argocd/` changed. The suites
  of the Application ran in the default lane.
- **Helm render and Kubernetes schema of the chart.** No file under `charts/`
  changed. One new test runs `helm template` over the generated values and the
  Application's hand-written values, with Helm ``v3.19.0``.
- **Terraform format, validate, and lint.** Not applicable: no file under `infra/`
  changed.
- **A new freeze revision.** Not needed: no file that a freeze record pins changed,
  and the freeze check passed.
- **A decision record.** None was added. The change alters no accepted decision. It
  reads what ADR 0018 and ADR 0019 decided.

## Privacy and publicability

The diff was read for private planning text, local paths, credentials, account
identifiers, and story identifiers that are not merged. Files are named by repository
path. The record in the document holds commit identifiers, digests, and names that
were public already. The one story identifier that is not merged is this change's
own.

## What this does not establish

- **That an applied object was rendered at a commit.** The tool relates a commit
  to the release that the commit holds. It relates no object to either.
- **That a controller reported the commit.** The commit is an input.
- **That the commit declares the same release paths as the checkout that ran the
  tool.**
- **That the record holds no secret.** One test applies a credential-prefix
  heuristic to every value.
- **That a cluster carries the three labels.** They were read from a render.
- **That Argo CD reports the commit that it applied.**
- **That the values file is what the recorded renderer revision derives.** The tool
  does not render at the commit.
- **That a commit is on `main`, or that a merge was reviewed.**
- **Anything about the API image or the hand-written values.** Neither is read from
  the commit.
- **Anything about a caller.**
- **Anything about `kind`.**
