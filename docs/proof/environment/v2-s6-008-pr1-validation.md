# Validation: the selection of the span of V2-E04, and the rebinding of V2-E03 (V2-S6-008-PR1)

Static evidence at C0. This change registers revision 3 of the V2-E04 freeze record and
revision 2 of the V2-E03 freeze record, adds rule set 4 to
`tools/experiment_preregistration`, three rules to `tools/analysis_preregistration`, and
the outcome reference `tools/reversal_outcome`. **Nothing ran**: no E04 run, no
bad-release fixture, no known-good identity record, no driver, no E03 or E06 analysis,
and no other run was executed or created, and no cluster was contacted.

## What the change adds

- [`v2-e04/freeze-r3.v1alpha1.json`](../experiments/v2-e04/freeze-r3.v1alpha1.json),
  revision 3 of V2-E04, under rule set 4. It supersedes revision 2, removes the exclusion
  reason `recovery-onset-not-after-reversal` and every statement of it, and selects the
  span of E04-AC12 by one preregistered rule, `definition.reversalTiming.selection`.
- [`v2-e03/freeze-r2.v1alpha1.json`](../experiments/v2-e03/freeze-r2.v1alpha1.json),
  revision 2 of V2-E03. It supersedes revision 1 and binds revision 3 of V2-E04 by path,
  revision, content digest, and rule set. Its extension counts only the runs of V2-E04
  that executed under revision 3.
- Rule set 4 of [`tools/experiment_preregistration`](../../../tools/experiment_preregistration/core.py),
  which reads revision 3, and three rules of
  [`tools/analysis_preregistration`](../../../tools/analysis_preregistration/core.py),
  which read a V2-E03 revision after revision 1.
- [`tools/reversal_outcome`](../../../tools/reversal_outcome/core.py), one pure function
  that applies the selection and the outcome rules of revision 3 to declared inputs.
- [`tests/testing/test_reversal_outcome.py`](../../../tests/testing/test_reversal_outcome.py),
  and new parts of the preregistration and analysis-preregistration suites.

## The prerequisites, checked before the branch was made

| Prerequisite | Observed at `0863728` |
|---|---|
| The analysis freezes are merged | Pull request #156 is merged into `main`: revision 1 of V2-E03 and V2-E06 |
| Revision 2 is the latest registered V2-E04 revision | The registry pins it, `fae41b8b244cda76e1325ff36e305705d620163bcfac8c1e7bffec2c61b1e619`, and no later revision file exists |
| Revision 1 is the latest registered V2-E03 revision | The registry pins it, `e0aeb1d228df5dfe28adede301fd038c2445f505a196a73b3dbae6461c4e0bca`, and no later revision file exists |
| No run of V2-E02A, V2-E02B, V2-E02C, V2-E04, or V2-E05 exists | No `runs/` or `procedure/` directory exists under any of the five experiment directories |
| `bounds-r1` is unchanged | Content digest `542b05dd9627b25330a4602071d99276218776cf1f78a5c34ac764fbb3188116`, the only bound record |

## What revision 2 got wrong

The collective re-review of the Sprint 6 records on 2026-10-19 found that revision 2 adds an exclusion that the amended definition of the reversal timing does
not authorize. The definition takes as the recovery the first stabilization span that
starts after `reversalStart` and is then observed complete. Revision 2 read the onset
from `stabilizedRecovery.span.first.finishedAt` of the run analysis, whose search starts
at the `fault-injection-finished` event, and when that span did not start after
`reversalStart` it left E04-AC12 not judged, for `recovery-onset-not-after-reversal`.
Its validation record and its limitations said so: the reason could make `INCONCLUSIVE`
a run that the definition judges `PASSED`, or `FAILED` when no span after `reversalStart`
starts within 52,000 ms of it. The checker required the reason, and green checks encoded
the deviation. Revision 3 removes it before any E04 run.

## The selection rule and the outcome rules, as revision 3 states them

**The selection**, `definition.reversalTiming.selection`, structured so that the checker
reads each member:

1. **Candidates**: the caller completions of the window after `reversalStart`, in
   completion order (`candidates.after`, `candidates.source`).
2. **Span rule**: `_find_span` of `tools/reliability_analysis`, unchanged
   (`spanRule.tool`, `spanRule.function`, `spanRule.unchanged`): consecutive successful
   completions, at least 10 over at least 60,000 ms, each condition held, at least one
   reading of each condition inside the span, and the reversal commit as the expected
   desired revision.
