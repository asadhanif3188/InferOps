# V2-S5-002-PR2 validation

Status: **the experiment evidence layout is published, with an offline check of a run
directory. No run executed in this change, and no run directory of the layout exists.**
Nothing writes a run directory, and nothing reads one for analysis. The evidence is
static, C0: the suite reads committed files and files that it writes under a temporary
directory. No claim was registered.

> [!IMPORTANT]
> **Nothing here is a result of an experiment.** Each run directory that the suite
> checks is built by the suite: a manifest from a committed fixture with placeholder
> identities, a freeze record of two members, a caller record that the runner's own loop
> writes against one scripted answer, and a few lines of text for each other file. The
> suite shows that the check, the layout page, and the evidence index's hashing agree.
> It does not show that a run happened, or that a file of a run directory came from a
> cluster.

| Property | Value |
|---|---|
| Date | 2026-10-11 |
| Base | `7f6e6e4`, the merge of pull request #138 |
| Branch | `feat/v2-s5-002-evidence-layout` |
| Commits | The first commit: the check, the suite, the layout page, and the pages that name it. A second commit, when an independent review of the first finds a defect: the corrections |
| Host | One Windows workstation, Git Bash (GNU bash 5.2.26); Python 3.12.12 from `uv` 0.9.16 |
| Container engine and cluster | Not used. No cluster was contacted |
| Evidence level | C0, static |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, or experiment freeze record was added or changed |

## What changed

