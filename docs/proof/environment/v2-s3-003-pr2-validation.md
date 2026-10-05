# V2-S3-003-PR2 validation

Date: 2026-10-05

What this change checked before it was committed, and how. What it adds is described
in [the reconciliation evidence document](../../environment/reconciliation-evidence.md).
This page is about the checks run over the repository after the operation, the tool,
the suites, and the documents were written.

> [!IMPORTANT]
> **The observation ran on one provider.** On 2026-10-05, on the `docker-desktop`
> provider, the `observe` operation read one Application beside an apply, after
> it, and beside a removal.
> [The record of the run](v2-s3-003-pr2-reconciliation-observation-run.md) is the
> `C2` evidence of this change, and it says what the run does not establish. A
> first attempt was aborted, and it is kept there.
>
> **What Argo CD reports is not a caller outcome.** One caller request was sent
> in the run. Nothing else on this page is evidence that a request was answered.
>
> **No claim moves.** The change adds no record to the evidence pack and registers
> no claim.

## Evidence levels on this page

| Evidence | Level | What executed |
|---|---|---|
| [`tests/domain/test_reconciliation_evidence.py`](../../../tests/domain/test_reconciliation_evidence.py) | `C0` | The evidence tool, on directories that the suite wrote, and Git, to read the commit that `HEAD` names |
| The `observe` cases of [`test_argocd_application_procedure.py`](../../../tests/architecture/test_argocd_application_procedure.py) | `C1` | The committed procedure, with `kubectl`, `kind`, `docker`, and `sleep` replaced by recording stubs. Four cases then give the written directory to the evidence tool |
| [`tests/architecture/test_argocd_application.py`](../../../tests/architecture/test_argocd_application.py) | `C0` | Nothing. It reads the procedure and the documents as text |
| [The run of 2026-10-05](v2-s3-003-pr2-reconciliation-observation-run.md) | `C2` | The procedure, with the real tools, on a real cluster of one provider, with a real Argo CD. Bounded to that provider, that host, one day, and one commit |

The levels are defined in [the evidence levels](../../testing/evidence-levels.md).

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `4045295`, the merge of pull
  request 121, which added the desired-state provenance tool.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0
  with `RELEASED v1.0.0` with the set `1d40b33f…` and the pack `652e9051…`, and
  `CURRENT` with the set `0271ae27…` and the pack `222bc533…`. The command was run
  after this change was written. It was not run on `main` in this session.
- **The frozen experiment.** After the last edit, `python -m
  tools.experiment_freeze --check` exited 0 for both freeze records, and `python
  -m tools.experiment_e01 --check` exited 0 for both runs. This change edits no
  file that a freeze record pins. Neither command was run before the first edit
  in this session.

## What changed

- **[`scripts/environment/argocd-application.sh`](../../../scripts/environment/argocd-application.sh)**
  — a fourth operation, `observe`. It reads and does not mutate. The bytes of the
  procedure changed, so its SHA-256 is no longer the one that the transcripts of
  2026-10-04 print. Those transcripts are unchanged.
- **[`tools/reconciliation_evidence`](../../../tools/reconciliation_evidence/core.py)**
  — a new tool. It reads the directory that `observe` writes and prints one
  record. It reads no cluster and writes nothing.
- **[`tests/domain/test_reconciliation_evidence.py`](../../../tests/domain/test_reconciliation_evidence.py)**
  — a new default-lane suite, with 97 cases.
- **Two existing suites of the procedure.** The executed suite went from 95 cases
  to 121: 20 cases of `observe`, and 6 more argument cases. The static suite went
  from 35 cases to 36.
- **One other existing suite.** The render-boundary suite lists the new tool
  beside the four repository checks, because the tool names three of them.
- **[The reconciliation evidence document](../../environment/reconciliation-evidence.md)**
  — a new document. It also states the boundary for a manual change.
- **[The record of the run](v2-s3-003-pr2-reconciliation-observation-run.md)**,
  with two transcripts, five records, and the driver.
- **Indexes and living documents**: the architecture index, the system
  architecture, the Argo CD Application document, the desired-state provenance
  document, the renderer input boundary document, the proof index, the
  contributor guide, the README, the test inventory, and the changelog.

