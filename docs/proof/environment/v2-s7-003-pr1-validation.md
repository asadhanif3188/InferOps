# Validation: the G1 switch and revision 4 of the V2-E02A record (V2-S7-003-PR1)

Status: **C0.** This change executes rule G1 of the V2-E02A freeze record in the tree: the
two desired-state files become the files of the single-runtime baseline profile, and the
declaration that the repository checks derive them from names the baseline's contract. It
registers revision 4 of the V2-E02A record in the same change, and revision 4 of V2-E03 and
revision 3 of V2-E06, which bind it. Every check is static. Nothing ran on a cluster: no
cluster was read or changed, no fault was injected, no caller request was sent, and no run
identifier was taken. A freeze record is not evidence, and no claim is registered.

**The merge is the switch.** The Argo CD Application follows `main`. On a cluster where an
operator applied the Application, the merge of this change delivers two API replicas and
one runtime replica. Rule G4 requires the explicit authorization of the repository owner
for that merge. An open change, an implementation instruction, or a passing suite is not
that authorization.

## What the change adds

| Item | Path |
|---|---|
| The two switched desired-state files | [`gitops/environments/local-docker-desktop/workloads/support-assistant`](../../../gitops/environments/local-docker-desktop/workloads/support-assistant/values.generated.yaml) |
| The declaration, which names the `0.1.0` contract | [`tools/gitops_desired_state/core.py`](../../../tools/gitops_desired_state/core.py) |
| The target declared apart from the desired state, and two check rules | [`tools/baseline_profile`](../../../tools/baseline_profile/core.py) |
| V2-E02A freeze, revision 4, 232 pins | [`docs/proof/experiments/v2-e02a/freeze-r4.v1alpha1.json`](../experiments/v2-e02a/freeze-r4.v1alpha1.json) |
| V2-E03 freeze, revision 4, 125 pins | [`docs/proof/experiments/v2-e03/freeze-r4.v1alpha1.json`](../experiments/v2-e03/freeze-r4.v1alpha1.json) |
| V2-E06 freeze, revision 3, 145 pins | [`docs/proof/experiments/v2-e06/freeze-r3.v1alpha1.json`](../experiments/v2-e06/freeze-r3.v1alpha1.json) |
| Three registry rows | [`docs/proof/experiments/registry.v1alpha1.json`](../experiments/registry.v1alpha1.json) |
| A copy of the delivery inputs that holds the two-replica target, for the suites | [`tests/support/target_tree.py`](../../../tests/support/target_tree.py) |
| The description | [The G1 switch and revision 4](../experiments/README.md#the-g1-switch-and-revision-4), [the desired-state page](../../environment/git-desired-state.md), and [the baseline-profile page](../../environment/single-runtime-baseline-profile.md) |

The registered content digests are
`2b1844b9c28c3854db40a5df539cc32ab03ff514639dc3ba0c9bd7ae0bf71234` (V2-E02A revision 4),
`ae500cf4f96bb5c1425e096d4433c83e7ca9e7dc1b4d7ba1587b42058e69d63d` (V2-E03 revision 4), and
`4e9d23deafae70e652f795cb2c0e1bb28b4ad1e1fdf5d1d95e8ccaa2b3ce47c9` (V2-E06 revision 3).
Each is written out in `tests/testing/test_experiment_freeze.py`, so that a change to it is
visible in review.

## The prerequisites, checked before the change was made

| Prerequisite | Observed at `a07a23e` |
|---|---|
| The change that adds the E02A driver is merged, and revision 3 is the latest V2-E02A record | Merged as pull request #158, `a07a23e`. The registry held revisions 1, 2, and 3 of V2-E02A and no later one |
| The desired state on `main` is the target of V2-E02B, two API and two runtime replicas | `rendered-workload-release.yaml` had `810b4b27…` and `values.generated.yaml` had `6a1304a8…`, the digests of the topology of revision 2 of V2-E02B |
| The order of the Sprint 7 changes, and the rebinding of V2-E03 and V2-E06 | The repository owner decided both. The records of those decisions are not in this repository |
| The five checks of the freeze records pass | `experiment_freeze`, `experiment_preregistration`, `analysis_preregistration`, `environment_qualification`, and `experiment_bounds`, each `--check`, passed |

## The design

- **The smallest change of the declaration.** The desired-state declaration changes its
  contract and nothing else: the directory, the binding, the platform defaults, and both
  revisions stay those of the target. So the renderer gives the bytes of the profile,
  which were derived from the same inputs with the baseline's contract, and the two
  switched files are the profile's files byte for byte. `_REFERENCE_RENDER_REVISION` does
  not move.
- **One owner for each field.** `tools/gitops_desired_state` owns the directory, the
  binding, the platform defaults, and both revisions of the desired-state release, and
  the contract that the desired state selects. `tools/baseline_profile` owns the two
  contracts of the comparison: `TARGET_CONTRACT`, the two-replica contract, and
  `BASELINE_CONTRACT`, the `0.1.0` contract. The target is the desired-state declaration
  with `TARGET_CONTRACT`. No field is stated twice.
- **The desired state selects one side.** The check of the baseline profile holds that
  the desired-state declaration names `TARGET_CONTRACT` or `BASELINE_CONTRACT`, and no
  other (`baseline-desired-state-not-compared`), and that its committed files are what it
  derives (`baseline-desired-state-drifted`). The second rule replaces
  `baseline-target-release-drifted`, which held the committed files to the target alone.
- **The comparison record does not depend on the selected side.** The record derives both
  sides from their declarations, reads the Application and the install description, and
  reads no committed generated file. So it is byte for byte the record that revisions 1 to
  3 of V2-E02A and revision 2 of V2-E02B pin, and the switch back, rule G3, needs no new
  record. `python -m tools.experiment_preregistration --check` reads the record and holds
  it to the digest that both records state, and it passes.

## How the comparison stays 2+1 against 2+2

| Proof | Where |
|---|---|
| The comparison record is unchanged: `c17b7136d4e8268b2b04a7f282495c62d3a4003727113ac260949326faf5c334`, the digest that both records state, and `COMPARABLE` | `git diff` names no file of the profile; `test_the_committed_record_is_the_record_the_tree_gives` |
| The target is the two-replica contract while the desired state names the baseline's | `test_the_target_is_declared_apart_from_the_desired_state` |
| A target that follows the desired-state declaration, and the baseline compared with itself, are each `REFUSED` by `baseline-topology-not-declared` and `baseline-version-not-distinct`, never `COMPARABLE` | `test_a_target_that_follows_the_desired_state_is_refused` |
| A target contract replaced by the baseline's is refused by the check and the command | `test_a_target_contract_lost_to_the_baseline_is_refused_by_the_check` |
| The record is the same, byte for byte, when the desired state selects the target and its files are the target's | `test_the_record_is_the_same_whichever_side_the_desired_state_selects` |
| After the switch, a declared API image digest of the target that differs, and a readiness input set in the target's Application alone, each still refuse the comparison | `test_after_the_switch_a_target_digest_or_readiness_drift_is_still_refused`, and the earlier suites of both, which now run on the switched tree |
| The desired-state files are the profile's, byte for byte | `test_the_desired_state_holds_the_baseline_profile_byte_for_byte`, and a test of the desired-state suite |
| A switch made in one of its two parts is refused: the declaration without its files, the files without the declaration, a hand edit, and a declaration of a third contract | four tests of `tests/domain/test_baseline_profile.py`, and the drift rule of `python -m tools.gitops_desired_state --check` |

`python -m tools.baseline_profile --check` passes and prints
`OK       the desired state selects the baseline: contracts/workload/examples/valid/synchronous-llm-local.yaml`.

## Revision 4 of the V2-E02A record

### Every member that differs from revision 3

| Member | What differs |
|---|---|
| `metadata` | Revision 4, registered on 2026-10-23 by `V2-S7-003-PR1`, superseding revision 3 by path and digest. Rule set 2 |
| `definition.gitTransitions` | G1 states that revision 4 is the revision that the switch change registers. G4 states that the change that registers revision 4 executes the switch. G2 and G3 are those of revision 3 |
| `definition.limitations` | One item restated, "Revisions 3 and 4 pin both", and three added: 22 items |
| `definition.history` | One entry states when and why revision 4 was written |
| `fields.experimentIdVersion` | The freeze revision is 4 |
| `fields.gitRevision` | Prepared from `a07a23e` |
| `pinnedInputs` | The six pins below have their present digests |
| `inputChanges` | Each moved pin, classified |

A test holds that no other member differs. The material scope, the topology, the
exclusion reasons, the driver, and the control are those of revision 3, and every member
that V2-E02A shares with V2-E02B is unchanged.

The three added limitations state: what the switch changes and that the comparison record
is unchanged; that no tool checks the authorization of the merge or that the controller
delivered the baseline after it; and that the line of the comparison record "The capacity
preflight derives the footprint of the target only" is not true while the desired state
selects the baseline, because the preflight derives the footprint of the desired-state
release, and P4 reads it.

### G1 and G4

Rule G1 of revision 3 states: "That change registers revision 4 of this record, which
classifies each moved pin, and revision 4 merges before the first run." Revision 4 states:
"That change registers revision 4 of this record, which is this revision. Revision 4 pins
the two switched files and classifies each moved pin, and it merges with the switch,
before the first run."

Rule G4 of revisions 1 to 3 states: "No switch is executed by the change that registers
this record." That held for each of them. Revision 4 is registered by the switch, so its
G4 states: "The change that registers this record executes the G1 switch, in the same
merge." The second sentence, "Each switch is a commit to main that needs the explicit
authorization of the repository owner.", is word for word that of revisions 1 to 3.
Revisions 1, 2, and 3 are not edited, and their pins and rows are unchanged.

### The pins and their classification

| Path | Material | Reason, in short |
|---|---|---|
| `gitops/…/support-assistant/rendered-workload-release.yaml` | yes | Rule G1: the release document of the profile, byte for byte, with the digest that `desiredStateFiles` states |
| `gitops/…/support-assistant/values.generated.yaml` | yes | Rule G1: the generated values of the profile, byte for byte. The Application delivers them |
| `tools/gitops_desired_state/core.py` | yes | The declaration names the `0.1.0` contract, so the check of the tree derives the switched files. No rule changes |
| `tools/baseline_profile/core.py` | no | The target keeps the two-replica contract, and the check gains the selection rule. The comparison record is unchanged, and P1 does not run this check |
| `tools/baseline_profile/__init__.py` | no | Two names exported, and the docstring |
| `tools/baseline_profile/__main__.py` | no | `--check` prints the selected side |

`python -m tools.experiment_freeze --changes` lists no file for revision 4. For revision 3
it lists these six files, and a run refuses under revision 3 because revision 4 is the
latest.

## Revision 4 of V2-E03 and revision 3 of V2-E06

The check of the analysis records holds the latest revision of each to the latest revision
of each source, and it refuses revision 3 of V2-E03 and revision 2 of V2-E06 once revision
4 of V2-E02A is registered (`e03-sources-stale`, `e06-sources-stale`; a test removes the
two new records from a copy and finds both). The repository owner decided that this change
registers the rebinding records, as in `V2-S7-001-PR1`.

- **V2-E03 revision 4** binds revision 4 of V2-E02A by path, revision, content digest, and
  rule set, and lists each member that differs from revision 3 in
  `definition.changesFromSupersededRevision`. Its moved pin is revision 4 of V2-E02A,
  material.
- **V2-E06 revision 3** binds revision 4 of V2-E02A. It also classifies the two
  desired-state files, which its scope pins as the files of the target, as material: the
  files of the target are at that path again only after rule G3. A revision that binds the
  executed V2-E02B revision pins the restored files before any figure is computed.

A test holds that the definition, the fields, and the material scope of each keep the
values of the revision that it supersedes, except the V2-E02A binding, the history, the
list of changes of V2-E03, the freeze revision, and the revision of `main`.

## What each latest freeze owes

This table supersedes, for the records that this change moves,
[the table of `V2-S7-001-PR1`](v2-s7-001-pr1-validation.md#what-each-latest-freeze-owes).
`python -m tools.experiment_freeze --changes` was read for each latest record in the tree
of this change. "Switched" names the three files that the switch moved in every record
whose scope pins them: the two desired-state files and `core.py` of
`tools/gitops_desired_state`. No record below is revised by this change.

| Latest record | Moved by the switch | Moved before | Material, in this assessment | What it owes before its next run |
|---|---|---|---|---|
| V2-E02A, revision 4 | None: UNCHANGED | None | None | Its first run, at a merged commit that holds the switch, under the authorization of the repository owner for its faults |
| V2-E02B, revision 2 | Switched, and the three files of `tools/baseline_profile` | `core.py` of the preregistration check | The two desired-state files: its target is not at its path. The rule G3 restores them, and the restored files have the pinned digests again. The declaration and the baseline-profile tool: not material, because the declaration of the target and the comparison record do not change | The G3 restoration with its own owner authorization, its driver, and a revision that classifies each moved pin |
| V2-E02C, revision 2 | Switched | `core.py` of the preregistration check | As V2-E02B: the desired-state files until G3 | The G3 restoration, its driver, and a revision that classifies each moved pin |
| V2-E04, revision 3 | Switched | None | As V2-E02B: the desired-state files until G3 | The G3 restoration, its driver, the bad-release fixture, the known-good identity record, and a revision that classifies each moved pin |
| V2-E05, revision 2 | Switched | `core.py` of the preregistration check | As V2-E02B: the desired-state files until G3 | The G3 restoration, its driver and its drift injector, and a revision that classifies each moved pin |
| V2-E03, revision 4 | None: UNCHANGED | None | None | A revision that binds the source revisions under which the counted runs execute, and its analysis code |
| V2-E06, revision 3 | None: UNCHANGED | None | None | The same, and the restored files of the target |
| Q1, revision 2 | Switched | None | The desired-state files: Q1 qualifies the target, and the desired state holds the baseline | Only if a new qualification is needed: the G3 restoration and a revision that classifies them. `q1-1` and `q1-2` ran before the switch |
| Q2, revision 3 | Switched | None | As Q1 | Only if a new characterization is needed: as Q1. `q2-2` ran before the switch |
| Q3, revision 2 | Switched | None | As Q1 | Only if a new characterization is needed: as Q1. `q3-2` ran before the switch |
| Sprint 5 integration validation, revision 2 | Switched | The three files of `tools/experiment_evidence` | As Q1 | Only if a new attempt is needed: as Q1, and the three earlier files |
| V2-E01, revision 3 | No path that it did not list before: the two desired-state files and the declaration already differed from its pins | 30 files in all | Unchanged by this change | Only if a new run is needed: a revision that classifies each |

The materiality in this table is the assessment of this change. The revision that
classifies a moved pin decides it, before the run that it governs.

## The tests

`tests/domain/test_baseline_profile.py` gains a section on the selected side: ten tests,
each listed in [the comparison table](#how-the-comparison-stays-21-against-22). Its earlier tests are unchanged except where the target is now read:
the committed values and release of the target, and the regeneration that repairs the
desired state, are read from the derived target.

The suites that test two replicas of a tier read them from
[`tests/support/target_tree.py`](../../../tests/support/target_tree.py): a copy of the
delivery inputs, made once for a session under a temporary directory, in which the
desired-state directory holds the target derived again by `tools.baseline_profile`. Those
are the suites of the capacity preflight, the runtime model cache, the Helm chart, the
renderer, the desired-state tree, and Q1. Each also holds what this tree selects: one
runtime replica, the footprint of one runtime pod fewer, a render with the API tier's
budget alone, and a release that differs from the fixture release in the API replica
count alone. The suites of the provenance tool and of the reconciliation evidence read
`HEAD`, and they read the switched release once the change is committed.

The tripwires of the Q1, Q2, and Q3 records, and of the records of the five reliability
experiments and the two analysis records, name the files that the switch moved, record
by record. The suites of the freeze records write out the three new pins, count 32
records, and leave the three new records out of the copies that read an earlier state.

## Validation

| Command | Result |
|---|---|
| `uv run --locked python -m tools.gitops_desired_state --check` | OK: the release is what its declared sources derive, and the tree holds nothing else |
| `uv run --locked python -m tools.baseline_profile --check` | OK, and the desired state selects the baseline |
| `uv run --locked python -m tools.generated_release --check` | OK |
| `uv run --locked python -m tools.experiment_freeze --check` | PASSED: 32 freeze record(s) |
| `uv run --locked python -m tools.experiment_preregistration --check` | PASSED: 5 experiment record(s) and 8 superseded revision(s) |
| `uv run --locked python -m tools.analysis_preregistration --check` | PASSED: 2 analysis experiment(s) |
| `uv run --locked python -m tools.environment_qualification --check` | PASSED: 2 committed qualification(s) |
| `uv run --locked python -m tools.experiment_bounds --check` | PASSED: 1 committed bound record(s) |
| `uv run --locked python -m tools.experiment_freeze --changes` of each of the three new records | UNCHANGED |
| `uv run --locked python -m tools.experiment_e02a plan` | Revision 4, 2 API and 1 runtime replica, the baseline digests |
| `uv run --locked ruff check .`, `ruff format --check .` | Passed |
| `uv run --locked python -m mypy`, and with `--platform linux` | Passed, 448 source files |
| The suites of the changed modules, before the first commit | Passed, except the tests that read `HEAD`, which hold the switched release only once it is committed. In a scratch clone with the change committed, the suites of the provenance tool, the reconciliation evidence, and the Argo CD Application passed, 226 tests. The P2 test of the control suite was left to the lane |
| `git diff --check` | No finding |

The default lane of the first commit was run after that commit, because the suites of the
provenance tool, the reconciliation evidence, and P2 read `HEAD`. Its result is recorded
by the second commit.

## What this does not establish

- **That a cluster delivers the baseline.** No cluster was read. The merge is the switch,
  and the observation of the controller after the merge is evidence of the run change,
  committed before its first run.
- **That the repository owner authorized the merge.** No tool checks it. The review of the
  change and the record of the merge state it.
- **Any figure of V2-E02A.** No run exists, no fault was injected, and no caller request
  was sent.
- **That the baseline is eligible for the comparison.** The comparison record states the
  eligibility as not-established, and a run and its review decide it.
- **That the materiality above is final.** Each later revision decides the moved pins of
  its record.