| Path | Change |
|---|---|
| [`tools/experiment_evidence/core.py`](../../../tools/experiment_evidence/core.py), `__main__.py`, `__init__.py` | New. The check of a run directory, the repository listing, the helpers of a writer, and three commands: `check`, `repository`, and `digests` |
| [`tests/testing/test_experiment_evidence_layout.py`](../../../tests/testing/test_experiment_evidence_layout.py) | New. 79 test functions, 161 cases |
| [`docs/testing/experiment-evidence-layout.md`](../../testing/experiment-evidence-layout.md) | New. The layout page: the tree, the hashing, the 13 roles, the correction form, the 21 rules, the compatibility notes, the measured gaps, and what no rule holds |
| [`tools/evidence_index/core.py`](../../../tools/evidence_index/core.py) | One function added and one line changed. The result review gate reads the freeze record of a run manifest in both shapes. See [the decisions](#decisions-taken-in-this-change) |
| [`docs/contracts/experiment-run.md`](../../contracts/experiment-run.md) | Five passages: the status, one measured gap, the opening of the rules that nothing applies, one item of that list, and two items of what the contract does not do. Each now names the layout. No rule and no table of the contract changed |
| `docs/testing/README.md`, `docs/proof/README.md`, `docs/proof/experiments/README.md`, `CHANGELOG.md` | One row, one clause, one paragraph, and one entry |
| `docs/testing/test-inventory.md` and `.v1alpha1.json` | One row, and two written counts: eighty-four modules with no claim, and fifty-six modules in the documentation layer |
| `.github/secret-scanning-allowlist.md` | The new suite. The count of suites became thirteen. `.gitleaks.toml` is unchanged |

**Not changed:** the ExperimentRun schema, its fixtures, its validator, the pre-schema
register, each freeze record, the freeze registry, each run directory, each review
record, the claim and evidence register, each ledger, the evidence index, the proof
dashboard, the E01 runner, the reliability runner, the chart, and the Git desired state.

## What the change was asked to reach, and what it reached

| Asked | Reached | How it is held |
|---|---|---|
| Evidence-directory conventions | A run directory at `runs/<runId>` beside the freeze record its manifest names, closed in both directions, with corrections beside the `runs` directory | 21 rules, each with a test that provokes it |
| Integrity checks | Each named file is present with its stated digest; each present file is named; the freeze record has its revision and digest; a link and a file of an unsupported form are refused | `python -m tools.experiment_evidence check` and `repository` |
| Helpers for raw caller, endpoint, pod and Deployment, Argo, telemetry, resource, transcript, analysis, and result files | A registered role for each, with three more: `commands`, `environment`, and `release`. `describe_file` returns one `evidence.files` entry, and `digests` prints each digest. **Only the caller file has a defined form.** No collector for the other raw roles exists | The role table of the page is compared with the module |
| Hashing compatible with the current evidence tooling | The digest and the list of text suffixes are the evidence index's own objects. The two digests of a run are the index's set digest | The suite compares the objects, converts a run directory to CRLF, and recomputes both digests with the index's functions |
| Index compatibility | A run directory is where the result review gate reads one. The gate now reads the freeze record of a manifest of the published schema | The suite gives the gate a run of this layout with a review record |
| Additive corrections | A correction is a new file outside the run directory. It states the digest of the manifest, of each file it corrects, and of the correction before it | 6 rules are of a correction, and the file rules hold the files it adds. The suite holds that a correction moves neither digest of the run |
| Secrets, prompts, and personal paths are not required | The layout requires no file and no role. A `REFUSED` run with no evidence file conforms. Two text rules refuse a word with a published credential prefix and a path under a user directory | The suite, with each rule's measured limits |
| Generated summaries stay downstream of raw evidence | Each role is raw or derived. A derived file with no raw file is refused. The raw digest is taken over the raw files alone | The suite rewrites a summary and holds that the raw digest does not move. **No rule shows that a summary was computed from the raw files** |

### The criteria of the parent change

| Criterion | State |
|---|---|
| ExperimentRun `v1alpha1` or an equivalent is versioned and validated | Reached by `V2-S5-002-PR1`. Unchanged here |
| It records the experiment, the spec, the environment, the release, the profile, the fault, the result, the evidence, and the limitations | Reached by `V2-S5-002-PR1`. Unchanged here |
| The raw evidence layout is deterministic, hashable, and public-safe | **Reached as a layout and a check, at C0.** Deterministic: a manifest fixes the place of its run directory, and each name is compared as text. Hashable: one digest for a file in each tool and on each host. Public-safe: within the limits of two text rules, which are heuristics. **No run directory of the layout exists**, so the criterion is not shown on evidence of a run |
| `PASSED`, `FAILED`, `INCONCLUSIVE`, `REFUSED`, and `ABORTED` are explicit run states | Reached by `V2-S5-002-PR1`. The layout binds no rule to a state |

## Decisions taken in this change

Each is a choice that the request left open. Each can be reversed by a later change.

1. **A separate tool.** The check is `tools/experiment_evidence`, and
   `tools/experiment_run` is unchanged. The ExperimentRun validator reads one document
   and its pages say that it opens no evidence file. That stays true.
2. **A run directory is beside its freeze record.** This is where the three committed
   run directories are, and where the result review gate reads a run. The experiment
   specification's sketch of another tree was a candidate and not a requirement.
3. **An evidence file is text of one of seven suffixes.** The evidence index hashes
   those as text and every other file byte for byte. A file under another suffix could
   have two digests on two hosts. So an image and an archive cannot be evidence files of
   this layout. A run that needs one needs a later change.
4. **The role vocabulary is closed, with 13 roles.** The request names nine kinds of
   file. Pod and Deployment readings are two roles. Three roles are added for files that
   each executed run so far has held: `commands`, `environment`, and `release`. A run
   that needs another role adds it in a change that a reviewer reads.
5. **A correction is outside the run directory.** The result review gate compares each
   file of a run directory with the digests in a review record. A correction inside the
   directory would end each earlier review of the run.
6. **The form of a correction is held in code.** No JSON Schema file defines it, as
   none defines the pre-schema register. It is not a fifth contract.
7. **The credential rule reads a published prefix and not a shape.** The shape heuristic
   of the ExperimentRun rules was measured on the committed proof files: it reads words
   of raw records, of transcripts, and of two run manifests as credentials. A rule that
   refuses raw evidence would require an edit of raw evidence. The prefix rule was
   measured on the same files: no file that is not a Markdown page starts a word with a
   published prefix.
8. **One function of the result review gate changed.** The gate named the freeze record
   of a run through `metadata.freezeRecord`. A manifest of the published schema states it
   in `metadata.spec.freezeRecord`. Without the change, the gate would refuse the review
   of the first run of the published schema. The gate now reads either member. Its
   verdict on each committed ledger is unchanged, and `tools.evidence_index --check`
   passes with the same two digests.
9. **The three earlier run directories are listed and not checked.** The schema refuses
   each manifest, so no rule of the layout applies. The mechanisms that held them hold
   them still.
10. **No example run directory is committed.** A directory under
    `docs/proof/experiments/` would be listed as a run. The suite builds each directory
    it checks.

## The negative controls

Each is a case of the suite, and each is refused by exactly the rules named.

| Case | Refused by |
|---|---|
| A directory with no manifest, and a path that names no directory | `evidence-manifest-missing` |
| A manifest with a member removed, and a manifest that is not JSON | `evidence-manifest-refused`, and nothing else of the directory is read |
| A run directory under another name, beside another freeze record, and outside the tree | `evidence-run-directory-misplaced` |
| 3 freeze records outside one experiment directory | `evidence-run-directory-misplaced` |
| A freeze record that is edited, absent, not JSON, under another letter case, and of 4 other revisions | `evidence-freeze-record-differs` |
| A named file that is absent | `evidence-file-missing` |
| 3 files that no manifest names, one of them a file that Git would ignore | `evidence-file-unlisted` |
| An edited file | `evidence-file-digest-differs` |
| A file under another letter case | `evidence-file-missing` and `evidence-file-unlisted` |
| `pods.jsonl` beside `pods.jsonl/a.json` | `evidence-file-missing` |
| A link | `evidence-file-not-regular`. On this host the suite replaces the host's answer for one file name: see [the two skipped tests](#validation-at-the-first-commit) |
| 5 files: two suffixes outside the seven, no suffix, bytes that are not UTF-8, and a NUL character | `evidence-file-form-unsupported` |
| The role `completion` | `evidence-role-unregistered` |
| A result file and an analysis file with no raw file | `evidence-summary-without-raw` |
| A caller file with one header member, and a caller record with no end line | `evidence-caller-record-refused` |
| A caller record of another run, of another experiment, of another release, of a rehearsal, and under a manifest with no caller profile | `evidence-caller-record-identity-differs` |
| 4 texts with a word that starts with a published credential prefix | `evidence-file-credential-prefix`, and the message repeats no word |
| 6 paths under a user directory, one of them as JSON writes it | `evidence-file-personal-path`, and the message repeats no name |
| 22 corrections that do not have the form | `evidence-correction-unreadable` |
| A correction that is a JSON array, and one that states a member twice | `evidence-correction-unreadable` |
| A correction of another run, of another experiment, and with another manifest digest | `evidence-correction-identity-differs` |
| A first correction that states an earlier one, a second with another digest, and an edited first correction under a second | `evidence-correction-chain-broken` |
| A correction numbered 2 with no first, and a number that is not the file's | `evidence-correction-number-out-of-sequence` |
| A corrected file with another digest, a file that is not of the run, and a correction that corrects itself | `evidence-correction-target-differs` |
| A file edited after its correction | `evidence-file-digest-differs` and `evidence-correction-target-differs` |
| A file and its manifest digest rewritten together, after a correction | `evidence-correction-identity-differs` |
| An added file that is edited, absent, not named, or of an unregistered role | The rule that holds the same defect in a run directory |
| A corrections directory for no run, and for an earlier run directory | `evidence-correction-run-unknown` |
| A register with a defect | `evidence-manifest-refused`, as a finding of the listing |
| 8 entries that a writer asks for and the check would refuse | `LayoutError` with the rule, from `describe_file` |

**The controls that must pass.** A run directory that holds what its manifest names. The
same directory with each file converted to CRLF. A `REFUSED` run with no evidence file. A
derived file beside one raw file, for each of the 10 raw roles other than `caller`. A
file under each of the seven suffixes. One correction with an added file, and a second
correction of the first. A caller record that declares no release. A review record of a
run of this layout, before and after a correction.

**What is measured as accepted.** Seven texts that the two text rules do not refuse. A
file and its manifest digest rewritten together with no correction. A result page that
was not computed from the raw files. A file with the role `pods` that holds no reading
of a pod. Each is a test, and [the layout page](../../testing/experiment-evidence-layout.md#measured-gaps)
lists each.

## Validation at the first commit

| Command | Result |
|---|---|
| `uv run --locked python -m pytest tests/testing/test_experiment_evidence_layout.py -q` | 159 passed, 2 skipped |
| `uv run --locked python -m pytest tests/testing/test_test_inventory.py tests/contracts/test_experiment_run_v1alpha1.py tests/testing/test_result_review_gate.py tests/testing/test_evidence_index.py tests/testing/test_document_links.py tests/testing/test_test_strategy.py tests/security -q` | 0 failed. Run as three commands |
| `uv run --locked python -m tools.experiment_evidence repository` | Exit 0. Three `pre-schema` lines, and `runs       3: 3 pre-schema and not checked, 0 conforming, 0 refused` |
| `uv run --locked python -m tools.experiment_evidence digests docs/proof/experiments/v2-e01/runs/20261006-e01-d-1` | Exit 0. 11 lines. Each digest is the one that the committed review record of that run states for the file |
| `uv run --locked python -m tools.experiment_run repository` | Exit 0. `manifests  3: 3 pre-schema, 0 conforming, 0 refused` |
| `uv run --locked python -m tools.evidence_index --check` | `OK`. The committed index is what the register and the ledgers produce |
| `uv run --locked python -m tools.evidence_index --gate` | Exit 0. Evidence set `549946af...cbefcc` and evidence pack `06e214dc...3d0720`, as before this change |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_freeze --changes` for revisions 2 and 3 | 17 and 30 material files differ, the same counts as on the base commit. This change moves no material file |
| `uv run --locked python -m tools.experiment_e01 --check` | `PASSED: 2 run(s), each agrees with its own evidence` |
| `uv run --locked ruff format --check .` | 714 files already formatted |
| `uv run --locked ruff check .` | All checks passed |
| `uv run --locked python -m mypy` | No issues found in 392 source files |
| `uv run --locked python -m pytest -q` | Started on the tree of the first commit, and not complete when that commit was made. [The second commit](#validation-at-the-second-commit) states the result |
| `uv run --locked python -m tools.ci_gates expected-failures` | Exit 0. 63 controls produced the exit status that the repository requires of them |
| `git diff --check` | No output |

## Validation at the second commit

The second commit writes this section.

**The two skipped tests.** One creates a symbolic link, and this host does not let the
suite create one. One creates a file whose name holds a line break, and this host's file
system holds none. A second test of each rule runs on every host: one replaces the host's
answer to "is this a link" for one file name, and one gives the name to the function
that prints it. So on this host the link rule was provoked through a replaced answer and
not through a real link.

**Not run.** No cluster was contacted, no image was built, and no model was read. The
hosted workflows did not run on this branch before the push. No test under the `cluster`,
`realruntime`, `failure`, or `load` marker ran: the default marker expression deselects
them, and this change bears on none.

## What the evidence establishes

- At C0, the committed check refuses each case of the table above and accepts each
  control.
- The layout's digest of a text file is the evidence index's digest of it.
- The layout page states each rule and each role as the module does.

## What the evidence does not establish

- That a run executed. No run directory of the layout exists.
- That the layout holds what a real run needs. No run wrote a directory of it, and no
  collector wrote a file with a raw role other than `caller`.
- That a file of a run directory was committed, or that a run directory was not replaced
  together with its manifest. The check reads one tree and not Git.
- That a derived file follows from the raw files beside it.
- That a file holds no secret. The two text rules are heuristics with measured limits.
- That the result review gate accepts a ledger for a run of this layout. The suite gives
  the gate's check of one review record a run of this layout. No ledger bears on such a
  run.
- Runtime behaviour of any kind. A C0 record does not establish that a release serves,
  that a fault was survived, or that a caller saw an answer.
