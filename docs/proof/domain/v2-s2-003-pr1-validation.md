# V2-S2-003-PR1 validation

Date: 2026-10-02

What this change checked before it was committed, and how. What it publishes is in
[V1 synchronous compatibility](../../domain/v1-synchronous-compatibility.md) and
[experiment freeze records](../experiments/README.md); this page is about the checks run
over the repository after the code, its suites, and the documents were written.

The change executed nothing against a host: no cluster, runtime, registry, or model was
contacted, and nothing was installed, provisioned, or published. `helm` ran locally to
render and lint templates, which contacts nothing. Every check below is static, which is
`C0` under [the evidence levels](../../testing/evidence-levels.md). **No part of V2-E01
ran.** The change commits the E01 family freeze so that the first E01 run can use it; the
suites below are unit and documentation tests, not E01 runs, and no experiment result is
recorded. The change adds no record to the evidence pack and moves no claim.

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `3801f75`, the merge of `V2-S2-002-PR1`,
  so the renderer, the generated release, the writer, admission of hand-written values,
  and the drift check over the reference release were in place.
- **The target is the released workload.** `git diff --stat v1.0.0 HEAD` over the chart
  directory, the reference contract, the compatibility matrix, the model-source record,
  and the runtime-profile record printed nothing: those files are byte for byte what
  `v1.0.0` released.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0 with
  `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` at `718ad2e0…` with the set `1d40b33f…`
  and the pack `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack
  `0c2f2508…`. It reported the same five values after the change: no file this change
  touches is cited by a record.

## What changed

- **V1 synchronous compatibility.** A record,
  [`v1-synchronous-compatibility.v1alpha1.json`](../../domain/v1-synchronous-compatibility.v1alpha1.json),
  with one row for each of the 40 chart values the V1 real release or its V2 render sets,
  and [its page](../../domain/v1-synchronous-compatibility.md). A new suite,
  [`tests/domain/test_v1_sync_compatibility.py`](../../../tests/domain/test_v1_sync_compatibility.py),
  holds every row against the code and the committed files.
- **Chart checks.** Two tests in
  [`tests/architecture/test_helm_chart.py`](../../../tests/architecture/test_helm_chart.py)
  render the committed generated release with the reference hand-written file and compare
  it with the V1 render, lint the pair under `--strict`, and read from lint's report what
  the chart's guards require beyond the generated values.
- **The freeze format and its check.** [`tools/experiment_freeze`](../../../tools/experiment_freeze/core.py),
  with `--check` and `--changes`, the [records page](../experiments/README.md), and the
  suite [`tests/testing/test_experiment_freeze.py`](../../../tests/testing/test_experiment_freeze.py).
- **The V2-E01 family freeze, revision 1.**
  [`freeze-r1.v1alpha1.json`](../experiments/v2-e01/freeze-r1.v1alpha1.json), pinned in
  `FROZEN_RECORDS`.
- **Documents.** The renderer page, the contracts index, the proof index, the README's
  contracts row, the contributor guide, the changelog, and the test inventory, whose
  count phrases moved: fourteen `unit` modules, fifty `documentation` modules, and
  sixty-three modules that defend no claim.

## What the change was asked to reach, and what it reached

| Criterion | State after this change |
|---|---|
| The V1 synchronous real workload renders successfully through V2 | Reached at `C0`. The reference inputs render; the generated values satisfy the chart's schema; with the hand-written file they render the V1 manifests under the contract's environment label and lint under `--strict` with no guard failing |
| No claim-relevant workload intent must be handwritten after rendering | Asserted for the reference workload: the hand-written file is admitted, every contract-owned chart value is generated, and the chart's guards require only six hand-written values, none contract-owned. Two hand-written strings repeat contract pins; that is measured and stated, not closed |
| Intentional ownership migration recorded | Reached: the record and its page, with the one intended difference |
| An E01 freeze record carrying every freeze field merges before any E01 result-bearing run | Committed here. It merges with this change; no E01 run has happened |
| E01-A/B/C frozen completely as `C0`; E01-D's procedure and criteria frozen as `C2`; E01-D's environment identity pending on `V2-S3-004-PR1` | Reached, and held by the freeze suite |
| A check fails when a freeze field is missing or empty | Reached: `python -m tools.experiment_freeze --check`, run by the default lane |
| A merged record is not edited in place | Enforced by the content-digest pin; a change is a new revision |
| Two clean identical renders match | Pending: the E01-A run, after the freeze merges |
| A controlled contract mutation changes only expected semantic output | Pending: the E01-B run |
| Invalid and conflicting cases refuse deterministically | Pending: the E01-C run |
| Static evidence is `C0` and does not claim runtime deployment | Holds: nothing here claims a deployment |

The repository's existing suites already render twice, mutate the replica count, and
refuse each case. Those are development tests. They are not E01 runs, and the freeze
record says so.

## Decisions taken while writing, and what was left out on purpose

Each is a decision rather than a fact, recorded so a later change can revisit it.

1. **The environment label is an intended difference.** V1 labels its run `dev`, the
   chart's default; the contract owns the label in V2 and the reference contract declares
   `local`. No `dev` contract or binding was added to make the bytes equal, because the
   run is local and the label follows the contract.
2. **Four hand-written classes.** `platform-component` for the API image,
   `model-acquisition`, `model-metadata`, and `host-operation`. The API image is a
   platform component every workload shares, not workload intent; no input owns it while
   no image is published.
3. **The two strings that repeat contract pins are measured, not closed.** Deriving the
   download URL and the licence reference from the contract would need a derivation rule
   nobody has decided, and would change the renderer and the golden release. The
   acquisition's digest check is what refuses other bytes.
4. **The chart checks are tests in the chart suite, not new workflow steps.** The CI job
   that installs a pinned Helm already runs that suite and fails on a skip, so no workflow
   or gate-matrix change was needed. `kubeconform` was not run over the pair. The pair
   renders what the V1 values render under the contract's label; CI validates the V1
   render with `kubeconform`, and the two renders differ in two string values.
5. **The freeze format.** One JSON record per revision, at
   `docs/proof/experiments/<family>/freeze-r<N>.v1alpha1.json`. Each of the 13 fields is a
   list of entries covering every part once. No convention for freeze records existed, so
   the format is minimal, and only E01 is frozen.
6. **Pins, not a commit.** A record cannot name the commit that merges it, so the record
   pins 67 inputs by content digest and names `3801f75…` as the revision it was prepared
   from. The renderer's 39 pinned files are the modules that importing the domain's
   render, environment, workload, and release packages loads, measured on this branch.
7. **No test compares the pins with today's files.** Such a test would refuse every later
   change to the renderer until a freeze revision existed. The planned order is the
   reverse: a change may merge, and the run's precondition refuses to start until a merged
   revision classifies it. `--changes` lists what moved.
8. **Six E01-C cases.** Schema-invalid, semantic-invalid, two ownership conflicts, an
   unsupported profile, and an unsupported capability. One ownership conflict, a binding
   that supplies the contract's replica range, is refused by the binding parser, which
   publishes a code and a field and no rule category; the record states that.
9. **The expected refusals were calibrated, and that is not evidence.** Each case's
   expected refusal is the one the published rule table assigns. A scratch script, not
   committed, ran each case's inputs once to check that before the record was written. The
   record says that check is not an E01 run.
10. **One later story identifier is public.** The pending entry must name its owner, so
    `V2-S3-004-PR1` appears in the record, the check's allowance, and the records page. No
    other later identifier appears; a test holds that for the record.
11. **A stale sentence fixed.** The contracts index said the renderer does not exist,
    which has been false since `V2-S2-001-PR1`. It now names the renderer page.

## What the checks caught before the first commit

- **Lint is not a check of the guards.** `helm lint --strict` over the generated values
  alone exits 0 and reports six `[INFO] Fail:` lines. A test built on the exit status
  would have passed with a guard failing, so both chart tests read the report.
- **A placeholder list that refused an answer.** The first draft of the field check
  treated the word `none` as a placeholder, which refused the record's own answer
  "cluster: none". It was removed from the list.
- **A file off the experiment path was pinned.** The chart's `README.md` was among the
  pinned inputs; Helm does not render it, so it was dropped, and 68 pins became 67.
- **A later story identifier in a test.** A test of a wrong pending owner used a real later
  story identifier; it now uses `another-owner`.
- `ruff` flagged an unsorted `__all__` and `mypy` a lambda returning a tuple; both fixed.

## Checks that the new tests are not decorative

- **The compatibility record.** Eleven misstatements are planted in a copy of the record -
  a row removed, a row for a value nobody sets, a wrong owner, context value, V1 source,
  or class, a generated value called hand-written, a restated pin left out, the
  difference left out, a wrong difference value, and a blank reason - and each is caught.
  A hand-written file that sets `model.revision` again is caught as both generated and
  hand-written.
- **The chart checks**, by hand with `helm`: a hand-written file whose `model.alias`
  differs renders other manifests than the V1 values, and a hand-written file without
  `model.alias` lints with exit status 0 and reports `Fail: model.alias is required`.
- **The freeze check** (first commit). Each of the 13 fields is removed in turn; 19 field defects, 6 misplaced pending entries, 6 wrong shapes, and 8 malformed pins are
  planted; and on a copy of the records directory, an edit, an unpinned record, an absent
  one, a misnamed one, a wrong and a skipped revision, a wrong predecessor, a first
  revision that supersedes something, and an unclassified moved input are each refused,
  while a CRLF checkout and a correctly classified revision are not.

## Commands

```sh
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked python -m mypy
uv run --locked python -m pytest tests/domain/test_v1_sync_compatibility.py tests/testing/test_experiment_freeze.py -q
uv run --locked python -m tools.ci_gates no-skips helm
uv run --locked python -m tools.generated_release --check
uv run --locked python -m tools.experiment_freeze --check
uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r1.v1alpha1.json
uv run --locked python -B -m tools.evidence_index --gate
uv run --locked python -m pytest -q
git diff --check
gitleaks dir <each changed file> --config .gitleaks.toml --redact --no-banner
```

All ran from Git Bash on Windows, with Helm `v3.19.0`, the version the CI job pins.

## Results

| Check | Result |
|---|---|
| `ruff format --check`, `ruff check`, `mypy` | Clean: 600 files formatted, no lint finding, no type error in 332 source files |
| The two new suites | 107 passed |
| `no-skips helm` | The chart suite ran 203 tests with none skipped |
| `tools.generated_release --check` | The reference release is what its declared sources derive |
| `tools.experiment_freeze --check` | 1 freeze record, every rule held |
| `tools.experiment_freeze --changes` | Every pinned input has its pinned content |
| `tools.evidence_index --gate` | Exit 0; the five values above, unchanged |
| The default lane | 17,354 passed, 35 skipped, 14 deselected, in 17 minutes. The 35 skips are the ones the lane had before this change |
| `git diff --check` | Clean |
| `gitleaks` 8.30.1, the CI pin, with the repository's configuration | No finding in any of the 20 changed files, scanned as files before the commit |

## What the independent review found

An independent review read the first commit against the change's requirements, ran the
suites and the six E01-C cases' inputs, and recounted the published numbers. It found no
critical or high finding. It confirmed the E01-C expectations, the E01-B expected change,
the coverage of the experiment's procedure and criteria, the 67 pins, and the record's
counts. What it found, and what was done:

1. **`not-applicable` was accepted on any field.** The first commit's check required only
   a reason, so `acceptanceCriteria` or `abortConditions` answered "not applicable" for
   every part passed. The records page said `not-applicable` is for a part with no
   counterpart, which the code did not enforce. Fixed: eight fields every run has are
   listed in `ALWAYS_ANSWERED`, and `not-applicable` is refused for them under a new rule,
   `freeze-field-always-answered`.
2. **Two criteria overstated against the record's own limitation.** E01-AC5 and
   E01-AC10 said no claim-relevant workload intent is written by hand, while a limitation
   said the two strings that repeat contract pins are not covered. A criterion that is
   true only because a separate line carves out part of it is an overclaim. Fixed: both
   criteria and the hypothesis now name the two strings as the one exception. The record
   had not merged, so revision 1 was corrected and re-pinned rather than revised; its
   content digest moved from `b5674111…` to `fcb19502…`.
3. **Statements of a refusal no code makes.** The records page, the contributor guide,
   and the record said a run "cannot" or "does not" start in two cases. No runner exists.
   The records page now lists the refusal as a procedure that nothing enforces, and the
   contributor guide says so.
4. **Placeholders are detected only as whole strings.** The page said "a stand-in such as
   `TBD`", which implied more. It now says "exactly", and that a stand-in inside a longer
   string is not detected. `.` and `...` were added to the stand-ins.
5. **Criteria had no structure check.** A new rule, `freeze-criteria-malformed`, requires
   an `id` and a `statement` for each criterion and refuses an `id` used twice in a record.
6. **Two abort lists left items out without saying why.** Each now carries a note: the
   static parts have no cluster, caller stream, fault, or spend, and E01-D runs no caller
   workload and injects no fault.
7. **Later experiment identifiers as test data.** Two tests used later experiment
   identifiers as arbitrary names. They now use `EXP-OTHER`, `exp-a`, and `exp-b`.
8. **Pinning `uv.lock` makes every dependency update a moved input.** Kept, because the
   parsers are on the experiment path; the records page now says so.

Declined, with the reason:

- **Refuse a pin whose file is absent.** A merged record would then fail `--check` for
  ever after a later, legitimate deletion of a pinned file, which is the gate this change
  chose not to build (decision 7). `--changes` reports an absent input, and the records
  page now lists this as not enforced.
- **The commit trailer.** The review read the attribution line as wrong. It is the one
  this session was instructed to use, and earlier commits carry the same line.

### Results after the fixes

| Check | Result |
|---|---|
| `ruff format --check`, `ruff check`, `mypy` | Clean: 601 files formatted, no lint finding, no type error in 332 source files |
| The two new suites | 121 passed: 25 for compatibility, 96 for the freeze check |
| `no-skips helm` | The chart suite ran 203 tests with none skipped |
| `tools.generated_release --check` | The reference release is what its declared sources derive |
| `tools.experiment_freeze --check` and `--changes` | 1 freeze record, every rule held; every pinned input has its pinned content |
| `tools.evidence_index --gate` | Exit 0; the same five values |
| The default lane | 17,368 passed, 35 skipped, 14 deselected, in 18 minutes: the first run's 17,354 and the 14 tests the fixes added |
| `gitleaks` over the files the fixes changed | No finding in any of the 10 files |

## Privacy and publicability

The diff was read for private planning text, local paths, credentials, and later story
identifiers. The record, the pages, and the tests describe the experiment in this
repository's own words. The one later story identifier is the pending owner, as decision
10 says. No credential, personal path, model artifact, or generated machine state is
committed.

## What this does not establish

- **That any part of V2-E01 passes.** No part ran. The freeze fixes what a run must do; a
  run decides whether E01-A, E01-B, and E01-C pass.
- **That anything was installed or served.** The compatibility checks compare values and
  rendered manifests.
- **That the pinned inputs are unchanged at the commit a run executes.** The run checks
  that, with `--changes`.
- **That E01-D can run.** Its environment identity is pending.
- **That the two hand-written strings that repeat contract pins agree with the contract.**
