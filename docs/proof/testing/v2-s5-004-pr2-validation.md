# V2-S5-004-PR2 validation

Status: **the analysis of an experiment run can be bound to the digests of its
evidence files and computed again. The tool is checked at evidence level C0,
against run directories that the suite builds from synthetic files. No run was
analysed, the proof tree holds no run directory of the published layout, no
figure was compared with a bound, and no claim was registered or changed.**

| Property | Value |
|---|---|
| Date | 2026-10-13 |
| Base | `580c62b`, the merge of pull request #142 |
| Branch | `test/v2-s5-004-analysis-replay` |
| Commits | The first commit, `1264e54`: the tool, the suite, the example, the gate of the evidence index, and the pages. The second commit: the corrections of two independent reviews, and the record of them in this file |
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
  134 tests from 95 test functions. The first commit held 110 from 78.
- [One synthetic tree](../../../tests/testing/fixtures/analysis-replay) of 9
  files, as a replay example: a freeze record that freezes no experiment, and
  one run directory of 8 files, which are a manifest, six evidence files, and
  the run analysis.
- [The replay page](../../testing/analysis-replay.md), with the document, the
  steps of a replay, what a replay refuses, the rules of the aggregate, the
  gate of the evidence index, the limits, and what a run analysis does not
  establish. The table of the rules and the lists of statements are held to
  the constants of the tool by the suite.
- The contributor guide, the README, one architecture table, the changelog, the
  index of the testing pages, the index of the proof records, the page of the
  evidence index, and the test inventory each gain an entry. Three pages that
  said that nothing reads a run directory or a manifest for analysis now name
  the tool: the reliability analysis page, the evidence layout page, and the
  ExperimentRun page. One cell of the index of the contracts, and two notes of
  the test inventory, said the same and were reworded. They do not name the
  tool.
- The suite of the test inventory gains the number word for 91. The suite of
  the evidence layout has one docstring reworded, and the command of the
  evidence index has one sentence added to its docstring.

**One existing tool changed: the evidence index.** No other tool changed. The
reliability analysis is not edited, so its document, its six committed cases,
and its page tables are as `V2-S5-004-PR1` left them. No chart, manifest,
contract schema, script, or freeze record was changed. Two pages about a
contract were edited. The vocabulary of the
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
| The analysis revision is recorded | Reached at C0, in two forms. The commit identifier is read from Git, and the command refuses while a source file is not the file of that commit. The source digest is taken over the Python files of seven packages. **The commit of no committed document is a real one**: each document of the suite and the example state a placeholder, and the suite compares a commit with Git in a temporary repository. One document with the commit `1264e54` was printed and replayed by hand, as the section on what was not done states |
| Evidence that was changed is detected | Reached at C0. A changed file is refused by the layout check. A file and its digest in the manifest, changed together, are refused by the digest that the document states |
| Evidence that is absent is detected | Reached at C0. An absent file is refused by the layout check. A stream removed from the run and from the manifest is refused by the inputs that the document states. A caller record removed in that way is refused by the analysis, which requires it |
| The all-run rule and the median rule are documented | Reached. The page states six rules of the aggregate, the tool states them in each aggregate document, and the suite holds the two to each other |
| Integration with the evidence index, with no automatic promotion of a claim | Reached at C0. The build of the index refuses a run whose analysis does not replay. It adds no entry, no claim, no status, and no level. **No committed run reaches the new check**: the three committed runs name no analysis, so the gate has refused only run directories that the suite builds |
| A summary that was edited by hand is not authoritative | Reached at C0. Seven hand edits of a stored document are each refused with the manifest changed to match, an open episode that was given a duration and a changed reason included, and one with the manifest left as it was |

### The criteria of the parent change

| Criterion | State after this change |
|---|---|
| The analysis computes the failure episode, the maximum success gap, the zero-Ready interval, the detection lag, the false-healthy and false-unavailable time, and the stabilization exactly | Reached at C0 by `V2-S5-004-PR1`, on synthetic files. This change computes no figure of its own. It holds a run analysis to the committed analysis of each of the six cases, byte for byte |
| The analysis replays from raw evidence and records the code revision | Reached at C0, on synthetic run directories. The proof tree holds no run directory of the published layout, so no analysis of a run was replayed |
| The aggregation of a small sample follows the registered rules | Reached at C0 for the rules that the tool can check: each run is listed, no run of the experiment is left out, a counted run is not dropped, an excluded run stays visible, and the median is for three counted runs. **Not reached:** no rule holds the reason of an exclusion to one that was registered before the run, and no rule covers an experiment of two runs |
| Data that is missing or inconclusive does not become a result | Reached at C0. A run with no caller record has no run analysis. A counted run with no value, and a counted run with no run analysis, leave the aggregate with no median. A stored document that gives an open episode a duration is refused |

