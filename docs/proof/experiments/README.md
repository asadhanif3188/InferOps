# Experiment freeze records and runs

Status: **format and check added by `V2-S2-003-PR1`**, with one record: the V2-E01 family
freeze, revision 1. **One run added by `V2-S2-003-PR2`**: E01-A, E01-B, and E01-C, executed
once under that record. **Revision 2 added by `V2-S2-004-PR1`**: it restores the governing
no-duplication criterion and freezes the whole executable path, runner and analysis
included. **One run added by `V2-S2-004-PR2`**: E01-A, E01-B, and E01-C, executed once
under revision 2 from the merged checkout. A freeze record fixes an experiment family before its first
result-bearing run. A record is not evidence: it says what a run must do and what counts as
a pass. A run is evidence, and it is kept whatever its outcome.

| Experiment | Revision | Record | Parts and intended level | State |
|---|---|---|---|---|
| V2-E01, contract-to-deployment determinism | 1 | [`v2-e01/freeze-r1.v1alpha1.json`](v2-e01/freeze-r1.v1alpha1.json) | E01-A, E01-B, E01-C at C0; E01-D at C2 | Superseded by revision 2 on 2026-10-03, and kept unchanged. E01-A, E01-B, and E01-C ran once under it, in [`20261002-e01-abc-1`](v2-e01/runs/20261002-e01-abc-1/result.md), and each PASSED under its criteria. That run carries an [audit limitation](#audit-of-the-first-run-2026-10-03) |
| V2-E01, contract-to-deployment determinism | 2 | [`v2-e01/freeze-r2.v1alpha1.json`](v2-e01/freeze-r2.v1alpha1.json) | E01-A, E01-B, E01-C at C0; E01-D at C2 | Frozen. E01-A, E01-B, and E01-C ran once under it, in [`20261003-e01-abc-1`](v2-e01/runs/20261003-e01-abc-1/result.md), and each PASSED under its criteria. E01-D's environment identity is still pending, so E01-D cannot start |

## Why a freeze comes first

A result is only as good as the method it was measured against. If the procedure, the
inputs, or the pass condition can change after a result is seen, the result is a search for
a number. So every field a run depends on is written down and committed before the first
result-bearing run, and a run uses the merged record. A later change to what the record
fixes is a new revision, never an edit.

## The fields

A record answers 13 fields, in `fields`. Each field is a list of entries, and the entries of
one field together cover every part of the experiment exactly once. A field with no entry is
refused. It is never read as "not applicable".

| Field | Meaning |
|---|---|
| `experimentIdVersion` | The experiment's identifier and version. |
| `gitRevision` | The Git revision, or the pinned inputs, the run must use. |
| `environmentIdentity` | The environment the run executes in. |
| `callerProfileRevision` | The revision of the caller profile selected. |
| `topology` | What is deployed, and how many of each. |
| `fault` | The fault the run injects. |
| `repetitionCount` | How many result-bearing runs, and of what. |
| `acceptanceCriteria` | What must hold for the run to pass. |
| `derivedNumericBounds` | The numeric bounds derived from runtime-startup and stable-caller qualification. |
| `evidencePaths` | Where the run's evidence is written. |
| `abortConditions` | The conditions that stop a run that has started. |
| `cleanupProcedure` | How the run is cleaned up afterwards. |
| `intendedEvidenceLevel` | The evidence level the run aims at, under [InferOps Evidence Levels](../../testing/evidence-levels.md). |

**How an entry answers.** Every entry names its `parts` and has one `status`:

- `value`, with a `value` that is not empty: not an empty string, list, or object, not
  `null`, and not a string that is exactly a stand-in - `TBD`, `TODO`, `N/A`, `unknown`,
  `pending`, `.`, and the others the check lists - or exactly a `<...>` placeholder. A
  stand-in inside a longer string is not detected. An intended evidence level is one of
  `C0` to `C4`, and every acceptance criterion has an `id` and a `statement`, with no `id`
  used twice in a record.
- `not-applicable`, with a `reason`, for a part that has no counterpart to the field. E01
  injects no fault, so its `fault` is not applicable, with the reason. Only five fields can
  lack a counterpart: `environmentIdentity`, `callerProfileRevision`, `topology`, `fault`,
  and `derivedNumericBounds`. The other eight are ones every run has, and
  `not-applicable` is refused for them.
- `pending`, with a `reason` and an `owner`, only where an allowance in
  [`tools/experiment_freeze`](../../../tools/experiment_freeze/core.py) names the
  experiment, the field, and the part. One allowance exists: E01-D's
  `environmentIdentity`, owned by `V2-S3-004-PR1`, the change that will name E01-D's real
  environment. A part with a pending field cannot run.

An entry may add a `note`, which must not be empty. Beside the fields, a record states its
definition, its parts with their inputs and procedures, and its pinned inputs.

## Pinned inputs

A record cannot name the commit that merges it. So it pins every file on the experiment
path in `pinnedInputs`, with a role and a **content digest**: the SHA-256 of the file's bytes
with every CRLF replaced by LF, which is what Git stores for a text file under this
repository's attributes. A Windows checkout and a Linux one give the same digest. The run
records the merged commit it executes, and checks the pins at that commit before it starts.

```sh
# List every material file that differs from the record. Exit 1 if any does.
uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json
```

**The material scope** (from revision 2). A pin list can only say whether the files it
names changed. It cannot see a file nobody listed - the gap the first E01 run fell through:
its runner was not pinned, so the change check reported nothing. So a record now declares
`materialScope`: the entry modules of the run, the package roots they resolve in, and the
data files and patterns the parts read. The experiment path is the **static import
closure** of the entry modules within those roots - every product module, the runner, the
analysis, the freeze checker, and every local helper they import - plus the data files.
`--changes` computes that set from the tree and lists four kinds of difference:

| Kind | Meaning |
|---|---|
| `changed` | Pinned, present, with other content |
| `absent` | Pinned and missing |
| `added` | In the scope and not pinned: a new file, or a new local helper an import now reaches |
| `unscoped` | Pinned, present, and no longer in the scope |

The closure follows `import` statements, wherever they are, and matches each module name
against its directory's listing, so a name in the wrong case resolves to nothing on Windows
as on Linux. It does not see a module loaded by a name built at run time, so a run also
records every module file it and its second process loaded from the record's package
directories - `src/inferops/` and `tools/` - and aborts when one is not a pinned input with
its pinned content, or when the second process imported the runner or the package from
outside the checkout. Third-party packages, including those in a `.venv/` inside the
checkout, are outside those directories: `uv.lock` pins them by version, not by content.
`--check` recomputes these conditions from what a revision-2 run recorded. `exclusions` may remove a file from
the scope, each with a reason, inside the frozen record; revision 2 excludes nothing.
Revision 1 has no scope and is checked against its own pins, as it was registered.

## Revisions

The registry, [`registry.v1alpha1.json`](registry.v1alpha1.json), pins the content digest of
every committed record. A record whose content differs from its pin is refused, and so is
a record nobody pinned. Until 2026-10-03 the pins were a constant, `FROZEN_RECORDS`, in the
checker's own code. A record that pins the checker - as revision 2 does, because the run
calls it - could then never be registered: adding the record's pin changes the checker,
which moves the record's pin of it. The registry is data, so the cycle is gone. A record
does not pin the registry, and says so; a run records the registry's digest beside the
record's. No record names the commit that merges it: the run records the commit it
executes. To change what a record fixes, add `freeze-r<N+1>.v1alpha1.json` beside it:

- `metadata.supersedes` names the previous revision's path and content digest;
- `inputChanges` classifies every pinned input whose digest moved since that revision, added
  or removed ones included, with `material` true or false and a `reason`;
- every freeze field is answered again, in full.

A revision is pinned when it is added, like the first.

## The check

```sh
uv run --locked python -m tools.experiment_freeze --check
```

It exits 0 when every committed record holds every rule, and 1 when one does not. The
default-lane suite [`tests/testing/test_experiment_freeze.py`](../../../tests/testing/test_experiment_freeze.py)
runs it, and plants each defect below in a copy.

| Rule | Statement |
|---|---|
| `freeze-record-unreadable` | A freeze record is a JSON object. |
| `freeze-record-shape` | A freeze record declares its version and kind, its metadata, and its parts. |
| `freeze-field-missing` | A freeze record carries every freeze field. |
| `freeze-field-unknown` | A freeze record carries no field the procedure does not name. |
| `freeze-field-parts` | The entries of one field cover every part of the experiment exactly once. |
| `freeze-field-status-unknown` | An entry is a value, not-applicable, or pending. |
| `freeze-field-empty` | A value is not empty, and is not a placeholder. |
| `freeze-field-reason-missing` | A not-applicable or pending entry states its reason. |
| `freeze-field-pending-not-allowed` | Only an allowed field of an allowed part is pending, and it names its owner. |
| `freeze-field-always-answered` | A field every run has is never answered not-applicable. |
| `freeze-criteria-malformed` | Every acceptance criterion has an identifier and a statement, and no identifier is used twice in a record. |
| `freeze-evidence-level-unknown` | An intended evidence level is one of the project's evidence levels. |
| `freeze-pinned-input-malformed` | Every pinned input names one repository path once, with a content digest. |
| `freeze-scope-missing` | Every record declares a material scope, except a record registered before scopes existed. |
| `freeze-scope-malformed` | A material scope names its entry modules, the package roots they resolve in, and its data paths, and every exclusion names a path and a reason. |
| `freeze-registry-unreadable` | The freeze registry is a JSON object that pins records by path and content digest, each path once. |
| `freeze-record-unregistered` | Every committed freeze record is pinned. |
| `freeze-record-missing` | Every pinned freeze record is committed. |
| `freeze-record-edited` | A committed freeze record is what was pinned. |
| `freeze-revision-sequence` | An experiment's revisions are numbered from 1 without a gap, as their files are. |
| `freeze-revision-supersedes` | Revision 1 supersedes nothing; a later revision names the one before it and its content digest. |
| `freeze-input-change-unclassified` | A revision classifies every pinned input that changed, appeared, or disappeared since the revision it supersedes. |

## What is enforced, and what is not

Enforced in the default lane: every rule above, over every committed record.

Not enforced:

- **A change to a pinned input merges freely.** No test compares the pins with today's
  files. A change to the experiment path does not need a freeze revision to merge. The run
  that follows does: its first precondition is that every pin holds, or that a merged
  revision classifies the change, and `--changes` lists what moved.
- **No test asserts that today's code passes.** The E01 suite executes the static parts
  end to end in a temporary repository on every default lane, and asserts only that the
  judge agrees with what the runner recorded, never that a part PASSED. A result-bearing
  run is one a contributor names with `--run`, recorded under `runs/`.
- **A run's refusal to start, for E01-D.** The E01 runner refuses to start E01-A, E01-B, and
  E01-C when a precondition fails, and it never runs E01-D. No runner for E01-D exists, so
  "a part with a pending field cannot run" is, for E01-D, a procedure the next run follows
  and no code enforces.
- **That a pinned file exists.** A pin is checked for its shape, not against the working
  tree. A file deleted after a record merged is reported by `--changes`, not refused by
  `--check`: refusing it would make a merged record fail the build for a later, legitimate
  change.
- **Whether the content is right.** The check says every field is answered. It does not
  judge an answer, and it does not check that a revision a record names is a commit.
- **That the registry is append-only.** A change can edit a record and its registry pin
  together. The test suite writes each registered pin out literally, so such an edit
  shows in review as a changed test; nothing else refuses it.
- **That a scope is complete when it merges.** `--check` reads the record, not the tree, so
  it does not compare the scope with the files. `--changes` does, and the run refuses to
  start on any difference. At registration, revision 2's `--changes` reported none, and the
  run under it recorded none.
- **The rule against previews.** Revision 2 forbids a full execution of the parts outside
  `--run`, in any repository. No code can see a run in a throwaway repository, so this is a
  procedure the record states and nothing enforces.

The E01 record pins `uv.lock` and `pyproject.toml`, because the parsers and their
dependencies are on the experiment path. So any dependency update is listed by
`--changes`, and the next E01 run needs a revision that classifies it.

## The V2-E01 freeze

[`v2-e01/freeze-r1.v1alpha1.json`](v2-e01/freeze-r1.v1alpha1.json) freezes the V2-E01 family,
contract-to-deployment determinism, in four parts:

- **E01-A, deterministic double render (C0).** Two renders of the reference inputs, in two
  processes, compared byte for byte, with the release's provenance checked against digests
  computed apart from it, and the no-hand-written-intent criterion checked statically.
- **E01-B, intent mutation (C0).** The contract's replica count changed from 1 to 2, and
  only `runtime.replicaCount`, the contract digest, the values digest, and the release
  identifier may move.
- **E01-C, negative cases (C0).** Six cases, each run twice: schema-invalid,
  semantic-invalid, two ownership conflicts, an unsupported profile, and an unsupported
  capability, each with its expected refusal.
- **E01-D, real deployment (C2).** The release rendered from the unmodified contract,
  accepted into Git, reconciled by Argo CD, and serving one real completion. Its procedure
  and criteria are frozen. Its environment identity is pending, so it cannot run until a
  merged revision names the environment.

The record states every procedure, criterion, and limitation in full. It pins 67 inputs: the
contract, the binding, the chart and its defaults, the compatibility matrix, the renderer's
39 source files, the hand-written values, the V1 values, the negative-case contract, the V1
synchronous compatibility record, the defaults reader, and the dependency lock and project
metadata.

### Revision 2

[`v2-e01/freeze-r2.v1alpha1.json`](v2-e01/freeze-r2.v1alpha1.json), registered by
`V2-S2-004-PR1` on 2026-10-03, supersedes revision 1. The first Sprint 2 collective review
found two defects in revision 1, and revision 2 corrects both without editing it:

- **The criterion is the governing one again.** Revision 1's hypothesis, E01-AC5, and
  E01-AC10 excepted two hand-written strings that repeated the contract's model pins. The
  renderer now derives both, so revision 2 states the criterion without the exception:
  no claim-relevant workload intent is written by hand after rendering, and no hand-written
  string contains a contract-owned generated value of eight characters or more. E01-C gains
  a seventh case: a hand-written download URL that contradicts the pins, refused.
- **The executable path is frozen.** Revision 2 declares its material scope and pins 74
  inputs: the 39 product files and the data files revision 1 pinned, the runner and
  analysis, the freeze checker, and the packages they belong to. `inputChanges` classifies
  every difference from revision 1: four changed files, from the renderer correction, and
  seven added ones, the runner and checker files revision 1 never pinned.

It also states, before any run under it: the run's preconditions, which now include that the
runner and the `inferops` package are imported from the checked-out tree and that the record
is registered; the executions that are not result evidence; the rule against previews; how
the record avoids pinning itself; and, in `history`, the first run's audit limitation and
what is and is not available of the earlier previews. E01-D's environment identity stays
pending, with the same owner.

## The E01 static run

`tools/experiment_e01` runs E01-A, E01-B, and E01-C once, as the freeze record registers
them, and checks a committed run. It reads every input, edit, and expected refusal from the
record itself, not from a copy of its own.

```sh
# Run the static parts once. The run's identifier is its UTC date, the parts, and a sequence.
PYTHONHASHSEED=1 uv run --locked python -m tools.experiment_e01 --run YYYYMMDD-e01-abc-N
# Judge every committed run again from its raw evidence. Writes nothing.
uv run --locked python -m tools.experiment_e01 --check
```

**Before it runs a part,** the runner checks the record's preconditions and records each
observation. Under revision 2 it also checks that the runner module it runs is the
checked-out tree's `tools/experiment_e01/core.py`, that the record is registered and
unedited, and that no material file differs - added files included - and it records the
`inferops` distribution version, the registry's digest, and every repository module file it
and its second process loaded. Under revision 1 it checked: the executing commit is a full revision reachable from `origin/main`, the
freeze record is in it, `git status --porcelain --untracked-files=all` prints nothing,
every pinned input has its pinned content, and the `inferops` package it imported is the
one under the checkout's `src`. If one fails, it writes a run with every part REFUSED and
runs nothing. `origin/main` is read as the clone holds it, so a clone that has not fetched
refuses a commit that is merged; the reverse cannot happen. A new run executes the latest
revision, revision 2; a committed run is judged by the analysis of the revision it names,
so the first run is still judged by revision 1's criteria and page, byte for byte. It refuses an identifier whose date is not today's UTC date, and an
evidence directory that already exists. It starts only with `PYTHONHASHSEED=1`; the second
E01-A render runs in its own process with `PYTHONHASHSEED=2`.

**After the parts,** it records the commit and the status again. A changed commit, or a
change outside the run's evidence directory, is an abort condition, and the parts are
ABORTED. It removes its temporary directory and records that it did. The status check
sees what `git status` sees: a write to an ignored path, or outside the repository, is
not detected. A step that raises is recorded as the run's `error`, and the parts it left
unanswered are INCONCLUSIVE; a criterion that did not hold makes its part FAILED even when
another went unanswered, because a FAILED run is not repeated.

**What a run holds.** One directory under
[`v2-e01/runs/`](v2-e01/runs/), named by its identifier, with the files the record's
`evidencePaths` names: `run.v1alpha1.json` (the manifest: identifier, parts, executing
commit, preconditions, host, runner file digests, observations, abort checks, the SHA-256
of every file, each criterion's verdict, and each part's outcome), `commands.txt`,
`render-a/`, `render-b/`, `mutation/`, `refusals.json`, and `result.md`.

**The check.** `--check` derives every verdict again from the committed renders, the
recorded refusals, and the observations the manifest records: the two renders compared,
the release fields read from the files, the mutation's differences listed again, and every
refusal compared with the record's expected one. It does not recompute the contract,
binding, or mutated-contract digests, the admission of the hand-written values, or the V1
merge; those are the run's observations. It fails when a file does not have the digest the
manifest records, when the manifest names a file that is absent or omits one that is
present, when a verdict or an outcome differs from the one the evidence gives, when
`result.md` is not the page the evidence generates, when the run names a reference other
than `origin/main`, when its recorded precondition findings are not the ones its recorded
observations give, and when the manifest cannot be read. The manifest is not in its own
digest list, so an edit to it and to `result.md` together passes `--check`; the evidence
index, which binds every cited file of the run's record by SHA-256, the manifest
included, is what refuses that. The
default-lane suite [`tests/testing/test_experiment_e01.py`](../../../tests/testing/test_experiment_e01.py)
runs it over the committed run and plants each of these defects in a copy.

**The first run.** [`20261002-e01-abc-1`](v2-e01/runs/20261002-e01-abc-1/result.md) executed at
the merged commit `707e29f4a0ff31ea90fa33f6b8cf2ec883cfb6a3`, in a detached worktree with no
change before the run and only the evidence directory after it. E01-A, E01-B, and E01-C each
PASSED: every criterion from E01-AC1 to E01-AC7 held. The claim
`the-first-e01-static-run-recorded-identical-renders-and-every-registered-refusal`
in the [claim and evidence register](../../testing/claim-evidence-matrix.v1alpha2.json)
holds it at C0. The run's [validation record](../domain/v2-s2-003-pr2-validation.md) says
how it was prepared and what was checked.

**The second run.** [`20261003-e01-abc-1`](v2-e01/runs/20261003-e01-abc-1/result.md) executed at the merged commit
`a5b6a5db2011a68a3f27acdeaa8186c226bfedb4`, the merge of the change that registered revision
2, with no change before the run and only the evidence directory after it. It is the
first run under revision 2. The manifest records that the record had its registered
digest, that no material file differed, that the runner was the checkout's
`tools/experiment_e01/core.py` and the package the checkout's `src/inferops`, in both
processes, and that each process loaded 47 repository module files, every one a pinned
input with its pinned content. E01-A, E01-B, and E01-C each PASSED: every criterion from
E01-AC1 to E01-AC7 held, E01-AC5 without revision 1's exception and E01-AC7 over seven
cases. The claim
`the-second-e01-static-run-recorded-its-frozen-path-identical-renders-and-every-registered-refusal`
holds it at C0. The run's [validation record](../domain/v2-s2-004-pr2-validation.md) says
what was checked before it, what executed before it, and every attempt. The run answers
revision 2 only: it is not evidence that the first run's execution boundary was valid.

| Run | Freeze revision | Executing revision | E01-A | E01-B | E01-C |
|---|---|---|---|---|---|
| [`20261002-e01-abc-1`](v2-e01/runs/20261002-e01-abc-1/result.md) | 1 | `707e29f4` | PASSED | PASSED | PASSED |
| [`20261003-e01-abc-1`](v2-e01/runs/20261003-e01-abc-1/result.md) | 2 | `a5b6a5db` | PASSED | PASSED | PASSED |

Every run stays in this table with its outcome state, whatever it is. No run under either
revision was REFUSED, ABORTED, INCONCLUSIVE, or FAILED.

**What the first run does not do.** The runner is not a pinned input of freeze revision 1, and the
first run executed from a byte copy outside the checked-out tree, so the commit it
records does not contain the runner. The manifest records the content digest of each runner
file instead. Those digests are of the runner as `V2-S2-003-PR2` first committed it: its
independent review then changed the runner, so the files committed beside the run are not
the ones that ran, and the first commit of that change holds the ones that did. The fixes
changed no verdict of the run. Nothing compares a committed run with today's code: a later change to the
renderer leaves the run as it was, and a new run needs a new identifier. Nothing here
deploys the release input, reconciles it, or serves a completion; that is E01-D.

## Audit of the first run, 2026-10-03

The first Sprint 2 collective review examined run `20261002-e01-abc-1`. Its files, digests,
and revision 1 outcomes are unchanged, and `--check` still judges it by revision 1. The
audit adds this limitation; it does not reinterpret the run under revision 2:

- **The execution boundary was not the freeze's.** The run records executing revision
  `707e29f4`, but the runner it executed was not in that commit and was not a pinned input
  of revision 1. Revision 1's change check compared only the files it listed, so it could
  not report the runner. The run is not evidence that its execution was governed by its
  freeze.
- **The package location was observed by hand.** The run predates the check that records
  which `inferops` package was imported.
- **Previews were not preregistered.** Before the run, a full development preview executed
  E01-A, E01-B, and E01-C in a throwaway repository and reported all three PASSED. After
  it, two more full executions in throwaway repositories ran while review findings were
  fixed, and reported E01-A INCONCLUSIVE and E01-B and E01-C PASSED. None was exempted
  before it ran. Their raw evidence directories were deleted with their repositories and
  are not available; a partial console capture of each exists outside this repository and
  is not published, because it contains host paths. Nothing reconstructs them.
- **What the audit found intact.** The review found no evidence that thresholds, workload,
  faults, or raw result files were changed, every manifest-covered file keeps its digest,
  and an independent comparison reproduced both original render-a files.

Revision 2's `history` records the same. A new run under revision 2 answers revision 2's
criteria; it is not evidence that the first run's boundary was valid.

Since `V2-S2-004-PR2` the register carries the audit too: the first run's claim has the
limitation appended, dated, after the text it already had, and [a ledger](../testing/v2-s2-004-pr2-e01-corrected-static-proof.v1alpha1.json)
holds one correction beside the first run's result page. The claim's statement, status,
and record are unchanged.