3. **Onset and end**: `stabilizationOnset` is the completion of the first request, and
   `stabilizedAt` that of the last request, of the first span that the rule finds over the
   candidates and that completes inside the observation limit, 1,680,000 ms after
   `fault-injection-finished` (`observationLimit`), which `definition.observation` states
   unchanged.
4. **Before `reversalStart`**: a span, or the part of a span, that starts before it is
   never selected and never a reason for a verdict (`beforeReversalStart.selected` and
   `reasonForVerdict`, both false).
5. **Cross-clock orders** (`orders`): the order of each candidate completion and
   `reversalStart`, and the order of `stabilizedAt` and the end of the observation limit.
   Inside the margin of `definition.clockPolicy.ordering` each is resolved both ways:
   `margin-as-after` and `margin-as-before` for the first, and `margin-as-inside` and
   `margin-as-outside` for the second.
6. **Verdicts** (`verdicts.differ`): one verdict under every resolution is the verdict of
   E04-AC12. Different verdicts leave it not judged, for `clock-bound-reached`, and
   `definition.clockPolicy.notJudged` decides the state.
7. **Reported span** (`reported`): when the resolutions select different spans with one
   verdict, `stabilizationOnset`, `stabilizedAt`, `recoveryMs`, the post-recovery window,
   and E04-AC5 use the span of `margin-as-before`, which does not understate `recoveryMs`,
   and otherwise that of `margin-as-after`.
8. **Unusable end reading** (`endReading`): only the verdicts that depend on the clock
   bound are not judged, for `clock-reading-missing`. With no bound every completion is a
   candidate, and when no span completes over them E04-AC12 is not met.
9. **Outcome reference and evidence code** (`outcomeReference`, `evidenceComputation`):
   `reversal_outcome` of `tools.reversal_outcome.core` applies the rule to declared
   inputs; code that computes it from the evidence of a run is pinned by a revision
   registered before the first result-bearing run; until then the review of each run
   computes it by hand and checks it with the reference; the absence of a tool is never a
   reason to leave E04-AC12 not judged.

**Was one unambiguous rule supported?** Yes. The amended definition names the span, the
observation limit, the not-established rule, and the bound comparison, and the merged
clock policy names the margin and the rule for a verdict that is not judged. Neither
says which span the reported figures use when the two resolutions select different spans
with one verdict. Revision 3 takes the span of the resolution that orders the candidates
after `reversalStart`, because it does not understate `recoveryMs`, and states the choice
before any run. No other choice was left open.

**The outcome rules.** E04-AC12 stays a pass criterion with its bound, 52,000 ms, its
formula, `(2 * S) + 30000`, and the bound-record digest
`542b05dd9627b25330a4602071d99276218776cf1f78a5c34ac764fbb3188116`. When `reversalStart` is
established and no span that starts after it completes inside the observation limit,
recovery is not established and E04-AC12 is not met. When `reversalStart` is not
established, E04-AC12 is not judged, for `reversal-start-unconfirmed`. The reasons that
can leave E04-AC12 not judged are exactly `reversal-start-unconfirmed`,
`clock-bound-reached`, and `clock-reading-missing`. A `FAILED` state that the judged
verdicts decide stands.

## Every member that differs from revision 2

The tripwire `test_revision_three_differs_from_revision_two_only_in_the_listed_members`
holds this list.

