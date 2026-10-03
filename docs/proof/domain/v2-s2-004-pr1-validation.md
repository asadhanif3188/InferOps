# V2-S2-004-PR1 validation

Date: 2026-10-03

What this change checked before it was committed, and how. What it publishes is in
[the Helm values renderer](../../domain/helm-values-renderer.md),
[V1 synchronous compatibility](../../domain/v1-synchronous-compatibility.md), and
[experiment freeze records](../experiments/README.md); this page is about the checks run
over the repository after the code, its suites, and the documents were written.

The change executed nothing against a host: no cluster, runtime, registry, or model was
contacted, and nothing was installed, provisioned, or published. `helm` ran locally to
render and lint templates, which contacts nothing. Every check below is static, which is
`C0` under [the evidence levels](../../testing/evidence-levels.md). **No part of V2-E01
ran as a result-bearing run.** The test suites execute the runner against temporary
repositories, which freeze revision 2 lists as a non-result execution before any run under
it. The change adds no record to the evidence pack and moves no claim.

## Why this change exists

The first collective review of Sprint 2 returned *blocked* on two findings, both owned by
Sprint 2:

- **F1.** Two hand-written Helm values repeated contract-owned model pins: the download
  URL repeated the repository, revision, and file, and the licence reference the repository
  and revision. Admission accepted a hand-written copy that contradicted the contract, and
  freeze revision 1 stated an exception to the governing E01 criterion for those two
  strings.
- **F2.** The first E01-A/B/C run, `20261002-e01-abc-1`, executed a runner that was not in
  its executing revision and was not a pinned input of revision 1, and revision 1's change
  check compared only the files it listed, so it could not report the runner.

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `26aecfc`, the merge of `V2-S2-003-PR2`.
- **History is untouched.** `git diff --exit-code origin/main` over `docs/releases`,
  `docs/architecture/decisions`, `docs/proof/releases`, `charts`, freeze revision 1, the
  run directory, the model source record, the two V2-S2-003 validation records, the claim
  register, and `docs/proof/testing` printed nothing. `v1.0.0` still resolves to tag
  object `17c9bbd7…` and commit `718ad2e0…`.

## What changed

**F1, renderer ownership.**

- `DERIVED_HELM_VALUES` in `src/inferops/domain/render/helm_values.py` writes
  `model.artifact.sourceUrl` and `model.license.reference` from the contract's model
  repository, revision, and file, under one rule for one source:
  `https://huggingface.co/<repository>/resolve/<revision>/<file>?download=true` and
  `https://huggingface.co/<repository>/blob/<revision>/LICENSE`. The rule is the one the
  V1 model source record follows and the V1 acquisition preflight in
  `tools/model_acquisition` already enforces; a test holds the two to each other.
- Both values are generated values now, so the existing admission rule,
  `render-manual-value-generated`, refuses a hand-written copy that sets, replaces, or
  removes either - whether it agrees with the contract or not. The SPDX identifier stays
  hand-written: no pin determines it.
- A derived string is checked against the chart's constraint and the credential-shape rule
  only when none of its source pins is already refused, so a refused pin is reported once.
- The hand-written reference file loses both strings. The generated reference release has
  27 values, not 25; its values digest moved from `137a97b9…` to `1849af0c…`, and its
  release identifier did not, because the identifier is derived from the sources, not the
  values. The compatibility record now has 27 generated rows (22 owned by the contract,
  2 of them derived) and 13 hand-written ones; the chart's guards require four hand-written
  values, not six.

**F2, the freeze and the executable path.**

- `freeze-r2.v1alpha1.json` supersedes revision 1 by its content digest and leaves it
  unchanged. It restores the governing criterion in the hypothesis, E01-AC5, and
  E01-AC10, without the exception, and adds E01-C-7, a hand-written download URL that
  contradicts the pins. Every one of the 13 freeze fields is answered; E01-D's
  environment identity stays pending on `V2-S3-004-PR1`.
- It declares a material scope: the static import closure of
  `tools.experiment_e01.__main__` within `src/inferops` and `tools`, plus 14 data paths and
  patterns. It pins 74 files. `inputChanges` classifies 11 differences from revision 1:
  four changed files from the F1 correction (three material, the compatibility record
  not), and seven added, all material - the runner and analysis, the freeze checker, and
  the packages they belong to, none of which revision 1 pinned.
