# Experiment freeze records

Status: **format and check added by `V2-S2-003-PR1`**, with one record: the V2-E01 family
freeze, revision 1. A freeze record fixes an experiment family before its first
result-bearing run. A record is not evidence: it says what a run must do and what counts as
a pass, and no run of a frozen part has executed.

| Experiment | Revision | Record | Parts and intended level | State |
|---|---|---|---|---|
| V2-E01, contract-to-deployment determinism | 1 | [`v2-e01/freeze-r1.v1alpha1.json`](v2-e01/freeze-r1.v1alpha1.json) | E01-A, E01-B, E01-C at C0; E01-D at C2 | Frozen. No part executed. E01-D's environment identity is pending, so E01-D cannot start |

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
  `null`, and not a stand-in such as `TBD`, `N/A`, or a whole-string `<...>` placeholder.
  An intended evidence level is one of `C0` to `C4`.
- `not-applicable`, with a `reason`, for a part that has no counterpart to the field. E01
  injects no fault, so its `fault` is not applicable, with the reason.
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
# List every pinned input whose content differs from its pin. Exit 1 if any does.
uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r1.v1alpha1.json
```

## Revisions

`FROZEN_RECORDS` in [`tools/experiment_freeze`](../../../tools/experiment_freeze/core.py)
pins the content digest of every committed record. A record whose content differs from its
pin is refused, and so is a record nobody pinned. To change what a record fixes, add
`freeze-r<N+1>.v1alpha1.json` beside it:

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
| `freeze-evidence-level-unknown` | An intended evidence level is one of the project's evidence levels. |
| `freeze-pinned-input-malformed` | Every pinned input names one repository path once, with a content digest. |
| `freeze-record-unregistered` | Every committed freeze record is pinned. |
| `freeze-record-missing` | Every pinned freeze record is committed. |
| `freeze-record-edited` | A committed freeze record is what was pinned. |
| `freeze-revision-sequence` | An experiment's revisions are numbered from 1 without a gap, as their files are. |
| `freeze-revision-supersedes` | Revision 1 supersedes nothing; a later revision names the one before it and its content digest. |
| `freeze-input-change-unclassified` | A revision classifies every pinned input that changed since the revision it supersedes. |

## What is enforced, and what is not

Enforced in the default lane: every rule above, over every committed record.

Not enforced:

- **A change to a pinned input merges freely.** No test compares the pins with today's
  files. A change to the experiment path does not need a freeze revision to merge. The run
  that follows does: its first precondition is that every pin holds, or that a merged
  revision classifies the change, and `--changes` lists what moved.
- **Nothing runs an experiment.** No test executes a part's procedure, and no test compares
  a record's expected refusals with the code. That comparison is a result-bearing run.
- **Whether the content is right.** The check says every field is answered. It does not
  judge an answer, and it does not check that a revision a record names is a commit.

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