**What did not change.** No file under `charts/`, `src/`, `gitops/`, `infra/`,
`contracts/`, or `.github/`. No decision record. No ownership row. No security
control. No claim. The four mutations of the procedure are the same four.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| A collector for the desired revision, the observed revision, the sync state, and the health state | Reached as an operation and a tool, executed against stubs and on one provider. `observe` reads the Application a stated number of times, and the tool reports `followedRevision`, `resolvedRevision`, `syncStatus`, `healthStatus`, and the last operation at each sample |
| Transitions | Reached as a computation on samples. A transition is a difference in one of eight fields, or in the read of the Application, between two consecutive samples. The run observed 22 transitions beside the apply and 11 beside the removal |
| A bounded collection | Reached. The count and the interval have no default and have limits of 120 and 30 seconds. The time that one read takes is not bounded |
| Tests for missing and unavailable fields | Reached. See [the next section](#missing-stays-missing) |
| A statement that Argo CD state is reconciliation evidence and not caller truth | Reached in the document, in the output of `observe`, and in every record. A test holds each of the three |
| The boundary for an experiment or a break-glass change | Reached as a document: six rules, each with how it is held. Three are held by review, two are not enforced, and one is tested against stubs. No mechanism was added |
| Safe diagnostics | Reached. The record is built from an allowlist, and a message is cut and redacted. The redaction is a heuristic |
| A bounded observation on a cluster, recorded at `C2` | Reached on one provider. Four observations of run 2 are bounded to 80, 5, 40, and 3 samples. The observation of attempt 1 was stopped at 23 samples of 80, and its record says that it is not complete |

## Missing stays missing

The suite holds these properties of the tool. Each is a test on a directory that
the suite wrote.

| Property | Cases |
|---|---|
| A required field that is absent, null, empty, a number, or a mapping has a state other than `reported`, carries no value, and makes the sample not settled with a reason | 25: five fields, five changes each |
| A missing parent leaves each field below it missing | 5 |
| An Application with no status reports no state | 1 |
| A read that did not answer, an absent Application, and an answer that is not one JSON object report no field | 5 |
| No combination of absent required fields is settled | 31 combinations, in one case |
| A value is not carried across a read that did not answer | 1 |
| An Application with a deletion timestamp is not settled | 3 |
| A comparison that could not be made is recorded as not compared | 4 |
| The command exits 0 with a record of reads that did not answer, and the record counts no settled sample | 1 |

## The cluster

1. **The first cluster did not start.** Docker Desktop was started, and its
   Kubernetes cluster reported `failed to start`, twice. It was not reset by this
   change: a reset deletes the cluster.
2. **The owner of the host made a new cluster.** Its first form had two nodes.
   The provider guard refused it, with `provider-mismatch`, because this project
   has observed one node as the shape of Docker Desktop. The guard was not
   changed and not bypassed.
3. **The owner made a cluster of one node, at Kubernetes v1.36.1.** The run used
   it. The earlier runs used v1.34.3.

[The record of the run](v2-s3-003-pr2-reconciliation-observation-run.md) holds
attempt 1, which was aborted, and run 2.

### What the run changed in this change

| Found | Change |
|---|---|
| The record of attempt 1 reported nine transitions into a sample that was never taken | No transition leads to a `not-taken` sample or from one |
| The first record of the observation beside the apply was 1.17 MB | Each distinct list of objects is held once |
| Two samples of an Application that was being deleted were counted as settled | A sample with a deletion timestamp is not settled |
| The driver ran every step after a failed preparation | A failed preparation step ends the driver |

### One client-side check, before the run

The tool reads the labels of an object as one line of JSON after two tab
characters. Before a cluster was available, a real `kubectl` client, version
v1.36.1, printed that form for two local files, with `patch --local` and the
output template of `observe`. The run then read the labels of 26 applied objects
in that form.

## Commands and results

Run on the reference host, from Git Bash, at the working tree of this change.

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q` | 18,741 passed, 36 skipped, and 14 deselected, in 35 minutes 57 seconds. **This was before the run**, at an earlier state of this change. The tool, its suite, and the documents changed afterwards |
| `uv run --locked python -m pytest tests/domain/test_reconciliation_evidence.py tests/architecture/test_argocd_application.py tests/architecture/test_argocd_bootstrap.py tests/domain/test_renderer_input_boundary.py tests/testing -q` | 8,123 passed, after the last edit of a tool, a suite, or the procedure |
| `uv run --locked python -m pytest tests/architecture/test_argocd_application_procedure.py -q` | 121 passed, after the last edit of the procedure and of that suite |
| `uv run --locked ruff check .` | Passed |
| `uv run --locked ruff format --check .` | 645 files already formatted |
| `uv run --locked mypy` | No issues in 354 source files |
| `bash -n scripts/environment/argocd-application.sh` | Exit 0 |
| `uv run --locked python -m tools.experiment_freeze --check` | Passed: 2 freeze records |
| `uv run --locked python -m tools.experiment_e01 --check` | Passed: 2 runs |
| `uv run --locked python -B -m tools.evidence_index --gate` | Exit 0 |
| `uv run --locked python -m tools.gitops_desired_state --check` | Passed |
| `uv run --locked python -m tools.generated_release --check` | Passed |
| `git diff --check` | Exit 0 |

**Not run.**

- **The whole default lane after the last edit.** The affected suites ran. The
  whole lane runs again before the second commit of this change.
- **A run at the final bytes of the tool.** The tool changed after run 2, and
  the committed records were built again from the directories of the run.
- **`shellcheck`.** It is not installed on the reference host. The hosted lint
  job runs it.
- **The hosted workflows.** They run when the change is pushed.
- **The Helm, Terraform, and image checks.** This change edits no chart, no
  Terraform file, and no image.
- **Anything on `kind`.**

## What this does not establish

- **That `observe` works on another cluster**, another Kubernetes version, or
  another Argo CD release.
- **That a read which fails beside a running Argo CD is recorded.** That case
  ran against stubs only.
- **That a reported state is true.** The tool records what was reported.
- **Anything about a caller.**
- **That the boundary for a manual change is followed.** No admission control
  exists. Review holds three of its six rules, and nothing enforces two.
- **That the record holds no secret.** It is built from an allowlist, and the
  redaction of a message is a heuristic.
- **Anything about `kind`.**

## Acceptance

| Criterion of the story | State after this change |
|---|---|
| An applied workload traces to a Git revision and to render provenance | Met on one provider, for one commit, by labels and by commit. In the run, the commit that Argo CD reported resolved to one release, and 26 applied objects carried the three labels that the release derives. No applied object carries the release identifier, and the commit that Argo CD reports is not shown to be the commit it applied |
| The desired revision, the observed revision, and the reconciliation state are collectable | Met on one provider. Not shown on `kind` |
| GitOps state stays separate from caller health | Met as a rule that tests hold in the output and in every record. In the run, one caller request was sent apart from the observations. No caller measurement reads the record |
| A manual `kubectl` change is for an experiment or a break-glass action only | Met as a document. Nothing enforces it |

**What stays open.** The release identifier on an applied object, a way to
suspend reconciliation, a record format for a break-glass action, and `kind`.
[The reconciliation evidence document](../../environment/reconciliation-evidence.md#not-applied-yet)
lists each.
