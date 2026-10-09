# V2-S4-005-PR1 validation

Status: **the comparison of the single-runtime baseline with the two-replica
release now reads the install inputs and the readiness inputs of each side, and
it refuses one that a side states alone. This is static evidence at C0.** No
cluster was read, no run installed either side, and the tool renders nothing. No
chart file, contract, binding, Application, Terraform file, desired-state file,
or freeze record was changed, and no claim was registered.

> [!IMPORTANT]
> **This change corrects an omission of an earlier change, and the record says
> so.** [`V2-S4-003-PR2`](v2-s4-003-pr2-validation.md) added the baseline and its
> comparison. Its validation record states that a refusal of a changed readiness
> input was "not reached by the tool", and that an install adds inputs that the
> baseline does not declare. A review of the sprint on 2026-10-09 reported that
> omission as a defect of the comparison; it was reported to the author, and no
> file in this repository records that review. The earlier record is not edited.
>
> **A `COMPARABLE` record is not eligibility for an experiment.** It says that
> the committed inputs of the two sides are comparable. No run read them.

| Property | Value |
|---|---|
| Date | 2026-10-09 |
| Base | `b5e6d839ae811e963d068806e2511715e08fab5f`, the merge of pull request #132 |
| Branch | `fix/v2-s4-003-baseline-install-readiness-inputs` |
| Host | One Windows workstation, Git Bash (GNU bash 5.2.26); Python 3.12.12 from `uv` 0.9.16; Helm `v3.19.0` |
| Evidence level | C0. Every check reads committed files or renders them with the chart tool |
| Claim effect | None. No claim, ledger, register row, dashboard row, or evidence-index entry was added or changed |

## The defect, reproduced at the base

The edit below was made in a second working tree at the base commit, and then in
the working tree of this change. The file was restored afterwards in both.

**The edit.** In `infra/argocd/local-docker-desktop-support-assistant.yaml`, the
value `spec.source.helm.valuesObject.api.probes.readiness.timeoutSeconds` is set
to `1`. Nothing else is edited. The chart's default for that value is `5`.

| Tree | `python -B -m tools.baseline_profile --check` | `--record` |
|---|---|---|
| The base, unedited | Exit status 0 | `COMPARABLE` |
| The base, with the edit | Exit status 0, and the same three `OK` lines | `COMPARABLE` |
| This change, unedited | Exit status 0 | `COMPARABLE` |
| This change, with the edit | Exit status 1: `baseline-install-differs` at `install: /handWrittenValues/api/probes/readiness/timeoutSeconds`, `baseline-effective-values-differ` at `effective: /api/probes/readiness/timeoutSeconds` with the baseline at `5` and the target at `1`, and `baseline-record-stale` | Exit status 5, `REFUSED` |

At the base the tool did not read the Application. So the edit changed nothing
that it compared. This shows that the comparison did not consume that input. It
does not show that a cluster ran a release with another timeout: nothing was
installed.

## What changed

- **One file is new:**
  `tests/domain/fixtures/experiment-profiles/single-runtime-baseline.install.v1alpha1.yaml`.
  It states the install inputs of the baseline: the chart's repository, revision,
  and path, the release name, the namespace, the generated values file, and the
  hand-written values. A person writes it. Its values are the ones that the
  target's Application states, but for the values file. No procedure reads it.
- **`tools/baseline_profile` compares two more layers.** The install layer is
  the description of each side, with the chart's version and one digest of the
  chart files that a render reads. The effective layer is the values that the
  chart receives on each side: the chart's defaults, then the generated values,
  then the hand-written values. The tool reads the target's description from its
  Application, through the table of Applications that the capacity preflight
  already holds.
- **Four rules are added, so a record states 11.**
  `baseline-install-inputs-refused`, `baseline-install-differs`,
  `baseline-effective-values-differ`, and `baseline-readiness-input-absent`.
- **Three permitted paths are added, so 15 are permitted.** `/valuesFile` in the
  install layer, and the runtime replica count and the workload version in the
  effective layer. The two effective paths are the two generated differences,
  read again after the merge. No path was added to a layer that existed.
- **A record states more.** `installSources`, `installInputs`,
  `effectiveTopology`, `readinessInputs`, `unresolvedInputs`, and
  `experimentEligibility` are new members. The schema name of the record is
  unchanged, `inferops.io/baseline-profile-comparison/v1alpha1`. No reader of
  the record exists but the tool and its suite.
- **The committed record is written again.** The committed baseline release, its
  two generated files, is the same bytes.
- **`tests/domain/test_baseline_profile.py`** gains the tests of the two layers.
  **`tests/architecture/test_helm_chart.py`** now renders each side with the
  inputs of its own description, and it gains two negative controls.
