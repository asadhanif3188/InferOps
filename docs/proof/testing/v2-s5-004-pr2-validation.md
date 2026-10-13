# V2-S5-004-PR2 validation

Status: **the analysis of an experiment run can be bound to the digests of its
evidence files and computed again. The tool is checked at evidence level C0,
against run directories that the suite builds from synthetic files. No run was
analysed, no run directory of a real run exists, no figure was compared with a
bound, and no claim was registered or changed.**

| Property | Value |
|---|---|
| Date | 2026-10-13 |
| Base | `580c62b`, the merge of pull request #142 |
| Branch | `test/v2-s5-004-analysis-replay` |
| Host | One Windows workstation, Git Bash; Python 3.12.12 from `uv`. `gitleaks` is not installed |
| Evidence level | C0. Every check reads committed files or reads a file that the suite built. No check contacts a cluster, a caller, or a telemetry collector |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, or freeze record was added or changed. The committed evidence index is unchanged, and its two digests are unchanged |

## What changed

- [`tools/analysis_replay`](../../../tools/analysis_replay/__init__.py) reads a
  run directory and prints one run analysis: the reliability analysis, the
  digest of each input, the raw evidence digest, the declaration, and the code
  that computed the document. A second command computes each stored run
  analysis of a run directory again and compares the bytes. A third prints one
  figure of each run of one experiment and the median of three counted runs,
  with each result state read from its manifest.
- [`tools/evidence_index`](../../../tools/evidence_index/core.py) gains one
  function, `analysis_gate`, and its build calls it. The build refuses a run
  that a ledger bears on when the run names a run analysis that does not
  replay. The function adds nothing to the index.
- [`tests/testing/test_analysis_replay.py`](../../../tests/testing/test_analysis_replay.py),
  110 tests from 78 test functions.
- [One synthetic run directory](../../../tests/testing/fixtures/analysis-replay)
  of 9 files, as a replay example: a freeze record that freezes no experiment,
  a manifest, six evidence files, and the run analysis.
- [The replay page](../../testing/analysis-replay.md), with the document, the
  steps of a replay, what a replay refuses, the rules of the aggregate, the
  gate of the evidence index, the limits, and what a run analysis does not
  establish. The table of the rules and the lists of statements are held to
  the constants of the tool by the suite.
- The contributor guide, the README, one architecture table, the changelog, the
  index of the testing pages, the index of the proof records, the page of the
  evidence index, and the test inventory each gain an entry. Four pages that
  said that nothing reads a run directory or a manifest for analysis now name
  the tool: the reliability analysis page, the evidence layout page, the
  ExperimentRun page, and the index of the contracts. Two notes of the test
  inventory that said the same now say that no tool read a manifest or a run
  directory of a run.

**One existing tool changed: the evidence index.** No other tool changed. The
reliability analysis is not edited, so its document, its six committed cases,
and its page tables are as `V2-S5-004-PR1` left them. No chart, manifest,
schema, contract, script, or freeze record was changed. The vocabulary of the
evidence layout already held the derived role `analysis`, so no role was
added. The ExperimentRun schema is not changed.

