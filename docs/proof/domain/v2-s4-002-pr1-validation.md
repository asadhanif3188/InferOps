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
| 2 | A second contract document declares two replicas, at workload version `0.2.0`. The `0.1.0` document is not edited | The `0.1.0` document is the V1 workload: the V1 compatibility comparison and the fixture release are derived from it, and V1 ran one runtime. A changed replica range is a new version of the contract | Two documents carry the same pins. A test holds them equal outside three members. The workload version label changes on every object of the desired-state release |
| 3 | The platform defaults own the two runtime rollout bounds | A rollout policy is the same for every workload and environment, and neither the contract nor the binding has a field for it | A workload owner cannot choose a surge pod for the runtime. The defaults are still read from the chart's values file. No defaults file exists |
| 4 | The two bounds joined `v1alpha1` in place. No `v1alpha2` | No defaults file is committed at any revision, so no stored document changed its meaning | A caller that built a five-setting set no longer constructs one. Every caller in this repository was changed |
| 5 | `maxUnavailable` 1 and `maxSurge` 0 | A surge pod for the runtime is one more loaded model. The requirement names these bounds | A rollout runs one runtime pod fewer than the replica count until each replacement is Ready. At one replica that is none. The chart does not refuse that combination |
| 6 | The chart version moved to `0.5.0` | The render changed, and the bounds in effect changed at the replica counts the repository renders | The V1 compatibility record is amended again, and the release suite names the moved pin again |
| 7 | The chart's schema still permits a runtime surge bound above 0 | The bound is a platform default, and the schema definition is shared with the API tier. A chart-level refusal would be a second owner of the policy | A values file given to Helm directly can state a surge pod. A file admitted beside generated values cannot |
| 8 | No PodDisruptionBudget, no autoscaler, no capacity check, and no model-cache check | Each is another change's subject | An eviction is not bounded, and nothing refuses an environment that cannot run two runtime pods |
| 9 | No new freeze revision for the first experiment | The runs of that experiment are finished, and the earlier changes took the same course | See the next section |
| 10 | The provenance command gained no option for an earlier declaration | The command reads a commit with the declaration of its checkout, as its page states. A commit that a controller reports after this change holds the new contract | The command refuses a commit from before this change. The library function still reads one, when it is given the declaration that held |

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
Revision 3 also gains `tools/gitops_desired_state/__main__.py`. Every other file this
change edits was already listed at the base. The new contract document is not listed:
no freeze record names it, and no record's scope covers it.

**No freeze record, run, or review record was edited, and no new freeze revision was
written.** A new run of any part of that experiment was already refused at the base,
and it is still refused, until a later freeze revision classifies each moved file. The
desired-state release now names another contract than the one revision 3 pins. So a
later real-deployment run needs a freeze revision that names the new contract.

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
| The Service selects each replica, and readiness is per replica | Reached as a render property. The Service's selector is the Deployment's selector, it names no replica, the Service does not publish unready addresses, and the probes are in the pod template. **Not observed**: no endpoint was read |
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
| The default lane | **Not run at the first commit.** |
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

## What merging this change does

- **It must be merged with a merge commit.** The release names one of this change's
  commits as its revision. A squash or a rebase would leave that commit off `main`.
- **On a cluster where the Argo CD Application is applied, the merge changes the live
  release.** `infra/argocd/local-docker-desktop-support-assistant.yaml` follows `main`
  with automated sync and self-heal. Read from the render: the pod template of the API,
  runtime, and collector Deployments each carries the chart version label and the
  workload version label, which change, and the runtime Deployment declares two
  replicas and a strategy. So that controller would replace the pods of all three
  Deployments and start a second runtime pod. That pod mounts the same model cache
  claim and requests 1 CPU and 2Gi. None of this was observed. The one cluster that
  was read holds no Application.
- **A cluster that cannot run two runtime pods is not refused.** No capacity check
  exists for this topology. If the second pod cannot be scheduled, or cannot mount the
  claim, the Deployment does not become available, and the Application reports that.

## Privacy and publicability

The diff was read for private material before each commit. It holds no credential, no
secret value, no personal path, no cloud account identifier, no model artifact, and no
generated machine state. The API image digest in both committed renders is the
documented placeholder, as before.

## What this does not establish

- **That two runtime replicas run.** The count is in a contract, in a values file, and
  in a render. No release with that count was installed, and no model was loaded.
- **That one model cache claim serves two runtime pods.** Each pod mounts the claim
  read only. Whether the claim's access mode and the cluster's storage permit two pods
  is not established.
- **That an environment has room for the topology.** The chart's runtime requests sum
  to 2 CPU and 4Gi for two replicas, and the contract's ceilings to 12 CPU and 6Gi. No
  capacity check was run.
- **Anything about a rollout.** No rollout ran. The two bounds are a policy the
  Deployment controller would apply to a template change. Under them a rollout runs one
  runtime pod fewer until each replacement is Ready.
- **Anything about a pod deletion, a node loss, or an eviction.** A rollout policy does
  not bound any of them, and the chart renders no disruption budget.
- **That a caller is served when one runtime pod is unavailable.** No request was
  sent. Nothing here shows that a Service stops routing to a runtime pod that is not
  Ready, how quickly it does, or what the API returns for a request that was in flight.
- **That chart `0.5.0` installs.** It was rendered and linted. It was installed nowhere.
- **That the first experiment's results hold for this tree.** Those runs read the files
  their freeze revisions pinned. Fifteen of the files revisions 1 and 2 pin differ now,
  and twenty-five of the files revision 3 pins.
