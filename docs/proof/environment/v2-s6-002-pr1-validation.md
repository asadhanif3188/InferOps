# V2-S6-002-PR1 validation: the Q2 runtime startup characterization

Status: **the Q2 workflow is frozen, and no characterization has run yet. This record is
written in two steps. The first commit of the change adds the freeze record, the driver,
and the tool, before any characterization, and this record states what it validated.
The run, its directory, and what it showed are added by the next commit of the same
change.** No claim is registered.

| Property | Value |
|---|---|
| Branch | `test/v2-s6-002-q2-runtime-startup` |
| Base | `486ca49ae99ed7257a503e291d5710be88f7ce26`, the merge of `V2-S6-001-PR2` |
| Freeze record | [`v2-q2/freeze-r2.v1alpha1.json`](../experiments/v2-q2/freeze-r2.v1alpha1.json), registered by this change. It supersedes [revision 1](../experiments/v2-q2/freeze-r1.v1alpha1.json), registered by the first commit of this change, under which no characterization ran |
| Driver | [`v2-q2/procedure/q2-driver.txt`](../experiments/v2-q2/procedure/q2-driver.txt), a pinned input of the record |
| Tool | [`tools/runtime_startup`](../../../tools/runtime_startup/core.py) |
| Page | [Q2: the runtime startup characterization](../../environment/runtime-startup-characterization.md) |
| Suite | [`tests/domain/test_runtime_startup.py`](../../../tests/domain/test_runtime_startup.py) |
| Qualified environment | [`q1-1`](../experiments/v2-q1/runs/q1-1/result.md), `sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461` |

## What the story asks of this change

Story `V2-S6-002` characterizes the qualified release before any result-bearing
reliability run. This change is its first part: three controlled runtime restarts in the
qualified environment, with every observation kept, and S, the maximum interval from a
runtime start to Ready, stated by a record. Later work derives bounds from S. This
change derives none.

## What this change adds

- **`tools/runtime_startup`.** It reads one directory that the driver writes and prints
  one record whose result is `CHARACTERIZED`, `INCONCLUSIVE`, or `REFUSED`. It contacts
  no cluster. Its 16 rules are the 16 acceptance criteria of the freeze record, with the
  same statements. Seven are preconditions: the phase `up` completed at the executing
  commit, the working tree was clean, the frozen inputs of Q2 and of Q1 are at their
  pins, the delivery paths equal the desired revision, the environment digest is the one
  `q1-1` states, the release, the API image, and the runtime image are those of `q1-1`,
  and both Deployments are at 2 Ready replicas. A precondition that is not held makes the
  result `REFUSED`. Any other rule that is not held makes it `INCONCLUSIVE`. S has a value
  only when the result is `CHARACTERIZED`.
- **The driver.** Its phases `up` and `down` run the phases of the Q1 driver without a
  change, so the release is prepared and removed as for `q1-1`. Its phase
  `characterize` asks the tool for the preconditions and then runs three restarts, one
  at a time, with a watch of the runtime pods around each and one completion to each
  replacement after it.
- **The freeze record, revision 1.** Its material scope holds the whole material scope of
  the Q1 freeze record, the Q2 driver, the import closure of the Q2 tool, the Q1 freeze
  record, and the record of `q1-1`: 195 pinned inputs. It states the restart, the
  measurement, the rule that derives S, and no value of S.
- **The layout check admits the Q2 directories.** `tools/experiment_evidence` lists a
  directory of `v2-q2/runs/` as a qualification, as it lists one of `v2-q1/runs/`, and
  names `tools.runtime_startup --check` as its check. The edit moves the three pins of
  `tools/experiment_evidence` in revision 2 of the Sprint 5 integration validation again;
  its two attempts are finished, and the edit moves no pin of the Q1 or the Q2 record.

## Decisions this change makes

1. **A restart is a rollout restart of the runtime Deployment.** It is controlled and it
   is not the fault of a reliability experiment: the Deployment controller replaces the
   pods under the chart's rollout bounds, and no pod is deleted by name. Under those
   bounds one restart replaces both runtime pods, one after the other. So three restarts
   give six observations, and S is the maximum of the six. A rule holds that the second
   replacement of each restart was created no earlier than the first was Ready.
