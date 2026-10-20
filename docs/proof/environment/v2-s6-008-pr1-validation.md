# Validation: the selection of the span of V2-E04, and the rebinding of V2-E03 (V2-S6-008-PR1)

Static evidence at C0. This change registers revision 3 of the V2-E04 freeze record and
revision 2 of the V2-E03 freeze record, adds rule set 4 to
`tools/experiment_preregistration`, three rules to `tools/analysis_preregistration`, and
the outcome reference `tools/reversal_outcome`. **Nothing ran**: no E04 run, no
bad-release fixture, no known-good identity record, no driver, no E03 or E06 analysis,
and no other run was executed or created, and no cluster was contacted.

The change has three commits. The first two register the records and close the
findings of their independent review. The third corrects E04-AC2 before the change
merges: the repository owner decided by change control on 2026-10-20 that the
discovery of the reversal by the controller is recovery, which E04-AC12 judges, and no
condition of validity, so a valid run whose controller never discovers an accepted
reversal is `FAILED` and not `INCONCLUSIVE`. [The correction of
E04-AC2](#the-correction-of-e04-ac2) states it, and the sections below describe the
records as the third commit leaves them, except the two validation tables and the
review of the first commit, which describe their own commits.

## What the change adds

- [`v2-e04/freeze-r3.v1alpha1.json`](../experiments/v2-e04/freeze-r3.v1alpha1.json),
  revision 3 of V2-E04, under rule set 4. It supersedes revision 2, removes the exclusion
  reason `recovery-onset-not-after-reversal` and every statement of it, and selects the
  span of E04-AC12 by one preregistered rule, `definition.reversalTiming.selection`.
  E04-AC2 no longer requires an argo reading of the reversal commit, and
  `definition.reversalTiming.controllerDiscovery` states that E04-AC12 judges the
  controller's discovery as recovery.
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
starts within 52,000 ms of it. Rule set 3 requires the reason of revision 2, so its passing
check held the record to the exclusion. Revision 3 removes it before any E04 run.

## The correction of E04-AC2

The first two commits kept E04-AC2 as revisions 1 and 2 state it, and this page
disclosed the consequence. The third commit corrects it, by the change control of
2026-10-20, before the record merges and before any run of V2-E04.

| | E04-AC2, as the first two commits kept it | E04-AC2, as revision 3 states it |
|---|---|---|
| Statement | The operator events detection-reviewed, reversal-decided, reversal-created, and reversal-accepted are recorded in that order, with the reversal commit, and an argo reading reports the reversal commit as resolvedRevision inside the observation limit. | The operator events detection-reviewed, reversal-decided, reversal-created, and reversal-accepted are recorded in that order, with the reversal commit. reversal-accepted is recorded only after a read of main on the remote that the controller reads reports the reversal commit as its head, as definition.gitTransitions T3 states, so it records that the reversal is accepted into the authoritative remote branch. |
| Criterion clocks | Two: the order of the operator events, and the order of an argo reading of the reversal commit and the observation limit | One: the order of the operator events |
| What it reads | The operator event log and the argo stream | The operator event log alone |
| A valid run whose controller never discovers the accepted reversal | E04-AC2 not held: `INCONCLUSIVE`, with no registered reason | E04-AC2 held, E04-AC12 not met: `FAILED` |

The amended definition counts the discovery and the reconciliation of the reversal
by the controller as system recovery, which `recoveryMs` measures. The new member
`definition.reversalTiming.controllerDiscovery` states that, with the structure that the
check reads: `partOf` `recoveryMs`, `judgedBy` E04-AC12, `validity` false, and
`notDiscovered` `not-met`. When no argo reading reports the reversal commit, the
condition series hold no reading of it, so no span after `reversalStart` completes and
E04-AC12 is not met; `controllerObserved`, `desiredStateRestored`, and
`gitopsDiscoveryMs` are not stated, and the window of E04-AC8 ends at the end of the
window, as revision 2 already states, so the containment criteria are judged. No
exclusion reason is added, and no other criterion, window, bound, definition, or
reason changes. The reversal-start definition, the stabilization rule, the 52,000 ms
bound, the observation limit, the E04-AC8 window, and the clock policy are those of
revision 2.

What stays governed: a run whose operator events of the reversal are missing, out of
order, or without the reversal commit is `INCONCLUSIVE` through E04-AC2; a run whose
reversal no read of the remote branch confirms is not judged on E04-AC12, for
`reversal-start-unconfirmed`; a refused or incomplete argo stream is `INCONCLUSIVE`
through E04-AC3, `stream-incomplete`; and a verdict inside the clock margin keeps the
two computations of `definition.clockPolicy.notJudged`, so a conclusively failed pass
criterion stays `FAILED`.

**Held by a structured rule and by the reference.** The sixth selection rule of rule
set 4, `prereg-reversal-controller-discovery`, refuses revision 3 when the member is
absent or states other values, when E04-AC2 is not one validity criterion that names
the four events and the reversal commit, when a criterion clock of E04-AC2 reads
another source than the operator events, and when a validity criterion, a criterion
clock of one, an `INCONCLUSIVE` or `ABORTED` reason, or an abort condition names a
reading or an instant of the controller with the reversal or the known-good revision,
or another text of the record names one with a verdict that is not judged, an
`INCONCLUSIVE` run, or an abort. Since the fourth commit it also refuses, in a
validity criterion, its clocks, such a reason, or an abort condition, a reading of
the controller with `controllerObserved`, `desiredStateRestored`,
`gitopsDiscoveryMs`, or the sync state, and it reads the clock policy, the
repetition rule, the preparation, and the execution gate too. On the record of the
second commit it gives four findings: the clause, the argo criterion clock twice, and the missing member. The
outcome reference judges E04-AC2 itself, from the event log and the commit, and
refuses a declared one, so no reading of the controller can reach the verdict of E04-AC2
through it. A paraphrase that the named words do not reach passes the rule, which its
statement says.

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
4. **Before `reversalStart`**: when the clock bound is computable, a span, or the part
   of a span, that is ordered before it is never selected and never a reason for a
   verdict (`beforeReversalStart.selected` and `reasonForVerdict`, both false). After an
   unusable end reading of P8 no completion can be ordered before it, so none is known
   to be before it, and item 8 states that case.
5. **Cross-clock orders** (`orders`): the order of each candidate completion and
   `reversalStart`, and the order of `stabilizedAt` and the end of the observation limit.
   Inside the margin of `definition.clockPolicy.ordering` each is resolved both ways:
   `margin-as-after` and `margin-as-before` for the first, and `margin-as-inside` and
   `margin-as-outside` for the second.
6. **Verdicts** (`verdicts.differ`): one verdict under every resolution is the verdict of
   E04-AC12. Different verdicts leave it not judged, for `clock-bound-reached`, and
   `definition.clockPolicy.notJudged` decides the state. A verdict that is the same under
   every resolution does not need the order, so the ordering rule of the policy and the
   clock outcome rule do not leave it not judged. That is the record's reading of the
   policy, which leaves not judged a verdict that needs an order inside the margin, and
   the record states it before any run. E04-AC5 is judged the same way.
7. **Reported span** (`reported`): when the resolutions select different spans, whether
   their verdicts agree or differ, `stabilizationOnset`, `stabilizedAt`, `recoveryMs`, the
   post-recovery window, and E04-AC5 use the span of `margin-as-before`, which does not
   understate `recoveryMs`. When it selects no span, because it finds none or its span is
   ordered after the end of the observation limit, they use the span of `margin-as-after`.
8. **Unusable end reading** (`endReading`): only the verdicts that depend on the clock
   bound are not judged, for `clock-reading-missing`. With no bound no completion can be
   ordered before `reversalStart`, so every completion is a candidate. When no span
   completes over them E04-AC12 is not met. When one does, whether it starts after the
   reversal is not known, and that clock uncertainty, not a span known to start earlier,
   leaves E04-AC12 not judged. No reading holds the reversal commit before it is pushed,
   so the condition series hold no span before the push.
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
with one verdict, nor whether a verdict that is the same under every resolution of an
order inside the margin needs that order. Revision 3 takes the span of the resolution
that orders the candidates
after `reversalStart`, because it does not understate `recoveryMs`, reads such a verdict
as not needing the order, and states both before any run. No other choice was left open.

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
| `definition.reversalTiming.controllerDiscovery` | New, in the third commit | The controller's discovery is recovery, which E04-AC12 judges, and no condition of validity |
| `instants.stabilizationOnset` | `analysisMember` and `notAfterReversalStart` removed, `selectedBy` added, `completion` rewritten for the selection | The onset is not read from the search after the fault, and the exclusion is removed |
| `instants.stabilizedAt` | `analysisMember` removed, `selectedBy` added, the definition and the statement name the selected span | `stabilizedAt` refers to the selected span |
| `definition.observation` | Its last sentence names the selected span; the limit, 1,680 s, is unchanged | The observation-limit rule refers to the selected span |
| `definition.postRecoveryWindow` | Names the selected span | The post-recovery window follows the selected span |
| `definition.criterionClocks` | Counting from 0: entry 2 of revision 2, the argo order of E04-AC2, removed in the third commit; entries 7, 8, 16, 17, and 18 of revision 2, 6, 7, 15, 16, and 17 of revision 3: the two E04-AC5 entries and the E04-AC12 interval name the selected span; the E04-AC12 order of `reversalStart` now orders each candidate completion; both E04-AC12 orders, and the E04-AC5 limit order, are resolved both ways | The order entry that left the verdict not judged inside the margin is replaced |
| `definition.outcomeRules` | Rule 6 rewritten | The rule that left E04-AC12 not judged when the onset does not follow `reversalStart` is removed |
| `definition.limitations` | The limitation of the reason replaced by four limitations of the selection, eighteen in all | The reason is gone; the limits of the selection are stated |
| `definition.history` | Four entries added, thirteen in all | When revision 3 was written, the E04-AC2 correction, what revision 2 added and the re-review found, and the unchanged expected consequence |
| `exclusionReasons.reasons` | `recovery-onset-not-after-reversal` removed, eleven in all | The finding |
| `fields.acceptanceCriteria` | E04-AC2 loses its controller clause and states what reversal-accepted records; E04-AC5 names the selected span and holds with no selected span; E04-AC12 replaces its onset clause with the clause for no completed span after `reversalStart` | The change control of 2026-10-20, the permitted restatement of E04-AC5, and the finding |
| `fields.experimentIdVersion`, `fields.gitRevision` | Freeze revision 3; prepared from `0863728` | A new revision |
| `materialScope` | The entry module `tools.reversal_outcome.core`, and one sentence of the description | The outcome reference is pinned |
| `pinnedInputs`, `inputChanges` | 219 pins; three moved | Below |

Every other member is that of revision 2: the clock policy byte for byte, `reversalStart`,
`controllerObserved`, `desiredStateRestored`, the intervals, the operator events, the
detection rule, the Git transitions, the preparation, E04-AC1, E04-AC3, E04-AC4, E04-AC6 to
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
| `metadata`, `pinnedInputs`, `inputChanges` | Revision 2, registered 2026-10-20, superseding revision 1; revision 3 of V2-E04 pinned and the two checks with new digests; each moved pin classified |

The list itself, `definition.changesFromSupersededRevision`, is the one member that
revision 1 does not have and that the rule does not compare. (The first commit listed
five members, and the rule compared the definition, the fields, and the material scope
alone; its review found the three unlisted members.)

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
| V2-E04 r3 | `tools/experiment_preregistration/core.py` | yes | Rule set 4, which the record is read under, with its six selection rules |
| V2-E04 r3 | `tools/reversal_outcome/__init__.py` | no | The package of the outcome reference; it holds no rule |
| V2-E04 r3 | `tools/reversal_outcome/core.py` | yes | The outcome reference, which also judges E04-AC2 |
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

**Rule set 4** of `tools/experiment_preregistration`, 28 rule identifiers in all (27 before
the third commit):

- every rule of rule set 2, unchanged;
- `prereg-reversal-intervals` and `prereg-reversal-criteria` of rule set 3, unchanged;
- the parts of `prereg-reversal-instants` that hold `reversalStart` (Git visibility, the
  operator-event bracket, the earlier end, the not-established rule), `controllerObserved`,
  `desiredStateRestored`, the source and the clock of each of the five instants, the
  observation limit of `stabilizedAt`, and `recoveryEnd`, unchanged;
- the part of `prereg-reversal-reasons` that holds `reversal-start-unconfirmed`, unchanged;
- six selection rules: `prereg-reversal-selection`, the selection member and the
  definition of `stabilizationOnset`; `prereg-reversal-onset-exclusion`, no onset reason,
  no `notAfterReversalStart` member, exactly three reasons for E04-AC12 not judged, no
  other reason of the timing, no statement of the exclusion without its reason in the two
  forms that it names, and each E04-AC12 order resolved both ways; `prereg-reversal-unmet-recovery`, E04-AC12 a pass criterion with the clause for no
  completed span after `reversalStart`; `prereg-reversal-selected-span`, `stabilizedAt`,
  the observation limit, the post-recovery window, and E04-AC5 on the selected span; and
  `prereg-reversal-outcome-reference`, the outcome reference named, scoped, and pinned;
  and, since the third commit, `prereg-reversal-controller-discovery`, the controller's
  discovery as recovery and no condition of validity.

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
E04-AC12 and E04-AC5, and, since the third commit, E04-AC2, from the operator event log
and the reversal commit alone; it refuses a declared E04-AC2, and takes the verdict of
every other criterion as declared. It reads no file. `tests/testing/test_reversal_outcome.py` holds it on synthetic runs:

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
| The controller never resolves the reversal commit inside the limit, the operator events held | not met, E04-AC2 held | `FAILED` (`INCONCLUSIVE`, through E04-AC2, before the third commit) |
| The controller resolves the reversal commit only after the limit | not met | `FAILED` |
| The controller resolves it, and no stabilization follows | not met | `FAILED` |
| The controller resolves it, and a span completes inside the bound | held | `PASSED` |
| An operator event of the reversal missing, out of order, recorded twice, with a decreasing instant, or without the reversal commit | held; E04-AC2 not held | `INCONCLUSIVE`, for E04-AC2 |
| reversal-accepted recorded, but no read confirms the commit | not judged, `reversal-start-unconfirmed`; E04-AC2 held | `INCONCLUSIVE` |
| The argo stream refused, E04-AC3 not held | not met | `INCONCLUSIVE`, `stream-incomplete`, never `FAILED` |
| The controller never reports the reversal commit, and E04-AC8 not met | not met | `FAILED`: the window of E04-AC8 ends at the end of the window |
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
and revision 3 under rule set 3. Since the second commit it also refuses the exclusion
in the words `starts before` and `precedes`, in an outcome rule, a member of the timing,
and the observation limit, a reason of the timing that does not name E04-AC12, and a
defective E04-AC5 beside a conforming one. Since the third commit it also refuses, with
the exact findings, twenty-one defects of the controller rule: the E04-AC2 clause of
revision 2 restored, its argo criterion clock restored, the clause in other words, in
E04-AC3, and as the known-good revision in E04-AC4, an `INCONCLUSIVE` reason and an
abort condition for a controller that does not discover, an outcome rule and a clause of
E04-AC12 that leave the run `INCONCLUSIVE` or the criterion not judged on the
controller, the member of the restored state likewise, the member of the discovery
removed, made a condition of validity, judged by E04-AC2, or not judged, and E04-AC2
made a pass criterion or stated without reversal-accepted; and, since the fourth
commit, a modal and a passive paraphrase, a detection of the reversal, a sync state
in a validity criterion, and a verdict after a semicolon. A further test refuses a
controller condition in the clock policy. Sixteen malformed members give findings and
never raise.

**The negative tests of V2-E03 revision 2**: a binding of the superseded revision 2 of
V2-E04, a wrong digest, a wrong, textual, or missing rule set, an extension that counts
the runs of revision 2 or of a latest revision, a population, signal, candidate, ranking,
or caller-failure member changed and not listed, a member listed that does not differ or
listed twice, a change without its reason, and another superseded digest. Six malformed
members never raise.

## Every path to INCONCLUSIVE once reversalStart is established

When `reversalStart` is established, `reversal-start-unconfirmed` does not apply, and a run
that was neither refused nor aborted is `INCONCLUSIVE` only by one of these paths. Each is
governed by a criterion or a registered reason, **none depends on whether a
stabilization span is known to start before `reversalStart`**, and, since the third
commit, **none depends on whether the controller discovers the reversal**: when the clock bound is
computable, the selection never reads a completion ordered before `reversalStart`, and
no rule names one. After an unusable end reading no completion can be ordered before it,
so no span is known to start before it, and the last row governs that case.

| Path | Governing criterion or reason | Why it does not depend on a span before `reversalStart` |
|---|---|---|
| The fault is not produced | E04-AC1, `fault-not-produced` | It reads the argo and pods readings of the bad commit |
| The operator events are not recorded in their order with the reversal commit | E04-AC2 | It reads the operator event log, and nothing that the controller reports. No registered exclusion reason names this cause |
| Any clause of E04-AC3: a stream is refused, does not state a value in its first or its last reading inside the window, or has a gap of more than 10 s | E04-AC3, `stream-incomplete` | It reads the four streams |
| Any clause of E04-AC4: the caller record is refused, or is not of the plan, the mode, the target, or the end state, does not cover the window, does not end its last completion before the window with a success, or has no completion inside the window after the fault | E04-AC4, `caller-incomplete` | It reads the caller record and the window |
| The post-recovery window after the selected span does not hold | E04-AC5, `caller-incomplete` | It reads the completions after `stabilizedAt` of the selected span, which is not ordered before `reversalStart`; with no selected span it holds |
| An unrelated failure | E04-AC6, `unrelated-failure` | It reads the pods and the node |
| The evidence is incomplete or the analysis is not reproduced | E04-AC7, `evidence-incomplete` | It reads the run directory |
| A verdict needs a cross-clock order or bound comparison inside the margin, and the two computations of `definition.clockPolicy.notJudged` differ | `clock-bound-reached` | It is governed clock uncertainty. For E04-AC12 it arises only when the resolutions of a completion inside the margin of `reversalStart`, or of `stabilizedAt` inside the margin of the end of the limit, give different verdicts, or when `recoveryMs` is inside the margin of the bound |
| The end reading of P8 is unusable, and the two computations differ | `clock-reading-missing` | It is governed missing evidence of the clock bound. No completion can then be ordered before `reversalStart`, so no span is known to start before it; and the cross-clock orders of E04-AC4 are not judged either, so every such run is `INCONCLUSIVE` whatever its spans |

**Not a path.** A valid run in which no argo reading reports the reversal commit inside
the observation limit is `FAILED`: E04-AC2 holds on the operator events, and E04-AC12 is
not met. Until the third commit E04-AC2 required that reading, and the inventory listed
it as the one path by which such a run was `INCONCLUSIVE` where the amended definition
judges it `FAILED`. The outcome reference holds the case as a test, and states its
state, `FAILED`.

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
| V2-E04 revision 3 | The driver, the bad-release fixture, and the machine-readable known-good identity record, each under a later revision that pins it; that revision also pins code that computes the selection from evidence, or the review of each run computes it by hand and checks it with the outcome reference; and, for the aggregate, a registered reason for the E04-AC2 path above | **Not ready to run**: its pins are unchanged, and the three items do not exist. Its semantics have no onset exclusion, and no condition of validity on the controller's discovery |
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

**The earlier corrections still pass.** The clock-policy tests of rule set 2, which hold
the correction of `V2-S6-007-PR1`, and the E03 and E06 tests of the analysis suite, which
hold that of `V2-S6-006-PR1`, run unchanged against the copy of the records as they were
before this change, and the clock policy of revision 3 is that of every other latest
record, byte for byte.

## Validation

Run from Git Bash. The first table is of the first commit, `c1ade35`.

| Check | Command | Result |
|---|---|---|
| Preregistration check | `python -m tools.experiment_preregistration --check` | `PASSED: 5 experiment record(s) and 6 superseded revision(s), every rule held` |
| Analysis check | `python -m tools.analysis_preregistration --check` | `PASSED: 2 analysis experiment(s), every rule held` |
| Freeze check | `python -m tools.experiment_freeze --check` | `PASSED: 26 freeze record(s), every rule held` |
| Changed inputs of the two new records | `--changes` for V2-E04 revision 3 and V2-E03 revision 2 | `UNCHANGED`, exit 0, each |
| Changed inputs of the other latest records | `--changes` for each | exit 1 for V2-E02A, V2-E02B, V2-E02C, and V2-E05 revision 2, and for V2-E06 revision 1, as the readiness review states |
| Consumed records | `environment_qualification`, `runtime_startup`, `caller_characterization`, `experiment_bounds`, and `baseline_profile` `--check` | Each exit 0 |
| Evidence | `evidence_index --check` and `--gate`; the `experiment_run`, `experiment_evidence`, and `analysis_replay` repository checks | Each exit 0 |
| Lint and format | `ruff check .`, `ruff format --check .` | All checks passed; 799 files already formatted |
| Types | `mypy tools` and the changed test modules, and with `--platform linux` | No issues, both, after one fix in the new suite |
| Targeted suites | the preregistration, analysis-preregistration, freeze, replay, inventory, and outcome-reference suites | 2,242 passed, 1 skipped |
| Targeted suites, and the document links | the document-link, bounds, qualification, startup, caller, and reliability-analysis suites, every file staged | 1,032 passed |
| Whitespace | `git diff --cached --check` | Clean |
| Default lane | `python -m pytest -q` | Not measured on the first commit. It was started on that commit and stopped at 6 % once the review fixes began to change the files it reads, so its result would have described neither commit |

The second table is of the second commit, which closes the review findings below.

| Check | Command | Result |
|---|---|---|
| Preregistration, analysis, and freeze checks | the three `--check` commands above | `PASSED: 5 experiment record(s) and 6 superseded revision(s), every rule held`; `PASSED: 2 analysis experiment(s), every rule held`; `PASSED: 26 freeze record(s), every rule held` |
| Changed inputs | `--changes` for each latest record | V2-E04 revision 3 and V2-E03 revision 2 `UNCHANGED`, exit 0; V2-E02A, V2-E02B, V2-E02C, and V2-E05 revision 2 and V2-E06 revision 1 exit 1, as the readiness review states |
| Consumed records and evidence | the commands of the first table | Each exit 0 |
| Lint, format, and types | `ruff check .`, `ruff format --check .`, `mypy` as above, also with `--platform linux` | All checks passed; 799 files already formatted; no issues, both |
| The changed suites | the outcome-reference, analysis-preregistration, and the new parts of the preregistration suite | Each passes in the default lane below; the new fallback test fails on the reference of the first commit |
| Whitespace | `git diff --cached --check` | Clean |
| Default lane | `python -m pytest -q`, every file staged | 23,304 passed, 42 skipped, 14 deselected, in 40 min |

The third table is of the third commit, which corrects E04-AC2.

| Check | Command | Result |
|---|---|---|
| Preregistration, analysis, and freeze checks | the three `--check` commands above | `PASSED: 5 experiment record(s) and 6 superseded revision(s), every rule held`; `PASSED: 2 analysis experiment(s), every rule held`; `PASSED: 26 freeze record(s), every rule held` |
| The new rule on the record of the second commit | the rule-set-4 findings of this commit's check over revision 3 as the second commit registered it, `f842557` | Four findings, all of `prereg-reversal-controller-discovery`: the E04-AC2 clause, its argo criterion clock twice, and the missing member |
| Changed inputs | `--changes` for each latest record | V2-E04 revision 3 and V2-E03 revision 2 `UNCHANGED`, exit 0; V2-E02A, V2-E02B, V2-E02C, and V2-E05 revision 2 exit 1 on `tools/experiment_preregistration/core.py`, and V2-E06 revision 1 on the two checks, as the readiness review states |
| Consumed records and evidence | the commands of the first table | Each exit 0 |
| Lint, format, and types | `ruff check .`, `ruff format --check .`, `mypy` as above, also with `--platform linux` | All checks passed; 799 files already formatted; no issues in 195 source files, both |
| The changed suites | the outcome-reference, preregistration, analysis-preregistration, freeze, replay, and inventory suites | 2,290 passed, 1 skipped |
| The pages | the document-link, case-study, published-methods, test-strategy, authorization, gate-matrix, evidence-index, and release suites | 2,334 passed |
| Whitespace | `git diff --check` | Clean |

The fourth table is of the fourth commit, which closes the findings of the review of the
third commit below.

| Check | Command | Result |
|---|---|---|
| Preregistration, analysis, and freeze checks | the three `--check` commands above | `PASSED: 5 experiment record(s) and 6 superseded revision(s), every rule held`; `PASSED: 2 analysis experiment(s), every rule held`; `PASSED: 26 freeze record(s), every rule held` |
| Changed inputs | `--changes` for each latest record | V2-E04 revision 3 and V2-E03 revision 2 `UNCHANGED`, exit 0; V2-E02A, V2-E02B, V2-E02C, and V2-E05 revision 2 and V2-E06 revision 1 exit 1, as the readiness review states |
| Consumed records and evidence | the commands of the first table | Each exit 0 |
| Lint, format, and types | `ruff check .`, `ruff format --check .`, `mypy` as above, also with `--platform linux` | All checks passed; 799 files already formatted; no issues in 195 source files, both |
| Whitespace | `git diff --check` | Clean |
| Default lane | `python -m pytest -q`, every file staged except this cell | 23,350 passed, 42 skipped, 14 deselected, in 38 min, after the run with the two boundary failures that the review section states |

## Independent review of the first commit

Two independent reviews read the first commit: one of the outcome reference, the
checks, and their suites, and one of the records and the pages against the
requirements and the repository. Neither found a critical or a high defect. The first
draft got the following wrong, and the second commit corrects each:

- **The outcome reference reported the wrong span.** When the span of `margin-as-before`
  completed after the end of the observation limit, the reference still took it as the
  chosen span. It then reported no span and held E04-AC5 trivially, where the record
  says to use the span of `margin-as-after`. A test now holds the fallback; it fails on
  the first commit.
- **The record overclaimed that a span before `reversalStart` is never a reason for a
  verdict.** After an unusable end reading every completion is a candidate, so a span
  that would be ordered before `reversalStart` with a bound can leave E04-AC12 not
  judged instead of not met. That is governed clock uncertainty: with no bound no span is
  known to start before `reversalStart`. The selection, the outcome rule, this record,
  and the experiments README now say so, and state that such a run is `INCONCLUSIVE`
  through E04-AC4 whatever its spans.
- **The reported-span rule covered only resolutions that agree.** It now holds whether
  their verdicts agree or differ, and names the case of a span after the limit.
- **The two-way rule was not reconciled with the clock outcome rule**, which says that a
  verdict inside the margin is not judged. The selection now states that a verdict that is
  the same under every resolution does not need the order, as its reading of the policy.
- **The onset-exclusion rule was narrower than its statement.** It read three phrasings,
  `does not follow`, `does not start after`, and `does not come after`, in three texts.
  Exclusions in the words `starts before` or `precedes`, in a member of the timing, in the
  observation limit, or as a new reason whose text does not name E04-AC12, passed. It now
  reads a second form in every text of the timing, the observation limit, the
  post-recovery window, every criterion, every criterion clock, and the outcome rules,
  and refuses a reason of the timing other than `reversal-start-unconfirmed`; its
  statement says which words it reads and that a paraphrase can pass.
- **A reason that is not a string crashed rule set 4** (`TypeError`), for a
  not-established reason that is a list or an object. It is a finding now, and two
  malformed-member tests hold it.
- **A second E04-AC5 was not refused**, so a defective copy could sit beside a conforming
  one. It is refused now.
- **The change list of V2-E03 revision 2 left out three members** that differ: its
  metadata, its pins, and their classification. The list names them, and the rule
  compares them.
- **Wording.** The selection, selected-span, and outcome-reference statements now say
  that they read members and named phrases; the evidence-computation rule no longer says
  that the analysis of V2-E03 binds the revision that the runs execute under, which
  revision 2 does not; the inventory names every clause of E04-AC2, E04-AC3, and E04-AC4,
  and asks for a registered reason for each E04-AC2 path; a limitation states that the
  run analysis still reports its own stabilized recovery, which is not the span that
  E04-AC12 judges; this page no longer used two finding labels of a review that no public
  page defines; and two typos in the test inventory are fixed.

Both reviews confirmed what they checked and found correct: rule set 3 reads exactly as
before; E04 revisions 1 and 2 and E03 revision 1 are byte-identical to `0863728` and
their rows are unchanged; the clock policy, the bound, the containment window, the
observation limit, and the `reversalStart` definition of revision 3 are those of
revision 2; every count of this page; the pin classification; the readiness review; and
no private-planning text, finding identifier, later story identifier, or local path in
the diff. Left as they are, and disclosed: the outcome reference does not require every
declared criterion to be present, and on an `INCONCLUSIVE` state that the two
computations of `notJudged` decide it lists the reasons of every verdict that is not
judged.

## Independent review of the third commit

Two independent reviews read the third commit: one of the semantics, the outcome
reference, the check, and their suites, and one of the records, the binding, and the
pages. Neither found a critical or a high defect. **Asked whether any valid E04 recovery
failure can still be `INCONCLUSIVE` merely because Argo CD did not discover or
reconcile the accepted reversal, the first answered no.** It traced each validity
criterion, each exclusion reason, each abort condition, the outcome rules, the clock
policy, the fallback of the E04-AC8 window, and the two computations of the reference,
and ran the reference on a run whose condition series never hold the reversal commit:
E04-AC2 held, E04-AC5 held, E04-AC12 not met, `FAILED`, and still `FAILED` with E04-AC8
not met. It found that the controller paths that remain need a span, so a controller
that did discover the reversal: the clock margins of the bound and of the end of the
limit, and a post-recovery window that does not hold. The third commit got the
following wrong, and the fourth corrects each:

- **The new rule crashed on a criterion identifier that is a list** (`TypeError`),
  for a criterion or a criterion clock. It is a finding now, and four malformed-member
  tests hold it.
- **The rule missed modal and passive paraphrases**: `Argo CD must sync the reversal
  commit`, `Argo CD detects the reversal`, and `the reversal is not discovered`. It now
  reads up to three auxiliary words between the controller and its verb, the verbs
  `detect` and `reach`, and the passive forms, and three defects of the review hold it.
- **A validity criterion that reads a state only the controller sets passed** when it
  did not name the reversal, for example `the Application reports Synced`. A validity
  criterion, a criterion clock of one, an `INCONCLUSIVE` or `ABORTED` reason, or an abort
  condition is now refused when it names `controllerObserved`, `desiredStateRestored`,
  `gitopsDiscoveryMs`, or the sync state with a reading of the controller.
- **A verdict after a semicolon escaped** the scan of the other texts, which split
  sentences at semicolons. That scan now reads whole sentences, to their full stop.
- **The rule did not read the clock policy, the repetition rule, the preparation, or
  the execution gate.** It reads them now; a test plants a controller condition in the
  rule of `definition.clockPolicy.notJudged`.
- **Overclaim.** The experiments README and this page said that no reading of the
  controller reaches a validity verdict through the reference. E04-AC1, E04-AC3, and
  E04-AC5 read the argo stream or the condition series, so the pages now say that none
  reaches the verdict of E04-AC2. The reference docstring now says that the read that
  confirms the reversal decides `reversalStart`, which the caller declares, and that the
  reference does not read it. The criterion-clock row of the member table now counts
  its entries from 0.
- **The default lane then refused the fourth commit's first draft.** The pattern of the
  new rule named the controller in the words that the Argo CD boundary test of
  `tests/architecture/test_argocd_bootstrap.py` refuses in any tool outside its allowed
  list, so two of its tests failed: 2 failed, 23,348 passed, 42 skipped, 14 deselected.
  The pattern now spells the name with a whitespace class, which matches the same text,
  and the lane was run again on the final tree.

Both reviews confirmed what they checked and found correct: the binding of V2-E03
revision 2 to the registered digest of the final revision 3 and to rule set 4; the
byte identity of V2-E04 revisions 1 and 2, V2-E03 revision 1, every Q1 to Q4 record,
and `bounds-r1`, and of their registry rows, with `main`; the three checks and the
`--changes` results; rule set 3 and revision 2 unchanged; the faithfulness of the
reading of E04-AC2 by the reference; and no private-planning text, finding identifier,
later story identifier, or local path in the diff. Left as they are, and disclosed:
the reference requires the instants of the operator events not to decrease, so a step
of the host clock backwards between two of them leaves E04-AC2 not held; no registered
reason names a run whose operator events do not hold, as before; and the rule reads
named words, so a paraphrase that none of them reaches passes it.

## What this does not establish

- That any run follows the selection. No run exists, and no code computes the selection
  from the evidence of a run; the outcome reference applies it to inputs that a review
  declares.
- That the selection rules read every paraphrase. They read structure and named phrases,
  and the experiments README states the gaps. A restatement of the controller clause in
  words that `prereg-reversal-controller-discovery` does not name passes it.
- That a run whose operator events do not hold has a registered exclusion reason. None
  names that cause, so the state names E04-AC2, and the aggregate needs a reason that a
  later revision owes.
- That any latest result-bearing freeze is ready to run. None is.
