# The comparison eligibility of V2-E02A

`tools/comparison_eligibility` classifies the runs of V2-E02A and applies the eligibility rule of
revision 4 of [its freeze record](../proof/experiments/v2-e02a/freeze-r4.v1alpha1.json). It has two
outputs: [the classification record](../proof/experiments/v2-e02a/classification.v1alpha1.json), which
keeps its bytes, and [the adjudicated record](../proof/experiments/v2-e02a/eligibility-adjudicated.v1alpha1.json),
which states the current verdict, `not-decided`.
[The baseline report](../proof/experiments/v2-e02a/baseline-report.md) states the result.

```text
python -m tools.comparison_eligibility
python -m tools.comparison_eligibility --adjudicated
python -m tools.comparison_eligibility --check
```

The first two commands print a record. Exit status 0 says that the record was printed, and it
states no verdict. `--check` builds both records again and compares each with its
committed file, it holds each run to its executing commit, and it holds each current page to the
current verdict. Exit status 1 says that one differs, 2 that the arguments are not usable, and 5
that a rule refused an input.

The command reads files and Git objects. It writes no file, starts no run, and contacts no
cluster. It registers no claim and no freeze record.

## What the tool reads

| Input | How it is held |
|---|---|
| Revision 4 of V2-E02A, and revision 2 of V2-E02B | Each has the digest that the freeze registry pins. Both paths are fixed, so a later revision does not change this record |
| The rule | The record must state its two sentences word for word, and the three phrases of the repetition rule. The record of V2-E02B must name the two medians. Otherwise the tool refuses |
| The run directories | Identifiers 1 to N with no gap, at most 6, which the repetition rule allows. Each names revision 4. Each run analysis is reproduced by `tools.analysis_replay`, so an edited figure refuses the record |
| The medians | `aggregate_runs` of `tools.analysis_replay` holds the whole set once: the layout, the replay, and that no run is left out. The aggregate of `tools.reliability_analysis` then states each median over the replayed analyses. The tool computes none |
| The clock bound of each run | The one line `clock bound: N ms` of `environment.txt`. With no such line, or with two, no episode of that run is judged |
| The corrections | Each must name the run and the digest of its manifest |

## The rule, and where the tool is stricter than the record

A run counts when its state is `PASSED` or `FAILED`. The rule gives `eligible` when at least 2 of
the 3 counted runs show one of two conditions.

**A failure episode that starts at or after the `fault-injection-started` event, open or closed.**
The start is the completion of the first failed request, on the node clock. The event is on the
host clock. The clock policy of the record does not declare the set rules. The tool applies its
margin, the clock bound plus 1 ms: a start inside the margin is `not-judged`. It does not count
as a run that shows the condition, and it does not count against the set. A run with no clock
bound, or with no fault event, is not judged in the same way.

**A zero-Ready interval of the runtime tier that starts after that event, with an outer figure
above 0 ms.** The record does not state which instant starts an interval, so the tool states two
figures. `firstReadingAfterFault` reads the first read that gave zero. `outerStartAfterFault`
reads the read before it, which the outer figure measures from. Both instants are on the host
clock. Only the outer start can make a set eligible.

| The set | The verdict |
|---|---|
| Fewer than three counted runs | `not-decided` |
| More than three counted runs | Refused |
| The failure-episode condition holds | `eligible`, resting on it |
| The zero-Ready condition holds on the outer start | `eligible`, resting on it |
| The zero-Ready condition holds on the first reading alone | `not-decided`: the record does not state that reading, so a person decides it |
| A figure that was not judged could reach the 2 runs | `not-decided`: a figure that is not judged is neither held nor failed |
| Neither, and no such figure | `not-eligible`. The statement is the sentence of the record: the runs remain valid evidence, the claim of V2-E02B is narrowed to topology and endpoints, and no improvement percentage is stated |

The table is what the rule gives on the state of each manifest. An adjudicated reason comes
before each of its rows: the set is `not-decided` whatever the conditions give, and the conditions
are still stated.

## The adjudicated record

The classification record has a fixed path, and revision 3 of V2-E02B binds its digest and its
verdict in `definition.g3Provenance`. So a later verdict goes in a record at a new path, and
`--check` refuses that record unless the classification record is the one that the revision binds.
Revision 3 still says `eligible` until a successor revision.

| Input | How it is held |
|---|---|
| [The adjudication](../proof/experiments/v2-e02a/eligibility-adjudication.v1alpha1.json) | A committed file with exact members. Its reason is the statement of the verdict. It states no verdict, and `not-settled` is the only ruling it can state, so no input can make a set eligible |
| The criterion | Revision 4 must state `E02A-AC2` word for word |
| The classification record | Its digest and its verdict must be the ones that revision 3 of V2-E02B binds, and each attempt must keep `counted: true` |
| The target | The record names revision 3 of V2-E02B as its own target. The classification record keeps revision 2 |
| The raw streams | The four streams of each run, over the readings wholly inside the window of `declaration.json` |