| Member | Revision 3 | Reason |
|---|---|---|
| `metadata` | revision 3, registered 2026-10-20 by `V2-S6-008-PR1`, supersedes revision 2 by path and digest, rule set 4 | A new revision |
| `definition.reversalTiming.statement` | One sentence added: the selection selects the span | The selection is a member of the timing |
| `definition.reversalTiming.selection` | New | The selection rule above |
| `instants.stabilizationOnset` | `analysisMember` and `notAfterReversalStart` removed, `selectedBy` added, `completion` rewritten for the selection | The onset is not read from the search after the fault, and the exclusion is removed |
| `instants.stabilizedAt` | `analysisMember` removed, `selectedBy` added, the definition and the statement name the selected span | `stabilizedAt` refers to the selected span |
| `definition.observation` | Its last sentence names the selected span; the limit, 1,680 s, is unchanged | The observation-limit rule refers to the selected span |
| `definition.postRecoveryWindow` | Names the selected span | The post-recovery window follows the selected span |
| `definition.criterionClocks` | Entries 7, 8, 16, 17, and 18: the two E04-AC5 entries and the E04-AC12 interval name the selected span; the E04-AC12 order of `reversalStart` now orders each candidate completion; both E04-AC12 orders, and the E04-AC5 limit order, are resolved both ways | The order entry that left the verdict not judged inside the margin is replaced |
| `definition.outcomeRules` | Rule 6 rewritten | The rule that left E04-AC12 not judged when the onset does not follow `reversalStart` is removed |
| `definition.limitations` | The limitation of the reason replaced by four limitations of the selection, eighteen in all | The reason is gone; the limits of the selection are stated |
| `definition.history` | Three entries added, twelve in all | When revision 3 was written, what revision 2 added and the re-review found, and the unchanged expected consequence |
| `exclusionReasons.reasons` | `recovery-onset-not-after-reversal` removed, eleven in all | The finding |
| `fields.acceptanceCriteria` | E04-AC5 names the selected span and holds with no selected span; E04-AC12 replaces its onset clause with the clause for no completed span after `reversalStart` | The one permitted restatement of E04-AC5, and the finding |
| `fields.experimentIdVersion`, `fields.gitRevision` | Freeze revision 3; prepared from `0863728` | A new revision |
| `materialScope` | The entry module `tools.reversal_outcome.core`, and one sentence of the description | The outcome reference is pinned |
| `pinnedInputs`, `inputChanges` | 219 pins; three moved | Below |

Every other member is that of revision 2: the clock policy byte for byte, `reversalStart`,
`controllerObserved`, `desiredStateRestored`, the intervals, the operator events, the
detection rule, the Git transitions, the preparation, E04-AC1 to E04-AC4, E04-AC6 to
E04-AC11, E04-AC13, the observation limit, the window, the abort conditions, the cleanup,
the evidence paths, the repetitions, the measurements, and the executables.

**Revision 2 of V2-E03 against revision 1.** It lists each member that differs in
`definition.changesFromSupersededRevision`, and the new rule `e03-revision-changes`
holds the list:

| Member | Revision 2 |
|---|---|
| `definition.sources` | The V2-E04 binding moves to revision 3, its path, its digest, and rule set 4. The three other bindings are unchanged |
| `definition.population.extension` | `executedUnder` names revision 3 of V2-E04, and the runs statement counts only the runs that executed under it; a run under revision 2 is not in the population |
| `definition.history` | One entry added |
| `fields.experimentIdVersion`, `fields.gitRevision` | Freeze revision 2; prepared from `0863728` |

The population, the signals, the candidate, the ranking, the caller-failure rule, the
computations, the ordering, the clock-policy digest, and the limitations are those of
revision 1.

## The registry rows and the pin classification

Two rows are added after the last row, and no earlier row moves:

| Path | Registered by |
|---|---|
| `docs/proof/experiments/v2-e04/freeze-r3.v1alpha1.json` | `V2-S6-008-PR1` |
| `docs/proof/experiments/v2-e03/freeze-r2.v1alpha1.json` | `V2-S6-008-PR1` |

The digests are those of the registry; the freeze, preregistration, and analysis suites
hold them as literal pins.

**The moved pins of the two new revisions**, each classified in `inputChanges`:

| Record | Path | Material | Why |
|---|---|---|---|
| V2-E04 r3 | `tools/experiment_preregistration/core.py` | yes | Rule set 4, which the record is read under |
| V2-E04 r3 | `tools/reversal_outcome/__init__.py` | no | The package of the outcome reference; it holds no rule |
| V2-E04 r3 | `tools/reversal_outcome/core.py` | yes | The outcome reference |
| V2-E03 r2 | `docs/proof/experiments/v2-e04/freeze-r3.v1alpha1.json` | yes | The source revision that it binds |
| V2-E03 r2 | `tools/analysis_preregistration/core.py` | yes | The three rules of a later V2-E03 revision |
| V2-E03 r2 | `tools/experiment_preregistration/core.py` | no | Rule set 4; the two functions that this record imports are unchanged |

**The moved pins of the other records.** The edits of the two checks move pins of records
that this change does not revise. Each refuses a run under its P1 until a later revision
classifies it; none is revised here:

| Record | `--changes` | Moved by this change | The revision that must classify it |
|---|---|---|---|
| V2-E02A revision 2 | exit 1 | `tools/experiment_preregistration/core.py`, moved again (it was already moved by `V2-S6-005-PR1`) | V2-E02A revision 3, which also pins the driver and the Git switch |
| V2-E02B revision 2 | exit 1 | the same file, again | V2-E02B revision 3 |
| V2-E02C revision 2 | exit 1 | the same file, again | V2-E02C revision 3 |
| V2-E05 revision 2 | exit 1 | the same file, again | V2-E05 revision 3 |
| V2-E06 revision 1 | exit 1 | `tools/analysis_preregistration/core.py` and `tools/experiment_preregistration/core.py` | V2-E06 revision 2, which also binds the source revisions of the counted runs and pins the analysis code |

The superseded revisions are not run: V2-E04 revision 2 lists `core.py`, and V2-E03
revision 1 lists the added revision 3 of V2-E04 and the two checks. Both stay unchanged
history.

## The checker

**Rule set 4** of `tools/experiment_preregistration`, 27 rule identifiers in all:

- every rule of rule set 2, unchanged;
- `prereg-reversal-intervals` and `prereg-reversal-criteria` of rule set 3, unchanged;
- the parts of `prereg-reversal-instants` that hold `reversalStart` (Git visibility, the
  operator-event bracket, the earlier end, the not-established rule), `controllerObserved`,
  `desiredStateRestored`, the source and the clock of each of the five instants, the
  observation limit of `stabilizedAt`, and `recoveryEnd`, unchanged;
- the part of `prereg-reversal-reasons` that holds `reversal-start-unconfirmed`, unchanged;
- five selection rules: `prereg-reversal-selection`, the selection member and the
  definition of `stabilizationOnset`; `prereg-reversal-onset-exclusion`, no onset reason,
  no `notAfterReversalStart` member, exactly three reasons for E04-AC12 not judged, no
  statement of the exclusion without its reason, and each E04-AC12 order resolved both
  ways; `prereg-reversal-unmet-recovery`, E04-AC12 a pass criterion with the clause for no
  completed span after `reversalStart`; `prereg-reversal-selected-span`, `stabilizedAt`,
  the observation limit, the post-recovery window, and E04-AC5 on the selected span; and
  `prereg-reversal-outcome-reference`, the outcome reference named, scoped, and pinned.

**The gates.** `_record_findings` reads rule set 3 and rule set 4 by separate branches, so
rule set 3 reads exactly as before and rule set 4 inherits no onset requirement.
`_rule_set` requires a V2-E04 record after revision 2 to state rule set 4 or later. The
gate of `_shape_problem` requires only that the reversal timing is an object, which both
rule sets read, so it is kept. The one widened statement is that of
`prereg-rule-set-unknown`. The statements of `prereg-reversal-instants`,
`prereg-reversal-intervals`, `prereg-reversal-criteria`, and `prereg-reversal-reasons` now
also say what rule set 4 reads of them; what rule set 3 reads of them is unchanged. The
check does not import `tools/reversal_outcome`.

**Three rules of `tools/analysis_preregistration`**, which read a V2-E03 record after
revision 1 alone, so revision 1 keeps reading under its fourteen: `e03-binding-rule-set`,
each binding states the rule set of its bound record; `e03-extension-revision`, the
extension names the bound V2-E04 revision and counts only its runs; and
`e03-revision-changes`, the record lists each member that differs from the superseded
revision. V2-E03 has seventeen rules and V2-E06 thirteen. The edit moves the pin of V2-E06
revision 1 of `tools/analysis_preregistration`.

## The outcome reference and its tests

`reversal_outcome(ReversalInputs) -> ReversalOutcome`. It reuses `_find_span` of
`tools/reliability_analysis` by import, so it is coupled to the private `_Completion` and
`_Series` types of that tool; a change to them moves the pin of revision 3. It computes
E04-AC12 and E04-AC5, and takes the verdict of every other criterion as declared. It
reads no file. `tests/testing/test_reversal_outcome.py` holds it on synthetic runs:

