# V2-S4-001-PR1 validation

Status: **the API tier's reference topology is declared and rendered. Nothing was
installed.** This change makes the chart state the API Deployment's rolling-update
strategy, gives the platform defaults the two bounds of that strategy, and makes the
reference binding state two API replicas. The evidence level of everything below is
C0: committed files were read, the render path ran in memory, and `helm template` and
`helm lint` ran on a workstation. One cluster was read once, read-only, to learn
whether a controller there follows `main`. Nothing was written to it. No release was
installed, no rollout ran, and no request was sent.

| Property | Value |
|---|---|
| Date | 2026-10-07 |
| Base | `2c180eadc4b8ffa1fbe13dbff021fec1f012e800`, the merge of pull request #125 |
| Branch | `feat/v2-s4-001-api-redundancy` |
| Host | One Windows workstation, Git Bash; Python 3.12.12 from `uv` 0.9.16; Helm `v3.19.0` |
| Evidence level | C0, static. No claim was added or changed |

## Eligibility, checked before anything was written

| Check | Result |
|---|---|
| `main` | At the base commit above, with a clean working tree |
| Tag `v1.0.0` | Tag object `17c9bbd7…`, commit `718ad2e0…`, as before |
| `tools.experiment_freeze --check` | Exit 0: 3 freeze records, every rule held |
| `tools.experiment_freeze --changes`, revisions 2 and 3, at the base | Exit 1 for each, with 1 moved file: the runner, as the earlier records state |
| The local cluster | Read once, read-only, on 2026-10-07, with `kubectl --context docker-desktop get applications.argoproj.io -A`. The server answered that it has no resource type `applications`. So no Argo CD Application exists on that cluster, and merging this change applies nothing there. No transcript of the read is committed |

**The requirement is not a decision record of this repository.** Two API replicas and
the two rollout bounds were given to this change as a requirement. No decision record
under `docs/architecture/decisions/` states them. This record says what was built.

## What changed

**The chart, `0.3.0` to `0.4.0`.**

- `api.rollout` joins the values contract: `maxUnavailable` and `maxSurge`, each a
  whole number of pods from 0 to 16, both required. The defaults are 0 and 1.
- The API Deployment states `strategy.type: RollingUpdate` and the two bounds. Chart
  `0.3.0` stated no strategy, so the Kubernetes default applied.
- The schema refuses a percentage, a string, a fraction, a boolean, a missing bound,
  and any other member. The template refuses two zero bounds.
- Both committed renders were regenerated. Each differs from the earlier render in the
  five lines of the strategy and in the chart version label.
- The runtime Deployment and the collector are not changed. Each states no strategy.
- The chart renders no PodDisruptionBudget.

**The platform defaults and the renderer.**

- `ApiRolloutDefaults` holds the two bounds, and `ApiDefaults` requires one. A
  `v1alpha1` set carries five API settings instead of three. Two zeros, a bound outside
  0 to 16, a boolean, a float, and a string are refused at construction.
- The ownership table, the provenance trust table, and the disposition table each gain
  two rows. The render context has 46 values instead of 44. The renderer writes 29
  chart values instead of 27.
- `tools/generated_release` reads the two bounds from the chart's `api` block, where it
  reads the other three defaults.

**The reference binding and the two committed releases.**

- `local-docker-desktop` states `spec.platform.apiReplicas: 2`. `local-kind` still
  states 1.
- The reference release under `tests/domain/fixtures/helm-values/` and the desired-state
  release under `gitops/` were regenerated with the repository's own commands.

