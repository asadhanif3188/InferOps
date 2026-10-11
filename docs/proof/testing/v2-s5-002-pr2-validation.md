# V2-S5-002-PR2 validation

Status: **the experiment evidence layout is published, with an offline check of a run
directory. No run executed in this change, and no run directory of the layout exists.**
Nothing writes a run directory, and nothing reads one for analysis. The evidence is
static, C0: the suite reads committed files and files that it writes under a temporary
directory. No claim was registered. Two independent reviews read the first commit. They
found forms of a credential that the prefix rule passed, forms of a user directory that
the path rule passed, an error that no rule names, three kinds of entry that the check
did not read, and sentences that said more than the code does: see
[what the independent reviews found](#what-the-independent-reviews-found).

> [!IMPORTANT]
> **Nothing here is a result of an experiment.** Each run directory that the suite
> checks is built by the suite: a manifest from a committed fixture with placeholder
> identities, a freeze record that states one revision, a caller record that the
> runner's own loop writes against one scripted answer, and a few lines of text for each
> other file. Two tests read one committed run directory, and each holds that it is
> refused at its manifest. The suite shows that the check, the layout page, and the
> evidence index's hashing agree. It does not show that a run happened, or that a file
> of a run directory came from a cluster.

| Property | Value |
|---|---|
| Date | 2026-10-11 |
| Base | `7f6e6e4`, the merge of pull request #138 |
| Branch | `feat/v2-s5-002-evidence-layout` |
| Commits | The first commit: the check, the suite, the layout page, and the pages that name it. The second commit: the corrections of the two independent reviews, and the default lane on the final tree |
| Host | One Windows workstation, Git Bash (GNU bash 5.2.26); Python 3.12.12 from `uv` 0.9.16 |
| Container engine and cluster | Not used. No cluster was contacted |
| Evidence level | C0, static |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, or experiment freeze record was added or changed |

## What changed

The counts are of the second commit.

| Path | Change |
|---|---|
| [`tools/experiment_evidence/core.py`](../../../tools/experiment_evidence/core.py), `__main__.py`, `__init__.py` | New. The check of a run directory, the repository listing, the helpers of a writer, and three commands: `check`, `repository`, and `digests` |
| [`tests/testing/test_experiment_evidence_layout.py`](../../../tests/testing/test_experiment_evidence_layout.py) | New. 104 test functions, 217 cases |
| [`docs/testing/experiment-evidence-layout.md`](../../testing/experiment-evidence-layout.md) | New. The layout page: the tree, the hashing, the 13 roles, the correction form, the 21 rules, the compatibility notes, the measured gaps, and what no rule holds |
| [`tools/evidence_index/core.py`](../../../tools/evidence_index/core.py) | One function added, `_named_freeze_record`, and two lines of `_checked_review` changed: the call, and one more error type that it reads as "no freeze record named". See [the decisions](#decisions-taken-in-this-change) |
| [`docs/contracts/experiment-run.md`](../../contracts/experiment-run.md) | Six passages: the status, one measured gap, the opening of the rules that nothing applies, one item of that list, and two items of what the contract does not do. Each now names the layout. No rule and no table of the contract changed |
| `docs/testing/README.md`, `docs/proof/README.md`, `docs/proof/experiments/README.md`, `CHANGELOG.md` | One row, one clause, one paragraph, and one entry |
| `docs/testing/test-inventory.md` and `.v1alpha1.json` | One row, and two written counts: eighty-four modules with no claim, and fifty-six modules in the documentation layer |
| `.github/secret-scanning-allowlist.md` | The new suite. The count of suites became thirteen. `.gitleaks.toml` is unchanged |

**Not changed:** the ExperimentRun schema, its fixtures, its validator, the pre-schema
register, each freeze record, the freeze registry, each run directory, each review
record, the claim and evidence register, each ledger, the evidence index, the proof
dashboard, the E01 runner, the reliability runner, the chart, the Git desired state, and
`.gitattributes`.

## What the change was asked to reach, and what it reached

| Asked | Reached | How it is held |
|---|---|---|
| Evidence-directory conventions | A run directory at `runs/<runId>` beside the freeze record its manifest names, closed in both directions, with corrections beside the `runs` directory | 21 rules. The suite names each in an assertion that expects it |
| Integrity checks | Each named file is present with its stated digest; each present file is named; the freeze record has its revision and digest; a link and a file of an unsupported form are refused | `python -m tools.experiment_evidence check` and `repository` |
| Helpers for raw caller, endpoint, pod and Deployment, Argo, telemetry, resource, transcript, analysis, and result files | A registered role for each, with three more: `commands`, `environment`, and `release`. `describe_file` returns one `evidence.files` entry, and `digests` prints each digest. **Only the caller file has a defined form.** No tool writes a file of another raw role of this layout | The role table of the page is compared with the module |
| Hashing compatible with the current evidence tooling | The set of text suffixes is the evidence index's own object, and the digest function is the index's. The two digests of a run are the index's set digest | The suite holds the identity of the suffix set, compares the digests of the files of one run directory and of one committed record, converts a run directory to CRLF, and recomputes both run digests with the index's functions |
| Index compatibility | A run directory is where the result review gate reads one. The gate now reads the freeze record of a manifest of the published schema | The suite gives the gate's check of one review record a run of this layout |
| Additive corrections | A correction is a new file outside the run directory. It states the digest of the manifest, of each file it corrects, and of the correction before it | 6 rules are of a correction, and the file, role, and caller rules hold the files it adds. The suite holds that a correction moves neither digest of the run. **The chain is not a lock:** the suite measures that a run and its corrections, replaced together, conform |
| Secrets, prompts, and personal paths are not required | The layout requires no file and no role. A `REFUSED` run with no evidence file conforms. Two text rules refuse the published prefix of a credential format and a path under a user directory | The suite, with what each rule still accepts |
| Generated summaries stay downstream of raw evidence | Each role is raw or derived. A derived file with no raw file is refused. The raw digest is taken over the raw files alone | The suite rewrites a summary and holds that the raw digest does not move. **No rule shows that a summary was computed from the raw files** |

### The criteria of the parent change

| Criterion | State |
|---|---|
| ExperimentRun `v1alpha1` or an equivalent is versioned and validated | Reached by `V2-S5-002-PR1`. Unchanged here |
| It records the experiment, the spec, the environment, the release, the profile, the fault, the result, the evidence, and the limitations | Reached by `V2-S5-002-PR1`. Unchanged here |
| The raw evidence layout is deterministic, hashable, and public-safe | **Reached as a layout and a check, at C0, within stated limits.** Deterministic: a manifest fixes the place of its run directory, and the names the check opens beneath it are compared as text. Hashable: one digest for a text file in each tool and on each host. Public-safe: only within the limits of two text rules, which read a prefix and a path form and nothing else. **No run directory of the layout exists**, so the criterion is not shown on evidence of a run |
| `PASSED`, `FAILED`, `INCONCLUSIVE`, `REFUSED`, and `ABORTED` are explicit run states | Reached by `V2-S5-002-PR1`. The layout binds no rule to a state |

## Decisions taken in this change

Each is a choice that the request left open. Each can be reversed by a later change.

1. **A separate tool.** The check is `tools/experiment_evidence`, and
   `tools/experiment_run` is unchanged. The ExperimentRun validator reads one document
   and its pages say that it opens no evidence file. That stays true.
2. **A run directory is beside its freeze record.** This is where the three committed
   run directories are, and where the result review gate reads a run.
3. **An evidence file is text of one of seven suffixes.** The evidence index hashes
   those as text and every other file byte for byte. A file under another suffix could
   have two digests on two hosts. So an image and an archive cannot be evidence files of
   this layout. A run that needs one needs a later change.
4. **The role vocabulary is closed, with 13 roles.** The request names nine kinds of
   file. Pod and Deployment readings are two roles. Three roles are added for files that
   a committed run directory holds: `commands`, for a file that each of the three holds,
   and `environment` and `release`, for files of the E01-D run. A run that needs another
   role needs a change to the vocabulary.
5. **A correction is outside the run directory.** The result review gate compares each
   file of a run directory with the digests in a review record. A correction inside the
   directory would end each earlier review of the run.
6. **The form of a correction is held in code.** No JSON Schema file defines it, as
   none defines the pre-schema register. It is not a fifth contract.
7. **The credential rule reads a published prefix and not a shape.** The shape heuristic
   of the ExperimentRun rules, applied to the whole text of each committed proof file
   that is not a Markdown page, reads words of 27 files as credentials. Among them are
   raw records, transcripts, and the three run manifests. A rule that refuses raw
   evidence would require an edit of raw evidence. The prefix rule, applied to the same
   files, reads one: a ledger that names a prefix in a sentence.
8. **One function was added to the result review gate, and one was changed.** The gate
   named the freeze record of a run through `metadata.freezeRecord`. A manifest of the
   published schema states it in `metadata.spec.freezeRecord`. Without the change, the
   gate would refuse the review of the first run of the published schema. The gate now
   reads `metadata.spec.freezeRecord` when `metadata` has a `spec` member, and
   `metadata.freezeRecord` when it has none. It refuses a manifest that has both. None
   of the three committed manifests has a `spec` member, so the gate reads for each what
   it read before. The gate's suite and `tools.evidence_index --check` pass.
9. **The three earlier run directories are listed and not checked** by the `repository`
   command. The schema refuses each manifest, so no rule of the layout applies. The
   `check` command, given one, refuses it at its manifest.
10. **No example run directory is committed.** A directory under
    `docs/proof/experiments/` would be listed as a run.
11. **`.gitattributes` is not edited.** It pins LF for the run directories of one
    experiment directory. The layout's digest does not depend on the pin, because it
    replaces each CRLF. A later run under another experiment directory is not pinned.

## The negative controls

Each is a case of the suite, and each is refused by exactly the rules named. The table
does not list every case: the suite does.

| Case | Refused by |
|---|---|
| A directory with no manifest, and a path that names no directory | `evidence-manifest-missing` |
| A manifest with a member removed, and a manifest that is not JSON | `evidence-manifest-refused`, and nothing else of the directory is read |
| A committed run directory of the earlier shape, as a copy and through the `check` command | `evidence-manifest-refused` |
| A run directory under another name, beside another freeze record, and outside the tree | `evidence-run-directory-misplaced` |
| 3 freeze records outside one experiment directory | `evidence-run-directory-misplaced` |
| A freeze record that is edited, absent, not JSON, under another letter case, and of 4 other revisions | `evidence-freeze-record-differs` |
| 6 freeze records: a revision of `1.0` and of `1e0`, a member stated twice at two depths, a value that is not JSON, and 100,000 nested arrays | `evidence-freeze-record-differs` |
| A named file that is absent | `evidence-file-missing` |
| 3 files that no manifest names, one of them with a leading dot | `evidence-file-unlisted` |
| A file in a `runs` directory and a file in a `corrections` directory | `evidence-file-unlisted`, from the `repository` command |
| An edited file | `evidence-file-digest-differs` |
| A file under another letter case | `evidence-file-missing` and `evidence-file-unlisted` |
| `pods.jsonl` beside `pods.jsonl/a.json` | `evidence-file-missing` |
| A Windows directory junction in a run directory, and one in a `runs` directory | `evidence-entry-is-a-link`. Run on this host |
| A symbolic link | `evidence-entry-is-a-link`. On this host the suite replaces the host's answer for one file name: see [the skipped tests](#the-skipped-tests) |
| 5 files: two suffixes outside the seven, no suffix, bytes that are not UTF-8, and a NUL character | `evidence-file-form-unsupported` |
| An evidence path that ends in `run.v1alpha1.json`, absent and present, and the same name added by a correction | `evidence-file-form-unsupported` |
| The role `completion` | `evidence-role-unregistered` |
| A result file and an analysis file with no raw file | `evidence-summary-without-raw` |
| A caller file with one header member, and a caller record with no end line | `evidence-caller-record-refused` |
| A caller record of another run, of another experiment, of another release, of a rehearsal, of a rehearsal that names its own run, and under a manifest with no caller profile | `evidence-caller-record-identity-differs` |
| A caller file that a correction adds: one that is no caller record, and one of another run | `evidence-caller-record-refused`, `evidence-caller-record-identity-differs` |
| 14 texts with a published credential prefix: 4 in a run directory, and 10 in the forms that the first commit passed | `evidence-file-credential-prefix`, and the message repeats no value |
| 2 ordinary names that start with a published prefix | `evidence-file-credential-prefix`. Measured as a refusal of ordinary text |
| 13 paths under a user directory: 6 in a run directory, and 7 in further forms, one of them a URL whose host is `home` | `evidence-file-personal-path`, and the message repeats no name |
| A container path under a home directory | `evidence-file-personal-path`. Measured as a refusal of a path that is not of a host |
| 25 corrections that do not have the form | `evidence-correction-unreadable` |
| A correction that is a JSON array, and one that states a member twice | `evidence-correction-unreadable` |
| A correction of another run, of another experiment, and with another manifest digest | `evidence-correction-identity-differs` |
| A first correction that states an earlier one, a second with another digest, and an edited first correction under a second | `evidence-correction-chain-broken` |
| A correction numbered 2 with no first, and a number that is not the file's | `evidence-correction-number-out-of-sequence` |
| A corrected file with another digest, a file that is not of the run, a correction that corrects itself, and one that corrects a file it adds | `evidence-correction-target-differs` |
| A file edited after its correction, in the run directory and among the files of an earlier correction | `evidence-file-digest-differs` and `evidence-correction-target-differs` |
| A file and its manifest digest rewritten together, after a correction that is left unchanged | `evidence-correction-identity-differs` |
| A file that a correction adds: edited, absent, not named, or of an unregistered role | The rule that holds the same defect in a run directory |
| A statement of a correction with a published prefix, and one with a path under a user directory | `evidence-file-credential-prefix`, `evidence-file-personal-path` |
| A corrections directory of a run for no run, for an earlier run directory, and one that is a file | `evidence-correction-run-unknown` |
| A register with a defect | `evidence-manifest-refused`, as a finding of the listing |
| 10 entries that a writer asks for | `LayoutError` with the rule, from `describe_file` |
| A manifest that names its freeze record in both members, and 5 malformed `metadata` values | The result review gate's reader of a manifest raises, and the gate reads that as no freeze record named |

**The controls that must pass.** A run directory that holds what its manifest names. The
same directory with each file converted to CRLF. A `REFUSED` run with no evidence file. A
derived file beside one raw file, for each of the 10 raw roles other than `caller`. A
file under each of the seven suffixes. One correction with an added file, a second
correction of the first, and a correction of a file that an earlier correction adds. A
caller record that a correction adds. A caller record that declares no release. A review
record of a run of this layout, before and after a correction.

**What is measured as accepted.** Each is a test, and
[the layout page](../../testing/experiment-evidence-layout.md#measured-gaps) lists each: 7
texts in a run directory and 8 further forms that the two text rules do not refuse; a
file and its manifest digest rewritten together with no correction; a run and its
corrections rewritten together; an edited correction with the next one rewritten; removed
corrections; a corrections directory under another letter case; the corrections of a
refused run; a recorded time of 1999 and a statement of the shape that the ExperimentRun
rules refuse; an empty directory, an empty file, a byte order mark, and a lone carriage
return; a result page that was not computed from the raw files; a file with the role
`pods` that holds no reading of a pod; and an entry from `describe_file` for a caller
file that is no caller record.

## Validation at the first commit

| Command | Result |
|---|---|
| `uv run --locked python -m pytest tests/testing/test_experiment_evidence_layout.py -q` | 159 passed, 2 skipped, of 79 test functions |
| `uv run --locked python -m pytest tests/testing/test_test_inventory.py tests/contracts/test_experiment_run_v1alpha1.py tests/testing/test_experiment_evidence_layout.py tests/security -q -x` | 2,875 passed, 2 skipped |
| `uv run --locked python -m pytest tests/testing/test_document_links.py tests/testing/test_test_strategy.py tests/testing/test_test_inventory.py -q` | 2,136 passed |
| `uv run --locked python -m tools.experiment_evidence repository` | Exit 0. Three `pre-schema` lines, and `runs       3: 3 pre-schema and not checked, 0 conforming, 0 refused` |
| `uv run --locked python -m tools.experiment_evidence digests docs/proof/experiments/v2-e01/runs/20261006-e01-d-1` | Exit 0. 11 lines. Each digest is the one that the committed review record of that run states for the file |
| `uv run --locked python -m tools.experiment_run repository` | Exit 0. `manifests  3: 3 pre-schema, 0 conforming, 0 refused` |
| `uv run --locked python -m tools.evidence_index --check` | `OK`. The committed index is what the register and the ledgers produce |
| `uv run --locked python -m tools.evidence_index --gate` | Exit 0. Evidence set `549946af...cbefcc` and evidence pack `06e214dc...3d0720`. This change edits no file that either digest is taken over |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_freeze --changes <record>` for revisions 2 and 3 | 17 and 30 material files differ. The same command on the base commit, with this change stashed, printed the same two counts. This change moves no material file |
| `uv run --locked python -m tools.experiment_e01 --check` | `PASSED: 2 run(s), each agrees with its own evidence` |
| `uv run --locked ruff check .` and `uv run --locked python -m mypy` | All checks passed. No issues found in 392 source files |
| `uv run --locked python -m tools.ci_gates expected-failures` | Exit 0. 63 controls produced the exit status that the repository requires of them |
| `git diff --cached --check` | No output |
| `uv run --locked python -m pytest -q` | **Started on the tree of the first commit and stopped before it ended.** At about 6 percent it had printed two failures, and it was stopped when the reviews were read, because the tree was about to change. **The two failures were real, and this change caused them:** see [the default lane](#the-default-lane-found-a-defect-that-the-reviews-did-not). The first commit therefore has two failing tests in the default lane |

## What the independent reviews found

Two reviews read the first commit. Each was an automated session that had not written
the change. One read the code and built inputs against it. One compared each sentence of
the pages with the code. Neither edited a file. The second commit corrects what follows.

### What the code got wrong

| Finding | Correction |
|---|---|
| **A credential after a JSON line break passed the prefix rule.** The rule read the start of each word, and a backslash ended a word. In a JSON string, a line break is a backslash and a letter, so the letter stood before the prefix. A transcript in a `.jsonl` file has this form | The rule reads the text again with each escape of a JSON string replaced. 3 cases |
| **A credential in a URL, after a slash, or after `$`, `&`, or a byte order mark passed the prefix rule** | The rule reads a prefix after any character that is not a letter or a digit. 7 cases. It now refuses an ordinary name that starts with a prefix, and the suite measures that. A prefix after a percent escape still passes, and the suite measures that too |
| **A user directory with no separator after the account name passed the path rule.** So did `users` in lower case, and a name with a space or a letter outside ASCII | The rule needs no separator after the name and ignores letter case. 6 cases, and one URL that it now refuses |
| **A deeply nested freeze record raised an error that no rule names.** The `check` command exited 4, and the `repository` command failed for the whole tree | The record is read with the reader of a run manifest, which refuses it. That reader also refuses a member stated twice, and the revision must be an integer. 6 cases |
| **A caller file that a correction adds was not read as a caller record** | The caller rules hold a file with that role wherever it is named |
| **A file in a `runs` or `corrections` directory was not seen, and a corrections directory of a run that is a file was read as absent** | The `repository` command refuses the first two, and the check refuses the third |
| **A Windows directory junction was read as a directory.** A run directory could hold files outside the tree through one, and a junction to a run directory was listed as a second run | A junction is a link to the check, and a link is not followed. The rule is `evidence-entry-is-a-link`: the first commit named it `evidence-file-not-regular` |
| **A correction could add a file named `run.v1alpha1.json`.** The check passed it, and the `repository` command then listed that file as the manifest of a second run. A manifest could name such a file in a subdirectory with the same effect | No evidence file has that name |
| **The corrections directory of a run was opened by path.** Under another letter case it was read on this host and not on a host that tells case apart | Its name is compared as text |
| **A correction could not correct a file that an earlier correction adds** | It can, by the path `correction-<k>/<path>` |
| **`describe_file` opened a file under a name in another letter case, raised a type error for a role that is no text, and its docstring said that the check would not refuse what it returned** | The name is compared as text, the role is refused, and the docstring states what the helper does not read |
| **`digests` printed in an order that differs by host, printed a digest for a file that a text rule refuses, and exited 0 for a path that names no directory** | The order is that of the paths as text. Both other cases are findings |
| **The review gate's reader took `metadata.spec` first with no word on a manifest that has both members** | The gate refuses such a manifest |
| A statement of white space alone, a correction number above 9999, and one corrected path named twice were accepted | The form refuses each |

### What the pages got wrong

| Finding | Correction |
|---|---|
| **The page said that the prefix rule was measured on each proof file that is not a Markdown page, and that none held a prefix. One does**, and the test left out a directory | The test reads each such file, and the page names the one file |
| **The page said that a correction pins the manifest and that the chain refuses an edit.** Both hold only while the correction itself is unchanged | The page says so, and three tests measure a run and its corrections replaced together |
| **"No rule reads a statement of a correction"**, beside two text rules that read it | "For its meaning" |
| **The caller rule's statement** named the release without "or none", and did not name the profile digest or the case of a manifest with no caller profile | The statement has each |
| **"One tree has one verdict on each host"** | The page lists the names that are compared as text, and one directory that is opened by the path given |
| **"The check lists them and does not check them"**, of the three earlier run directories. That is the `repository` command. The `check` command refuses one | Both are stated, and the second has a test |
| **"Each directory that the suite checks is built by the suite"** | One committed directory is read, and the pages say so |
| **"Five" statements of the contract now held.** Four are of the list that the sentence names. The fifth is a measured gap | Four, and one gap |
| **"Files that each executed run so far has held"**, of three added roles. Two of the three run directories hold no environment file | Decision 4 names which directory holds which |
| **"It is the digest of the content that Git stores"** | True for a file that Git treats as text. The page states the other case and the one pin of `.gitattributes` |
| **"No collector of endpoint, pod ... readings exists yet"**. Tools of this repository read such things for their own records | "No tool writes a file with a raw role of this layout" |
| **"That the freeze record is registered"**, under a heading that said no code checks it. The freeze check holds a record under the usual file name to the registry | The item says which records the freeze check holds |
| **The allowlist said that gitleaks reports no finding in the new suite.** gitleaks was not run | The entry says that it was not run |
| This record: "five passages" for six, "one line changed" for two, "three commands" beside one command, a file "that Git would ignore" which this repository does not ignore, a link to the wrong section, a sentence on a document that is not in this repository, and a test named for provoking each rule that reads the source for a name | Each is corrected. The test is named for what it does |
| The first commit's message says "caller record of the same ... release" and "One function of the result review gate changes" | Not corrected: a commit message is not rewritten. This record and the changelog state both as they are |

### The default lane found a defect that the reviews did not

`tests/architecture/test_argocd_bootstrap.py` lists the build files that may name the
delivery controller's product, and it refuses a file outside the list. The first commit
described the role `argo` with the product's name, in `tools/experiment_evidence/core.py`.
So two tests of that module failed: one that holds the list for the bootstrap record, and
one that holds it for the serving path. Neither review ran that module, and neither found
this.

**The first reading of the failures was wrong.** The default lane that was started on the
first commit printed two failures at about 6 percent. The three Argo CD modules were then
run alone, and that command was read as passing: it ran past its time limit, and its
exit status was the exit status of the command that cut its output, not of the tests. An
earlier draft of this record said that the failures were not reproduced. The default lane
on the corrected tree printed the same two failures by name, and that draft was
corrected.

| Finding | Correction |
|---|---|
| **The tool's code named the delivery controller's product**, which a suite of the architecture permits in five build files and no sixth | The description of the role says "the delivery controller's Application". The role is still `argo`. The list of the suite is unchanged |

### What the reviews did not find, and what was not reviewed

Neither review found a refusal that repeats text of a file, a link that does not resolve,
or a count of the page that the code does not give, except the counts above. Neither
found the defect that the default lane found. **The second
commit was not reviewed by an independent session.** Its corrections were made by the
session that wrote the first commit.

## Validation at the second commit

| Command | Result |
|---|---|
| `uv run --locked python -m pytest tests/testing/test_experiment_evidence_layout.py -q` | 215 passed, 2 skipped |
| `uv run --locked python -m tools.experiment_evidence repository` | Exit 0. The same four lines as at the first commit |
| `uv run --locked python -m tools.experiment_evidence check docs/proof/experiments/v2-e01/runs/20261006-e01-d-1` | Exit 3. `evidence-manifest-refused` |
| `uv run --locked python -m tools.evidence_index --check`, `--gate` | `OK`, and exit 0 with the same two digests |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_e01 --check` | `PASSED: 2 run(s), each agrees with its own evidence` |
| `uv run --locked ruff format --check .` | 715 files already formatted |
| `uv run --locked ruff check .` | All checks passed |
| `uv run --locked python -m mypy` | No issues found in 392 source files |
| `uv run --locked python -m tools.ci_gates expected-failures` | Exit 0. 63 controls |
| `git diff --check` | No output |
| `uv run --locked python -m pytest -q`, first run on the corrected tree | 2 failed, 20,995 passed, 42 skipped, 14 deselected by the default marker expression, in 53 min 39 s. The two failures are those of [the default lane](#the-default-lane-found-a-defect-that-the-reviews-did-not) |
| `uv run --locked python -m pytest tests/architecture/test_argocd_bootstrap.py -q`, after the correction | 101 passed |
| `uv run --locked python -m pytest -q`, second run, on the final tree | 20,997 passed, 0 failed, 42 skipped, 14 deselected by the default marker expression, in 46 min 40 s. The tree is the tree of the second commit but for this row |

### The hosted type check failed on the second commit

The hosted workflow ran on the pull request after the push. Its job for format, lint,
and types failed at `python -m mypy`, with two errors in the suite of this change: the
test of a directory junction called a function that the type stubs define for Windows
only. On the Windows host of this change the same command found no issue, and no command
of this record checked the types for another platform. So the two rows above that state
"No issues found" were true of one platform.

A third commit corrects it. The call is in a helper that reads `sys.platform`, which the
type checker reads too. No rule, no page of the layout, and no other test changed.

| Command, at the third commit | Result |
|---|---|
| `uv run --locked python -m mypy` | No issues found in 392 source files |
| `uv run --locked python -m mypy --platform linux` | No issues found in 392 source files |
| `uv run --locked ruff format --check .` and `uv run --locked ruff check .` | 715 files already formatted. All checks passed |
| `uv run --locked python -m pytest tests/testing/test_experiment_evidence_layout.py -q` | 215 passed, 2 skipped |

The default lane was not run again for the third commit. It changes one test and this
record. The hosted workflow runs the lane on the pull request.

### The skipped tests

Three tests of the suite skip by host. On this host two skip: one creates a symbolic
link, which this host does not let the suite create, and one creates a file whose name
holds a line break, which this host's file system does not hold. The third creates a
Windows directory junction, and it ran here: so on this host a link was refused through a
real junction, and a symbolic link only through a replaced answer of the host for one
file name. A fourth test gives a name with a line break to the function that prints it,
on every host.

**Not run.** No cluster was contacted, no image was built, and no model was read.
gitleaks is not installed on this host and was not run. The hosted workflows did not run
on this branch before the push. No test under the `cluster`, `realruntime`, `failure`, or
`load` marker ran: the default marker expression deselects them, and this change bears on
none.

## What the evidence establishes

- At C0, the committed check refuses each case of the table above and accepts each
  control.
- The layout's digest of a text file is the evidence index's digest of it, for each file
  that the suite compares.
- The layout page states each rule and each role as the module does.

## What the evidence does not establish

- That a run executed. No run directory of the layout exists.
- That the layout holds what a real run needs. No run wrote a directory of it, and no
  tool wrote a file with a raw role other than `caller`.
- That a file of a run directory was committed, or that a run directory and its
  corrections were not replaced together. The check reads one tree and not Git.
- That a derived file follows from the raw files beside it.
- That a file holds no secret and no personal path. The two text rules read a prefix and
  a path form, and the page lists forms that each does not read.
- That the result review gate accepts a ledger for a run of this layout. The suite gives
  the gate's check of one review record a run of this layout. No ledger bears on such a
  run.
- That the check gives one verdict on a host that tells letter case apart. Every test
  ran on one Windows host.
- Runtime behaviour of any kind. A C0 record does not establish that a release serves,
  that a fault was survived, or that a caller saw an answer.