| Case | E04-AC12 | State |
|---|---|---|
| A valid run, `reversalStart` established, no span after it completes inside the limit | not met | `FAILED` |
| A span before `reversalStart` that completes, and no later qualifying span | not met | `FAILED`, never `INCONCLUSIVE` |
| A span before `reversalStart`, then a later qualifying span inside the bound | held | `PASSED` |
| The same, the later span outside the bound | not met | `FAILED` |
| The same, the later span inside the clock margin of the bound | not judged, `clock-bound-reached` | `INCONCLUSIVE` |
| A span that continues across `reversalStart` | its part after it is the candidate | `PASSED` |
| An interrupted candidate span after `reversalStart` | the next completed span is selected | `PASSED` |
| No completed span at all, every validity criterion held | not met | `FAILED` |
| An earlier span inside the limit, the first later span outside it | not met | `FAILED` |
| `stabilizedAt` inside the margin of the end of the limit, `recoveryMs` far above the bound | not met both ways | `FAILED` |
| Two resolutions select different spans with one verdict | held | the reported figures and E04-AC5 use the `margin-as-before` span |
| A first request inside the margin of `reversalStart`, one verdict both ways | held | `PASSED` |
| The same, two verdicts | not judged, `clock-bound-reached` | `INCONCLUSIVE` |
| An unusable end reading with a candidate span | not judged, `clock-reading-missing` | `INCONCLUSIVE` |
| An unusable end reading with no span that completes | not met | `FAILED` |
| The controller never resolves the reversal commit inside the limit | not met | `INCONCLUSIVE`, through E04-AC2 |
| `reversalStart` not established | not judged, `reversal-start-unconfirmed` | `INCONCLUSIVE` |
| `stream-incomplete` or `caller-incomplete` | held | `INCONCLUSIVE` |
| E04-AC10 or E04-AC11 not met, E04-AC12 not judged | not judged | `FAILED` stands |

It also holds that a span can start up to one reading before the reversal commit holds,
the limitation that revision 3 states, and that inputs that do not describe one run are
refused.

**The negative tests of revision 3**, each planted in a copy of every committed record
with its exact findings: the onset reason registered, or named in an outcome rule or in
E04-AC12; another reason that leaves E04-AC12 not judged, registered, named in an outcome
rule and not registered, or in a member; the onset read from
`stabilizedRecovery.span.first` of the search after the fault; candidates from the fault;
a span before `reversalStart` admitted; the two-way rule removed, or replaced by not
judged; the reported span of the other resolution; the no-span clause of E04-AC12 or of
the outcome rules removed; E04-AC12 made a validity criterion; E04-AC5, `stabilizedAt`,
or the post-recovery window on the span of the analysis; the observation limit shortened;
the E04-AC8 window, the bound value, the formula, or the bound-record digest changed; a
clock policy that differs from the other latest records; the outcome reference unpinned,
unscoped, or another; the `reversalStart` kind, bracket, or earlier end changed; the
recovery interval changed; the three statements of the exclusion that do not name its
reason, which are the clause of E04-AC12, the order entry of E04-AC12, and the outcome
rule; the onset member under an allowed reason; the evidence-computation rule removed;
and revision 3 under rule set 3. Ten malformed members give findings and never raise.

**The negative tests of V2-E03 revision 2**: a binding of the superseded revision 2 of
V2-E04, a wrong digest, a wrong, textual, or missing rule set, an extension that counts
the runs of revision 2 or of a latest revision, a population, signal, candidate, ranking,
or caller-failure member changed and not listed, a member listed that does not differ or
listed twice, a change without its reason, and another superseded digest. Six malformed
members never raise.

## Every path to INCONCLUSIVE once reversalStart is established

When `reversalStart` is established, `reversal-start-unconfirmed` does not apply, and a run
that was neither refused nor aborted is `INCONCLUSIVE` only by one of these paths. Each is
governed by a criterion or a registered reason, and **none depends on whether a
stabilization span starts before `reversalStart`**: the selection never reads such a span
or its part before `reversalStart`, and no rule names one.

