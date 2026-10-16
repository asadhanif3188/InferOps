# V2-S6-002-PR2 validation: the Q3 stable caller characterization and the Q4 bounds

Status: **one characterization ran, [`q3-1`](../experiments/v2-q3/runs/q3-1/result.md),
and it is `REFUSED`: its capacity reading was not of the environment of `q1-1`, so the
driver started no caller. No G was measured, and no Q4 bound record exists.** Evidence
level C2 for the refusal, on the docker-desktop provider with one node. No claim is
registered. The change freezes Q3 and the four Q4 formulas, adds the two tools, and keeps
the refused run. The parent story's Q3 and Q4 criteria stay open.

**Merge disposition.** Pull request #150 is mergeable as a valid preserved `REFUSED`
qualification attempt. Merging the pull request does not mean that `V2-S6-002` is
complete. [The merge disposition](#merge-disposition) and [the downstream
state](#the-downstream-state) below state why.

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
| Operator reads, by hand | Engine memory, and the memory that the node container's `/proc/meminfo` states, 10,429,972,480 B after the refusal (q1-1: 10,429,960,192 B, and the same figure in the capacity reading of `q3-1` for the node allocatable memory), VM uptime 4,574 s. After `docker desktop restart`: same memory, uptime 5,580 s. After `wsl --shutdown`: uptime 9 s, memory 10,429,956,096 B |

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

The table above is the local validation of the change before its push, and it stays as it
ran. After the fix of the two guard tests, only the affected suites ran again locally: the
layout suite, 258 passed and 2 skipped; the documentation, inventory, Q3, Q4, and layout
suites, 2142 passed and 2 skipped; and, after the corrections of the independent review,
those suites with the runtime startup and environment qualification suites, 2354 passed
and 2 skipped. The full local default lane did not run
again.

## Final hosted validation

Added after the push. On the head `9246e9056e95f04a405b099742afb16d02c383d3`, the hosted
workflow `checks`, run `38882852000`, attempt 1, started by the pull request, completed
with the conclusion `success`. Each of its 11 jobs completed with `success`:

| Hosted job | Conclusion |
|---|---|
| format, lint, and types | success |
| Helm chart and rendered manifests | success |
| API container image | success |
| default-lane test suite | success |
| secret scan | success |
| dependency and image vulnerability scan | success |
| Terraform format, validation, and lint | success |
| documentation links and whitespace | success |
| expected-failure controls | success |
| software bill of materials | success |
| distribution build | success |

The conclusions were read from the check runs of the head commit. The job logs need an
authenticated read, so no hosted test count is stated here. Every job runs on
`ubuntu-24.04`, and the default-lane job runs `uv run --locked python -m pytest -q`, the
command of the local row above, so the hosted default lane is a full default lane on Linux
with the fix of the two guard tests in the tree. It does not change the local history above.

## What the independent review found

An independent review read the whole change after the run. It found no defect in the
committed evidence and no private information. It found these defects of the first
draft, which the last commit of this change corrects:

- The test inventory said that the suite holds that the driver refuses a reused
  identifier. The suite reads the driver as text, and the driver refuses an identifier
  only within one work directory. The entry now says so, and the Q3 page states the gap.
- The inventory said that the bound suite reads the committed bound records in place and
  holds each to its sources. No bound record is committed, so that test holds at zero
  records. The entry now says so. The Q3 entry now says that the one committed record is
  `REFUSED` and exercises neither G nor the caller rules.
- The Q3 page had no section for the measured gaps of the pinned tools and driver. It now
  states six.
- The operator row above said that the hand reads gave the node memory. They gave the
  engine memory and the node container's `/proc/meminfo`; the node allocatable memory is
  from the capacity reading.
- Four pages said that the memory figure changes when the virtual machine boots. Two
  boots were observed. The pages now say that it changed at each of the two.

A pre-run review, before the freeze commit, found a stale pin of the Q4 tool, a sentence
of what a record does not establish that was stronger than the rules, and imprecise
wording about two host instants. The freeze commit corrects them, and its message states
them.

## Merge disposition

Added after the push, before the merge. It changes no result, record, pin, or criterion.

Pull request #150 is mergeable as a valid preserved `REFUSED` qualification attempt.
Merging the pull request does not mean that `V2-S6-002` is complete.

- `V2-S6-002-PR1` produced the Q2 characterization `q2-1`, `CHARACTERIZED`, with
  S = 11,000 ms.
- `V2-S6-002-PR2`, this change, froze the Q3 workflow and the four Q4 formulas, and
  preserved `q3-1`, `REFUSED`.
- The G that Q3 requires is absent.
- The Q4 numeric bounds are absent. No bound record is committed.
- The parent story's Q3 and Q4 acceptance criteria remain OPEN.
- `V2-S6-003` is BLOCKED.
- Further qualification work requires explicit Sprint 6 change control.

The change is valid because it kept the frozen refusal as it happened. The story is not
complete, because G and the Q4 bounds do not exist. Merging a valid refusal is not passing
the parent story.

## The downstream state

```text
Q1 q1-1
QUALIFIED
environment = sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461

Q2 q2-1
CHARACTERIZED
S = 11,000 ms

Q3 q3-1
REFUSED
G = absent

Q4
no bound record

V2-S6-002
INCOMPLETE

V2-S6-003
BLOCKED
```

`tools.experiment_bounds` refuses, with `bounds-environment-differs`, two source records
that do not state the same provider, environment digest, release identifier, and
qualification record. A later change therefore cannot combine `q2-1` with a Q3
characterization run under another environment. If later change control selects a new Q1
qualification or a new environment identity, its owner assesses whether Q2 must be
characterized again under that same identity before Q4 can be computed. This change does
not make that assessment.

## The environment-identity decision is deferred

This change does not decide whether the memory figure in bytes that the environment
digest holds is a property that defines the qualification, or an unstable observation
that should be represented in another way. That decision belongs to follow-up Sprint 6
change control. This change removes no value from the identity, adds no tolerance,
rounds or masks no figure, adds no wildcard, qualifies no environment again, relaxes no
part of `environment-qualified`, and changes no Q3 acceptance criterion.

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
  `q1-1` did not hold across either of the two boots of the engine's virtual machine that
  were observed, and Q2, Q3, and the
  rule that E02A and E02B share the environment of `q1-1` all compare that digest. A later
  change either qualifies the environment again and repeats the characterizations that
  depend on it, or revises how the environment identity treats the memory figure, under
  new freeze revisions. This change does neither.