**How the run directories of the suite are made.** The evidence files are the
committed files of the six cases of the reliability analysis, which that suite
builds from invented requests and objects. The manifest is the committed valid
fixture `fault-injected-passed.json` with other identifiers, times, and
evidence entries. The freeze record is one line that states a revision and
freezes no experiment. The suite computes each run analysis with the tool, with
a placeholder commit.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| A command that reads an ExperimentRun and raw evidence and computes a result summary | Reached at C0. `bind` reads the manifest of a run directory, holds the directory to the layout check, reads the one file of each of six raw roles, and prints a run analysis. The summary is the figures. It holds no result state: the manifest states that |
| The digests of the inputs are recorded | Reached at C0. The document states the path and the digest of each input as the manifest states them, and the raw evidence digest of the layout check over each raw file of the run |
| The analysis revision is recorded | Reached at C0, in two forms. The commit identifier is read from Git, and the command refuses while a source file is not the file of that commit. The source digest is taken over the Python files of six packages. **The commit of no built document is a real one**: each document of the suite states a placeholder, and the comparison of a commit with Git ran in a temporary repository only |
| Evidence that was changed is detected | Reached at C0. A changed file is refused by the layout check. A file and its digest in the manifest, changed together, are refused by the digest that the document states |
| Evidence that is absent is detected | Reached at C0. An absent file is refused by the layout check. A file removed from the run and from the manifest is refused by the inputs that the document states |
| The all-run rule and the median rule are documented | Reached. The page states six rules of the aggregate, the tool states them in each aggregate document, and the suite holds the two to each other |
| Integration with the evidence index, with no automatic promotion of a claim | Reached at C0. The build of the index refuses a run whose analysis does not replay. It adds no entry, no claim, no status, and no level. **No committed run reaches the new check**: the three committed runs name no analysis, so the gate has refused only run directories that the suite builds |
| A summary that was edited by hand is not authoritative | Reached at C0. Six hand edits of a stored document are each refused with the manifest changed to match, an open episode that was given a duration included, and one with the manifest left as it was |

### The criteria of the parent change

| Criterion | State after this change |
|---|---|
| The analysis computes the failure episode, the maximum success gap, the zero-Ready interval, the detection lag, the false-healthy and false-unavailable time, and the stabilization exactly | Reached at C0 by `V2-S5-004-PR1`, on synthetic files. This change computes no figure of its own. It holds a run analysis to the committed analysis of each of the six cases, byte for byte |
| The analysis replays from raw evidence and records the code revision | Reached at C0, on synthetic run directories. No run directory of a run exists, so no analysis of a run was replayed |
| The aggregation of a small sample follows the registered rules | Reached at C0 for the rules that the tool can check: each run is listed, no run of the experiment is left out, a counted run is not dropped, an excluded run stays visible, and the median is for three counted runs. **Not reached:** no rule holds the reason of an exclusion to one that was registered before the run, and no rule covers an experiment of two runs |
| Data that is missing or inconclusive does not become a result | Reached at C0. A run with no caller record has no run analysis. A counted run with no value, and a counted run with no run analysis, leave the aggregate with no median. A stored document that gives an open episode a duration is refused |

The parent change has three evidence obligations. The analysis tests and the
edge tests are those of `V2-S5-004-PR1` and of this suite. The replay example
is the committed run directory, and it is synthetic.

## What was not done

- **No run was analysed.** No run directory of a real run exists, so each
  property here is shown on files that the suite builds.
- **The declaration is held to no frozen record.** No frozen record of an
  experiment states a window, an expected state, or a signal. A document with
  another declaration, computed again, replays. A test states that.
- **The stated commit of a built document was compared with Git in a
  temporary repository only.** The commands `bind` and `aggregate` were not
  run to the end in this repository at the first commit: the source files of
  the tool were not yet committed, and `bind` refused with
  `replay-code-not-committed`, as the rule states.
- **The layout check does not call the tool.** A run directory with a run
  analysis that does not replay conforms to the layout.
- **No continuous-integration job runs the `repository` command.** The suite
  runs it, in the default lane.
- **A stored aggregate document is held by no check.**
- **The aggregate does not compare the declarations or the windows of its
  runs.**
- **A correction of a run is not read.**
- **The result page of a run is not computed again.** The role `result` is
  written by a person.
- **The source digest does not cover each module that the code imports.** It
  covers six packages. The layout check, the validator of the manifest, and
  the digest function of the evidence index are outside it, and a test states
  the three.

## Decisions taken in this change

Each of these is a choice that the requirement did not fix.

1. **A new tool, and the reliability analysis is not edited.** The document of
   that tool states no digest, and a run analysis holds it as one member. So
   the six committed cases did not change.
2. **The declaration is a member of the run analysis.** A replay needs the
   declaration. The layout has no role for it, and a run directory is closed.
   So the document holds it, and a replay takes no declaration as an argument.
   No role was added.