2. **The interval is from the creation of the pod to its first Ready condition.** The
   creation includes the scheduling and the verification of the model by the init
   container. Ready is the condition that the kubelet sets from the readiness probe on
   `/health`, which answers 503 while the model loads. The two parts of the interval are
   stated beside it. Both instants are cluster timestamps of whole seconds.
3. **Ready is confirmed by one completion of each replacement.** It is sent after the
   rollout of its restart completed. It is not a part of the interval.
4. **The environment is the one `q1-1` selected, and Q1 does not run again.** The Q1
   freeze record allows a later qualification only after the environment or a frozen
   input changes. So Q2 runs the phase `up` of the Q1 driver and compares the capacity
   record of that phase with `q1-1`: the tool computes the environment identity with the
   function of the Q1 tool, and compares the release identifier, the API image digest,
   and the runtime image with the record of `q1-1`.
5. **The driver requests no restart after a refusal.** It asks the tool for the
   preconditions with `--preconditions` before the first restart, and it requests no
   later restart after a rollout that did not complete within 1800 s.

## What the first commit got wrong: revision 1

The first commit registered revision 1. Its precondition `release-qualified` held the
API Deployment to the API image digest that the record of `q1-1` states. That cannot
hold: the phase `up` of the Q1 driver builds the API image again, and on 2026-10-15 the
phase `up` of the work directory `q2run-1`, at the first commit, reported
`sha256:cf30eac7cc2a75f9a91dac62c8c09a6080de5b2725d2b37262c15bafe924120d`, where `q1-1`
states `sha256:5b4be2da31141bc43c0fa65133b4377ef002a3ff922278cda98ba247a244c7e1`. The
freeze tool listed no changed input of the Q1 record, and the Dockerfile copies only
`src/inferops` and three paths of `tools/`, which the Q1 record pins. The build inputs
were unchanged, and the digest was another one. This record does not establish why.

What was done, in order:

1. The phase `up` completed, with exit status 0.
2. **No characterization ran under revision 1.** No identifier was spent. Instead, the
   operator read the capacity collection, the provenance, and the Deployments once into a
   scratch directory outside the repository, with a header written by hand, and ran
   `python -m tools.runtime_startup --preconditions` on it. Six preconditions were held.
   `release-qualified` was not held, with the detail "the declared API image is not the
   one q1-1 states". The environment digest was the one of `q1-1`. That reading is an
   operator check: it is not committed, and it is not a characterization.
3. The phase `down` removed the release. The namespaces and the custom resource
   definitions after it were those before the phase `up`.
4. The second commit registers revision 2, which holds the API Deployment to the digest
   that the phase `up` declared, as Q1 does. It changes no other rule, bound, or step.
   It classifies the two pins that moved: the tool (material) and the driver (not
   material: it names revision 2).

## Parent-story acceptance

| Criterion | State after the first commit |
|---|---|
| Q2 executes 3 controlled runtime starts or restarts and freezes S as the maximum start-to-Ready interval | **Mechanism frozen; not executed.** Rules `Q2-AC1` to `Q2-AC16` decide it |
| The other criteria of the story | **Pending: later work.** This change derives no bound |
| Qualification data is not promoted as a benchmark or as result-bearing reliability proof | **Held by the freeze record and the record:** the record states no average, percentile, or rate, and no claim cites S |

## Evidence level and limitations

The tool is evidence at C0: every directory it was given is synthetic, written by the
suite. The limitations of a characterization are those of the freeze record and of [the
page](../../environment/runtime-startup-characterization.md#limitations).

## Validation of the first commit

Run from Git Bash on the Windows workstation, before the first commit.

| Command | Result |
|---|---|
| `python -m pytest tests/domain/test_runtime_startup.py tests/testing/test_experiment_freeze.py tests/testing/test_experiment_evidence_layout.py -q` | Recorded in the commit message of the first commit |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 7 freeze record(s), every rule held` at the first commit, and `PASSED: 8` at the second |
| `uv run --locked python -m tools.experiment_freeze --changes` of the Q1 and the Q2 records | Unchanged |
| `bash -n docs/proof/experiments/v2-q2/procedure/q2-driver.txt` | No syntax error |