- These pages state the change:
  [the baseline profile page](../../environment/single-runtime-baseline-profile.md),
  `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, the architecture index, the
  Git desired-state page, the Application page, both test inventory files, and
  the proof index. This record is added.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| The comparison binds the install inputs of each side | Reached at C0. Each side states them in one committed file, and the record states both |
| The comparison binds the readiness inputs of each side | Reached at C0, as values. The record states each of 24 probe paths and probe settings for each side, read from the values that the chart receives. It states no rendered probe |
| A one-sided change is refused | Reached at C0. A probe setting, a hand-written value, an API image digest, a release name, a namespace, a chart revision, or a chart repository that one description states alone gives `REFUSED` at its path |
| An absent input is not read as an equal one | Reached at C0. An absent description, an absent member, and a readiness input that both sides lack each refuse the comparison |
| A malformed or unreadable input is refused | Reached at C0. A description that is not YAML, not text, empty, of another kind, or that states a member the tool does not read refuses the comparison |
| The chart revision and content are bound | Reached in part. The record states the chart's version and one digest of the files of the working tree. Both descriptions name the branch `main` as the revision, and nothing reads what a remote names by it |
| The API image identity is bound | Not reached, and stated. The repository and the pull policy are compared. No committed file states the digest, so the record lists it as unresolved |
| The caller profile stays explicit as unresolved | Reached. Every record lists it. This change adds no caller profile |
| Comparability is distinguished from eligibility | Reached. Every record states `experimentEligibility` as `not-established` |
| The replica-derived differences are kept | Reached. The 12 earlier permitted paths are unchanged, and the committed baseline release is the same bytes |

## Decisions taken in this change

**Two concrete descriptions are compared, and neither is derived from the
other.** The baseline could have been bound to the target's Application by
construction. Then no one-sided change could exist, and an edit of the
Application would move both sides without a refusal. With a second file, an edit
of one alone is a difference, and a person must make it twice. The cost is 24
duplicated lines of hand-written values.

**The description is not an Application.** It installs nothing, and no
controller reads it. A baseline Application is a decision on how a run selects
the baseline, and no change has made that decision.

**The whole of the effective values is compared.** The readiness inputs are 24
of 166 leaves. A second list of "relevant" values would be a second place to
forget one.

**The readiness inputs are named, and each must be stated.** A comparison of two
documents reads two absent values as equal. So the 24 paths are a list, and a
test compares the list with the values that the chart's two probe templates
read.

**A member that the tool does not read refuses the comparison.** A Helm
parameter, a second values file, or a second source in the Application is an
install input. The tool cannot compare what it does not read, so it does not
report `COMPARABLE` beside one.

**The schema name of the record is not changed.** The members are added, and
none is removed or renamed.

## The negative controls

Each is a test. Each edits a copy of the inputs in a temporary directory.

| Control | Result |
|---|---|
| API readiness timeout in the target's hand-written values | `REFUSED`: install path and effective path |
| API readiness timeout in the baseline's hand-written values | `REFUSED`: install path and effective path |
| Runtime startup budget in the baseline's hand-written values | `REFUSED`: install path and effective path |
| A null in the baseline that removes a readiness input | `REFUSED`: install path, effective path, and `baseline-readiness-input-absent` |
| Another image pull policy in the baseline | `REFUSED`: install path and effective path |
| A hand-written value that the target lacks, where the chart's default is the same value | `REFUSED`: install path alone |
| An API image digest in the baseline alone | `REFUSED`: install path and effective path |
| A hand-written runtime replica count in the baseline | `REFUSED`: install path, and the effective topology of the baseline |
| A hand-written runtime replica count in both | `REFUSED`: the effective topology of the baseline. The two descriptions are equal |
| Another release name, namespace, chart revision, or chart repository on one side | `REFUSED`: install path |
| A baseline that names the target's values file | `REFUSED`: `install: baseline /valuesFile` |
| A description that is absent, not YAML, not text, empty, of another schema or kind, without a member, or with a member the tool does not read: 13 forms for the baseline and 7 for the target | `REFUSED`: `baseline-install-inputs-refused`, with the three later rules `not-evaluated` |
| A chart without a template, a values schema, a mapping, or a version | `REFUSED` for both sides |
| A readiness input that the chart's defaults no longer state | `REFUSED` for both sides, with no difference in the effective layer |
| One probe timeout given to both descriptions | `COMPARABLE`, and `baseline-record-stale` |
| One changed template | `COMPARABLE` with another chart digest, and `baseline-record-stale` |
| A changed page of the chart, and a changed render fixture | No change to the record |
| Render: a readiness timeout on one side | The rendered readiness probe of the API differs, `1` beside `5`, in one Deployment |
| Render: no scrape annotations on one side | The renders differ in objects that the stated differences do not name |

## Validation

Each command ran on the host of the table above, on the working tree of the
first commit.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 687 files already formatted, with this record |
| `uv run --locked python -m mypy` | No issue in 375 source files |
| `uv run --locked python -m pytest tests/domain/test_baseline_profile.py -q` | 123 passed. The suite held 74 tests before this change |
| `uv run --locked python -m pytest tests/architecture/test_helm_chart.py -q -k baseline` | 3 passed, 267 deselected. `helm` is installed, so none skipped |
| `uv run --locked python -m pytest tests/domain/test_baseline_profile.py tests/architecture/test_helm_chart.py tests/architecture/test_argocd_bootstrap.py tests/architecture/test_argocd_application.py tests/domain/test_generated_release_drift.py tests/domain/test_renderer_input_boundary.py tests/domain/test_gitops_desired_state.py tests/domain/test_capacity_preflight.py tests/testing -q` | 9,162 passed, 7 skipped, and 2 failed. Both failures were the link suite, for the two links to this record, which was not written yet. Six skips are tests that need a symbolic link, which this host cannot create. One is the freeze test that skips after the desired-state release moved from revision 3 |
| `uv run --locked python -m pytest tests/testing/test_document_links.py tests/testing/test_test_inventory.py -q`, after this record was written | 1,600 passed |
| `uv run --locked python -m tools.baseline_profile --check` | Exit status 0: four `OK` lines |
| `uv run --locked python -m tools.generated_release --check` | Exit status 0 |
| `uv run --locked python -m tools.gitops_desired_state --check` | Exit status 0 |
| `uv run --locked python -m tools.capacity_preflight --check` | `PASSED: 7 committed collection(s)` |
| `uv run --locked python -m tools.runtime_model_cache --check` | `PASSED: 1 committed run(s)` |
| `uv run --locked python -m tools.service_endpoint_state --check` | `PASSED: 7 committed collection(s)` |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_e01 --check` | `PASSED: 2 run(s), each agrees with its own evidence` |
| `uv run --locked python -m tools.evidence_index --check` and `--gate` | Exit status 0 for each |
| `uv run --locked python -m tools.proof_dashboard --check` | Exit status 0 |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | Exit status 1, as at the base: 30 material files differ from revision 3. This change moves none that had not moved |
| `helm lint charts/inferops-llm --strict --namespace inferops-platform --values charts/inferops-llm/ci/real-values.yaml`, and the same with `mock-values.yaml` | `1 chart(s) linted, 0 chart(s) failed` for each |
| `git diff --check` against the base | No whitespace error |