The parent change has three evidence obligations. The analysis tests and the
edge tests are those of `V2-S5-004-PR1` and of this suite. The replay example
is the committed run directory, and it is synthetic.

## What was not done

- **No run was analysed.** The proof tree holds three run directories of real
  runs. Each was written before the schema, none names an analysis, and the
  tool replays none. So each property here is shown on files that the suite
  builds.
- **The declaration is held to no frozen record.** No frozen record of an
  experiment states a window, an expected state, or a signal. A document with
  another declaration, computed again, replays. A test states that.
- **No committed document states a real commit.** Before the first commit,
  `bind` on the example refused with `replay-code-not-committed`, as the rule
  states: the source files of the tool were not committed. After the first
  commit, `bind` on the example printed a document that states `1264e54`. A
  copy of the example tree outside the repository, with that document in
  place of the committed one, replayed with `revision  held`. That document is
  not committed, and the run was by hand. The suite compares a commit with Git
  in a temporary repository.
- **The aggregate and the gate of the evidence index compare no commit with
  Git.** The commands `verify` and `repository` do.
- **The gate of the evidence index reads the role of a file and not its
  content.** A run analysis under the role `result` is not held.
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
  covers seven packages. Seven packages that a source file imports are outside
  it: the layout check, the validator of the manifest, the evidence index, and
  four that the caller profile imports. A test reads the imports of each
  source file and states the seven. It does not read the imports of those
  seven in turn.

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
| A reason cannot be changed | The reason `episode-open` of a stored document is replaced by another registered reason. Refused |
| A raw file that the analysis does not read is bound | A transcript is added to the run and to the manifest. The raw evidence digest moved, and the replay refuses with `replay-evidence-differs` |
| A refusal repeats no value of a stored declaration | A stored declaration with a signal identifier that holds a number, and an unregistered source. The refusal names the rule of the analysis, and the number is not in it |
| A refusal holds no path of a host | A run directory outside the root is shown by its name |
| A bare document of the reliability analysis is not a run analysis | The committed analysis of a case, stored under the role `analysis`, is refused with `replay-record-unreadable` |
| The source digest is the digest of the rows | Nine other forms of the analysis code are each refused |
| A document of another code is stated as such | One source row is changed. The replay holds, states `differs`, and names the file. With one figure also changed, the replay refuses and states the number of files |
| A commit is not trusted without Git | A clone that does not hold the commit gives `not-checked`. A commit whose file differs gives `replay-revision-differs`. So does a commit that holds a Python file beside a stated one. The identifier of a tag is not checked as a commit |
| The commit of a checkout is not read from the status of Git alone | A file that Git ignores, and a changed file that Git is told to leave out of its status, each leave the status empty, and each refuses the commit |
| A source file has one form on each host | A file named `Shadow.PY` is not a source file. A file with a hyphen in its name gives no code, because no document can state its path |
| A run is not left out of an aggregate | A fourth run directory of the experiment that was not given refuses the aggregate, and the refusal names the directory |
| A run is not left out by the spelling of an argument | The third run is given as a path through one of its own directories and back. The fourth run is still required |
| A run is not left out by its manifest alone | The manifest of the fourth run states another experiment, and nothing else is changed. The layout check refuses that directory, and the aggregate refuses |
| An aggregate states the code of each figure | One run analysis with another source row and another commit is listed with `differs` and that commit |
| A counted run with no value is not dropped | Three counted runs, one with an open episode, give no median with the reason `counted-run-without-value`. So does a counted run with no run analysis |
| The run with the worst figure is counted | Three runs with 0 ms, 3,000 ms, and 20,900 ms. Each is counted, the two `FAILED` runs included, and the median is 3,000 ms |
| An excluded run stays visible | An `ABORTED` run is listed with its exclusion and is not counted |
| The state of a run is the one of its manifest | The command has no option for a state, and the suite gives each run its state in its manifest alone |
| The gate of the index refuses, and it promotes nothing | A ledger that bears on a run whose stored figure was changed raises. The committed index is what the register and the ledgers produce, and it holds no text of a run analysis. Three modes of the command of the index print `MISMATCH` and exit 1 when the gate raises |
| The gate is not passed by another spelling | The role written as `Analysis`, with a space after it, and in capitals is each held. Six forms of the `evidence` member that state no role for each file are each a refusal |
| A run analysis has no member for a claim, a level, or a result | Each member name of a built document is read |
| The tool writes no file | The text of the three modules is read for six calls |

**Four controls that do not hold.** A test states each.

- A run directory, its manifest, and its run analysis, replaced together,
  replay. The replay reads one tree and not Git.
