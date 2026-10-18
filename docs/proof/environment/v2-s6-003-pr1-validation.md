# Validation: the freeze records of the reliability experiments (V2-S6-003-PR1)

Status: **static, C0.** This change registers five freeze records before any run of
the experiments they fix, and adds one read-only check. Nothing ran: no cluster was
read or changed, no fault was injected, no Git switch or other commit was made to
`main`, and no caller request was sent. A freeze record is not evidence.

## What the change adds

| Item | Path |
|---|---|
| V2-E02A freeze, revision 1, 226 pins | [`docs/proof/experiments/v2-e02a/freeze-r1.v1alpha1.json`](../experiments/v2-e02a/freeze-r1.v1alpha1.json) |
| V2-E02B freeze, revision 1, 226 pins | [`docs/proof/experiments/v2-e02b/freeze-r1.v1alpha1.json`](../experiments/v2-e02b/freeze-r1.v1alpha1.json) |
| V2-E02C freeze, revision 1, 217 pins | [`docs/proof/experiments/v2-e02c/freeze-r1.v1alpha1.json`](../experiments/v2-e02c/freeze-r1.v1alpha1.json) |
| V2-E04 freeze, revision 1, 217 pins | [`docs/proof/experiments/v2-e04/freeze-r1.v1alpha1.json`](../experiments/v2-e04/freeze-r1.v1alpha1.json) |
| V2-E05 freeze, revision 1, 217 pins | [`docs/proof/experiments/v2-e05/freeze-r1.v1alpha1.json`](../experiments/v2-e05/freeze-r1.v1alpha1.json) |
| Five registry rows | [`docs/proof/experiments/registry.v1alpha1.json`](../experiments/registry.v1alpha1.json) |
| The check, 12 rules | [`tools/experiment_preregistration`](../../../tools/experiment_preregistration/core.py) |
| The suite | [`tests/testing/test_experiment_preregistration.py`](../../../tests/testing/test_experiment_preregistration.py) |
| The description | [The reliability experiment freezes](../experiments/README.md#the-reliability-experiment-freezes) |

The registered content digests are stated in the registry and written out in
`tests/testing/test_experiment_freeze.py`, so that a change to one is visible in review.

## The prerequisites, checked before the branch was made

| Prerequisite | Observed at `710e4c3` |
|---|---|
| The corrective story merged | Pull requests #151 and #152 are merged into `main` |
| A selected qualification | `q1-2` is `QUALIFIED`, stable identity `sha256:6a219b3f…cd5c` |
| A Q2 source that states S | `q2-2` is `CHARACTERIZED`, S = 11,000 ms |
| A Q3 source that states G | `q3-2` is `CHARACTERIZED`, G = 10,113 ms |
| One provider, environment, release, and qualification | `q2-2`, `q3-2`, and `bounds-r1` each state docker-desktop, the digest above, release `b5457f49…`, and `q1-2` |
| A committed matching bound record | `bounds-r1`, LF SHA-256 `542b05dd…8116`; `python -m tools.experiment_bounds --check` passed |
| The qualification rebuilds | `python -m tools.environment_qualification --check` passed for `q1-1` and `q1-2` |
| `q3-1` is kept | Its record is `REFUSED` and unchanged |

## Decisions, and who made them

The repository owner chose each of these before the records were written.

1. **E02A is delivered by the same Application and path as E02B.** A preregistered Git
   switch replaces the two desired-state files with the baseline profile's files, byte
   for byte, before the first E02A run, and restores the target's files before the first
   E02B run. The switch is later work under an E02A revision. No switch is authorized.
2. **No driver in this change.** Each record states the full procedure. Each scope names
   the record's empty `procedure/` directory, so a driver added there is listed as added,
   and the change that adds it registers a revision that pins it before any run.
3. **R = 210,000 ms for E05**, a conservatively selected threshold: the documented
   defaults of 120 s and up to 60 s of jitter, plus 30 s. It is not a guarantee, and the
   earlier 2 to 4 s self-heal observation is stated as prior knowledge.

Decisions taken in writing the records, before any run, and stated in them:

- **The Q4 bounds are shared experiment references.** They were derived on the target
  release, and the records do not attribute them to the baseline. No criterion of E02A
  uses a bound. No baseline-specific qualification is required for that reason.
- **E04's `recoveryEnd` is the start of the stabilization span.** The analysis states
  `stabilizedAt` at the end of a span of at least 60 s, which could never be within
  52,000 ms. The record states this.
- **E04's operator detection rule** is a pod of a new template hash that is not Ready
  after twice `runtime_start_bound_ms`, 22,000 ms.
- **The observation limits, windows, runner durations, and collector settings** are 600 s,
  fault + 720 s, 1,500 s, and pauses of 2 s and 15 s for E02 and E05, and 1,680 s,
  fault + 1,800 s, and 2,700 s for E04.
- **Repetitions.** A counted run is never replaced. An excluded run is kept, at most six
  runs start for an E02 experiment and four for E04 and E05.

## Validation

Run from Git Bash on the staged tree of the first commit, before this section was
written. This section is the one file that changed after the lane.

| Check | Command | Result |
|---|---|---|
| Freeze check | `python -m tools.experiment_freeze --check` | `PASSED: 17 freeze record(s), every rule held` |
| Preregistration check | `python -m tools.experiment_preregistration --check` | `PASSED: 5 experiment record(s), every rule held` |
| Changed inputs of every record | `python -m tools.experiment_freeze --changes RECORD`, for each | The five new records list none. Each of the twelve earlier records lists the same count as before this change |
| Consumed records | `python -m tools.experiment_bounds --check`, `python -m tools.environment_qualification --check`, `python -m tools.baseline_profile --check` | Each passed |
| Lint and format | `ruff check .`, `ruff format --check .` | All checks passed; 788 files already formatted |
| Types | `mypy tools tests/testing/test_experiment_preregistration.py`, and with `--platform linux` | No issues in 189 source files, both |
| Whitespace | `git diff --cached --check` | Clean |
| Default lane | `python -m pytest -q` | 22,867 passed, 42 skipped, 14 deselected, in 55 min |

## What this does not establish

- That any experiment passes or fails. No run exists.
- That the procedure is executable as written. No driver exists, and the procedure was
  not rehearsed.
- That a pinned input stays unchanged. `--changes` lists a moved input for a run.
- Anything about another provider, node, release, or caller workload.
