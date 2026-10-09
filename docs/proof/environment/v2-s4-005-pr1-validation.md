# V2-S4-005-PR1 validation

Status: **the comparison of the single-runtime baseline with the two-replica
release now reads the install inputs and the readiness inputs of each side, and
it refuses one that a side states alone. This is static evidence at C0.** No
cluster was read, no run installed either side, and the tool renders nothing. No
chart file, contract, binding, Application, Terraform file, desired-state file,
or freeze record was changed, and no claim was registered. An independent
review found that the first commit left seven edits of the Application
unrefused, did not hold the target's committed values file, and overstated what
the tool reads: see
[what the independent review found](#what-the-independent-review-found).

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
| Commits | `fa3824f5`: the install description, the two layers, the four rules, the suites, and the pages. A second commit: the corrections of the independent review, and the default lane |
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
| This change at the first commit, with the edit | Exit status 1: `baseline-install-differs` at `install: /handWrittenValues/api/probes/readiness/timeoutSeconds`, `baseline-effective-values-differ` at `effective: /api/probes/readiness/timeoutSeconds` with the baseline at `5` and the target at `1`, and `baseline-record-stale` | Exit status 5, `REFUSED` |

At the base the tool did not read the Application. So the edit changed nothing
that it compared. This shows that the comparison did not consume that input. It
does not show that a cluster ran a release with another timeout: nothing was
installed.

## What changed

- **One file is new:**
  `tests/domain/fixtures/experiment-profiles/single-runtime-baseline.install.v1alpha1.yaml`.
  It states the install inputs of the baseline: the chart's repository, revision,
  and path, the release name, the namespace, the cluster address, the generated
  values file, and the hand-written values. A person writes it. Its values are
  the ones that the target's Application states, but for the values file. No
  procedure reads it.
- **`tools/baseline_profile` compares two more layers.** The install layer is
  the description of each side, with the chart's version and one digest of the
  chart's files. The effective layer is the chart's defaults, then the derived
  generated values of the side, then its hand-written values. The tool reads the target's description from its
  Application, through the table of Applications that the capacity preflight
  already holds.
- **Four rules are added, so a record states 11.**
  `baseline-install-inputs-refused`, `baseline-install-differs`,
  `baseline-effective-values-differ`, and `baseline-readiness-input-unusable`.
  The check adds one more rule, so it adds 3:
  `baseline-target-release-drifted`.
- **Three permitted paths are added, so 15 are permitted.** `/valuesFile` in the
  install layer, and the runtime replica count and the workload version in the
  effective layer. The two effective paths are the two generated differences,
  read again after the merge. No path was added to a layer that existed.
- **A record states more.** `installSources`, `installInputs`,
  `targetDelivery`, `effectiveTopology`, `readinessInputs`, `unresolvedInputs`, and
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
| The comparison binds the install inputs of each side | Reached at C0 for the chart's repository, revision, and path, the release name, the namespace, the cluster address, the values file, and the hand-written values: each side states them in one committed file, and the record states both. The project, the sync policy, and the name of the Application are stated for the target and are not compared, because the baseline names no controller. The `apiVersion` of the Application is not read |
| The comparison binds the readiness inputs of each side | Reached at C0, as values. The record states 24 values for each side, read from the effective values: the 23 that the two probe templates read, and the runtime's startup budget. It states no rendered probe. The chart's defaults supply all 24 for both sides, so the two sides can differ in one only through a hand-written value |
| A one-sided change is refused | Reached at C0. A probe setting, a hand-written value, an API image digest, a release name, a namespace, a cluster address, a chart revision, a chart repository, or a chart path that one description states alone gives `REFUSED` at its path |
| An absent input is not read as an equal one | Reached at C0. An absent description, an absent member, and a readiness input that both sides lack each refuse the comparison. An absent values file of the target fails the check and does not change the comparison, which derives the values |
| A malformed or unreadable input is refused | Reached at C0, with one stated limit. A description that is not YAML, not text, empty, of another kind, that states a key twice, that refers to itself, or that states another member in a block the tool reads refuses the comparison. The forms not YAML, not text, and empty are planted for the baseline's file only. A readiness input of an unusable type is refused. Another value is not checked against the chart's schema, and the tool parses YAML 1.1, which Helm's parser does not do for every plain scalar |
| The chart revision and content are bound | Reached in part. The record states the chart's version and one digest of the files of the working tree. Both descriptions name one chart path, so the two digests are equal by construction: the digest binds the record to the chart, and the compared input is the path. Both descriptions name the branch `main` as the revision, and nothing reads what a remote names by it |
| The API image identity is bound | Not reached, and stated. The repository and the pull policy are compared. No committed file states the digest, so the record lists it as unresolved, and the result stays `COMPARABLE`. Nothing in this repository refuses a run while the digest is unresolved |
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
forget one. Both sides read one defaults file, so this layer finds a
hand-written value, a null, or a hand-written replica count. It is not a second
source of evidence about the chart's defaults.

**The unresolved digest does not refuse the comparison.** A refusal would make
`COMPARABLE` unreachable, because no committed file can state a digest that
names a build on one host. So the record states the digest as unresolved and
the eligibility as `not-established`.

**The readiness inputs are named, and each must be stated.** A comparison of two
documents reads two absent values as equal. So the 24 paths are a list, and a
test compares the list with the values that the chart's two probe templates
read.

**Another member in a block that the tool reads refuses the comparison.** A
Helm parameter, a second values file, a second source, an annotation, or a
top-level `operation` in the Application is an input. The tool cannot compare
what it does not read, so it does not report `COMPARABLE` beside one. Three
members are the exception, and the record states them: the project, the sync
policy, and the Application's name.

**The schema name of the record is not changed.** The members are added, and
none is removed or renamed.

## The negative controls

Each is a test. Each edits a copy of the inputs in a temporary directory.

| Control | Result |
|---|---|
| API readiness timeout in the target's hand-written values | `REFUSED`: install path and effective path |
| API readiness timeout in the baseline's hand-written values | `REFUSED`: install path and effective path |
| Runtime startup budget in the baseline's hand-written values | `REFUSED`: install path and effective path |
| A null in the baseline that removes a readiness input | `REFUSED`: install path, effective path, and `baseline-readiness-input-unusable` |
| Another image pull policy in the baseline | `REFUSED`: install path and effective path |
| A hand-written value that the target lacks, where the chart's default is the same value | `REFUSED`: install path alone |
| An API image digest in the baseline alone | `REFUSED`: install path and effective path |
| A hand-written runtime replica count in the baseline | `REFUSED`: install path, and the effective topology of the baseline |
| A hand-written runtime replica count in both | `REFUSED`: the effective topology of the baseline. The two descriptions are equal |
| Another release name, namespace, cluster address, chart revision, chart repository, or chart path on one side | `REFUSED`: install path |
| Scrape annotations switched off in the baseline | `REFUSED`: install path and effective path |
| A baseline that names the target's values file | `REFUSED`: `install: baseline /valuesFile` |
| A description that is not read whole: 17 forms for the baseline and 12 for the target. They are a file that is absent, not YAML, not text, or empty; another schema or kind; an absent member; another member, among them a Helm parameter, an annotation, and a top-level `operation`; a key stated twice; a description that refers to itself; a chart path that leaves the tree, that is absent, or that is in another case; a values file that is absolute or not from the root; two values files; and hand-written values that are a list | `REFUSED`: `baseline-install-inputs-refused`, with the three later rules `not-evaluated` |
| No Application declared for the target | `REFUSED`: `baseline-install-inputs-refused` for the target |
| A chart without a template, a values schema, a mapping, or a version | `REFUSED` for both sides |
| A readiness input that the chart's defaults no longer state | `REFUSED` for both sides, with no difference in the effective layer |
| A readiness input that both sides hold as a text, a zero, a list, an empty path, or a path without a slash | `REFUSED` for both sides |
| Probes switched to the plain text `n` on both sides | `REFUSED` for both sides |
| A text that is not a digest, on both sides | `COMPARABLE`, and the digest stays unresolved |
| Another project, or another sync policy, in the Application | `COMPARABLE`, and `baseline-record-stale` |
| A hand edit of the committed target values, and a missing target values file | The comparison is unchanged, and the check reports `baseline-target-release-drifted` |
| One probe timeout given to both descriptions | `COMPARABLE`, and `baseline-record-stale` |
| One changed template, a changed ignore file, an added subchart, and an added definition file | `COMPARABLE` with another chart digest each time, and `baseline-record-stale` |
| A changed page of the chart, and a changed render fixture | No change to the record |
| Render: a readiness timeout on one side | The rendered readiness probe of the API differs, `1` beside `5`, in one Deployment |
| Render: no scrape annotations on one side | No pod template of that side carries the scrape annotation, and each pod template of the other side does |

## Validation at the first commit

Each command ran on the host of the table above, on the working tree of the
first commit.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 687 files already formatted, with this record |
| `uv run --locked python -m mypy` | No issue in 375 source files |
| `uv run --locked python -m pytest tests/domain/test_baseline_profile.py -q` | 123 passed. The suite held 74 tests at the base |
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

## What the independent review found

Three reviewers read the first commit. None was given this record's
conclusions. One tried to defeat the comparison, one compared each sentence
with the code, and one read the design against what the change was asked to
reach. **Two of them made the first commit report `COMPARABLE`, with the check
at exit status 0, for an Application that was edited on one side.**

### What the tool got wrong

- **Seven edits of the Application alone were not refused, and none of them
  made the record stale.** The first commit admitted `spec.project`,
  `spec.syncPolicy`, and `spec.destination.server` and read none of them. It
  did not read `metadata` or a top-level member. So another cluster address,
  another project, another sync policy, a removed sync policy, another name, an
  annotation, and a top-level `operation` with its own source and Helm
  parameters each left the result `COMPARABLE`. The rule said that a
  description "states each member this tool reads and no other", and that was
  false. Now the cluster address is an install input of both descriptions and
  is compared. The document and `metadata` are read as blocks, and another
  member in them refuses the comparison. The project, the sync policy, and the
  name are stated in the record under `targetDelivery`: they are not compared,
  because the baseline names no controller, and a change to one makes the
  record stale. The rule and the pages say which members are compared, which
  are stated, and which are not read.
- **The values file of the target was never opened, and it did not have to
  exist.** The effective values are built from the derived generated values.
  The check held the baseline's committed file to them and not the target's. A
  hand edit of the target's committed values, or a copy without that file, left
  the check at exit status 0. The check now holds the target's committed
  release too, under `baseline-target-release-drifted`. The comparison itself
  still derives the values, and the pages say so.
- **A readiness input was checked for presence and not for a usable value.**
  A text, an empty path, a list, or a mapping on both sides was "stated", and
  the rule held. Each input now has a type: a path that starts with a slash,
  true or false, or a whole number above zero. The rule's identifier changed
  from `baseline-readiness-input-absent` to
  `baseline-readiness-input-unusable`.
- **Two parsers read some plain scalars differently, and the tool did not say
  so.** A plain `n` is a text for the tool and false for Helm. With `n` in one
  description and `"n"` in the other, the tool read two equal texts. For a
  readiness input the type rule now refuses both. For another value the limit
  stands, and the pages and the record state it. The tool does not validate a
  value against the chart's schema.
- **The chart digest left out files that a render reads.** It held three named
  files and the templates. A changed `.helmignore`, an added subchart, and an
  added definition file did not move it. It now holds each file of the chart
  directory but the chart's page and the render fixtures.
- **A chart path in another case was accepted on this host.** A file system
  that ignores case opened it. The tool now compares each segment with the
  name that its directory lists.
- **A key stated twice was read as its last value.** The loader of a
  description now refuses it.
- **A description that refers to itself ended the command with a traceback**,
  and so did a document nested very deeply. Each is a refusal now.
- **Any text resolved the API image digest, and two different digests
  resolved it too.** The record lists the digest as unresolved unless both
  sides hold one digest of the form `sha256:` and 64 hexadecimal digits.
- **A value that JSON cannot state made a record that is not JSON.** A
  not-a-number value is now stated as its text.

### What the first commit said, and what is true

- **"The values that the chart receives".** The tool derives the generated
  values and merges them. It reads no cluster and does not open the values file
  that a description names. The rule, the pages, and the changelog now say
  "effective values", and say how they are built.
- **"Each side must state each of the 24."** Neither description states a
  readiness input. The chart's one defaults file supplies all 24 for both
  sides. So the rule is broken by a null, by a changed default, or by a
  hand-written value of another type, and the pages say that.
- **"Each value that the chart's probe templates read."** The templates read
  23. The 24th is the runtime's startup budget, which the chart's validation
  compares with the probe budget. The validation compares two more values with
  a startup budget, the two progress deadlines. They are compared as effective
  values, and nothing requires that they are stated. The page said "one more".
- **"The digest of the files that a render reads", "in the order of the
  paths".** The first commit hashed a fixed list in another order. The text and
  the code now agree.
- **The chart digest was graded as a comparison.** Both descriptions name one
  chart path, so the two digests are equal by construction. This record now
  says that the path is the compared input and that the digest binds the
  record.
- **"The suite plants each of these"** was false for another chart path, and
  the page's render control named an edit that the domain suite did not plant.
  Both are tests now: another chart path, and scrape annotations switched off.
- **The inventory said more than the tests assert.** The chart cases did not
  assert the rule states or the absence of a host path, and 13 one-sided cases
  were said to run "through the command" when one does. The assertions are
  added, and the row says which run through the command.
- **This record graded three rows too high.** "The comparison binds the install
  inputs" said "Reached" while three members were not compared. The malformed
  row did not say that three forms are planted for one side only. The API image
  row did not say that nothing refuses a run while the digest is unresolved.
- **Counts differed between pages.** The architecture index said 13 rules and
  the other pages said 11. Each now says 11 in a record and 3 in the check.
- **The README named four kinds of permitted path and omitted the two of the
  declaration layer.** It names them now.
- **"A change to the chart in the Application alone is refused."** A changed
  chart file is comparable and stale. The page now says the chart's repository,
  revision, or path.
- **"The model cache claim is not a compared input."** The claim's name and its
  mount are compared. Its content and its state are not. The line is corrected.
- **Three statements that the first commit did not touch were stale**: the
  inventory's narrative of four layers, the tool's "one input replaced" beside
  two, and "the comparison rests on the parsers" beside a page that says the
  opposite. The attribute file's comment did not name the hand-written
  description that its pattern now holds. The earlier changelog entry now
  points at the later one.

### Noted, and not changed

- **An unresolved digest does not refuse the comparison.** The reason is under
  "Decisions taken in this change". Nothing enforces the unresolved state
  anywhere: a later gate of a run owns that.
- **The effective layer is equal by construction for chart defaults.** It
  finds a hand-written value, a null, and a hand-written replica count.
- **The record's schema name is still `v1alpha1`**, with seven added members.
  No reader exists but the tool and its suite.
- **The record holds the hand-written values verbatim.** A secret that a
  person writes into a description would be copied into the committed record.
  The Application is a public file already.
- **The tool holds its own copy of the values merge**, as the capacity
  preflight does. A test now holds that the two copies give equal results.
- **A description with many nested aliases is slow to refuse.** A reviewer measured one such file at
  about a minute.
- **A mapping with a key that is not text is compared whole**, so its finding
  is long.
- **Symbolic links were not tried.** This host cannot create one.
- **Every chart change now makes the committed record stale**, and a person
  runs `--write`. That is the cost of the digest.
- **Three members of the Application are not read**: `apiVersion`,
  `metadata.namespace`, and `metadata.labels`.

## Validation at the second commit

Each command ran on the same host, from the working tree that the second commit
holds.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 687 files already formatted |
| `uv run --locked python -m mypy` | No issue in 375 source files |
| `uv run --locked python -m pytest tests/domain/test_baseline_profile.py -q` | 146 passed. The first commit held 123 |
| `uv run --locked python -m pytest tests/architecture/test_helm_chart.py -q` | 270 passed. `helm` is installed, so none skipped |
| `uv run --locked python -m tools.baseline_profile --check` | Exit status 0: four `OK` lines |
| `uv run --locked python -m tools.generated_release --check`, `tools.gitops_desired_state --check`, `tools.capacity_preflight --check`, `tools.runtime_model_cache --check`, `tools.service_endpoint_state --check`, `tools.experiment_freeze --check`, `tools.experiment_e01 --check`, `tools.evidence_index --check`, `tools.evidence_index --gate`, and `tools.proof_dashboard --check` | Exit status 0 for each |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 30 material files differ, as at the base |
| `git diff --check` against the base | No whitespace error |

**The edit of "The defect, reproduced at the base" was not made again at the
second commit by hand.** A test makes it in a copy and holds the refusal:
`test_a_readiness_input_changed_in_the_target_alone_is_refused_by_the_command`.

## The default lane

`uv run --locked python -m pytest -q` ran once, on the working tree of the
second commit before this section was written: 20,051 passed, 37 skipped, and
14 deselected, in 29 minutes. No test failed.

The lane skipped 37 tests, for four kinds of reason: a fixture that a schema
layer does not apply to, a symbolic link that this host cannot create, a POSIX
signal that this host does not deliver, and the freeze test that skips after
the desired-state release moved from revision 3. The earlier changes of this sprint
record the same count on this host. The three render tests of this change ran:
`helm` is installed.

This section and the section above are the one edit after that run. They change
this page only. The link suite ran again for this page afterwards.

**Not run.** `gitleaks` is not installed on this host, so no secret scan ran.
Hosted CI was not read: no pull request existed. No cluster command ran,
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
- **The Application.** It is not edited. The baseline's description gained the
  cluster address that the Application already states.

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
  The Application that a cluster holds carries one Helm parameter that the
  committed file does not.
- **That the baseline is delivered as the target is.** The project and the sync
  policy are stated for the target and are not compared.
- **That Helm reads each hand-written value as this tool does.** The tool
  parses YAML 1.1 and validates no value against the chart's schema.
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
