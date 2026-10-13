# The replay of an experiment analysis

Status: **the tool is implemented, and run directories that the test suite builds show the binding, each refusal, and the replay at evidence level C0. No run was analysed. One synthetic run directory with its run analysis is committed as an example, outside the proof tree. The proof tree holds no run directory of the published layout: its three run directories were written before the schema, and none names an analysis. No claim is registered, and no claim status changed.**

[The reliability analysis](reliability-analysis.md) computes the figures of one
run from files that a command names. Its document states no digest of an input
and no revision of the code. A person can change a figure in a stored document,
and nothing computes the document again.

`tools/analysis_replay` closes that. It reads one
[run directory](experiment-evidence-layout.md): the
[ExperimentRun manifest](../contracts/experiment-run.md) and the raw evidence
files that the manifest names. It computes the reliability analysis and prints
one **run analysis**: the analysis, the digest of each input, the declaration,
and the code that computed the document. A **replay** computes a stored run
analysis again and compares the two byte for byte.

**A stored document is not authoritative. The replay is.** Each run analysis
states this: A replay computes this document from the manifest, the evidence
files, and the declaration below. A copy that a replay does not reproduce byte
for byte is not an analysis of the run.

**The tool computes figures and decides no result.** A run analysis states no
result state, no verdict, no claim status, and no evidence level. A document
that replays registers no claim.

## A run analysis

The schema name is `inferops.io/run-analysis/v1alpha1`. A run analysis is stored
in the run directory under the role `analysis`, with the suffix `.json`, and the
manifest names it as it names each evidence file.

| Member | What it holds |
|---|---|
| `experimentId`, `runId` | The two identifiers of the manifest |
| `runDirectory` | The run directory, as a path from the root of the repository |
| `rawEvidence` | The raw evidence digest of the layout check, and the number of raw files |
| `inputs` | For each evidence file that the analysis read: the name of the input, the path, and the digest that the manifest states |
| `notGiven` | Each input of the analysis that the run names no file for |
| `declaration` | The declaration that was given, as the analysis read it |
| `analysisCode` | The commit identifier, the source digest, and one row for each source file |
| `analysis` | The document of the reliability analysis |
| `authority` | The statement above |
| `limitations`, `doesNotEstablish` | The lists below |

- **An input is the file of a role.** The six inputs of the analysis have the
  names of six raw roles: `caller`, `endpoints`, `pods`, `deployments`, `argo`,
  and `operator-events`. The tool reads the one file that the manifest names
  with each role. Two files with one such role are refused. A role with no file
  is `not-given`, and each metric that reads it has no value. A run with no
  caller record has no run analysis.
- **A digest is the digest of the layout.** It is the SHA-256 of the content of
  a file with each CRLF replaced by LF. The tool reads each evidence file in
  that form, so a Windows checkout gives the same document.
- **The raw evidence digest covers each raw file of the run.** It covers a raw
  file that the analysis does not read. A run analysis is a derived file, so
  adding it to a run does not move that digest.
- **The analysis inside is the document of the reliability analysis, as that
  tool prints it.** One of its limitations says that the document states no
  digest of an input and no revision of the code. That sentence is about the
  `analysis` member alone. The run analysis around it states both.
- **The declaration is a part of the document.** A replay reads it from the
  document and takes no declaration as an argument. The declaration must name
  the experiment and the run of the manifest.
- **The document does not state the digest of the manifest.** The manifest
  states the digest of the document, and one of the two has to be written
  first.

## The analysis code

A run analysis states the code in two forms.

- **The source digest** is taken over the Python files of seven packages:
  `tools/analysis_replay`, `tools/experiment_events`,
  `tools/experiment_timeline`, `tools/reliability_analysis`,
  `tools/reliability_profile`, `tools/reliability_runner`, and
  `tools/service_endpoint_state`. They are this tool, the analysis, the reader
  of each input, the caller profile that the reader of a caller record holds
  a header to, and the tier names that those share. A source file is a file
  whose name ends with `.py` in lower case. `sources` states the path and the
  digest of each file, and `sourceSha256` is the SHA-256 over the sorted lines
  `<sha256>  <path>`.
