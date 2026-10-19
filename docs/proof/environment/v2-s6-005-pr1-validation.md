# Validation: the governed reversal timing of V2-E04 (V2-S6-005-PR1)

Status: **static, C0.** This change registers revision 2 of the V2-E04 freeze record
before any run of V2-E04, and adds a rule set to one read-only check. Nothing ran: no
cluster was read or changed, no clock was read, no fault was injected, no commit was made
to `main`, no bad-release fixture, known-good identity record, or driver was created, and
no caller request was sent. A freeze record is not evidence.

## What the change adds

| Item | Path |
|---|---|
| V2-E04 freeze, revision 2, rule set 3, 217 pins, 19 criterion clock entries | [`docs/proof/experiments/v2-e04/freeze-r2.v1alpha1.json`](../experiments/v2-e04/freeze-r2.v1alpha1.json) |
| One registry row | [`docs/proof/experiments/registry.v1alpha1.json`](../experiments/registry.v1alpha1.json) |
| The check: rule set 3, four reversal-timing rules, 22 rules in all | [`tools/experiment_preregistration`](../../../tools/experiment_preregistration/core.py) |
| The suite | [`tests/testing/test_experiment_preregistration.py`](../../../tests/testing/test_experiment_preregistration.py) |
| The description | [The reversal timing of V2-E04, and rule set 3](../experiments/README.md#the-reversal-timing-of-v2-e04-and-rule-set-3) |

The registered content digest is stated in the registry and written out in
`tests/testing/test_experiment_freeze.py`, so that a change to it is visible in review.

## The prerequisites, checked before the branch was made

| Prerequisite | Observed at `4c1e596` |
|---|---|
| The clock policy is merged | Pull request #154 is merged into `main`: revision 2 of V2-E02A, V2-E02B, V2-E02C, and V2-E05, under rule set 2 |
| The repository owner amended the reversal timing before any run of V2-E04 | The change control of 2026-10-18; no run of V2-E04 exists |
| V2-E04 revision 1 is unchanged | It has the content digest that the registry pins, `0dcc3b1c0cba1ee51acc962a083d78a82c42093a75fad72e41b193dde3124e5d`, and `python -m tools.experiment_freeze --check` passed |
| `bounds-r1` is unchanged | Content digest `542b05dd9627b25330a4602071d99276218776cf1f78a5c34ac764fbb3188116`, the only bound record |

## What revision 1 got wrong

A review of the Sprint 6 records found three things in the reversal timing of revision 1:

- `reversalStart` was a controller observation: the start of the last argo reading that
  reports another revision before the first one that reports the reversal commit.
- The time that the controller took to discover the accepted reversal commit was counted
  in the operator interval, and not in the recovery.
- `recoveryEnd` was the start of the stabilization span. Revision 1 chose that onset, and
  the start of the interval, after the Q4 values were known, and no change control
  governed those choices.

The repository owner amended the definition of the reversal timing by change control on
2026-10-18, also after the Q4 values were known, and before any run of V2-E04. The
record states both facts in its history.

## The instants and the intervals, as revision 2 states them

`definition.reversalTiming.instants`:

| Instant | Source, clock | Definition |
|---|---|---|
| `reversalStart` | operator event, host | The instant at which the accepted reversal commit is visible as the head of `main`, the branch that the Application follows, on the remote that the controller reads. Bracketed by the `recordedAt` of `reversal-created`, which the operator records immediately before the push starts, and the first read of that remote that reports the commit, after which the operator records `reversal-accepted`. Judged at the earlier end. It is not a controller observation. When no read reports the commit, it is not established, and E04-AC12 is not judged, for `reversal-start-unconfirmed` |
| `controllerObserved` | collector reading, host | The first argo reading inside the window that reports the reversal commit as `resolvedRevision`. Earliest instant: the start of the last argo reading that reports another revision. Latest: the finish of that reading |
| `desiredStateRestored` | collector reading, host | The finish of the first argo reading that reports the reversal commit as `resolvedRevision` and `Synced`. The reversal commit holds the known-good desired-state files, so `Synced` at it is the controller's report that the live runtime Deployment, its pod template included, is the known-good one |
| `stabilizationOnset` | caller record, node | `stabilizedRecovery.span.first.finishedAt` of the run analysis: the completion of the first request of the first stabilization span that starts after `reversalStart` and is then observed complete without interruption. When it does not follow `reversalStart`, E04-AC12 is not judged, for `recovery-onset-not-after-reversal` |
| `stabilizedAt` | caller record, node | `stabilizedRecovery.stabilizedAt`: the completion of the request that completes that span. A recovery counts only when it lies inside the observation limit, 1,680 s after `fault-injection-finished`. The post-recovery window follows it, and E04-AC5 judges it |

`definition.reversalTiming.recoveryEnd` is `stabilizationOnset`.

`definition.reversalTiming.intervals`:

| Interval | Start | End | Use |
|---|---|---|---|
| `recoveryMs` | `reversalStart` | `stabilizationOnset` | Judged by E04-AC12. System recovery, with the discovery and the reconciliation of the commit by the controller |
| `gitopsDiscoveryMs` | `reversalStart` | `controllerObserved` | Reported, with an inner figure to the earliest instant, never below 0 ms, and an outer figure to the latest. Inside `recoveryMs` |
| `operatorDecisionMs` | `detection-reviewed` | `reversalStart` | Reported. The human interval; no discovery, reconciliation, or stabilization is in it |

The operator events `detection-reviewed`, `reversal-decided`, `reversal-created`, and
`reversal-accepted` keep their own `recordedAt` instants.

E04-AC12 states `bound` `reversal_recovery_bound_ms`, `interval` `recoveryMs`,
`boundValueMs` 52000, `boundFormula` `(2 * S) + 30000`, and `boundRecord`
`bounds-r1` with its digest, and its interval entry in `definition.criterionClocks` runs
from the operator event on the host clock to the caller record on the node clock,
declared cross-clock. It is the first criterion of these records that compares an
interval between the two clocks with a bound, so the bound-comparison margin of the
policy applies for the first time: inside it, the comparison is not judged, for
`clock-bound-reached`.

**Why the onset can precede `reversalStart`.** `tools/reliability_analysis` searches for
the span from the `fault-injection-finished` event. A reading that does not hold the
reversal commit with `Synced` blocks the span only until that reading finishes, so a span
holds at least one argo reading that reports the commit with `Synced`, but its first
request can complete between the last argo reading that does not and `reversalStart`.
That needs the controller to resolve and sync the commit within about one reading of the
push. When it happens, the span of the analysis is not the span that the amended
definition names, and no figure states that span, so E04-AC12 is not judged, for
`recovery-onset-not-after-reversal`.

**That reason is a rule of this record, not of the amended definition.** The amended
definition would take the first span that starts after `reversalStart` and then
completes. No tool computes it, and the record does not ask the review to compute it by
hand. So the reason can make `INCONCLUSIVE` a run that the amended definition would
judge `PASSED`, or `FAILED` when no such span starts within 52,000 ms of `reversalStart`.
That second case is a relaxation, in a case that needs the controller to resolve the
commit within about one reading of the push. It was chosen before any run, and the
record states it as a limitation. The repository owner may prefer the other choice: a
later revision can replace the reason with a computed onset before any run.

## Every member that differs from revision 1

A test, `test_revision_two_of_e04_differs_from_revision_one_only_in_the_listed_members`,
holds this list.

| Member | Change | Why |
|---|---|---|
| `metadata.revision`, `registered`, `registeredBy`, `supersedes`, `preregistrationRules` | 2; 2026-10-19; `V2-S6-005-PR1`; revision 1 by path and digest; rule set 3 | A revision states the one it supersedes and its rule set |
| `definition.hypothesis` | Its last sentence no longer calls the bound an expected observation; it states that most runs are not expected to meet it | The expected consequence |
| `definition.gitTransitions`, T3 | The operator records `reversal-created` immediately before the push, reads `main` on the remote until a read reports the commit, and then records `reversal-accepted`; the transcript holds the push and each read | The bracket of `reversalStart` |
| `definition.detectionRule` | An object: `rule` is revision 1's text unchanged, with 22,000 ms; `clocks` states that the age runs from a Kubernetes timestamp to a reading, that the rule is an operator rule and not a verdict, and that the operator now declares detection only past 22,000 ms plus the margin known during the run | The clock policy; a change of the procedure, stated below |
| `definition.reversalTiming` | Replaced: the five instants, `recoveryEnd`, the three intervals, and the operator events. The revision-1 member `split`, which put the discovery in the operator interval, is removed | The amended timing |
| `definition.limitations` | The clock limitation rewritten, and the analysis limitation added, as in the four records of rule set 2; the discovery limitation now puts the discovery inside `recoveryMs`; four added: the record taken before the push, the template read from `Synced`, that no tool computes the timing, and that `recovery-onset-not-after-reversal` is a rule of the record beyond the amendment; the latest-revision limitation added. Six added in all, one rewritten, one replaced, fifteen in all | The policy; the amended timing |
| `definition.history` | Four entries added: revision 2, when revision 1 chose its timing, the amendment, and the expected consequence | What was known |
| `definition.preparation` | P1 gains the latest-revision clause, and P8 names the policy, as in the four records of rule set 2 | The policy |
| `definition.window.clocks` | As in the four records of rule set 2 | It stated the contradiction |
| `definition.clockPolicy` | The policy of revision 2 of V2-E02B, byte for byte | The policy |
| `definition.criterionClocks`, `definition.criteriaWithoutClocks` | New: 19 entries, 7 of them cross-clock; E04-AC7 and E04-AC13 without clocks | The clock of each criterion |
| `definition.measurements` | One added: the reversal timing, each interval with its start and end | Each interval names its ends |
| `definition.outcomeRules` | The clock rule names the policy and both clock reasons; one rule added for the two timing reasons and for a recovery that is not established | The policy; the amended timing |
| `exclusionReasons` | `clock-bound-reached` names the margin; `clock-reading-missing`, `reversal-start-unconfirmed`, and `recovery-onset-not-after-reversal` added, twelve reasons | The policy; the amended timing |
| `fields.acceptanceCriteria` | E04-AC8 ends its window at `desiredStateRestored` and states it in a `window` member; E04-AC12 judges `recoveryMs` and states the value, the formula, and the bound record | The amended timing |
| `fields.experimentIdVersion`, `fields.gitRevision` | Revision 2; prepared from `4c1e596` | A new revision |
| `pinnedInputs`, `inputChanges` | Three pins moved and are classified | The check changed |

**Unchanged:** the fault, the topology, the detection threshold of 22,000 ms, the
containment criteria E04-AC9, E04-AC10, E04-AC11, and E04-AC13, the validity criteria
E04-AC1 to E04-AC7, the repetitions, the third-run signature, the two bounds of the
window, `definition.window.from` and `definition.window.to`, the observation limit, the
post-recovery window, the abort conditions, the cleanup, the evidence paths, the
analysis declaration, the material scope, and every bound of `derivedNumericBounds`. The
clock text of the window, `definition.window.clocks`, changes as listed above.

**E04-AC8 keeps its coverage.** Revision 1 ended its window at its `reversalStart`, the
start of the last argo reading before the reversal commit was resolved. Revision 2 moves
`reversalStart` earlier, so revision 2 ends the window at `desiredStateRestored`, the
finish of an argo reading that reports the reversal commit, which is always later than
that start. When `desiredStateRestored` is not established, the window ends at the end
of the window. No containment window is shorter than under revision 1.

**The detection rule changes the procedure.** Its threshold of 22,000 ms is unchanged.
The age is the start of a pods reading, on the host clock, less the `createdAt` of a pod,
on the node clock to the second. Revision 1 declared detection at the first pods reading
with an age of at least 22,000 ms. Revision 2 declares it at the first reading whose age
exceeds 22,000 ms by more than d plus w of the start reading of P8 alone, plus 1,000 ms,
because the end reading follows the window. So detection can come later than under
revision 1 by up to that margin plus one reading interval, and the reversal with it. No
verdict is judged from the detection rule, and `operatorDecisionMs`, which starts at
`detection-reviewed`, does not grow with it. What moves is the reversal in time: the bad
rollout stays exposed to the containment criteria for longer, and less of the
observation limit is left. The result page states the age at the detection reading and
whether it exceeds 22,000 ms by more than the margin of the run.

## The registry row and the moved pins

| Record | Supersedes | Registered content digest |
|---|---|---|
| `v2-e04/freeze-r2` | `v2-e04/freeze-r1`, `0dcc3b1c…4e5d` | `fae41b8b244cda76e1325ff36e305705d620163bcfac8c1e7bffec2c61b1e619` |

| Moved pin | Material | Reason |
|---|---|---|
| `tools/experiment_preregistration/core.py` | Yes | P1 runs the check, and rule set 3 holds the record to the clock policy and to its reversal timing |
| `tools/experiment_preregistration/__init__.py` | No | It exports the names that the module added for rule set 2 |
| `tools/experiment_preregistration/__main__.py` | No | It states the number of superseded revisions; no rule changes |

No other pin moved. The scope of revision 2 is that of revision 1.

**The four records of rule set 2.** This change edits `core.py` after revision 2 of
V2-E02A, V2-E02B, V2-E02C, and V2-E05 pinned it. Each of the four now lists it under
`--changes` as changed, exit 1, and no revision classifies it, so the P1 of each refuses
a run until a later revision of it classifies the file. A test,
`test_the_moved_pins_of_each_record_are_this_check_alone`, holds that state. No run of
any of them is authorized, and each will need a later revision for its driver.

## The checker

**Rule set 3.** Revision 2 states rule set 3: every rule of rule set 2, unchanged, and
four reversal-timing rules that read a V2-E04 record. The repository's rule is that a
rule set that a registered record is read under is never edited, so the timing rules are
a new rule set and not an addition to rule set 2. A test, `test_rule_set_two_is_not_edited`,
holds the statement of rule set 2 word for word. A V2-E04 record after revision 1 must
state rule set 3 or later: `prereg-rule-set-unknown` refuses one that states 2 or none,
so a later revision cannot leave the timing rules. That clause is the one change to an
existing rule's statement, and no registered record reads differently under it: the only
such record is this revision 2. A record of another experiment under rule set 3 is held
to rule set 2 alone, because the timing rules read V2-E04 only.

The clock policy of revision 2 is that of revision 2 of V2-E02B byte for byte, and
`prereg-shared-differs` holds the five policies equal. Where its text names rule set 2,
such as "each record of rule set 2 states the same policy", it names the rules that a
record of rule set 3 also holds. The text could not be changed without breaking that
equality.

| Rule | Holds |
|---|---|
| `prereg-reversal-instants` | The five instants, each with a definition, its source, and its clock; `reversalStart` of kind `git-visibility`, bracketed by two operator events, judged at the earlier end, and not established for `reversal-start-unconfirmed`; `stabilizationOnset` read from `stabilizedRecovery.span.first.finishedAt`, of a completed span only, after `reversalStart`, and not judged for `recovery-onset-not-after-reversal` otherwise; `stabilizedAt` read from `stabilizedRecovery.stabilizedAt`, inside the observation limit; `recoveryEnd` is `stabilizationOnset`; the definition of `reversalStart`, its two bracket ends, and the definition of `stabilizationOnset` hold the phrases that the check names |
| `prereg-reversal-intervals` | The three intervals with their start, end, and judging criterion, and the four operator events |
| `prereg-reversal-criteria` | E04-AC12 judges `recoveryMs` against `reversal_recovery_bound_ms` with the value, the formula, and the bound record of `derivedNumericBounds`, which the existing bound rules hold to `bounds-r1`; its one interval entry runs from an operator event to a caller record, cross-clock; E04-AC8 ends its window at `desiredStateRestored`; each of the two is stated once |
| `prereg-reversal-reasons` | Both timing reasons registered for `INCONCLUSIVE` and named by the outcome rules |

The suite plants each defect in a copy of revision 2 and asserts the exact findings:
`reversalStart` made a controller observation, and judged at the later end of its
bracket; `recoveryEnd` set to `stabilizedAt`; an onset allowed from a span that did not
complete; `operatorDecisionMs` ending at `controllerObserved`; `gitopsDiscoveryMs`
removed; `desiredStateRestored` removed; an E04-AC12 bound value, formula, or bound-record
digest other than that of `bounds-r1`; the E04-AC12 interval declared same-clock, and
moved to one clock; the E04-AC8 window ending at `reversalStart`; the confirmation reason
removed, and the rule that names it removed; the onset reason removed; the onset read
from `stabilizedAt`; the onset no longer held after `reversalStart`; `stabilizedAt` no
longer held inside the limit; `recoveryMs` not judged; the operator events cut to one; a
clock policy of V2-E04 that differs; a V2-E04 revision 2 of rule set 2 and of none; a
V2-E04 record without a reversal timing; and ten malformed members, each a finding of a
rule that reads the member and never an error. The second commit adds fourteen more,
listed below with the review. Revision 1 of V2-E04 still passes under rule set 1, is byte-identical, and
is not held to the timing rules.

**The analysis semantics.** Two tests run `tools/reliability_analysis` on the committed
zero-failure case of its suite. On it, the member that revision 2 names for the onset
gives the completion of the first request of the span, `08:00:51.000Z`, and the member
for `stabilizedAt` gives `08:01:51.000Z`: they differ by the span, 60,000 ms, so the one
cannot be read for the other. With one completion inside that span turned into a failure,
the analysis states no stabilized recovery, and both members state nothing: an
interrupted span gives no onset.

**Known gaps.** The timing rules read the structure of a record. Of its prose they read
only the phrases that the check names in four texts, so a text that holds them can still
say something else, and every other definition is held only to be non-empty. They do not read
a run, and no tool computes `reversalStart`, `controllerObserved`,
`desiredStateRestored`, or the three intervals: the review of each run computes them
from the evidence. Nothing checks that the operator records `reversal-created`
immediately before the push.

## What stays unchanged

- V2-E04 revision 1, byte for byte, with its registry row, registered by
  `V2-S6-003-PR1`. A test holds it against its registered digest and the literal pins of
  the freeze suite.
- `bounds-r1`, content digest
  `542b05dd9627b25330a4602071d99276218776cf1f78a5c34ac764fbb3188116`, with
  `reversal_recovery_bound_ms` = 52,000 ms, `(2 * S) + 30000`, and its sources `q2-2`
  and `q3-2`. No Q4 formula, value, source, or digest changed, and the bound was not
  relaxed because of an expected failure.
- `q1-1`, `q2-1`, `q3-1` (`REFUSED`), `q1-2`, `q2-2`, `q3-2`, and the Q1, Q2, and Q3
  freezes and their revisions. The diff touches none of their files, and each check
  rebuilds them (see below).
- Every other freeze record and its revisions, among them the four records of rule set 2,
  whose `core.py` pin this change moves, as stated above.
- `tools/reliability_analysis`, and every other tool except
  `tools/experiment_preregistration/core.py`.
- Released V1 history and `v1.0.0`.

## Validation

Run from Git Bash. The first table is of the first commit, `ca3acb8`.

| Check | Command | Result |
|---|---|---|
| Freeze check | `python -m tools.experiment_freeze --check` | `PASSED: 22 freeze record(s), every rule held` |
| Preregistration check | `python -m tools.experiment_preregistration --check` | `PASSED: 5 experiment record(s) and 5 superseded revision(s), every rule held` |
| Changed inputs of V2-E04 revision 2 | `python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e04/freeze-r2.v1alpha1.json` | `UNCHANGED`, exit 0 |
| Changed inputs of the other records | the same, for V2-E04 revision 1 and the four revisions 2 of rule set 2 | Revision 1 lists the three files of the check, exit 1, and revision 2 classifies them. Each revision 2 of rule set 2 lists `core.py`, exit 1, and no revision classifies it yet |
| Bounds | `python -m tools.experiment_bounds --check` | `PASSED: 1 committed bound record(s), each is what its source records give` |
| Consumed records | `python -m tools.environment_qualification --check`, `runtime_startup`, `caller_characterization`, and `baseline_profile` | Each exit 0: 2 qualifications, 2 Q2 and 2 Q3 characterizations, and the baseline comparison, each rebuilt as committed |
| Evidence index | `python -m tools.evidence_index --check`, and `--gate` | Both exit 0 |
| Lint and format | `ruff check .`, `ruff format --check .` | All checks passed; 790 files already formatted |
| Types | `mypy tools tests/testing/test_experiment_preregistration.py tests/testing/test_experiment_freeze.py`, and with `--platform linux` | No issues in 191 source files, both, after one fix: a default `(None, {})` was typed as `dict[Never, Never]` |
| Related suites | `python -m pytest` over the preregistration, freeze, analysis-replay, reliability-analysis, test-inventory, and document-link suites | 2,634 passed, 1 skipped |
| Whitespace | `git diff --check` | Clean |
| Default lane | `python -m pytest -q` | 23,037 passed, 42 skipped, 14 deselected, in 68 min |

The second table is of the second commit, which closes the review findings below.

| Check | Command | Result |
|---|---|---|
| Freeze and preregistration checks | `python -m tools.experiment_freeze --check`, `python -m tools.experiment_preregistration --check` | `PASSED: 22 freeze record(s), every rule held`; `PASSED: 5 experiment record(s) and 5 superseded revision(s), every rule held` |
| Changed inputs | `python -m tools.experiment_freeze --changes RECORD` | V2-E04 revision 2 lists none, exit 0. V2-E04 revision 1 lists the three files of the check, and each revision 2 of rule set 2 lists `core.py`, exit 1 |
| Bounds, consumed records, and evidence index | the six `--check` commands above, and `evidence_index --gate` | Each exit 0 |
| Lint, format, and types | `ruff check .`, `ruff format --check .`, and `mypy` as above, also with `--platform linux` | All checks passed; 790 files already formatted; no issues in 191 source files, both |
| Whitespace | `git diff --check` | Clean |
| Default lane | `python -m pytest -q` | 23,052 passed, 42 skipped, 14 deselected, in 79 min |

## Independent review of the first commit

Two independent reviews read the first commit: one of the check and its suite, one of
the record and the pages against the amended definition and the repository. Neither
found a critical defect. The second commit corrects every finding below. The record was
generated and registered again, so its registered digest is not that of the first
commit.

**What the first commit got wrong, in the check:**

- A second E04-AC12 or E04-AC8 hid a defective first one. The criteria were read into a
  map by identifier, so the last copy won: a record with a wrong first E04-AC12 and a
  conforming copy after it passed. Each of the two must now be stated once, and the
  first copy is the one read.
- The rule statement said that `reversalStart` is bracketed and that the onset follows
  it, and the check read only flags and member names. Bracket ends of "x" and "y", the
  two ends swapped, and an onset defined as "the stabilizedAt instant" all passed. The
  check now reads named phrases in four texts, and the rule statement says that no other
  prose is read.
- The malformed-member test asserted only that some finding named the record. It now
  holds the rule of each finding.
- No negative test reached a wrong source of `controllerObserved`, a wrong clock of
  `stabilizedAt`, another reason or another instant in the onset rule, another interval
  in E04-AC12, an E04-AC8 statement that names `reversalStart`, outcome rules that do not
  name a timing reason, or an E04-AC12 interval entry declared twice or not at all. The
  suite now plants each.
- No test held that each record is read under the rule set it was registered under. One
  does now.

**What the first commit got wrong, in the record and the pages:**

- This record said that the detection rule moves `operatorDecisionMs` alone, and that
  detection can be declared up to the margin later. Both were false: the interval starts
  at `detection-reviewed` and does not grow, the delay is up to the margin plus one
  reading interval, and what moves is the reversal in time. The pages did not say that
  the procedure changed. Each says so now, and the record names d plus w of the start
  reading, which its policy defines, in place of a clock bound of the start reading,
  which it does not.
- `recovery-onset-not-after-reversal` was presented as following from the amended
  definition. It is a rule of the record, and in a rare case it relaxes a `FAILED`
  verdict to `INCONCLUSIVE`. The record states it as a limitation, and this record and
  the experiments page state its consequences. Its boundary was described as the last
  argo reading that reports another revision; it is the last reading that does not hold
  the reversal commit with `Synced`.
- The experiments page said that three limitations were added and that the windows were
  unchanged. Six were added, and the clock text of the window changed. The page now
  lists the members that change as in the four records of rule set 2, and this record
  no longer lists the windows as unchanged.
- The reason `reversal-start-unconfirmed` left out a missing read in the transcript,
  which the rule it names includes. CONTRIBUTING said that every revision of V2-E04
  states rule set 3, which revision 1 does not. The CHANGELOG did not say that the
  amendment came after the Q4 values were known. Each is corrected.
- The definition of `reversalStart` repeated the wording of a source outside the
  repository. It is reworded.
- The validation table of this record held placeholders when the reviews read it. It
  was filled from the runs before the first commit.

**Kept, and why.** The clause of `prereg-rule-set-unknown` that a V2-E04 record after
revision 1 states rule set 3 or later stays in that rule, which selects the rule set of a
record. A test now holds the rule set of every registered record. The four records of
rule set 2 stay unrunnable until a later revision of each classifies `core.py`.

## What this does not establish

- That any run of V2-E04 passes or fails. No run exists. The record states before any
  run that most runs are not expected to meet E04-AC12.
- That the operator can record `reversal-created` immediately before the push, or that a
  read of the remote confirms the commit in a run. The procedure has no driver.
- That `Synced` at the reversal commit means that the live pod template is the
  known-good one beyond the controller's own comparison.
- That the offset between the clocks stays inside the bound between the two readings.
  It is an assumption, and no reading tests it.
- That the analysis orders node and host instants within any margin. It does not.
- Anything about another provider, node, release, or caller workload.
