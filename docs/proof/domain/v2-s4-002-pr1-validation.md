# V2-S4-002-PR1 validation

Status: **the serving runtime tier's reference topology is declared and rendered.
Nothing was installed.** This change makes the chart state the runtime Deployment's
rolling-update strategy, gives the platform defaults the two bounds of that strategy,
adds a contract version that declares two runtime replicas, and renders the
desired-state release from it. The evidence level of everything below is C0: committed
files were read, the render path ran in memory, and `helm template` and `helm lint` ran
on a workstation. One cluster was read once, read-only, to learn whether a controller
there follows `main`. Nothing was written to it. No release was installed, no rollout
ran, no model was loaded, and no request was sent.

| Property | Value |
|---|---|
| Date | 2026-10-08 |
| Base | `ee1edcdc94fab22d53a50dd7e925f750fce4f551`, the merge of pull request #127 |
| Branch | `feat/v2-s4-002-runtime-redundancy` |
| Host | One Windows workstation, Git Bash; Python 3.12.12 from `uv` 0.9.16; Helm `v3.19.0` |
| Evidence level | C0, static. No claim was added or changed |

## Eligibility, checked before anything was written

| Check | Result |
|---|---|
| `main` | At the base commit above, with a clean working tree |
| Tag `v1.0.0` | Tag object `17c9bbd7…`, commit `718ad2e0…`, as before |
| `tools.experiment_freeze --check` | Exit 0: 3 freeze records, every rule held |
| `tools.experiment_freeze --changes`, at the base | Exit 1 for each revision: 14 moved files for revisions 1 and 2, and 23 for revision 3. The two changes before this one moved them, as their records state |
| The local cluster | Read once, read-only, on 2026-10-08, with `kubectl --context docker-desktop get applications.argoproj.io -A`. The server answered that it has no resource type `applications`. So no Argo CD Application exists on that cluster, and merging this change applies nothing there. No transcript of the read is committed |

**The requirement is not a decision record of this repository.** Two runtime replicas
and the two rollout bounds were given to this change as a requirement. No decision
record under `docs/architecture/decisions/` states them. This record says what was
built.

## What changed

**The chart, `0.4.0` to `0.5.0`.**

- `runtime.rollout` joins the values contract: `maxUnavailable` and `maxSurge`, each a
  whole number of pods from 0 to 16, both required. The defaults are 1 and 0. It takes
  the schema definition that `api.rollout` already takes.
- The runtime Deployment states `strategy.type: RollingUpdate` and the two bounds.
  Chart `0.4.0` stated no strategy for the runtime, so the Kubernetes default applied.
- The template refuses two zero bounds for the runtime, under either profile. The one
  guard now covers both tiers.
- Both committed renders were regenerated. The real render differs from the earlier
  render in the five lines of the runtime strategy and in the chart version label. The
  mock render differs in the chart version label alone: it renders no runtime.
- The collector is not changed. It states no strategy.
- The chart renders no PodDisruptionBudget and no autoscaler.

**The platform defaults and the renderer.**

- `RuntimeRolloutDefaults` holds the two bounds, `RuntimeDefaults` requires one, and
  `PlatformDefaults` requires a `RuntimeDefaults`. A `v1alpha1` set carries seven
  settings instead of five. Two zeros, a bound outside 0 to 16, a boolean, a float, and
  a string are refused at construction. The API tier's bounds and the runtime tier's
  bounds are two types, and each tier refuses the other's.
- The ownership table, the provenance trust table, and the disposition table each gain
  two rows. The render context has 48 values instead of 46. The renderer writes 31
  chart values instead of 29.
- `tools/generated_release` reads the two bounds from the chart's `runtime.rollout`
  block. The function that reads the defaults keeps its name, because the first
  experiment's pinned runner imports it by that name.

**The contract and the two committed releases.**

- `contracts/workload/examples/valid/synchronous-llm-two-replicas.yaml` is new. It is
  version `0.2.0` of the reference workload, and it declares
  `spec.scaling.minimumReplicas: 2` and `maximumReplicas: 2`. It differs from the
  `0.1.0` document in the version, the description, and the replica range. A test
  compares every other member.
- The desired-state release under `gitops/` is declared to be derived from the new
  contract. It was regenerated with the repository's own command.
- The reference release under `tests/domain/fixtures/helm-values/` still comes from the
  `0.1.0` contract. It was regenerated, and it gained the two runtime bounds.