3. **The document does not state the digest of the manifest.** The manifest
   states the digest of the document. The document states the raw evidence
   digest and the digest of each input.
4. **The code has a commit and a source digest.** A commit alone cannot be
   compared in a clone that does not hold it. A digest alone names no place to
   read the code.
5. **The command reads the commit, and no option states it.** It refuses while
   a source file is changed, added, or not tracked.
6. **A document of another code replays when the present code gives the same
   bytes.** The other choice refuses each committed run analysis after each
   edit of a source file. The output states that the code differs and names
   each file.
7. **An input is the one file of a role.** Two files with one role that the
   analysis reads are refused, and the tool does not choose between them.
8. **`verify` exits 3 for a run directory that names no run analysis.** A
   script that reads the exit status then does not read "replayed" for a run
   that has nothing to replay. The gate of the index does not refuse such a
   run.
9. **The all-run rule is held by the runs directory.** The aggregate reads each
   directory beside the given ones and refuses a run of the experiment that
   was not given.
10. **A counted run with no run analysis is counted and has no value.** It is
    not left out, so the aggregate then has no median.
11. **The gate of the index holds an analysis and requires none.** A run that
    names no analysis is not refused. The gate adds no member to the index, so
    the committed index did not change.
12. **The example is outside the proof tree.** A run directory under
    `docs/proof/experiments` would be listed as a run. The example states a
    placeholder commit, and it is not written again when a source file changes.

## The negative controls

Each row is a property and the case that would show it is false.

| Property | Control |
|---|---|
| A figure that was changed by hand is refused | The episode figure of a stored document is lowered by 1 ms, and the digest in the manifest is changed to match. The layout check accepts the directory, and the replay refuses with `replay-document-differs` |
| An open episode cannot be given a duration | The stored document of `open-episode` states 60,000 ms in place of no value. Refused |
| A metric with no value cannot be removed from the list | `withoutValue` is emptied. Refused |
| A statement cannot be removed | The last limitation is removed. Refused. A new member is refused too |
| The declared window and a declared threshold are bound to the figures | Each is changed in the stored document alone. Refused, because the figures are those of the earlier declaration |
| The form of the file is bound | The same members with other white space are refused |
| A hand edit with the manifest left as it was is refused | The layout check refuses the directory with `evidence-file-digest-differs`, and the replay states `replay-run-directory-refused` |
| An evidence file that changed is refused | One value of the caller record that no figure reads is changed. Refused at the layout check |
| An evidence file that is absent is refused | The endpoints stream is removed. Refused at the layout check |
| A file and its digest in the manifest, changed together, are refused | The layout check accepts the pair. The replay refuses with `replay-evidence-differs` |
| Digests that were patched by hand do not make the figures true | The argo stream is removed from the run and the manifest, and the three evidence members of the document are changed to match. Refused with `replay-document-differs` |
| A document of another run is refused | Four members of the document are each changed |
| A bare document of the reliability analysis is not a run analysis | The committed analysis of a case, stored under the role `analysis`, is refused with `replay-record-unreadable` |
| The source digest is the digest of the rows | Nine other forms of the analysis code are each refused |
| A document of another code is stated as such | One source row is changed. The replay holds, states `differs`, and names the file. With one figure also changed, the replay refuses and states the number of files |
| A commit is not trusted without Git | A clone that does not hold the commit gives `not-checked`. A commit whose file differs gives `replay-revision-differs` |
| A run is not left out of an aggregate | A fourth run directory of the experiment that was not given refuses the aggregate, and the refusal names the directory |
| A counted run with no value is not dropped | Three counted runs, one with an open episode, give no median with the reason `counted-run-without-value`. So does a counted run with no run analysis |
| The run with the worst figure is counted | Three runs with 0 ms, 3,000 ms, and 20,900 ms. Each is counted, the two `FAILED` runs included, and the median is 3,000 ms |
| An excluded run stays visible | An `ABORTED` run is listed with its exclusion and is not counted |
| The state of a run is the one of its manifest | The command has no option for a state, and the suite gives each run its state in its manifest alone |
| The gate of the index refuses, and it promotes nothing | A ledger that bears on a run whose stored figure was changed raises. The committed index is what the register and the ledgers produce, and it holds no text of a run analysis |
| A run analysis has no member for a claim, a level, or a result | Each member name of a built document is read |
| The tool writes no file | The text of the three modules is read for six calls |

