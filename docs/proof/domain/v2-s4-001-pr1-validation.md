# V2-S4-001-PR1 validation

Status: **the API tier's reference topology is declared and rendered. Nothing was
installed.** This change makes the chart state the API Deployment's rolling-update
strategy, gives the platform defaults the two bounds of that strategy, and makes the
reference binding state two API replicas. The evidence level of everything below is
C0: committed files were read, the render path ran in memory, and `helm template` and
`helm lint` ran on a workstation. No cluster was contacted, no release was installed,
no rollout ran, and no request was sent.

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
| The local cluster | Read once, read-only: the `docker-desktop` context answered, and it holds no Argo CD Application resource type. So no controller on that cluster follows `main`, and merging this change applies nothing there |

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
| 4 | Whole pods only. A percentage is refused | A percentage rounds to a different number of pods at each replica count | A policy that should scale with the replica count cannot be stated |
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
| `tools.experiment_freeze --changes …/freeze-r3.v1alpha1.json` | Exit 1, 1 file | Exit 1, 16 files |
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
| Service, correlation, and error behaviour are kept | Reached as a render property: at one replica and at two, the render differs in one line, the API Deployment's `replicas`. No source file under `src/inferops/api` changed. **Not observed**: no request was sent to two replicas |
| The API's readiness reflects what the API itself can do | **Not in this change.** The readiness answer is unchanged: it is still false whenever the selected adapter is unable |
| The API Service's Ready endpoints are observable | **Not in this change.** Nothing here reads an endpoint |
| No path-level resilience claim | Held. No claim was added, and every page this change edits says that a replica count and a rollout policy are configuration |
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
| The default lane | **Not run at the first commit.** It is run on the final tree, and the result is recorded below when it exists |
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
and corrects the page. The four tests are run again there.

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
  their freeze revisions pinned. Thirteen of the files revision 2 pins differ now.
