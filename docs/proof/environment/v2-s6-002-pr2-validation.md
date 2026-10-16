# V2-S6-002-PR2 validation: the Q3 stable caller characterization and the Q4 bounds

Status: **one characterization ran, [`q3-1`](../experiments/v2-q3/runs/q3-1/result.md),
and it is `REFUSED`: its capacity reading was not of the environment of `q1-1`, so the
driver started no caller. No G was measured, and no Q4 bound record exists.** Evidence
level C2 for the refusal, on the docker-desktop provider with one node. No claim is
registered. The change freezes Q3 and the four Q4 formulas, adds the two tools, and keeps
the refused run. The parent story's Q3 and Q4 criteria stay open.

| Property | Value |
|---|---|
| Branch | `test/v2-s6-002-q3-q4-bounds` |
| Base | `b0bdccad4cce78ea532c206ecb4cbb99e4f4c420`, the merge of `V2-S6-002-PR1` |
| Freeze record | [`v2-q3/freeze-r1.v1alpha1.json`](../experiments/v2-q3/freeze-r1.v1alpha1.json), registered by this change, SHA-256 `b8c5f7acf2bde60d82f0909eb02fc2f01572e214351ea8b4d6e56043543d8c82`, 200 pinned inputs |
| Driver | [`v2-q3/procedure/q3-driver.txt`](../experiments/v2-q3/procedure/q3-driver.txt), a pinned input of the record |
| Tools | [`tools/caller_characterization`](../../../tools/caller_characterization/core.py) and [`tools/experiment_bounds`](../../../tools/experiment_bounds/core.py), both pinned inputs of the record |
| Page | [Q3: the stable caller characterization, and the Q4 bounds](../../environment/stable-caller-characterization.md) |
| Suites | [`tests/domain/test_caller_characterization.py`](../../../tests/domain/test_caller_characterization.py) and [`tests/domain/test_experiment_bounds.py`](../../../tests/domain/test_experiment_bounds.py) |
| Run | [`q3-1`](../experiments/v2-q3/runs/q3-1/result.md), `REFUSED` on `environment-qualified` |
| Qualified environment | [`q1-1`](../experiments/v2-q1/runs/q1-1/result.md), `sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461` |
| S | 11,000 ms, from [`q2-1`](../experiments/v2-q2/runs/q2-1/result.md). Not combined with any G |

## What the story asks of this change

Story `V2-S6-002` characterizes the qualified release before any result-bearing
reliability run. `V2-S6-002-PR1` ran Q2 and stated S. This change was to run Q3, RP-1
for at least five minutes with the topology healthy, state G from the gaps between
successive successes, compute the four Q4 bounds from S and G by fixed formulas, and bind
the bound record to the exact Q2 and Q3 evidence. It froze Q3 and the formulas, and ran
Q3 once. The run was refused before its caller started, so G and the bounds are not
stated.

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
- **The run `q3-1`**, kept under `docs/proof/experiments/v2-q3/runs/q3-1/` with its
  record, header, capacity collection without `capacity/pods.json`, provenance,
  Deployments, pods, redacted transcript, and page.

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
- **The refusal was kept, and the criterion was not changed.** After the refusal, the host
  owner authorized one attempt to restore the environment: `docker desktop restart`, which
  did not reboot the virtual machine, and then `wsl --shutdown`, which did. The memory
  figure came back as a third value, so no identifier was spent on a second
  characterization, and the precondition was not relaxed.

## The run

All instants are UTC, on 2026-10-16. [The run page](../experiments/v2-q3/runs/q3-1/result.md)
states each value.

| Step | Result |
|---|---|
| Phase `up` (Q1 driver, unchanged), work directory `q3run-1`, 07:26:17 to 07:33:55 | Exit 0. Both capacity readings `ACCEPTED`. Application `Synced` and `Healthy` at `b0bdcca`. API image digest declared: `sha256:de5173b2c143f6f80ecec4fab34b3d7be67e1713a604ba970bb40c07c4257953` |
| Characterization `q3-1`, 07:34:10.644 to 07:34:24.556 | `REFUSED`. Held: the six preconditions other than `environment-qualified`. Not held: `environment-qualified`, digest `sha256:ac3a1022e86facb519bb0820b57d7a7fb32c0c6ea1011a59e88b8c1aa4efd087`. Not observed: the seven rules of the measurement. No caller and no watch was started |
| Phase `down` (Q1 driver, unchanged), ended 07:36:23 | Exit 0. Namespaces and custom resource definitions equal to those before `up` |
| Operator reads, by hand | Engine and node memory 10,429,972,480 B after the refusal (q1-1: 10,429,960,192 B), VM uptime 4,574 s. After `docker desktop restart`: same memory, uptime 5,580 s. After `wsl --shutdown`: uptime 9 s, memory 10,429,956,096 B |

`python -m tools.caller_characterization --check` builds the committed record again, byte
for byte. `python -m tools.experiment_bounds --check` finds no committed bound record.

## Validation

All commands ran from Git Bash in the locked environment (`uv run --locked`).

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check .` | clean |
| Format | `ruff format --check .` | clean |
| Types | `python -m mypy` on the two new tools, `tools/experiment_evidence`, and the two new suites, and again with `--platform linux` | clean on both |
| Driver syntax | `bash -n docs/proof/experiments/v2-q3/procedure/q3-driver.txt` | clean |
| Freeze records | `python -m tools.experiment_freeze --check` | PASSED, 9 records |
| Freeze changes | `python -m tools.experiment_freeze --changes` for Q1 r1, Q2 r2, and Q3 r1 | UNCHANGED for each |
| Committed characterizations | `python -m tools.caller_characterization --check`, `python -m tools.runtime_startup --check` | PASSED, 1 each |
| Bound records | `python -m tools.experiment_bounds --check` | PASSED, 0 records |
| Evidence layout | `python -m tools.experiment_evidence repository` | `q3-1` listed as a qualification, 0 refused |
| Targeted suites before the freeze commit | 14 suites, among them the two new ones | 3334 passed, 3 skipped |
| Default lane after the run | `python -m pytest -q` | 22,737 passed, 39 skipped, 2 failed, in 68 min. The two failures were guard tests of the layout suite that list the committed qualification directories and did not yet name `q3-1`; after the fix the layout suite passed: 258 passed, 2 skipped |
| Whitespace | `git diff --check` | clean |

## What is not established

- G, any latency or gap of a caller, or any count of caller requests. No caller ran.
- Any Q4 bound: `runtime_start_bound_ms`, `caller_gap_reference_ms`,
  `reversal_recovery_bound_ms`, and `caller_total_unavailability_bound_ms` have no value.
- That the formulas are right for a reliability experiment. They are fixed, and they were
  not applied.
- Why the kernel of the virtual machine reports another memory figure after a boot.

## What is left open

- **Q3 and Q4 are not done.** The parent story's criteria that Q3 freezes G and that Q4
  computes the bounds stay open. Q2 is done (`V2-S6-002-PR1`). No qualification data is
  promoted as a benchmark or as result-bearing proof.
- **The environment identity is a decision for later work.** On this host the digest of
  `q1-1` does not survive a boot of the engine's virtual machine, and Q2, Q3, and the
  rule that E02A and E02B share the environment of `q1-1` all compare that digest. A later
  change either qualifies the environment again and repeats the characterizations that
  depend on it, or revises how the environment identity treats the memory figure, under
  new freeze revisions. This change does neither.