The verdict string is the existing `not-decided`, and the schema has no other status. Neither
record has a schema file: `schema` is a name, and the tool holds each member. Each attempt states
`validityEstablished: false`, and that member is not a status.

**The two readings.** `readingScope` asks whether a reading has a value, with three variants
together: the read answered, with no fault, no null member, and no refused tier.
`selectedRuntimeCounts` asks whether the reading reports runtime `readyReplicas` or
`availableReplicas`. No source selects those two counts: the review of each run reported on them
after the evidence was read. A count that a reading omits is missing, and it is not zero.
`everyCount` asks whether it reports each of the eight Deployment counts of both tiers, and each
run states which counts each reading reports and which no reading reports. Each states the gap
from one start to the next and from one finish to the next start, and `held` reads the first, the
larger. Fewer than two readings with a value hold nothing. `held` reads the second and the third
clause of the criterion, and the replay of each run holds the first. The tool refuses readings
that are out of order, or a reading that finished before it started. The tool states these
figures, and it does not choose: the reading scope holds in 3 of 3 runs, and the two runtime
counts in 0 of 3.

**The consumers.** `consumers` states the latest revision of V2-E02B, V2-E03, and V2-E06 on
2026-11-02, with what the repository owner decided for each. `consumesRuns` is an empty list that
this tool writes, and it is a statement of that decision and not a reading of the record.
`usable_baseline` gives the figures to a consumer only from the adjudicated record, and it refuses
with the rule `eligibility-disputed` while that verdict is not `eligible`. It never reads the
classification record, whose verdict stays `eligible`.

**The current pages.** `--check` reads each page of `SCANNED_PAGES` for a sentence that the verdict
withdrew or that presupposes an authorization of a switch, and each page of `CURRENT_PAGES` for
the name of the adjudicated record. A page of a past change keeps its text, so the check does not
read one.

## No percentage

`comparisonFigures` states the two medians that the record of V2-E02B reads, each with a basis.

| Basis | Meaning |
|---|---|
| `positive` | The median is above zero |
| `zero` | The median is zero. No percentage is computed over a zero baseline |
| `no-value` | The aggregate states no median. The improvement is not computed |

`percentageOverThisBasisPossible` is true only for a positive basis of an eligible set, so it is
false in the adjudicated record. The tool computes no percentage in any case. No code here divides
by a figure of the baseline.

## The handoff

The `handoff` member states the last run, the governing record, and the two desired states that
rule G3 moves between. The record is about the runs that executed. The tool reads no desired state
of the working tree, so a switch of `main` to the target does not change the record. The check of
each executing commit reads the objects of the clone at that commit.

`--check` replays each run with the analysis code of the checkout, and the replay reads the commit
of the checkout. It refuses while a source file of the analysis code differs from that commit. A
change to that code that also changes a run analysis makes the replay refuse the run, as it does
for each other reader of the run.

## What is enforced, and what is not

- `tests/testing/test_comparison_eligibility.py` holds each row of the two tables above on
  synthetic sets, and the committed record on the committed runs.
- A clone that does not hold an executing commit cannot compare it. `--check` prints
  `NOT COMPARED` and exits 0, so a shallow clone compares less. A run of the check in a full clone
  compares each commit.
- The tool holds a run that has a run analysis with a fault instant. A run directory with neither
  refuses the record, so a set with a run that was refused before its fault needs another
  reading. All three runs have both.
- The tool reads a state from the manifest. It does not judge a criterion again. The review of
  the runs did that.
- The approval of the reading of `E02A-AC2` is a statement of the repository owner. No tool
  reads it. Nor does a tool read the acceptance of the adjudication: the input states it.
- No tool reads the figures of the baseline yet, so nothing calls `usable_baseline`. A test holds
  the refusal for V2-E02B, V2-E03, and V2-E06. A later reader has to call it, and no test can
  require that today. A reader that opens the classification record directly gets `eligible`.
- No tool reads the population of a later revision, so no check holds that V2-E03 and V2-E06
  consume none of the three runs. It is a decision of the repository owner.
- The check of the pages matches sentences. A page can state the withdrawn verdict in other words
  and pass, and a sentence that states the rule or quotes history can fail. The review of the page
  is what reads for that, and such a sentence is reworded.
- `check_adjudicated` reads the streams as they are on disk. `--check` first holds them to the
  manifest of each run, by the replay, so run the command and not the function alone.
- The freeze record of V2-E02B still says `eligible`, and no check can change that. A successor
  revision states the outcome.
- No freeze record pins this package, and no tool that a run executes imports it. A test holds
  the second statement.

## What this does not establish

Neither record establishes a comparison, an improvement, or a percentage. Neither authorizes a
run of V2-E02B, the G3 switch, or a later sprint. The adjudicated record does not establish that
any run is valid, that any run is not valid, or which reading of `E02A-AC2` is right. The
`doesNotEstablish` member of each record states the full list.
