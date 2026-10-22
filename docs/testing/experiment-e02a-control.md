# The E02A control and its driver

V2-E02A deletes the one runtime pod of the single-runtime baseline release, two API
replicas and one runtime replica, while the RP-1 runner sends requests. Its
[freeze record](../proof/experiments/v2-e02a/freeze-r3.v1alpha1.json) states the whole
procedure. This page describes the code that runs that procedure:

- [`docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt`](../proof/experiments/v2-e02a/procedure/e02a-driver.txt),
  the driver. It is the one file through which the control issues a cluster command.
  The scripts that it calls, such as the capacity gate, the runner script, and the two
  collectors, run their own commands.
- [`tools/experiment_e02a`](../../tools/experiment_e02a/control.py), the control. It
  runs the steps in the order of the record and decides each one.

Revision 3 of the record pins both. **Neither has run on a cluster.** The tests and the
dry runs executed the control against scenario files, and the tests executed the fault
phase of the driver against a stub `kubectl`; no cluster command and no fault was
executed. No run of V2-E02A exists, and the desired state on `main` is still the target
topology of V2-E02B, two API replicas and two runtime replicas. A run refuses at P2 until
a later change switches the desired state and registers revision 4 of the record.

## How the parts fit

| Part | What it does | What it does not do |
|---|---|---|
| [`core.py`](../../tools/experiment_e02a/core.py) | Reads the latest registered record, holds it to its registry pin and to the phrases of the figures that the control restates, and decides each step from what the control read | Read or change a cluster, run a command, or judge a criterion |
| [`control.py`](../../tools/experiment_e02a/control.py) | Runs P1 to P8, the collection, the checks of the stable pre-fault window, F1 to F4, the observation, and C1 to C4, and writes `control.json` | Delete a pod except through a fault object, or state a result of a run that reached the fault |
| [`ports.py`](../../tools/experiment_e02a/ports.py) | The live port runs each cluster read and act as one verb of the driver and keeps `commands.txt` and `transcript.txt`. The scenario port answers each cluster read from a scenario file and executes no cluster command | Name the delivery controller or a script |
| [`__main__.py`](../../tools/experiment_e02a/__main__.py) | The command: `plan`, `dry-run`, and `run` | Start a run that the driver did not start |
| The driver | Starts the control, holds each cluster command of the control as one verb, and holds the fault as its own phase | Decide anything |

The package does not name the delivery controller, its namespace, or the scripts that
install it. The driver names them, and the control reads through its verbs. Two
repository tests hold this: one refuses an Argo CD spelling in any file under `tools/`,
and one refuses the name of a repository check, such as the desired-state provenance
tool, on a delivery path. The package names the provider `docker-desktop` as the context
of the fault command that it records, and in no command that it runs.

## The record is the source

`python -m tools.experiment_e02a plan` prints what a run takes from the record. The
control reads the latest V2-E02A record that the freeze registry of the checkout
registers. It refuses the record when:

- its bytes differ from the registry pin;
- its revision is before revision 3, which is the first that pins a driver;
- its text does not state a figure of the control in the phrase that
  [`BOUND_PHRASES`](../../tools/experiment_e02a/core.py) names, or it states other
  abort codes.

The structured members give the replica counts, the namespace, the desired-state path and
the digests of its two files, the release identifier, the model SHA-256, the stable
environment identity, the caller duration and request ceiling, the exclusion reasons, and
the rule of the analysis declaration. **Some values are constants of the control, and the
record states none of them:** the Helm release `inferops`, the names of the two Services,
the labels of the tiers, the line that the model verification prints, and the context
`docker-desktop` of the fault command.

The figures that the record states in prose, and that the control restates, are below. A
later revision that moves one of them refuses this control until the control moves too.

