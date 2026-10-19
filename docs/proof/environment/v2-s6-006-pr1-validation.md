# Validation: the V2-E03 and V2-E06 freezes, and the pre-run readiness review (V2-S6-006-PR1)

Status: **static, C0.** This change registers revision 1 of the freeze records of V2-E03
and V2-E06 before any run of an experiment whose runs they read, and adds one read-only
check. It also records the consolidated pre-run readiness review of every latest
result-bearing and analysis freeze. Nothing ran: no cluster was read or changed, no fault
was injected, no caller request was sent, no analysis was executed, and no figure of
V2-E03 or V2-E06 was computed. A freeze record is not evidence.

## What the change adds

| Item | Path |
|---|---|
| V2-E03 freeze, revision 1, 120 pins, four validity criteria | [`docs/proof/experiments/v2-e03/freeze-r1.v1alpha1.json`](../experiments/v2-e03/freeze-r1.v1alpha1.json) |
| V2-E06 freeze, revision 1, 143 pins, five validity criteria | [`docs/proof/experiments/v2-e06/freeze-r1.v1alpha1.json`](../experiments/v2-e06/freeze-r1.v1alpha1.json) |
| Two registry rows | [`docs/proof/experiments/registry.v1alpha1.json`](../experiments/registry.v1alpha1.json) |
| The check: 14 rules for V2-E03 and 13 for V2-E06 | [`tools/analysis_preregistration`](../../../tools/analysis_preregistration/core.py) |
| The suite | [`tests/testing/test_analysis_preregistration.py`](../../../tests/testing/test_analysis_preregistration.py) |
| The description | [The analysis experiment freezes](../experiments/README.md#the-analysis-experiment-freezes) |

The registered content digests are `8efdb239bb1b3ad5901d31b8cc7c7d45edd7059366bc7e7ad7fcd389b004117a` (V2-E03) and `10e28991745dd5ad32ba3b6c55ef8aeefae26bb7f99c47302b7dcb6bb497f82f` (V2-E06). Each
is stated in the registry and written out in `tests/testing/test_experiment_freeze.py` and
`tests/testing/test_analysis_preregistration.py`, so that a change to it is visible in
review.

## The prerequisites, checked before the branch was made

| Prerequisite | Observed at `938e9f3` |
|---|---|
| The clock policy is merged | Pull request #154 is merged into `main`: revision 2 of V2-E02A, V2-E02B, V2-E02C, and V2-E05, under rule set 2 |
| The governed reversal timing is merged | Pull request #155 is merged into `main`: revision 2 of V2-E04, under rule set 3 |
| The latest revisions of V2-E02A, V2-E02B, V2-E02C, V2-E04, and V2-E05 state one clock policy | Each `definition.clockPolicy` has the canonical SHA-256 `c8343a26197dd3cbd346016dd492964ff5dbcce653daa6863530360ccbc64896`, and `python -m tools.experiment_preregistration --check` passed |
| No run of V2-E02A, V2-E02B, V2-E02C, V2-E04, or V2-E05 exists | No `runs/` or `procedure/` directory exists under any of the five experiment directories |
| The repository owner decided the freeze of V2-E03 and V2-E06 | On 2026-10-18, after the date that was set for it. Each record states the late date |

## The decisions as frozen

- **The V2-E03 population.** The initial analysis reads the valid, counted runs of
  V2-E02A, V2-E02B, and V2-E02C under their bound revisions. The extension adds the
  counted runs of V2-E04 under its latest revision, once they exist, and the initial
  result stays published. A later source revision needs a later revision of the record.
- **The V2-E05 scope rule.** V2-E05 is not in the population, and no signal is ranked on
  its runs, because it is an optional source, no planned change extends the analysis over
  it, and a reverted drift is a scenario that the ranking does not preregister.
- **The operational signal candidate.** Signal 2, the API canonical error rate. Its one
  role is the comparator of the ranking. It meets the comparator condition trivially,
  because it is compared with itself, so it has no ranking preference, and it is not a
  predetermined winner. The caller record stays the reference truth.
- **The uncounted-caller-failure rule.** For each failed outcome of the caller record, the
  record states how it is identified and whether it can state a canonical error code: only
  `http-error` can. The false-healthy time of every signal counts every failed
  completion, and each run reports the failures without a canonical code and the failures
  with no matching error-counter change.
- **The V2-E06 statistic.** The mean processor use of the API in one run, in cores, from
  `api-cpu-seconds` of the `resources` stream of the counted runs of V2-E02A and V2-E02B,
  over the valid pairs of consecutive readings in the window, with the median of each
  side. A reading with no series is not zero. API memory and every resource of the serving
  runtime are labeled unavailable, with their reasons.

## The source bindings

| Record | Source | Role | Path | Content digest |
|---|---|---|---|---|
| V2-E03 | V2-E02A | initial | `docs/proof/experiments/v2-e02a/freeze-r2.v1alpha1.json` | `edd57be9aca1574d975592f3152c6ad67acfcfd705c4d6478c96a56f5faa4562` |
| V2-E03 | V2-E02B | initial | `docs/proof/experiments/v2-e02b/freeze-r2.v1alpha1.json` | `be4cc00beaa93fee52eb1625fd6c71a1ff31bade06cd726a9d7958fa44a94e0c` |
| V2-E03 | V2-E02C | initial | `docs/proof/experiments/v2-e02c/freeze-r2.v1alpha1.json` | `abcf6af5e3d3c050df5b028ac94163c6bda9de5ee1bfe557fe725de87ea3a818` |
| V2-E03 | V2-E04 | extension | `docs/proof/experiments/v2-e04/freeze-r2.v1alpha1.json` | `fae41b8b244cda76e1325ff36e305705d620163bcfac8c1e7bffec2c61b1e619` |
| V2-E06 | V2-E02A | baseline | `docs/proof/experiments/v2-e02a/freeze-r2.v1alpha1.json` | `edd57be9aca1574d975592f3152c6ad67acfcfd705c4d6478c96a56f5faa4562` |
| V2-E06 | V2-E02B | target | `docs/proof/experiments/v2-e02b/freeze-r2.v1alpha1.json` | `be4cc00beaa93fee52eb1625fd6c71a1ff31bade06cd726a9d7958fa44a94e0c` |

Each digest is that of the file and of its registry pin. Both records state the clock
policy digest above, the qualification `q1-2`, the caller profile RP-1 revision 1, and
`bounds-r1`, as their sources state them.

## The checks and the tests of each record

`python -m tools.analysis_preregistration --check` holds V2-E03 to 14 rules and V2-E06 to
13, listed in [the experiments page](../experiments/README.md#the-analysis-check). Seven
rules of each have the same form and separate identifiers: the record exists, its shape,
every freeze field answered, the source bindings, the values stated for the sources, the
contradiction scan of the clock rules, and the analysis-code rule. The other seven of
V2-E03 read its population, its signal set, the streams of its signals, its candidate,
its ranking rule, its caller-failure rule, and its computations. The other six of V2-E06
read its views, its labels, its metrics, its utilization statistic, its cost basis, and its
evidence target.

The suite plants each defect in a copy of the registry and the freeze records, and asserts
the exact findings:

- **V2-E03, refused:** a removed signal; an eleventh signal without the exploratory label,
  and an exploratory one that is ranked; a stale source digest; a source that is a
  superseded revision; a later source revision registered after the record; a signal
  stream that no source collects; a sampling interval other than that of the source
  collection; a query outside the registered telemetry queries; V2-E05 in the population;
  a V2-E05 scope rule without its reason; V2-E04 in the initial population; a missing
  candidate; a candidate declared a winner; any signal declared a winner; another signal
  as the candidate; a removed comparator statement, and one without either of its two
  phrases; a removed caller-failure rule, and one that misses an outcome or a figure; an
  unanswered and a pending freeze field; a source value that differs from its source; a
  claim of synchronized clocks; an ordering rule without the margin; a missing signal read
  as healthy; a ranking on one figure alone; a scope without its procedure directory; a
  missing record; and ten malformed members, which give findings and never an error.
  Accepted: an eleventh signal that is labeled exploratory and is not ranked.
- **V2-E06, refused:** a stale source digest; a view labeled measured that reads requests
  only; a metric labeled measured that reads only limits, a claim request, or requests and
  limits; a missing utilization statistic, and a missing utilization member; source runs
  that are not the fixed ones; a missing cost basis; a cloud cost without a later
  revision; an unanswered freeze field; a View B side that is not reconstructed; a View A
  side that differs from its source; another evidence target; and a missing metric with a
  missing headroom definition.
- **Historical:** the freeze check and the reliability preregistration check still pass
  over every committed record; the two records are the last two registry rows, so no
  earlier row moved; and the pins of each source record differ from the tree exactly as
  on `main`, so this change moves none of them.

## The consolidated pre-run readiness review

Each latest result-bearing and analysis freeze, read at the commit of this change. A
`--changes` result is `python -m tools.experiment_freeze --changes RECORD`.

| Record | Registered digest | Supersedes | Rule set | `--changes` | Clock policy | Bounds |
|---|---|---|---|---|---|---|
| V2-E02A revision 2 | `edd57be9…4562` | revision 1, `adfd9511…d1fc` | 2 | exit 1: `tools/experiment_preregistration/core.py` | `c8343a26…4896` | `bounds-r1`; no criterion uses a bound |
| V2-E02B revision 2 | `be4cc00b…4e0c` | revision 1, `27c5934b…56e5` | 2 | exit 1: the same file | `c8343a26…4896` | `bounds-r1`; 20,226 ms in an observation that is not a pass criterion |
| V2-E02C revision 2 | `abcf6af5…a818` | revision 1, `b41a9a69…2352` | 2 | exit 1: the same file | `c8343a26…4896` | `bounds-r1`; 20,226 ms in E02C-AC10 |
| V2-E05 revision 2 | `f7e1da03…95b2` | revision 1, `420255fd…7492` | 2 | exit 1: the same file | `c8343a26…4896` | `bounds-r1`, no Q4 bound in a criterion; its own reconciliation bound, 210,000 ms, in E05-AC9 |
| V2-E04 revision 2 | `fae41b8b…e619` | revision 1, `0dcc3b1c…4e5d` | 3 | exit 0 | `c8343a26…4896` | `bounds-r1`; 52,000 ms in E04-AC12, 20,226 ms in E04-AC11, and 11,000 ms in the detection rule |
| V2-E03 revision 1 | `8efdb239…117a` | none | not applicable: its own check | exit 0 | `c8343a26…4896`, bound to its four sources | `bounds-r1`, named; no criterion uses a bound |
| V2-E06 revision 1 | `10e28991…f82f` | none | not applicable: its own check | exit 0 | `c8343a26…4896`, bound to its two sources | `bounds-r1`, named; no figure uses a bound |

**What is still owed before the first run of each, and the verdict:**

| Record | Owed before its first run | Verdict |
|---|---|---|
| V2-E02A revision 2 | A later revision that classifies the moved `core.py` pin; the driver, under a later revision that pins it; and the preregistered Git switch of the two desired-state files to the baseline profile and back, whose commit moves the pins of the desired-state tree | **Not ready to run.** Its P1 refuses a run while `--changes` exits 1 |
| V2-E02B revision 2 | A later revision that classifies the moved `core.py` pin, and the driver under a later revision | **Not ready to run**, for the same reason |
| V2-E02C revision 2 | A later revision that classifies the moved `core.py` pin, and the driver under a later revision | **Not ready to run**, for the same reason |
| V2-E05 revision 2 | A later revision that classifies the moved `core.py` pin, the driver, and the drift injector, each under a later revision | **Not ready to run**, for the same reason |
| V2-E04 revision 2 | The driver, the bad-release fixture, and the machine-readable known-good identity record, each under a later revision that pins it | **Not ready to run**: its pins are unchanged, and the three items do not exist |
| V2-E03 revision 1 | The analysis code, under a later revision that pins it; and, because each source registers a later revision before its first run, a later revision that binds the source revisions of the counted runs | **Frozen and complete for this change.** No analysis may run under revision 1 |
| V2-E06 revision 1 | The analysis code, under a later revision that pins it, and a later revision that binds the source revisions of the counted runs of V2-E02A and V2-E02B | **Frozen and complete for this change.** No analysis may run under revision 1 |

The four exits of 1 are not caused by this change. `V2-S6-005-PR1` moved the `core.py`
pin of the four records of rule set 2, and its validation record states it. This change
edits no file of `tools/experiment_preregistration`, and a test holds that each source
record differs from the tree exactly in that one file, or, for V2-E04, in none.

**No result-bearing run, analysis, or later-sprint implementation exists.** No `runs/`,
`procedure/`, `analyses/`, or `corrections/` directory exists under V2-E02A, V2-E02B,
V2-E02C, V2-E03, V2-E04, V2-E05, or V2-E06. No driver, bad-release fixture, known-good
identity record, drift injector, signal analysis, or resource calculation exists. A test
holds the absence of the run, procedure, and analysis directories.

## What stays unchanged

- Every existing freeze record and revision, and its registry row. The two new rows are
  added after the last row, and the registry test holds every earlier pin.
- `q1-1`, `q2-1`, `q3-1` (`REFUSED`), `q1-2`, `q2-2`, `q3-2`, their freezes, and
  `bounds-r1`.
- `tools/experiment_preregistration`, `tools/experiment_freeze`,
  `tools/reliability_analysis`, `tools/experiment_telemetry`, and every other tool that a
  freeze record pins. The new package is outside the import closure of every earlier
  record.
- Released V1 history and `v1.0.0`.

## Validation

Run from Git Bash. The first table is of the first commit.

| Check | Command | Result |
|---|---|---|
| Analysis check | `python -m tools.analysis_preregistration --check` | `PASSED: 2 analysis experiment(s), every rule held` |
| Freeze check | `python -m tools.experiment_freeze --check` | `PASSED: 24 freeze record(s), every rule held` |
| Reliability preregistration check | `python -m tools.experiment_preregistration --check` | `PASSED: 5 experiment record(s) and 5 superseded revision(s), every rule held` |
| Changed inputs of the two new records | `python -m tools.experiment_freeze --changes` for V2-E03 and V2-E06 revision 1 | `UNCHANGED`, exit 0, each |
| Changed inputs of the source records | the same, for the five latest source revisions | V2-E04 revision 2 exit 0; V2-E02A, V2-E02B, V2-E02C, and V2-E05 revision 2 list `tools/experiment_preregistration/core.py` alone, exit 1, as on `main` |
| Bounds | `python -m tools.experiment_bounds --check` | `PASSED: 1 committed bound record(s), each is what its source records give` |
| Consumed records | `python -m tools.environment_qualification --check`, `runtime_startup`, `caller_characterization`, and `baseline_profile` | Each exit 0 |
| Evidence layout | `python -m tools.experiment_evidence repository` | Exit 0: 11 runs, 0 refused |
| Evidence index | `python -m tools.evidence_index --check`, and `--gate` | Both exit 0 |
| Lint and format | `ruff check .`, `ruff format --check .` | All checks passed; 795 files already formatted |
| Types | `mypy tools` and the changed test modules, and with `--platform linux` | No issues, both, after one fix: an unused `type: ignore` in the new suite |
| Testing and security suites, which include the document-link tests | `python -m pytest tests/testing tests/security`, all files staged | 9,908 passed, 3 skipped |
| Whitespace | `git diff --cached --check` | Clean |
| Default lane | `python -m pytest -q` | 23,135 passed, 42 skipped, 14 deselected, in 41 min |

## What this does not establish

- That a signal states caller impact, that one signal is earlier or more caller-truthful
  than another, or that the reliability topology has any resource cost. No figure exists.
- That the analysis code that a later change adds follows these records. The records state
  the rule, and the check reads the records, not code.
- That the definitions of the records are right. The check reads structure, identifiers,
  intervals, and named phrases.
- That a source run will be counted. Each source states its own outcome and exclusion
  rules.
- Anything about V2-E07. Its freeze is not part of this change.
