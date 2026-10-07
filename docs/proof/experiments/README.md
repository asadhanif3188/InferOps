# Experiment freeze records and runs

Status: **format and check added by `V2-S2-003-PR1`**, with one record: the V2-E01 family
freeze, revision 1. **One run added by `V2-S2-003-PR2`**: E01-A, E01-B, and E01-C, executed
once under that record. **Revision 2 added by `V2-S2-004-PR1`**: it restores the governing
no-duplication criterion and freezes the whole executable path, runner and analysis
included. **One run added by `V2-S2-004-PR2`**: E01-A, E01-B, and E01-C, executed once
under revision 2 from the merged checkout. **One independent review published by
`V2-S2-005-PR1`**: a review of that second run, with one finding about the wording of its
register claim. **One correction and one gate added by `V2-S2-005-PR2`**: the claim's
statement is [narrowed to the frozen criterion](#correction-of-the-second-run-claim-and-the-review-gate-2026-10-03),
and a register change that bears on a run now needs a review artifact of that run.
**Revision 3 added by `V2-S3-004-PR1`**: it [names the environment of E01-D](#revision-3),
the Git desired-state path, and the Argo CD Application, and it changes one clause of
E01-AC10. No part of E01 ran in that change.
**One run added by `V2-S3-004-PR2`**: [E01-D, executed once under revision 3](#the-e01-d-run)
on the environment that revision names, with one completion request. The part PASSED.
The same change makes the committed-run check leave an E01-D run out, which moves one
pinned input of revisions 2 and 3. It also publishes
[one independent review of that run](v2-e01/reviews/20261006-e01-d-1-review-1.md), which found no defect in the verdicts.
That change registered no claim for the result.
**One claim added by `V2-S3-005-PR1`**: [the register claim of the E01-D run](#registration-of-the-e01-d-result-2026-10-07),
at `C2`, bounded to the one run and dated 2026-10-07. No part of E01 ran in that change.
A freeze record fixes an experiment family before its first
result-bearing run. A record is not evidence: it says what a run must do and what counts as
a pass. A run is evidence, and it is kept whatever its outcome.

| Experiment | Revision | Record | Parts and intended level | State |
|---|---|---|---|---|
| V2-E01, contract-to-deployment determinism | 1 | [`v2-e01/freeze-r1.v1alpha1.json`](v2-e01/freeze-r1.v1alpha1.json) | E01-A, E01-B, E01-C at C0; E01-D at C2 | Superseded by revision 2 on 2026-10-03, and kept unchanged. E01-A, E01-B, and E01-C ran once under it, in [`20261002-e01-abc-1`](v2-e01/runs/20261002-e01-abc-1/result.md), and each PASSED under its criteria. That run carries an [audit limitation](#audit-of-the-first-run-2026-10-03) |
| V2-E01, contract-to-deployment determinism | 2 | [`v2-e01/freeze-r2.v1alpha1.json`](v2-e01/freeze-r2.v1alpha1.json) | E01-A, E01-B, E01-C at C0; E01-D at C2 | Frozen. E01-A, E01-B, and E01-C ran once under it, in [`20261003-e01-abc-1`](v2-e01/runs/20261003-e01-abc-1/result.md), and each PASSED under its criteria. Superseded by revision 3 on 2026-10-06, and kept unchanged. Its E01-D environment identity is pending |
| V2-E01, contract-to-deployment determinism | 3 | [`v2-e01/freeze-r3.v1alpha1.json`](v2-e01/freeze-r3.v1alpha1.json) | E01-A, E01-B, E01-C at C0; E01-D at C2 | Frozen. It names the E01-D environment. E01-D ran once under it, in [`20261006-e01-d-1`](v2-e01/runs/20261006-e01-d-1/result.md), and PASSED under its criteria. No static part ran under it. Since that run, one pinned input differs from its pin: [the runner's committed-run listing](#the-e01-d-run) |

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
  environment. A part with a pending field cannot run. Revision 3 answers that field with a
value, and no field of it is pending. The allowance stays in the checker, which revision 3
pins and which was not edited, so a test, not the checker, holds that revision 3 uses none.

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
  "a part with a pending field cannot run" is, for E01-D, a procedure that a run follows
  and no code enforces. The one E01-D run followed it under revision 3, which leaves no
  field pending.
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
  and criteria are frozen. In revisions 1 and 2 its environment identity is pending, so
  it could not run until a merged revision named the environment. Revision 3 names it,
  and [E01-D ran once under revision 3](#the-e01-d-run).

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

### Revision 3

[`v2-e01/freeze-r3.v1alpha1.json`](v2-e01/freeze-r3.v1alpha1.json), registered by
`V2-S3-004-PR1` on 2026-10-06, supersedes revision 2. Revision 2 left the environment
identity of E01-D pending. Revision 3 answers it, and no field of it is pending. Revisions 1
and 2 are unchanged.

**No part of E01 ran in this change.** Nothing was deployed, Argo CD synchronized
nothing, and no completion was sent. The environment was read with read-only requests on
2026-10-06. A freeze record is not evidence.

- **The environment.** One provider, `docker-desktop`: one cluster at Kubernetes v1.36.1
  with one node, the default storage class `standard`, Argo CD v3.5.3 from the pinned
  install manifest, the runtime image by digest, and the model by repository, revision,
  file, and SHA-256. The API image digest is not in Git: the run builds the image and
  records the digest. When the environment was read, Argo CD, the platform namespace, and
  the model cache claim were absent. The preparation steps create them.
- **The Git and Argo CD path.** The release is the one committed at
  `gitops/environments/local-docker-desktop/workloads/support-assistant/`, derived from the
  reference contract and the `local-docker-desktop` binding. The Application is
  `local-docker-desktop-support-assistant`, in the project `inferops-workloads`, and it
  follows `main`. The run commits no release: it derives the release again at the
  executing commit and compares the bytes.
- **The steps and the rules.** Seven preparation steps and six run steps, each with its
  commands, and for each E01-D criterion the comparisons that judge it. One request is
  sent, with no retry. A preparation step that fails ends the run before the Application
  is applied. A release that is not ready 600 seconds after Argo CD reported the sync
  makes the part FAILED. The record separates the identity attributes that the run reads
  before it prepares anything from the ones a preparation step establishes, and names
  the step that verifies each.
- **One criterion clause changed.** Revision 2's E01-AC10 said that the release is
  installed "from the generated values file and one hand-written values file only, with no
  parameter override". [ADR 0019](../../architecture/decisions/ADR-0019-argocd-application-and-sync-policy.md)
  D5, accepted after revision 2, delivers the values as the generated values file,
  hand-written values inside the Application, and one operator-supplied Helm parameter,
  `api.image.digest`. On that delivery the clause cannot hold, whatever a run observes.
  Revision 3 states the ownership property in its place: no hand-written value and no
  operator-supplied parameter restates or overrides claim-relevant workload intent. The
  parameter is permitted because no contract, binding, platform default, or renderer owns
  it. `criteriaChanges` holds both statements, the reason, and who approved the change.
  E01-AC1 to E01-AC9 are those of revision 2, character for character.
- **Every other difference from revision 2 is listed.** Three statements of the E01-D
  procedure and inputs carried the same mechanism or predate the Git layout, and
  `procedureChanges` lists each replacement. `fieldChanges` lists twelve more, each with
  revision 2's text: the environment, the topology, the evidence paths, two added abort
  conditions, the cleanup, the preconditions, and the outcome rules. The cleanup of
  revision 2 was written for an environment it could not name, and four of its items
  have no subject on this one.
- **The change was written after runs of the same path.** No E01-D run had executed. But
  between 2026-10-03 and 2026-10-05 the Argo CD procedures ran on this provider, applied
  this release with this parameter, and sent caller requests: five of six were answered
  in one set of runs. They are not E01-D runs. The record lists them in `history`, and
  says that the criterion change was written with knowledge of them.
- **The pins.** 160 inputs: the 74 of revision 2, and 86 added for the E01-D path. The
  86 are the rest of the `inferops` package that the API image copies, the three tools
  the steps run, the API container's entry module and the carrier it imports, the
  desired-state tree, the two Argo CD manifests, five procedures and the library they
  source, the Terraform prerequisite layer, the image build files, the model source
  record, the `local-docker-desktop` binding, one test module, and the two pytest
  configuration files. `inputChanges` classifies each.
- **No pin of revision 2 moved.** Each of the 74 has the content revision 2 pinned.
  `changesSinceSupersededRevision` lists all 132 files that changed between the merge of
  revision 2 and the commit revision 3 was prepared from: 18 are on the E01-D path, 114
  are not, and none is a pinned input of revision 2.
- **The static result is consumed, not repeated.** Run `20261003-e01-abc-1` under
  revision 2 is the static result. No pinned input of revision 2 moved, so no change is
  material to it.

What revision 3 does not do:

- **No runner exists for E01-D, and no code computes its verdicts.** A person executes the
  registered steps and applies the registered rules. A driver that transcribes the steps
  is committed with the run and is not a pinned input.
- **The E01 runner still executes revision 2.** Its `CURRENT_REVISION` is 2. It is a
  pinned input, and this change does not edit it. A new static run would execute under
  revision 2.
- **The committed-run check refused an E01-D run, and the change that registered
  revision 3 did not fix that.** `tools.experiment_e01 --check` read every directory under
  `runs/` as a static run and knows revisions 1 and 2. Revision 3 puts an E01-D run
  under `runs/`, because the review gate reads runs there. So the change that commits an
  E01-D run had to change that check, after the run. The edit was tried when revision 3
  was registered: 13 tests of the default lane failed, and it was taken back out.
  `V2-S3-004-PR2` made the edit after the run. [The E01-D run](#the-e01-d-run) says what
  it moved. A run of any part after that edit needs a later revision.
- **No command judges a committed E01-D run again.** The evidence index binds each
  cited file by SHA-256, and the review gate compares the review's digests with the
  run's files.
- **No step observes whether the model was downloaded.** The claim is filled before
  the Application is applied, so the acquisition hook is expected to download nothing.
  No step reads the hook's job, and Argo CD deletes it when it succeeds.
- **The cleanup leaves images in the node and on the host.**
- **The eight-character clause of E01-AC10 is not computed over the live Application.**
  It rests on the static result's verdict for the hand-written values fixture, and on a
  test that holds the Application's hand-written values equal to that fixture without its
  digest.
- **Nothing here blocks a merge that changes a pinned file.** As before, the run that
  follows refuses to start until a merged revision classifies the change.

An E01-D result enters the register only through
[the review gate](#correction-of-the-second-run-claim-and-the-review-gate-2026-10-03): a
ledger that bears on the run names one independent review artifact of that run. The
review of the second static run is not a review of an E01-D run, and the gate refuses it
for one.

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
refuses a commit that is merged; the reverse cannot happen. A new run executes
revision 2, the runner's `CURRENT_REVISION`, and not [revision 3](#revision-3); a committed run is judged by the analysis of the revision it names,
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

**The check.** `--check` reads every directory under `runs/` as a static run, except a
directory named as a run of E01-D, `YYYYMMDD-e01-d-N`, which it leaves out. It derives every verdict again from the committed renders, the
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

Every committed run stays in this table with its outcome state, whatever it is. No committed
run under either revision was REFUSED, ABORTED, INCONCLUSIVE, or FAILED. The previews
[the audit](#audit-of-the-first-run-2026-10-03) describes are not runs of record; two of
them reported E01-A INCONCLUSIVE.

**What the first run does not do.** The runner is not a pinned input of freeze revision 1, and the
first run executed from a byte copy outside the checked-out tree, so the commit it
records does not contain the runner. The manifest records the content digest of each runner
file instead. Those digests are of the runner as `V2-S2-003-PR2` first committed it: its
independent review then changed the runner, so the files committed beside the run are not
the ones that ran, and the first commit of that change holds the ones that did. The fixes
changed no verdict of the run. Nothing compares a committed run with today's code: a later change to the
renderer leaves the run as it was, and a new run needs a new identifier. Nothing here
deploys the release input, reconciles it, or serves a completion; that is E01-D.

## The E01-D run

[`20261006-e01-d-1`](v2-e01/runs/20261006-e01-d-1/result.md) is the one run of part E01-D. It executed on
2026-10-06 under revision 3, at the merged commit
`ad725905a7838e8210e54a29de7913bc0c7c49e5`, which merged revision 3 and which `main` named
on the remote when the run started. Its [validation record](../domain/v2-s3-004-pr2-validation.md)
says what was checked before it and after it.

| Run | Freeze revision | Executing revision | Environment | E01-D |
|---|---|---|---|---|
| [`20261006-e01-d-1`](v2-e01/runs/20261006-e01-d-1/result.md) | 3 | `ad725905` | `docker-desktop`, Kubernetes v1.36.1, one node | PASSED |

**What executed.** A driver ran the steps that revision 3 registers, once: preparation P1
to P7, procedure D1 to D6, and the cleanup. The run rendered the release again at the
executing commit and compared it with the release in Git, byte for byte. It applied the
Argo CD Application with one parameter, `api.image.digest`. Argo CD reported a succeeded
sync at the executing commit. Both rollouts completed 18 seconds after the apply returned,
against a deadline of 600 seconds. It is a warm start: the preparation had started the
same images on the same node about two minutes earlier. The readiness request returned 200. The run then sent
one completion request and no other.

**What the criteria gave.**

- **E01-AC8 holds.** The one request returned HTTP 200, with one choice whose assistant
  message has a length of 6 characters. The generated text is not kept.
- **E01-AC9 holds.** Argo CD reports the executing commit as synced and as applied. The
  provenance tool resolves that commit to the release identifier and the values digest
  that revision 3 names. The runtime container's image identity ends with the generated
  runtime image digest. The runtime mounts the generated model revision, and the init
  container that verifies the artifact ended with exit code 0. The response names the
  generated model identifier.
- **E01-AC10 holds.** The live Application takes its values from the one generated values
  file, from hand-written values equal to those of the committed manifest, and from the
  one parameter, whose value is the digest that the run's build printed. The three
  admission tests passed at the executing commit. The eight-character clause rests on
  the consumed static result, as revision 3 registers. No code computes it over the live
  Application.

**What the run holds.** Twelve files: `run.v1alpha1.json` (the manifest, with each
compared value, each rule's verdict, and the SHA-256 of every other file),
`commands.txt`, `driver.txt`, `transcript.txt`, `environment.json`, `release.json`,
`argo.json`, `pods.json`, `reconciliation.record.json`, `provenance.json`,
`completion.json`, and `result.md`.

**What the run does not do.**

- **No runner judged it.** The automated assistant session that drove the run applied
  the registered rules. It is not independent of the run. The default-lane suite applies
  each rule again to the committed files and requires the recorded verdict. It reads
  two rules from less than a structured file: the admission rule from the pytest summary
  in the transcript, and the eight-character rule from the consumed static run. The
  suite does not show that the cluster returned those files.
- **Its files fall short of the registered form in four places.** `commands.txt` has no
  shell quoting and lists once a command that ran twice. `transcript.txt` does not hold
  the output of three commands of step P3, which went to ignored files. Two of the
  thirteen compared environment attributes are literals of the driver. The manifest
  cites step D6 for the eight-character rule and does not state the consumed run's
  verdict. The files are evidence and are not edited.
  [The validation record](../domain/v2-s3-004-pr2-validation.md) gives each, and the
  weaknesses of the driver that this run did not meet.
- **It sent one request.** It does not establish that a second request is answered.
- **It did not observe the network.** It does not establish that the acquisition hook
  downloaded nothing. Argo CD reports that the sync operation, which holds the hook,
  lasted 9 seconds.
- **The pod status names another digest for the API image than the run supplied.** The
  pod requested the supplied digest. After the run, a read of the node listed both digests
  for one image identifier, which is the one the run's build exported. That read is not
  a registered step. No E01-D criterion names the API image digest.
- **The transcript is redacted.** Terminal colour codes are removed, the absolute path of
  the repository on the host is replaced, and two Docker build links are replaced. Line
  endings are changed to LF, and trailing whitespace is removed. The run's own files
  name the first three only.
- **It is one run on one provider, with one node.** The evidence is C2, bounded to the
  environment that `environment.json` records. It is not representative.

**The committed-run check, changed after the run.** `tools.experiment_e01 --check` read
every directory under `runs/` as a static run, so it refused the E01-D directory. This
change edits one function of the runner, `committed_runs`, after the run. The listing
leaves a directory out when its name is that of an E01-D run and its own manifest names
part E01-D and no other. Every other directory is still listed, so a static run under
such a name is checked. The command does not print what it left out.

- **The edit moves one pinned input of revisions 2 and 3:**
  `tools/experiment_e01/core.py`. `python -m tools.experiment_freeze --changes` reports
  it for both records, and exits 1.
- **The E01-D run executed before the edit.** Its step P2 reports no difference for
  revision 3 at the executing commit. The E01-D steps do not run the runner. The run
  and the edit are in one commit, so Git history does not order them: the transcript
  supports the order and does not prove it.
- **A new run of any part is refused** until a merged later revision classifies the
  edit. This change registers no revision and classifies nothing.
- **The static result is not judged again by other code.** `--check` passes over both
  static runs with the edited runner. The edit changes which directories are listed, and
  no line of the analysis.
- **The suites that copy the pinned inputs rebuild the pinned runner.** They take the
  runner in the tree and put back the two passages that the edit replaced. A test holds
  the result to the digest that both records pin. So the listing is the only difference
  between the runner in the tree and the pinned one. Another edit to the runner fails
  that test. The second process of each such test, and one whole test, therefore execute
  the pinned runner and not the runner in the tree.

**The independent review.** [`v2-e01/reviews/20261006-e01-d-1-review-1.md`](v2-e01/reviews/20261006-e01-d-1-review-1.md) is the report of one independent
review of this run, with
[its machine-readable record](v2-e01/reviews/20261006-e01-d-1-review-1.v1alpha1.json). The review
read the first commit of the change that adds the run, `2f2e1ff`, read-only, on
2026-10-06. That commit held no register change. A review record is not evidence of the
run, and no register claim cites it.

- **The frozen run.** The reviewer applied each registered rule to the raw files. Every
  verdict equals the one the run recorded. It found no defect in the files, the digests,
  the freeze identity, the procedure, or the outcome, and it found that a rerun is not
  justified.
- **Fourteen findings, none claim-material.** They are about disclosure and prose. Six
  are corrected in the same change. Four are in run files, which are not edited, and
  are stated. Four are observations.
- **What it could not verify.** That the remote named the executing commit, that the
  cluster returned the committed files, the test result of step D6, and whether a model
  download happened.
- **The limits of its independence.** The reviewer is a separate session of the
  automated assistant that drove the run. It is not a person. It also read uncommitted
  files on the host, which the brief did not ask for.
- **The register.** When the review was published, no ledger referenced this record,
  and the claim and register reconciliation of E01-D was owed by a later change.
  `V2-S3-005-PR1` is that change:
  [its ledger](#registration-of-the-e01-d-result-2026-10-07) references this record, and
  the [review gate](#correction-of-the-second-run-claim-and-the-review-gate-2026-10-03)
  holds the ledger to it: the record must describe the run's files as they are.

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

## Independent review of the second run, 2026-10-03

[`v2-e01/reviews/20261003-e01-abc-1-review-1.md`](v2-e01/reviews/20261003-e01-abc-1-review-1.md)
is the report of one independent review of run `20261003-e01-abc-1`, with
[its machine-readable record](v2-e01/reviews/20261003-e01-abc-1-review-1.v1alpha1.json).
The review read the merge of pull request 114, `3f08f439`, on 2026-10-03, read-only. It
started no run. A review record is not evidence of the run, and no register claim cites it.

- **The frozen run.** The review found no defect in the run's ten files, its digests, its
  freeze and registry identity, its executing revision and 74 pins, its seven criterion
  verdicts, or its three PASSED outcome states.
- **The register statement.** The review found one claim-material defect, in wording only.
  The second-run claim's statement says the evidence holds "no hand-written string that
  contains a generated workload-intent value". E01-AC5 limits that to generated values
  "of eight characters or more". Without the limit the clause is false: three hand-written
  strings contain a shorter generated string value, `local` or `6`. With the limit the clause is
  true. When the review was published, the register, the ledgers, the evidence index,
  and the dashboard carried the broader clause. `V2-S2-005-PR2`
  [corrected the claim later](#correction-of-the-second-run-claim-and-the-review-gate-2026-10-03).
- **The order of review and registration.** The review that the second run's validation
  record documents read commit `c24fda4`, which already held the register change. This
  review also read a revision that held it. So no record establishes that an independent
  review preceded the register change for this run, and this review does not repair that
  order. The same holds for the first run: its documented review read the commit that
  added its claim.
- **No rerun.** The finding is in one sentence of the register, not in the run. A new run
  would answer the same frozen criteria and could not change the sentence.

The report lists thirteen findings, what the review could not verify, and the limits of its
independence: the reviewer is a separate session of the automated assistant that
co-authored the run's change, not a person and not anyone outside the project. When the
review was published, no check required a review record before a register change.
Since `V2-S2-005-PR2` [a gate](#correction-of-the-second-run-claim-and-the-review-gate-2026-10-03)
requires one.

## Correction of the second-run claim, and the review gate, 2026-10-03

`V2-S2-005-PR2` started from `4023487e`, the merge of the change that published the
review. It corrected one statement and added one gate. No part of E01 ran again, and
both runs and both freeze records are unchanged.

**The correction.** [A ninth ledger of register changes](../testing/v2-s2-005-pr2-e01-claim-correction.v1alpha1.json)
narrows the second-run claim's statement. The clause now reads "no hand-written string
that contains a generated workload-intent value of eight characters or more", which is
the limit E01-AC5 carries. The ledger also appends a dated correction to the claim's
limitation. The claim's status, its evidence level, and its record are unchanged.
The correction is additive and later. The ledger that added the claim is not edited and
still holds the earlier wording, and the ninth ledger records that wording as the value
before the change. The earlier wording is on `main` from the merge of `V2-S2-004-PR2`
until this correction merges.

**The order.** Git history gives this sequence, by commit:

1. `c24fda4` added the second run, its claim, and its ledger. The review that the run's
   validation record documents read that commit.
2. `4023487e` merged the published review, which read a revision that held the claim.
3. This change corrected the statement.

No record establishes that an independent review preceded the register change for either E01 run.
The correction does not repair that order, and no later change can.

**The gate.** A register change *bears on* a run when the claim or record it adds, or the
claim or record it changes, names a file under that run's directory, in any field, before
or after the change. A ledger with such a change
must name one review artifact for each run in `resultReviews`: the run's path, the
artifact's path, and the artifact's content digest.
[`tools/evidence_index`](../../../tools/evidence_index/core.py) checks every ledger when
it builds the index, so `--check` and `--write` print `MISMATCH` and exit 1 on a refusal,
as does `--gate` where it reports a freeze, and the
default-lane suite [`tests/testing/test_result_review_gate.py`](../../../tests/testing/test_result_review_gate.py)
plants each refusal in a copy.

| Refused | Reason |
|---|---|
| A ledger that bears on a run and names no review of it | The review reference is omitted |
| A reference whose artifact is absent | The review is not in the repository state the index is built from |
| An artifact whose content digest is not the one the ledger states | The artifact changed after the ledger named it, or the ledger names other content |
| A `resultReviews` row that is not exactly the three strings, or references that are not a list | The reference cannot be read |
| A register change with an operation the gate does not know | The gate cannot say what the change bears on |
| An artifact that is not JSON, is not an `ExperimentResultReview`, or is not a plain path under the experiment's `reviews/` directory | It is not a result review of this experiment |
| An artifact whose `subject` names another run | The review is about another result |
| An artifact whose file digests are not those of the run's files, or that omits or adds a file | The review is stale: the run is not what the review read |
| An artifact that does not name the freeze record the run's manifest names, or that gives another digest for it | The review read another freeze record |
| Two references for one run, or a reference for a run no change bears on | The reference is ambiguous or unrelated |
| A review stated by a ledger written before the gate | A review written since did not precede that ledger |

The ninth ledger bears on the second run. It references
[the published review record](v2-e01/reviews/20261003-e01-abc-1-review-1.v1alpha1.json),
and the gate accepts that reference. The review record is unchanged since it merged.

**What the gate does not do.**

- **It does not prove an order in time.** The gate reads one repository state.
  It does not show that a review was committed before the register change: a review
  artifact and a ledger can arrive in one commit. For this correction only, a test reads
  Git history and finds the review record, with its present content, at `4023487e`, where
  the ninth ledger does not exist. That test skips in a clone without that commit, and a
  skip is not a pass.
- **It does not judge the review.** It does not show that a review took place, who did
  it, whether it was independent, or what it concluded. A review record that reports a
  defect satisfies the gate.
- **It does not bind a review to a change.** One review artifact of a run satisfies
  every later ledger that bears on that run, including a change the review did not read.
  The gate does not read the register state the review recorded.
- **It does not cover the two earlier ledgers.** The ledgers that added the two E01
  claims were written before the gate. Each names no review, and the tool lists them in
  `PRE_GATE_LEDGER_PATHS` and in the index, under `registeredBeforeTheGate`. That list
  records what happened. It does not say that either ledger complied. The gate does not
  check these two ledgers, whatever they hold; a test holds each to its content.
- **It sees a run only by a named path.** A record that states a run's result and names
  no file under the run's directory does not bear on the run, as the gate reads it. The
  gate matches a path in the repository's normal form; the register's own rules, which
  the default lane runs, refuse a path in another form. The gate follows a symbolic
  link, and a path in another letter case resolves on a host whose file system ignores
  case.
- **It can be changed with the ledger.** A change that edits the gate, or the list of
  earlier ledgers, together with a ledger passes the check. A test holds that list to
  its two entries, so such an edit shows in review as a changed test.

E01-D ran once, in [`20261006-e01-d-1`](v2-e01/runs/20261006-e01-d-1/result.md). A register change that
bears on that run is to reference a review of that run: the review record of the static
run names another run, and the gate would refuse it for a record that names a file under
another run directory. [The registration of the E01-D result](#registration-of-the-e01-d-result-2026-10-07)
is the first such change.

## Registration of the E01-D result, 2026-10-07

`V2-S3-005-PR1` added the result of [the E01-D run](#the-e01-d-run) to the claim and
evidence register. No part of E01 ran in that change. No file of a run, of a freeze
record, or of a review record changed. Its
[validation record](../domain/v2-s3-005-pr1-validation.md) lists each identity it
consumed.

**The order of events.** The history is kept as it happened:

1. On 2026-10-06, `V2-S3-004-PR1` merged revision 3.
2. On 2026-10-06, `V2-S3-004-PR2` ran E01-D once, published the independent review of
   the run, and merged. It registered no claim and no evidence record. Its validation
   record says that the reconciliation was owed by a later change.
3. On 2026-10-06, a collective review of the sprint found that the reconciliation the
   story requires was missing. It found the freeze inputs, the raw run, the result
   classification, and the review record sound, and it stated that the finding
   justifies no repeated run.
4. On 2026-10-07, `V2-S3-005-PR1` added the claim, through
   [the E01-D registration ledger](../testing/v2-s3-005-pr1-e01-d-registration.v1alpha1.json),
   the tenth ledger of register changes and the sixth after `v1.0.0`.

The register does not state that the registration happened on the day of the run. The
claim's limitation and the record's limitations each carry the two dates.

**The claim.** `the-e01-real-deployment-run-served-one-completion-from-the-release-reconciled-from-git`
is `certified` on one record at `C2`. It says, in the past tense, what one run showed: on
the `docker-desktop` provider, on one cluster with one node, the release rendered from
the unmodified reference contract was accepted into Git at one commit, was reconciled by
Argo CD, and answered one completion request with HTTP 200 and a non-empty assistant
message, under E01-AC8, E01-AC9, and E01-AC10 of revision 3.

**The review reference.** The ledger names two review artifacts in `resultReviews`, each
with its content digest:

- [the review of the E01-D run](v2-e01/reviews/20261006-e01-d-1-review-1.v1alpha1.json),
  because the claim and its record cite the run's files;
- [the review of the second static run](v2-e01/reviews/20261003-e01-abc-1-review-1.v1alpha1.json),
  because one rule of E01-AC10 rests on that run, so the record cites its manifest, and
  because the ledger changes one clause of that run's claim.

The gate was not changed. It checked each artifact against the run it names: the files
of the run directory have the digests the review states, and the review names the freeze
record that the run's manifest names. For the E01-D run, Git history also shows the
order: the review record has had its present content since the merge of
`V2-S3-004-PR2`, and the ledger is not in that commit. The gate does not read history.
A test does, and it skips in a clone that lacks that commit.

**What else the ledger changes.**

- **Two planned claims gain a dated note and stay planned.**
  `the-platform-serves-a-workload-the-contract-describes` and
  `deployment-values-derive-only-from-a-validated-document` each said something that the
  E01-D run made out of date. Each keeps its earlier text, gains sentences dated
  2026-10-07 that name the run, and cites no record. One run, with one contract, on one
  provider, does not establish either general statement.
- **One clause of the second static run's claim is replaced.** The clause said that
  E01-D "has not run".
- **One surface reason is replaced.** It named nine ledgers.

**What it does not correct.**

- **The first static run's claim still says that E01-D "has not run".** A change to that
  claim bears on run `20261002-e01-abc-1`. No review record of that run exists, so the
  gate refuses the change, and `V2-S3-005-PR1` creates no review. The clause is a
  statement of 2026-10-02.
- **The evidence records of the two static runs say the same.** Each is a dated record,
  and neither is changed.
- **The files of the E01-D run keep their text.** The review record lists where a run
  file says less than what executed. The register record states those limits.

**What the claim does not establish.** A second request. Another provider, Kubernetes
version, node count, storage class, workload shape, contract, or binding. That Argo CD
applies a later commit. A caller outcome from a sync state, a health state, pod
readiness, or a replica count. That the acquisition hook downloads the model into an
empty claim. Latency, throughput, capacity, availability, or behaviour under overload.
Reliability under failure, high availability, or tolerance of the loss of a pod, a node,
a zone, or a region. That a service-level objective is met. Representative evidence,
`C3`, or operational evidence, `C4`. A cost, a saving, a return on investment, or a
business effect. That a person reviewed the result. Production readiness.

**What stays open.**

- No command judges the committed E01-D run again. `python -m tools.experiment_e01
  --check` judges the two static runs and leaves the E01-D run out, so its exit status
  says nothing about E01-D. Tests apply the registered rules to the run's files.
- A new run of any part of E01 is refused until a later freeze revision classifies the
  edit to the committed-run listing.
- The review of the result is a record of an automated session. No person and no
  outside party reviewed it.