| Figure | Value | Where the record states it |
|---|---:|---|
| Successful requests in the stable window | 10 in the last 60 s | `definition.stablePreFaultWindow` |
| First check, interval, last check | 150 s, 30 s, 600 s after the runner pod started | `definition.stablePreFaultWindow` |
| Window | fault-injection-started less 60,000 ms to fault-injection-finished plus 720,000 ms | `definition.window` |
| Observation limit | 600 s after fault-injection-finished | `definition.observation` |
| Timeline collection | 900 samples, 2 s | `definition.collection.timeline` |
| Telemetry collection | 120 samples, 15 s | `definition.collection.telemetry` |
| Pause before the runner | 30 s | `definition.collection.order` |
| Topology wait | 1,800 s | P6 of `definition.preparation` |
| Runs under one revision | 6 | `definition.repetitionRule` |
| A node not Ready, or an API that does not answer | more than 60 s | `abort-cluster-incident` of `fields.abortConditions` |

## A run, step by step

`bash docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt run e02a-N` starts one
run. N is the next identifier: none is reused or skipped, and at most six runs start
under one revision. A run spends its identifier once its work directory under
`.artifacts/v2-e02a/runs/` exists, whatever its result. The driver hands the control the
paths of the driver and of its bash in the Windows form, because the control is a Windows
program under Git Bash.

| Step | What the control reads or does | A refusal |
|---|---|---|
| P1 | The executing revision, a clean working tree, the four checks, and `--changes` of the record | Before any cluster read |
| P2 | The remote main, the delivery paths at it, and the two desired-state files at it, which must have the baseline digests of the record | Before any cluster read |
| P3 | The target check of `scripts/environment/lib.sh`, and a cluster with no release namespace and no controller namespace | Before any act |
| P4 | The capacity gate before anything is installed, and its stable environment identity | Before any act |
| P5 | The images, the prerequisite layer, the model cache from the seed image, the controller, a second capacity reading, and the Application | Then C4 |
| P6 | Two API and one runtime readyReplicas and Ready endpoints, the Application `Synced` and `Healthy` at the desired revision, within 1,800 s, then the Application verification | Then C4 |
| P7 | The provenance of the release key, the verified model file of each runtime pod, and the namespaces and the definitions that the abort conditions compare with | Then C4 |
| P8 | The start reading of the clocks | Then C4 |
| Collection | The event log, the timeline collector, the telemetry collector when the first one samples, 30 s, the runner | Then C1, C2, and C4 |
| Stable window | At each offset, 150 s after the runner pod started and every 30 s to 600 s, or later: the abort conditions, then the caller record so far and the Deployments | `stable-window-not-reached`, then the runner is removed |
| F1 | The first Ready runtime pod by name, with every pod of the release | |
| F2 to F4 | `fault-injection-started`, the fault, `fault-injection-finished` | A fault command that fails is a finding, and the run goes on |
| Declaration | Written from the rule of the record before any evidence is read | |
| Observation | No mutating command. The abort conditions every 30 s until the window ends, then the end of the Job | An abort |
| P8 | The end reading, and the clock bound | `clock-reading-missing` is recorded |
| C1 to C4 | Collect the caller record and remove the runner; wait for the collectors, then close the log; verify the Application, `spec.replicas` and `readyReplicas` of both Deployments, the sync at the desired revision, and a success in the last 60 s of the window, each recorded as drift; remove the release, the controller, and the prerequisite layer, and compare the namespaces and the definitions | |

Each refusal states `precondition-not-held` unless the table names another reason. An
abort records the event `run-aborted` with its code, collects the caller record, waits for
the collectors, closes the log, and runs C4. The control writes each decision into
`control.json`, with the instant and the findings of each step. A step whose findings are
not empty states `held: false`.

**The control states no result of a run that reached the fault.** It states
`OBSERVED`. The review of the run judges each criterion and writes the result page.

**An error that the procedure does not decide stops the control.** An interrupt, or a file
that cannot be written, ends the procedure with the state `STOPPED`, the reason
`control-error` and the type of the error. The control runs the cleanup that it can, as
after an abort when the fault was reached and as after a refusal otherwise, writes
`control.json`, and exits 4. It raises an interrupt again after that.

## The fault

The fault is one command:
`kubectl --context docker-desktop delete pod <name> --namespace inferops-release --wait=false`.
The record states it without the context, which each kubectl command of the driver names,
and `control.json` states it with the context.

- The control deletes a pod only through a fault object, and the dry-run command never
  constructs one.
