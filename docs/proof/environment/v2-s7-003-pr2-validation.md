# Validation: the G3 switch and revision 3 of the V2-E02B record (V2-S7-003-PR2)

> **Correction, 2026-11-02.** This page is a record of its date. No authorization of the G1
> merge, `ff45093`, or of the G3 merge, `a3ed812`, was found before it merged, in the search that
> [the deviation page](v2-s7-004-pr1-switch-deviations.md) states. The verdict `eligible` that
> this page reports is not the current verdict, which is `not-decided`, in
> [the adjudicated record](../experiments/v2-e02a/eligibility-adjudicated.v1alpha1.json).

Status: **C0.** This change executes rule G3 of the V2-E02A freeze record in the tree: the two
desired-state files and the declaration that the repository checks derive them from return to
the bytes that they had before the G1 switch. It registers revision 3 of the V2-E02B record in
the same change, and revision 5 of V2-E03 and revision 4 of V2-E06, which bind it. Every check
is static. Nothing ran on a cluster: no cluster was read or changed, no fault was injected, no
caller request was sent, and no run identifier was taken. A freeze record is not evidence, and
no claim is registered.

**The merge is the switch.** The Argo CD Application follows `main`. On a cluster where an
operator applied the Application, the merge of this change makes two API replicas and two
runtime replicas the desired state. Whether that cluster delivers them is observed after the
merge, and it is not in this change. Rule G4 of the V2-E02A record requires the explicit authorization of the
repository owner for that merge, separate from the authorization of the G1 merge. An open
change, an implementation instruction, a passing suite, or the authorization of G1 is not that
authorization.

## What the change adds