- **The commit identifier** is the commit of the checkout that ran the command.
  The command reads it from Git and takes no option that states it. It refuses
  to print a document while a source file does not have the content that the
  commit holds for it, or while the commit holds another Python file in a
  source package. It compares the files with the commit, file by file. It does
  not rely on the status of Git alone, which leaves out a file that Git
  ignores and a file that Git is told not to compare.

**The source digest does not cover each package that a source file imports.**
Eight are outside it, and a change to one of them does not move the digest:

- `tools/experiment_evidence`, the layout check, `tools/experiment_run`, the
  validator of the manifest and the result states, and `tools/evidence_index`,
  the digest function. This tool reads the three.
- `tools/experiment_freeze`, the reader of the freeze registry. The aggregate
  reads the registry for a run that is not counted.
- `tools/llm_load`, `tools/model_acquisition`, `tools/runtime_configuration`,
  and `tools/runtime_packaging`, which the caller profile imports.

The suite reads the imports of each source file and holds this list to them.
It does not read the imports of the eight packages in turn.

## A replay

`python -m tools.analysis_replay verify <run directory>` does this, in order.

1. **The layout check.** The run directory must conform to the
   [evidence layout](experiment-evidence-layout.md). An evidence file that
   changed, an evidence file that is absent, and a file that the manifest does
   not name each refuse the replay here, and no figure is computed.
2. **The stored document.** Each file with the role `analysis` must be one JSON
   object with the schema name of a run analysis, with a declaration, and with
   an analysis code in its form.
3. **The computation.** The tool computes the run analysis again from the
   manifest, the evidence files, and the declaration of the stored document. It
   takes the analysis code from the stored document.
4. **The evidence of the document.** The identifiers, the run directory, the raw
   evidence digest, the inputs, and the inputs that are not given must be those
   that the manifest gives now.
5. **The bytes.** The stored text must be the computed text, byte for byte,
   after each CRLF is replaced by LF.
6. **The source files.** The tool compares the source rows of the document with
   the files that are present. The output states `code same` or
   `code differs`, and it names each file that differs.
7. **The commit.** When the clone holds the stated commit, each source file must
   have its stated digest at that commit, and the commit must hold no other
   Python file in the directory of a stated row. When the clone does not hold
   the commit, the output states `revision  not-checked`. The identifier of a
   tag is not a commit, and it is not checked.

The function `replay_run` does steps 1 to 6. The commands `verify` and
`repository` add step 7. The gate of the evidence index and the `aggregate`
command do not: neither compares a commit with Git.

**What a replay refuses.** Step 3 runs before step 4. So a change that the
reliability analysis itself refuses is stated as `replay-analysis-refused`,
whatever else it changed.

| Change | Refused by |
|---|---|
| A figure, a reason, or a list of the analysis is changed in the stored file | `replay-run-directory-refused`, because the file no longer has the digest of the manifest |
| The same change, with the digest in the manifest changed to match | `replay-document-differs` |
| A limitation is removed, a member is added, or the file is written in another form, with the digest in the manifest changed to match | `replay-document-differs` |
| The declared window or a declared threshold is changed in the stored file, with the digest in the manifest changed to match | `replay-document-differs`, because the figures are those of the earlier declaration |
| An evidence file is changed or is absent | `replay-run-directory-refused` |
| An evidence file and its digest in the manifest are changed together | `replay-evidence-differs`, or `replay-analysis-refused` when the reader of the file no longer accepts it |
| An evidence file is removed from the run and from the manifest | `replay-evidence-differs`, or `replay-analysis-refused` when the file is the caller record |
| A raw file that the analysis does not read is added to the run and to the manifest | `replay-evidence-differs`, because the raw evidence digest moved |
| The digests of the document are changed to match such a run, and the figures are not | `replay-document-differs` |
| The source digest is not the digest of the source rows | `replay-record-form-unsupported` |
| A source file does not have its stated digest at the stated commit, or the document leaves out a Python file that the commit holds beside a stated one | `replay-revision-differs`, from `verify` and `repository`, in a clone that holds the commit |