## Decisions taken in this change

| # | Decision | Why | What it costs |
|---|---|---|---|
| 1 | The WorkloadContract owns the runtime replica count. No new owner was added, and the binding was not given one | `spec.scaling` already owned it, the binding's schema already refuses a `runtimeReplicas` field, and the ownership table already refused the count from any other layer | One contract document states one count. A second count needs a second document |
| 2 | A second contract document declares two replicas, at workload version `0.2.0`. The `0.1.0` document is not edited | The `0.1.0` document is the V1 workload: the V1 compatibility comparison and the fixture release are derived from it, and V1 ran one runtime. A changed replica range is a new version of the contract | Two documents carry the same pins. A test holds them equal outside the version, the description, and the two members of the replica range. In the render of the desired-state release the workload version changes one ConfigMap value and the configuration checksum annotation of two pod templates |
| 3 | The platform defaults own the two runtime rollout bounds | A rollout policy is the same for every workload and environment, and neither the contract nor the binding has a field for it | A workload owner cannot choose a surge pod for the runtime. The defaults are still read from the chart's values file. No defaults file exists |
| 4 | The two bounds joined `v1alpha1` in place. No `v1alpha2` | No defaults file is committed at any revision, so no stored document changed its meaning | A caller that built a five-setting set no longer constructs one. Every caller in this repository was changed |
| 5 | `maxUnavailable` 1 and `maxSurge` 0 | A surge pod for the runtime is one more loaded model. The requirement names these bounds | Kubernetes documents that such a rollout may run one runtime pod fewer than the replica count until each replacement is Ready. At one replica that is none. The chart does not refuse that combination. No rollout was run |
| 6 | The chart version moved to `0.5.0` | The render changed, and the bounds in effect changed at the replica counts the repository renders | The V1 compatibility record is amended again, and the release suite names the moved pin again |
| 7 | The chart's schema still permits a runtime surge bound above 0 | The bound is a platform default, and the schema definition is shared with the API tier. A chart-level refusal would be a second owner of the policy | A values file given to Helm directly can state a surge pod. A file admitted beside generated values cannot |
| 8 | No PodDisruptionBudget, no autoscaler, no capacity check, and no model-cache check | Each is another change's subject | An eviction is not bounded, and nothing refuses an environment that cannot run two runtime pods |
| 9 | No new freeze revision for the first experiment | The runs of that experiment are finished, and the earlier changes took the same course | See the next section |
| 10 | The bounds are the chart's default, so they also apply to a release with one runtime replica | The platform defaults are read from the chart's values, and one policy for every generated release is the ownership rule. A second default for one-replica releases would be a second owner | The V1 values file, the fixture release, and a default install now render bounds under which a rollout may remove the one runtime pod first. Three V1 pages described the earlier behaviour as general. Each now carries a dated note. See [the V1 procedures](#the-v1-procedures-and-the-new-default) |
| 11 | The provenance command gained no option for an earlier declaration | The command reads a commit with the declaration of its checkout, as its page states. A commit that a controller reports after this change holds the new contract | The command refuses a commit from before this change. The library function still reads one, when it is given the declaration that held |

## The first experiment's freeze

The freeze records of the first experiment pin the chart, the render package,
`tools/generated_release`, `tools/gitops_desired_state`, the desired-state release, and
the V1 compatibility record by content. This change edits files in each of them.

| Command | At the base | With this change |
|---|---|---|
| `tools.experiment_freeze --changes …/freeze-r1.v1alpha1.json` | Exit 1, 14 files | Exit 1, 15 files |
| `tools.experiment_freeze --changes …/freeze-r2.v1alpha1.json` | Exit 1, 14 files | Exit 1, 15 files |
| `tools.experiment_freeze --changes …/freeze-r3.v1alpha1.json` | Exit 1, 23 files | Exit 1, 25 files |
| `tools.experiment_freeze --check` | Exit 0 | Exit 0: no record was edited |
| `tools.experiment_e01 --check` | Exit 0 | Exit 0: 2 runs, each agrees with its own evidence |

The file new to each listing is `charts/inferops-llm/templates/runtime-deployment.yaml`.
Revision 3 also gains `tools/gitops_desired_state/__main__.py`. Every other pinned file
this change edits was already listed at the base. The new contract document is not listed:
no freeze record names it, and no record's scope covers it.

**No freeze record, run, or review record was edited, and no new freeze revision was
written.** A new run of any part of that experiment was already refused at the base,
and it is still refused, until a later freeze revision classifies each moved file. The
desired-state release now names another contract than the one revision 3 pins. So a
later real-deployment run needs a freeze revision that names the new contract.

## The V1 procedures and the new default

The chart's default runtime bounds apply at every replica count, and the chart's default
replica count is one. The V1 real values file and the fixture release render one runtime
replica, so each now renders `maxUnavailable` 1 and `maxSurge` 0 for it.

Three V1 pages described a rollout at one replica as it behaved on chart `0.3.0`, where
the Kubernetes default applied: the upgrade and rollback experiment, the unready-model
recovery, and the operator runbook. They say that the candidate pod is started beside
the serving pod and that the serving pod keeps serving while a candidate fails. Under
the bounds chart `0.5.0` states, Kubernetes documents that the serving pod may be
removed first. That was not observed.

**What was done.** Each of the three pages gained a note dated 2026-10-08. The chart
README and the chart's values say the same. No descriptor, script, record tool, or
published record of those procedures was edited, and none was run again.

**What was not done.** The two procedures were not changed to state the earlier bounds
in their own values, and their static suites were not changed. A rerun of either on
chart `0.5.0` would run under bounds its descriptor does not expect. That is a decision
for the change that reruns them. A maintainer can also reverse decision 10: a chart
default of 0 and 1, with the two-replica release stating 1 and 0 from another owner,
would keep the V1 behaviour. That needs an owner for the bounds that is not the chart's
values file, and no such owner exists.

## The release data of `v1.0.0`

`docs/releases/v1.0.0.v1alpha1.json` names `version: 0.3.0` in `Chart.yaml` as the pin of
the released chart. The release data was not edited. `tests/testing/test_release.py`
names the one pin that `main` has moved, and now requires the tree to carry
`version: 0.5.0` and not the released pin.

The V1 compatibility record states the relation to the released chart. It was measured
for this change: the chart was extracted from the `v1.0.0` tag into a temporary
directory, and `helm template` was run over it and over the chart in this tree with the
V1 real values file. The two renders differ in ten lines, the two stated strategies,
and in 27 occurrences of the chart version label. The extracted chart and the two
renders are not committed.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| The reference runtime replica count is 2 | Reached as configuration. The two-replica contract declares 2, the committed desired-state values state 2, and the chart renders 2 from them. **Not reached as an observation**: no release with two runtime replicas was installed |
| Both replicas use the same pinned real runtime and model identity | Reached as a render property. A Deployment has one pod template, and the render of the desired-state release carries the image reference of the runtime package record and the artifact digest of the model source record in that template. The two-replica contract carries the pins of the `0.1.0` contract. **Not observed**: no pod started |
| The runtime rollout uses `maxUnavailable` 1 and `maxSurge` 0 | Reached as a rendered policy. The platform defaults own both bounds, the renderer writes them, and the runtime Deployment states them. **No rollout ran** |
| The runtime's readiness stays false until real inference is possible | **Not changed, and not observed here.** The readiness probe and the startup gate still ask the runtime's health endpoint, and liveness is still a TCP connect. A test reads that from the two-replica render. The V1 records are the evidence for one runtime. No record exists for two |
| The V1 model-cache ownership and integrity are preserved | Reached as a render property. The chart renders no PersistentVolumeClaim, each runtime pod mounts the binding's claim read only at the revision directory, and each pod's init container verifies the pinned artifact. **Not reached as an observation**: whether one claim can be mounted by two runtime pods is not established. Another change owns that |
| The Service selects each replica, and readiness is per replica | Reached as a render property. The Service's selector is the Deployment's selector, it names no replica, the Service sets no `publishNotReadyAddresses`, and the probes are in the pod template. **Not observed**: no endpoint was read |
| The generated desired state records the replica intent | Reached. The release's values state `runtime.replicaCount: 2`, and the release document records the digest of the contract that declares it, the workload version `0.2.0`, and the digest of the values file |
| The configuration comes from an owner and not from an override | Reached for a file admitted beside generated values: a hand-written file that sets, replaces, or removes the runtime replica count or a bound is refused. **Not reached for any other route**: a values file passed to Helm by hand is not checked, as the renderer page already states |
| Invalid replica and resource cases are refused | Reached in two places. The renderer refuses a replica range of two numbers, a count outside 1 to 16, a CPU or memory ceiling below the chart's runtime request, a quantity the chart's schema does not take, and an accelerator. The chart's schema refuses a count outside 1 to 16, a bound outside 0 to 16, a fraction, and a percentage, and the template refuses two zeros. **One case is not refused by the chart**: a runtime limit below the runtime request, given to Helm directly. A test records it |
| No autoscaling, batching, queueing, or third surge replica | Held. The chart renders no autoscaler, the default surge bound is 0, and no committed values file states another. No source file under `src/inferops/api` or `src/inferops/adapters` changed |

## Results at the first commit

These checks ran on the working tree that became the first commit, before it was
committed.

| Check | Result |
|---|---|
| `ruff check`, `ruff format --check` | Clean: 659 files formatted, no lint finding |
| `mypy`, and `mypy --platform linux` | No type error in 357 source files, on each platform |
| `helm template`, both committed fixtures | Each render is the committed render, byte for byte |
| `helm template` with `runtime.rollout.maxUnavailable=0`, real and mock fixtures | Refused by the template for each: the two bounds must not both be 0 |
| `helm template` with `runtime.rollout.maxSurge=25%` | Refused by the schema at `/runtime/rollout/maxSurge` |
| `helm lint --strict`, real fixture | Exit 0, with no guard failure in the report |
| `tools.generated_release --check` | Exit 0: the reference release is what its declared sources derive |
| `tools.gitops_desired_state --check` | Exit 0: the release is what its declared sources derive, and the tree holds nothing else |
| `tools.experiment_freeze --check`, `tools.experiment_e01 --check` | Exit 0 for each |
| `tools.evidence_index --check` and `--gate` | Exit 0. The current evidence set `549946af…cbefcc` and pack `06e214dc…3d0720` are the ones the index page already states |
| `tools.proof_dashboard --check` | Exit 0: the dashboard is what the register produces |
| `tests/domain`, `tests/contracts`, the chart suite, the release suite, the two experiment suites, and the inventory suite | 4,265 passed, 8 failed, 32 skipped, and 47 errors. Each failure and error is stated in the next section |
| The default lane | Not run before the first commit. It ran on the committed first commit, and [the result is below](#the-default-lane-on-the-first-commit) |
| `gitleaks` | Not run: it is not installed on this host. The hosted CI job runs it |
| Hosted CI | Not read: no pull request existed when this record was written |

## What failed before the first commit, and why

**Fifty-three results came from an uncommitted tree.** Forty-seven errors are every
test of `tests/domain/test_desired_state_provenance.py` that reads the commit `HEAD`
names, and six failures are the tests of `tests/domain/test_reconciliation_evidence.py`
that do the same. `HEAD` was the base commit, which does not hold the new contract
document, so the tool refused it under `desired-state-absent-at-revision`. Those tests
can pass only on a commit that holds this change.

**One failure was a defect of this change, and it is corrected in the first commit.**
`test_the_recorded_runs_reported_one_commit_and_it_resolves_to_the_release` reads the
commit that the recorded Argo CD runs reported, with the release declaration of the
tree. The declaration now names the two-replica contract, and that earlier commit does
not hold it. The provenance tool reads every commit with the declaration of the
checkout it runs from, as its page already states. The test now reads the earlier
commit with the declaration that held at it, and it also asserts that the tool refuses
that commit under the declaration of this tree. The page states the consequence: the
command refuses a commit from before this change, and has no option for an earlier
declaration. After the correction that test passed when run alone.

**One failure is by construction.** A release cannot name the commit that adds it. At
the first commit the desired-state release is regenerated from the new inputs and still
names the earlier revision, `9bc07a57ca112f5e578914d2265c8e7ab2ae4fb0`. That statement
is false for that one commit, and
`test_the_declared_revision_names_a_commit_that_holds_the_defaults_read_today` says so:
the chart at that revision has no `runtime.rollout`. A later commit of this change
declares the first commit as the revision and regenerates the release.

## The default lane, on the first commit

The lane ran once on the committed first commit,
`40803f2fe9a95753da6480de1e5321efafb3cbf0`, with a clean working tree:
`uv run --locked python -m pytest -q`. No file was edited while it ran.

| Result | Count |
|---|---|
| Passed | 19,201 |
| Failed | 2 |
| Skipped | 37 |
| Deselected | 14 |
| Duration | 53 minutes 27 seconds |

**The fifty-three results that needed a commit passed, and so did the corrected test.**

**One failure is the one stated above as by construction**:
`test_the_declared_revision_names_a_commit_that_holds_the_defaults_read_today`.

**One failure was a second defect of the first commit.** One case of
`test_a_planted_defect_is_refused_under_the_rules_it_breaks` in
`tests/domain/test_desired_state_provenance.py` plants "a contract that changed after
the release was rendered" by replacing the text `version: 0.1.0` in the declared
contract. The declared contract is now the `0.2.0` document, so the edit found nothing
to replace. The tool under test was not at fault. The case now changes the declared
replica range.

## The releases, by commit

| Commit | Release identifier in `gitops/` | Both revisions | Chart | Runtime replicas |
|---|---|---|---|---|
| The base, `ee1edcdc…` | `f23c37d81fbb297643af9e6005cffd805ac05bc98847a6360894fdd238b41d8c` | `9bc07a57ca112f5e578914d2265c8e7ab2ae4fb0` | `0.4.0` | 1 |
| The first commit, `40803f2fe9a95753da6480de1e5321efafb3cbf0` | `541a944e1a480bafbcd4ec0267c139ab6a72cfa98c3a6a3928bcbe1db8aa6228` | `9bc07a57ca112f5e578914d2265c8e7ab2ae4fb0`, which is false for that commit | `0.5.0` | 2 |
| The second commit | `79b1e3890f1f820a64115c4e5a362a6ddf114ba48cbeecf1788106a173e66812` | `40803f2fe9a95753da6480de1e5321efafb3cbf0` | `0.5.0` | 2 |

The values file is the same at the first and the second commit: SHA-256
`314a34829e7b44c62402249f1e93ba4493ec5b019ca7becdd1a5595025d6b6f9`. The second commit
moves the two revisions and the identifier in the release file, and nothing else in
`gitops/`. The reference release in the test fixtures has the values digest
`49538bea8fae419d021f3d3bd8d28184fe328109b76a1eeef7f68cce4b9ac9eb` and keeps its
placeholder revisions.

The second commit edits comments in the chart's values and in the runtime template.
`helm template` of both fixtures gives the committed renders after those edits, and the
chart's `api` and `runtime.rollout` blocks parse to the same values. So the release
still names a commit whose renderer and defaults derive it.

## What merging this change does

- **It must be merged with a merge commit.** The release names one of this change's
  commits as its revision. A squash or a rebase would leave that commit off `main`.
- **On a cluster where the Argo CD Application is applied, the merge changes the live
  release.** `infra/argocd/local-docker-desktop-support-assistant.yaml` follows `main`
  with automated sync and self-heal. Read from the render: the pod template of the API,
  runtime, and collector Deployments each carries the chart version label, which
  changes, and the runtime Deployment declares two replicas and a strategy. The
  workload version is not a label. It changes one ConfigMap value and the
  configuration checksum annotation of the API and runtime pod templates. So a
  controller that applies the render would be given a new pod template for all three
  Deployments and a second runtime replica. That replica's pod mounts the same model
  cache claim and requests 1 CPU and 2Gi. None of this was observed. The one cluster
  that was read holds no Application.
- **A cluster that cannot run two runtime pods is not refused.** This change adds no
  capacity check for this topology. If the second runtime pod cannot be scheduled, or
  cannot mount the claim, Kubernetes documents that the rollout does not complete and
  that the Deployment reports a failed progress condition after its deadline, which
  the render sets to 900 seconds. What an Application then reports was not observed.
- **A rollout of a one-replica release may remove its one runtime pod first.** That
  applies to any release of chart `0.5.0` that keeps the default bounds, the V1 values
  file among them. The section on [the V1 procedures](#the-v1-procedures-and-the-new-default)
  states it.

## What the independent review found

Two automated reviewing sessions read the first commit, read-only. Neither ran a test
suite. One read the code, the chart, and the tests, and ran `helm template`. One
compared every changed page with the repository and searched the whole tree for
statements the change made stale. Neither is a person.

**What the first commit got wrong.**

| # | The first commit said | What is true | Corrected |
|---|---|---|---|
| 1 | This record and the desired-state page said that each pod template carries a "workload version label", and that it changes | No template renders the workload version as a label. It reaches one ConfigMap value, and through it the configuration checksum annotation of the API and runtime pod templates. Three rendered lines differ. The collector's template does not change with it | Both pages. The chart test now asserts exactly those three lines, where it accepted any line holding the version |
| 2 | Nothing said what the new default does to a one-replica release | The default bounds apply at one replica too, where a rollout may remove the one runtime pod first. Three V1 pages described the earlier behaviour as general fact | Decision 10, a section of this record, a dated note on each of the three pages, the chart README, the chart's values, the V1 compatibility page, and the CHANGELOG |
| 3 | This record said that whether the claim's access mode permits two pods "is not established" | The access mode is committed: the prerequisite layer creates the claim as `ReadWriteOnce`. What is not established is that two pods mount it | This record, the chart README, and the desired-state page name the mode and what Kubernetes documents for it |
| 4 | This record, the desired-state page, and the CHANGELOG said "No capacity check was run", with no qualification | This change ran none. An earlier record holds one for this shape on the provider the release names, and it refused the host | Each place names that record and its bound |
| 5 | The contract fixture said "No record of two runtime replicas exists yet" | A record about two runtime replicas exists: the refusal above. No record of two runtime replicas running exists | The fixture's comment |
| 6 | This record said that if the second pod cannot start "the Deployment does not become available, and the Application reports that" | Neither was observed, and the first is not what Kubernetes documents: with two replicas and one allowed unavailable, one Ready pod meets the availability minimum. Kubernetes documents that the rollout does not complete and the progress deadline passes | The merge section |
| 7 | The chart's values, the runtime template, the chart README, the renderer page, this record, and four test docstrings stated what a rollout, a Service, a Deployment, or an admission check does as a fact | Each is what Kubernetes documents, or what the render states. None was observed | Each place |
| 8 | Two pages kept counts the change moved: 46 context values, and 29 values written | 48 and 31 | The boundary page and the renderer page |
| 9 | Five places still named the chart's `api` defaults as the only platform defaults | The runtime rollout bounds are platform defaults too | The contributing guide, the desired-state page, the release contract page, and the V1 compatibility page |
| 10 | This record said every other file the change edits was already listed by the freeze listing | Every other pinned file | The freeze section |
| 11 | This record said the Service "does not publish unready addresses" | The Service sets no `publishNotReadyAddresses`. What it then does is Kubernetes behaviour | The row |
| 12 | A test asserted that an out-of-range replica count is refused with an "in" check, and its zero case built a two-number range | The zero case would pass if the count check were removed | The test states the exact findings for each case |
| 13 | A test's comment said nothing "pins a replica to a node", and checked four members | It did not check a node selector or a topology spread | It checks six members and says what their absence means |
| 14 | The planted-defect case named in the lane section edited text the declared contract no longer holds | See above | The case |

**What was missing, and was added.**

- Negative cases: an inverted replica range, a CPU form the chart does not take, a
  replica count that is not a number, each bound below and above its range, and a
  member the rollout block does not define. Each chart case now names the schema
  location it must be refused at.
- Five cases for the values loader: a values file with no `runtime.rollout`, with one
  that is not a mapping, with one bound missing, with two zeros, and with a percentage.
  No test had read those paths.
- Limitations in this record: the claim's access mode and placement, the acquisition
  hook as one more consumer of the claim, thread count and start time with two
  runtimes, and the single-node consequence.

**Measured, and left as it is.**

- **The schema is the only refusal of a malformed bound.** With
  `--skip-schema-validation`, a null `runtime.rollout` reaches the template guard as two
  zeros and is refused with the two-zeros message, which does not name the real fault.
  The API tier's guard already behaved so. The reviewer measured it with
  `helm template`.
- **A wrong type in the chart's values is refused under another exception type than a
  missing member.** Both are reported as a refusal of the sources. The API tier's
  bounds already behaved so.
- **Two rows of the V1 compatibility record say `chart-default` for a value V1 never
  had**, as the two API rows already do. The row format has no member that could say
  so per row.

**Noted, and not changed.**

- **The pull request title and the branch name carry the words "reliability" and
  "redundancy".** They were given to this change. They name the subject of the
  topology. Nothing in this change measures reliability, and no page claims it.
- **Four statements of this record cannot be checked from the repository**: the one
  cluster read, the file counts of the lint and type checks, the test counts, and the
  freeze counts at the base. The record says which of them has no committed transcript.

## Results at the second commit

These checks ran on the working tree that became the second commit, before it was
committed. No file was edited while the suites ran.

| Check | Result |
|---|---|
| `ruff check`, `ruff format --check` | Clean |
| `mypy` | No type error in 357 source files |
| `helm template`, both committed fixtures | Each render is the committed render, byte for byte, after the comment edits |
| `tools.generated_release --check`, `tools.gitops_desired_state --check` | Exit 0 for each |
| `tests/domain`, `tests/contracts`, `tests/architecture`, `tests/testing`, `tests/security`, and `tests/serving` | 16,149 passed, 2 failed, 37 skipped, in 44 minutes 10 seconds |
| The default lane on the second commit | Run on the committed tree. A later commit of this change records the result in this file |

**The two failures came from an uncommitted tree.** Both are cases of
`test_a_planted_defect_is_refused_under_the_rules_it_breaks`: "an edited release
identifier" and "a release that records another renderer revision". Each reads the
identifier or the revision from the release file in the working tree, and plants its
edit in a copy of the commit that `HEAD` names. Before the second commit those two
held different releases, so the edit found nothing to replace. They can pass only on a
commit that holds the regenerated release.

## Privacy and publicability

The diff was read for private material before each commit. It holds no credential, no
secret value, no personal path, no cloud account identifier, no model artifact, and no
generated machine state. The API image digest in both committed renders is the
documented placeholder, as before.

## What this does not establish

- **That two runtime replicas run.** The count is in a contract, in a values file, and
  in a render. No release with that count was installed, and no model was loaded.
- **That one model cache claim serves two runtime pods.** The pod template mounts the
  claim read only. The prerequisite layer creates the claim as `ReadWriteOnce`
  (`infra/terraform/modules/platform-prerequisites/main.tf`). Kubernetes documents that
  such a claim can be mounted by several pods on one node and not by pods on two nodes.
  The render states no node selector, affinity, or topology spread for the runtime, so
  it states nothing about placement. The acquisition hook mounts the same claim on
  every install and upgrade, while runtime pods may hold it. None of this was observed
  with two runtime pods.
- **That an environment has room for the topology.** The chart's runtime requests sum
  to 2 CPU and 4Gi for two replicas, and the contract's ceilings to 12 CPU and 6Gi.
  This change ran no capacity check. One earlier record bears on it: the V1
  multi-replica certification (`docs/serving/kubernetes-multi-replica-certification.md`)
  ran a capacity gate for two API replicas and two runtime replicas on
  `docker-desktop`, and the gate refused that host, 172,765,184 bytes of uncommitted
  memory short. That page states the sum for that shape: 2,310 millicores and
  4,496 MiB of requests. It is a record of one host on one day.
- **Anything about CPU contention or start time with two runtimes.** Each runtime pod
  runs six inference threads by default, so two pods run twelve, against a request of
  1 CPU each. The startup budget, the rollout deadline, and every V1 performance record
  were set or measured with one runtime. Two concurrent model loads were not timed.
- **Anything about a rollout.** No rollout ran. The two bounds are a policy the
  Deployment controller would be given for a template change. Kubernetes documents that
  under them a rollout may run one runtime pod fewer until each replacement is Ready.
  At one replica that is none.
- **That the V1 upgrade and recovery procedures behave on chart `0.5.0` as their
  records describe.** Those records are of chart `0.3.0`. Neither procedure was run
  again.
- **Anything about a pod deletion, a node loss, or an eviction.** A rollout policy does
  not bound any of them, and the chart renders no disruption budget. Both runtime pods
  may be placed on one node, and Kubernetes documents that pods sharing a
  `ReadWriteOnce` claim are on one node. So this topology states nothing about the
  loss of that node.
- **That a caller is served when one runtime pod is unavailable.** No request was
  sent. Nothing here shows that a Service stops routing to a runtime pod that is not
  Ready, how quickly it does, or what the API returns for a request that was in flight.
- **That chart `0.5.0` installs.** It was rendered and linted. It was installed nowhere.
- **That the first experiment's results hold for this tree.** Those runs read the files
  their freeze revisions pinned. Fifteen of the files revisions 1 and 2 pin differ now,
  and twenty-five of the files revision 3 pins.
