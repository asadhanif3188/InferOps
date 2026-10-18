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
  runs start for an E02 experiment, five for E04, and four for E05. (Until the second
  commit this said four for E04.)

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
| Default lane, second commit | `python -m pytest -q`, on the staged tree of the second commit, before this row was written | 22,897 passed, 42 skipped, 14 deselected, in 42 min. The 30 more are the tests that the review added. The freeze check, the preregistration check, ruff, the formatter, mypy on both platforms, the `--changes` command of each new record, and `git diff --check` passed again on that tree |

## Independent review of the first commit

Two independent reviews read the first commit, `9a9f064`: one of the check and its suite,
one of the records and the pages against the experiment definitions and the repository.
Neither found a critical defect. The second commit corrects every finding below. The five
records were regenerated and registered again before this change merged, so their
registered digests are not those of the first commit:

| Record | Registered content digest |
|---|---|
| `v2-e01` | `fcb19502d1d8350395b88293f4e3e2bf92076591e3fa8ecfc814defa46267fa9` |
| `v2-e01` | `198f60b5133338e445b1c0fef9f9171ad3e58fe3bde66ac1e7a8d1d674730ac8` |
| `v2-e01` | `b4aa013dc482a8f536395c094ab76dc2b753e04d7c139a4b0cadf17c672da739` |
| `v2-e02a` | `adfd951101ca5a40cc41c9b196b5394f9217eb82d3befc242671885ef3a0d1fc` |
| `v2-e02b` | `27c5934bb13b55c9ea2495e664f7f06f45886b1d8eacd1abffde293b08d156e5` |
| `v2-e02c` | `b41a9a698301d3c0d4cc1242343d534e4bf63fe200020f2c65113b981dc62352` |
| `v2-e04` | `0dcc3b1c0cba1ee51acc962a083d78a82c42093a75fad72e41b193dde3124e5d` |
| `v2-e05` | `420255fda1b95e0d6c25ce1a262a68a656f1b621d3c7204b682d3298ede47492` |

**What the first commit got wrong, in the check:**

- A malformed record raised a Python error instead of a finding: a `fields` list, a
  `metadata` string, an `exclusionReasons` string, a list as an executable or as a bound
  name, and a bound record with no list of bounds. The shape rule now holds every member
  that a later step reads to its type, and eight malformed kinds are tested.
- An empty `definition.executables` passed the rule against missing pins. A record now
  lists at least one executable, and the entry file of a tool must have its entry module
  in the scope.
- The rule of the baseline difference said that the permitted members are anchored to
  the comparison. Two of them were not: the runtime disruption budget and the statement.
  The budget is now structured and held to the replica count, and the statement is stated
  as free text.
- A criterion's bound figure was found as a substring, so 20,000 ms matched 120,000 ms.
  The figure is now matched whole.
- The identifiers of the two sides were replaced as plain substrings. They are now
  replaced as whole tokens.
- A null identity member passed when the qualification also lacked it. Each member is
  now held to its type.
- Several branches had no test, and two tests asserted membership instead of the exact
  findings. 30 tests were added, and the loose test is exact.
- A finding about the target side named the baseline's record. It now names its own.

**What the first commit got wrong, in the records and the pages:**

- Four public pages still said that no frozen record names the baseline, RP-1, or an
  exclusion reason: the baseline profile page, the RP-1 page, the replay page, and the
  replay suite's inventory note. Each now has a dated note.
- E04's third-run rule required a third run when the two runs differ in a verdict. A
  verdict against a bound differs with a duration alone, so the rule contradicted its own
  next sentence. It is now a causal signature of four facts, and the run ceiling is five.
- An `INCONCLUSIVE` reason had no validity criterion behind it: the outcome rules make a
  run `INCONCLUSIVE` only through a validity criterion, and E02C-AC8 assigned the state
  itself. Each record now has a validity criterion for every stream that its criteria
  read, for an unrelated failure, and for the post-recovery window.
- Instants of two clocks were compared with a bound, and no clock was read. The
  preparation now reads the node clock against the host clock before and after a run, and
  an interval within that bound of a bound is `INCONCLUSIVE` for the new reason
  `clock-bound-reached`.
- E05 reused E02C's unrelated-failure text, which named the pods that its own fault
  removes. It has its own text now. E05 also gains a pass criterion that the controller's
  operation started after the drift, and it keeps the two live ConfigMaps.
- The abort conditions had no codes, while the event log needs one. Each has a code, and
  a manual action has the code `operator-intervention`.
- The latency percentiles were p50, p90, and p99. They are p50, p95, and p99, stated only
  with at least 100 successes.
- The E02A eligibility rule named the aggregate command, which states neither figure that
  the rule reads. It now reads each run analysis.
- The validation record left its validation section to be completed. It was completed
  before the first commit, and this section was added in the second.

Smaller corrections: E05-AC10 and E02C-AC12 name the observation limit and `commands.txt`;
the caller validity criterion refuses a window that starts inside an episode; P4 states
where the capacity gate takes its footprint; the cleanup verifies caller success; the
pods stream's missing node name is a limitation; ADR 0021 R4 keeps its earlier status.

**Choices that the records state and this record did not list in the first commit:**
E02B-AC12, a stabilized recovery inside the limit, is a pass criterion, so a run that
does not stabilize is `FAILED`; E04's `reversalStart` is the controller's first possible
resolution of the reversal, so the discovery time is in the operator interval; and the
unrelated-failure validity criterion, which makes a runtime replacement in E02C
`INCONCLUSIVE`.

**Kept on purpose:** the check imports `_reasons_problem`, a private function of the
analysis tool, so that it reads exclusion reasons as the aggregate does. A change to that
function moves a pin of each record. The tripwire test that compares each pin list with
its scope stays: a file added to a scope moves it.

## What this does not establish

- That any experiment passes or fails. No run exists.
- That the procedure is executable as written. No driver exists, and the procedure was
  not rehearsed.
- That a pinned input stays unchanged. `--changes` lists a moved input for a run.
- Anything about another provider, node, release, or caller workload.