**Not run at the first commit.** The whole default lane, which runs at the
second commit. `gitleaks` is not installed on this host, so no secret scan ran.
Hosted CI was not read: no pull request existed. No `kubeconform` command ran,
because no chart file and no rendered fixture changed. No cluster command ran,
because the change reads no cluster.

## What stayed as it was

- **Released V1 evidence and history.** No file under a released path is in the
  diff. `tools.evidence_index --gate` passes.
- **The first experiment.** No freeze record, run, review record, or ledger of
  V2-E01 is in the diff. `tools.experiment_freeze --check` and
  `tools.experiment_e01 --check` pass.
- **The other evidence of this sprint.** The model cache run, the capacity
  preflight reading, and the seven endpoint-state cases are not in the diff, and
  each check of them passes.
- **The earlier validation record of the baseline.** It is not edited.

## Privacy and publicability

The diff was read for private material.

- The install description holds a repository address, a branch name, a release
  name, a namespace, and hand-written values. Each is already in the committed
  Application.
- The record adds those values, one chart version, and one digest of committed
  chart files.
- No credential, secret value, cloud account identifier, model artifact, or path
  of the workstation is in the diff. A refusal names a file under the
  repository root, and a test holds that no record states the path of a copy.
- No planning text, prompt, or identifier of a later change is in the diff.

## What this does not establish

- **That a run installs either side with the described inputs.** No procedure
  reads the baseline's description, and nothing compares a cluster with either.
- **That the baseline is eligible for an experiment.** Every record states the
  eligibility as `not-established`.
- **That both sides install with one API image digest.** No committed file
  states it.
- **That one caller profile is applied to both sides.** None exists.
- **That a cluster reads the chart files whose digest the record states.** The
  digest is of the files of the working tree.
- **That the two sides render equal probes on a cluster, or that a probe
  behaves as its settings state.** The tool compares values. Three tests render
  files. No pod ran.
- **That a cluster ran the baseline**, or what a caller observes when a runtime
  pod stops, under either topology.
- **Anything about availability, reliability, latency, or cost.** The baseline
  is a controlled input of a later comparison. It is not a result.