| Path | Governing criterion or reason | Why it does not depend on a span before `reversalStart` |
|---|---|---|
| The fault is not produced | E04-AC1, `fault-not-produced` | It reads the argo and pods readings of the bad commit |
| The operator events are not recorded in their order with the reversal commit | E04-AC2 | It reads the operator event log |
| No argo reading reports the reversal commit as `resolvedRevision` inside the observation limit | E04-AC2, inherited from revision 1 unchanged | It reads the argo stream. This is the path by which a run in which the controller never discovers the reversal commit is `INCONCLUSIVE`, where the amended definition would judge it `FAILED`; this change does not change E04-AC2. No registered exclusion reason names this cause, so the aggregate of such a run would need one: a later revision owes it |
| A stream is refused or has a gap of more than 10 s | E04-AC3, `stream-incomplete` | It reads the four streams |
| The caller record is refused or does not cover the window | E04-AC4, `caller-incomplete` | It reads the caller record and the window |
| The post-recovery window after the selected span does not hold | E04-AC5, `caller-incomplete` | It reads the completions after `stabilizedAt` of the selected span, which starts after `reversalStart`; with no selected span it holds |
| An unrelated failure | E04-AC6, `unrelated-failure` | It reads the pods and the node |
| The evidence is incomplete or the analysis is not reproduced | E04-AC7, `evidence-incomplete` | It reads the run directory |
| A verdict needs a cross-clock order or bound comparison inside the margin, and the two computations of `definition.clockPolicy.notJudged` differ | `clock-bound-reached` | It is governed clock uncertainty. For E04-AC12 it arises only when the resolutions of a completion inside the margin of `reversalStart`, or of `stabilizedAt` inside the margin of the end of the limit, give different verdicts, or when `recoveryMs` is inside the margin of the bound |
| The end reading of P8 is unusable, and the two computations differ | `clock-reading-missing` | It is governed missing evidence of the clock bound |

The validation of the outcome reference holds the E04-AC2 path as a test, and states
its state, `INCONCLUSIVE`.

## The consolidated pre-run readiness review

Each latest result-bearing and analysis freeze, read at the head of this change. It
supersedes the review of `V2-S6-006-PR1` for the records that this change moves, and
repeats the others. A `--changes` result is
`python -m tools.experiment_freeze --changes RECORD`.

| Record | Supersedes | Rule set | `--changes` | Clock policy | Bounds |
|---|---|---|---|---|---|
| V2-E02A revision 2 | revision 1 | 2 | exit 1: `tools/experiment_preregistration/core.py` | `c8343a26…4896` | `bounds-r1`; no criterion uses a bound |
| V2-E02B revision 2 | revision 1 | 2 | exit 1: the same file | `c8343a26…4896` | `bounds-r1`; 20,226 ms in an observation that is not a pass criterion |
| V2-E02C revision 2 | revision 1 | 2 | exit 1: the same file | `c8343a26…4896` | `bounds-r1`; 20,226 ms in E02C-AC10 |
| V2-E05 revision 2 | revision 1 | 2 | exit 1: the same file | `c8343a26…4896` | `bounds-r1`, no Q4 bound in a criterion; its own reconciliation bound, 210,000 ms, in E05-AC9 |
| V2-E04 revision 3 | revision 2, `fae41b8b…e619` | 4 | exit 0 | `c8343a26…4896` | `bounds-r1`; 52,000 ms in E04-AC12, 20,226 ms in E04-AC11, and 11,000 ms in the detection rule |
| V2-E03 revision 2 | revision 1, `e0aeb1d2…0bca` | not applicable: its own check | exit 0 | `c8343a26…4896`, bound to its four sources | `bounds-r1`, named; no criterion uses a bound |
| V2-E06 revision 1 | none | not applicable: its own check | exit 1: `tools/analysis_preregistration/core.py` and `tools/experiment_preregistration/core.py` | `c8343a26…4896`, bound to its two sources | `bounds-r1`, named; no figure uses a bound |

| Record | Owed before its first run | Verdict |
|---|---|---|
| V2-E02A revision 2 | A later revision that classifies the moved `core.py` pin; the driver, under a later revision that pins it; and the preregistered Git switch of the two desired-state files to the baseline profile and back | **Not ready to run.** Its P1 refuses a run while `--changes` exits 1 |
| V2-E02B revision 2 | A later revision that classifies the moved `core.py` pin, and the driver under a later revision | **Not ready to run**, for the same reason |
| V2-E02C revision 2 | The same | **Not ready to run**, for the same reason |
| V2-E05 revision 2 | A later revision that classifies the moved `core.py` pin, the driver, and the drift injector, each under a later revision | **Not ready to run**, for the same reason |
| V2-E04 revision 3 | The driver, the bad-release fixture, and the machine-readable known-good identity record, each under a later revision that pins it; that revision also pins code that computes the selection from evidence, or the review of each run computes it by hand and checks it with the outcome reference; and, for the aggregate, a registered reason for the E04-AC2 path above | **Not ready to run**: its pins are unchanged, and the three items do not exist. Its semantics have no onset exclusion |
| V2-E03 revision 2 | The analysis code, under a later revision that pins it, and a later revision that binds the source revisions of the counted runs | **Frozen and complete for this change.** No analysis may run under it |
| V2-E06 revision 1 | A later revision that classifies its two moved check pins, binds the source revisions of the counted runs of V2-E02A and V2-E02B, and pins the analysis code | **Frozen; not ready to run**: its P1 equivalent, `--changes`, exits 1 |

