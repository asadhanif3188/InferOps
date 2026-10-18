# Validation: one clock policy for the reliability experiment freezes (V2-S6-007-PR1)

Status: **static, C0.** This change registers revision 2 of four freeze records before
any run of the experiments they fix, and adds a rule set to one read-only check. Nothing
ran: no cluster was read or changed, no clock was read, no fault was injected, no commit
was made to `main`, and no caller request was sent. A freeze record is not evidence.

## What the change adds

| Item | Path |
|---|---|
| V2-E02A freeze, revision 2, 226 pins, 11 criterion clock entries | [`docs/proof/experiments/v2-e02a/freeze-r2.v1alpha1.json`](../experiments/v2-e02a/freeze-r2.v1alpha1.json) |
| V2-E02B freeze, revision 2, 226 pins, 17 entries | [`docs/proof/experiments/v2-e02b/freeze-r2.v1alpha1.json`](../experiments/v2-e02b/freeze-r2.v1alpha1.json) |
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
- `definition.limitations` stated three clocks whose difference is not read, and
  `definition.window.clocks` stated the same, with a fixed ordering threshold of one
  second.

The check that registered them, rule set 1, read none of these members, so it passed.

## The clock policy

Each revision 2 states one policy, `definition.clockPolicy`, and the four policies are
equal. [The experiments page](../experiments/README.md#the-clock-policy-of-rule-set-2)
states it in full. In short:

- **Inventory.** Two clocks: the node clock and the host clock. Six sources: the caller
  record and the P8 node instant on the node clock, to 1 ms; the Kubernetes and
  delivery-controller timestamps on the node clock, to 1,000 ms; the collector readings,
  the operator events, and the P8 host instants on the host clock, to 1 ms. The node
  sources share one clock because the provider has one node.
- **Measurement.** P8, as in revision 1: a start reading before the runner starts and an
  end reading after the window ends, each a host instant, a node instant, and a second
  host instant.
- **Bound.** The formula of revision 1, word for word: "the largest of the two
  differences between the node instant and the nearer host instant, plus the time
  between the two host instants". The formula can be read in two ways, so the policy
  states the computation and takes the larger: the larger nearer-difference d of the two
  readings plus the larger host interval w of the two readings. It is conservative
  because the node instant was printed between the two host instants of its reading, so
  the size of the offset at that reading is at most the larger of the two differences,
  and that is at most d plus w.
- **Uncertainty.** The bound is measured at two readings. Its use between them is an
  explicit assumption that the offset stays inside it. Drift is not measured. The result
  page states the net change of the offset, and no verdict reads it. Nothing is
  synchronized or guaranteed.
- **Missing readings.** An unusable start reading: no fault is injected, and the run is
  `REFUSED` for `precondition-not-held`. An unusable end reading: the bound is not
  computable, and each cross-clock order and bound comparison is not judged, for the new
  reason `clock-reading-missing`.
- **A verdict that is not judged.** The state is computed with each such verdict taken as
  held and as failed. When the two agree, that is the state. When they differ, the run is
  `INCONCLUSIVE` for the reason of the verdict. A state that the judged verdicts decide
  stands, so a clear `FAILED` is never made `INCONCLUSIVE`.
- **Ordering and bound comparison.** One margin, the clock bound plus the coarser
  resolution of the two sources. Inside it, no cross-clock order is stated and no
  cross-clock bound comparison is judged, for `clock-bound-reached`. Instants of one clock
  are ordered to their resolution, and an interval of one clock is compared directly.

### One decision of the repository owner

The task stated two rules. An unusable end reading made the run `INCONCLUSIVE` only when
a verdict that is not judged could change its state. A cross-clock interval near a bound
made the run `INCONCLUSIVE` in every case, as revision 1 did. Read together, a run that
another pass criterion had clearly failed would become an exclusion because of one
near-threshold interval. The repository owner chose one rule for both, and for the
ordering rule, before the records were written. This is the one place where revision 2
judges a run otherwise than revision 1 would: such a run is `FAILED` and counted, where
revision 1 made it `INCONCLUSIVE`.

### The clock of each criterion

`definition.criterionClocks` declares the source and the clock of the two instants of
each order and each interval that a criterion states. Of the 57 entries, 23 are
cross-clock.

- **Bound comparisons on one clock.** E02C-AC10, `callerFailureEpisodeMs` against
  20,226 ms, is on the node clock: both ends are caller completions. E05-AC9, the
  restoration against 210,000 ms, is on the host clock: it runs from an operator event to
  a collector reading. The clock bound applies to neither, and an unusable end reading
  leaves both judged. The 10 s of AC2 is on the host clock, and the 60 s of the
  post-recovery window is on the node clock.
- **Cross-clock orders.** A caller completion or `stabilizedAt` against the window, an
  event, or the observation limit; a `deletionTimestamp` against the observation limit;
  a manual-action event against `stabilizedAt` in E02B-AC11; and the controller's
  `operationStartedAt`, to the second, against the `fault-injection-started` event in
  E05-AC8.

## Every member that differs from revision 1

A test, `test_revision_two_differs_from_revision_one_only_in_the_listed_members`, holds
this list for each record.

| Member | Change | Why |
|---|---|---|
| `metadata.revision`, `registeredBy`, `supersedes`, `preregistrationRules` | 2; `V2-S6-007-PR1`; revision 1 by path and digest; rule set 2 | A revision states the one it supersedes and its rule set |
| `definition.limitations` | The clock limitation rewritten to the two-clock inventory and the assumption; one limitation added: no tool checks that a run executes the latest revision | The policy; P1 |
| `definition.history` | One entry added for revision 2 | What was known |
| `definition.preparation` | P1 gains one clause: the record is the latest registered revision of its experiment. P8 keeps its reading and its formula, and names the policy | The task; the policy |
| `definition.window.clocks` | Rewritten to the inventory and the margin | It stated the contradiction |
| `definition.clockPolicy`, `definition.criterionClocks` | New | The policy, and the clock of each criterion |
| `definition.outcomeRules`, the clock rule | Names the policy and both clock reasons | It named the bound alone |
| `exclusionReasons` | `clock-bound-reached` names the margin; `clock-reading-missing` added, ten reasons | The missing-reading rule |
| V2-E05 `definition.reconciliationTiming` | Both instants named as on the host clock; a `clocks` member states that the bound does not apply | It named a collecting and a recording host |
| `fields.experimentIdVersion`, `fields.gitRevision` | Revision 2; prepared from `8a335ce` | A new revision |
| `pinnedInputs`, `inputChanges` | Three pins moved and are classified | The check changed |

No criterion, bound, window, fault, topology, repetition rule, abort condition, cleanup
step, or evidence path changed. No tool checks the new clause of P1: the review of each
run compares it.

## Registry rows and moved pins

| Record | Supersedes | Registered content digest |
|---|---|---|
| `v2-e02a/freeze-r2` | `v2-e02a/freeze-r1`, `adfd9511…1fc` | `5a35408b07d5671732ac8f2e6643c7c61ec6878aeb5200b4c5bd9fdbed61e3d5` |
| `v2-e02b/freeze-r2` | `v2-e02b/freeze-r1`, `27c5934b…6e5` | `ac470a3eb5294c6f3f4b46a99ad71c1e8bbe5f7453bf30bd27a900f344e9d211` |
| `v2-e02c/freeze-r2` | `v2-e02c/freeze-r1`, `b41a9a69…2353` | `58b75d19126cdb2b2d9602c92b8ad387c1c990de3608ccebdac098704758375b` |
| `v2-e05/freeze-r2` | `v2-e05/freeze-r1`, `420255fd…7492` | `b1d20b3fd5a71a835db3aa09f47aed08b529239184250d73489c3228cae8eba0` |

| Moved pin | Material | Reason |
|---|---|---|
| `tools/experiment_preregistration/core.py` | Yes | P1 runs the check, and it now holds the record to its clock policy |
| `tools/experiment_preregistration/__init__.py` | No | It exports the names that the module adds |
| `tools/experiment_preregistration/__main__.py` | No | It states the number of superseded revisions; no rule changes |

No other pin moved. The scope of each record is that of revision 1.

## The checker

Each record is read under its own rule set. The five revision-1 records state none and
are read under rule set 1, the twelve rules that registered them. Every later revision
states `metadata.preregistrationRules`, and a record that states no known rule set of 2 or
later is refused, so a revision cannot leave the clock rules by omitting it. Discovery
reads every revision of each experiment: the latest is checked in full, and each earlier
one alone, under its own rule set, without the two clauses that compare it with the
present. The cross-record rules read the latest records, as before. The shared rule now
holds the four policies equal.

| Rule | Holds |
|---|---|
| `prereg-rule-set-unknown` | Revision 1 states no rule set; every other record states a known one of 2 or later |
| `prereg-clock-inventory` | The two clocks and six sources of rule set 2; each criterion entry names a criterion, two instants with a source and a clock of the inventory, and is cross-clock exactly when the inventory puts its sources on two clocks; each criterion that names a bound declares the clocks of its interval |
| `prereg-clock-measurement` | P8 reads at the start and at the end and states the formula of revision 1; the policy measures with P8 and states the formula and the computation |
| `prereg-clock-rules` | The offset-stability assumption, the two missing-reading rules, the rule for a verdict that is not judged, and the one margin |
| `prereg-clock-reasons` | Both clock reasons registered for `INCONCLUSIVE` and named by the outcome rules |
| `prereg-clock-contradiction` | No text states that the difference is not measured, orders by a fixed time that does not name the clock bound, or names synchronization or a guarantee with no negation |

The tests plant each defect of the task in a copy and assert the exact findings: (a) a
limitation or a window that says the difference is not measured; (b) P8 removed, and its
end reading removed from P8 and from the policy; (c) and (d) each clock reason removed;
(e) a one-second ordering threshold; (f) a clock that the inventory does not hold; (g) a
cross-clock entry declared same-clock, the reverse, and a source moved to the other
clock; (h) E02A and E02B policies that differ, and an E05 policy that differs; (i) the
formula without the time between the two host instants, in the policy and in P8, and the
computation without the larger w; (j) wording that claims synchronization or a
guarantee; (k) a rule that makes every run with an unusable end reading `INCONCLUSIVE`,
and one in which a decided state does not stand; and (l) the offset-stability assumption
removed. Others: outcome rules that name one reason, an inventory that moves the caller
to the host clock, a bound criterion without its clocks, each missing-reading rule, a
record with no known rule set in five forms, a superseded revision with a rule set, a
record of rule set 2 without a policy, eight malformed policy members, a superseded
revision checked against its own sources, and a later bound record that leaves the
superseded revisions alone.

**A known gap.** The contradiction rule reads phrases, not meaning. A sentence that names
synchronization and holds a negation anywhere is not refused, and a test,
`test_a_negation_hides_a_claim_from_the_scan`, holds that gap. Run over the five
revision-1 records, the rule finds exactly the three contradictions above in each and
nothing else.

## What stays unchanged

- The five revision-1 records, byte for byte, with their registry rows. A test holds
  each against its registered digest and the literal pins of the freeze suite, and
  `check_records` over the five passes under rule set 1, cross-record rules included.
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
- `tools/reliability_analysis`. Its page and the timeline page gain one sentence each
  that points to the policy; neither tool reads the bound.
- The baseline comparison record. It names no freeze record, and both revisions 2 state
  its digest. Its check passed.
- Released V1 history and `v1.0.0`.

## V2-E04

V2-E04 revision 1 stays the latest V2-E04 record and is read under rule set 1. Its clock
statements still contradict its P8. Since this change, `--changes` for it lists the
three files of the check as changed, and no revision classifies them, so its P1 refuses
a run. The later change that supersedes it must register V2-E04 revision 2 under rule
set 2, with this policy
word for word, the clock of each instant of its criteria, including `reversalStart` and
`recoveryEnd` of E04-AC12, and the classification of the moved pins.

## Validation

Run from Git Bash on the tree of the first commit. The default-lane row was written
after the lane, and this section is the one file that changed after it.

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

## What this does not establish

- That any experiment passes or fails. No run exists.
- That the offset between the clocks stays inside the bound between the two readings.
  It is an assumption, and no reading tests it.
- That a record means what the policy says. The check reads values and phrases.
- That the procedure is executable as written. No driver exists.
- Anything about another provider, node, release, or caller workload.