**A document of another code.** A source file can change after a document was
written. The replay then computes with the code that is present. When that code
gives the stored bytes, the replay holds, and the output states
`code differs` with each file. When it does not, the replay refuses the
document, and the refusal states that source files differ. The replay does not
run the stated code. To do that, check out the stated commit and run the
command there.

## The aggregate of the runs of an experiment

`python -m tools.analysis_replay aggregate --metric NAME <run directory> ...`
prints one figure of each run and the median of three counted runs. The schema
name is `inferops.io/run-aggregate/v1alpha2`. The figures are computed by the
aggregate of [the reliability analysis](reliability-analysis.md#the-aggregate-of-three-runs),
and this command adds what that one does not check. The name was
`inferops.io/run-aggregate/v1alpha1` until `V2-S5-005-PR1`, which changed the
`exclusion` member of a run from text to an object. No document with the
earlier name is committed.

- Each run directory of the runs directory whose manifest names the experiment
  is given and is listed. No run is left out.
- The result state and the reason of each run are read from its manifest.
- A run in the state PASSED or FAILED is counted. A run that worsens the figure
  is not dropped.
- A run in the state INCONCLUSIVE, REFUSED, or ABORTED is not counted only when
  the reason of its manifest is, character for character, a reason that the
  freeze record of the manifest registers for the experiment, the result state,
  and the run, and the freeze registry of the tree pins that record. Otherwise
  the aggregate is refused. A result state alone leaves no run out.
- A run that is not counted is listed with its value, the reason of its
  manifest, the identifier of the registered reason, and the freeze record.
- A counted run with no run analysis, or with no value for the figure, leaves
  the aggregate with no median.
- The median is stated for exactly three counted runs. No confidence interval
  and no statistical significance is stated.

**The all-run rule.** The command reads each directory of the runs directory,
at its place under the root and not at the spelling of an argument. A
directory whose manifest names the experiment and that was not given is a
refusal. A directory that does not conform to the layout is a refusal too,
because its experiment is not known. The layout check holds a caller record
to the experiment of its manifest, so a run with a caller record is not left
out by another experiment in its manifest alone. A run directory of another
experiment that conforms is not required.

**Each run must replay.** A run directory that the layout check refuses, and a
run whose run analysis does not replay, refuse the aggregate. A run with two
run analyses is refused, because the aggregate reads one.

### A run that is not counted

**A result state alone leaves no run out.** Until `V2-S5-005-PR1` the aggregate
did not count a run in the state INCONCLUSIVE, REFUSED, or ABORTED, whatever
reason its manifest stated. The document stated `result-state-inconclusive` for
such a run, and it did not state the reason of the manifest. So one edit of a
manifest, from FAILED to INCONCLUSIVE with a reason written after the run, took
the run out of the median, and no document showed that reason. A review of the
sprint on 2026-10-13 reported this with a probe. It was reported to the author,
and no file in this repository records that review. The suite now runs the
probe.

The aggregate holds each such run to a reason that was registered before the
run. It does this in order.

1. **The freeze record.** The manifest names its freeze record by path, by
   revision, and by content digest. The layout check holds the record to the
   revision and the digest. The aggregate holds it to the freeze registry too:
   the file `docs/proof/experiments/registry.v1alpha1.json` under the root must
   pin that path with that digest. A record that the registry does not pin
   registers no reason.
2. **The exclusion reasons.** The record states them in the member
   `exclusionReasons`, an object with exactly two members. `experimentId` is the
   experiment identifier that the manifests of the runs state. `reasons` is a
   list of at most 32 reasons. A record with no such member registers no
   reason.
3. **The comparison.** The reason of the manifest must be, character for
   character, the `reason` of one entry whose `resultState` is the state of the
   run, in a record whose `experimentId` is the experiment of the run. When the
   entry states `runIds`, the run must be one of them.

A reason has these members, and no other.

| Member | Required | Statement |
|---|---|---|
| `id` | yes | An identifier of the reason, used once in the record. The aggregate repeats it |
| `resultState` | yes | `INCONCLUSIVE`, `REFUSED`, or `ABORTED`. A reason for `PASSED` or `FAILED` is refused |
| `reason` | yes | The text that a manifest must state: 1 to 2,000 characters, with no white space at its ends. One result state has one text once |
| `runIds` | no | The run identifiers that the reason is for, each once. With no such member the reason is for each run of the experiment |

The form, with a reason that is the reason of no experiment:

```json
"exclusionReasons": {
  "experimentId": "example-experiment",
  "reasons": [
    {
      "id": "example-reason",
      "resultState": "ABORTED",
      "reason": "An example reason. No experiment registers it."
    }
  ]
}
```

A run that is not counted is listed like this. The `preregistration` member is
how the manifest names the freeze record. Each run of the outer `runs` list,
counted or not, states the same three values of its own manifest.

```json
{
  "runId": "run-4",
  "resultState": "ABORTED",
  "counted": false,
  "exclusion": {
    "reasonId": "example-reason",
    "reason": "An example reason. No experiment registers it.",
    "preregistration": {
      "freezeRecord": "docs/proof/experiments/example/freeze-r1.v1alpha1.json",
      "freezeRevision": 1,
      "freezeContentSha256": "<the content digest of the record>"
    }
  },
  "value": null
}
```

| Change to a run that is not counted | Refused by |
|---|---|
| The manifest states a reason that the record does not register, or one that differs from the registered text by one character | `replay-exclusion-refused`, with `analysis-exclusion-unregistered` |
| The record has no `exclusionReasons` member, or the member registers the reason for another result state, for other runs, or for another experiment | `replay-exclusion-refused`, with `analysis-exclusion-unregistered` |
| The run answers a later revision of the record, and that revision does not register the reason | `replay-exclusion-refused`, with `analysis-exclusion-unregistered` |
| The member is not in its form | `replay-exclusion-refused`, with `analysis-exclusion-reasons-unsupported` |
| The tree has no registry that can be read, or the registry does not pin the record with the digest of the manifest | `replay-exclusion-record-unpinned` |
| The reason is added to the record after the run | `replay-aggregate-run-refused`, because the record no longer has the digest that each manifest states |
| The same, with the digest in each manifest changed to match | `replay-exclusion-record-unpinned` |
| The manifest states no reason | `replay-aggregate-run-refused`, because the manifest schema requires the reason and the layout check refuses the run |

**A run in the state PASSED or FAILED is counted, whatever reason its manifest
states.** No record is read for it, and a registered reason beside a counted
state leaves no run out.

**What the check does not do.**

- **It does not decide that the reason is true.** The manifest is the authority
  for the result state and for the reason. A person can change the manifest of
  a FAILED run to a state that is not counted, with a reason that the record
  registers. The aggregate accepts that manifest. It then states the reason,
  the record, and another manifest digest than before, so the change is in the
  document. The history of the manifest in Git and the review of the run hold
  the classification. This tool does not.
- **It reads one tree and not Git.** A freeze record, each manifest that names
  it, and the registry, replaced together, are accepted, and the aggregate then
  states another record digest. `python -m tools.experiment_freeze --check`
  holds each committed record to its pin, and the history of the registry is in
  Git.
- **The freeze check does not read the member.** A committed record with an
  `exclusionReasons` member that is not in its form passes the freeze check.
  The aggregate refuses it when a run that is not counted names it.
- **It compares text as it is.** Two texts that look the same and differ in a
  code point are two reasons.
- **It does not compare the freeze records of the runs.** Each run that is not
  counted is held to the record of its own manifest. The runs of one aggregate
  can name different revisions.
- **No committed freeze record states the member.** The three committed records
  are of E01, which has no numerical aggregate, and this change edits none of
  them. No experiment has registered an exclusion reason, and no run was left
  out of an aggregate of real runs.

An aggregate document lists, for each run, the digest of the manifest, how the
manifest names its freeze record, the raw
evidence digest, and the path and the digest of the run analysis. For each run
analysis it repeats the commit and the source digest that the run analysis
states, and it states `same` or `differs` for the source files that are
present. The `analysisCode` member of the aggregate is the code of the command
that printed the aggregate. It is not the code of a listed figure.

**The aggregate compares no commit with Git.** A run analysis that `verify`
refuses with `replay-revision-differs` is accepted here. Run `verify` on each
run directory for that check.

| Metric | Path in the analysis of a run analysis |
|---|---|
| `caller-failure-episode-ms` | `caller.failureEpisodes.callerFailureEpisodeMs` |
| `max-success-gap-ms` | `caller.maxSuccessGap.ms` |
| `requests-failed-in-window` | `caller.requests.failed` |
| `requests-failed-since-fault` | `stabilizedRecovery.requestsFailedSinceFault` |
| `stabilized-since-fault-started-ms` | `stabilizedRecovery.sinceFault.fromFaultStartedMs` |

**No check holds a stored aggregate document.** The layout gives it no place,
and no command reads one. To hold a stored copy, run the command again and
compare the two.

## The evidence index

[The evidence index](../proof/v1-evidence-index.md) is built from the claim and
evidence register and its ledgers. Since this change the build reads each run
directory that a register change of a ledger bears on.

- A run whose manifest names a file with the role `analysis` must replay. The
  index is not built while it does not, and each mode of
  `python -m tools.evidence_index` that builds the index prints `MISMATCH` and
  exits 1.
- A run whose manifest names no such file is not held. The gate requires no
  analysis. None of the three committed run directories names one.
- The gate reads the manifest as JSON for the role and does not validate it for
  that question. A manifest of another shape that names such a file must replay
  in full, and the layout check then refuses it. A role is read with its white
  space removed and in lower case, so `Analysis` does not pass the gate.
- A manifest whose `evidence` member is not a list of files with a role each
  is a refusal. A manifest with no `evidence` member names no file, and the
  three committed manifests are such manifests.
- The gate reads the role of a file and not its content. A document with the
  schema name of a run analysis under the role `result` is not held.
- The gate reads no Git object. It compares no commit.

**The gate refuses and promotes nothing.** A run analysis that replays adds no
claim, changes no claim status, and assigns no evidence level. The index
states nothing about a run analysis, and its two digests are unchanged. A claim
that rests on a figure is registered by a ledger, with a review artifact of the
run, as before.

## Rules of refusal

| Rule | Statement |
|---|---|
| `replay-run-directory-refused` | The layout check accepts the run directory: each file that the manifest names is present with its stated digest, and each file that is present is named. |
| `replay-input-ambiguous` | A run names at most one file with each role that the analysis reads. |
| `replay-declaration-identity-differs` | The declaration names the experiment and the run of the manifest. |
| `replay-analysis-refused` | The reliability analysis accepts the declaration and the evidence files of the run. The refusal names the rule of that tool. |
| `replay-analysis-missing` | A run directory that is given to be computed again names at least one file with the role analysis. |
| `replay-record-unreadable` | A file with the role analysis is one JSON object with no member stated twice, and it states the schema name of a run analysis. |
| `replay-record-form-unsupported` | A run analysis states its declaration as an object, and its analysis code as a commit identifier, a source digest, and source rows in their form. The source digest is the digest of the rows. |
| `replay-evidence-differs` | A run analysis states the experiment, the run, the run directory, the raw evidence digest, and the path and the digest of each input as the manifest of the run gives them. |
| `replay-document-differs` | A run analysis is, byte for byte, the document that the tool computes from the manifest, the evidence files, and the declaration that the document states. |
| `replay-revision-differs` | Each source file has, at the commit that a run analysis states, the digest that the run analysis states for it. |
| `replay-code-not-committed` | A document is computed by source files that are the files of the commit that it states. |
| `replay-aggregate-unsupported` | An aggregate is asked for a registered metric of run directories of one runs directory and one experiment, each given once, and each with at most one run analysis. |
| `replay-aggregate-run-omitted` | An aggregate is given each run directory of the runs directory whose manifest names the experiment, and each directory there that is not given conforms to the layout. |
| `replay-aggregate-run-refused` | Each run of an aggregate conforms to the layout, and its run analysis replays. |
| `replay-exclusion-record-unpinned` | The freeze registry of the tree pins the freeze record that the manifest of each run that is not counted names, with the content digest that the manifest states, and that record is one JSON object. |
| `replay-exclusion-refused` | The reliability analysis accepts the reason of each run that is not counted against the exclusion reasons of the freeze record that the manifest of the run names. The refusal names the rule of that tool. |

A refusal of `verify` and of `repository` names a rule, a path, and a message.
A refusal of `bind` and of `aggregate` names a rule and a message. A message
can hold a count, the name of a role, a run identifier, the name of a
directory, and the rule of another tool. A refusal of an exclusion also holds
the message of that rule, which names the run. It repeats no figure, no text of an
evidence file, no value of a declaration, and no reason of a manifest or of a
freeze record. A run directory outside the
root is shown by its name alone. A refusal of the layout check names each
rule of the layout that refused the directory.

| Exit status | Meaning |
|---|---|
| 0 | Nothing was refused. `bind` and `aggregate` printed a document. `verify` reproduced each run analysis of each given run directory |
| 2 | The arguments are not usable |
| 3 | A rule refused a run directory, a declaration, or a document. `verify` exits 3 with `replay-analysis-missing` for a run directory that names no run analysis. The `repository` command and the gate of the evidence index do not refuse such a run |

**Exit status 0 does not say that each metric has a value, and it does not say
that a run passed.**

## Limitations

- The declaration is a part of this document, and it is not held to a frozen
  record of an experiment. A document with another declaration replays as
  another analysis.
- The source digest covers the Python files of the registered source packages.
  It does not cover a module of another package that those files import, the
  interpreter, or a library.
- The commit identifier is the one that the command read from its checkout. A
  replay compares it with Git only when the commit is in the clone.
- A replay with source files that differ from the stated ones compares the
  document with what the present code computes. It does not run the stated
  code.
- A run directory, its manifest, and this document, replaced together, replay.
  A replay reads one tree and not Git.
- A replay reads the files that the manifest names. It reads no correction of
  the run.
- The document does not state the digest of the manifest, because the manifest
  states the digest of this document.

## What a run analysis does not establish

- That the evidence files are the evidence of a real run. A replay reads the
  files of a run directory.
- The result state of the run. The manifest states it, and no figure here is
  compared with a bound.
- A claim status or an evidence level. A document that replays registers no
  claim and certifies none.
- That the declared window, expected state, and signals are those that an
  experiment froze.
- That the stated commit is the code that computed the document, when the
  commit is not in the clone that replays it.

## The replay example

[`tests/testing/fixtures/analysis-replay`](../../tests/testing/fixtures/analysis-replay)
holds one tree with one run directory, at
`docs/proof/experiments/example-replay/runs/concurrency-1` under that root.

**The example is synthetic. No run produced it.** Its six evidence files are
the files of the `concurrency` case of
[the reliability analysis](reliability-analysis.md#the-six-cases), and the
suite holds each to the digest of that case. Its manifest is a fixture with
placeholder identities, and its freeze record freezes no experiment. The
example is outside `docs/proof/experiments`, so no run directory of the layout
exists in the proof tree.

```sh
uv run --locked python -m tools.analysis_replay verify \
  tests/testing/fixtures/analysis-replay/docs/proof/experiments/example-replay/runs/concurrency-1 \
  --root tests/testing/fixtures/analysis-replay
```

```text
replayed    docs/proof/experiments/example-replay/runs/concurrency-1/analysis.json  (6 input file(s), code same)
            revision  not-checked: the clone does not hold the stated commit, or Git is not available
```

- **The printed block is the output at the commit that wrote the example.** No
  test holds the words `code same`.
- **The stated commit is a placeholder.** A commit cannot name itself, so the
  example states forty times the letter `c`. No clone holds that commit, and
  the commit of the example is not compared.
- **The example states the source files of the commit that wrote it.** A later
  change to a source file does not change the example. The command then prints
  `code differs` and names the file, and the replay still holds while the
  present code gives the stored bytes. To write the example again with the
  present source files, run `python tests/testing/test_analysis_replay.py`.

## Commands

```sh
# Print the run analysis of one run directory.
uv run --locked python -m tools.analysis_replay bind RUN_DIRECTORY --declaration FILE
# Compute each run analysis of the run directories again.
uv run --locked python -m tools.analysis_replay verify RUN_DIRECTORY [RUN_DIRECTORY ...]
# Replay every run directory under docs/proof/experiments.
uv run --locked python -m tools.analysis_replay repository
# Print one figure of each run of one experiment, and the median of three.
uv run --locked python -m tools.analysis_replay aggregate --metric NAME RUN_DIRECTORY [RUN_DIRECTORY ...]
# Print the digest of each source file of the analysis code.
uv run --locked python -m tools.analysis_replay sources
```

`bind`, `verify`, `repository`, and `aggregate` take `--root`, the root of the
tree that holds `docs/proof/experiments`. `bind` and `aggregate` print one JSON document with
sorted members and LF line endings. No command writes a file: a person stores
the output of `bind` in the run directory and names it in the manifest.

`repository` prints `pre-schema` for a run directory whose manifest the
pre-schema register names, `no-analysis` for a run that names no run analysis,
`replayed` for each run analysis that was reproduced, and `REFUSED` otherwise.
In this change it prints three `pre-schema` lines and exits 0.

## What is not done

- No run was analysed. Each run directory of the suite is built by the suite.
- No frozen record of an experiment states a window, an expected state, or a
  signal, so no check holds a declaration to one. The tool does not compare the
  declaration with the manifest, except for the two identifiers.
- The layout check does not call this tool. A run directory with a run analysis
  that does not replay conforms to the layout. The `verify` command, the
  `repository` command, and the gate of the evidence index hold it.
- No continuous-integration job runs the `repository` command. The suite runs
  it, and the build of the evidence index reads the runs that a ledger bears
  on.
- A stored aggregate document is held by no check.
- The aggregate and the gate of the evidence index compare no commit with Git.
- The gate of the evidence index does not read a run analysis that is stored
  under another role than `analysis`.
- The comparison with Git reads the directories of the stated source rows. A
  document that leaves out a whole package is not refused by it.
- The aggregate does not compare the declarations or the windows of its runs.
- The aggregate holds the reason of a run that is not counted to the freeze
  record of its manifest. It does not decide that the reason is true of the
  run, it does not read Git for the history of a record or of a manifest, and
  it does not compare the freeze records of its runs. No committed freeze
  record registers an exclusion reason.
- The freeze check does not read the `exclusionReasons` member of a record.
- The replay reads no correction. A correction that adds a caller record or a
  run analysis is not replayed.
- The result page of a run, the role `result`, is written by a person. No tool
  computes it again.
- A replay does not run the code of the stated commit.

## Tests

[`tests/testing/test_analysis_replay.py`](../../tests/testing/test_analysis_replay.py)
builds run directories from the six committed cases of the reliability
analysis. It holds a run analysis to the committed analysis of each case, a
replay to each refusal that this page states, the aggregate to its rules, and
the gate of the evidence index to a run that does not replay. It reads the text
of the tool for a call that writes a file, and it compares the rules, the
limitations, the boundaries, and the aggregate rules on this page with the
tool's. It runs the probe that showed that a result state alone left a run
out, and it holds an exclusion to each refusal that this page states.
[The validation record](../proof/testing/v2-s5-004-pr2-validation.md)
states what was run for the tool, and
[a second record](../proof/testing/v2-s5-005-pr1-validation.md) states what
was run for the exclusion reasons.