- A changed declaration that is computed again replays.
- A document whose source rows were changed by hand, with the source digest
  computed again, replays and is stated as a document of another code. The
  comparison with Git refuses it only in a clone that holds the stated commit.
- A run analysis whose figure was changed, stored under the role `result`,
  conforms to the layout, and the gate of the evidence index does not read it.

## Validation at the first commit

Each command ran on the files of the first commit, on the host above. Each ran
before the commit was made, except where a row says otherwise.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 746 files already formatted |
| `uv run --locked python -m mypy` | No issue in 414 source files |
| `uv run --locked python -m mypy --platform linux` | No issue in 414 source files |
| `uv run --locked python -m pytest tests/testing/test_analysis_replay.py -q` | 110 passed |
| `uv run --locked python -m pytest tests/testing tests/security tests/contracts/test_experiment_run_v1alpha1.py tests/domain/test_reliability_analysis.py tests/domain/test_renderer_input_boundary.py tests/architecture/test_argocd_bootstrap.py -q` | 10,394 passed, 3 skipped. **This run was before the files of the change were staged.** The link suite reads tracked files only, so it did not read the two new pages. With them the selection collects 10,399 tests |
| `uv run --locked python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 30 material files differ. `V2-S5-004-PR1` recorded the same number |
| `uv run --locked python -m tools.experiment_evidence repository` | 3 run directories, each pre-schema and not checked. No change |
| `uv run --locked python -m tools.analysis_replay repository` | 3 run directories, each pre-schema and not replayed, 0 with no analysis, 0 replayed, 0 refused |
| `uv run --locked python -m tools.analysis_replay verify` of the example, with its `--root` | `replayed`, 6 input files, `code same`, and `revision  not-checked` |
| `uv run --locked python -m tools.analysis_replay bind` of the example, with its `--root` | Before the commit: exit status 3, `replay-code-not-committed`. After it: exit status 0, and a document that states `1264e54` and 19 source rows |
| `python tests/testing/test_analysis_replay.py`, and then the suite | The example is written again, and the suite passes |
| `git diff --cached --check` | No whitespace error |

The default lane was not run at the first commit.

## What the independent reviews found

Two reviews read the first commit, `1264e54`. Each was an automated session
that was given the repository and no conclusion. One executed inputs against
the code, with its own scripts outside the repository. The other compared each
sentence of the pages, of this record, and of the suite with the code. Neither
is a review by a person.

### What the code got wrong

- **An aggregate could leave a run out by the spelling of an argument.** The
  first commit listed the parent of the last path as it was written. With the
  third run given as a path through one of its own directories and back, the
  tool listed that run directory in place of the runs directory. A fourth run
  of the experiment was left out, the document stated a median of three, and
  the exit status was 0. The runs directory is now read at its place under the
  root. Two other spellings raised an error that no rule names, and each is now
  a refusal.
- **An aggregate could leave a run out by its manifest alone.** A run that was
  not given was read for its experiment from a manifest that validates. The
  manifest of the worst run, with another experiment and no other change, was
  passed as a run of that experiment. A directory that is not given must now
  conform to the layout, and the layout check holds a caller record to the
  experiment of its manifest.
- **The commit of a checkout was read from the status of Git alone.** A file
  that Git ignores, and a changed file that Git is told to leave out of its
  status, left the status empty. `bind` then printed a document that stated the
  commit. The command now compares each source file with the content that the
  commit holds.
- **A commit was held to the stated rows only.** A document that stated some of
  the files of a package was reported as `revision  held`. The commit must now
  hold no other Python file in the directory of a stated row. The identifier of
  a tag was accepted as a commit, and it is not now.
- **A refusal repeated a value of a stored declaration.** The message of the
  reliability analysis quotes the identifier of a signal, and the first commit
  repeated that message. A refusal now names the rule of that tool alone. The
  build of the evidence index printed the same text.
- **A refusal could print a path of a host.** A run directory outside the root
  was shown by its whole path. It is now shown by its name.
- **A name in another script stopped the output.** The command printed the name
  as it was, and a console of another encoding raised an error. The output is
  now ASCII.
- **The gate of the index compared the role as text.** `Analysis`, and
  `analysis` with a space after it, passed the gate. So did an `evidence`
  member of another form, and a manifest that was a directory. Each is now held
  or refused.
- **`bind` could print a document that a replay refuses.** A source file with a
  hyphen in its name has a path that the form of a source row does not accept.
  The tool now refuses to state such a code. A file named with the suffix in
  capitals was a source file on a host that ignores letter case and not on
  another. It is now a source file on neither.
- **The source packages left out the caller profile.** The reader of a caller
  record holds a header to `tools/reliability_profile`. The package is now the
  seventh source package.
- **An aggregate stated the code of the command as if it were the code of each
  figure.** Each row now states the commit and the source digest of its own run
  analysis, and whether the present source files are those.

### What the tests got wrong

- The test of the source packages read the direct imports of two files, and its
  docstring said that it stated what the digest does not cover. It now reads
  the imports of each source file. It found four packages that the first commit
  named nowhere.
- No test read a reason, a raw file that the analysis does not read, the
  `repository` command on a tree with a run of this layout, or the command of
  the evidence index with a gate that refuses. Each has a test now.
- The helper that reads imports did not read `from tools import name`. It does
  now.

### What the pages got wrong

- **"No run directory of a real run exists" was false.** The proof tree holds
  three run directories of real runs, one at C2. Each was written before the
  schema. The sentence was in the page, the changelog, this record, the layout
  page, the ExperimentRun page, and the test inventory. Each now says that the
  proof tree holds no run directory of the published layout.
- **The first commit added a run directory of the layout and left four
  sentences that said that none exists.** The layout page, the index of the
  testing pages, one note of the test inventory, and one docstring now say
  where the one fixture is.
- **Four rows of the table of what a replay refuses named a rule that is not
  the one that refuses.** Two rows left out that the digest in the manifest
  was changed to match. Two rows named `replay-evidence-differs` for a change
  that the analysis refuses first.
- **The recorded count of the selection was not that of the commit.** The run
  was before the files were staged, and the link suite reads tracked files. The
  row now says so.
- This record said that four pages now name the tool. Three do.
- This record said that the run directory of the example has 9 files. It has 8,
  and the tree has 9.
- The page said that a refusal has a fixed message. A message can hold a count,
  a role, a run identifier, and the name of a directory.
- The page did not say that the aggregate compares no commit with Git, or that
  the analysis inside a run analysis states a limitation that is about that
  member alone.
- The test inventory said that each hand edit is refused with the manifest left
  as it was. One is tested in that way.

### Noted, and not changed

- A run whose manifest is changed from `FAILED` to `INCONCLUSIVE`, with a
  reason, is no longer counted. The manifest is the authority for the state,
  and no rule holds the reason to one that was registered before the run. The
  aggregate states the digest of each manifest, and no check holds a stored
  aggregate.
- The gate of the index does not hold a run directory that the layout check
  refuses and that names no analysis. The gate holds an analysis.
- An aggregate replays each run and then reads it again. A file that changes
  between the two reads is not detected.
- The printed block of the example on the page is held by no test.

## Validation at the second commit

Each command ran on the files of the second commit, on the host above, before
the commit was made.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 746 files already formatted |
| `uv run --locked python -m mypy` | No issue in 414 source files |
| `uv run --locked python -m mypy --platform linux` | No issue in 414 source files |
| `uv run --locked python -m pytest tests/testing/test_analysis_replay.py -q` | 134 passed. The first commit held 110 |
| `uv run --locked python -m pytest tests/testing tests/security tests/contracts/test_experiment_run_v1alpha1.py tests/domain/test_reliability_analysis.py tests/domain/test_renderer_input_boundary.py tests/architecture/test_argocd_bootstrap.py -q` | 10,420 passed, 3 skipped. The first commit collects 10,399 |
| `uv run --locked python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.analysis_replay repository` | 3 run directories, each pre-schema and not replayed |
| `uv run --locked python -m tools.analysis_replay verify` of the example, with its `--root` | `replayed`, 6 input files, `code same`, and `revision  not-checked` |
| The scripts of the first review, run again | The two aggregates that left a run out are refused. The ignored file and the file left out of the status refuse the commit. The refusal of a declaration names a rule and no value |
| `python tests/testing/test_analysis_replay.py`, and then the suite | The example is written again with the source rows of this commit, and the suite passes |
| `git diff --check` against the base | No whitespace error |

The run analysis of the example changed in the second commit: its source rows
went from 19 to 22, and two of the 19 have another digest. No figure of it
changed, and no evidence file of the example changed.

## The default lane

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q` | 22,172 passed, 42 skipped, 14 deselected, no failure, in 53 minutes |

The lane ran once, on the files of the second commit, before this table held
its result. The reasons of the skipped tests were not read.

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
- `gitleaks` is not installed on this host, so no secret scan ran here. No
  pull request exists yet, and its scan has not run.

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
- That a stated commit computed a document. Each committed document states a
  placeholder commit.
- That a declaration is the one that an experiment froze.
- That a run directory was not replaced as a whole, with its manifest and its
  run analysis.
- The result of a run, an availability figure, or a production SLO.
- A claim. A run analysis that replays certifies nothing.