**No result-bearing run, analysis, or later-sprint implementation exists.** No `runs/`,
`procedure/`, `analyses/`, or `corrections/` directory exists under V2-E02A, V2-E02B,
V2-E02C, V2-E03, V2-E04, V2-E05, or V2-E06, and the suites hold the absence of the run and
procedure directories.

## What stays unchanged

- V2-E04 revision 1 (`0dcc3b1c0cba1ee51acc962a083d78a82c42093a75fad72e41b193dde3124e5d`),
  V2-E04 revision 2 (`fae41b8b244cda76e1325ff36e305705d620163bcfac8c1e7bffec2c61b1e619`),
  V2-E03 revision 1 (`e0aeb1d228df5dfe28adede301fd038c2445f505a196a73b3dbae6461c4e0bca`),
  and their registry rows, byte for byte; the freeze suite holds every literal pin.
- q1-1, q2-1, q3-1 (`REFUSED`), q1-2, q2-2, q3-2, every Q1 to Q3 freeze revision, and
  `bounds-r1` (`542b05dd9627b25330a4602071d99276218776cf1f78a5c34ac764fbb3188116`).
- `tools/reliability_analysis`, `tools/analysis_replay`, `tools/experiment_freeze`, and
  every other tool that a freeze record pins, other than the two checks.
- The records of V2-E02A, V2-E02B, V2-E02C, V2-E05, and V2-E06. Their moved pins are listed
  above.
- Rule set 1, rule set 2, and rule set 3.
- Released V1 history and `v1.0.0`.

**The F2 and F3 corrections still pass.** The clock-policy tests of rule set 2, which hold
the F3 correction, and the E03 and E06 tests of the analysis suite that hold the F2
correction, run unchanged against the copy of the records as they were before this change,
and the clock policy of revision 3 is that of every other latest record, byte for byte.

## Validation

Run from Git Bash on the head of the first commit.

| Check | Command | Result |
|---|---|---|
| Preregistration check | `python -m tools.experiment_preregistration --check` | `PASSED: 5 experiment record(s) and 6 superseded revision(s), every rule held` |
| Analysis check | `python -m tools.analysis_preregistration --check` | `PASSED: 2 analysis experiment(s), every rule held` |
| Freeze check | `python -m tools.experiment_freeze --check` | `PASSED: 26 freeze record(s), every rule held` |
| Changed inputs of the two new records | `--changes` for V2-E04 revision 3 and V2-E03 revision 2 | `UNCHANGED`, exit 0, each |
| Changed inputs of the other latest records | `--changes` for each | as the readiness review states: exit 1 for V2-E02A, V2-E02B, V2-E02C, V2-E05, and V2-E06 |
| Consumed records | `environment_qualification`, `runtime_startup`, `caller_characterization`, `experiment_bounds`, and `baseline_profile` `--check` | RESULT_CONSUMED |
| Evidence | `evidence_index --check` and `--gate`; `experiment_run`, `experiment_evidence`, and `analysis_replay` repository checks | RESULT_EVIDENCE |
| Lint and format | `ruff check .`, `ruff format --check .` | RESULT_LINT |
| Types | `mypy`, and with `--platform linux` | RESULT_TYPES |
| Targeted suites | the preregistration, analysis-preregistration, freeze, bounds, qualification, reliability-analysis, outcome-reference, replay, and inventory suites | RESULT_TARGETED |
| Document links | the document-link tests | RESULT_LINKS |
| Whitespace | `git diff --cached --check` | RESULT_WHITESPACE |
| Default lane | `python -m pytest -q` | RESULT_LANE |

## What this does not establish

- That any run follows the selection. No run exists, and no code computes the selection
  from the evidence of a run; the outcome reference applies it to inputs that a review
  declares.
- That the selection rules read every paraphrase. They read structure and named phrases,
  and the experiments README states the gaps.
- That E04-AC2 matches the amended definition for a controller that never discovers the
  reversal commit. It does not, as the inventory above states. It is inherited from
  revision 1, and this change does not change it.
- That any latest result-bearing freeze is ready to run. None is.