| Item | Path |
|---|---|
| The two restored desired-state files | [`gitops/environments/local-docker-desktop/workloads/support-assistant`](../../../gitops/environments/local-docker-desktop/workloads/support-assistant/values.generated.yaml) |
| The declaration, which names the `0.2.0` contract, byte for byte as before the G1 switch | [`tools/gitops_desired_state/core.py`](../../../tools/gitops_desired_state/core.py) |
| V2-E02B freeze, revision 3, 226 pins | [`docs/proof/experiments/v2-e02b/freeze-r3.v1alpha1.json`](../experiments/v2-e02b/freeze-r3.v1alpha1.json) |
| V2-E03 freeze, revision 5, 126 pins | [`docs/proof/experiments/v2-e03/freeze-r5.v1alpha1.json`](../experiments/v2-e03/freeze-r5.v1alpha1.json) |
| V2-E06 freeze, revision 4, 146 pins | [`docs/proof/experiments/v2-e06/freeze-r4.v1alpha1.json`](../experiments/v2-e06/freeze-r4.v1alpha1.json) |
| Three registry rows | [`docs/proof/experiments/registry.v1alpha1.json`](../experiments/registry.v1alpha1.json) |
| A suite for this change | [`tests/testing/test_experiment_e02b_restoration.py`](../../../tests/testing/test_experiment_e02b_restoration.py) |
| The description | [The G3 switch and revision 3 of V2-E02B](../experiments/README.md#the-g3-switch-and-revision-3-of-v2-e02b), and [the desired-state page](../../environment/git-desired-state.md) |

The change adds no tool, and it edits no file of `tools/` but the one declaration. It edits no
chart, contract, binding, Application manifest, platform default, script, or driver. It edits
no record of V2-E02A, no file of a run, no correction, no review, and not the classification.

## The prerequisites, checked before the change was made

| Prerequisite | Observed at `4249226` |
|---|---|
| The runs of V2-E02A are merged, with every attempt retained | Merged as pull request #160: `e02a-1`, `e02a-2`, and `e02a-3`, each `PASSED`, at the executing commit `ff45093` |
| The classification is merged | Merged as pull request #162. The verdict is `eligible`, and its `handoff` member names the last run and both desired states |
| Revision 2 is the latest V2-E02B record | The registry held revisions 1 and 2 and no later one |
| The desired state on `main` is the baseline of revision 4 of V2-E02A | `rendered-workload-release.yaml` had `f7eaab84…` and `values.generated.yaml` had `e0b2507c…` |
| The delivery path did not move after the runs | Between `ff45093` and `4249226`, the chart, the contracts, the deploy files, the Application, the Terraform layer, the environment scripts, the source package, and the lock file have no difference. One scanner exception file differs, which a run does not read. Of the tools that a run executes, the two files of `tools/evidence_index` differ, which `tools/analysis_replay` and `tools/experiment_evidence` import: the path of one ledger and the list that holds it, and no rule |

## The preflight in a scratch tree

Before any file of this tree changed, a copy of the delivery inputs at `4249226` took the
declaration of the commit before the G1 switch. In that copy:

| Step | Result |
|---|---|
| `python -m tools.gitops_desired_state --check`, before the files were written | Exit 1, six findings of `desired-state-release-drifted`: the drift refusal of a declaration without its files |
| `--write local-docker-desktop/support-assistant` | Wrote the two files |
| The two files | `810b4b27e40ec0cf1514d97caa5a7a27818aa12598b1c7b441e4b0ae3c5cb31a` and `6a1304a8f7a2c629a20a2b2ee6697f29a05d9963be43b470c82589c7f469b930`, the digests that the topology of revisions 1 and 2 of V2-E02B states |
| `tools.gitops_desired_state`, `tools.baseline_profile`, and `tools.generated_release`, each `--check` | Passed, and the baseline tool printed that the desired state selects the target |
| The comparison record | Byte for byte the committed record, `c17b7136d4e8268b2b04a7f282495c62d3a4003727113ac260949326faf5c334`. It is still 2+1 against 2+2 with no new difference |
| `helm template`, with the Application's hand-written values, of the baseline and the restored tree | 24 objects and 25 objects. The added object is the PodDisruptionBudget of the runtime tier. No object leaves the render |
| The differences of the objects that both renders hold | The runtime Deployment `spec.replicas`, 1 and 2. The ConfigMap value `INFEROPS_WORKLOAD_VERSION`, `0.1.0` and `0.2.0`. The configuration checksum annotation of both Deployments. Nothing else |

The checksum annotation is in both pod templates, so the merge rolls both Deployments. The
Application does not prune, and the render loses no object, so G3 leaves nothing behind in the
way that G1 could leave the runtime budget. These statements are read from a render. They were
not observed on a cluster.

## The design

- **The declaration is restored byte for byte.** The G1 change edited the contract of the
  declaration and its comments, and no later change edited the file. So this change takes the
  file of the commit before the G1 change. Any other edit would have moved a pin of every
  record that pins the file. With the bytes restored, revisions 1, 2, and 3 of V2-E02B pin one
  digest of it, and the records of Q1, Q2, and Q3 list no moved file. The comments of the file
  no longer describe the switch. The experiments page and Git history do.
- **`tools/baseline_profile` does not change.** It declares the target apart from the desired
  state, so it needed no edit for this switch. At this tree the two statements of the
  two-replica contract name one contract, and the check prints the target as the selected
  side. A test holds that a declaration of the baseline's contract, the state that G1 made,
  still leaves the target a two-replica release.
- **The comparison record does not change.** It reads no committed generated file. Both
  switches leave it byte for byte the same, and a test holds that in both directions.
- **The provenance is copied and held.** `definition.g3Provenance` of revision 3 is a new
  member. Each of its values is copied from the classification record, and a test holds each
  one. No check of `tools/experiment_preregistration` reads it, because a new rule there would
  move a pin of every record that pins that file.

## Revision 3 of the V2-E02B record

### Every member that differs from revision 2

| Member | What differs |
|---|---|
| `metadata` | Revision 3, registered on 2026-11-01 by `V2-S7-003-PR2`, superseding revision 2 by path and digest. Rule set 2 |
| `definition.gitTransitions` | The first item names rule G3 of revision 4 of V2-E02A. The second states that the change that registers revision 3 executes the switch, and it keeps word for word the sentence of rule G4 of V2-E02A on the authorization of each switch |
| `definition.g3Provenance` | New: the governing record, the last run, the classification, and the release that the switch leaves |
| `definition.limitations` | Three items restated and five added: 16 items |
| `definition.history` | One entry states when and why revision 3 was written, and which runs it was written after |
| `fields.experimentIdVersion` | The freeze revision is 3 |
| `fields.gitRevision` | Prepared from `4249226` |
| `pinnedInputs` | The six pins below have their present digests |
| `inputChanges` | Each moved pin, classified |

A test holds that no other member differs. The criteria, the topology, the exclusion reasons,
the material scope, and every member that V2-E02B shares with V2-E02A are those of revision 2.

**Revision 2 stated one thing that stopped being true.** Its limitation "The single-runtime
baseline release has never been installed" held when it was written. The three runs of V2-E02A
installed that release. Revision 3 restates the limitation, and revision 2 is not edited.

**Two limitations are restated for this experiment.** Revision 2 states that no code holds a
declaration of the analysis, and that no tool checks that a run executes the latest revision.
Each sentence named every experiment. V2-E02A has a control since its revision 3, so revision 3
states each of V2-E02B, which has none.

**The five added limitations state:** how to read the sentence of
`fields.derivedNumericBounds` that no characterization of the baseline exists, which stays
because the check holds the two records equal in that field; that no tool checks the
authorization of the merge or the delivery after it; that no check reads
`definition.g3Provenance`; that the owner's reading of
`E02A-AC2` is about those three runs, `E02B-AC2` has the same words, and a later revision decides
its reading before the first run; and that this revision was written after the figures of
V2-E02A were read, changes no set rule, and leaves the two limits of those figures with a reader
of any improvement.

**Revision 3 was written after a result of the comparison was known.** It was written after the
baseline figures were read: `B_failures` 2 and `B_episode` 4,065 ms. Its history states that. It
changes no criterion and no set rule, so the hypothesis and the threshold of the improvement are
those of revision 1.

### The pins and their classification

| Path | Material | Reason, in short |
|---|---|---|
| `tools/baseline_profile/__init__.py` | no | Two names exported. No decision changes |
| `tools/baseline_profile/__main__.py` | no | `--check` prints the selected side. No exit status changes |
| `tools/baseline_profile/core.py` | no | The target is declared apart from the desired state, and the check gains `baseline-desired-state-not-compared` and `baseline-desired-state-drifted`, so it accepts a declaration of either side and refuses a third. The comparison record is unchanged, and P1 does not run this check |
| `tools/evidence_index/__init__.py` | no | The path of the eleventh ledger is exported. No function changes |
| `tools/evidence_index/core.py` | no | One more ledger in the list. No rule of the index changes, and the procedure reads no ledger |
| `tools/experiment_preregistration/core.py` | no | Rule sets 3 and 4 read a V2-E04 record alone. This record is read under the rules of revision 2 |

The two files of `tools/evidence_index` are the inventory that
[the classification](../experiments/v2-e02a/classification.v1alpha1.json) hands to this change.
The three restored files are not in this table: their digests are those of revision 2.

`python -m tools.experiment_freeze --changes` lists no file for revision 3. For revision 2 it
lists these six files, and a run refuses under revision 2 because revision 3 is the latest.

### The two sides of the comparison

Every file that both revision 4 of V2-E02A and revision 3 of V2-E02B pin has one digest, except
five: the three switched files and the two files of the list of ledgers. A test holds that set.
So a change to the chart, a contract, a script, or any other pinned tool between the last run of
V2-E02A and revision 3 fails that test.

## Revision 5 of V2-E03 and revision 4 of V2-E06

The check of the analysis records holds the latest revision of each to the latest revision of
each source. It refuses revision 4 of V2-E03 and revision 3 of V2-E06 once revision 3 of V2-E02B
is registered (`e03-sources-stale`, `e06-sources-stale`), and a test removes the two new records
from a copy and finds both. The repository owner decided, for `V2-S7-001-PR1` and for
`V2-S7-003-PR1`, that the change that registers the source registers the rebinding records.
**This change applies those decisions. The owner did not state it for this change.** The
alternative is a change with the check red.

- **V2-E03 revision 5** binds revision 3 of V2-E02B and lists each member that differs from
  revision 4. Its moved pins are revision 3 of V2-E02B, material, and the two files of the list
  of ledgers, not material.
- **V2-E06 revision 4** binds revision 3 of V2-E02B, and it pins the restored desired-state
  files, as its revision 3 states that a later revision does before any figure is computed. Each
  of those three pins is material. The two files of the list of ledgers are not.

The V2-E02A binding of each stays revision 4, the revision that the runs executed under.

## What each latest freeze owes

This table supersedes, for the records that this change moves,
[the table of `V2-S7-003-PR1`](v2-s7-003-pr1-validation.md#what-each-latest-freeze-owes).
`python -m tools.experiment_freeze --changes` was read for each latest record in the tree of
this change. A test holds each of the moved sets below, except the row of V2-E01. P1 of each
record states that a run refuses while a file is listed. Only V2-E02A has a control that applies
P1, so for each other record the review of the run holds it until that record has a driver. The
materiality in this table is the assessment of this change. The revision that classifies a moved
pin decides it, before the run that it governs.

| Latest record | Files that `--changes` lists | What it owes before its next run |
|---|---|---|
| V2-E02B, revision 3 | None: UNCHANGED | Its driver in a later revision, which also decides the reading of `E02B-AC2`, and a run authorization of the repository owner |
| V2-E02A, revision 4 | The three switched files, and the two of the list of ledgers | Nothing: no further run is planned. A further run refuses at P1 and at P2, and rule G2 requires that |
| V2-E02C, revision 2 | `core.py` of the preregistration check, and the two of the list of ledgers | Its driver, and a revision that classifies each listed file |
| V2-E04, revision 3 | The two of the list of ledgers | Its driver, the bad-release fixture, the known-good identity record, and a revision that classifies each listed file |
| V2-E05, revision 2 | `core.py` of the preregistration check, and the two of the list of ledgers | Its driver and its drift injector, and a revision that classifies each listed file |
| V2-E03, revision 5 | None: UNCHANGED | A revision that binds the source revisions under which the counted runs execute, and its analysis code |
| V2-E06, revision 4 | None: UNCHANGED | The same |
| Q1, revision 2 | None: UNCHANGED. The G3 switch restored the three pins | Nothing while `q1-2` stands |
| Q2, revision 3 | None: UNCHANGED | Nothing while `q2-2` stands |
| Q3, revision 2 | None: UNCHANGED | Nothing while `q3-2` stands |
| Sprint 5 integration validation, revision 2 | The two of the list of ledgers, and the three files of `tools/experiment_evidence` | Only if a new attempt is needed: a revision that classifies each |
| V2-E01, revision 3 | 30 files. Its pins are older than either switch, so this change lists no new path | Only if a new run is needed: a revision that classifies each |

## The tests

[`tests/testing/test_experiment_e02b_restoration.py`](../../../tests/testing/test_experiment_e02b_restoration.py)
is new. It holds the digests of the restored files against the topology and the derivation, the
one digest of each file in revisions 1 to 3, the five files in which the two sides differ, the
members of each new record that differ from the record that it supersedes, the classification of
each moved pin, the transitions, the provenance against the classification and the registry, the
limitations and the history, the rebinding, and the moved set of each latest record.

**A switch that is not whole.** The negative tests cover a restored declaration with the files of
the baseline, restored files with the declaration of the baseline, a declaration of a third
contract, a lost target contract, a hand edit of the runtime replica count, the files of the
baseline at the path against revision 3, a declaration left at the baseline against revision 3,
and the analysis records with no rebinding. No test can show that the owner authorized a merge:
no tool reads that authorization.

**What moved in the earlier suites.** The tests that held that this tree selects the baseline hold
now that it selects the target, and the tests of the selected side run in the opposite direction
on a copy. The suites that read the tree at `HEAD` read the restored release once the change is
committed. The suites of the freeze records write out the three new pins, count 35 records, and
leave the three new records out of the copies that read an earlier state.

## Validation

| Command | Result |
|---|---|
| `uv run --locked python -m tools.gitops_desired_state --check` | OK: the release is what its declared sources derive, and the tree holds nothing else |
| `uv run --locked python -m tools.baseline_profile --check` | OK, and the desired state selects the target |
| `uv run --locked python -m tools.generated_release --check` | OK |
| `uv run --locked python -m tools.experiment_freeze --check` | PASSED: 35 freeze record(s) |
| `uv run --locked python -m tools.experiment_preregistration --check` | PASSED: 5 experiment record(s) and 9 superseded revision(s) |
| `uv run --locked python -m tools.analysis_preregistration --check` | PASSED: 2 analysis experiment(s) |
| `uv run --locked python -m tools.environment_qualification --check` | PASSED: 2 committed qualification(s) |
| `uv run --locked python -m tools.experiment_bounds --check` | PASSED: 1 committed bound record(s) |
| `uv run --locked python -m tools.comparison_eligibility --check` | PASSED: the classification is what the runs give |
| `uv run --locked python -m tools.experiment_freeze --changes` of each latest record | As [the table above](#what-each-latest-freeze-owes) states |
| `uv run --locked python -m tools.evidence_index --check`, and `tools.proof_dashboard --check` | OK. No claim or record changed. Ledgers cite the experiments page, which this change edits, and the check passes |
| `helm lint charts/inferops-llm` | One chart linted, none failed. The chart did not change |
| `uv run --locked ruff check .`, `ruff format --check .` | Passed |
| `uv run --locked python -m mypy`, and with `--platform linux` | Passed, 453 source files |
| `git diff --check 4249226 HEAD` | No finding |

Terraform and the Kubernetes schema gates were not run for this change: it edits no file that
they read.

The suites that read `HEAD` hold the restored release only once it is committed, so the default
lane needs the first commit, as it did for the G1 switch. `uv run --locked pytest` ran on the
second commit, `8b05802`, which holds the fixes of the review: 23,850 passed, 42 skipped, and
14 deselected, in 1:04:21, on Windows. Every command in the table above also ran on that
commit. The commit that adds this paragraph edits this page alone. The hosted lane has not
run: it starts when the pull request opens.

## Independent review of the first commit

Two independent reviewers read the first commit, `01bb664`: one for the code, the tests, and
safety, and one for the records, the claims of the documents, and private information. Neither
changed a file. Neither found a blocking defect in a record: each reviewer compared the three new
records with the records that they supersede, and no criterion, bound, window, fault,
measurement, outcome rule, set rule, exclusion reason, abort condition, cleanup, repetition rule,
topology, or material scope differs. The first reviewer found that the three restored files are
byte for byte those of the commit before the G1 switch, that no other file of the delivery path
moved, that no test went weaker, and that planted edits of a restored file, of the declaration, of
a classification, of a pin, and of the provenance each fail a test. The second reviewer ran each
row of the table of `--changes`, repeated the preflight, and found no later story identifier, no
private text, and no local path. The second commit fixed each finding below. It changed revision
3, so the three records were registered again; the digests of the first commit are superseded and
no file states them.

**What the first commit got wrong:**

- **A false claim.** [The desired-state page](../../environment/git-desired-state.md) said that the
  run of 2026-10-08 applied the release that the tree holds now. That release first appears on
  2026-10-09, and that run has another values digest, on chart `0.5.0`. The page now names the
  two qualifications, each of which reconciled it. Two older sentences had the same looseness, one
  of that page and one of the README, and each now names the chart of that run.
- **A statement of the preflight that was too wide.** This page said that the tools that a run
  executes have no difference between `ff45093` and `4249226`. The two files of
  `tools/evidence_index` differ, and `tools/analysis_replay` and `tools/experiment_evidence` import
  it. The statement now names them.
- **Text carried from revision 2 that stopped being true as written.** The first commit restated
  one limitation. Two more were true of V2-E02B alone, because V2-E02A has a control, and they are
  restated. `fields.derivedNumericBounds` states that no characterization of the baseline exists,
  while the record names V2-E02A a baseline characterization. That field stays, because the check
  holds the two records equal in it, and a fifth added limitation reads the sentence.
- **Overclaims of what is enforced.** This page said that a test holds each moved set, and no test
  held the rows of Sprint 5 and V2-E01. A test now holds the first, and the table states that none
  holds the second. It also said that a stale record cannot run. P1 states that a run refuses, and
  only V2-E02A has a control that applies it.
- **A pin reason less specific than it could be.** The reason of `tools/baseline_profile/core.py`
  omitted the two rules of the check that changed.
- **Smaller defects:** the experiments page said that V2-E02C and V2-E05 owe a classification and
  omitted V2-E04, said that revision 4 differs from the tree in the three switched files where five
  differ, stated "Frozen before any run" for revision 3 with no qualification, and named no table
  for the latest freezes; the opening of this page stated what the merge delivers with no
  qualification; the row of V2-E02C said that it owes a binding of the target, which it holds; the
  validation table said that no cited file changed, where the experiments page is cited and
  changed; and a negative test wrote text where the suite writes bytes.

**What stays as it is.** The tests of the Q1, Q2, and Q3 records assert that no file moved. They
no longer show that the G1 switch had moved those files. Git history and the record of that change
show it.

## What this does not establish

- **That a cluster delivers the target.** No cluster was read. The merge is the switch, so the
  observation of two API and two runtime Ready endpoints at the merged revision cannot be in this
  change. If that observation cannot be made, this change does not show that the target was
  restored: a static render is not a proof of restoration.
- **That the repository owner authorized the merge.** No tool checks it.
- **That the host holds both runtime pods.** The capacity preflight compares stated figures. The
  host of the V2-E02A runs paged during those runs.
- **Any figure of V2-E02B.** No run exists, no fault was injected, and no caller request was sent.
- **Any comparison.** The classification permits one, and no run of the other side exists.
- **That a later record is ready to run.** The table above states what each still owes.
- **That the materiality above is final.** Each later revision decides the moved pins of its record.
