# Validation: the E02A driver and revision 3 of the V2-E02A record (V2-S7-001-PR1)

Status: **C0 for the records, C1 for the control.** This change adds the driver of
V2-E02A and the control that it starts, and registers revision 3 of the V2-E02A freeze
record, which pins both. It also registers revision 3 of V2-E03 and revision 2 of V2-E06,
which bind revision 3. The tests executed the control against scenario files on a virtual
clock, and the fault phase of the driver against a stub `kubectl`: that is substituted
execution, C1. The records are static, C0. Nothing ran on a cluster: no cluster was read
or changed, no fault was injected, no caller request was sent, and no run identifier was
taken. A freeze record is not evidence, and no claim is registered.

## What the change adds

| Item | Path |
|---|---|
| The driver: the one file of the procedure that runs a cluster command | [`docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt`](../experiments/v2-e02a/procedure/e02a-driver.txt) |
| The control: five modules | [`tools/experiment_e02a`](../../../tools/experiment_e02a/control.py) |
| V2-E02A freeze, revision 3, 232 pins | [`docs/proof/experiments/v2-e02a/freeze-r3.v1alpha1.json`](../experiments/v2-e02a/freeze-r3.v1alpha1.json) |
| V2-E03 freeze, revision 3, 124 pins | [`docs/proof/experiments/v2-e03/freeze-r3.v1alpha1.json`](../experiments/v2-e03/freeze-r3.v1alpha1.json) |
| V2-E06 freeze, revision 2, 144 pins | [`docs/proof/experiments/v2-e06/freeze-r2.v1alpha1.json`](../experiments/v2-e06/freeze-r2.v1alpha1.json) |
| Three registry rows | [`docs/proof/experiments/registry.v1alpha1.json`](../experiments/registry.v1alpha1.json) |
| The suite, 90 tests | [`tests/testing/test_experiment_e02a_control.py`](../../../tests/testing/test_experiment_e02a_control.py) |
| The description | [The E02A control and its driver](../../testing/experiment-e02a-control.md), and [the section of the experiments page](../experiments/README.md#the-e02a-driver-and-revision-3) |

The registered content digests are
`2eb83a06ba4c1a6289f9f9ebeeb971298ae7f001d91475e8dc6c09696528d456` (V2-E02A revision 3),
`c95d8bc5a11871f6138088ee62917ecff1920584e427f6f4a9c5189d97e8bb10` (V2-E03 revision 3), and
`3c70ee508893be8df42aacea1dbb391be3f3228ca1768401ec6dd3d9a029139a` (V2-E06 revision 2).
Each is written out in `tests/testing/test_experiment_freeze.py`, so that a change to it is
visible in review.

## The prerequisites, checked before the branch was made

| Prerequisite | Observed at `39432e4` |
|---|---|
| Sprint 6 is approved, and the order of the Sprint 7 changes is decided | Both were recorded by the repository owner on 2026-10-21, before the branch was made |
| The tag `learning-baseline-v1` is unchanged | The tag object is `bffcfb4` and it peels to `39432e4`, locally and on the remote |
| Revision 2 is the latest registered V2-E02A record | The registry held revisions 1 and 2 of V2-E02A and no later one |
| The desired state on `main` is the target of V2-E02B, two API and two runtime replicas | `rendered-workload-release.yaml` has `810b4b27…` and `values.generated.yaml` has `6a1304a8…`, the digests of the topology of revision 2 of V2-E02B |
| The five checks of the freeze records pass | `experiment_freeze`, `experiment_preregistration`, `analysis_preregistration`, `environment_qualification`, and `experiment_bounds`, each `--check`, passed |

## The design

- **The driver holds every cluster command, and the control decides.** The control,
  `tools/experiment_e02a`, runs the steps in the order of the record and decides each one
  with a pure function of what it read. It reads and acts only through a port. The live
  port runs each read and each act as one verb of the driver. The package names no
  cluster, no delivery controller, and no script, so it passes the two repository tests
  that refuse an Argo CD spelling under `tools/` and the name of a repository check on a
  delivery path.
- **A dry run cannot inject a fault.** The control deletes a pod only through a fault
  object. The dry-run command constructs none. A fault object is constructed for a run
  identifier `e02a-N` alone, the fault phase of the driver refuses outside a run, and it
  creates a marker before its one command, so one run deletes at most one pod.
- **The record is the source.** The control reads the latest registered V2-E02A record,
  holds it to its registry pin, refuses a revision before 3, and takes every structured
  value from it. The figures that the record states in prose are constants of the control,
  each held to its phrase in the record, so a later revision that changes one refuses the
  control.
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
| `definition.limitations` | Three items replaced and six added, below |
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
`definition.executables`.

The limitations that revision 2 stated, "No driver for this experiment exists", "No code
holds a declaration of the analysis", and "No tool checks that a run executes the latest
registered revision", are replaced by what is now true. The six added items state the
figures that the control restates, the two capacity readings of P4, the six abort
conditions that the control reads, the bounds of its waits, the caller record that it reads
from the log of the runner pod, and the work directory.

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

| Path | Material | Reason |
|---|---|---|
| `docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt` | yes | The driver of the procedure |
| `tools/experiment_e02a/__init__.py`, `__main__.py`, `control.py`, `core.py`, `ports.py` | yes | The control that the driver starts |
| `tools/experiment_preregistration/core.py` | no | Each rule and gate that `V2-S6-005-PR1` and `V2-S6-008-PR1` added reads a V2-E04 record alone. A V2-E02A record of rule set 2 is read under the same rules, and the comparison with V2-E02B is unchanged. The diff from the pinned file adds 1,499 lines and changes 11: the statement of `prereg-rule-set-unknown`, the selection of the rule set of a record, and the refusal detail of an unknown rule set, each of which adds a clause for V2-E04 alone |

`python -m tools.experiment_freeze --changes` lists no file for revision 3. For revisions 1
and 2 it lists the driver as added and `core.py` as changed, as it should: neither pins
them, and a run refuses under them because revision 3 is the latest.

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
  The bindings of V2-E02B, V2-E02C, and V2-E04, the population, the signals, and every other
  member keep their revision-2 values. Its one moved pin is revision 3 of V2-E02A, material.
- **V2-E06 revision 2** binds revision 3 of V2-E02A and keeps every other member of
  revision 1. It also classifies the two pins of revision 1 that `V2-S6-008-PR1` moved, as
  not material: `core.py` of `tools/analysis_preregistration`, whose added rules read a
  V2-E03 record after revision 1 alone, and `core.py` of
  `tools/experiment_preregistration`, whose two functions that this record imports are
  unchanged.

A test holds that each of them differs from its predecessor in the V2-E02A binding, the
history, the change list, the freeze revision, and the revision of `main` alone. The runs
of V2-E02A will execute under a later revision of V2-E02A, so a later revision of each
analysis record binds that revision before any figure is computed from them, as
`definition.population.laterSourceRevision` of V2-E03 already states.

## The control

[The control page](../../testing/experiment-e02a-control.md) states each step and its
refusal. Three facts are stated here because they are decisions of this change.

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
- **The waits have bounds that the record does not state:** 120 s for a collector to start
  sampling, 300 s after the caller duration for the Job to end, and 3,600 s for the
  collectors. They bound waits and change no figure of a run.

## The tests

`tests/testing/test_experiment_e02a_control.py` holds 90 tests in the documentation layer:

- **The binding to revision 3**: the plan, each phrase, the refusals of a record that
  differs from its pin, of a latest revision 2, and of three changed figures, the pins of
  the driver and the control, the moved pins, the members that differ, G1 and G4, the
  shared members, and the 2+2 desired state of the tree, which P2 refuses.
- **Each decision**: the identifier, P1 to P8, the stable pre-fault window and the caller
  log, the target, the declaration, and each abort condition that the control reads.
- **The order of the steps**, on scenarios run on a virtual clock: a refusal at each
  precondition and what it leaves, the stable window that never holds, an abort after the
  fault, and an observed run that ends with C1 to C4.
- **The fault**: a run deletes the target once between the two fault events; a dry run
  issues no fault and records no fault event; the dry-run command constructs no fault and
  starts no process; and, with bash and a stub `kubectl`, the driver refuses a verb or a
  fault outside a run, refuses another identifier, run, or pod name, and deletes one pod
  once per run.
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
| `uv run --locked ruff check .`, `ruff format --check .` | Passed |
| `uv run --locked python -m mypy`, and with `--platform linux` | Passed, 447 source files |
| `uv run --locked pytest tests/testing/test_experiment_e02a_control.py` | 90 passed |
| The default lane, `uv run --locked pytest` | 23,455 passed, 42 skipped, 14 deselected, in 72 min, before the first commit |
| `git diff --check` | No finding |

## Independent review of the first commit

The first commit is reviewed by an independent reviewer before this change is pushed. The
second commit of this change records what the review found and what changed.

## What this does not establish

- **That the driver works on a cluster.** No verb has been executed against a cluster. A
  scenario states what a cluster answers, and a cluster can answer otherwise.
- **That a run follows the procedure.** The tests hold the order and the decisions of the
  control. The review of each run compares the run with the record.
- **Any figure of V2-E02A.** No run exists, no fault was injected, and no caller request
  was sent.
- **That the desired state can be switched.** The desired state on `main` stays two API and
  two runtime replicas, and a run refuses at P2 until a later change switches it and
  registers revision 4 with the authorization of the repository owner.
- **That the analysis of V2-E03 or V2-E06 is computed.** Their revisions move a binding and
  compute nothing.