- The registry moved from a constant in the freeze checker to
  `docs/proof/experiments/registry.v1alpha1.json`, so the checker can be pinned without
  pinning itself. Revision 1's pin is unchanged: `fcb19502…`. Revision 2's is `198f60b5…`.
- `--changes` now lists `added` and `unscoped` files beside `changed` and `absent` ones.
  Three rules are new: `freeze-scope-missing`, `freeze-scope-malformed`, and
  `freeze-registry-unreadable`; there are 22.
- The runner executes revision 2. Before any part, it refuses unless the runner and the
  `inferops` package are the checkout's own and the record is registered and unedited.
  It records the `inferops` distribution version, the registry digest, and every module
  file it and its second process loaded from `src/inferops/` and `tools/`; an unpinned
  loaded file, or a second process that imported from outside the checkout, aborts the run.
- A committed run is judged by the analysis of the revision it names. The first run is
  still judged by revision 1, byte for byte, and `--check` passes over it.
- Revision 2 states, before any run under it, the executions that are not result evidence,
  the rule against previews, how it avoids pinning itself, and - in `history` - the first
  run's audit limitation and what is and is not available of the earlier previews.

## What the change was asked to reach, and what it reached

| Requirement | State |
|---|---|
| Derive both references from the pins by an explicit rule for the supported source | Reached: `DERIVED_HELM_VALUES` and two tests |
| Remove the duplicated strings; keep independent licence metadata separate | Reached |
| Refuse hand-written values that set, replace, remove, or contradict renderer-owned values | Reached: path ownership, tested for identical, stale, and contradicting copies |
| Regression tests: pin change, stale and contradicting copies, determinism, unrelated output, schema and render | Reached |
| Reconcile the compatibility record, fixtures, ownership mapping, and documents | Reached, except the claim register, below |
| New freeze revision with the §16 criterion restored and every §35 field | Reached |
| Inventory and classify every change since revision 1, added files included | Reached: 11 changes |
| Pin the runner and analysis; detect added, deleted, and changed files | Reached |
| Resolve the self-reference without a mutable exclusion | Reached: the registry is data; revision 2 excludes nothing |
| Execution from the merged checkout, with package identity recorded | Reached in code; a run under it is `V2-S2-004-PR2`'s |
| Non-result executions defined before execution | Reached; the rule against previews is a procedure, not enforced |
| First run kept, with a dated audit limitation; preview evidence stated | Reached: [the audit](../experiments/README.md#audit-of-the-first-run-2026-10-03) |
| No result-bearing run | Held |

**Deliberately left for `V2-S2-004-PR2`.** The claim register is not edited here. Its
current record for the first run still states, as a limitation, that the download URL
and the licence reference repeat contract pins and are not checked against the contract.
That statement describes the first run's inputs correctly and the current renderer no
longer; `V2-S2-004-PR2` reconciles the register additively, with the new run, through a
ledger. The evidence index and the dashboard were checked and are current.

## Checks that the new controls are not decorative

- An added chart template, a new local helper the runner imports, and a pinned file the
  scope no longer names are each listed by `--changes`; revision 1, which has no scope,
  still does not see the added file.
- A run in a temporary merged repository refuses when a material file is added, when the
  record is unregistered, and when the runner and the package come from another checkout,
  and aborts when a loaded module is not pinned or the second process imports from
  another checkout.
- `--check` finds a revision-2 manifest whose recorded loaded modules, identity abort
  conditions, or second-process identity do not agree, and one that drops the identity
  records.
- The first run judged by revision 2 would not reproduce its own page; it is judged by
  revision 1, which does.
- The command, run from a temporary merged checkout with that checkout first on the import
  path, imports the runner and the package from it, passes every precondition, and loads
  only pinned module files.

## Commands

```sh
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked python -m mypy
uv run --locked python -m tools.generated_release --check
uv run --locked python -m tools.experiment_freeze --check
uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json
uv run --locked python -m tools.experiment_e01 --check
uv run --locked python -B -m tools.evidence_index --check
uv run --locked python -B -m tools.evidence_index --gate
uv run --locked python -m tools.proof_dashboard --check
uv run --locked python -m tools.ci_gates no-skips helm
uv run --locked python -m pytest -q -rs
git diff --check
```

All ran from Git Bash on Windows, with Helm `v3.19.0`, the version the CI job pins.

## Results

| Check | Result |
|---|---|
| `ruff format --check`, `ruff check`, `mypy` | Clean: 608 files formatted, no lint finding, no type error in 336 source files |
| `tools.generated_release --check` | The reference release is what its declared sources derive |
| `tools.experiment_freeze --check` | 2 freeze records, every rule held |
| `tools.experiment_freeze --changes` on revision 2 | No material file differs from the record |
| `tools.experiment_freeze --changes` on revision 1 | 4 files differ, the F1 correction's; revision 2 classifies each |
| `tools.experiment_e01 --check` | 1 run, which agrees with its own evidence under revision 1 |
| `tools.evidence_index --check` | The index is what the register and ledgers produce |
| `tools.evidence_index --gate` | Exit 0; released `v1.0.0` set `1d40b33f…` and pack `652e9051…`, current set `0a03ee79…` and pack `4f42e4a1…`, all unchanged by this change |
| `tools.proof_dashboard --check` | The dashboard is what the register produces |
| `tools.ci_gates no-skips helm` | The chart suite ran 203 tests with none skipped, with Helm `v3.19.0`: the generated and admitted values render the V1 manifests, lint under `--strict`, and leave four hand-written values for the guards |
| The renderer, compatibility, drift, freeze, and E01 suites, after the review's fixes | 198 renderer tests passed; 219 freeze and E01 tests passed |
| The default lane, before one wording fix | 17,586 passed, 1 failed, 35 skipped, 14 deselected, in 12 minutes 26 seconds. The failure was the security baseline's reserved-term check on the word "audited" in the records page; the word was replaced and the suites that read that page were run again, below. The 35 skips are the ones the lane had before this change: host symlink privileges, POSIX signals on Windows, an absent collector image, and fixtures a test does not apply to |
| The suites that read the changed pages, after the fix: `pytest tests/security/test_security_baseline.py tests/testing -q` | 8,298 passed, none failed, none skipped |
| `git diff --check` | Clean |
| `gitleaks` | Not run: it is not installed on this host. The hosted CI job runs it over the full history |

## What the independent review found

An independent review read the change before it was committed and reproduced each finding
below before it was fixed. What the first draft got wrong:

- **Every documented run would have aborted.** The first draft counted every module file
  loaded from under the checkout as the run's own. `uv run` keeps its virtual environment
  in `.venv/` inside the checkout, so third-party modules counted as unpinned, and every run
  started the documented way would have been recorded ABORTED. The end-to-end test missed
  it: its temporary checkout had no `.venv/`, and the in-process tests replaced the
  loaded-module record. Now only the record's package directories count, a test plants
  modules under `.venv/` and `tests/`, and an import of the command in this checkout under
  `uv run` counted 47 module files, all pinned.
- **`--check` did not re-verify the execution identity.** A revision-2 manifest without the
  identity records passed, and the list of unpinned loaded modules and the abort condition
  were never recomputed. Now they are, and the second process's identity is an abort
  condition the check recomputes too.
- **The registry is not append-only.** A change can edit revision 2 and its registry pin
  together. A test now writes both registered pins out literally, and the records page
  says nothing else refuses such an edit.
- **A test name overclaimed.** The test named for "pins exactly its material scope" checked
  four members. It now compares the computed scope with the pins.
- **Paths and case.** A Windows drive path passed as relative in a scope, and an import in
  the wrong case resolved on Windows and not on Linux. Both are refused or resolved the
  same way on every host now.
- **A weak default.** The precondition check defaulted to revision 1's checks; the revision
  is now a required argument.

The review confirmed every count this page and the records state.

## Privacy and publicability

The diff was read for private planning text, local paths, credentials, and later story
identifiers. The records and pages describe the change in this repository's own words.
The earlier previews' console capture contains host paths and is not published; the audit
says it exists and does not reproduce it. The one later story identifier is the pending
owner, `V2-S3-004-PR1`.

## What this does not establish

- **That any part of V2-E01 passes under revision 2.** No result-bearing run executed.
- **That anything was installed or served.** The compatibility checks compare values and
  rendered manifests.
- **That the derived licence reference resolves.** Nothing fetches it.
- **That a module loaded by a computed name is in scope.** The closure is static; the run
  records what it loaded instead.
- **That the rule against previews holds.** It is a procedure.
- **That the first run's execution boundary was governed by its freeze.** It was not, and
  its audit limitation says so.