**Three controls that do not hold.** A test states each.

- A run directory, its manifest, and its run analysis, replaced together,
  replay. The replay reads one tree and not Git.
- A changed declaration that is computed again replays.
- A document whose source rows were changed by hand, with the source digest
  computed again, replays and is stated as a document of another code. The
  comparison with Git refuses it only in a clone that holds the stated commit.

## Validation at the first commit

Each command ran on the tree of the first commit, on the host above.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 746 files already formatted |
| `uv run --locked python -m mypy` | No issue in 414 source files |
| `uv run --locked python -m mypy --platform linux` | No issue in 414 source files |
| `uv run --locked python -m pytest tests/testing/test_analysis_replay.py -q` | 110 passed |
| `uv run --locked python -m pytest tests/testing tests/security tests/contracts/test_experiment_run_v1alpha1.py tests/domain/test_reliability_analysis.py tests/domain/test_renderer_input_boundary.py tests/architecture/test_argocd_bootstrap.py -q` | 10,394 passed, 3 skipped |
| `uv run --locked python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 30 material files differ. `V2-S5-004-PR1` recorded the same number |
| `uv run --locked python -m tools.experiment_evidence repository` | 3 run directories, each pre-schema and not checked. No change |
| `uv run --locked python -m tools.analysis_replay repository` | 3 run directories, each pre-schema and not replayed, 0 with no analysis, 0 replayed, 0 refused |
| `uv run --locked python -m tools.analysis_replay verify` of the example, with its `--root` | `replayed`, 6 input files, `code same`, and `revision  not-checked` |
| `uv run --locked python -m tools.analysis_replay bind` of the example, with its `--root` | Exit status 3, `replay-code-not-committed`. The source files of the tool were not committed yet |
| `python tests/testing/test_analysis_replay.py`, and then the suite | The example is written again, and the suite passes |
| `git diff --cached --check` | No whitespace error |

The default lane was not run at the first commit.

## Privacy and publicability

- No file of this change holds a credential, a prompt, a completion, a model
  file, a path of a personal directory, or the name of a person.
- The six evidence files of the example are copies of the committed files of
  one case of the reliability analysis. The suite holds each to the digest of
  that file. The caller record states `promptText` and `completionText` as
  false.
- The manifest of the example is a committed fixture with placeholder
  identities, and its first limitation says that no run executed.
- A run analysis holds the paths of the source files under `tools/`, the paths
  of the evidence files of its run, and digests. It holds no path of a host.
- The layout check reads each file of the example with its two text rules, and
  it refuses none.
- `gitleaks` is not installed on this host, so no secret scan ran here. The
  scan of the pull request is the check.

## What the evidence establishes

The evidence is static, at level C0.

**It establishes:**

- For run directories that the suite builds, the tool gives a document that
  holds the committed analysis of each of the six cases, and a replay
  reproduces the document byte for byte, on a checkout with CRLF too.
- For each case in the table of negative controls, a stored document or a run
  directory that was changed is refused, and the refusal names a rule.
- The aggregate lists each run, reads each state from a manifest, and states a
  median for exactly three counted runs with a value each.
- The build of the evidence index refuses a run directory whose run analysis
  does not replay, and the committed index is unchanged.

**It does not establish:**

- Any figure of a real run. No run was analysed, and no run directory of a run
  was replayed.
- That a stated commit computed a document. Each built document states a
  placeholder commit.
- That a declaration is the one that an experiment froze.
- That a run directory was not replaced as a whole, with its manifest and its
  run analysis.
- The result of a run, an availability figure, or a production SLO.
- A claim. A run analysis that replays certifies nothing.
