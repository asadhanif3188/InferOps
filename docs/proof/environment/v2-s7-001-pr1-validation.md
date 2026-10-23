# Validation: the E02A driver and revision 3 of the V2-E02A record (V2-S7-001-PR1)

Status: **C0 for the records, C1 for the control.** This change adds the driver of
V2-E02A and the control that it starts, and registers revision 3 of the V2-E02A freeze
record, which pins both. It also registers revision 3 of V2-E03 and revision 2 of V2-E06,
which bind revision 3. The tests executed the control against scenario files on a virtual
clock, the fault phase of the driver against a stub `kubectl`, its phase `run` against a
stub `uv`, and the live port against a stub driver: that is substituted execution, C1. One
dry run executed the control against this checkout with a scenario file. The records are
static, C0. Nothing ran on a cluster: no cluster was read or changed, no fault was
injected, no caller request was sent, and no run identifier was taken. A freeze record is
not evidence, and no claim is registered.

## What the change adds

| Item | Path |
|---|---|
| The driver: the one file through which the control issues a cluster command | [`docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt`](../experiments/v2-e02a/procedure/e02a-driver.txt) |
| The control: five modules | [`tools/experiment_e02a`](../../../tools/experiment_e02a/control.py) |
| V2-E02A freeze, revision 3, 232 pins | [`docs/proof/experiments/v2-e02a/freeze-r3.v1alpha1.json`](../experiments/v2-e02a/freeze-r3.v1alpha1.json) |
| V2-E03 freeze, revision 3, 124 pins | [`docs/proof/experiments/v2-e03/freeze-r3.v1alpha1.json`](../experiments/v2-e03/freeze-r3.v1alpha1.json) |
| V2-E06 freeze, revision 2, 144 pins | [`docs/proof/experiments/v2-e06/freeze-r2.v1alpha1.json`](../experiments/v2-e06/freeze-r2.v1alpha1.json) |
| Three registry rows | [`docs/proof/experiments/registry.v1alpha1.json`](../experiments/registry.v1alpha1.json) |
| The suite, 107 tests, one of them on Windows alone | [`tests/testing/test_experiment_e02a_control.py`](../../../tests/testing/test_experiment_e02a_control.py) |
| The description | [The E02A control and its driver](../../testing/experiment-e02a-control.md), and [the section of the experiments page](../experiments/README.md#the-e02a-driver-and-revision-3) |

The registered content digests are
`2e9ed0950a22f4793b12af051b5602d75b335c8ad017d121c86fb1db017bbbaf` (V2-E02A revision 3),
`036e9077d4f479e2e01873fbf02bc06c7345c8760e6ea2b13b3afa7507ea6f3f` (V2-E03 revision 3), and
`d8e562da2b131697bee29f9b1d5848b4353f72513c3e3e42326d20dd0f5086bf` (V2-E06 revision 2).
Each is written out in `tests/testing/test_experiment_freeze.py`, so that a change to it is
visible in review. The second commit of this change regenerated the three records after
it changed the control and the texts of revision 3; the digests of the first commit are
superseded and no file states them.

## The prerequisites, checked before the branch was made

| Prerequisite | Observed at `39432e4` |
|---|---|
| Sprint 6 is approved, and the order of the Sprint 7 changes is decided | The repository owner approved both on 2026-10-21. The record of that approval is not in this repository |
| The tag `learning-baseline-v1` is unchanged | The tag object is `bffcfb4` and it peels to `39432e4`, locally and on the remote |
| Revision 2 is the latest registered V2-E02A record | The registry held revisions 1 and 2 of V2-E02A and no later one |
| The desired state on `main` is the target of V2-E02B, two API and two runtime replicas | `rendered-workload-release.yaml` has `810b4b27…` and `values.generated.yaml` has `6a1304a8…`, the digests of the topology of revision 2 of V2-E02B |
| The five checks of the freeze records pass | `experiment_freeze`, `experiment_preregistration`, `analysis_preregistration`, `environment_qualification`, and `experiment_bounds`, each `--check`, passed |

## The design

- **The driver holds every cluster command of the control, and the control decides.**
  The control, `tools/experiment_e02a`, runs the steps in the order of the record and
  decides each one with a pure function of what it read. It reads and acts only through a
  port. The live port runs each cluster read and act as one verb of the driver. The scripts
  that a verb calls run their own commands. The package names no delivery controller and
  no script, so it passes the two repository tests that refuse an Argo CD spelling under
  `tools/` and the name of a repository check on a delivery path.
- **A dry run cannot inject a fault.** The control deletes a pod only through a fault
  object. The dry-run command constructs none. A fault object is constructed for a run
  identifier `e02a-N` alone, the fault phase of the driver refuses outside a run, and it
  creates a marker before its one command, so one run deletes at most one pod.
- **The record is the source.** The control reads the latest registered V2-E02A record,
  holds it to its registry pin, refuses a revision before 3, and takes the topology, the
  release, the model, the environment identity, the caller run, the exclusion reasons,
  and the rule of the declaration from it. The figures that the record states in prose are
  constants of the control, each held to its phrase in the record, so a later revision
  that changes one refuses the control. The Helm release, the Service names, the labels of
  the tiers, the line of the model verification, and the context of the fault command are
  constants that the record does not state.
- **The run directory is assembled after the review.** The control writes a work
  directory under `.artifacts/v2-e02a/`. It does not write a run directory of the proof
  tree, a manifest, a run analysis, or a result page, and it states no result of a run
  that reached the fault.

## Revision 3 of the V2-E02A record

### Every member that differs from revision 2

| Member | What differs |
|---|---|
| `metadata` | Revision 3, registered on 2026-10-22 by `V2-S7-001-PR1`, superseding revision 2 by path and digest. Rule set 2 |
| `definition.gitTransitions` | G1 states that the switch change registers revision 4. G2, G3, and G4 are those of revision 2 |
| `definition.limitations` | Three items replaced and eight added, below: 19 items |
| `definition.history` | One entry states when and why revision 3 was written |
| `fields.experimentIdVersion` | The freeze revision is 3 |
| `fields.gitRevision` | Prepared from `39432e4` |
| `materialScope` | The entry module `tools.experiment_e02a.__main__`, and a description that names the driver |
| `pinnedInputs` | The driver and the five modules of the control are added, and `core.py` of the preregistration check has its present digest |
| `inputChanges` | Each moved pin, classified |

A test holds that no other member differs. Every member of the definition that V2-E02A
shares with V2-E02B is that of revision 2, `executables` included, and
`python -m tools.experiment_preregistration --check` compares them. So the driver is
pinned through the scope, which already named `v2-e02a/procedure/*`, and not listed in
`definition.executables`, and one limitation states this.

The limitations that revision 2 stated, "No driver for this experiment exists", "No code
holds a declaration of the analysis", and "No tool checks that a run executes the latest
registered revision", are replaced by what is now true. The eight added items state the
figures that the control restates and the constants that the record does not state, the
two capacity readings of P4, the six abort conditions that the control reads, the bounds
of its waits and its commands, the caller record that it reads from the log of the runner
pod, the work directory, the context of the fault command, and that the shared
executables name neither the driver nor the control.

### The rule G1, stated prospectively

Rule G1 of revisions 1 and 2 states: "That change registers revision 2 of this record". In
revision 1 that named the next revision. Revision 2 was registered by a change that
executed no switch, and copied the sentence, so in revision 2 it names a revision that
exists. Revision 3 states: "That change registers revision 4 of this record, which
classifies each moved pin, and revision 4 merges before the first run." Revisions 1 and 2
are not edited, and their pins and rows are unchanged.

G4 is word for word that of revision 2. Its first sentence, "No switch is executed by the
change that registers this record", holds for revision 3: this change switches nothing. Its
second sentence, "Each switch is a commit to main that needs the explicit authorization of
the repository owner", stays the requirement of each switch.

### The pins and their classification

| Path | Material | Reason, in short |
|---|---|---|
| `docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt` | yes | The driver: it starts the control and holds each cluster command of the control as one verb, the fault included |
| `tools/experiment_e02a/__init__.py` | yes | The package entry, which exports the decisions of `core.py` |
| `tools/experiment_e02a/__main__.py` | yes | The command that the driver starts: it loads the plan and starts the control |
| `tools/experiment_e02a/control.py` | yes | It runs P1 to C4 in the order of the record |
| `tools/experiment_e02a/core.py` | yes | It reads the record and decides each step, and it holds the figures to their phrases |
| `tools/experiment_e02a/ports.py` | yes | It runs each read and act as one verb of the driver, or answers it from a scenario |
| `tools/experiment_preregistration/core.py` | no | Each rule and gate that `V2-S6-005-PR1` and `V2-S6-008-PR1` added reads a V2-E04 record alone. A V2-E02A record of rule set 2 is read under the same rules, and the comparison with V2-E02B is unchanged. The diff from the pinned file inserts 1,499 lines and removes 11: the import from `tools.reliability_analysis.core`, which also takes two constants of that pinned module; the statement of `prereg-rule-set-unknown`; the selection of the rule set of a record and its docstring; and the refusal detail of an unknown rule set. Each of the last three adds a clause for V2-E04 alone |

`python -m tools.experiment_freeze --changes` lists no file for revision 3. For revision 2
it lists the driver as added and `core.py` as changed. For revision 1 it also lists the two
other files of the check that revision 2 classified. Neither pins the control, and a run
refuses under either because revision 3 is the latest.

## Revision 3 of V2-E03 and revision 2 of V2-E06

The check of the analysis records, `tools/analysis_preregistration`, holds the latest
revision of each analysis record to the latest revision of each source: its rule
`sources-stale`. Revision 2 of V2-E03 and revision 1 of V2-E06 bind revision 2 of V2-E02A,
so the check refuses once revision 3 is registered. The repository owner decided on
2026-10-22 that this change registers the rebinding records, and that each changes the
V2-E02A binding alone.

- **V2-E03 revision 3** binds revision 3 of V2-E02A by path, revision, content digest, and
  rule set, and lists each member that differs from revision 2 in
  `definition.changesFromSupersededRevision`, as its rule `e03-revision-changes` requires.
  Its moved pin is revision 3 of V2-E02A, material.
- **V2-E06 revision 2** binds revision 3 of V2-E02A. It also classifies the two pins of
  revision 1 that `V2-S6-008-PR1` moved, as not material: `core.py` of
  `tools/analysis_preregistration`, whose added rules read a V2-E03 record after revision 1
  alone, and `core.py` of `tools/experiment_preregistration`, whose two functions that this
  record imports are unchanged.

A test holds that the definition, the fields, and the material scope of each keep the
values of the revision that it supersedes, except the V2-E02A binding, the history, the
list of changes of V2-E03, the freeze revision, and the revision of `main`. Their
`metadata`, `pinnedInputs`, and `inputChanges` differ as for any revision. The runs of
V2-E02A will execute under a later revision of V2-E02A, so a later revision of each
analysis record binds that revision before any figure is computed from them, as
`definition.population.laterSourceRevision` of V2-E03 already states.

## What each latest freeze owes

This table supersedes, for the three records that this change registers, the readiness
review of [`V2-S6-008-PR1`](v2-s6-008-pr1-validation.md#the-consolidated-pre-run-readiness-review).
`python -m tools.experiment_freeze --changes` was read for each latest record at the second
commit of this change.

| Latest record | `--changes` | What it owes before its first run or figure |
|---|---|---|
| V2-E02A, revision 3 | UNCHANGED | The switch of the desired state to the baseline, and the later revision of this record that the switch change registers. A run refuses at P2 until then |
| V2-E02B, revision 2 | `core.py` of the preregistration check changed | Its driver, and a revision that classifies the moved pin |
| V2-E02C, revision 2 | `core.py` of the preregistration check changed | Its driver, and a revision that classifies the moved pin |
| V2-E04, revision 3 | UNCHANGED | Its driver, the bad-release fixture, and the machine-readable known-good identity record, each under a later revision, and the rest that the readiness review of `V2-S6-008-PR1` states for it |
| V2-E05, revision 2 | `core.py` of the preregistration check changed | Its driver and its drift injector, and a revision that classifies the moved pin |
| V2-E03, revision 3 | UNCHANGED | A revision that binds the source revisions under which the counted runs execute, and its analysis code |
| V2-E06, revision 2 | UNCHANGED | A revision that binds the source revisions under which the counted runs execute, and its analysis code |

## The control

[The control page](../../testing/experiment-e02a-control.md) states each step and its
refusal. Four facts are stated here because they are decisions of this change.

- **P4 reads capacity twice**: before the preparation installs anything, and immediately
  before the Application is applied, as the qualification `q1-2` did. Both must be
  accepted, and each must have the stable environment identity of the record. The record
  states "before the Application is applied", which both readings satisfy.
- **The control reads six of the nine abort conditions** at each check: a changed
  checkout, a node not Ready or an API that does not answer for more than 60 s, a namespace
  or a definition that appears or disappears, a lost caller, a resolved revision other than
  the desired one, and a deleted model cache claim. The target check of P3 decides the
  wrong-target condition before the preparation, and the fault is issued once. It does not
  read a change that a person makes, the model file of a replacement pod, or an unsafe
  cleanup.
- **The waits and the commands have bounds that the record does not state:** 120 s for a
  collector to start sampling, 300 s after the caller duration for the Job to end,
  3,600 s for the collectors, 3,600 s for each verb, 900 s for each check of P1, 120 s for
  each read of Git, and 300 s for the fault command. They bound waits and change no figure
  of a run.
- **An error that the procedure does not decide stops the control** with the state
  `STOPPED`, after the cleanup that it can run, and the command exits 4.

## The tests

`tests/testing/test_experiment_e02a_control.py` holds 107 tests in the documentation
layer. One of them runs on Windows alone: it holds the drive-letter forms of the checkout
path.

- **The binding to revision 3**: the plan, each phrase, the refusals of a record that
  differs from its pin, of a latest revision 2, and of three changed figures, the pins of
  the driver and the control, the moved pins, the members that differ, G1 and G4, the
  shared members, and the 2+2 desired state of the tree, which P2 refuses.
- **Each decision**: the identifier, P1 to P8, the stable pre-fault window and the caller
  log, the target, the declaration, each abort condition that the control reads, and C3.
- **The order of the steps**, on scenarios run on a virtual clock: a refusal at each
  precondition and what it leaves, the stable window that never holds, an abort after the
  fault, a failed fault command, a failed collector, an error and an interrupt, and an
  observed run that ends with C1 to C4.
- **The fault**: a run deletes the target once between the two fault events; a dry run
  issues no fault and records no fault event; the dry-run command constructs no fault and
  starts no process; and, with bash and a stub `kubectl`, the driver refuses a verb or a
  fault outside a run, refuses another identifier, run, or pod name, and deletes one pod
  once per run.
- **The live path, against stubs**: the phase `run` hands the control paths that it can
  read, against a stub `uv`; the live port runs each verb through a stub driver and keeps
  the command and its output with the checkout path replaced; and a live fault returns the
  status of the fault phase.
- **The analysis and its replay**: a synthetic 2+1 run, built with the builders of the
  reliability-analysis suite, analyzed under the declaration that the control writes, bound
  with `tools/analysis_replay`, and replayed.

The suites of the freeze records changed where they count or list records:
`test_experiment_freeze.py` writes out the three new pins; `test_experiment_preregistration.py`
names revision 3 of V2-E02A as the latest and holds that the driver is added to revisions 1
and 2; `test_analysis_preregistration.py` leaves the three new records out of its earlier
copies and adds a copy with every record; `test_analysis_replay.py` counts 29 records.

## Validation

| Command | Result |
|---|---|
| `uv run --locked python -m tools.experiment_freeze --check` | PASSED: 29 freeze record(s) |
| `uv run --locked python -m tools.experiment_preregistration --check` | PASSED: 5 experiment record(s) and 7 superseded revision(s) |
| `uv run --locked python -m tools.analysis_preregistration --check` | PASSED: 2 analysis experiment(s) |
| `uv run --locked python -m tools.environment_qualification --check` | PASSED: 2 committed qualification(s) |
| `uv run --locked python -m tools.experiment_bounds --check` | PASSED: 1 committed bound record(s) |
| `uv run --locked python -m tools.experiment_freeze --changes` of each of the three new records | UNCHANGED |
| `uv run --locked python -m tools.experiment_e02a plan` | Revision 3, 2 API and 1 runtime replica, the baseline digests |
| `bash docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt dry-run dry-run-1 SCENARIO`, with a scenario that states no repository member, at the first commit `e7cfa4c` with a clean tree | `REFUSED (precondition-not-held, at P2)`: P1 held with the four checks run, and P2 found the 2+2 digests `810b4b27…` and `6a1304a8…` where the record states `f7eaab84…` and `e0b2507c…`. No cluster read was made |
| `uv run --locked ruff check .`, `ruff format --check .` | Passed |
| `uv run --locked python -m mypy`, and with `--platform linux` | Passed, 447 source files |
| `uv run --locked pytest tests/testing/test_experiment_e02a_control.py` | 107 passed |
| The default lane, `uv run --locked pytest`, before the first commit | 23,455 passed, 42 skipped, 14 deselected, in 72 min |
| The default lane, before the second commit | 23,472 passed, 42 skipped, 14 deselected, in 79 min: the 17 tests that the second commit adds, over the first lane |
| `git diff --check` | No finding |

### The hosted lane of the second commit

The hosted default lane, on Ubuntu, failed on the second commit `7a7c04a` with one test:
`test_the_live_port_runs_each_verb_through_the_driver_and_keeps_it`. Its stub driver
printed the working directory with `pwd -W`, an option of Git Bash alone. Linux bash
refuses the option and printed nothing, so the transcript held no checkout path to
replace. Every other job of the run passed. The local lanes ran on Windows, where the
option exists, so they did not show the defect. The job log is not readable without
admin rights, and the failure was located by its position in the collection order: the
mark `F` was followed by a pass and a skip, as that test is followed by
`test_a_live_fault_returns_the_status_of_the_fault_phase` and by the test that runs on
Windows alone.

The third commit changes the stub to `pwd -W 2>/dev/null || pwd`, which prints the form of
the path that each host prints. The change is in the test alone: no file that a freeze
record pins moved, and `--changes` of each new record is UNCHANGED. After it, the suite
passed 107 tests on Windows, and ruff and mypy, with and without `--platform linux`,
passed. The default lane was not run again locally; the hosted lane of the third commit
is its check on Linux.

## Independent review of the first commit

Two independent reviewers read the first commit, `e7cfa4c`: one for the code and its
safety, one for the records, the claims of the documents, and private information. Neither
changed a file. Both found that a dry run cannot inject a fault, that the fault target and
its one command are as the record states, that the figures of the control are those of
the record, that revisions 1 and 2 are byte-unchanged, that G1 and G4 are as required, that
the three records differ from their predecessors in the stated members alone, that the
material classifications are true, and that no private text, local path, or later story
identifier is in the change. The second commit fixed each finding below.

**What the first commit got wrong in the code:**

- **The live run could not start under Git Bash.** The driver exported its own path and
  the path of its bash in the MSYS form, `/d/...` and `/usr/bin/bash`. The control is a
  Windows program, and `MSYS_NO_PATHCONV` kept the shell from converting them, so the
  control found no driver and refused every run. It failed safe, and no test covered the
  hand-off. The driver now exports the Windows form with `cygpath -m -a`, and a test runs
  the phase `run` against a stub `uv`.
- **An error that the procedure does not decide skipped the cleanup.** Only the refusals and
  the aborts of the procedure ran it. An interrupt or a file that cannot be written after P5
  left the release installed and wrote no outcome, and a `ValueError` was printed as a
  refusal that wrote nothing. The control now stops with `STOPPED`, runs the cleanup that it
  can, and exits 4; only an identifier that cannot be used is a refusal that writes nothing.
- **A fault command that failed was recorded as held.** It is now a finding of the step.
  The run is still observed to the end of its window, as the record states.
- **An unanswered read of the namespaces after P7 became an empty list**, which would have
  aborted a valid run as `abort-unrelated-change`. P7 now refuses it.
- **C2 stated a failed collector as held**, and C3 did not read `spec.replicas` or the
  caller record of the last 60 s of the window, which the record names. Both are fixed.
- **Smaller defects:** a reused dry-run identifier raised an error instead of a refusal; a
  scenario with `everyMs` of 0 made the virtual clock loop for ever; stopping a collector on
  Windows ended its bash and not its children; the output of a command went to a pipe that
  a remaining child could hold; the transcript replaced the Windows forms of the checkout
  path and not the form `/d/...` that Git Bash prints; the recorded fault command lacked
  its context; and one test assertion was vacuous.

**What the first commit got wrong in the records and the documents:**

- **The pin reasons of the five modules were one copied sentence**, true for `control.py`
  alone. Revision 3 now states one reason for each file.
- **"The one file of the procedure that runs a cluster command"** was false: the scripts
  that the driver calls run their own commands. Every statement now says that the driver is
  the one file through which the control issues a cluster command.
- **The list of wait bounds was incomplete**, and "every other value" of a run was not read
  from the record: the Service names, the Helm release, the labels, and the line of the
  model verification are constants. Revision 3 and the pages now state both, and the 60 s
  of `abort-cluster-incident`, which `BOUND_PHRASES` holds, is in the list of figures.
- **The diff of `core.py` was miscounted** as "adds 1,499 lines and changes 11"; it inserts
  1,499 and removes 11, the import line among them.
- **The binding table of the experiments page** gave the V2-E03 row of V2-E02A no revision,
  and its dated note was inaccurate. **Stale text** remained in the architecture index, the
  README, and the test inventory, and three pages sent the reader to a readiness review that
  no longer covers the latest records; [the table above](#what-each-latest-freeze-owes) now
  states what each latest freeze owes.
- **Smaller defects:** the count of the sources that owe a classification included V2-E05,
  which neither analysis reads; a dated note of the V2-E02A revision-2 row was dropped; the
  page stated the cleanup order wrongly; "the dry run executes nothing" was not literal when
  a scenario states no repository member; and the record of the prerequisites named an
  approval that no public file holds.

## What this does not establish

- **That the driver works on a cluster.** No verb has been executed against a cluster. A
  scenario or a stub states what a cluster answers, and a cluster can answer otherwise.
- **That a run follows the procedure.** The tests hold the order and the decisions of the
  control. The review of each run compares the run with the record.
- **Any figure of V2-E02A.** No run exists, no fault was injected, and no caller request
  was sent.
- **That the desired state can be switched.** The desired state on `main` stays two API and
  two runtime replicas, and a run refuses at P2 until a later change switches it and
  registers revision 4 with the authorization of the repository owner.
- **That the analysis of V2-E03 or V2-E06 is computed.** Their revisions move a binding and
  compute nothing.
