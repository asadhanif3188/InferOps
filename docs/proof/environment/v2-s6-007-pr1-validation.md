# Validation: one clock policy for the reliability experiment freezes (V2-S6-007-PR1)

Status: **static, C0.** This change registers revision 2 of four freeze records before
any run of the experiments they fix, and adds a rule set to one read-only check. Nothing
ran: no cluster was read or changed, no clock was read, no fault was injected, no commit
was made to `main`, and no caller request was sent. A freeze record is not evidence.

## What the change adds

| Item | Path |
|---|---|
| V2-E02A freeze, revision 2, 226 pins, 11 criterion clock entries | [`docs/proof/experiments/v2-e02a/freeze-r2.v1alpha1.json`](../experiments/v2-e02a/freeze-r2.v1alpha1.json) |
| V2-E02B freeze, revision 2, 226 pins, 15 entries | [`docs/proof/experiments/v2-e02b/freeze-r2.v1alpha1.json`](../experiments/v2-e02b/freeze-r2.v1alpha1.json) |
| V2-E02C freeze, revision 2, 217 pins, 16 entries | [`docs/proof/experiments/v2-e02c/freeze-r2.v1alpha1.json`](../experiments/v2-e02c/freeze-r2.v1alpha1.json) |
| V2-E05 freeze, revision 2, 217 pins, 13 entries | [`docs/proof/experiments/v2-e05/freeze-r2.v1alpha1.json`](../experiments/v2-e05/freeze-r2.v1alpha1.json) |
| Four registry rows | [`docs/proof/experiments/registry.v1alpha1.json`](../experiments/registry.v1alpha1.json) |
| The check: rule set 2, five clock rules and one rule-set rule, 18 rules in all | [`tools/experiment_preregistration`](../../../tools/experiment_preregistration/core.py) |
| The suite | [`tests/testing/test_experiment_preregistration.py`](../../../tests/testing/test_experiment_preregistration.py) |
| The description | [The clock policy of rule set 2](../experiments/README.md#the-clock-policy-of-rule-set-2) |

The registered content digests are stated in the registry and written out in
`tests/testing/test_experiment_freeze.py`, so that a change to one is visible in review.

## The prerequisites, checked before the branch was made

| Prerequisite | Observed at `8a335ce` |
|---|---|
| The change that registered revision 1 merged | Pull request #153 is merged into `main` |
| The five revision-1 records are unchanged | Each has the content digest that the registry pins, and `python -m tools.experiment_freeze --check` passed |
| The check passed on them | `python -m tools.experiment_preregistration --check` passed |

## What revision 1 got wrong

Each of the five revision-1 records contradicted itself about the clocks:

- P8 read the node clock against the host clock before and after the run, and computed
  a clock bound from the readings.
- An outcome rule compared a cross-clock interval with that bound, and the run was
  `INCONCLUSIVE` for `clock-bound-reached` when the interval lay within it.
- `definition.limitations` described three clocks whose difference is not read, and
  `definition.window.clocks` did the same, with a fixed ordering threshold of one
  second.

The check that registered them, rule set 1, read none of these members, so it passed.

## The clock policy

Each revision 2 states one policy, `definition.clockPolicy`, and the four policies are
equal. [The experiments page](../experiments/README.md#the-clock-policy-of-rule-set-2)
states it in full. In short:

- **Scope.** It governs each verdict instant that `definition.criterionClocks` declares.
  It does not govern how `tools/reliability_analysis` cuts the window, searches a
  stabilization span, or overlaps readings with a span: those order node and host
  instants with no margin, and each record states that as a limitation.
- **Inventory.** Two clocks: the node clock and the host clock. Six sources: the caller
  record and the P8 node instant on the node clock, to 1 ms; the Kubernetes and
  delivery-controller timestamps on the node clock, to 1,000 ms; the collector readings,
  the operator events, and the P8 host instants on the host clock, to 1 ms. The node
  sources share one clock because the provider has one node. The policy names three
  kinds of instant that no verdict reads: the telemetry collector's evaluation instants,
  on the node clock; an operator event's `occurredAt`, which can be on a third clock;
  and the Application status instants other than those of an operation.
- **Measurement.** P8, as in revision 1: a start reading before the runner starts and an
  end reading after the window ends, each a host instant, a node instant, and a second
  host instant.
- **Bound.** The formula of revision 1, word for word: "the largest of the two
  differences between the node instant and the nearer host instant, plus the time
  between the two host instants". Revision 1 does not say whether the difference and
  the time are taken from one reading or each over both readings. The policy computes
  the larger d of the two readings plus the larger w of the two readings, where d is the
  difference between the node instant and the nearer host instant and w the time between
  the two host instants. The other reading, the larger of d1 + w1 and d2 + w2, is never
  larger, because each of those is at most the larger d plus the larger w.
- **Why it is conservative.** The node instant was printed between the two host instants
  of its reading, so the size of the offset at that reading is at most the larger of the
  two differences, and that is at most d + w. Each instant is cut to the millisecond, so
  the offset can exceed the bound by less than 1 ms. The margin adds the coarser
  resolution of the two sources, at least 1 ms.
- **Uncertainty.** The bound is measured at two readings. Its use between them is an
  explicit assumption that the offset stays inside it. Drift is not measured. The result
  page states the net change of the offset, and no verdict reads it. The procedure does
  not synchronize the clocks, and it does not guarantee the bound.
- **Unusable readings.** An unusable start reading: no fault is injected, and the run is
  `REFUSED` for `precondition-not-held`. An unusable end reading: the bound is not
  computable, and each cross-clock order and bound comparison is not judged, for the new
  reason `clock-reading-missing`. The end-reading rule names no state of its own.
- **A verdict that is not judged.** The state is computed with each such verdict taken as
  held and as failed. When the two agree, that is the state. When they differ, the run is
  `INCONCLUSIVE` for the reason of the verdict. A `FAILED` state that the judged verdicts
  decide is never made `INCONCLUSIVE`.
- **Ordering and bound comparison.** One margin: the clock bound plus the coarser
  resolution of the two sources. Inside it, no cross-clock order is stated and no
  cross-clock bound comparison is judged, for `clock-bound-reached`. Instants of one clock
  are ordered to their resolution, and an interval of one clock is compared directly.

### One decision of the repository owner

The repository owner chose one rule for a verdict that is not judged, before the records
were written, and applied it to an unusable end reading, to an order inside the margin,
and to a bound comparison inside the margin. Without it, a near-threshold verdict could
turn a run that another pass criterion had failed into an exclusion.

### How revision 2 judges a run otherwise than revision 1

No criterion of the four records compares an interval between the two clocks with a
bound: the two bound comparisons, E02C-AC10 and E05-AC9, are each on one clock. So the
clock-bound rule of revision 1 had no case to apply to. Revision 2 judges otherwise in
four places, each under the rule above:

- the margin replaces the fixed one-second ordering rule;
- an order inside the margin is not judged and can make a run `INCONCLUSIVE` for
  `clock-bound-reached`, where revision 1 stated no consequence;
- an unusable end reading can make a run `INCONCLUSIVE` for `clock-reading-missing`;
- an unusable start reading makes a run `REFUSED`. Revision 1's P8 stated no outcome.

### The clock of each criterion

`definition.criterionClocks` declares the source and the clock of the two instants of
each order and each interval that a criterion states. Of the 55 entries, 22 are
cross-clock. `definition.criteriaWithoutClocks` lists the seven criteria that order no
instant and compare no interval: the evidence criterion of each record, the
manual-action criterion of V2-E02B and V2-E05, which each fail on any manual-action
event, and the drift criterion of V2-E05.

- **Comparisons on one clock.** E02C-AC10, `callerFailureEpisodeMs` against 20,226 ms,
  is on the node clock: both ends of a closed episode are caller completions. Whether an
  episode near an edge of the window is in it follows the analysis's cut of the window.
  E05-AC9, the restoration against 210,000 ms, is on the host clock. The 10 s of AC2 is
  on the host clock, and the 60 s of the post-recovery window is on the node clock.
- **Cross-clock orders.** A caller completion or `stabilizedAt` against the window, an
  event, or the observation limit; a `deletionTimestamp` against the observation limit;
  and the controller's `operationStartedAt`, to the second, against the
  `fault-injection-started` event in E05-AC8. An operation that starts within the margin
  of that event is not ordered with it, so E05-AC8 is then not judged.

## Every member that differs from revision 1

A test, `test_revision_two_differs_from_revision_one_only_in_the_listed_members`, holds
this list for each record.

| Member | Change | Why |
|---|---|---|
| `metadata.revision`, `registeredBy`, `supersedes`, `preregistrationRules` | 2; `V2-S6-007-PR1`; revision 1 by path and digest; rule set 2 | A revision states the one it supersedes and its rule set |
| `definition.limitations` | The clock limitation rewritten to the two-clock inventory and the assumption; two limitations added: the analysis cuts that the policy does not govern, and that no tool checks that a run executes the latest revision | The policy; P1 |
| `definition.history` | One entry added for revision 2 | What was known |
| `definition.preparation` | P1 gains one clause: the record is the latest registered revision of its experiment. P8 keeps its reading and its formula, and names the policy | The latest-revision rule; the policy |
| `definition.window.clocks` | Rewritten to the inventory and the margin | It stated the contradiction |
| `definition.clockPolicy`, `definition.criterionClocks`, `definition.criteriaWithoutClocks` | New | The policy, and the clock of each criterion |
| `definition.outcomeRules`, the clock rule | Names the policy and both clock reasons | It named the bound alone |
| `exclusionReasons` | `clock-bound-reached` names the margin; `clock-reading-missing` added, ten reasons | The missing-reading rule |
| V2-E05 `definition.reconciliationTiming` | Both instants named as on the host clock; a `clocks` member states that the bound does not apply | It named a collecting and a recording host |
| `fields.experimentIdVersion`, `fields.gitRevision` | Revision 2; prepared from `8a335ce` | A new revision |
| `pinnedInputs`, `inputChanges` | Three pins moved and are classified | The check changed |

No criterion, bound, window, fault, topology, repetition rule, abort condition, cleanup
step, or evidence path changed. No tool checks the new clause of P1: the review of each
run compares it.

## Registry rows and moved pins

A registry row names a path and a content digest only. Each revision 2 names the
revision that it supersedes in `metadata.supersedes`.

| Record | Supersedes | Registered content digest |
|---|---|---|
| `v2-e02a/freeze-r2` | `v2-e02a/freeze-r1`, `adfd9511…1fc` | `edd57be9aca1574d975592f3152c6ad67acfcfd705c4d6478c96a56f5faa4562` |
| `v2-e02b/freeze-r2` | `v2-e02b/freeze-r1`, `27c5934b…6e5` | `be4cc00beaa93fee52eb1625fd6c71a1ff31bade06cd726a9d7958fa44a94e0c` |
| `v2-e02c/freeze-r2` | `v2-e02c/freeze-r1`, `b41a9a69…2353` | `abcf6af5e3d3c050df5b028ac94163c6bda9de5ee1bfe557fe725de87ea3a818` |
| `v2-e05/freeze-r2` | `v2-e05/freeze-r1`, `420255fd…7492` | `f7e1da03503a29ac49de0c6dcaa3536f8640e51d10a53adaf5972821a2d895b2` |

| Moved pin | Material | Reason |
|---|---|---|
| `tools/experiment_preregistration/core.py` | Yes | P1 runs the check, and it now holds the record to its clock policy |
| `tools/experiment_preregistration/__init__.py` | No | It exports the names that the module adds |
| `tools/experiment_preregistration/__main__.py` | No | It states the number of superseded revisions; no rule changes |

No other pin moved. The scope of each record is that of revision 1.

## The checker

Each record is read under its own rule set. The five revision-1 records state none and
are read under rule set 1, the twelve rules that registered them. Every later revision
states `metadata.preregistrationRules`, and a record that states no known rule set of 2
or later is refused, so a revision cannot leave the clock rules by omitting it.
Discovery reads every revision of each experiment: the latest is checked in full, and
each earlier one alone, under its own rule set. A superseded revision is not held to
two clauses that compare it with the present: that its bound record is the latest
committed, and that its qualified release is that of the latest V2-E02B. That is the one
narrowing of a revision-1 check, and it applies only to a superseded revision. A test,
`test_each_revision_one_record_still_passes_under_its_own_rules`, runs the full rule set
1, cross-record rules included, over the five revision-1 records. The cross-record
rules read the latest records. The shared rule holds the four policies equal, and the
clocks of the validity criteria of V2-E02A and V2-E02B alike.

| Rule | Holds |
|---|---|
| `prereg-rule-set-unknown` | Revision 1 states no rule set; every other record states a known one of 2 or later |
| `prereg-clock-inventory` | The two clocks and six sources of rule set 2; each criterion entry names a criterion and two instants with a source and a clock of the inventory, and is cross-clock exactly when the inventory puts its sources on two clocks; each criterion declares clocks or is listed as without clocks; each criterion that names a bound declares the clocks of its interval |
| `prereg-clock-measurement` | P8 reads at the start and at the end and states the formula of revision 1; the policy measures with P8 and states the formula and the computation |
| `prereg-clock-rules` | The offset-stability assumption, the two missing-reading rules, the rule for a verdict that is not judged, and the ordering and bound-comparison rules with the one margin, each word for word |
| `prereg-clock-reasons` | Both clock reasons registered for `INCONCLUSIVE` and named by the outcome rules |
| `prereg-clock-contradiction` | No text states that the difference is not measured, orders instants by a time without naming the margin, names synchronization or a guarantee with no negation, or states that every run is `INCONCLUSIVE`, in the phrases that the check names |

The suite plants each defect in a copy and asserts the exact findings. For the clock
rules: a limitation or a window that states that the difference is not measured; P8
removed, and its end reading removed from P8 and from the policy; each clock reason
removed; outcome rules that name one reason; a one-second ordering threshold; a clock
that the inventory does not hold; a cross-clock entry declared same-clock, the reverse,
and a source moved to the other clock; an inventory that moves the caller to the host
clock; a bound criterion without its clocks; a criterion with no clocks that is not
listed, and a listed one that is unknown or declares clocks; policies of V2-E02A and
V2-E02B that differ, a V2-E05 policy that differs, and validity clocks of V2-E02A and
V2-E02B that differ; the formula without the time between the two host instants, in the
policy and in P8, and the computation without the larger w; wording that claims
synchronization or a guarantee; a rule that makes every run with an unusable end reading
`INCONCLUSIVE`, one in which a decided state does not stand, an end reading with a fixed
state, and an end-reading statement other than that of rule set 2; the offset-stability
assumption removed; each missing-reading rule and each same-clock rule; a record with no
known rule set in five forms; a superseded revision with a rule set; a record of rule set
2 without a policy; fourteen malformed members, six of them a list where a string is
read; ten paraphrases that the scan names; a superseded revision checked against its own
sources; and a later bound record that leaves the superseded revisions alone.

**Known gaps.** The contradiction rule reads phrases, not meaning. A sentence that names
synchronization and holds a negation anywhere is not refused, and neither is a
paraphrase that no phrase names. A test,
`test_a_paraphrase_that_the_scan_does_not_name_is_not_refused`, holds four such gaps.
Run over the five revision-1 records, the rule finds three contradictions in each and
nothing else: the limitation and the window text each state that the difference is not
measured, and the window text states the one-second threshold.

## What stays unchanged

- The five revision-1 records, byte for byte, with their registry rows. A test holds
  each against its registered digest and the literal pins of the freeze suite.
- `q1-1`, `q2-1`, `q3-1` (`REFUSED`), `q1-2`, `q2-2`, `q3-2`, the Q1 revisions 1 and 2,
  the Q2 revisions 1 to 3, the Q3 revisions 1 and 2, and `bounds-r1`, content digest
  `542b05dd9627b25330a4602071d99276218776cf1f78a5c34ac764fbb3188116`. The diff touches
  none of their files, and each of their checks rebuilds them (see below).
- **Why Q2 and Q3 are unaffected.** Each uses one clock. The Q2 interval runs from a
  pod's `creationTimestamp` to the transition of its Ready condition: two Kubernetes
  timestamps, on the node clock, to one second. A gap of Q3 is the difference of two
  completions of the runner pod, on the same clock, to one millisecond. Neither compares
  an instant of the runner or of the cluster with an instant of the host, so no clock
  bound enters S, G, or a bound of `bounds-r1`.
- The E01 freezes and runs, and the Sprint 5 integration freezes, runs, and corrections,
  with their own wording about clocks.
- `tools/reliability_analysis`. Its page and the pages of the timeline, telemetry, and
  operator-event streams each gain one sentence that points to the policy; no tool reads
  the bound.
- The baseline comparison record. It names no freeze record, and both revisions 2 state
  its digest. Its check passed.
- Released V1 history and `v1.0.0`.

## V2-E04

V2-E04 revision 1 stays the latest V2-E04 record and is read under rule set 1. Its clock
statements still contradict its P8. Since this change, `--changes` for it lists the
three files of the check as changed, and no revision classifies them, so its P1 refuses
a run. The later change that supersedes it must register V2-E04 revision 2 under rule
set 2, with this policy word for word, the clock of each instant of its criteria,
including `reversalStart` and `recoveryEnd` of E04-AC12, and the classification of the
moved pins.

## Validation

Run from Git Bash. The first table is of the first commit, `3e02ef5`.

| Check | Command | Result |
|---|---|---|
| Freeze check | `python -m tools.experiment_freeze --check` | `PASSED: 21 freeze record(s), every rule held` |
| Preregistration check | `python -m tools.experiment_preregistration --check` | `PASSED: 5 experiment record(s) and 4 superseded revision(s), every rule held` |
| Changed inputs of each revision 2 | `python -m tools.experiment_freeze --changes RECORD` | Each of the four lists none, exit 0 |
| Changed inputs of each revision 1 | the same, for the five revision-1 records | Each lists the three files of `tools/experiment_preregistration` as changed, exit 1. Revision 2 classifies them for four records; for V2-E04 no revision classifies them yet |
| Consumed records | `python -m tools.environment_qualification --check`, `runtime_startup`, `caller_characterization`, `experiment_bounds`, and `baseline_profile` | Each passed: 2 qualifications, 2 Q2 and 2 Q3 characterizations, 1 bound record, and the comparison each rebuilt as committed |
| Evidence index | `python -m tools.evidence_index --check`, and `--gate` | Both exit 0 |
| Lint and format | `ruff check .`, `ruff format --check .` | All checks passed; 789 files already formatted |
| Types | `mypy tools tests/testing/test_experiment_preregistration.py tests/testing/test_experiment_freeze.py`, and with `--platform linux` | No issues in 190 source files, both |
| Related suites | `python -m pytest` over the preregistration, freeze, bounds, qualification, Q2, Q3, baseline-profile, reliability-analysis, analysis-replay, evidence-index, test-inventory, and document-link suites | Passed after one stale count in the analysis-replay suite was corrected: 21 committed freeze records, and nine of them register exclusion reasons |
| Whitespace | `git diff --check` | Clean |
| Default lane | `python -m pytest -q` | 22,957 passed, 42 skipped, 14 deselected, in 83 min |

The second table is of the second commit, which closes the review findings below.

| Check | Command | Result |
|---|---|---|
| Freeze check | `python -m tools.experiment_freeze --check` | `PASSED: 21 freeze record(s), every rule held` |
| Preregistration check | `python -m tools.experiment_preregistration --check` | `PASSED: 5 experiment record(s) and 4 superseded revision(s), every rule held` |
| Changed inputs | `python -m tools.experiment_freeze --changes RECORD` | Each revision 2 lists none, exit 0. Each revision 1 lists the three files of the check, exit 1 |
| Consumed records and evidence index | the five `--check` commands above, and `evidence_index --check` and `--gate` | Each exit 0 |
| Lint, format, and types | `ruff check .`, `ruff format --check .`, and `mypy` over `tools` and the three changed suites, also with `--platform linux` | All checks passed; 789 files already formatted; no issues in 191 source files, both |
| Whitespace | `git diff --check` | Clean |
| Default lane | `python -m pytest -q` | 22,985 passed, 1 failed, 42 skipped, 14 deselected, in 56 min. The failure was `test_the_page_states_each_limitation_and_each_boundary`: the second commit had reworded a limitation of the analysis page that the test holds word for word. The sentence is restored, with the pointer to the policy after it |
| After that fix | `python -m pytest tests/domain/test_reliability_analysis.py tests/testing/test_document_links.py` | 642 passed. The fix changed that one page alone, and the default lane was not run again |

## Independent review of the first commit

Two independent reviews read the first commit: one of the check and its suite, one of
the records and the pages against the experiment definitions and the repository.
Neither found a critical defect. The second commit corrects every finding below. The
four records were regenerated and registered again before this change merged, so their
registered digests are not those of the first commit.

**What the first commit got wrong, in the check:**

- A malformed record of rule set 2 raised a `TypeError` instead of a finding. A list as a
  source identifier, a criterion identifier, an entry's criterion, an entry's bound, or a
  reason's identifier or result state was used as a key. The check now uses only a
  string as a key, and the suite plants each of the six.
- The contradiction rule matched exact wording. "Was never measured", "has not been
  measured", "four seconds", "one minute", "precedes", and a sentence that named the
  clock bound only to reject it all passed. The rule now reads more phrases, splits
  sentences at a line break, and exempts an ordering sentence only when it names the
  margin. It still reads phrases, and four gaps are held by a test.
- The end-reading rule was checked as a fixed `INCONCLUSIVE` state and a non-empty
  statement. A statement that made every run `INCONCLUSIVE` passed. The end-reading
  statement is now held word for word, it names no state, and the rule for a verdict
  that is not judged decides it. The scan refuses a text that makes every run
  `INCONCLUSIVE`. The same-clock ordering and bound-comparison texts are held word for
  word too.
- Only a criterion that named a bound had to declare its clocks. A record could drop
  every order entry. Each criterion now declares clocks or is listed in
  `definition.criteriaWithoutClocks`.
- The clocks of the validity criteria of V2-E02A and V2-E02B were not compared. They are
  now.
- One string with two matching sentences gave the same finding twice. It now gives it
  once.

**What the first commit got wrong, in the records and the pages:**

- The policy said that it governs each instant, order, and interval of the record. The
  analysis cuts the window, searches the stabilization span, and overlaps readings with
  a span across the two clocks with no margin, and the check of the stable pre-fault
  window does the same. The policy now says that it governs the instants that
  `definition.criterionClocks` declares, and each record has a limitation for the rest.
  E02C-AC10 no longer says that it is compared directly without that qualification.
- This record said that the owner's rule was the one place where revision 2 judges a run
  otherwise than revision 1. That was false: no criterion has a cross-clock bound
  comparison, so that case cannot occur. The four real differences are listed above.
- This record listed the tests in the wording and the lettering of a source outside the
  repository. It now describes them in the repository's own terms.
- The inventory called the collection scripts "collectors", which is the name of the
  in-cluster telemetry component, and did not name the instants that are on no source.
  It now says "collection scripts" and names them.
- The two readings of the formula were not stated, the conservative argument ignored the
  cut to the millisecond, and the measurement did not say that the precedent read the node
  container. Each is stated now.
- E02B-AC11 declared two orders that its verdict does not need: it fails on any
  manual-action event. E05-AC11 declared one. Both criteria are now listed without
  clocks. E05-AC8 did not declare its argo reading, and did not say that it is not judged
  when the operation starts inside the margin. It does now.
- The README pasted a constant that said "this record", and long unwrapped lines. The
  constant now says "each record of rule set 2", and the lines are wrapped.
- The architecture index still said five records and 12 rules. The telemetry and
  operator-event pages kept their "not measured" sentence with no pointer to the policy.
  Both are corrected. The CHANGELOG and the README called a run "a clear FAILED", and
  CONTRIBUTING said that the check refuses each forbidden claim. Both are reworded.
- The validation record did not say that a registry row names no supersession, and did
  not name the one narrowing of a revision-1 check. Both are stated now.

## What this does not establish

- That any experiment passes or fails. No run exists.
- That the offset between the clocks stays inside the bound between the two readings.
  It is an assumption, and no reading tests it.
- That a record means what the policy says. The check reads values and phrases.
- That the analysis orders node and host instants within any margin. It does not.
- That the procedure is executable as written. No driver exists.
- Anything about another provider, node, release, or caller workload.