**Three test harness changes that the chart and renderer changes made necessary.** They
are listed under [decisions](#decisions-taken-in-this-change), because each is a choice.

## Decisions taken in this change

| # | Decision | Why | What it costs |
|---|---|---|---|
| 1 | The binding owns the API replica count. No new owner was added | `spec.platform.apiReplicas` already owned it, and the ownership table already refused the count from any other layer | The reference count is a fact of one binding. Another binding states its own |
| 2 | The platform defaults own the two rollout bounds | A rollout policy is the same for every workload and environment, and neither the contract nor the binding has a field for it | The defaults are still read from the chart's `api` block. No defaults file exists |
| 3 | The two bounds joined `v1alpha1` in place. No `v1alpha2` | No defaults file is committed at any revision, so no stored document changed its meaning | A caller that built a three-setting set no longer constructs one. Every caller in this repository was changed |
| 4 | Whole pods only. A percentage is refused | The number of pods a percentage resolves to depends on the replica count. Whole pods keep the bounds fixed when the count changes | A policy that should scale with the replica count cannot be stated |
| 5 | The chart version moved to `0.4.0` | The render changed, and `0.3.0` is the version `v1.0.0` released. One version for two renders would hide the change | The chart is no longer the released one. The V1 compatibility record is amended, and the release suite names the moved pin |
| 6 | No PodDisruptionBudget | A budget bounds a voluntary eviction. Nothing in this change evicts a pod, and no test here could state what a budget would bound | An eviction is not bounded. A test fails when the chart first renders a budget |
| 7 | The runtime Deployment is not changed | Its replica count and its rollout are another topology decision | The Kubernetes default still applies to it. A test fails when a runtime rollout value first appears |
| 8 | The experiment suites re-pin a temporary copy of the freeze record | See the next section | The end-to-end runner tests no longer show that the tree holds what revision 2 pinned |

## The first experiment's freeze, and what this change did about it

Revisions 2 and 3 of the first experiment's freeze record pin the chart, the render
package, `tools/generated_release`, and the V1 compatibility record by content. This
change edits files in each of them.

| Command | At the base | With this change |
|---|---|---|
| `tools.experiment_freeze --changes …/freeze-r2.v1alpha1.json` | Exit 1, 1 file | Exit 1, 13 files |
| `tools.experiment_freeze --changes …/freeze-r3.v1alpha1.json` | Exit 1, 1 file | Exit 1, 17 files. It was 16 at the first commit: the second commit edits `tools/gitops_desired_state/core.py`, which revision 3 pins |
| `tools.experiment_freeze --check` | Exit 0 | Exit 0: no record was edited |
| `tools.experiment_e01 --check` | Exit 0 | Exit 0: 2 runs, each agrees with its own evidence |

**No freeze record, run, or review record was edited, and no new freeze revision was
written.** A new run of any part of that experiment was already refused at the base,
and it is still refused, until a later freeze revision classifies each moved file.

**Fifteen tests failed because of the moved files, and the cause was the harness.** The
suites `tests/testing/test_experiment_e01.py` and `tests/testing/test_experiment_freeze.py`
build a temporary repository from the files in the tree and from the committed pins.
The runner refuses a tree that differs from its pins, so nine tests of the first suite
and six of the second failed. Those tests do not assert that the tree holds the pinned
content: the second suite's own description says that no test compares the pins with
today's files, and that a change to a material file may merge.

**What was changed.** `tests/support/e01_repinned_record.py` rewrites the copy of the
record in the temporary repository so that each pin is the digest of the copied file,
classifies each moved pin as the freeze rules require, and registers the copy in the
temporary registry. It writes only under the temporary root. Its reasons state that a
test wrote them.

**What that changes about what the tests show.** They show how the runner and the
listing behave on a tree that agrees with its record, and on one planted difference.
They no longer show, even by accident, that the tree holds what revision 2 pinned.
The runner itself is still held to its pin by the earlier support module.

**The alternative that was not taken.** A fourth freeze revision that re-pins the moved
files would also make the tests pass. It would be a freeze revision of an experiment
whose runs are finished, written to change no criterion and to govern no run. It was
not written. That is a choice a maintainer can reverse: the support module and a
freeze revision do not conflict.

## The release data of `v1.0.0`

`docs/releases/v1.0.0.v1alpha1.json` names `version: 0.3.0` in `Chart.yaml` as the pin of
the released chart, and `tests/testing/test_release.py` required the tree to carry it.
The release data was not edited. The test now names the one pin that `main` has moved,
requires the tree to carry `version: 0.4.0` and not the released pin, and reads the
released pin at the tag in a checkout that holds the tag.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| The reference API replica count is 2 | Reached as configuration. The `local-docker-desktop` binding states 2, the committed desired-state values state 2, and the chart renders 2 from them. **Not reached as an observation**: no release with two API replicas was installed |
| The API rollout uses `maxUnavailable` 0 and `maxSurge` 1 | Reached as a rendered policy. The platform defaults own both bounds, the renderer writes them, and the API Deployment states them. **No rollout ran** |
| The configuration comes from an owner and not from an override | Reached for a file admitted beside generated values: a hand-written file that sets, replaces, or removes the replica count or a bound is refused. **Not reached for any other route**: a values file passed to Helm by hand is not checked, as the renderer page already states |
| The rendered Service, pod template, and configuration are the same at one replica and at two | Reached as a render property: the two renders differ in one line, the API Deployment's `replicas`. No source file under `src/inferops/api` changed. **Not observed**: no request was sent to two replicas, so nothing here shows what a caller, a correlation identifier, or an error response does there |
| The API's readiness reflects what the API itself can do | **Not in this change.** The readiness answer is unchanged: it is still false whenever the selected adapter is unable |
| The API Service's Ready endpoints are observable | **Not in this change.** Nothing here reads an endpoint |
| No path-level resilience claim | Held. No claim was added. The chart README, the chart values, the binding fixture, the binding contract page, the renderer page, the boundary page, the desired-state page, the README, and the CHANGELOG each say that a replica count and a rollout policy are configuration |
| A bounded disruption budget, where appropriate | **Not added**: decision 6 |

## Results at the first commit

| Check | Result |
|---|---|
| `ruff check`, `ruff format --check` | Clean: 654 files formatted, no lint finding |
| `mypy`, and `mypy --platform linux` | No type error in 356 source files, on each platform |
| `helm template`, both committed fixtures | Each render is the committed render, byte for byte |
| `helm template` with `api.rollout.maxSurge=0` | Refused by the template: the two bounds must not both be 0 |
| `helm template` with `api.rollout.maxSurge=25%` | Refused by the schema at `/api/rollout/maxSurge` |
| `helm lint --strict`, real fixture | Exit 0, with no guard failure in the report |
| `tools.generated_release --check` | Exit 0: the reference release is what its declared sources derive |
| `tools.gitops_desired_state --check` | Exit 0: the release is what its declared sources derive, and the tree holds nothing else |
| `tools.evidence_index --check` and `--gate` | Exit 0. The current evidence set `549946af…cbefcc` and pack `06e214dc…3d0720` are the ones the index page already states. The released pair is unchanged |
| `tools.proof_dashboard --check` | Exit 0: the dashboard is what the register produces |
| `tests/testing/test_experiment_e01.py` and `test_experiment_freeze.py` | 279 passed, 1 skipped |
| `tests/domain`, `tests/contracts`, `tests/security`, the chart suite, and the Application suite | 3,748 passed, 4 failed, 31 skipped. The four failures are stated in the next section |
| The default lane | **Not run at the first commit.** It ran on the second commit, and [the result is below](#the-default-lane-on-the-second-commit) |
| `gitleaks` | Not run: it is not installed on this host. The hosted CI job runs it |
| Hosted CI | Not read: no pull request existed when this record was written |

## Four tests fail at the first commit, by construction

A release cannot name the commit that adds it. The desired-state release records the
commit at which the renderer and the chart's `api` defaults were read, and this change
edits both. So the commit that edits them cannot also hold a release that names a
commit holding them.

At the first commit the desired-state release is regenerated from the new inputs and
still names the earlier revision, `c056b9772a3de391fd61589649b1d3ed1c5ac7c4`. That
statement is false for that one commit, and four tests say so:

- `test_the_declared_revision_names_a_commit_that_holds_the_defaults_read_today`: the
  chart at that revision has no `api.rollout`;
- two tests of `tests/domain/test_desired_state_provenance.py`: the chart at that
  revision is `0.3.0`, and the committed renders carry `0.4.0`;
- `test_the_document_names_every_release_and_its_revision`: the desired-state page
  still names the earlier release identifier.

The second commit declares the first commit as the revision, regenerates the release,
and corrects the page.

## The releases, by commit

| Commit | Release identifier in `gitops/` | Both revisions | Chart |
|---|---|---|---|
| The base, `2c180ead…` | `eeda9493e0ffca2af499342e2850c63e30ff7254d094016c816d7fbe23fc01ae` | `c056b9772a3de391fd61589649b1d3ed1c5ac7c4` | `0.3.0` |
| The first commit, `9bc07a57ca112f5e578914d2265c8e7ab2ae4fb0` | `901c4a5ae968d135624c21c8cf118512df8dc3bfa77ece5bffa3cfb87f7f762f` | `c056b9772a3de391fd61589649b1d3ed1c5ac7c4`, which is false for that commit | `0.4.0` |
| The second commit | `f23c37d81fbb297643af9e6005cffd805ac05bc98847a6360894fdd238b41d8c` | `9bc07a57ca112f5e578914d2265c8e7ab2ae4fb0` | `0.4.0` |

The values file is the same at the first and the second commit: SHA-256
`62c677a778cc12388c8070073542bbfbe62d5f9c6faf7908262cdc0fcd897dfc`. The second commit
moves the two revisions and the identifier in the release file, and nothing else in
`gitops/`. The reference release in the test fixtures has the values digest
`0c3cd4cc9f7462f1964d3832c6a7415bdb72dc78cccb5be8a83bd78101212cdd` and keeps its
placeholder revisions.

The second commit edits comments in the chart's values, schema, and templates, and
docstrings in the render package. `helm template` of both fixtures gives the committed
renders after those edits, and the chart's `api` block parses to the same values. So
the release still names a commit whose renderer and defaults derive it.

## What merging this change does

- **It must be merged with a merge commit.** The release names the first commit as its
  revision. A squash or a rebase would leave that commit off `main`, and the release
  would then name a commit that `main` does not hold. The test that reads the defaults
  at the declared revision would skip, not fail.
- **On a cluster where the Argo CD Application is applied, the merge changes the live
  release.** `infra/argocd/local-docker-desktop-support-assistant.yaml` follows `main`
  with automated sync and self-heal. Read from the render: the pod template of the API,
  runtime, and collector Deployments each carries the chart version label, which
  changes, and the API Deployment declares two replicas. So that controller would
  replace the pods of all three Deployments. The runtime is one replica with no stated
  strategy. None of this was observed. The one cluster that was read holds no
  Application.
- **The self-heal check needs another count.** The earlier runs scaled the API
  Deployment from one replica to two as their manual change. Two is now the declared
  count, so that step changes nothing. The Application page says so.

## What the independent review found

Two automated reviewing sessions read the first commit and the staged second commit,
read-only. Neither ran a test. One read the code, the chart, and the tests. One
compared every changed page with the repository. Neither is a person.

**What the first commit got wrong.**

| # | The first commit said | What is true | Corrected |
|---|---|---|---|
| 1 | A percentage "rounds differently at each replica count", in the chart README, the values file, the schema, the template, a test docstring, the CHANGELOG, and this record | Kubernetes documents that it rounds `maxUnavailable` down and `maxSurge` up. At one, two, and three replicas, 25% resolves to 0 and 1, the bounds the chart now states. They first differ at four. So at the replica counts the two bindings state, chart `0.4.0` changes what the Deployment says and not the bounds in effect. This is arithmetic on the documented rule. It was not observed | Every place now states the rule and the counts |
| 2 | This record said "No cluster was contacted", and also that the local cluster was read | One cluster was read once, read-only | The opening paragraph and the eligibility row, with the command |
| 3 | This record gave 16 moved files for freeze revision 3 | 16 at the first commit and 17 at the second | The freeze table |
| 4 | `Chart.yaml` said a values file written against `0.3.0` "still installs" | It passes the schema and renders. Nothing was installed | `Chart.yaml` |
| 5 | The chart README, the values file, the template header, and the CHANGELOG stated what a rollout does under the bounds as a fact | It is what Kubernetes documents. No rollout ran | Each place |
| 6 | The renderer page still said the chart, its templates, and its schema are unchanged | This change adds `api.rollout` to all three | The renderer page |
| 7 | The renderer suite's description still said both bindings render the same bytes, and the refusal suite's still said 44 values | They differ in `api.replicaCount`, and the context has 46 values | Both descriptions |
| 8 | The defaults module said each default is the value "every environment the repository describes runs with" | No environment has run with the rollout bounds. It is the value every values file the repository renders with uses | The module's description |
| 9 | This record said every page the change edits calls the count and the policy configuration | Two edited pages gained a table cell or a row and carry no such sentence | The row names the pages that do |
| 10 | The desired-state page said the second commit regenerated the release | The first commit regenerated the values. The second moved the two revisions and the identifier | The page, with the intermediate identifier |
| 11 | Two tests were named or described with "availability-first" | That is a label, not a measurement | The test name and the docstring state the two bounds |
| 12 | The acceptance row was labelled "Service, correlation, and error behaviour are kept" | The evidence is a render difference of one line | The row's label and its limit |
| 13 | The support module said both that it classifies each moved pin and that it classifies nothing | It writes rows the freeze rules require, each `material: false` with a reason that says a test wrote it | The module's description. A pin new in a revision is now written as `added` |
| 14 | A test was named `…moved_nothing` after the harness change made that true by construction | It shows that a tree and a record re-pinned to it list nothing | The test is renamed and says what it does not show |

**What was missing.** This record did not state the merge style the release depends on,
what the merge does on a cluster that follows `main`, or the consequence for the
self-heal check. The section above states them. It did not name the first commit, the
three release identifiers, or the fifteen tests. Those are stated now.

**The fifteen tests, by name.** In `tests/testing/test_experiment_e01.py`:
`test_a_run_writes_evidence_the_judge_agrees_with`,
`test_a_moved_pinned_input_refuses_the_run`,
`test_an_added_material_file_refuses_the_run`,
`test_a_loaded_module_that_is_not_pinned_aborts_the_run`,
`test_a_second_process_from_another_checkout_aborts_the_run`,
one case of `test_check_finds_an_execution_identity_the_record_does_not_support`,
`test_a_step_that_raises_is_recorded_and_answers_nothing`,
`test_a_tracked_file_changed_during_the_run_aborts_it`, and
`test_the_command_run_from_a_merged_checkout_imports_only_pinned_code`. In
`tests/testing/test_experiment_freeze.py`: the test now named
`test_a_copy_that_agrees_with_its_repinned_record_lists_nothing`,
`test_a_changed_and_an_absent_input_are_listed_and_a_crlf_one_is_not`,
`test_an_added_material_file_is_listed`,
`test_a_new_local_helper_the_runner_imports_is_listed`,
`test_a_pinned_file_the_scope_no_longer_names_is_listed`, and
`test_the_command_reports_moved_inputs_and_an_edited_record`. They were read from one
run of the two suites before the harness change. That run's output is not committed.

**Measured, and left as it is.**

- **The schema is the only refusal of a bad bound.** With `--skip-schema-validation`,
  `helm template` turns `api.rollout.maxSurge=25%` into `maxSurge: 0` and reports
  nothing, and a null `api.rollout` ends in a template error that is not the guard's
  message. The chart README states the first. The template still coerces with `int`.
- **Two rows of the V1 compatibility record say `chart-default` for a value V1 never
  had.** The rows are read against chart `0.4.0`, as the record's amendment says. The
  row format has no member that could say so per row.

**Suggested, and not done.**

- **A test that lists which pins the harness moved.** The reviewer of the code noted
  that `repin_record` returns the moved paths and no test reads them, so the set can
  grow without a test changing. Such a test would compare the committed pins with the
  tree, which the freeze suite's description says no test does. `tools.experiment_freeze
  --changes` lists the set, and this record states it: 13 files for revision 2 and 17
  for revision 3.

## Results at the second commit

| Check | Result |
|---|---|
| `ruff check`, `ruff format --check` | Clean |
| `mypy`, and `mypy --platform linux` | No type error in 356 source files, on each platform |
| `helm template`, both committed fixtures | Each render is the committed render, byte for byte, after the comment edits |
| `tools.generated_release --check`, `tools.gitops_desired_state --check` | Exit 0 for each |
| `tools.experiment_freeze --check`, `tools.experiment_e01 --check` | Exit 0 for each |
| `tools.evidence_index --check` and `--gate`, `tools.proof_dashboard --check` | Exit 0 for each, with the evidence set and pack unchanged |
| The chart suite, five domain suites, the freeze suite, `tests/security`, the link suite, and the inventory suite, with the second commit staged | 3,712 passed, 7 skipped |
| The four tests that failed at the first commit, and the default lane | Run on the committed tree. The results are in the next section |

## The default lane, on the second commit

The lane ran once, on the committed second commit, `4c4e0f0`, with a clean working tree:
`uv run --locked python -m pytest -q -rs`.

| Result | Count |
|---|---|
| Passed | 19,043 |
| Failed | 2 |
| Skipped | 37 |
| Deselected | 14 |
| Duration | 48 minutes 13 seconds |

**The four tests that failed at the first commit passed.**

**Two tests failed, and the third commit corrects them.** Both are cases of
`test_a_planted_defect_is_refused_under_the_rules_it_breaks` in
`tests/domain/test_desired_state_provenance.py`. Each planted its defect by replacing
text of the earlier release: its identifier, and a renderer revision that begins with
`c`. The release in the tree holds neither, so the edit found nothing to replace. The
tool under test was not at fault. The two cases now read the identifier and the
revision from the committed release. After that change the suite was run alone: 80
passed, none skipped. `ruff` and `mypy`, on both platforms, are clean.

**The lane was not run again after the third commit.** The third commit changes that
one test module and this record. Every other result above is the lane's.

**One skip is new, and it is a consequence of this change.**
`test_revision_three_names_what_the_files_it_pins_hold` in
`tests/testing/test_experiment_freeze.py` compares freeze revision 3 with the release
files while they have their pinned content. The release changed, so the test reports
that and skips, as it was written to. It no longer checks anything. The other 36
skips are host limits and fixtures that a layer does not read: symbolic links that this
Windows host cannot create, one POSIX signal case, and the schema-only fixtures.

## Privacy and publicability

The diff was read for private material before each commit. It holds no credential, no
secret value, no personal path, no cloud account identifier, no model artifact, and no
generated machine state. The API image digest in both committed renders is the
documented placeholder, as before.

## What this does not establish

- **That two API replicas run.** The count is in a binding, in a values file, and in a
  render. No release with that count was installed.
- **Anything about a rollout.** No rollout ran. The two bounds are a policy the
  Deployment controller would apply to a template change.
- **Anything about a pod deletion, a node loss, or an eviction.** A rollout policy does
  not bound any of them, and the chart renders no disruption budget.
- **That a caller is served when one API pod is unavailable.** No request was sent. The
  API's readiness answer still follows the selected adapter, so an adapter that is
  unable makes every API replica not ready at once.
- **That the host has room for the topology.** The chart's API requests sum to 200m CPU
  and 256Mi for two replicas, and to 300m and 384Mi while a rollout runs. No capacity
  check was run.
- **That chart `0.4.0` installs.** It was rendered and linted. It was installed nowhere.
- **That the first experiment's results hold for this tree.** Those runs read the files
  their freeze revisions pinned. Thirteen of the files revision 2 pins differ now,
  and seventeen of the files revision 3 pins.
