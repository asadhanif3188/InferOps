# Experiment freeze records and runs

Status: **format and check added by `V2-S2-003-PR1`**, with one record: the V2-E01 family
freeze, revision 1. **One run added by `V2-S2-003-PR2`**: E01-A, E01-B, and E01-C, executed
once under that record. **Revision 2 added by `V2-S2-004-PR1`**: it restores the governing
no-duplication criterion and freezes the whole executable path, runner and analysis
included. **One run added by `V2-S2-004-PR2`**: E01-A, E01-B, and E01-C, executed once
under revision 2 from the merged checkout. **One independent review published by
`V2-S2-005-PR1`**: a review of that second run, with one finding about the wording of its
register claim. **One correction and one gate added by `V2-S2-005-PR2`**: the claim's
statement is [narrowed to the frozen criterion](#correction-of-the-second-run-claim-and-the-review-gate-2026-10-03),
and a register change that bears on a run now needs a review artifact of that run.
**Revision 3 added by `V2-S3-004-PR1`**: it [names the environment of E01-D](#revision-3),
the Git desired-state path, and the Argo CD Application, and it changes one clause of
E01-AC10. No part of E01 ran in that change.
**One run added by `V2-S3-004-PR2`**: [E01-D, executed once under revision 3](#the-e01-d-run)
on the environment that revision names, with one completion request. The part PASSED.
The same change makes the committed-run check leave an E01-D run out, which moves one
pinned input of revisions 2 and 3. It also publishes
[one independent review of that run](v2-e01/reviews/20261006-e01-d-1-review-1.md), which found no defect in the verdicts.
That change registered no claim for the result.
**One claim added by `V2-S3-005-PR1`**: [the register claim of the E01-D run](#registration-of-the-e01-d-result-2026-10-07),
at `C2`, bounded to the one run and dated 2026-10-07. No part of E01 ran in that change.
**One schema added by `V2-S5-002-PR1`**: [ExperimentRun v1alpha1](../../contracts/experiment-run.md).
The three run manifests on this page were written before it. Each states its `apiVersion`
and `kind`, and the schema refuses each. They are unchanged, and
[a register](../../contracts/experiment-run.md#compatibility-with-the-manifests-committed-before-the-schema)
names each by path and content digest. No part of E01 ran in that change.
**One layout added by `V2-S5-002-PR2`**: [the experiment evidence layout](../../testing/experiment-evidence-layout.md).
It gives a run directory the place that the three on this page have. Its `repository`
command lists each of the three as `pre-schema` and does not check it. Its `check`
command, given one of them, refuses it at its manifest. They are unchanged. No part
of E01 ran in that change.
**One record added by `V2-S5-006-PR1`**: [the Sprint 5 integration validation](#the-sprint-5-integration-validation),
revision 1, in its own directory, committed before its first attempt. It is not one
of the experiments E01 to E06, and it is not result-bearing. Its first attempt,
`integration-1`, FAILED: no request of the runner reached the API, and three readings
point to the release's network policy as the cause. Revision 2 gives each run its own network policy, and the second attempt,
`integration-2`, PASSED. Both are kept, and they are the first two run directories of
the published [evidence layout](../../testing/experiment-evidence-layout.md) in this
tree.
**One record added by `V2-S6-001-PR1`**: [the Q1 environment qualification](#the-q1-environment-qualification),
revision 1, in its own directory, committed before any qualification. It is a
prerequisite of the V2 reliability experiments and not one of them. Since
`V2-S6-001-PR2` one qualification ran under it, [`q1-1`](v2-q1/runs/q1-1/result.md), and
it is `QUALIFIED`. (Until then this paragraph said that no qualification had run.)
**Two records added by `V2-S6-002-PR1`**: [the Q2 runtime startup characterization](#the-q2-runtime-startup-characterization),
revisions 1 and 2, in their own directory. Revision 1 could not be satisfied and was
superseded before any characterization. One characterization ran under revision 2,
[`q2-1`](v2-q2/runs/q2-1/result.md), and it is `CHARACTERIZED`, with S = 11,000 ms. It
is a prerequisite of the V2 reliability experiments and not one of them. The same change
edits `tools/experiment_evidence` again, which moves the three pins of that package in
the Sprint 5 revision 2 once more.
**One record added by `V2-S6-002-PR2`**: [the Q3 stable caller characterization and the
Q4 bounds](#the-q3-stable-caller-characterization-and-the-q4-bounds), revision 1, in its
own directory, committed before any characterization. It also fixes the four Q4 formulas.
The same change edits `tools/experiment_evidence` once more, so that the layout check
lists a Q3 characterization. One characterization ran under it, [`q3-1`](v2-q3/runs/q3-1/result.md),
and it is `REFUSED`: its capacity reading was not of the environment of `q1-1`. No G was
measured, and no bound record exists.
**Three records added by `V2-S6-004-PR1`**: revision 2 of [the Q1
qualification](#the-q1-environment-qualification), revision 3 of [the Q2
characterization](#the-q2-runtime-startup-characterization), and revision 2 of [the Q3
characterization](#the-q3-stable-caller-characterization-and-the-q4-bounds), each
committed before any run under it. [ADR 0021](../../architecture/decisions/ADR-0021-environment-identity-is-configuration-memory-is-capacity.md) decides that the environment
identity states the configuration and that memory is a capacity fact. The three revisions
hold the next qualification, `q1-2`, and the next Q2 and Q3 characterizations to the
stable identity, and still hold each run to the capacity gate on its own reading.
`q1-1`, `q2-1`, and `q3-1` are built again unchanged under the revisions they name.
**Three runs and one bound record added by `V2-S6-004-PR2`**, and no freeze record: one
run under each of those revisions, once each and in order. [`q1-2`](v2-q1/runs/q1-2/result.md)
is `QUALIFIED`, in the stable environment
`sha256:6a219b3ff959a0020d982d967abeed6696aa0f0d1b594bdf3ad86b9aeda8cd5c`;
[`q2-2`](v2-q2/runs/q2-2/result.md) is `CHARACTERIZED` with S = 11,000 ms; and
[`q3-2`](v2-q3/runs/q3-2/result.md) is `CHARACTERIZED` with G = 10,113 ms. The Q4 tool
built [`v2-q4/bounds-r1.v1alpha1.json`](v2-q4/bounds-r1.v1alpha1.json) from `q2-2` and
`q3-2` ([see below](#the-committed-bound-record)). These are qualifications and
experiment bounds, not results of a reliability experiment. (Until `V2-S6-004-PR2` this
paragraph said that no run existed under any of the three revisions.)
**Five records added by `V2-S6-003-PR1`**: [the reliability experiment
freezes](#the-reliability-experiment-freezes) of V2-E02A, V2-E02B, V2-E02C, V2-E04, and
V2-E05, revision 1 each, in their own directories, committed before any run. Each names
`q1-2` and `bounds-r1`, and [`tools/experiment_preregistration`](../../../tools/experiment_preregistration/core.py)
holds each to them and to the others. No run of any of them exists, and nothing ran in
that change.
**Four records added by `V2-S6-007-PR1`**: revision 2 of the records of V2-E02A, V2-E02B,
V2-E02C, and V2-E05, which supersede revision 1 with [one clock
policy](#the-clock-policy-of-rule-set-2). Revision 1 of each is kept unchanged, and V2-E04
stayed at revision 1 in that change. No run exists, and nothing ran in that change.
**One record added by `V2-S6-005-PR1`**: revision 2 of the record of V2-E04, under rule
set 3, which supersedes revision 1 with the same clock policy and [the reversal timing as
the repository owner amended it](#the-reversal-timing-of-v2-e04-and-rule-set-3). Revision
1 is kept unchanged. No run exists, and nothing ran in that change.
**Two records added by `V2-S6-006-PR1`**: revision 1 of [the analysis experiment
freezes](#the-analysis-experiment-freezes) of V2-E03 and V2-E06, in their own directories,
committed before any run of an experiment whose runs they read. Each binds the latest
records of its sources by digest, and [`tools/analysis_preregistration`](../../../tools/analysis_preregistration/core.py)
holds each to them. No source run and no figure of either exists, the code that computes
either analysis in full does not exist, and nothing ran in that change.
**Two records added by `V2-S6-008-PR1`**: revision 3 of the record of V2-E04, under rule
set 4, which supersedes revision 2 and [selects the span of its recovery criterion with no
onset exclusion](#the-selection-of-the-span-of-v2-e04-and-rule-set-4), and revision 2 of
the record of V2-E03, which supersedes revision 1 and binds revision 3. Revision 2 of
V2-E04 and revision 1 of V2-E03 are kept unchanged. No run exists, and nothing ran in that
change.
A freeze record fixes an experiment family before its first
result-bearing run. A record is not evidence: it says what a run must do and what counts as
a pass. A run is evidence, and it is kept whatever its outcome.

| Experiment | Revision | Record | Parts and intended level | State |
|---|---|---|---|---|
| V2-E01, contract-to-deployment determinism | 1 | [`v2-e01/freeze-r1.v1alpha1.json`](v2-e01/freeze-r1.v1alpha1.json) | E01-A, E01-B, E01-C at C0; E01-D at C2 | Superseded by revision 2 on 2026-10-03, and kept unchanged. E01-A, E01-B, and E01-C ran once under it, in [`20261002-e01-abc-1`](v2-e01/runs/20261002-e01-abc-1/result.md), and each PASSED under its criteria. That run carries an [audit limitation](#audit-of-the-first-run-2026-10-03) |
| V2-E01, contract-to-deployment determinism | 2 | [`v2-e01/freeze-r2.v1alpha1.json`](v2-e01/freeze-r2.v1alpha1.json) | E01-A, E01-B, E01-C at C0; E01-D at C2 | Frozen. E01-A, E01-B, and E01-C ran once under it, in [`20261003-e01-abc-1`](v2-e01/runs/20261003-e01-abc-1/result.md), and each PASSED under its criteria. Superseded by revision 3 on 2026-10-06, and kept unchanged. Its E01-D environment identity is pending |
| V2-E01, contract-to-deployment determinism | 3 | [`v2-e01/freeze-r3.v1alpha1.json`](v2-e01/freeze-r3.v1alpha1.json) | E01-A, E01-B, E01-C at C0; E01-D at C2 | Frozen. It names the E01-D environment. E01-D ran once under it, in [`20261006-e01-d-1`](v2-e01/runs/20261006-e01-d-1/result.md), and PASSED under its criteria. No static part ran under it. Since that run, one pinned input differs from its pin: [the runner's committed-run listing](#the-e01-d-run) |
| Sprint 5 integration validation, `s5-integration-validation` | 1 | [`v2-s5-integration/freeze-r1.v1alpha1.json`](v2-s5-integration/freeze-r1.v1alpha1.json) | One part, S5I, at C2 | Frozen before its first attempt. Not result-bearing: [see below](#the-sprint-5-integration-validation). One attempt ran under it, [`integration-1`](v2-s5-integration/runs/integration-1/result.md), and FAILED on S5I-AC2. Superseded by revision 2 on 2026-10-14, and kept unchanged. Seven pinned inputs differ from its pins: the four that revision 2 classifies, and the three files of `tools/experiment_evidence`, which `V2-S6-001-PR2` edited |
| Sprint 5 integration validation, `s5-integration-validation` | 2 | [`v2-s5-integration/freeze-r2.v1alpha1.json`](v2-s5-integration/freeze-r2.v1alpha1.json) | One part, S5I, at C2 | Frozen. A run brings its own network policy. One attempt ran under it, [`integration-2`](v2-s5-integration/runs/integration-2/result.md), and PASSED under its criteria. Since `V2-S6-001-PR2`, three pinned inputs differ from their pins: the three files of `tools/experiment_evidence`, which that change edited after both attempts so that the layout check lists a Q1 qualification. A later attempt needs a revision that classifies them |
| Q2 runtime startup characterization, `v2-q2-runtime-startup-characterization` | 1 | [`v2-q2/freeze-r1.v1alpha1.json`](v2-q2/freeze-r1.v1alpha1.json) | One part, Q2, at C2 | Superseded by revision 2 before any characterization, and kept unchanged: its precondition on the API image digest could not hold. No characterization ran under it |
| Q2 runtime startup characterization, `v2-q2-runtime-startup-characterization` | 2 | [`v2-q2/freeze-r2.v1alpha1.json`](v2-q2/freeze-r2.v1alpha1.json) | One part, Q2, at C2 | Frozen before any characterization. One characterization ran under it, [`q2-1`](v2-q2/runs/q2-1/result.md), `CHARACTERIZED`, S = 11,000 ms. Not result-bearing: [see below](#the-q2-runtime-startup-characterization). Superseded by revision 3 on 2026-10-17, and kept unchanged. Six pinned inputs differ from its pins, which revision 3 classifies |
| Q2 runtime startup characterization, `v2-q2-runtime-startup-characterization` | 3 | [`v2-q2/freeze-r3.v1alpha1.json`](v2-q2/freeze-r3.v1alpha1.json) | One part, Q2, at C2 | Frozen before any characterization. It holds a characterization to `q1-2` and to the stable environment identity. Since `V2-S6-004-PR2`, one characterization ran under it, [`q2-2`](v2-q2/runs/q2-2/result.md), `CHARACTERIZED`, S = 11,000 ms. (Until `V2-S6-004-PR2` this cell said that no characterization ran under it.) |
| Q3 stable caller characterization, `v2-q3-stable-caller-characterization` | 1 | [`v2-q3/freeze-r1.v1alpha1.json`](v2-q3/freeze-r1.v1alpha1.json) | One part, Q3, at C2 | Frozen before any characterization. It fixes the rule of G and the four Q4 formulas. Not result-bearing: [see below](#the-q3-stable-caller-characterization-and-the-q4-bounds). One characterization ran under it, [`q3-1`](v2-q3/runs/q3-1/result.md), `REFUSED` on the environment; no caller ran, no G, no bound record. Superseded by revision 2 on 2026-10-17, and kept unchanged. Nine pinned inputs differ from its pins, which revision 2 classifies |
| Q3 stable caller characterization, `v2-q3-stable-caller-characterization` | 2 | [`v2-q3/freeze-r2.v1alpha1.json`](v2-q3/freeze-r2.v1alpha1.json) | One part, Q3, at C2 | Frozen before any characterization. It holds a characterization to `q1-2` and to the stable environment identity, and keeps the rule of G and the four Q4 formulas. Since `V2-S6-004-PR2`, one characterization ran under it, [`q3-2`](v2-q3/runs/q3-2/result.md), `CHARACTERIZED`, G = 10,113 ms, and the bound record [`v2-q4/bounds-r1.v1alpha1.json`](v2-q4/bounds-r1.v1alpha1.json) exists. (Until `V2-S6-004-PR2` this cell said that no characterization ran under it and that no bound record exists.) |
| Q1 environment and identity qualification, `v2-q1-environment-qualification` | 1 | [`v2-q1/freeze-r1.v1alpha1.json`](v2-q1/freeze-r1.v1alpha1.json) | One part, Q1, at C2 | Frozen before any qualification. Not result-bearing: [see below](#the-q1-environment-qualification). Since `V2-S6-001-PR2`, one qualification ran under it, [`q1-1`](v2-q1/runs/q1-1/result.md), and it is `QUALIFIED`. (Until then this row said that no qualification ran under it.) Superseded by revision 2 on 2026-10-17, and kept unchanged. Three pinned inputs differ from its pins, which revision 2 classifies. (Until then this row said that no pinned input differs from its pin.) |
| Q1 environment and identity qualification, `v2-q1-environment-qualification` | 2 | [`v2-q1/freeze-r2.v1alpha1.json`](v2-q1/freeze-r2.v1alpha1.json) | One part, Q1, at C2 | Frozen before any qualification under it. Its records state the stable environment identity, which holds no memory figure. The seventeen criteria are those of revision 1. Since `V2-S6-004-PR2`, one qualification ran under it, [`q1-2`](v2-q1/runs/q1-2/result.md), and it is `QUALIFIED`; the next identifier is `q1-3`. (Until `V2-S6-004-PR2` this cell said that no qualification ran under it and that the next identifier is `q1-2`.) |
| V2-E02A, controlled single-runtime baseline | 1 | [`v2-e02a/freeze-r1.v1alpha1.json`](v2-e02a/freeze-r1.v1alpha1.json) | One part, E02A, at C2 | Frozen before any run. No run exists. Superseded by revision 2 on 2026-10-18, and kept unchanged: its clock statements contradicted its P8. The three files of `tools/experiment_preregistration` differ from its pins, and revision 2 classifies them. (Until `V2-S6-007-PR1` this cell said only that it was frozen before any run and that no run exists.) [See below](#the-reliability-experiment-freezes) |
| V2-E02B, multi-runtime pod loss | 1 | [`v2-e02b/freeze-r1.v1alpha1.json`](v2-e02b/freeze-r1.v1alpha1.json) | One part, E02B, at C2 | Frozen before any run. No run exists. Superseded by revision 2 on 2026-10-18, and kept unchanged: its clock statements contradicted its P8. The three files of `tools/experiment_preregistration` differ from its pins, and revision 2 classifies them. (Until `V2-S6-007-PR1` this cell said only that it was frozen before any run and that no run exists.) [See below](#the-reliability-experiment-freezes) |
| V2-E02C, API pod loss | 1 | [`v2-e02c/freeze-r1.v1alpha1.json`](v2-e02c/freeze-r1.v1alpha1.json) | One part, E02C, at C2 | Frozen before any run. No run exists. Superseded by revision 2 on 2026-10-18, and kept unchanged: its clock statements contradicted its P8. The three files of `tools/experiment_preregistration` differ from its pins, and revision 2 classifies them. (Until `V2-S6-007-PR1` this cell said only that it was frozen before any run and that no run exists.) [See below](#the-reliability-experiment-freezes) |
| V2-E04, bad release and Git reversal | 1 | [`v2-e04/freeze-r1.v1alpha1.json`](v2-e04/freeze-r1.v1alpha1.json) | One part, E04, at C2 | Frozen before any run. No run exists. Superseded by revision 2 on 2026-10-19, and kept unchanged: its clock statements contradicted its P8, and its recovery interval started at a controller observation and counted the discovery of the reversal as operator time. The three files of `tools/experiment_preregistration` differ from its pins, and revision 2 classifies them. (Until `V2-S6-005-PR1` this cell said that it is the latest V2-E04 record and that no revision classifies the three files.) [See below](#the-reversal-timing-of-v2-e04-and-rule-set-3) |
| V2-E05, drift reconciliation | 1 | [`v2-e05/freeze-r1.v1alpha1.json`](v2-e05/freeze-r1.v1alpha1.json) | One part, E05, at C2 | Frozen before any run. No run exists. Superseded by revision 2 on 2026-10-18, and kept unchanged: its clock statements contradicted its P8. The three files of `tools/experiment_preregistration` differ from its pins, and revision 2 classifies them. (Until `V2-S6-007-PR1` this cell said only that it was frozen before any run and that no run exists.) [See below](#the-reliability-experiment-freezes) |
| V2-E02A, controlled single-runtime baseline | 2 | [`v2-e02a/freeze-r2.v1alpha1.json`](v2-e02a/freeze-r2.v1alpha1.json) | One part, E02A, at C2 | Frozen before any run, under rule set 2. It supersedes revision 1 with one clock policy and changes no criterion, bound, window, fault, or repetition rule. No run exists. Since `V2-S6-005-PR1`, `core.py` of `tools/experiment_preregistration` differs from its pin and no revision classifies it, so a run refuses to start until a later revision classifies it. (Until `V2-S6-005-PR1` this cell ended "No run exists.") [See below](#the-clock-policy-of-rule-set-2) |
| V2-E02B, multi-runtime pod loss | 2 | [`v2-e02b/freeze-r2.v1alpha1.json`](v2-e02b/freeze-r2.v1alpha1.json) | One part, E02B, at C2 | Frozen before any run, under rule set 2. It supersedes revision 1 with one clock policy and changes no criterion, bound, window, fault, or repetition rule. No run exists. Since `V2-S6-005-PR1`, `core.py` of `tools/experiment_preregistration` differs from its pin and no revision classifies it, so a run refuses to start until a later revision classifies it. (Until `V2-S6-005-PR1` this cell ended "No run exists.") [See below](#the-clock-policy-of-rule-set-2) |
| V2-E02C, API pod loss | 2 | [`v2-e02c/freeze-r2.v1alpha1.json`](v2-e02c/freeze-r2.v1alpha1.json) | One part, E02C, at C2 | Frozen before any run, under rule set 2. It supersedes revision 1 with one clock policy and changes no criterion, bound, window, fault, or repetition rule. No run exists. Since `V2-S6-005-PR1`, `core.py` of `tools/experiment_preregistration` differs from its pin and no revision classifies it, so a run refuses to start until a later revision classifies it. (Until `V2-S6-005-PR1` this cell ended "No run exists.") [See below](#the-clock-policy-of-rule-set-2) |
| V2-E04, bad release and Git reversal | 2 | [`v2-e04/freeze-r2.v1alpha1.json`](v2-e04/freeze-r2.v1alpha1.json) | One part, E04, at C2 | Frozen before any run, under rule set 3. It supersedes revision 1 with the clock policy of rule set 2 and the reversal timing as the repository owner amended it: E04-AC12 judges the recovery from Git visibility to the onset of the stabilization span against the unchanged 52,000 ms, and E04-AC8 ends its window when the desired state is restored. No run exists. Superseded by revision 3 on 2026-10-20, and kept unchanged: its reason `recovery-onset-not-after-reversal` is not authorized by the amended definition. Since `V2-S6-008-PR1`, `core.py` of `tools/experiment_preregistration` differs from its pin, and revision 3 classifies it. (Until `V2-S6-008-PR1` this cell ended "No run exists.") [See below](#the-reversal-timing-of-v2-e04-and-rule-set-3) |
| V2-E04, bad release and Git reversal | 3 | [`v2-e04/freeze-r3.v1alpha1.json`](v2-e04/freeze-r3.v1alpha1.json) | One part, E04, at C2 | Frozen before any run, under rule set 4. It supersedes revision 2: it removes the reason `recovery-onset-not-after-reversal` and selects the span of E04-AC12, the first span that starts after `reversalStart` and then completes inside the observation limit, by one preregistered rule, and it pins the outcome reference `tools/reversal_outcome`. A valid run with no such span is `FAILED`. The bound, the reversal-start definition, the window of E04-AC8, the observation limit, and the clock policy are those of revision 2. No run exists. [See below](#the-selection-of-the-span-of-v2-e04-and-rule-set-4) |
| V2-E05, drift reconciliation | 2 | [`v2-e05/freeze-r2.v1alpha1.json`](v2-e05/freeze-r2.v1alpha1.json) | One part, E05, at C2 | Frozen before any run, under rule set 2. It supersedes revision 1 with one clock policy and changes no criterion, bound, window, fault, or repetition rule. No run exists. Since `V2-S6-005-PR1`, `core.py` of `tools/experiment_preregistration` differs from its pin and no revision classifies it, so a run refuses to start until a later revision classifies it. (Until `V2-S6-005-PR1` this cell ended "No run exists.") [See below](#the-clock-policy-of-rule-set-2) |
| V2-E03, signal truthfulness | 1 | [`v2-e03/freeze-r1.v1alpha1.json`](v2-e03/freeze-r1.v1alpha1.json) | One part, E03, at C2, derived from the C2 runs of its sources | Frozen before any run of its sources. It binds revision 2 of V2-E02A, V2-E02B, and V2-E02C, the initial population, and of V2-E04, the extension, and excludes V2-E05 by a stated rule. No figure exists, and the code that computes the analysis in full does not exist. Superseded by revision 2 on 2026-10-20, and kept unchanged: its V2-E04 binding is superseded. Since `V2-S6-008-PR1`, revision 3 of V2-E04 and the two checks differ from its pins, and revision 2 classifies them. (Until `V2-S6-008-PR1` this cell ended "does not exist.") [See below](#the-analysis-experiment-freezes) |
| V2-E03, signal truthfulness | 2 | [`v2-e03/freeze-r2.v1alpha1.json`](v2-e03/freeze-r2.v1alpha1.json) | One part, E03, at C2, derived from the C2 runs of its sources | Frozen before any run of its sources. It binds revision 3 of V2-E04 by path, revision, digest, and rule set, counts in its extension only the runs that execute under it, keeps the three other bindings of revision 1, and lists each member that differs from revision 1. No figure exists. [See below](#the-analysis-experiment-freezes) |
| V2-E06, reliability resource and cost overhead | 1 | [`v2-e06/freeze-r1.v1alpha1.json`](v2-e06/freeze-r1.v1alpha1.json) | One part, E06, at C2: C0 for the allocation arithmetic and C2 for the figures read from runs | Frozen before any run of its sources. It binds revision 2 of V2-E02A and V2-E02B. The cost basis is local, and no cloud provider is used. Since `V2-S6-008-PR1`, `core.py` of `tools/analysis_preregistration` and of `tools/experiment_preregistration` differ from its pins and no revision classifies them, so an analysis refuses to start until a later revision does. No figure and no code that computes one exists. [See below](#the-analysis-experiment-freezes) |

## Why a freeze comes first

A result is only as good as the method it was measured against. If the procedure, the
inputs, or the pass condition can change after a result is seen, the result is a search for
a number. So every field a run depends on is written down and committed before the first
result-bearing run, and a run uses the merged record. A later change to what the record
fixes is a new revision, never an edit.

## The fields

A record answers 13 fields, in `fields`. Each field is a list of entries, and the entries of
one field together cover every part of the experiment exactly once. A field with no entry is
refused. It is never read as "not applicable".

| Field | Meaning |
|---|---|
| `experimentIdVersion` | The experiment's identifier and version. |
| `gitRevision` | The Git revision, or the pinned inputs, the run must use. |
| `environmentIdentity` | The environment the run executes in. |
| `callerProfileRevision` | The revision of the caller profile selected. |
| `topology` | What is deployed, and how many of each. |
| `fault` | The fault the run injects. |
| `repetitionCount` | How many result-bearing runs, and of what. |
| `acceptanceCriteria` | What must hold for the run to pass. |
| `derivedNumericBounds` | The numeric bounds derived from runtime-startup and stable-caller qualification. |
| `evidencePaths` | Where the run's evidence is written. |
| `abortConditions` | The conditions that stop a run that has started. |
| `cleanupProcedure` | How the run is cleaned up afterwards. |
| `intendedEvidenceLevel` | The evidence level the run aims at, under [InferOps Evidence Levels](../../testing/evidence-levels.md). |

**How an entry answers.** Every entry names its `parts` and has one `status`:

- `value`, with a `value` that is not empty: not an empty string, list, or object, not
  `null`, and not a string that is exactly a stand-in - `TBD`, `TODO`, `N/A`, `unknown`,
  `pending`, `.`, and the others the check lists - or exactly a `<...>` placeholder. A
  stand-in inside a longer string is not detected. An intended evidence level is one of
  `C0` to `C4`, and every acceptance criterion has an `id` and a `statement`, with no `id`
  used twice in a record.
- `not-applicable`, with a `reason`, for a part that has no counterpart to the field. E01
  injects no fault, so its `fault` is not applicable, with the reason. Only five fields can
  lack a counterpart: `environmentIdentity`, `callerProfileRevision`, `topology`, `fault`,
  and `derivedNumericBounds`. The other eight are ones every run has, and
  `not-applicable` is refused for them.
- `pending`, with a `reason` and an `owner`, only where an allowance in
  [`tools/experiment_freeze`](../../../tools/experiment_freeze/core.py) names the
  experiment, the field, and the part. One allowance exists: E01-D's
  `environmentIdentity`, owned by `V2-S3-004-PR1`, the change that will name E01-D's real
  environment. A part with a pending field cannot run. Revision 3 answers that field with a
value, and no field of it is pending. The allowance stays in the checker, which revision 3
pins and which was not edited, so a test, not the checker, holds that revision 3 uses none.

An entry may add a `note`, which must not be empty. Beside the fields, a record states its
definition, its parts with their inputs and procedures, and its pinned inputs.

## Pinned inputs

A record cannot name the commit that merges it. So it pins every file on the experiment
path in `pinnedInputs`, with a role and a **content digest**: the SHA-256 of the file's bytes
with every CRLF replaced by LF, which is what Git stores for a text file under this
repository's attributes. A Windows checkout and a Linux one give the same digest. The run
records the merged commit it executes, and checks the pins at that commit before it starts.

```sh
# List every material file that differs from the record. Exit 1 if any does.
uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json
```

**The material scope** (from revision 2). A pin list can only say whether the files it
names changed. It cannot see a file nobody listed - the gap the first E01 run fell through:
its runner was not pinned, so the change check reported nothing. So a record now declares
`materialScope`: the entry modules of the run, the package roots they resolve in, and the
data files and patterns the parts read. The experiment path is the **static import
closure** of the entry modules within those roots - every product module, the runner, the
analysis, the freeze checker, and every local helper they import - plus the data files.
`--changes` computes that set from the tree and lists four kinds of difference:

| Kind | Meaning |
|---|---|
| `changed` | Pinned, present, with other content |
| `absent` | Pinned and missing |
| `added` | In the scope and not pinned: a new file, or a new local helper an import now reaches |
| `unscoped` | Pinned, present, and no longer in the scope |

The closure follows `import` statements, wherever they are, and matches each module name
against its directory's listing, so a name in the wrong case resolves to nothing on Windows
as on Linux. It does not see a module loaded by a name built at run time, so a run also
records every module file it and its second process loaded from the record's package
directories - `src/inferops/` and `tools/` - and aborts when one is not a pinned input with
its pinned content, or when the second process imported the runner or the package from
outside the checkout. Third-party packages, including those in a `.venv/` inside the
checkout, are outside those directories: `uv.lock` pins them by version, not by content.
`--check` recomputes these conditions from what a revision-2 run recorded. `exclusions` may remove a file from
the scope, each with a reason, inside the frozen record; revision 2 excludes nothing.
Revision 1 has no scope and is checked against its own pins, as it was registered.

## Revisions

The registry, [`registry.v1alpha1.json`](registry.v1alpha1.json), pins the content digest of
every committed record. A record whose content differs from its pin is refused, and so is
a record nobody pinned. Until 2026-10-03 the pins were a constant, `FROZEN_RECORDS`, in the
checker's own code. A record that pins the checker - as revision 2 does, because the run
calls it - could then never be registered: adding the record's pin changes the checker,
which moves the record's pin of it. The registry is data, so the cycle is gone. A record
does not pin the registry, and says so; a run records the registry's digest beside the
record's. No record names the commit that merges it: the run records the commit it
executes. To change what a record fixes, add `freeze-r<N+1>.v1alpha1.json` beside it:

- `metadata.supersedes` names the previous revision's path and content digest;
- `inputChanges` classifies every pinned input whose digest moved since that revision, added
  or removed ones included, with `material` true or false and a `reason`;
- every freeze field is answered again, in full.

A revision is pinned when it is added, like the first.

## The check

```sh
uv run --locked python -m tools.experiment_freeze --check
```

It exits 0 when every committed record holds every rule, and 1 when one does not. The
default-lane suite [`tests/testing/test_experiment_freeze.py`](../../../tests/testing/test_experiment_freeze.py)
runs it, and plants each defect below in a copy.

| Rule | Statement |
|---|---|
| `freeze-record-unreadable` | A freeze record is a JSON object. |
| `freeze-record-shape` | A freeze record declares its version and kind, its metadata, and its parts. |
| `freeze-field-missing` | A freeze record carries every freeze field. |
| `freeze-field-unknown` | A freeze record carries no field the procedure does not name. |
| `freeze-field-parts` | The entries of one field cover every part of the experiment exactly once. |
| `freeze-field-status-unknown` | An entry is a value, not-applicable, or pending. |
| `freeze-field-empty` | A value is not empty, and is not a placeholder. |
| `freeze-field-reason-missing` | A not-applicable or pending entry states its reason. |
| `freeze-field-pending-not-allowed` | Only an allowed field of an allowed part is pending, and it names its owner. |
| `freeze-field-always-answered` | A field every run has is never answered not-applicable. |
| `freeze-criteria-malformed` | Every acceptance criterion has an identifier and a statement, and no identifier is used twice in a record. |
| `freeze-evidence-level-unknown` | An intended evidence level is one of the project's evidence levels. |
| `freeze-pinned-input-malformed` | Every pinned input names one repository path once, with a content digest. |
| `freeze-scope-missing` | Every record declares a material scope, except a record registered before scopes existed. |
| `freeze-scope-malformed` | A material scope names its entry modules, the package roots they resolve in, and its data paths, and every exclusion names a path and a reason. |
| `freeze-registry-unreadable` | The freeze registry is a JSON object that pins records by path and content digest, each path once. |
| `freeze-record-unregistered` | Every committed freeze record is pinned. |
| `freeze-record-missing` | Every pinned freeze record is committed. |
| `freeze-record-edited` | A committed freeze record is what was pinned. |
| `freeze-revision-sequence` | An experiment's revisions are numbered from 1 without a gap, as their files are. |
| `freeze-revision-supersedes` | Revision 1 supersedes nothing; a later revision names the one before it and its content digest. |
| `freeze-input-change-unclassified` | A revision classifies every pinned input that changed, appeared, or disappeared since the revision it supersedes. |

## What is enforced, and what is not

Enforced in the default lane: every rule above, over every committed record.

Not enforced:

- **A change to a pinned input merges freely.** No test compares the pins with today's
  files. A change to the experiment path does not need a freeze revision to merge. The run
  that follows does: its first precondition is that every pin holds, or that a merged
  revision classifies the change, and `--changes` lists what moved.
- **No test asserts that today's code passes.** The E01 suite executes the static parts
  end to end in a temporary repository on every default lane, and asserts only that the
  judge agrees with what the runner recorded, never that a part PASSED. A result-bearing
  run is one a contributor names with `--run`, recorded under `runs/`.
- **A run's refusal to start, for E01-D.** The E01 runner refuses to start E01-A, E01-B, and
  E01-C when a precondition fails, and it never runs E01-D. No runner for E01-D exists, so
  "a part with a pending field cannot run" is, for E01-D, a procedure that a run follows
  and no code enforces. The one E01-D run followed it under revision 3, which leaves no
  field pending.
- **That a pinned file exists.** A pin is checked for its shape, not against the working
  tree. A file deleted after a record merged is reported by `--changes`, not refused by
  `--check`: refusing it would make a merged record fail the build for a later, legitimate
  change.
- **Whether the content is right.** The check says every field is answered. It does not
  judge an answer, and it does not check that a revision a record names is a commit.
- **That the registry is append-only.** A change can edit a record and its registry pin
  together. The test suite writes each registered pin out literally, so such an edit
  shows in review as a changed test; nothing else refuses it.
- **That a scope is complete when it merges.** `--check` reads the record, not the tree, so
  it does not compare the scope with the files. `--changes` does, and the run refuses to
  start on any difference. At registration, revision 2's `--changes` reported none, and the
  run under it recorded none.
- **The rule against previews.** Revision 2 forbids a full execution of the parts outside
  `--run`, in any repository. No code can see a run in a throwaway repository, so this is a
  procedure the record states and nothing enforces.

The E01 record pins `uv.lock` and `pyproject.toml`, because the parsers and their
dependencies are on the experiment path. So any dependency update is listed by
`--changes`, and the next E01 run needs a revision that classifies it.

## The V2-E01 freeze

[`v2-e01/freeze-r1.v1alpha1.json`](v2-e01/freeze-r1.v1alpha1.json) freezes the V2-E01 family,
contract-to-deployment determinism, in four parts:

- **E01-A, deterministic double render (C0).** Two renders of the reference inputs, in two
  processes, compared byte for byte, with the release's provenance checked against digests
  computed apart from it, and the no-hand-written-intent criterion checked statically.
- **E01-B, intent mutation (C0).** The contract's replica count changed from 1 to 2, and
  only `runtime.replicaCount`, the contract digest, the values digest, and the release
  identifier may move.
- **E01-C, negative cases (C0).** Six cases, each run twice: schema-invalid,
  semantic-invalid, two ownership conflicts, an unsupported profile, and an unsupported
  capability, each with its expected refusal.
- **E01-D, real deployment (C2).** The release rendered from the unmodified contract,
  accepted into Git, reconciled by Argo CD, and serving one real completion. Its procedure
  and criteria are frozen. In revisions 1 and 2 its environment identity is pending, so
  it could not run until a merged revision named the environment. Revision 3 names it,
  and [E01-D ran once under revision 3](#the-e01-d-run).

The record states every procedure, criterion, and limitation in full. It pins 67 inputs: the
contract, the binding, the chart and its defaults, the compatibility matrix, the renderer's
39 source files, the hand-written values, the V1 values, the negative-case contract, the V1
synchronous compatibility record, the defaults reader, and the dependency lock and project
metadata.

### Revision 2

[`v2-e01/freeze-r2.v1alpha1.json`](v2-e01/freeze-r2.v1alpha1.json), registered by
`V2-S2-004-PR1` on 2026-10-03, supersedes revision 1. The first Sprint 2 collective review
found two defects in revision 1, and revision 2 corrects both without editing it:

- **The criterion is the governing one again.** Revision 1's hypothesis, E01-AC5, and
  E01-AC10 excepted two hand-written strings that repeated the contract's model pins. The
  renderer now derives both, so revision 2 states the criterion without the exception:
  no claim-relevant workload intent is written by hand after rendering, and no hand-written
  string contains a contract-owned generated value of eight characters or more. E01-C gains
  a seventh case: a hand-written download URL that contradicts the pins, refused.
- **The executable path is frozen.** Revision 2 declares its material scope and pins 74
  inputs: the 39 product files and the data files revision 1 pinned, the runner and
  analysis, the freeze checker, and the packages they belong to. `inputChanges` classifies
  every difference from revision 1: four changed files, from the renderer correction, and
  seven added ones, the runner and checker files revision 1 never pinned.

It also states, before any run under it: the run's preconditions, which now include that the
runner and the `inferops` package are imported from the checked-out tree and that the record
is registered; the executions that are not result evidence; the rule against previews; how
the record avoids pinning itself; and, in `history`, the first run's audit limitation and
what is and is not available of the earlier previews. E01-D's environment identity stays
pending, with the same owner.

### Revision 3

[`v2-e01/freeze-r3.v1alpha1.json`](v2-e01/freeze-r3.v1alpha1.json), registered by
`V2-S3-004-PR1` on 2026-10-06, supersedes revision 2. Revision 2 left the environment
identity of E01-D pending. Revision 3 answers it, and no field of it is pending. Revisions 1
and 2 are unchanged.

**No part of E01 ran in this change.** Nothing was deployed, Argo CD synchronized
nothing, and no completion was sent. The environment was read with read-only requests on
2026-10-06. A freeze record is not evidence.

- **The environment.** One provider, `docker-desktop`: one cluster at Kubernetes v1.36.1
  with one node, the default storage class `standard`, Argo CD v3.5.3 from the pinned
  install manifest, the runtime image by digest, and the model by repository, revision,
  file, and SHA-256. The API image digest is not in Git: the run builds the image and
  records the digest. When the environment was read, Argo CD, the platform namespace, and
  the model cache claim were absent. The preparation steps create them.
- **The Git and Argo CD path.** The release is the one committed at
  `gitops/environments/local-docker-desktop/workloads/support-assistant/`, derived from the
  reference contract and the `local-docker-desktop` binding. The Application is
  `local-docker-desktop-support-assistant`, in the project `inferops-workloads`, and it
  follows `main`. The run commits no release: it derives the release again at the
  executing commit and compares the bytes.
- **The steps and the rules.** Seven preparation steps and six run steps, each with its
  commands, and for each E01-D criterion the comparisons that judge it. One request is
  sent, with no retry. A preparation step that fails ends the run before the Application
  is applied. A release that is not ready 600 seconds after Argo CD reported the sync
  makes the part FAILED. The record separates the identity attributes that the run reads
  before it prepares anything from the ones a preparation step establishes, and names
  the step that verifies each.
- **One criterion clause changed.** Revision 2's E01-AC10 said that the release is
  installed "from the generated values file and one hand-written values file only, with no
  parameter override". [ADR 0019](../../architecture/decisions/ADR-0019-argocd-application-and-sync-policy.md)
  D5, accepted after revision 2, delivers the values as the generated values file,
  hand-written values inside the Application, and one operator-supplied Helm parameter,
  `api.image.digest`. On that delivery the clause cannot hold, whatever a run observes.
  Revision 3 states the ownership property in its place: no hand-written value and no
  operator-supplied parameter restates or overrides claim-relevant workload intent. The
  parameter is permitted because no contract, binding, platform default, or renderer owns
  it. `criteriaChanges` holds both statements, the reason, and who approved the change.
  E01-AC1 to E01-AC9 are those of revision 2, character for character.
- **Every other difference from revision 2 is listed.** Three statements of the E01-D
  procedure and inputs carried the same mechanism or predate the Git layout, and
  `procedureChanges` lists each replacement. `fieldChanges` lists twelve more, each with
  revision 2's text: the environment, the topology, the evidence paths, two added abort
  conditions, the cleanup, the preconditions, and the outcome rules. The cleanup of
  revision 2 was written for an environment it could not name, and four of its items
  have no subject on this one.
- **The change was written after runs of the same path.** No E01-D run had executed. But
  between 2026-10-03 and 2026-10-05 the Argo CD procedures ran on this provider, applied
  this release with this parameter, and sent caller requests: five of six were answered
  in one set of runs. They are not E01-D runs. The record lists them in `history`, and
  says that the criterion change was written with knowledge of them.
- **The pins.** 160 inputs: the 74 of revision 2, and 86 added for the E01-D path. The
  86 are the rest of the `inferops` package that the API image copies, the three tools
  the steps run, the API container's entry module and the carrier it imports, the
  desired-state tree, the two Argo CD manifests, five procedures and the library they
  source, the Terraform prerequisite layer, the image build files, the model source
  record, the `local-docker-desktop` binding, one test module, and the two pytest
  configuration files. `inputChanges` classifies each.
- **No pin of revision 2 moved.** Each of the 74 has the content revision 2 pinned.
  `changesSinceSupersededRevision` lists all 132 files that changed between the merge of
  revision 2 and the commit revision 3 was prepared from: 18 are on the E01-D path, 114
  are not, and none is a pinned input of revision 2.
- **The static result is consumed, not repeated.** Run `20261003-e01-abc-1` under
  revision 2 is the static result. No pinned input of revision 2 moved, so no change is
  material to it.

What revision 3 does not do:

- **No runner exists for E01-D, and no code computes its verdicts.** A person executes the
  registered steps and applies the registered rules. A driver that transcribes the steps
  is committed with the run and is not a pinned input.
- **The E01 runner still executes revision 2.** Its `CURRENT_REVISION` is 2. It is a
  pinned input, and this change does not edit it. A new static run would execute under
  revision 2.
- **The committed-run check refused an E01-D run, and the change that registered
  revision 3 did not fix that.** `tools.experiment_e01 --check` read every directory under
  `runs/` as a static run and knows revisions 1 and 2. Revision 3 puts an E01-D run
  under `runs/`, because the review gate reads runs there. So the change that commits an
  E01-D run had to change that check, after the run. The edit was tried when revision 3
  was registered: 13 tests of the default lane failed, and it was taken back out.
  `V2-S3-004-PR2` made the edit after the run. [The E01-D run](#the-e01-d-run) says what
  it moved. A run of any part after that edit needs a later revision.
- **No command judges a committed E01-D run again.** The evidence index binds each
  cited file by SHA-256, and the review gate compares the review's digests with the
  run's files.
- **No step observes whether the model was downloaded.** The claim is filled before
  the Application is applied, so the acquisition hook is expected to download nothing.
  No step reads the hook's job, and Argo CD deletes it when it succeeds.
- **The cleanup leaves images in the node and on the host.**
- **The eight-character clause of E01-AC10 is not computed over the live Application.**
  It rests on the static result's verdict for the hand-written values fixture, and on a
  test that holds the Application's hand-written values equal to that fixture without its
  digest.
- **Nothing here blocks a merge that changes a pinned file.** As before, the run that
  follows refuses to start until a merged revision classifies the change.

An E01-D result enters the register only through
[the review gate](#correction-of-the-second-run-claim-and-the-review-gate-2026-10-03): a
ledger that bears on the run names one independent review artifact of that run. The
review of the second static run is not a review of an E01-D run, and the gate refuses it
for one.

## The E01 static run

`tools/experiment_e01` runs E01-A, E01-B, and E01-C once, as the freeze record registers
them, and checks a committed run. It reads every input, edit, and expected refusal from the
record itself, not from a copy of its own.

```sh
# Run the static parts once. The run's identifier is its UTC date, the parts, and a sequence.
PYTHONHASHSEED=1 uv run --locked python -m tools.experiment_e01 --run YYYYMMDD-e01-abc-N
# Judge every committed run again from its raw evidence. Writes nothing.
uv run --locked python -m tools.experiment_e01 --check
```

**Before it runs a part,** the runner checks the record's preconditions and records each
observation. Under revision 2 it also checks that the runner module it runs is the
checked-out tree's `tools/experiment_e01/core.py`, that the record is registered and
unedited, and that no material file differs - added files included - and it records the
`inferops` distribution version, the registry's digest, and every repository module file it
and its second process loaded. Under revision 1 it checked: the executing commit is a full revision reachable from `origin/main`, the
freeze record is in it, `git status --porcelain --untracked-files=all` prints nothing,
every pinned input has its pinned content, and the `inferops` package it imported is the
one under the checkout's `src`. If one fails, it writes a run with every part REFUSED and
runs nothing. `origin/main` is read as the clone holds it, so a clone that has not fetched
refuses a commit that is merged; the reverse cannot happen. A new run executes
revision 2, the runner's `CURRENT_REVISION`, and not [revision 3](#revision-3); a committed run is judged by the analysis of the revision it names,
so the first run is still judged by revision 1's criteria and page, byte for byte. It refuses an identifier whose date is not today's UTC date, and an
evidence directory that already exists. It starts only with `PYTHONHASHSEED=1`; the second
E01-A render runs in its own process with `PYTHONHASHSEED=2`.

**After the parts,** it records the commit and the status again. A changed commit, or a
change outside the run's evidence directory, is an abort condition, and the parts are
ABORTED. It removes its temporary directory and records that it did. The status check
sees what `git status` sees: a write to an ignored path, or outside the repository, is
not detected. A step that raises is recorded as the run's `error`, and the parts it left
unanswered are INCONCLUSIVE; a criterion that did not hold makes its part FAILED even when
another went unanswered, because a FAILED run is not repeated.

**What a run holds.** One directory under
[`v2-e01/runs/`](v2-e01/runs/), named by its identifier, with the files the record's
`evidencePaths` names: `run.v1alpha1.json` (the manifest: identifier, parts, executing
commit, preconditions, host, runner file digests, observations, abort checks, the SHA-256
of every file, each criterion's verdict, and each part's outcome), `commands.txt`,
`render-a/`, `render-b/`, `mutation/`, `refusals.json`, and `result.md`.

**The check.** `--check` reads every directory under `runs/` as a static run, except a
directory named as a run of E01-D, `YYYYMMDD-e01-d-N`, which it leaves out. It derives every verdict again from the committed renders, the
recorded refusals, and the observations the manifest records: the two renders compared,
the release fields read from the files, the mutation's differences listed again, and every
refusal compared with the record's expected one. It does not recompute the contract,
binding, or mutated-contract digests, the admission of the hand-written values, or the V1
merge; those are the run's observations. It fails when a file does not have the digest the
manifest records, when the manifest names a file that is absent or omits one that is
present, when a verdict or an outcome differs from the one the evidence gives, when
`result.md` is not the page the evidence generates, when the run names a reference other
than `origin/main`, when its recorded precondition findings are not the ones its recorded
observations give, and when the manifest cannot be read. The manifest is not in its own
digest list, so an edit to it and to `result.md` together passes `--check`; the evidence
index, which binds every cited file of the run's record by SHA-256, the manifest
included, is what refuses that. The
default-lane suite [`tests/testing/test_experiment_e01.py`](../../../tests/testing/test_experiment_e01.py)
runs it over the committed run and plants each of these defects in a copy.

**The first run.** [`20261002-e01-abc-1`](v2-e01/runs/20261002-e01-abc-1/result.md) executed at
the merged commit `707e29f4a0ff31ea90fa33f6b8cf2ec883cfb6a3`, in a detached worktree with no
change before the run and only the evidence directory after it. E01-A, E01-B, and E01-C each
PASSED: every criterion from E01-AC1 to E01-AC7 held. The claim
`the-first-e01-static-run-recorded-identical-renders-and-every-registered-refusal`
in the [claim and evidence register](../../testing/claim-evidence-matrix.v1alpha2.json)
holds it at C0. The run's [validation record](../domain/v2-s2-003-pr2-validation.md) says
how it was prepared and what was checked.

**The second run.** [`20261003-e01-abc-1`](v2-e01/runs/20261003-e01-abc-1/result.md) executed at the merged commit
`a5b6a5db2011a68a3f27acdeaa8186c226bfedb4`, the merge of the change that registered revision
2, with no change before the run and only the evidence directory after it. It is the
first run under revision 2. The manifest records that the record had its registered
digest, that no material file differed, that the runner was the checkout's
`tools/experiment_e01/core.py` and the package the checkout's `src/inferops`, in both
processes, and that each process loaded 47 repository module files, every one a pinned
input with its pinned content. E01-A, E01-B, and E01-C each PASSED: every criterion from
E01-AC1 to E01-AC7 held, E01-AC5 without revision 1's exception and E01-AC7 over seven
cases. The claim
`the-second-e01-static-run-recorded-its-frozen-path-identical-renders-and-every-registered-refusal`
holds it at C0. The run's [validation record](../domain/v2-s2-004-pr2-validation.md) says
what was checked before it, what executed before it, and every attempt. The run answers
revision 2 only: it is not evidence that the first run's execution boundary was valid.

| Run | Freeze revision | Executing revision | E01-A | E01-B | E01-C |
|---|---|---|---|---|---|
| [`20261002-e01-abc-1`](v2-e01/runs/20261002-e01-abc-1/result.md) | 1 | `707e29f4` | PASSED | PASSED | PASSED |
| [`20261003-e01-abc-1`](v2-e01/runs/20261003-e01-abc-1/result.md) | 2 | `a5b6a5db` | PASSED | PASSED | PASSED |

Every committed run stays in this table with its outcome state, whatever it is. No committed
run under either revision was REFUSED, ABORTED, INCONCLUSIVE, or FAILED. The previews
[the audit](#audit-of-the-first-run-2026-10-03) describes are not runs of record; two of
them reported E01-A INCONCLUSIVE.

**What the first run does not do.** The runner is not a pinned input of freeze revision 1, and the
first run executed from a byte copy outside the checked-out tree, so the commit it
records does not contain the runner. The manifest records the content digest of each runner
file instead. Those digests are of the runner as `V2-S2-003-PR2` first committed it: its
independent review then changed the runner, so the files committed beside the run are not
the ones that ran, and the first commit of that change holds the ones that did. The fixes
changed no verdict of the run. Nothing compares a committed run with today's code: a later change to the
renderer leaves the run as it was, and a new run needs a new identifier. Nothing here
deploys the release input, reconciles it, or serves a completion; that is E01-D.

## The E01-D run

[`20261006-e01-d-1`](v2-e01/runs/20261006-e01-d-1/result.md) is the one run of part E01-D. It executed on
2026-10-06 under revision 3, at the merged commit
`ad725905a7838e8210e54a29de7913bc0c7c49e5`, which merged revision 3 and which `main` named
on the remote when the run started. Its [validation record](../domain/v2-s3-004-pr2-validation.md)
says what was checked before it and after it.

| Run | Freeze revision | Executing revision | Environment | E01-D |
|---|---|---|---|---|
| [`20261006-e01-d-1`](v2-e01/runs/20261006-e01-d-1/result.md) | 3 | `ad725905` | `docker-desktop`, Kubernetes v1.36.1, one node | PASSED |

**What executed.** A driver ran the steps that revision 3 registers, once: preparation P1
to P7, procedure D1 to D6, and the cleanup. The run rendered the release again at the
executing commit and compared it with the release in Git, byte for byte. It applied the
Argo CD Application with one parameter, `api.image.digest`. Argo CD reported a succeeded
sync at the executing commit. Both rollouts completed 18 seconds after the apply returned,
against a deadline of 600 seconds. It is a warm start: the preparation had started the
same images on the same node about two minutes earlier. The readiness request returned 200. The run then sent
one completion request and no other.

**What the criteria gave.**

- **E01-AC8 holds.** The one request returned HTTP 200, with one choice whose assistant
  message has a length of 6 characters. The generated text is not kept.
- **E01-AC9 holds.** Argo CD reports the executing commit as synced and as applied. The
  provenance tool resolves that commit to the release identifier and the values digest
  that revision 3 names. The runtime container's image identity ends with the generated
  runtime image digest. The runtime mounts the generated model revision, and the init
  container that verifies the artifact ended with exit code 0. The response names the
  generated model identifier.
- **E01-AC10 holds.** The live Application takes its values from the one generated values
  file, from hand-written values equal to those of the committed manifest, and from the
  one parameter, whose value is the digest that the run's build printed. The three
  admission tests passed at the executing commit. The eight-character clause rests on
  the consumed static result, as revision 3 registers. No code computes it over the live
  Application.

**What the run holds.** Twelve files: `run.v1alpha1.json` (the manifest, with each
compared value, each rule's verdict, and the SHA-256 of every other file),
`commands.txt`, `driver.txt`, `transcript.txt`, `environment.json`, `release.json`,
`argo.json`, `pods.json`, `reconciliation.record.json`, `provenance.json`,
`completion.json`, and `result.md`.

**What the run does not do.**

- **No runner judged it.** The automated assistant session that drove the run applied
  the registered rules. It is not independent of the run. The default-lane suite applies
  each rule again to the committed files and requires the recorded verdict. It reads
  two rules from less than a structured file: the admission rule from the pytest summary
  in the transcript, and the eight-character rule from the consumed static run. The
  suite does not show that the cluster returned those files.
- **Its files fall short of the registered form in four places.** `commands.txt` has no
  shell quoting and lists once a command that ran twice. `transcript.txt` does not hold
  the output of three commands of step P3, which went to ignored files. Two of the
  thirteen compared environment attributes are literals of the driver. The manifest
  cites step D6 for the eight-character rule and does not state the consumed run's
  verdict. The files are evidence and are not edited.
  [The validation record](../domain/v2-s3-004-pr2-validation.md) gives each, and the
  weaknesses of the driver that this run did not meet.
- **It sent one request.** It does not establish that a second request is answered.
- **It did not observe the network.** It does not establish that the acquisition hook
  downloaded nothing. Argo CD reports that the sync operation, which holds the hook,
  lasted 9 seconds.
- **The pod status names another digest for the API image than the run supplied.** The
  pod requested the supplied digest. After the run, a read of the node listed both digests
  for one image identifier, which is the one the run's build exported. That read is not
  a registered step. No E01-D criterion names the API image digest.
- **The transcript is redacted.** Terminal colour codes are removed, the absolute path of
  the repository on the host is replaced, and two Docker build links are replaced. Line
  endings are changed to LF, and trailing whitespace is removed. The run's own files
  name the first three only.
- **It is one run on one provider, with one node.** The evidence is C2, bounded to the
  environment that `environment.json` records. It is not representative.

**The committed-run check, changed after the run.** `tools.experiment_e01 --check` read
every directory under `runs/` as a static run, so it refused the E01-D directory. This
change edits one function of the runner, `committed_runs`, after the run. The listing
leaves a directory out when its name is that of an E01-D run and its own manifest names
part E01-D and no other. Every other directory is still listed, so a static run under
such a name is checked. The command does not print what it left out.

- **The edit moves one pinned input of revisions 2 and 3:**
  `tools/experiment_e01/core.py`. `python -m tools.experiment_freeze --changes` reports
  it for both records, and exits 1.
- **The E01-D run executed before the edit.** Its step P2 reports no difference for
  revision 3 at the executing commit. The E01-D steps do not run the runner. The run
  and the edit are in one commit, so Git history does not order them: the transcript
  supports the order and does not prove it.
- **A new run of any part is refused** until a merged later revision classifies the
  edit. This change registers no revision and classifies nothing.
- **The static result is not judged again by other code.** `--check` passes over both
  static runs with the edited runner. The edit changes which directories are listed, and
  no line of the analysis.
- **The suites that copy the pinned inputs rebuild the pinned runner.** They take the
  runner in the tree and put back the two passages that the edit replaced. A test holds
  the result to the digest that both records pin. So the listing is the only difference
  between the runner in the tree and the pinned one. Another edit to the runner fails
  that test. The second process of each such test, and one whole test, therefore execute
  the pinned runner and not the runner in the tree.

**The independent review.** [`v2-e01/reviews/20261006-e01-d-1-review-1.md`](v2-e01/reviews/20261006-e01-d-1-review-1.md) is the report of one independent
review of this run, with
[its machine-readable record](v2-e01/reviews/20261006-e01-d-1-review-1.v1alpha1.json). The review
read the first commit of the change that adds the run, `2f2e1ff`, read-only, on
2026-10-06. That commit held no register change. A review record is not evidence of the
run. When it was published no register claim cited it; since `V2-S3-005-PR1` one
register record cites it, as the review of the run. The review read no register
statement about the run, and it does not establish that the claim is correct.

- **The frozen run.** The reviewer applied each registered rule to the raw files. Every
  verdict equals the one the run recorded. It found no defect in the files, the digests,
  the freeze identity, the procedure, or the outcome, and it found that a rerun is not
  justified.
- **Fourteen findings, none claim-material.** They are about disclosure and prose. Six
  are corrected in the same change. Four are in run files, which are not edited, and
  are stated. Four are observations.
- **What it could not verify.** That the remote named the executing commit, that the
  cluster returned the committed files, the test result of step D6, and whether a model
  download happened.
- **The limits of its independence.** The reviewer is a separate session of the
  automated assistant that drove the run. It is not a person. It also read uncommitted
  files on the host, which the brief did not ask for.
- **The register.** When the review was published, no ledger referenced this record,
  and the claim and register reconciliation of E01-D was owed by a later change.
  `V2-S3-005-PR1` is that change:
  [its ledger](#registration-of-the-e01-d-result-2026-10-07) references this record, and
  the [review gate](#correction-of-the-second-run-claim-and-the-review-gate-2026-10-03)
  holds the ledger to it: the record must describe the run's files as they are.

## Audit of the first run, 2026-10-03

The first Sprint 2 collective review examined run `20261002-e01-abc-1`. Its files, digests,
and revision 1 outcomes are unchanged, and `--check` still judges it by revision 1. The
audit adds this limitation; it does not reinterpret the run under revision 2:

- **The execution boundary was not the freeze's.** The run records executing revision
  `707e29f4`, but the runner it executed was not in that commit and was not a pinned input
  of revision 1. Revision 1's change check compared only the files it listed, so it could
  not report the runner. The run is not evidence that its execution was governed by its
  freeze.
- **The package location was observed by hand.** The run predates the check that records
  which `inferops` package was imported.
- **Previews were not preregistered.** Before the run, a full development preview executed
  E01-A, E01-B, and E01-C in a throwaway repository and reported all three PASSED. After
  it, two more full executions in throwaway repositories ran while review findings were
  fixed, and reported E01-A INCONCLUSIVE and E01-B and E01-C PASSED. None was exempted
  before it ran. Their raw evidence directories were deleted with their repositories and
  are not available; a partial console capture of each exists outside this repository and
  is not published, because it contains host paths. Nothing reconstructs them.
- **What the audit found intact.** The review found no evidence that thresholds, workload,
  faults, or raw result files were changed, every manifest-covered file keeps its digest,
  and an independent comparison reproduced both original render-a files.

Revision 2's `history` records the same. A new run under revision 2 answers revision 2's
criteria; it is not evidence that the first run's boundary was valid.

Since `V2-S2-004-PR2` the register carries the audit too: the first run's claim has the
limitation appended, dated, after the text it already had, and [a ledger](../testing/v2-s2-004-pr2-e01-corrected-static-proof.v1alpha1.json)
holds one correction beside the first run's result page. The claim's statement, status,
and record are unchanged.

## Independent review of the second run, 2026-10-03

[`v2-e01/reviews/20261003-e01-abc-1-review-1.md`](v2-e01/reviews/20261003-e01-abc-1-review-1.md)
is the report of one independent review of run `20261003-e01-abc-1`, with
[its machine-readable record](v2-e01/reviews/20261003-e01-abc-1-review-1.v1alpha1.json).
The review read the merge of pull request 114, `3f08f439`, on 2026-10-03, read-only. It
started no run. A review record is not evidence of the run, and no register claim cites it.

- **The frozen run.** The review found no defect in the run's ten files, its digests, its
  freeze and registry identity, its executing revision and 74 pins, its seven criterion
  verdicts, or its three PASSED outcome states.
- **The register statement.** The review found one claim-material defect, in wording only.
  The second-run claim's statement says the evidence holds "no hand-written string that
  contains a generated workload-intent value". E01-AC5 limits that to generated values
  "of eight characters or more". Without the limit the clause is false: three hand-written
  strings contain a shorter generated string value, `local` or `6`. With the limit the clause is
  true. When the review was published, the register, the ledgers, the evidence index,
  and the dashboard carried the broader clause. `V2-S2-005-PR2`
  [corrected the claim later](#correction-of-the-second-run-claim-and-the-review-gate-2026-10-03).
- **The order of review and registration.** The review that the second run's validation
  record documents read commit `c24fda4`, which already held the register change. This
  review also read a revision that held it. So no record establishes that an independent
  review preceded the register change for this run, and this review does not repair that
  order. The same holds for the first run: its documented review read the commit that
  added its claim.
- **No rerun.** The finding is in one sentence of the register, not in the run. A new run
  would answer the same frozen criteria and could not change the sentence.

The report lists thirteen findings, what the review could not verify, and the limits of its
independence: the reviewer is a separate session of the automated assistant that
co-authored the run's change, not a person and not anyone outside the project. When the
review was published, no check required a review record before a register change.
Since `V2-S2-005-PR2` [a gate](#correction-of-the-second-run-claim-and-the-review-gate-2026-10-03)
requires one.

## Correction of the second-run claim, and the review gate, 2026-10-03

`V2-S2-005-PR2` started from `4023487e`, the merge of the change that published the
review. It corrected one statement and added one gate. No part of E01 ran again, and
both runs and both freeze records are unchanged.

**The correction.** [A ninth ledger of register changes](../testing/v2-s2-005-pr2-e01-claim-correction.v1alpha1.json)
narrows the second-run claim's statement. The clause now reads "no hand-written string
that contains a generated workload-intent value of eight characters or more", which is
the limit E01-AC5 carries. The ledger also appends a dated correction to the claim's
limitation. The claim's status, its evidence level, and its record are unchanged.
The correction is additive and later. The ledger that added the claim is not edited and
still holds the earlier wording, and the ninth ledger records that wording as the value
before the change. The earlier wording is on `main` from the merge of `V2-S2-004-PR2`
until this correction merges.

**The order.** Git history gives this sequence, by commit:

1. `c24fda4` added the second run, its claim, and its ledger. The review that the run's
   validation record documents read that commit.
2. `4023487e` merged the published review, which read a revision that held the claim.
3. This change corrected the statement.

No record establishes that an independent review preceded the register change for either E01 run.
The correction does not repair that order, and no later change can.

**The gate.** A register change *bears on* a run when the claim or record it adds, or the
claim or record it changes, names a file under that run's directory, in any field, before
or after the change. A ledger with such a change
must name one review artifact for each run in `resultReviews`: the run's path, the
artifact's path, and the artifact's content digest.
[`tools/evidence_index`](../../../tools/evidence_index/core.py) checks every ledger when
it builds the index, so `--check` and `--write` print `MISMATCH` and exit 1 on a refusal,
as does `--gate` where it reports a freeze, and the
default-lane suite [`tests/testing/test_result_review_gate.py`](../../../tests/testing/test_result_review_gate.py)
plants each refusal in a copy.

| Refused | Reason |
|---|---|
| A ledger that bears on a run and names no review of it | The review reference is omitted |
| A reference whose artifact is absent | The review is not in the repository state the index is built from |
| An artifact whose content digest is not the one the ledger states | The artifact changed after the ledger named it, or the ledger names other content |
| A `resultReviews` row that is not exactly the three strings, or references that are not a list | The reference cannot be read |
| A register change with an operation the gate does not know | The gate cannot say what the change bears on |
| An artifact that is not JSON, is not an `ExperimentResultReview`, or is not a plain path under the experiment's `reviews/` directory | It is not a result review of this experiment |
| An artifact whose `subject` names another run | The review is about another result |
| An artifact whose file digests are not those of the run's files, or that omits or adds a file | The review is stale: the run is not what the review read |
| An artifact that does not name the freeze record the run's manifest names, or that gives another digest for it | The review read another freeze record |
| Two references for one run, or a reference for a run no change bears on | The reference is ambiguous or unrelated |
| A review stated by a ledger written before the gate | A review written since did not precede that ledger |

The ninth ledger bears on the second run. It references
[the published review record](v2-e01/reviews/20261003-e01-abc-1-review-1.v1alpha1.json),
and the gate accepts that reference. The review record is unchanged since it merged.

**What the gate does not do.**

- **It does not prove an order in time.** The gate reads one repository state.
  It does not show that a review was committed before the register change: a review
  artifact and a ledger can arrive in one commit. For this correction only, a test reads
  Git history and finds the review record, with its present content, at `4023487e`, where
  the ninth ledger does not exist. That test skips in a clone without that commit, and a
  skip is not a pass.
- **It does not judge the review.** It does not show that a review took place, who did
  it, whether it was independent, or what it concluded. A review record that reports a
  defect satisfies the gate.
- **It does not bind a review to a change.** One review artifact of a run satisfies
  every later ledger that bears on that run, including a change the review did not read.
  The gate does not read the register state the review recorded.
- **It does not cover the two earlier ledgers.** The ledgers that added the two E01
  claims were written before the gate. Each names no review, and the tool lists them in
  `PRE_GATE_LEDGER_PATHS` and in the index, under `registeredBeforeTheGate`. That list
  records what happened. It does not say that either ledger complied. The gate does not
  check these two ledgers, whatever they hold; a test holds each to its content.
- **It sees a run only by a named path.** A record that states a run's result and names
  no file under the run's directory does not bear on the run, as the gate reads it. The
  gate matches a path in the repository's normal form; the register's own rules, which
  the default lane runs, refuse a path in another form. The gate follows a symbolic
  link, and a path in another letter case resolves on a host whose file system ignores
  case.
- **It can be changed with the ledger.** A change that edits the gate, or the list of
  earlier ledgers, together with a ledger passes the check. A test holds that list to
  its two entries, so such an edit shows in review as a changed test.

E01-D ran once, in [`20261006-e01-d-1`](v2-e01/runs/20261006-e01-d-1/result.md). A register change that
bears on that run is to reference a review of that run: the review record of the static
run names another run, and the gate would refuse it for a record that names a file under
another run directory. [The registration of the E01-D result](#registration-of-the-e01-d-result-2026-10-07)
is the first such change.

## Registration of the E01-D result, 2026-10-07

`V2-S3-005-PR1` added the result of [the E01-D run](#the-e01-d-run) to the claim and
evidence register. No part of E01 ran in that change. No file of a run, of a freeze
record, or of a review record changed. Its
[validation record](../domain/v2-s3-005-pr1-validation.md) lists each identity it
consumed.

**The order of events.** The history is kept as it happened:

1. On 2026-10-06, `V2-S3-004-PR1` merged revision 3.
2. On 2026-10-06, `V2-S3-004-PR2` ran E01-D once, published the independent review of
   the run, and merged. It registered no claim and no evidence record. Its validation
   record says that the reconciliation was owed by a later change.
3. On 2026-10-06, a review of the sprint reported that the reconciliation was missing.
   It reported no defect in the freeze inputs, the raw run, the result classification,
   or the review record, and it reported that the finding justifies no repeated run.
   That review was reported to the author, and no file in this repository records it.
4. On 2026-10-07, `V2-S3-005-PR1` added the claim, through
   [the E01-D registration ledger](../testing/v2-s3-005-pr1-e01-d-registration.v1alpha1.json),
   the tenth ledger of register changes and the sixth after `v1.0.0`.

The register does not state that the registration happened on the day of the run. The
claim's limitation and the record's limitations each carry the two dates.

**The claim.** `the-e01-real-deployment-run-served-one-completion-from-the-release-reconciled-from-git`
is `certified` on one record at `C2`. It says, in the past tense, what one run showed: on
the `docker-desktop` provider, on one cluster with one node, the release rendered from
the unmodified reference contract was accepted into Git, was read by the run at one
commit, was reconciled by Argo CD, and answered one completion request with HTTP 200 and a non-empty assistant
message, under E01-AC8, E01-AC9, and E01-AC10 of revision 3.

**The review reference.** The ledger names two review artifacts in `resultReviews`, each
with its content digest:

- [the review of the E01-D run](v2-e01/reviews/20261006-e01-d-1-review-1.v1alpha1.json),
  because the claim and its record cite the run's files;
- [the review of the second static run](v2-e01/reviews/20261003-e01-abc-1-review-1.v1alpha1.json),
  because one rule of E01-AC10 rests on that run, so the record cites its manifest, and
  because the ledger changes one clause of that run's claim.

The gate was not changed. It checked each artifact against the run it names: the files
of the run directory have the digests the review states, and the review names the freeze
record that the run's manifest names. For the E01-D run, Git history also shows the
order: the review record has had its present content since the merge of
`V2-S3-004-PR2`, and the ledger is not in that commit. The gate does not read history.
A test does, and it skips in a clone that lacks that commit.

**What else the ledger changes.**

- **Two planned claims gain a dated note and stay planned.**
  `the-platform-serves-a-workload-the-contract-describes` and
  `deployment-values-derive-only-from-a-validated-document` each said something that the
  E01-D run made out of date. Each keeps its earlier text, gains sentences dated
  2026-10-07 that name the run, and cites no record. One run, with one contract, on one
  provider, does not establish either general statement.
- **One clause of the second static run's claim is replaced.** The clause said that
  E01-D "has not run".
- **One surface reason is replaced.** It named nine ledgers.

**What it does not correct.**

- **The first static run's claim still says that E01-D "has not run".** A change to that
  claim bears on run `20261002-e01-abc-1`. No review record of that run exists, so the
  gate refuses the change, and `V2-S3-005-PR1` creates no review. The clause is a
  statement of 2026-10-02.
- **The evidence records of the two static runs say the same.** Each is a dated record,
  and neither is changed.
- **The files of the E01-D run keep their text.** The review record lists where a run
  file says less than what executed. The register record states those limits.

**What the claim does not establish.** A second request. Another provider, Kubernetes
version, node count, storage class, workload shape, contract, or binding. That Argo CD
applies a later commit. A caller outcome from a sync state, a health state, pod
readiness, or a replica count. That the acquisition hook downloads the model into an
empty claim. Latency, throughput, capacity, availability, or behaviour under overload.
Reliability under failure, high availability, or tolerance of the loss of a pod, a node,
a zone, or a region. That a service-level objective is met. Representative evidence,
`C3`, or operational evidence, `C4`. A cost, a saving, a return on investment, or a
business effect. That a person reviewed the result. Production readiness.

**What stays open.**

- No command judges the committed E01-D run again. `python -m tools.experiment_e01
  --check` judges the two static runs and leaves the E01-D run out, so its exit status
  says nothing about E01-D. Tests apply the registered rules to the run's files.
- A new run of any part of E01 is refused until a later freeze revision classifies the
  edit to the committed-run listing.
- The review of the result is a record of an automated session. No person and no
  outside party reviewed it.

## The Sprint 5 integration validation

[`v2-s5-integration/freeze-r1.v1alpha1.json`](v2-s5-integration/freeze-r1.v1alpha1.json)
fixes one bounded validation of the Sprint 5 evidence path before its first attempt:
the in-cluster RP-1 runner, the timeline and telemetry collectors, and the operator
event log, run together against one release on the docker-desktop provider, with one
API pod deleted while the runner sends. The procedure is
[the driver beside it](v2-s5-integration/procedure/run-driver.txt), a pinned input of
the record, and the record states seven acceptance criteria, `S5I-AC1` to `S5I-AC7`.

- **It is not result-bearing.** No attempt is a run of E02, E03, E04, E05, or E06, no
  figure of an attempt is compared with a bound, and no claim cites one.
- **It has its own directory.** The freeze check holds one experiment in each
  directory, so the record is not a revision of E01.
- **Each attempt is kept.** An attempt has its own run directory under
  `v2-s5-integration/runs/`, in the [evidence layout](../../testing/experiment-evidence-layout.md),
  whatever it shows. A later attempt runs only under a later revision that states what
  changed, or after an attempt that was refused before its capture.

### The two attempts

| Attempt | Revision | Executing commit | State | What it showed |
|---|---|---|---|---|
| [`integration-1`](v2-s5-integration/runs/integration-1/result.md) | 1 | `7f150c25af26f855a7390125be82dd44fba772a5` | FAILED on S5I-AC2 | The runner pod kept one UID and no restart while one API pod was replaced, and each stream passed its checker. Each of its six requests ended at the client deadline, and the API counted none. Three readings point to the network plugin applying the release's API policy, which admits only the pods of the release and a named collector; that is an inference |
| [`integration-2`](v2-s5-integration/runs/integration-2/result.md) | 2 | `7089a53ac0a62933cfba74facfe998e73c5a4f97` | PASSED | 98 requests, each a success, 42 before the deletion of one API pod and 51 after the replacement was Ready. The runner pod kept one UID and no restart. Each stream, the log, the layout check, and the replay of the analysis passed |

- **Both attempts used one release.** The phase up of the driver prepared it once; its
  transcript is [`preparation/up-s5i-1-transcript.txt`](v2-s5-integration/preparation/up-s5i-1-transcript.txt).
  That phase ran from [a draft of the driver](v2-s5-integration/preparation/draft-driver.txt)
  outside the tree, before revision 1 was committed. Its function `up` is the one that
  the committed driver holds. An earlier phase up, under another run name, refused at
  its first capacity reading because a collection of that name already existed on the
  host, and installed nothing: [`preparation/up-run-1-refused-transcript.txt`](v2-s5-integration/preparation/up-run-1-refused-transcript.txt).
- **The release was removed after the second attempt**, by the phase down:
  [`preparation/down-s5i-1-transcript.txt`](v2-s5-integration/preparation/down-s5i-1-transcript.txt).
  The namespaces and the custom resource definitions of the cluster then equal those
  read before the phase up. The images loaded into the node are left there.
- **Revision 2 was written after the first attempt, and before the second.** It
  changes the runner and its script so that a run brings its own network policy, and it
  classifies each moved input. The procedure, the bounds, the criteria, and the fault
  are those of revision 1, except that the start of the runner (procedure step 5) and
  `S5I-AC7` name the network policy of the run.
- **Revision 2 states the cause of the first failure more firmly than the evidence
  does.** Its limitations say that the first attempt "observed" that the plugin
  enforces the policy, and its purpose says that the attempt failed "because" it does.
  The first attempt saw that no request reached the API; that the policy dropped them
  is an inference from three readings, as [its result page](v2-s5-integration/runs/integration-1/result.md)
  states. The record is pinned and is not edited. Its criteria and its procedure do not
  depend on the wording.
- **One correction is recorded for the first attempt**, at
  [`corrections/integration-1/correction-1.v1alpha1.json`](v2-s5-integration/corrections/integration-1/correction-1.v1alpha1.json).
  It corrects four statements of the result page and changes no state.
- **What neither attempt establishes.** A recovery time, an availability, a service
  level, a capacity, or a threshold; behaviour when a runtime pod is replaced; and
  behaviour on another provider, node count, or network plugin.

## The Q1 environment qualification

[`v2-q1/freeze-r1.v1alpha1.json`](v2-q1/freeze-r1.v1alpha1.json) fixes Q1 before any
qualification runs. Q1 decides whether one local environment holds the target topology
of the desired-state release, two API replicas and two runtime replicas, at its exact
identities, before a V2 reliability experiment runs. The procedure is
[the driver beside it](v2-q1/procedure/q1-driver.txt), and the decision is made by
[`tools/environment_qualification`](../../../tools/environment_qualification/core.py).
Both are pinned inputs of the record. The record states seventeen acceptance criteria,
`Q1-AC1` to `Q1-AC17`, and each is one rule of the tool, with the same statement.
[The Q1 page](../../environment/environment-qualification.md) describes each rule.

- **It is a qualification, not an experiment.** Q1 injects no fault and derives no bound.
  Any bound is later work. No qualification is a result of E02 to E06, and no claim
  cites one.
- **The result is `QUALIFIED` or `REFUSED`.** A refusal is kept, and it is not converted
  into a weaker target: no replica count, request, limit, or bound is changed to obtain
  `QUALIFIED`.
- **It selects one environment.** A `QUALIFIED` record states the environment identity
  and its digest. E02A and E02B execute in that one environment, and a run whose identity
  differs is not a run of the controlled comparison. This is a rule of the record. Since
  `V2-S6-003-PR1` the [freeze records of E02A and E02B](#the-reliability-experiment-freezes)
  name `q1-2` and its stable identity. (Until then this item said that no freeze record of
  E02A or E02B exists. Until `V2-S6-004-PR1` it also said that no tool compares two
  identities; the Q2 and Q3 tools compare them.)
- **It has its own directory.** The freeze check holds one experiment in each directory.
  A qualification is committed under `v2-q1/runs/q1-N/` with its record, whatever it shows.
- **The first qualification is `QUALIFIED`.** (Until `V2-S6-004-PR2` this item began "One
  qualification has run".) The record was registered by
  `V2-S6-001-PR1`. Under it, `V2-S6-001-PR2` ran [`q1-1`](v2-q1/runs/q1-1/result.md) on
  2026-10-15, at the commit `08b8914`, on the docker-desktop provider with one node, and
  each of the 17 criteria held. Its environment identity,
  `sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461`, was the
  selected environment of E02A and E02B until `V2-S6-004-PR1`. It is evidence at C2 of
  that one environment, and of no other provider, node, Kubernetes version, or release.
  (Until `V2-S6-001-PR2` this item said that no qualification had run.) Since
  `V2-S6-004-PR1` it selects no environment: the selection passes to `q1-2` under
  revision 2, and only if `q1-2` is `QUALIFIED`.
- **Since `V2-S6-004-PR2`, `q1-2` is `QUALIFIED` under revision 2.** It ran once, on
  2026-10-17, at the commit `ed892a4`, and each of the 17 criteria held. Its stable
  environment identity, `sha256:6a219b3ff959a0020d982d967abeed6696aa0f0d1b594bdf3ad86b9aeda8cd5c`,
  is the selected environment of E02A and E02B. Its capacity reading stated 10,429,972,480
  bytes of memory, and the gate accepted it. It is evidence at C2 of that one environment.
- **The layout check lists a qualification and does not hold it to a manifest.** A
  qualification has no ExperimentRun manifest. Since `V2-S6-001-PR2`,
  `python -m tools.experiment_evidence repository` lists each directory of
  `v2-q1/runs/` as a qualification and applies its two text rules to each file, and
  `python -m tools.environment_qualification --check` builds its record again. The
  first draft of the run directory was refused by the layout check, which `V2-S6-001-PR1`
  had not foreseen.
- **One read is not committed.** The capacity gate's read of every pod of the cluster,
  `capacity/pods.json`, holds container paths under a home directory in the
  controller's pods, and the publication check refuses it. [The page of
  `q1-1`](v2-q1/runs/q1-1/result.md) states its digest.
- **Its digest did not hold across a boot.** Since `V2-S6-002-PR2`: after the engine's
  virtual machine booted again, the memory figure of the identity changed, and the Q3
  characterization [`q3-1`](v2-q3/runs/q3-1/result.md) was refused on the environment.
  A further boot gave another figure: two boots were observed, and each changed it. [The Q1 page](../../environment/environment-qualification.md#the-selected-environment)
  states the reads.
- **Revision 2 states the stable identity.** Since `V2-S6-004-PR1`, [ADR 0021](../../architecture/decisions/ADR-0021-environment-identity-is-configuration-memory-is-capacity.md)
  decides that the identity states the configuration: the provider, the server version,
  each node with its kubelet version and the CPU and the pods that it allocates, and the
  CPU count of the engine. Memory is a capacity fact, which the capacity gate decides for
  each reading, and `capacity-accepted` still requires `ACCEPTED`. [Revision
  2](v2-q1/freeze-r2.v1alpha1.json) changes the identity that a record states and no
  criterion. The tool builds each record under the revision that its header names, so
  `q1-1` keeps its exact identity and its digest. Since `V2-S6-004-PR2`, `q1-2` ran under
  revision 2 (below). (Until `V2-S6-004-PR2` this item said that no qualification ran under
  revision 2.)

## The Q2 runtime startup characterization

[`v2-q2/freeze-r2.v1alpha1.json`](v2-q2/freeze-r2.v1alpha1.json) fixes Q2 before any
characterization runs. It supersedes [revision 1](v2-q2/freeze-r1.v1alpha1.json), under
which no characterization ran. Q2 measures, under revision 2 in the environment that
[`q1-1`](v2-q1/runs/q1-1/result.md) selected and under revision 3 in that of
[`q1-2`](v2-q1/runs/q1-2/result.md), the interval from the creation of each replacement runtime pod to its first Ready
condition, when the Deployment controller replaces it in a controlled restart. It runs
three restarts of the runtime Deployment, one at a time, so one characterization has six
observations. S is their maximum. The procedure is
[the driver beside it](v2-q2/procedure/q2-driver.txt), and the record is built by
[`tools/runtime_startup`](../../../tools/runtime_startup/core.py). Both are pinned inputs
of the record, and so is everything that the Q1 record pins, because the phases `up` and
`down` of the Q2 driver are those of the Q1 driver. The record states sixteen acceptance
criteria, `Q2-AC1` to `Q2-AC16`, and each is one rule of the tool, with the same
statement. [The Q2 page](../../environment/runtime-startup-characterization.md) describes
each rule.

- **It is a qualification, not an experiment.** A restart is a rollout restart of the
  runtime Deployment, carried out by the Deployment controller under the chart's rollout
  bounds. No pod is deleted by name, and no caller runs. No characterization is a result
  of E02 to E06, no run of those experiments is used as one, and no claim cites S.
- **The result is `CHARACTERIZED`, `INCONCLUSIVE`, or `REFUSED`.** Seven rules are
  preconditions: when one is not held, the result is `REFUSED`, and the driver requests no
  restart. When another rule is not held, the result is `INCONCLUSIVE`. Only a
  `CHARACTERIZED` record states S.
- **S is the maximum and not an average.** The freeze record states the rule and no
  value. Later work derives other bounds from S, and they are not part of this record.
- **Revision 1 could not be satisfied.** Revision 1 held the API Deployment to the API image manifest-list digest that the record of `q1-1` states. The phase `up` of the Q1 driver builds the API image again, and its build at the first commit of `V2-S6-002-PR1` reported another digest, `sha256:cf30eac7cc2a75f9a91dac62c8c09a6080de5b2725d2b37262c15bafe924120d`, than `q1-1` states, `sha256:5b4be2da31141bc43c0fa65133b4377ef002a3ff922278cda98ba247a244c7e1`, while the freeze tool listed no changed input of the Q1 record. So that precondition could not hold. No characterization ran under revision 1. Revision 2 holds the API Deployment to the digest that the phase `up` declared, as Q1 does, and changes no other rule, bound, or step.
- **It has its own directory.** A characterization is committed under `v2-q2/runs/q2-N/`
  with its record, whatever it shows, and the layout check lists it as a qualification.
- **The first characterization is `CHARACTERIZED`.** (Until `V2-S6-004-PR2` this item
  began "One characterization has run".) Under revision 2,
  `V2-S6-002-PR1` ran [`q2-1`](v2-q2/runs/q2-1/result.md) on 2026-10-15, at the commit
  `65bd9bb`, on the docker-desktop provider with one node, in the environment of `q1-1`.
  Each of the 16 rules held. The six intervals were 10,000 ms once and 11,000 ms five
  times, so **S = 11,000 ms**. During each, the other runtime pod was Ready, and every
  interval lies close to the probe period of 10 s.
  It is evidence at C2 of that one environment, and no claim cites it.
- **Revision 3 holds Q2 to `q1-2`.** Since `V2-S6-004-PR1`, [revision
  3](v2-q2/freeze-r3.v1alpha1.json) holds a characterization to the qualification `q1-2`
  of Q1 revision 2 and compares the stable identity of its capacity reading; the gate
  must still accept that reading. Three statements change, and no restart, measurement,
  or bound. The tool builds each record under the revision, the qualification, and the
  rules that its header names, so `q2-1` is built again unchanged. That closes the gap
  that the Q2 page stated. Since `V2-S6-004-PR2`, one characterization ran under revision
  3, [`q2-2`](v2-q2/runs/q2-2/result.md), on 2026-10-17, at the commit `28d2534`: each of
  the 16 rules held, the six intervals were each 11,000 ms, and S = 11,000 ms. (Until
  `V2-S6-004-PR2` this item said that no characterization ran under revision 3.)

## The Q3 stable caller characterization and the Q4 bounds

[`v2-q3/freeze-r1.v1alpha1.json`](v2-q3/freeze-r1.v1alpha1.json) fixes Q3 before any
characterization runs. Q3 measures, under revision 1 in the environment that
[`q1-1`](v2-q1/runs/q1-1/result.md) selected and under revision 2 in that of
[`q1-2`](v2-q1/runs/q1-2/result.md), and with the target topology healthy, what one RP-1 caller run of 360 s sees
through the API Service: the successful requests, the latency distribution, the gaps
between successive successes, and the canonical errors. G is the nearest-rank p99 of the
gaps, or the maximum gap with fewer than 100 successes. The procedure is
[the driver beside it](v2-q3/procedure/q3-driver.txt), and the record is built by
[`tools/caller_characterization`](../../../tools/caller_characterization/core.py). The
record states fourteen acceptance criteria, `Q3-AC1` to `Q3-AC14`, and each is one rule
of the tool, with the same statement. [The Q3 page](../../environment/stable-caller-characterization.md)
describes each rule.

- **It is a qualification, not an experiment.** Q3 injects no fault. Healthy is a state of
  the topology that a watch of the API pods and the runtime pods holds, not of the caller:
  a request that fails while the topology holds is counted and does not refuse. No
  characterization is a result of E02 to E06, and no claim cites G.
- **It also fixes the Q4 formulas, before G is observed.** `runtime_start_bound_ms = S`,
  `caller_gap_reference_ms = G`, `reversal_recovery_bound_ms = (2 * S) + 30000`, and
  `caller_total_unavailability_bound_ms = max(2 * G, 5000)`.
  [`tools/experiment_bounds`](../../../tools/experiment_bounds/core.py), a pinned input of
  the record, computes them from one committed `CHARACTERIZED` Q2 record and one committed
  `CHARACTERIZED` Q3 record of the same environment and release, and binds the result to
  the path and digest of each source record and of its freeze record. A bound record is
  committed as `v2-q4/bounds-rN.v1alpha1.json`, and `python -m tools.experiment_bounds
  --check` builds it again. The bounds are experiment bounds, not production SLOs.
- **The result is `CHARACTERIZED`, `INCONCLUSIVE`, or `REFUSED`.** Seven rules are
  preconditions: when one is not held, the result is `REFUSED`, and the driver starts no
  caller. When another rule is not held, the result is `INCONCLUSIVE`. Only a
  `CHARACTERIZED` record states G.
- **A record is built under the revision that its header names.** The tool registers
  each revision that a header may name, so a later revision does not refuse an earlier
  characterization when `--check` builds it again. That closes, for Q3, a gap that the Q2
  page states for Q2.
- **It has its own directory.** A characterization is committed under `v2-q3/runs/q3-N/`
  with its record, whatever it shows, and the layout check lists it as a qualification.
- **The first characterization is `REFUSED`.** (Until `V2-S6-004-PR2` this item began
  "One characterization has run".) `V2-S6-002-PR2` ran
  [`q3-1`](v2-q3/runs/q3-1/result.md) on 2026-10-16, at the commit `0307f7f`, on the
  docker-desktop provider. The phase `up` and the six other preconditions held, but the
  environment identity of the capacity reading had the digest
  `sha256:ac3a1022e86facb519bb0820b57d7a7fb32c0c6ea1011a59e88b8c1aa4efd087`, not the one
  of `q1-1`: the engine and the node reported 10,429,972,480 bytes of memory, 12,288 bytes
  more, after the engine's virtual machine had booted again. The driver started no
  caller. One further boot, which the host owner authorized, gave a third figure, so no
  further characterization was run. No G was measured, and the Q4 tool built no bound
  record. [The Q1 section](#the-q1-environment-qualification) and the Q1 page state what
  this shows about the digest of `q1-1`.
- **Revision 2 holds Q3 to `q1-2`.** Since `V2-S6-004-PR1`, [revision
  2](v2-q3/freeze-r2.v1alpha1.json) holds a characterization to the qualification `q1-2`
  and compares the stable identity of its capacity reading; the gate must still accept
  that reading. Two statements change. The rule of G and the four Q4 formulas are
  unchanged, and the Q4 tool accepts a Q2 source of revision 3 and a Q3 source of
  revision 2. It still requires the two sources to state the same provider, environment
  digest, release identifier, and qualification record, so `q2-1` is not combined with a
  characterization of `q1-2`. `q3-1` is built again under revision 1 and stays
  `REFUSED`. Since `V2-S6-004-PR2`, one characterization ran under revision 2,
  [`q3-2`](v2-q3/runs/q3-2/result.md), on 2026-10-17, at the commit `0dbea91`: each of the
  14 rules held, 153 of 153 requests succeeded in 362,958 ms, and G = 10,113 ms by the p99
  rule over 152 gaps. (Until `V2-S6-004-PR2` this item said that no characterization ran
  under revision 2 and that no bound record exists.)

### The committed bound record

Since `V2-S6-004-PR2`, [`v2-q4/bounds-r1.v1alpha1.json`](v2-q4/bounds-r1.v1alpha1.json) is
the one committed bound record. `tools/experiment_bounds` built it from `q2-2` and `q3-2`,
which state the same provider, environment, release, and qualification record, `q1-2`, and
`--check` builds it again with the same bytes.

| Bound | Formula | Value |
|---|---|---|
| `runtime_start_bound_ms` | `S` | 11,000 ms |
| `caller_gap_reference_ms` | `G` | 10,113 ms |
| `reversal_recovery_bound_ms` | `(2 * S) + 30000` | 52,000 ms |
| `caller_total_unavailability_bound_ms` | `max(2 * G, 5000)` | 20,226 ms |

These are experiment bounds of one environment. They are not service levels,
availability targets, production thresholds, or a benchmark, and no claim cites them. A
later freeze record of a reliability experiment cites them by the path and the digest of
the record, SHA-256 `542b05dd9627b25330a4602071d99276218776cf1f78a5c34ac764fbb3188116`.
Since `V2-S6-003-PR1` the [five reliability experiment
freezes](#the-reliability-experiment-freezes) cite them so.

## The reliability experiment freezes

`V2-S6-003-PR1` registered five freeze records on 2026-10-18, revision 1 each, one
for each reliability experiment, in its own directory. They fix each experiment
before its first result-bearing run. **No run of any of them exists, and nothing ran
in that change**: no Git switch, no commit to `main`, no fault, and no cluster read.

| Experiment | Record | Topology | Fault | Counted runs | Bounds in a criterion | Level |
|---|---|---|---|---|---|---|
| V2-E02A, controlled single-runtime baseline | [`v2-e02a/freeze-r1.v1alpha1.json`](v2-e02a/freeze-r1.v1alpha1.json) | 2 API, 1 runtime: the baseline release `ecc4b9cf…` | Delete the one runtime pod | 3 | None | C2 |
| V2-E02B, multi-runtime pod loss | [`v2-e02b/freeze-r1.v1alpha1.json`](v2-e02b/freeze-r1.v1alpha1.json) | 2 API, 2 runtime: the qualified release `b5457f49…` | Delete one of two runtime pods | 3 | None. The caller bound is an observation | C2 |
| V2-E02C, API pod loss | [`v2-e02c/freeze-r1.v1alpha1.json`](v2-e02c/freeze-r1.v1alpha1.json) | As V2-E02B | Delete one of two API pods | 3 | `caller_total_unavailability_bound_ms` | C2 |
| V2-E04, bad release and Git reversal | [`v2-e04/freeze-r1.v1alpha1.json`](v2-e04/freeze-r1.v1alpha1.json) | As V2-E02B | Accept a bad runtime release into `main`, then revert it | 2, and a third when the two differ in their causal signature | `caller_total_unavailability_bound_ms`, `reversal_recovery_bound_ms` | C2 |
| V2-E05, drift reconciliation | [`v2-e05/freeze-r1.v1alpha1.json`](v2-e05/freeze-r1.v1alpha1.json) | As V2-E02B | Scale the live runtime Deployment from 2 to 1, with Git unchanged | 2 | `reconciliation_bound_ms`, 210,000 ms | C2 |

Since `V2-S6-007-PR1` the latest record of V2-E02A, V2-E02B, V2-E02C, and V2-E05 is
revision 2. The latest record of V2-E04 was revision 2 from `V2-S6-005-PR1`, and since
`V2-S6-008-PR1` it is revision 3. Each revision 2 of the four differs from its revision 1
only in [its clock policy and the members that it lists](#the-clock-policy-of-rule-set-2),
revision 2 of V2-E04 also in
[its reversal timing](#the-reversal-timing-of-v2-e04-and-rule-set-3), and revision 3 of
V2-E04 differs from its revision 2 in
[the selection of the span of its recovery criterion](#the-selection-of-the-span-of-v2-e04-and-rule-set-4).
The topologies, faults, counted runs, bounds, and levels of the table are unchanged.
(Until `V2-S6-005-PR1` this paragraph said that the latest record of V2-E04 is revision
1, and until `V2-S6-008-PR1` that it is revision 2.)

A record is not evidence. It states what a run must do and what counts as a pass. Each
record states its procedure, its measurements, its criteria, each marked `validity` or
`pass`, its exclusion reasons, its abort conditions, its cleanup, its limitations, what it
does not establish, and what was known when it was written.

### One lineage, and the role of the bounds

- **The environment is that of `q1-2`.** Each record names
  [`q1-2`](v2-q1/runs/q1-2/record.v1alpha1.json) by path and digest, `QUALIFIED`, and its
  stable environment identity,
  `sha256:6a219b3ff959a0020d982d967abeed6696aa0f0d1b594bdf3ad86b9aeda8cd5c`. Each run is
  held to the capacity gate on its own reading, and its stable identity must have that
  digest. A run on another provider, node, or identity is not a run of these records.
- **The bounds are those of `bounds-r1`.** Each record names
  [`v2-q4/bounds-r1.v1alpha1.json`](v2-q4/bounds-r1.v1alpha1.json) by path and digest and
  states its four values: 11,000 ms, 10,113 ms, 52,000 ms, and 20,226 ms. They were derived
  from `q2-2` and `q3-2`, which ran on the qualified target release `b5457f49…`. The
  records state them as preregistered, shared experiment-reference bounds. They are not
  bounds of the baseline release: no characterization of the baseline exists, and no
  criterion of V2-E02A uses a bound. They are not service levels.
- **No baseline qualification is required.** The qualification and the two
  characterizations are of the target topology, and V2-E02A uses no bound. V2-E02A
  executes in the one environment that `q1-2` selected, as V2-E02B does, and its capacity
  gate decides each reading.
- **`q1-1`, `q2-1`, and `q3-1` are unchanged.** `q3-1` stays `REFUSED`, and each record
  names it in what was known.

### The controlled comparison

V2-E02A and V2-E02B state the same environment, caller profile and caller run, fault rule
and mechanism, collection, window, declaration rule, measurements, validity criteria,
outcome rules, exclusion reasons, repetition rule, abort conditions, cleanup, and evidence
layout. Their topologies differ only in four members: the runtime replica count, the
release that follows it, the runtime disruption budget, which the chart renders for two
replicas and not for one, and the statement. The release differs in the contract, `0.1.0`
and `0.2.0`, the workload version, the contract and values digests, and the release
identifier. The committed [baseline comparison record](../../environment/single-runtime-baseline-profile.md)
is `COMPARABLE` and lists those as its permitted differences. Its tool compared every other
claim-relevant input of the two sides, and both records pin it by digest.

**One Application delivers both.** The baseline is not given a second Application or a
second path. `definition.gitTransitions` of V2-E02A preregisters the switch:

1. Before the first V2-E02A run, one change merged into `main` replaces the two files of
   the desired-state path with the two files of the baseline profile, byte for byte, and
   changes no other file of the delivery path. That change registers revision 2 of the
   V2-E02A record, which classifies each moved pin, before the first run.
2. Each V2-E02A run executes at a commit whose two files have the baseline digests.
3. After the last V2-E02A run, one change restores the two files to the target digests,
   before the first V2-E02B run.

No switch is authorized by the records. Each is a commit to `main` that needs the explicit
authorization of the repository owner.

### The procedure, without a driver

**No driver exists for any of the five.** Each record states its procedure in full: the
preparation P1 to P8, with a reading of the node clock against the host clock before and
after each run, the caller run, the collection, the stable pre-fault window, the
fault steps, the observation limit, the window of the analysis, the post-recovery window,
the declaration rule of the analysis, and the cleanup C1 to C5. The material scope of each
record names its own `procedure/` directory, which does not exist at registration. A driver added there is
listed as `added` by `--changes`, so the change that adds it registers a later revision
that pins the driver and its dependencies, and that revision merges before the first
result-bearing run. A change to the caller profile, the topology, the fault, a measurement,
a window, a bound, an outcome rule, an exclusion reason, an abort condition, the cleanup, or
a criterion is material, and it is a later revision too.

- **Outcomes.** `REFUSED` when a precondition did not hold and no fault was injected;
  `ABORTED` when an abort condition was crossed, recorded with the code of that condition;
  `INCONCLUSIVE` when a validity criterion did not hold; `FAILED` when every validity
  criterion held and a pass criterion did not; and `PASSED` when every criterion held. Each
  record has a validity criterion for each stream that its criteria read, for the caller
  record, for the post-recovery window, for an unrelated failure, and for the evidence.
  V2-E02A has validity criteria only, so it is a characterization: a run of it is never
  `FAILED`.
- **Two clocks.** Under revision 1, an interval between instants of two clocks that lies
  within the clock bound of the run of a bound is neither held nor failed: the run is
  `INCONCLUSIVE` for the reason `clock-bound-reached`. Revision 2 of V2-E02A, V2-E02B,
  V2-E02C, and V2-E05, since `V2-S6-005-PR1` revision 2 of V2-E04, and since
  `V2-S6-008-PR1` revision 3 of V2-E04, replaces that rule with
  [the clock policy of rule set 2](#the-clock-policy-of-rule-set-2).
- **Repetitions.** A `PASSED` or `FAILED` run is counted and never repeated, replaced, or
  left out. A `REFUSED`, `INCONCLUSIVE`, or `ABORTED` run is kept, for one of nine
  registered exclusion reasons under revision 1, or of ten under revision 2, or of twelve under revision 2 of V2-E04, or of eleven under revision 3 of V2-E04, and the next run takes the next identifier, up to six runs
  for E02, five for E04, and four for E05.
- **The caller is the reference.** No stream, readiness state, endpoint count, replica
  count, sync state, health state, or scrape state changes a caller figure.

### What V2-E04 and V2-E05 decide before any run

- **V2-E04 measures the recovery from Git visibility to the onset of the stabilization
  span.** The analysis states `stabilizedAt` at the end of a span of at least 10 successes
  and 60 s. A recovery measured to that instant could never be within
  `reversal_recovery_bound_ms`, 52,000 ms. So `recoveryEnd` is the completion of the first
  request of the first span that then completes. Under revision 2, `reversalStart` is the
  instant at which the reversal commit is visible on the remote that the controller reads,
  judged at the earlier end of its bracket. Revision 1 started the interval at the last
  controller reading before the reversal commit was resolved, a choice made after the Q4
  values were known and governed by no change control. [The reversal timing of revision
  2](#the-reversal-timing-of-v2-e04-and-rule-set-3) states each instant. Since
  `V2-S6-008-PR1`, revision 3
  [selects that span by one preregistered rule](#the-selection-of-the-span-of-v2-e04-and-rule-set-4),
  with no onset exclusion: a valid run in which no span that starts after
  `reversalStart` completes inside the observation limit is `FAILED`. (Until
  `V2-S6-005-PR1` this bullet described revision 1 alone.)
- **V2-E04 needs a third run only for a different causal signature**: whether a container of
  a bad pod started, whether the runtime Service fell to one Ready endpoint, whether the API
  Deployment rolled out, and whether a caller failure episode started after the fault. A
  difference in a duration, or in a verdict against a bound, alone does not.
- **V2-E04's recovery holds the discovery of the reversal.** Under revision 2 the periodic
  discovery and the reconciliation of the reversal commit by the controller are system
  recovery: they are inside `recoveryMs`, and `gitopsDiscoveryMs` also reports them on
  their own. The operator interval ends at `reversalStart` and holds none of them.
  Revision 1 put the discovery in the operator interval. The record states before any run
  that most runs are not expected to meet E04-AC12. (Until `V2-S6-005-PR1` this bullet
  said that the operator interval holds the discovery.)
- **V2-E04's bad release is not implemented.** The record fixes the preferred fault: the
  same runtime image started with a model file path that does not exist. The change that
  implements it registers a later revision that pins it. When an accepted validation rule
  refuses that release before deployment, the rule is not weakened: a later revision
  selects another safe fault before any run.
- **V2-E05's bound is 210,000 ms.** It is a conservatively selected experiment threshold:
  the documented default reconciliation timeout of Argo CD, two minutes, plus its
  documented maximum jitter, one minute, plus 30 s. The pinned install sets neither key, and
  a precondition refuses a run when the live configuration sets one. Argo CD does not
  guarantee a recovery within 210,000 ms, and the record does not state that periodic Git
  polling is what restores a live drift. The earlier observation that a manual replica
  change was reverted within 2 to 4 s was known when the bound was chosen. It is stated as
  history, apart from the bound and from the result of any run.
- **V2-E05's restoration is read from the controller's streams.** It starts at the
  `fault-injection-started` event and ends at the finish of the first deployments reading
  that reports `specReplicas` 2 at a later generation, both on the clock of the collecting
  host. A pass criterion also requires an operation of the controller that started after
  the drift. No caller figure changes those verdicts. Each run keeps the two live
  ConfigMaps that the precondition read.

### The clock policy of rule set 2

`V2-S6-007-PR1` registered revision 2 of the records of V2-E02A, V2-E02B, V2-E02C, and
V2-E05 on 2026-10-18, before any run. A review of the Sprint 6 records found that the
clock statements of each revision 1 contradicted its own procedure. P8 read the node
clock against the host clock and computed a clock bound, and an outcome rule compared
intervals with that bound. The limitations and the window of the same record described
the clocks as three clocks whose difference is not read, and stated a fixed ordering
threshold of one second. Revision 2 replaces those statements with one clock policy,
`definition.clockPolicy`, which is the same in each of the four records. Revision 1 of
each is kept unchanged. **No run exists under either revision, and nothing ran in that
change.** V2-E04 stayed at revision 1 in that change. `V2-S6-005-PR1` superseded it with
the same policy, [below](#the-reversal-timing-of-v2-e04-and-rule-set-3).

**What the policy governs.** It governs each verdict instant that
`definition.criterionClocks` declares: each order of two instants and each interval that
a criterion compares with a value. It does not govern how
[`tools/reliability_analysis`](../../testing/reliability-analysis.md) puts a request in
the window by its completion instant, starts its search for a stabilized recovery at the
`fault-injection-finished` event, and holds a span to the readings that overlap it. Each
of these orders an instant of the node clock and an instant of the host clock with no
margin, and so does the check of the stable pre-fault window. Each record states this as
a limitation, and a verdict that reads such a figure reads it as the analysis states it.

**Two clocks, six sources.** The provider has one node, so the runner pod, the
Kubernetes API server, the kubelet, and the delivery controller read one clock. The
control process, the collection scripts, the operator event log, and the P8 readings run
on one host and read the other.

| Source | Clock | Resolution |
|---|---|---|
| `caller-record`: the start and the completion of each request | node | 1 ms |
| `kubernetes-timestamp`: a creation, deletion, or condition timestamp, or the start or the finish of an operation of the Application, inside a reading | node | 1,000 ms |
| `collector-reading`: the start and the finish of each read of a stream | host | 1 ms |
| `operator-event`: the `recordedAt` instant of each event. The window and the observation limit are stated from these | host | 1 ms |
| `clock-reading-host`: the two host instants of each P8 reading | host | 1 ms |
| `clock-reading-node`: the node instant of each P8 reading | node | 1 ms |

Three kinds of instant are on no source, and no verdict reads them: the evaluation and
scrape instants of the in-cluster telemetry collector, on the node clock; the
`occurredAt` instant of an operator event, on the clock that the event names, which can
be a third clock such as that of the Git host; and the instants of the Application
status other than those of an operation.

**The measurement is P8, unchanged.** P8 reads the clocks before the runner starts and
again after the window ends. Each reading is a host instant, the UTC time that a pod of
the node prints, and a second host instant, as the Sprint 5 integration validation read
them. That validation read the node instant from the node container, and a pod of the
node reads the same kernel clock. The bound formula is that of revision 1, word for
word: the largest of the two differences between the node instant and the nearer host
instant, plus the time between the two host instants. Revision 1 does not say whether
the largest difference and the time between the host instants are taken from one reading
or each over both readings. Rule set 2 states the computation: For each reading, d is
the absolute difference between the node instant and the nearer of its two host
instants, and w is the time from its first to its second host instant. The clock bound
of the run is the larger d of the start and the end reading plus the larger w of the two
readings, in milliseconds. The other reading, the larger over the two readings of d plus
w of one reading, is never larger, because the larger of d1 plus w1 and d2 plus w2 is at
most the larger d plus the larger w.

The bound is conservative to the resolution of its instants. The node instant was
printed at a host instant between the two host instants of its reading, so at that
reading the node clock less the host clock lies between the node instant less the second
host instant and the node instant less the first. Its size is at most the larger of
those two differences, which is at most d plus w. Each instant is cut to the
millisecond, so the offset can exceed the bound by less than 1 ms, and the margin below
adds at least 1 ms to the bound.

**The bound is measured at two readings only.** The clock bound is measured at the start
reading and at the end reading only. To apply it to an instant between the two readings
is an assumption: the offset between the node clock and the host clock stays inside the
clock bound between them. Each record of rule set 2 makes that assumption explicitly,
and no reading tests it. Drift between the readings is not measured. The result page
states the net change of the offset from the start reading to the end reading, and no
verdict reads it. The procedure does not synchronize the clocks, and it does not
guarantee the bound.

**An unusable reading.** A reading is unusable when it is missing, when one of its
instants is not a UTC instant to the millisecond, or when its second host instant is
before its first. An unusable start reading ends the run before the fault: no fault is
injected, and the run is `REFUSED` for `precondition-not-held`. Revision 1 stated no
outcome for an unusable reading. An unusable end reading makes the bound not computable,
and each verdict that depends on it is not judged, for the new exclusion reason
`clock-reading-missing`. Each other verdict is judged. The end-reading rule names no
state of its own: the rule below decides the state.

**A verdict that is not judged.** A verdict that is not judged is neither held nor
failed. The state of the run is computed twice from the judged verdicts: once with each
verdict that is not judged taken as held, and once with each taken as failed. When the
two states are the same, that is the state of the run. When they differ, the run is
INCONCLUSIVE for the reason of a verdict that is not judged. So a state that the judged
verdicts decide stands, and a FAILED state that they decide is never made INCONCLUSIVE.
The repository owner chose this one rule for an unusable end reading, for an order
inside the margin, and for a bound comparison inside the margin.

**Orders and bound comparisons across the two clocks use one margin**: the clock bound
of the run plus the coarser resolution of the two sources. No order is stated between an
instant of the node clock and an instant of the host clock whose difference is inside
the margin. An interval between the two clocks is compared with a bound only when it
differs from the bound by more than the margin. Inside it, the verdict is not judged,
for `clock-bound-reached`. Two instants of one clock are ordered to the coarser
resolution of their sources, so two Kubernetes timestamps of one second are not ordered,
and an interval of one clock is compared with a bound directly. This replaces the fixed
one-second rule of revision 1.

**How revision 2 judges a run otherwise than revision 1.** No criterion of the four
records compares an interval between the two clocks with a bound, so the clock-bound
rule of revision 1 had no case to apply to. Revision 2 differs in four places: the
margin replaces the fixed one-second ordering rule; an order inside the margin is not
judged and can make a run `INCONCLUSIVE` for `clock-bound-reached`, where revision 1
stated no consequence; an unusable end reading can make a run `INCONCLUSIVE` for
`clock-reading-missing`; and an unusable start reading makes a run `REFUSED`. Each
follows the rule for a verdict that is not judged.

**The clock of each instant of each criterion.** `definition.criterionClocks` names, for
each criterion that orders instants or compares an interval with a value, the source and
the clock of each instant. `definition.criteriaWithoutClocks` lists each other
criterion: the evidence criterion of each record, the manual-action criterion of V2-E02B
and V2-E05, which holds for no manual-action event at all, and the drift criterion of
V2-E05. These comparisons with a value are on one clock:

- E02C-AC10 compares `callerFailureEpisodeMs` with `caller_total_unavailability_bound_ms`,
  20,226 ms. Both ends of a closed episode are caller completions, on the node clock.
  Whether an episode near an edge of the window is in it, and is closed, follows the cut
  of the window by the analysis.
- E05-AC9 compares the restoration with `reconciliation_bound_ms`, 210,000 ms. It runs
  from the `fault-injection-started` event to the finish of a deployments reading, both
  on the host clock. The clock bound does not apply to it, and an unusable end reading
  leaves it judged.
- The 10 s between two readings of AC2 is on the host clock, and the 60 s of the
  post-recovery window is on the node clock.

The cross-clock orders are those of a caller completion or `stabilizedAt` against the
window, an event, or the observation limit, of a pod's `deletionTimestamp` against the
observation limit, and of the controller's `operationStartedAt`, to the second, against
the `fault-injection-started` event in E05-AC8. An operation that starts within the
margin of that event is not ordered with it, so E05-AC8 is then not judged.

**What else changed.** Each revision 2 differs from its revision 1 in these members
alone, and a test holds that list:

- `metadata`: the revision, the change that registered it, `supersedes`, and
  `preregistrationRules`, 2;
- `definition.limitations`: the clock limitation, rewritten to the policy, and two new
  limitations: the analysis cuts that the policy does not govern, and that no tool
  checks that a run executes the latest revision;
- `definition.history`: one new entry, for revision 2;
- `definition.preparation`: P1 gains one clause, that the record is the latest revision
  of its experiment that the freeze registry of the executing revision registers, and P8
  names the policy. No tool checks the P1 clause: the review of the run compares it;
- `definition.window.clocks` and the clock outcome rule, rewritten to the policy;
- `definition.clockPolicy`, `definition.criterionClocks`, and
  `definition.criteriaWithoutClocks`, new;
- `exclusionReasons`: `clock-bound-reached` names the margin, and `clock-reading-missing`
  is new, so each record registers ten reasons;
- for V2-E05, `definition.reconciliationTiming` names the host clock, and states that
  the clock bound does not apply to it;
- the freeze revision and `preparedFrom`, the pins, and `inputChanges`.

The pins moved for the three files of `tools/experiment_preregistration` alone. Revision
2 classifies `core.py` as material, because P1 runs the check and the check now holds
the record to its clock policy, and `__init__.py` and `__main__.py` as not material. The
supersession is stated in `metadata.supersedes` of each record; a registry row names a
path and a digest only. Every criterion, bound, window, fault, topology, repetition
rule, abort condition, cleanup step, and evidence path is that of revision 1. The
[baseline comparison record](../../environment/single-runtime-baseline-profile.md) is
unchanged: it names no freeze record, and both revisions 2 state its digest.

**V2-E04 revision 1.** Until `V2-S6-005-PR1` it was the latest V2-E04 record, read under
rule set 1, with clock statements that contradict its P8. Revision 2 supersedes it and
classifies the three files of the check that differ from its pins. (Until
`V2-S6-005-PR1` this paragraph said that no revision classifies them.)

**These four records since `V2-S6-005-PR1`.** That change edited `core.py` of the check
again, to add rule set 3, after these four records had pinned it. `--changes` lists it as
changed for each of them, no revision classifies it, and the P1 of each refuses a run
until a later revision of it classifies the file. Rule set 2 itself is not edited, so the
check reads each of them as before. No run of any of them is authorized yet.

### The reversal timing of V2-E04, and rule set 3

`V2-S6-005-PR1` registered revision 2 of the record of V2-E04 on 2026-10-19, before any
run. A review of the Sprint 6 records found that revision 1 started its recovery interval
at a controller observation, counted the discovery of the reversal commit by the
controller as operator time, and ended the interval at the start of the stabilization
span. Revision 1 made those choices after the Q4 values were known, and no change control
governed them. The repository owner amended the definition of the reversal timing by
change control on 2026-10-18, also after the Q4 values were known and before any run of
V2-E04. Revision 2 applies it, with the clock policy of rule set 2 byte for byte.
Revision 1 is kept unchanged. **No run exists under either revision, and nothing ran in
that change.**

**The instants.** Each names its source and its clock in the inventory of the policy.

| Instant | Source and clock | What it is |
|---|---|---|
| `reversalStart` | operator event, host | The instant at which the reversal commit is visible as the head of `main` on the remote that the controller reads. Its bracket runs from the record of `reversal-created`, which the operator takes immediately before the push, to the first read of that remote that reports the commit, after which the operator records `reversal-accepted`. It is judged at the earlier end, so the recovery is not understated. It is not a controller observation. |
| `controllerObserved` | collector reading, host | The first argo reading that reports the reversal commit as `resolvedRevision`. Its earliest instant is the start of the last argo reading that reports another revision, and its latest is its own finish. |
| `desiredStateRestored` | collector reading, host | The finish of the first argo reading that reports the reversal commit as `resolvedRevision` and `Synced`. The deployments stream states no pod template, so the known-good template is read from the controller's `Synced` report at a commit whose files are the known-good ones. |
| `stabilizationOnset` | caller record, node | `stabilizedRecovery.span.first.finishedAt` of the run analysis: the completion of the first request of the first stabilization span that is then observed complete without interruption. `recoveryEnd` is this instant. |
| `stabilizedAt` | caller record, node | `stabilizedRecovery.stabilizedAt`: the completion of the request that completes that span. A recovery counts only when it lies inside the observation limit, and the post-recovery window that E04-AC5 judges follows it. |

**The intervals.** Each names its start and its end.

| Interval | From | To | Use |
|---|---|---|---|
| `recoveryMs` | `reversalStart` | `stabilizationOnset` | Judged by E04-AC12. System recovery, with the discovery and the reconciliation by the controller in it. From the host clock to the node clock. |
| `gitopsDiscoveryMs` | `reversalStart` | `controllerObserved` | Reported, with an inner and an outer figure. It is inside `recoveryMs`. Host clock. |
| `operatorDecisionMs` | `detection-reviewed` | `reversalStart` | Reported. The human interval, with no discovery, reconciliation, or stabilization in it. Host clock. |

The four operator events of the reversal, `detection-reviewed`, `reversal-decided`,
`reversal-created`, and `reversal-accepted`, keep their own instants.

**The criteria.** E04-AC12 judges `recoveryMs` against `reversal_recovery_bound_ms`,
52,000 ms, the value of the formula `(2 * S) + 30000` in `bounds-r1`, and it states the
value, the formula, and the bound record with its digest. No Q4 formula, value, source, or
digest changes. The interval runs between the two clocks, so the comparison follows the
policy: inside its margin it is not judged, for `clock-bound-reached`. E04-AC8 ended its
window at `reversalStart` under revision 1. Revision 2 moves `reversalStart` earlier, so
E04-AC8 now ends its window at `desiredStateRestored`, or at the end of the window when
that is not established. The argo reading that establishes it finishes after the instant
at which revision 1 ended the window, so no containment window is shorter than under
revision 1.

**When an instant is not established.**

- No span completes, or `stabilizedAt` lies outside the observation limit: recovery is
  not established, and E04-AC12 is not met. An interrupted span establishes no recovery,
  because the analysis states only a span that completed.
- No read of the remote reports the reversal commit inside the observation limit, or
  the transcript holds no such read ahead of `reversal-accepted`: `reversalStart` is not
  established, and E04-AC12 is not judged, for the new reason
  `reversal-start-unconfirmed`.
- The span of the analysis does not start after `reversalStart`. The analysis searches
  from the `fault-injection-finished` event. A span holds at least one argo reading that
  reports the reversal commit with `Synced`, but the requests between the last argo
  reading that does not and `reversalStart` can start one. That needs the controller to
  resolve and sync the commit within about one reading of the push. No figure then
  states the span that the amended definition names, and E04-AC12 is not judged, for the
  new reason `recovery-onset-not-after-reversal`. **This reason is a rule of the record,
  chosen before any run, and not of the amended definition**, which would take the first
  span that starts after `reversalStart` and then completes; no tool computes it. So it
  can make `INCONCLUSIVE` a run that the amended definition would judge `PASSED`, or, when
  no such span starts within 52,000 ms of `reversalStart`, `FAILED`. The record states this
  as a limitation. (Since `V2-S6-008-PR1` this bullet describes revision 2 alone. The
  collective re-review of the Sprint 6 records on 2026-10-19 found the reason
  unauthorized, and revision 3 removes it:
  [the selection of the span](#the-selection-of-the-span-of-v2-e04-and-rule-set-4) states
  what replaces it.)

When E04-AC12 is not judged, the rule of the policy for a verdict that is not judged
decides the state, so a `FAILED` state that the judged containment criteria decide stands.

**The detection rule changes the procedure.** Its threshold, 22,000 ms, is unchanged.
The age that it reads runs from a Kubernetes timestamp, on the node clock to the second,
to a reading, on the host clock. It is an operator rule and not a verdict. Revision 1
declared detection at the first pods reading with an age of at least 22,000 ms. Revision
2 declares it at the first reading whose age exceeds 22,000 ms by more than the margin of
the policy, as far as it is known during the run: d plus w of the start reading of P8
alone, plus 1,000 ms, because the end reading follows the window. So detection, and with
it the reversal, can come later than under revision 1, by up to that margin plus one
reading interval. That leaves the bad rollout exposed to the containment criteria for
longer, and leaves less of the observation limit. The result page states the margin of
the run.

**What else changes.** As in the four records of rule set 2: P1 gains the
latest-revision clause, P8 names the policy, `definition.window.clocks` and the clock
outcome rule are rewritten, the reason `clock-bound-reached` names the margin, the clock
limitation is rewritten, and the analysis and latest-revision limitations are added.
Beyond them, the hypothesis no longer calls the bound an expected observation, and T3
states when the operator records `reversal-created` and `reversal-accepted` around the
push and the confirming read. The limitation that put the discovery in the operator
interval is replaced, and four limitations are added for the reversal timing, among them
the one for `recovery-onset-not-after-reversal`: six limitations are added in all. The
history gains four entries, and one measurement and one outcome rule are added. The
exclusion reasons gain `clock-reading-missing`, `reversal-start-unconfirmed`, and
`recovery-onset-not-after-reversal`, twelve in all. Every other member is that of revision
1: the fault, the topology, the containment criteria E04-AC9 to E04-AC11 and E04-AC13, the
repetitions, the third-run signature, the bounds of the window and the observation limit,
the abort conditions, the cleanup, and the evidence paths. The pins moved for the three files of the check alone, and revision 2
classifies `core.py` as material and the other two as not.

**The expected consequence, stated before any run.** A span cannot hold the reversal
commit before the controller reports it, and the procedure permits no manual refresh. So
`recoveryMs` holds the periodic discovery of the controller, whose documented default
basis, as revision 2 of V2-E05 takes it, is a 120,000 ms timeout plus up to 60,000 ms of
jitter. Most runs are not expected to meet E04-AC12. Such a run is `FAILED`, counted, and
kept, and `gitopsDiscoveryMs` states why. The bound is not relaxed because of an expected
or an observed failure.

**Rule set 3.** Revision 2 states rule set 3. Rule set 3 holds every rule of rule set 2,
unchanged, so the clock policy of revision 2 is held exactly as in the four records of
rule set 2, and its text is theirs byte for byte. Where that text names rule set 2, it
names the rules that a record of rule set 3 also holds. Rule set 3 adds four rules that
read a V2-E04 record, and a V2-E04 record after revision 1 must state rule set 3 or later,
so a later revision cannot leave the timing rules by stating rule set 2. Rule set 2 is not
edited: each record registered under it reads as before.

### The selection of the span of V2-E04, and rule set 4

`V2-S6-008-PR1` registered revision 3 of the record of V2-E04 on 2026-10-20, before any
run. The collective re-review of the Sprint 6 records on 2026-10-19 found that revision 2
adds the exclusion reason `recovery-onset-not-after-reversal`, which the amended
definition of the reversal timing does not authorize. The definition takes the first
stabilization span that starts after `reversalStart` and then completes. Revision 2 left
E04-AC12 not judged instead when the span of the run analysis, which searches from the
`fault-injection-finished` event, does not start after `reversalStart`, so it could make
`INCONCLUSIVE` a run that the definition judges `FAILED`. Revision 3 removes the reason,
and every statement of it, and selects that span by one preregistered rule. Revision 2
and its registry row are kept unchanged, and its digest is
`fae41b8b244cda76e1325ff36e305705d620163bcfac8c1e7bffec2c61b1e619`. Revision 3 has the
digest `c95186c6ef1bb7034c71ef6a8e39ed3a92dd1a265497d11d2f99d570fc81ce29`. **No run exists under any revision, and nothing ran in that
change.**

**The selection**, `definition.reversalTiming.selection`:

| Member | What it states |
|---|---|
| Candidates | The caller completions of the window after `reversalStart`, in completion order. A span that continues across `reversalStart` is a candidate from its first request after it. |
| Span rule | `_find_span` of `tools/reliability_analysis`, unchanged: consecutive successful completions, at least 10 of them over at least 60,000 ms, each condition held, at least one reading of each condition inside the span, and the reversal commit as the expected desired revision. A failed completion ends a candidate span, so an interrupted span is not selected and the next span that completes can be. |
| `stabilizationOnset` and `stabilizedAt` | The completion of the first and of the last request of the first span that the rule finds over the candidates and that completes inside the observation limit, 1,680 s after `fault-injection-finished`, which is unchanged. |
| Before `reversalStart` | A span, or the part of a span, that starts before `reversalStart` is never selected and is never a reason for a verdict. |
| Two clocks | `reversalStart` and the end of the observation limit are host instants, and a completion is a node instant. Inside the margin of the policy each of the two orders is resolved both ways. The selection is made once over the completions not ordered before `reversalStart`, where a completion inside the margin counts as after it, `margin-as-after`, and once over the completions ordered after it, `margin-as-before`. `stabilizedAt` inside the margin counts once as inside the limit and once as outside it. When every resolution gives one verdict, that is the verdict of E04-AC12. When they differ, E04-AC12 is not judged, for `clock-bound-reached`, and `definition.clockPolicy.notJudged` decides the state. |
| The reported span | When the resolutions select different spans and give one verdict, `stabilizationOnset`, `stabilizedAt`, `recoveryMs`, the post-recovery window, and E04-AC5 use the span of `margin-as-before`, which does not understate `recoveryMs`. When it selects no span, they use the span of `margin-as-after`. |
| An unusable end reading of P8 | Only the verdicts that depend on the clock bound are not judged, for `clock-reading-missing`. With no bound no completion can be held before `reversalStart`, so every completion of the window is a candidate, and when no span completes over them, E04-AC12 does not depend on the bound and is not met. |

**The outcome rules.** E04-AC12 stays a pass criterion with its bound, 52,000 ms, its
formula, `(2 * S) + 30000`, and the digest of `bounds-r1`. When `reversalStart` is
established and no span that starts after it completes inside the observation limit,
recovery is not established, and E04-AC12 is not met: a valid run with no such span is
`FAILED`. When `reversalStart` is not established, E04-AC12 is not judged, for
`reversal-start-unconfirmed`. The reasons that can leave E04-AC12 not judged are exactly
`reversal-start-unconfirmed`, `clock-bound-reached`, and `clock-reading-missing`. A
`FAILED` state that the judged verdicts decide stands. The validation record lists
[every path by which a run whose `reversalStart` is established can be `INCONCLUSIVE`](../environment/v2-s6-008-pr1-validation.md#every-path-to-inconclusive-once-reversalstart-is-established),
and none depends on whether a span starts before `reversalStart`. One of them is
inherited from revision 1 unchanged: E04-AC2, a validity criterion, requires an argo
reading that reports the reversal commit inside the observation limit, so a run in which
the controller never resolves the commit is `INCONCLUSIVE` and not `FAILED`.

**The outcome reference.** [`tools/reversal_outcome`](../../../tools/reversal_outcome/core.py)
is one pure function, `reversal_outcome`, that applies the selection and the outcome
rules of revision 3 to declared inputs: whether `reversalStart` is established and its
instant, the clock bound and the resolution that give the margin, whether the end reading
of P8 is usable, the caller completions and the condition series, the ends of the
observation limit and of the window, the bound, and the verdict of every other criterion.
It returns the verdicts of E04-AC12 and E04-AC5, the reason of a verdict that is not
judged, the reported span, and the state. It reads no run directory and runs nothing. It
imports `_find_span` of `tools/reliability_analysis` and copies none of it, which couples
it to the private completion and series types of that tool. Revision 3 names it in its
material scope and pins it. No code computes the selection from the evidence of a run:
code that does is pinned by a revision of the record registered before the first
result-bearing run, and until then the review of each run computes the selection by hand
and checks it with the reference. The absence of a tool is never a reason to leave
E04-AC12 not judged. The default-lane suite
[`tests/testing/test_reversal_outcome.py`](../../../tests/testing/test_reversal_outcome.py)
holds it to each case that the record names, on synthetic runs built in memory.

**What else changes.** `stabilizationOnset` loses the member of the run analysis that it
was read from and the member of the exclusion, and names the selection. `stabilizedAt`,
the observation-limit sentence of `definition.observation`, the post-recovery window, and
E04-AC5 name the selected span; the thresholds and the condition of E04-AC5 are
unchanged, and with no selected span it holds, as under revision 2. E04-AC12 replaces
its clause that the criterion is not judged when the onset does not follow
`reversalStart` with the clause for a run with no span after it. Five criterion clocks
change: the two of E04-AC5 and the interval of E04-AC12 name the selected span, the order
of E04-AC12 and `reversalStart` now orders each candidate completion, and both orders of
E04-AC12 are resolved both ways. The outcome rule of the timing is rewritten, the reason
is removed, eleven in all, the limitation of the reason is replaced by four limitations
of the selection, eighteen in all, and the history gains three entries. The material
scope gains the outcome reference, and the pins move for `core.py` of
`tools/experiment_preregistration`, material, and for the two files of the reference.
Every other member is that of revision 2, the clock policy byte for byte: `reversalStart`,
`controllerObserved`, `desiredStateRestored`, the intervals, the operator events, the
detection rule, E04-AC1 to E04-AC4, E04-AC6 to E04-AC11, E04-AC13, the observation
limit, the windows, the abort conditions, the cleanup, the evidence paths, the
repetitions, and the executables.

**The limitations of the selection.** The span rule holds a span to the readings that
overlap it across the two clocks with no margin, as before. A reading that does not hold
a condition blocks a span only until that reading finishes, so a span can start up to one
reading interval of the argo stream before the first reading that holds the reversal
commit, and `recoveryMs` can be understated by up to that interval. Inside the margin the
selection is made under each resolution, and different verdicts leave E04-AC12 not
judged. No tool computes the selection from the evidence of a run at registration.

**The expected consequence is unchanged.** Most runs are not expected to meet E04-AC12.
Such a run is `FAILED`, counted, and kept, and `gitopsDiscoveryMs` states why.

**Rule set 4.** Revision 3 states rule set 4. Rule set 4 holds every rule of rule set 2,
unchanged, `prereg-reversal-intervals` and `prereg-reversal-criteria` of rule set 3,
unchanged, the parts of `prereg-reversal-instants` that hold `reversalStart`,
`controllerObserved`, `desiredStateRestored`, the source and the clock of each instant,
the observation limit of `stabilizedAt`, and `recoveryEnd`, and the part of
`prereg-reversal-reasons` that holds `reversal-start-unconfirmed`, each unchanged. It
adds five selection rules: `prereg-reversal-selection`, `prereg-reversal-onset-exclusion`,
`prereg-reversal-unmet-recovery`, `prereg-reversal-selected-span`, and
`prereg-reversal-outcome-reference`. Rule set 3 is not edited, so revision 2 reads
exactly as before, and the check reads rule set 3 and rule set 4 by separate gates, so
that rule set 4 inherits no requirement of the onset reason or of its member. A V2-E04
record after revision 2 must state rule set 4 or later. That widens the statement of
`prereg-rule-set-unknown`, and it is the one widened statement. The check does not
import `tools/reversal_outcome`, so the pins of the records that do not name it do not
gain it.

### The check

```sh
uv run --locked python -m tools.experiment_preregistration --check
```

[`tools/experiment_preregistration`](../../../tools/experiment_preregistration/core.py)
reads the latest record of each of the five experiments and compares it with the
qualification, the bound record, and the baseline comparison that it names, and with the
other records. It reads each record under its own rule set: a revision-1 record of
`V2-S6-003-PR1` states none and is read under rule set 1, the first twelve rules below,
and every later revision states its rule set in `metadata.preregistrationRules`. Rule set
2 adds the five clock rules, and `prereg-rule-set-unknown` refuses a record that states
no known rule set. Rule set 3 holds rule set 2 and adds the four reversal-timing rules,
which read a V2-E04 record, and a V2-E04 record after revision 1 must state rule set 3 or
later. Rule set 4 replaces the onset exclusion of rule set 3 with five selection rules,
and a V2-E04 record after revision 2 must state rule set 4 or later. (Until
`V2-S6-005-PR1` there were two rule sets and eighteen rules, and until `V2-S6-008-PR1`
three rule sets and twenty-two rules.) It also checks each superseded revision alone, under its own
rule set, except for the two clauses that compare a record with the present: that its
bound record is the latest committed, and that its qualified release is that of the latest
V2-E02B. Those two clauses are the one narrowing of a revision-1 check, and it applies
only to a superseded revision. Today it prints `PASSED: 5 experiment record(s) and 6 superseded revision(s),
every rule held`. It exits 0 when every rule holds and 1 when one does not, so a run can use
it as a precondition. It reads files and writes none. Each record pins it. The default-lane
suite [`tests/testing/test_experiment_preregistration.py`](../../../tests/testing/test_experiment_preregistration.py)
runs it and plants each defect below in a copy.

| Rule | Statement |
|---|---|
| `prereg-record-missing` | Each of the five experiments has a committed freeze record in its directory, and the record names that experiment. |
| `prereg-record-shape` | A record answers each field that this check reads with one value, and each member that it reads has the type that the check reads. |
| `prereg-qualification-incompatible` | The qualification that a record names is committed with the stated digest, is QUALIFIED, and states the provider, the environment digest, the identity revision, the server version, the node count, the freeze record, and the release that the record states. |
| `prereg-bounds-stale` | The bound record that a record names is the latest committed one, has the stated digest, and states the four bounds of the record with the same names, formulas, and values. |
| `prereg-bounds-incompatible` | The bound record states the environment, the qualification, and the release that the record states. |
| `prereg-criterion-bound-unknown` | A criterion that names a bound names a bound of the record and states its value as a whole figure in milliseconds. |
| `prereg-reconciliation-bound-differs` | The reconciliation bound of V2-E05 is the sum of its three registered components. |
| `prereg-shared-differs` | The five records state one environment, one caller profile, one intended level, and one bound record with its bounds. Every record of rule set 2 states one clock policy. V2-E02A and V2-E02B state every shared field, definition, clock policy, validity criterion with its clocks, and exclusion reason alike. |
| `prereg-baseline-difference-unpermitted` | The topology of V2-E02A differs from that of V2-E02B only in the permitted members. The replica counts and the release of each side are those of the committed COMPARABLE baseline comparison and of the pinned desired-state files, and each disruption budget is the one the chart renders for its replica count. |
| `prereg-target-topology-differs` | V2-E02C, V2-E04, and V2-E05 state the topology of V2-E02B. |
| `prereg-executable-unpinned` | A record lists at least one executable, each is a pinned input, the entry file of a tool has its entry module in the material scope, and the scope names this check, the record's procedure directory, the qualification, and the bound record. |
| `prereg-exclusion-reasons-unsupported` | A record registers exclusion reasons for its own experiment, in the form that the aggregate reads. |
| `prereg-rule-set-unknown` | A revision-1 record of V2-S6-003-PR1 states no rule set and is read under rule set 1. Every other record states a rule set of 2 or later that this check knows, a V2-E04 record after revision 1 states rule set 3 or later, and a V2-E04 record after revision 2 states rule set 4 or later. |
| `prereg-clock-inventory` | A record of rule set 2 states the node clock and the host clock, and each instant source with the clock and the resolution of rule set 2. Each criterion entry of definition.criterionClocks names a criterion of the record and two instants, each with a source and a clock of the inventory, and is cross-clock exactly when the inventory puts its sources on two clocks. Each criterion declares clocks or is listed in definition.criteriaWithoutClocks, and not both. Each criterion that names a bound declares the clocks of its interval. |
| `prereg-clock-measurement` | A record of rule set 2 has a P8 that reads the clocks before the runner starts and after the window ends and states the bound formula of revision 1, and its clock policy measures with P8, a start and an end reading of three instants, and the bound formula and the computation of rule set 2. |
| `prereg-clock-rules` | The clock policy of a record of rule set 2 states the offset-stability assumption, refuses a run with an unusable start reading before the fault, leaves the bound not computable after an unusable end reading with the state that the rule for a verdict that is not judged decides, applies that rule of rule set 2, and orders and compares instants of two clocks with the margin and the words of rule set 2. |
| `prereg-clock-reasons` | A record of rule set 2 registers clock-reading-missing and clock-bound-reached for INCONCLUSIVE, and its outcome rules name both. |
| `prereg-clock-contradiction` | No text of a record of rule set 2 states that the clock difference is not measured, orders instants by a time in a sentence that does not name the margin of rule set 2, names synchronization or a guarantee in a sentence with no negation, or states that every run is INCONCLUSIVE, in the phrases that this check names. |
| `prereg-reversal-instants` | A V2-E04 record of rule set 3 or 4 names reversalStart, controllerObserved, desiredStateRestored, stabilizationOnset, and stabilizedAt, each with its source and clock. reversalStart is the Git-visibility instant of an operator event, bracketed and judged at the earlier end, and it leaves E04-AC12 not judged when it is not established. stabilizedAt lies inside the observation limit, and recoveryEnd is stabilizationOnset. The definition of reversalStart and its two bracket ends hold the phrases that this check names. Under rule set 3, stabilizationOnset is also read from stabilizedRecovery.span.first.finishedAt of a span that completed, and follows reversalStart, stabilizedAt is read from stabilizedRecovery.stabilizedAt, and the definition of stabilizationOnset holds the phrases that this check names. No other prose is read. |
| `prereg-reversal-intervals` | A V2-E04 record of rule set 3 or 4 states recoveryMs from reversalStart to stabilizationOnset, judged by E04-AC12, gitopsDiscoveryMs from reversalStart to controllerObserved, and operatorDecisionMs from detection-reviewed to reversalStart, each reported, and keeps the instants of the four operator events of the reversal. |
| `prereg-reversal-criteria` | In a V2-E04 record of rule set 3 or 4, E04-AC12 judges recoveryMs against reversal_recovery_bound_ms with the value, the formula, and the bound record of derivedNumericBounds, and declares that interval cross-clock, from reversalStart on the host clock to stabilizationOnset on the node clock. E04-AC8 ends its window at desiredStateRestored. Each of the two criteria is stated once. |
| `prereg-reversal-reasons` | A V2-E04 record of rule set 3 registers reversal-start-unconfirmed and recovery-onset-not-after-reversal for INCONCLUSIVE, and its outcome rules name both. A V2-E04 record of rule set 4 registers reversal-start-unconfirmed for INCONCLUSIVE, and its outcome rules name it. |
| `prereg-reversal-selection` | A V2-E04 record of rule set 4 selects the span of E04-AC12 in definition.reversalTiming.selection: the candidates are the caller completions after reversalStart, the span rule is _find_span of tools/reliability_analysis, unchanged, with 10 successes over 60,000 ms, stabilizationOnset is the first and stabilizedAt the last request of the first span that it finds, inside the observation limit of 1,680,000 ms after fault-injection-finished, which definition.observation states, and a span or the part of a span that starts before reversalStart is never selected and never a reason for a verdict. The order of a candidate and reversalStart, and that of stabilizedAt and the end of the observation limit, are each resolved both ways inside the margin, and different verdicts leave E04-AC12 not judged, for clock-bound-reached, with the state that definition.clockPolicy.notJudged decides. The reported span is that of the resolution that counts only the completions ordered after reversalStart, and otherwise that of the other one. An unusable end reading leaves not judged only the verdicts that depend on the bound, and with no span that completes the criterion is not met. stabilizationOnset names the selection and no member of the run analysis, and its definition holds the phrases that this check names. |
| `prereg-reversal-onset-exclusion` | A V2-E04 record of rule set 4 registers no recovery-onset-not-after-reversal, names it in no outcome rule, criterion, criterion clock, or member of the reversal timing, and has no notAfterReversalStart member. The only reasons for which a member, a registered reason, or an outcome rule leaves E04-AC12 not judged are reversal-start-unconfirmed, clock-bound-reached, and clock-reading-missing. No outcome rule, criterion, or criterion clock states that the onset or a span does not follow reversalStart, in the phrases that this check names, no criterion clock of E04-AC12 orders stabilizationOnset, and each order of E04-AC12 is resolved both ways. |
| `prereg-reversal-unmet-recovery` | In a V2-E04 record of rule set 4, E04-AC12 is a pass criterion, and it and the outcome rules state that when reversalStart is established and no span that starts after it completes inside the observation limit, the criterion is not met. E04-AC12 states that it is not judged, for reversal-start-unconfirmed, when reversalStart is not established. |
| `prereg-reversal-selected-span` | In a V2-E04 record of rule set 4, stabilizedAt names the selection and no member of the run analysis, and the definitions of stabilizedAt, of the observation limit, and of the post-recovery window, and E04-AC5, a validity criterion, each name the selected span and not the stabilized recovery that the analysis states. |
| `prereg-reversal-outcome-reference` | A V2-E04 record of rule set 4 names the outcome reference, reversal_outcome of tools.reversal_outcome.core, in its selection, names that module in its material scope and pins its file, and states that code which computes the selection from the evidence of a run is pinned before the first result-bearing run. |

### What is enforced, and what is not

Enforced in the default lane: every rule above and every rule of the freeze check, over
the committed records. Not enforced:

- **That a run follows the procedure.** No driver exists, and no code computes a verdict
  or holds a declaration to the rule of its record. The review of each run compares them.
- **That a pinned input is unchanged.** As for every record, `--changes` lists a moved
  input, and the run refuses to start until a merged revision classifies it.
- **That the comparison record stays as pinned.** When a change regenerates it, the check
  refuses until revisions of V2-E02A and V2-E02B name the new digest. This is deliberate:
  the comparison rests on that record.
- **That the scope is complete.** A test holds each pin list equal to its material scope
  at registration. A file added to a scope later moves that test, and the change owes a
  revision.
- **That a statement of a record is right.** The check compares values. It does not judge
  a procedure, a criterion, or a limitation. The `statement` member of a topology is free
  text that it compares with nothing, and a criterion that names a bound is held to state
  the figure, not to say what it says about it.
- **That an abort code or a fault code is recorded.** The records register the codes. No
  check compares a recorded code with them.
- **That a run executes the latest revision of its experiment.** P1 of each revision 2
  states it. No tool checks it: the review of the run compares it.
- **That the offset stays inside the bound between the two readings.** It is an
  assumption that each revision 2 states. No reading tests it, and drift is not measured.
- **That a text means what the policy says.** The contradiction rule reads phrases. A
  sentence that names synchronization or a guarantee and holds a negation anywhere is not
  refused, and neither is a paraphrase that no phrase names, such as "the two clocks
  agree". Tests hold four such gaps.
- **That a criterion listed without clocks orders no instant.** The check requires each
  criterion either to declare its clocks or to be listed in
  `definition.criteriaWithoutClocks`, and it requires the clocks of the interval of each
  criterion that names a bound. Whether a listed criterion truly orders no instant, and
  whether an entry names every order that a criterion states, is the record's statement.
- **How the analysis orders node and host instants.** The window, the stabilization
  search, and the span overlap of `tools/reliability_analysis` order instants of the two
  clocks with no margin. The policy does not govern them, and each record says so.
- **V2-E04 revision 1 is read under rule set 1.** Its clock statements still contradict
  its P8, and its timing is the one that the repository owner amended. Revision 2
  supersedes it, and no run uses it. (Until `V2-S6-005-PR1` this bullet said that its
  statements contradict P8 until a later revision supersedes it.)
- **That a run computes the reversal timing as the record states it.** The timing rules
  read the structure of a record: its instants and their sources, its intervals and their
  ends, E04-AC8, E04-AC12, and the reasons. Of its prose they read only the phrases that
  the check names in four texts: the definition of `reversalStart`, its two bracket ends,
  and the definition of `stabilizationOnset`. A text that holds them can still say
  something else. No tool computes `reversalStart`, `controllerObserved`,
  `desiredStateRestored`, or the three intervals. The review of each run computes them
  from the evidence.
- **That the operator records `reversal-created` immediately before the push.** The
  record states it. The event log does not check it, and no reading compares the record
  with the push. The time between them is inside `recoveryMs`, so it can lengthen the
  interval and cannot shorten it.
- **That `desiredStateRestored` reads the template of the Deployment.** It reads the
  `Synced` report of the controller at the reversal commit. No stream states a pod
  template of a Deployment.
- **That the four records of rule set 2 can be run.** Since `V2-S6-005-PR1`, `core.py`
  differs from the pin of each, and its P1 refuses a run until a later revision of it
  classifies the file. `V2-S6-008-PR1` moved it again.
- **That a run selects the span as revision 3 states it.** The selection rules read the
  structure of the selection, the members of the selected span, the criteria, the
  criterion clocks, the outcome rules, and the reasons. They read prose for the phrases
  that they name: the definition of `stabilizationOnset`, the clause of E04-AC12 and of the
  outcome rules for a run with no span after `reversalStart`, the selected span in four
  texts, the two-way resolution in each order of E04-AC12, the evidence-computation rule,
  and a statement that the onset or a span does not follow `reversalStart`, in the forms
  `does not follow`, `does not start after`, and `does not come after`. A paraphrase of
  the onset exclusion that no form names is not refused. No code computes the selection
  from the evidence of a run: the outcome reference applies it to declared inputs, and the
  review of each run declares them.
- **That the outcome reference is the one that a run uses.** Revision 3 pins it, and a
  later revision that pins code which computes the selection from evidence must pin that
  code before the first result-bearing run. No check compares a run's selection with the
  reference.

## The analysis experiment freezes

`V2-S6-006-PR1` registers revision 1 of two more freeze records:
[`v2-e03/freeze-r1.v1alpha1.json`](v2-e03/freeze-r1.v1alpha1.json), V2-E03, signal
truthfulness, and [`v2-e06/freeze-r1.v1alpha1.json`](v2-e06/freeze-r1.v1alpha1.json),
V2-E06, reliability resource and cost overhead. Neither experiment injects a fault or
starts a caller. Each reads the stored evidence of the runs of other experiments, its
**sources**. So each record fixes, before any source run exists, which runs it reads, what
it reads from them, and how it computes. No source run and no figure of either experiment
exists, and nothing ran in that change. Part of the V2-E03 computation exists:
`tools/reliability_analysis` computes some figures of one run for a signal of one timeline
stream and one tier. The rest of each analysis does not exist.

The repository owner decided on 2026-10-18 that V2-E03 and V2-E06 each have their own
freeze record before any source run. That decision was due before Sprint 6 began, and it
was made after the Sprint 6 changes had merged. Each record states the late date, and does
not change or waive it. The freeze record of the external review experiment, V2-E07, is
not part of this change.

### One binding to the sources

Each record names each of its sources in `definition.sources` by the path, the revision,
and the content digest of its latest registered freeze record:

| Record | Source | Role | Revision | Registered digest |
|---|---|---|---|---|
| V2-E03 | V2-E02A | initial | 2 | `edd57be9aca1574d975592f3152c6ad67acfcfd705c4d6478c96a56f5faa4562` |
| V2-E03 | V2-E02B | initial | 2 | `be4cc00beaa93fee52eb1625fd6c71a1ff31bade06cd726a9d7958fa44a94e0c` |
| V2-E03 | V2-E02C | initial | 2 | `abcf6af5e3d3c050df5b028ac94163c6bda9de5ee1bfe557fe725de87ea3a818` |
| V2-E03, revision 1 | V2-E04 | extension | 2 | `fae41b8b244cda76e1325ff36e305705d620163bcfac8c1e7bffec2c61b1e619` |
| V2-E03, revision 2 | V2-E04 | extension | 3 | `c95186c6ef1bb7034c71ef6a8e39ed3a92dd1a265497d11d2f99d570fc81ce29` |
| V2-E06 | V2-E02A | baseline | 2 | `edd57be9aca1574d975592f3152c6ad67acfcfd705c4d6478c96a56f5faa4562` |
| V2-E06 | V2-E02B | target | 2 | `be4cc00beaa93fee52eb1625fd6c71a1ff31bade06cd726a9d7958fa44a94e0c` |

Revision 2 of V2-E03, registered by `V2-S6-008-PR1` on 2026-10-20, binds revision 3 of
V2-E04 by path, revision, content digest, and rule set, 4, and keeps the three other
bindings of revision 1. Each binding of a revision after 1 states the rule set of the
record that it binds. (Until `V2-S6-008-PR1` the table named the V2-E04 binding of
revision 1 alone.)

Each record also states the environment, the caller profile, the topology, the fault, the
repetition count, and the bound record of each source, as that source states them, and
`definition.sourceClockPolicy.sha256`, the SHA-256 of the one clock policy that every
source states, in canonical JSON. The material scope of each record names every revision
file of each source, `freeze-r*.v1alpha1.json`, so
`python -m tools.experiment_freeze --changes` lists a later source revision as added, and
the check refuses a binding that is not the latest revision. **A run under a later source
revision is not in the population of either record until a later revision of that record
binds the source revision.** The sources will need such revisions before their first run:
each owes its driver, and four of them owe a classification of a moved pin ([see the
readiness review](../environment/v2-s6-008-pr1-validation.md#the-consolidated-pre-run-readiness-review),
which since `V2-S6-008-PR1` supersedes
[the review of `V2-S6-006-PR1`](../environment/v2-s6-006-pr1-validation.md#the-consolidated-pre-run-readiness-review)
for the records that it moves).
So the first analysis of each experiment is expected to run under a later revision of its
record, which also pins the analysis code.

### V2-E03: which signals state caller impact

V2-E03 compares what each preregistered signal stated with what the caller record shows.

- **The population.** The initial analysis reads the valid, counted runs of V2-E02A,
  V2-E02B, and V2-E02C: each run whose state is PASSED or FAILED under the repetition rule
  of its bound revision. The extension adds the counted runs of V2-E04, once they exist,
  and the initial result stays published beside the extended one. Under revision 2 of
  V2-E03 the extension counts only the runs that executed under revision 3 of V2-E04, the
  revision that it binds, and names it in `executedUnder`. A run under revision 2 of
  V2-E04 is not in the population. (Until `V2-S6-008-PR1` this bullet said that the
  extension counts the runs of V2-E04 under its latest revision, as revision 1 states.) V2-E05 is excluded from the ranking by a stated rule: it is an optional source, no
  planned change extends the analysis over it, and a drift that the delivery controller
  reverts is a scenario that this ranking does not preregister.
- **The ten signals.** Signal 1 is the caller outcome, the reference truth, and is not
  ranked. The nine candidates are the API canonical error rate (2), from the counters
  `inferops_inference_errors_total` and `inferops_inference_requests_total`, the Ready endpoint
  counts of the API Service (3) and the runtime Service (4), the pod readiness of the API
  tier (5) and the runtime tier (6), the Deployment ready replica count (7), the scrape
  state of the API and runtime targets (8), and the sync state (9) and health state (10)
  that the delivery controller reports. Each signal names its stream, the interval at
  which the sources collect that stream (2 s for the timeline streams and 15 s for the
  telemetry streams), the reader or the registered queries that it uses, and its problem,
  healthy, and not-observed definitions. A signal added after a result is seen is labeled
  exploratory and is not ranked.
- **The operational signal candidate.** Signal 2 is the candidate for operator use. Its one
  role is the comparator of the ranking: a signal is named most caller-truthful only when
  its false-unavailable time is not greater than that of signal 2. Signal 2 meets that
  condition trivially, because it is compared with itself, and that gives it no ranking
  preference. It is not a predetermined winner.
- **Caller failures that the API error counter does not count.** The record states how the
  caller record identifies each failed outcome: `http-error` states a canonical error code
  when the answer stated one, and `invalid-response`, `timeout`, `transport-error`, and
  `identity-refused` never do. The false-healthy time of every signal counts every failed
  completion, whatever its outcome. Each run reports the failures without a canonical code
  and the failures with no matching error-counter change.
- **The computations.** The first change, the detection lag from the first caller impact,
  the false-healthy and the false-unavailable time, and the not-observed time of each
  signal, each with an inner and an outer figure, as `tools/reliability_analysis`
  computes a sampled interval. A signal that is not observed is never healthy. The ranking
  uses two ranking figures that add the not-observed time to the false-healthy and the
  false-unavailable time, so they are stricter than the published figures, which stay
  unchanged beside them.
- **Ordering.** The timelines are aligned under the clock policy of the sources, and the
  record states that this is not a claim of synchronized clocks. A lead or a lag between
  a caller instant and a reading is stated only when it is more than the clock bound of
  the run plus the coarser resolution of the two sources.
- **Two readings of no series.** The API publishes its error counter only after it counts
  its first error. So signal 2 reads a no-series answer of the error query as no counted
  error only when, in the same sample, the request query answered with a series and every
  expected API target was scraped. Signal 8 reads an answered target-count query with no
  series as a tier with no discovered target, which is a problem. Each rule is stated in
  the signal's derivation, and both are limitations of the record.

### V2-E06: the resources beside the caller outcome

V2-E06 states what the reliability topology requests and uses.

- **View A** compares the requested CPU and memory of V2-E02A, two API and one runtime
  replica, with those of V2-E02B, two and two, from the desired-state files that each
  source names by digest, rendered with the pinned chart.
- **View B** compares a single-path equivalent, one API and one runtime replica, with the
  two and two of V2-E02B. The single-path side is reconstructed by arithmetic from the pod
  templates of the target release. No such release is rendered, applied, or run, and no
  released V1 configuration is read. The view is labeled static and allocation-based.
- **The six metrics**: the API requests, the runtime requests, the total requests, the
  utilization, the model-cache storage, and the rollout headroom. Each states what it reads
  and has one label: `measured`, `static-allocation`, or `unavailable`. A view or a metric
  that reads only requests, limits, a claim size, or a rollout strategy is never labeled
  measured.
- **The utilization statistic** is fixed: the mean processor use of the API in one run, in
  cores, from the `resources` stream of the counted runs of V2-E02A and V2-E02B, over the
  valid pairs of consecutive readings in the window, with the median of each side. A
  reading with no series is not zero. The memory use of the API is expected to be
  unavailable, because the API declares that metric and does not emit it, and no source
  states the resource use of the serving runtime.
- **The cost basis is local.** No price, charge, or currency figure is computed, and no
  saving or return on investment is stated. If a cloud provider is used later, a later
  revision states its cost basis before any figure from it is computed.
- **The evidence target** is C0 for the allocation arithmetic and C2 for the figures read
  from runs. The caller figures of V2-E02A and V2-E02B are shown beside View A. No V2-E04
  figure is paired with a resource difference, because V2-E04 has no counterpart on
  another topology.

### The analysis check

```sh
uv run --locked python -m tools.analysis_preregistration --check
```

[`tools/analysis_preregistration`](../../../tools/analysis_preregistration/core.py) is a
sibling of `tools/experiment_preregistration`. It is a separate package so that the rules
of the two analysis records stay apart from the rule sets of the five reliability records,
and so that this change edits no file that those records pin. It imports two private
functions of that package, the phrase scan of the clock rules, and it changes nothing in
it. It reads the latest record of each of the two experiments in full, and a superseded
revision against every rule except that its sources are the latest ones. V2-E03 and
V2-E06 each have their own rules, seventeen and thirteen. Three of the V2-E03 rules read
a revision after revision 1 alone: the rule set of each binding, the V2-E04 revision of
the extension, and the list in `definition.changesFromSupersededRevision` of each member
that differs from the superseded revision. Revision 1 is read under the fourteen that it
was registered under. (Until `V2-S6-008-PR1` V2-E03 had fourteen rules.) Today it prints `PASSED: 2
analysis experiment(s), every rule held`. It exits 0 when every rule holds and 1 when one
does not. It reads files and writes none. Each record pins it. The default-lane suite
[`tests/testing/test_analysis_preregistration.py`](../../../tests/testing/test_analysis_preregistration.py)
runs it and plants each defect below in a copy.

| Rule | Statement |
|---|---|
| `e03-record-missing` | V2-E03 has a committed freeze record in its directory, and the record names that experiment. |
| `e03-record-shape` | The record states its version, its kind, its experiment, an integer revision, one part, and a definition object. |
| `e03-fields-unanswered` | Each freeze field has one entry for the one part, answered with a value or as not applicable with a reason, and never pending. |
| `e03-sources-stale` | The record binds each source experiment once, in its role, to the path, the revision, and the content digest of a registered freeze record of that experiment. The digest is that of the file and of its registry pin, and the latest record binds the latest revision. |
| `e03-source-fields-differ` | The environment, the caller profile, the topology, the fault, the repetition count, the bound record, and the clock policy digest that the record states for its sources are those that each bound source states. |
| `e03-clock-contradiction` | No text of the record states that the clock difference is not measured, orders instants by a time without the margin of the source clock policy, names synchronization or a guarantee in a sentence with no negation, or states that every run is INCONCLUSIVE, in the phrases that tools.experiment_preregistration names. |
| `e03-analysis-code` | The analysis-code rule of the record names its procedure directory and holds the phrases that this check names, and no other prose of it is read. The material scope names this check, the procedure directory, and every revision file of each source, and each executable that the record lists is pinned. Whether the procedure directory exists is not read. |
| `e03-population` | The initial population is the counted runs of V2-E02A, V2-E02B, and V2-E02C. The extension is the counted runs of V2-E04. V2-E05 is excluded from the ranking with a reason. No experiment is in two of them, and the later-source-revision rule holds the phrases that this check names. No other prose of it is read. |
| `e03-signal-set` | The preregistered signals are the ten of the record, numbered 1 to 10, each with its identifier. Signal 1 is the caller reference and is not a candidate. A further signal is labeled exploratory, is a candidate with a number above 10, and is not ranked. |
| `e03-signal-streams` | Each signal reads the stream of its number. Every bound source collects that stream, and the signal states the interval at which the source collects it. A timeline signal names a source that tools.reliability_analysis registers for its stream, a telemetry signal names queries of the registered query set that the sources name, and each signal states its problem, healthy, and not-observed definitions. |
| `e03-candidate` | The operational signal candidate is signal 2, the API error rate. Its role is the comparator, it has no ranking preference, it is not declared a winner, and its statements hold the phrases that this check names. No member of the definition named winner or predeterminedWinner is other than false, and none named rankingPreference is other than none. |
| `e03-ranking` | The ranking rule states the earliest change, the most caller-truthful signal, the trade-off, the exploratory label, and the not-observed time. Its comparator is the candidate, and it is judged on the inner and the outer figure. |
| `e03-caller-failures` | The record states, for each failed caller outcome, how the caller record identifies it and whether it states a canonical error code, a false-healthy rule that holds the phrase that this check names, and the two figures that it reports for each run. |
| `e03-computations` | The record states each computation. Its not-observed computation holds the phrase never healthy, and its ordering rule holds the margin of the source clock policy and the phrase no lead or lag. No other prose of them is read. |
| `e03-binding-rule-set` | In a V2-E03 record after revision 1, each source binding states, as an integer, the rule set that its bound freeze record states in metadata.preregistrationRules. |
| `e03-extension-revision` | In a V2-E03 record after revision 1, the extension counts only the runs of V2-E04 that executed under the V2-E04 revision that definition.sources binds: it names that path and that revision, and its runs statement names the revision, holds the phrases that this check names, and does not count the runs of a latest revision. |
| `e03-revision-changes` | A V2-E03 record after revision 1 names the revision that it supersedes by path and registered digest, and lists in definition.changesFromSupersededRevision each member of its definition, its fields, and its material scope that differs from that revision, once and with a reason, and no member that does not differ. A member that is an object in both is compared by its own members. |
| `e06-record-missing` | V2-E06 has a committed freeze record in its directory, and the record names that experiment. |
| `e06-record-shape` | The record states its version, its kind, its experiment, an integer revision, one part, and a definition object. |
| `e06-fields-unanswered` | Each freeze field has one entry for the one part, answered with a value or as not applicable with a reason, and never pending. |
| `e06-sources-stale` | The record binds each source experiment once, in its role, to the path, the revision, and the content digest of a registered freeze record of that experiment. The digest is that of the file and of its registry pin, and the latest record binds the latest revision. |
| `e06-source-fields-differ` | The environment, the caller profile, the topology, the fault, the repetition count, the bound record, and the clock policy digest that the record states for its sources are those that each bound source states. |
| `e06-clock-contradiction` | No text of the record states that the clock difference is not measured, orders instants by a time without the margin of the source clock policy, names synchronization or a guarantee in a sentence with no negation, or states that every run is INCONCLUSIVE, in the phrases that tools.experiment_preregistration names. |
| `e06-analysis-code` | The analysis-code rule of the record names its procedure directory and holds the phrases that this check names, and no other prose of it is read. The material scope names this check, the procedure directory, and every revision file of each source, and each executable that the record lists is pinned. Whether the procedure directory exists is not read. |
| `e06-views` | View A compares V2-E02A and V2-E02B with the replica counts that they state. View B compares one API and one runtime replica, reconstructed by arithmetic, with the two and two of V2-E02B. |
| `e06-labels` | Each view and each metric has one label of the three and reads only registered reads. A view or a metric that reads only configuration is not labeled measured, a measured one reads a run stream, and a static allocation reads configuration alone. The utilization metric is labeled measured or unavailable, and no other view or metric is labeled measured. |
| `e06-metrics` | The record states the six metrics, each with what it reads and a statement, and the rollout headroom definition. |
| `e06-utilization` | The utilization statistic, its stream, its query set, its queries, its source runs, its aggregate, and its no-series rule are stated. |
| `e06-cost-basis` | The cost basis is local, no cloud provider is used, its cloud rule holds the phrase that this check names, and no member of the cost basis is named price, charge, currency, or amount. |
| `e06-evidence-target` | The evidence target is C0 for the allocation arithmetic and C2 for the figures read from runs, and the confidence of a cost is stated apart. |

### What is enforced for the analysis records, and what is not

Enforced in the default lane: every rule above and every rule of the freeze check, over
the two committed records. Not enforced:

- **That an analysis follows its record.** The code that computes either analysis in full
  does not exist. For one run, `tools/reliability_analysis` computes whether a signal
  changed, its detection lag, and its false-healthy and false-unavailable time, for a
  signal of one timeline stream and one tier. It reads no telemetry stream. A later change
  adds the rest, and a later revision of the record pins every part before any figure. Code added outside the procedure
  directory is listed as added only when a pinned module imports it, and the review of
  that revision checks the rest.
- **That a phrase means what it says.** Where a rule reads named phrases, a text that
  holds them and then says otherwise passes; a test holds one such gap. A member named
  `winner` or `predeterminedWinner` anywhere in the V2-E03 definition must be false, and
  one named `rankingPreference` must be `none`, but a winner stated in prose is not read.
- **That the procedure directory is absent.** The check reads the scope, not the tree.
  A suite test holds that no procedure directory exists today.
- **That a definition is right.** The check reads structure, identifiers, intervals, and
  the phrases that it names in seven texts of V2-E03: the two statements of the candidate,
  the false-healthy rule of the caller failures, the not-observed computation, the ordering
  rule, the later-source-revision rule, and the analysis-code rule. V2-E06 has two such
  texts, its analysis-code rule and its cloud rule. The
  contradiction scan reads every text of both records. A problem, healthy, or not-observed definition
  is held to exist, not to be correct.
- **That a source collects what its text says.** The check reads the stream names and the
  interval from the collection text of each source. It does not run a collector.
- **That a paraphrase is refused.** The contradiction scan is the one of the reliability
  records, and it has the same gaps.
- **That a member listed as changed changed as its reason says.** The revision-change rule
  compares each member of the definition, the fields, and the material scope with the
  superseded revision, and one level inside a member that is an object in both. A change
  deeper inside a list or an object is listed by the member that holds it, and the reason
  that the record gives is not read.
- **That the V2-E06 arithmetic reads the files that the record pins.** The record names
  them and pins them. No code renders the chart or computes a request yet.