- A fault object is constructed for a run identifier `e02a-N` alone.
- The phase `fault` of the driver refuses unless the phase `run` started it, refuses
  another identifier or a name that is not a pod name, and creates a marker in the work
  directory of the run before the command. It refuses when the marker exists, so one run
  deletes at most one pod.
- The driver holds no other `delete` command.
- A fault command that fails is recorded with its exit status, and the run is observed
  to the end of its window, as the record states. The review judges
  `fault-not-produced`.

## A dry run

```sh
bash docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt dry-run dry-run-1 SCENARIO
uv run --locked python -m tools.experiment_e02a dry-run --run-id dry-run-1 --scenario SCENARIO
```

A dry run takes an identifier `dry-run-N` and never `e02a-N`, and it writes under
`.artifacts/v2-e02a/dry-runs/`. Its port answers each cluster read from the scenario on a
virtual clock, records each act as not executed, and executes no cluster command. It has
no fault: it records the command that a run would issue, and no fault event. Its event log
holds no fault event, and its declaration states the instants at which the events would
have been recorded.

A scenario that states no repository member reads that member from the checkout: it runs
`git` and the four checks of P1, which read files and contact no network, and it reads the
local tracking branch of the remote main and the files of the desired-state path at it. So
a dry run of this checkout that states no repository member refuses at P2: the desired
state of `main` is still the 2+2 target. The schema of a scenario is
`inferops.io/experiment-e02a-dry-run-scenario/v1alpha1`. Each read answers the latest
entry whose act has happened, at least `from` seconds before, and the scenario states the
requests of the runner as an interval of at least 1 ms and failing intervals.

## What it does not do

- **It has not run on a cluster.** No verb has been executed against a cluster in this
  change.
- **It does not judge a criterion or state a result** of a run that reached the fault.
- **It reads six of the nine abort conditions at each check**: a changed checkout, a
  node not Ready or an API that does not answer for more than 60 s, a namespace or a
  definition that appears or disappears, a lost caller, a resolved revision other than
  the desired revision, and a deleted model cache claim. The target check of P3 decides
  `abort-wrong-target` before the preparation, and the fault is issued at most once. It
  does not read a change that a person makes, the model file of a replacement pod, or
  `abort-cleanup-unsafe`. The review of the run compares them. A commit pushed to `main`
  during a run moves the revision that the Application resolves, so the control aborts the
  run with `abort-revision-unknown`, as the record states.
- **It bounds its waits and its commands with figures that the record does not state:**
  120 s for a collector to start sampling, 300 s after the caller duration for the Job to
  end, 3,600 s for the collectors, 3,600 s for each verb of the driver, 900 s for each
  check of P1, 120 s for each read of Git, and 300 s for the fault command. A verb or a
  check that reaches its bound gives no answer, and the control refuses the step that reads
  it. It polls the topology every 10 s and its waits every 5 s. None of these changes a
  criterion, a window, or a figure of a run.
- **It takes each check of the stable window at its offset or later.** It reads the abort
  conditions first, and each check states its instant.
- **It reads the caller record of the stable window from the log of the runner pod**
  while the runner runs, and it skips a line that is not a complete request line of the
  run. It schedules the checks from the start instant of the runner pod, which
  Kubernetes states to the second.
- **It reads capacity twice**, before the preparation installs anything and immediately
  before the Application is applied. Both readings must be accepted.
- **It does not write the run directory of the proof tree**, its manifest, the run
  analysis, or the result page. They are assembled from the work directory after the
  review of the run.

## Validation

The suite [`tests/testing/test_experiment_e02a_control.py`](../../tests/testing/test_experiment_e02a_control.py)
holds the binding to revision 3, each decision, the order of the steps on scenarios, the
dry run, the STOPPED state, the live port and the fault phase of the driver against a
stub driver and a stub `kubectl`, the hand-off of the paths from the driver against a stub
`uv`, and the analysis and replay of a synthetic 2+1 run. The validation record of the
change is
[`docs/proof/environment/v2-s7-001-pr1-validation.md`](../proof/environment/v2-s7-001-pr1-validation.md).
