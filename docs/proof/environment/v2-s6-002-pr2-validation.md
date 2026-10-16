# V2-S6-002-PR2 validation: the Q3 stable caller characterization and the Q4 bounds

Status: **frozen before the run. No characterization has run, and no bound record
exists.** The first commit of this change registers the Q3 freeze record, revision 1,
with the Q3 tool, the Q4 tool, and the driver. No claim is registered.

| Property | Value |
|---|---|
| Branch | `test/v2-s6-002-q3-q4-bounds` |
| Base | `b0bdccad4cce78ea532c206ecb4cbb99e4f4c420`, the merge of `V2-S6-002-PR1` |
| Freeze record | [`v2-q3/freeze-r1.v1alpha1.json`](../experiments/v2-q3/freeze-r1.v1alpha1.json), registered by this change |
| Driver | [`v2-q3/procedure/q3-driver.txt`](../experiments/v2-q3/procedure/q3-driver.txt), a pinned input of the record |
| Tools | [`tools/caller_characterization`](../../../tools/caller_characterization/core.py) and [`tools/experiment_bounds`](../../../tools/experiment_bounds/core.py), both pinned inputs of the record |
| Page | [Q3: the stable caller characterization, and the Q4 bounds](../../environment/stable-caller-characterization.md) |
| Suites | [`tests/domain/test_caller_characterization.py`](../../../tests/domain/test_caller_characterization.py) and [`tests/domain/test_experiment_bounds.py`](../../../tests/domain/test_experiment_bounds.py) |
| Qualified environment | [`q1-1`](../experiments/v2-q1/runs/q1-1/result.md), `sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461` |
| S | 11,000 ms, from [`q2-1`](../experiments/v2-q2/runs/q2-1/result.md) |

## What the story asks of this change

Story `V2-S6-002` characterizes the qualified release before any result-bearing
reliability run. `V2-S6-002-PR1` ran Q2 and stated S. This change runs Q3: RP-1 for at
least five minutes with the topology healthy, and G from the gaps between successive
successes. It then computes the four Q4 bounds from S and G by fixed formulas, and binds
the bound record to the exact Q2 and Q3 evidence.

## What this change adds

- **`tools/caller_characterization`.** It reads one directory that the driver writes and
  prints one record whose result is `CHARACTERIZED`, `INCONCLUSIVE`, or `REFUSED`. Its 14
  rules are the 14 acceptance criteria of the freeze record. Seven are preconditions, as
  for Q2, with one change: the topology precondition also reads the API pods and the
  runtime pods. G has a value only when the result is `CHARACTERIZED`.
- **`tools/experiment_bounds`.** It reads one committed Q2 record and one committed Q3
  record and prints the four bounds, or refuses with one of five rules.
- **The driver.** Its phases `up` and `down` run the phases of the Q1 driver without a
  change. Its phase `characterize` asks the tool for the preconditions, then runs one
  RP-1 caller run of 360 s inside a watch of the API pods and the runtime pods.
- **The freeze record, revision 1.** Its material scope holds the whole material scope of
  the Q1 freeze record, the Q3 driver, the import closure of both tools, the Q1 freeze
  record, and the record of `q1-1`: 200 pinned inputs. It states the healthy state, the
  measurement, the rule of G, the four Q4 formulas, and no value.
- **The layout check admits the Q3 directories.** `tools/experiment_evidence` lists a
  directory of `v2-q3/runs/` as a qualification. The edit moves the three pins of
  `tools/experiment_evidence` in revision 2 of the Sprint 5 integration validation again;
  it moves no pin of the Q1, the Q2, or the Q3 record.

## Decisions this change makes

- **Healthy is a state of the topology, not of the caller.** A caller failure is a caller
  result. Refusing a run because a request failed would choose the runs that give a
  smaller G.
- **The duration is 360 s.** Q3 requires at least five minutes of caller traffic. The rule
  `five-minutes-run` holds the run to at least 300,000 ms and to its own duration.
- **G is the nearest-rank p99.** The method is stated before the run, so no method is
  chosen after G is seen.
- **The Q4 formulas are frozen with Q3, before G is observed.** The Q4 tool is a pinned
  input of the Q3 freeze record.
- **A Q3 record is built under the revision that its header names.** The Q2 page states
  that a later Q2 revision would refuse `q2-1` when it is built again. The Q3 tool does not
  repeat that gap.

## Validation

To be completed with the run.
