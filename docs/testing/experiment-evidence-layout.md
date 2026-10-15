# Experiment evidence layout

Status: **published layout with an offline check**, added by `V2-S5-002-PR2`. The layout,
its rules, its role vocabulary, its correction form, and a tool that checks a run
directory are published here and checked on every change. **Two run directories of
this layout exist, and neither is of a result-bearing run.** Since `V2-S5-006-PR1` the
proof tree holds the two attempts of
[a non-result integration validation](../proof/experiments/README.md#the-sprint-5-integration-validation).
Scripts run by hand assembled both, and they are not committed. No tool writes a run
directory. (Until `V2-S5-006-PR1` this page said that no run directory of this layout
exists and that no run produced one.) Each run directory that the
suite checks is built by the suite, with a synthetic caller record and placeholder
identities, except one copy of a committed run directory, which is refused at its
manifest, and the two attempts, which its listing reads in place. Its listing also reads
in place the Q1 qualification `q1-1`, which is not a run directory of this layout (see
[the Q1 qualifications](#the-q1-qualifications)). The three other run directories that are committed were written before the
[ExperimentRun schema](../contracts/experiment-run.md).
[The compatibility section](#the-three-earlier-run-directories) says how they are held.
(Since `V2-S5-004-PR2` one synthetic run directory of this layout is committed as a test fixture,
under `tests/testing/fixtures/analysis-replay`.
It is outside the proof tree, and no run produced it.) Each sentence of this page that says that no run
directory of this layout exists is about the proof tree.

| Property | Value |
|---|---|
| Proof tree | `docs/proof/experiments/` |
| Run directory | `docs/proof/experiments/<experiment>/runs/<runId>/` |
| Manifest | `run.v1alpha1.json`, an [ExperimentRun](../contracts/experiment-run.md) |
| Corrections directory of a run | `docs/proof/experiments/<experiment>/corrections/<runId>/` |
| Digest | SHA-256 of a file's content with each CRLF replaced by LF |
| Evidence file suffixes | `.csv`, `.json`, `.jsonl`, `.md`, `.txt`, `.yaml`, `.yml` |
| Roles | 14: 12 raw and 2 derived |
| Rules | 21 |
| Tool | [`tools/experiment_evidence`](../../tools/experiment_evidence/core.py) |
| Suite | [`tests/testing/test_experiment_evidence_layout.py`](../../tests/testing/test_experiment_evidence_layout.py) |

**Three terms.** A *run directory* is the directory of one run. *The check* is what
`tools/experiment_evidence` applies to one run directory. The `check` command applies it
to the directories it is given. The `repository` command applies it to each run directory
of the proof tree that the pre-schema register does not name and that is not a
[Q1 qualification](#the-q1-qualifications).

## What it is for

An [ExperimentRun](../contracts/experiment-run.md) names each evidence file of a run by
role, path, and digest. Its validator reads the manifest and opens no evidence file. So a
manifest can validate when a file it names is absent, or has another content.

This layout says where a run directory is, which files it holds, and how each file is
hashed. The check opens the files. It holds a run directory to its manifest in both
directions: each file that the manifest names is present with its stated digest, and
each file that is present is named.

A reader of a result can then recompute each digest with a tool that this repository did
not write. `sha256sum` gives the same value for a file that holds no CRLF.

## The layout

```text
docs/proof/experiments/
+-- <experiment>/
    |-- freeze-r<N>.v1alpha1.json        the freeze record a manifest names
    |-- runs/
    |   +-- <runId>/
    |       |-- run.v1alpha1.json        the manifest
    |       |-- caller.jsonl             an evidence file the manifest names
    |       |-- pods.jsonl
    |       +-- result.md
    |-- reviews/                         review records. This layout does not change them
    +-- corrections/
        +-- <runId>/
            |-- correction-1.v1alpha1.json
            +-- correction-1/
                +-- result.md            a file the correction adds
```

- **The place of a run is fixed by its manifest.** The manifest names a freeze record.
  The run directory is `runs/<runId>` beside that record. The record is a file of one
  directory of `docs/proof/experiments/`. So one manifest has one place, and the check
  refuses a run directory in another place.
- **The name of the experiment directory is not fixed.** The layout does not derive it
  from `metadata.experimentId`. It is the directory of the freeze record.
- **The names of the evidence files are not fixed.** The tree above is an example. A
  file has the path that its manifest states. The role of a file says what it is, and
  the name does not. One name is refused: no evidence file is named `run.v1alpha1.json`,
  in any directory.
- **A run directory is closed.** Each file in it, at any depth, is the manifest or a file
  that the manifest names. The check does not read `.gitignore`: a file that Git would
  ignore is a file of the directory. An empty directory is not a file and is not
  refused.
- **A `runs` directory and a `corrections` directory hold directories.** A file in one of
  them is refused by the `repository` command.
- **No entry is a link.** A symbolic link and a Windows directory junction are refused
  and not followed.
- **A committed run directory is not edited.** A change to a run is a
  [correction](#corrections), outside the run directory.

## Hashing

A digest is the SHA-256 of a file's content with each CRLF replaced by LF, as 64
lowercase hexadecimal characters.

- **It is the digest of the evidence index.**
  [`tools/evidence_index`](../../tools/evidence_index/core.py) hashes a text file in this
  form, and the check calls that function. So a file of a run directory has one digest in
  the manifest, in a review record, and in [the evidence index](../proof/v1-evidence-index.md).
- **For a file that Git treats as text, it is the digest of the content that Git
  stores.** The repository stores such a file with LF, and a Windows checkout can hold
  it with CRLF. The digest does not move between the two, and the suite converts a run
  directory to CRLF to hold that. Git stores a file that holds a lone carriage return,
  or that Git reads as binary, byte for byte. For such a file that holds a CRLF, the
  digest is not the digest of the stored content. `.gitattributes` pins LF for the run
  directories of the experiment directory `v2-e01` and, since `V2-S5-006-PR1`, for every
  file of `v2-s5-integration`, and for no other. (Until `V2-S5-006-PR1` this item said
  that it pins LF for `v2-e01` only, and that this change does not edit it.)
- **An evidence file is text of a known suffix.** The index hashes seven suffixes as
  text and every other file byte for byte. A file under another suffix could have two
  digests on two hosts. So an evidence file must have one of the seven suffixes, be
  UTF-8, and hold no NUL character. An image, an archive, and a model artifact are
  refused.
- **A writer computes the digest with the same function.**
  `python -m tools.experiment_evidence digests <directory>` prints one
  `<sha256>  <path>` line for each file of a directory that can be an evidence file, and
  `describe_file` returns one `evidence.files` entry. A writer that hashes the raw bytes
  of a file that holds CRLF states a digest that the check refuses.

The ExperimentRun contract says that `evidence.files[].sha256` is the SHA-256 of the
file's bytes. For a file that holds no CRLF the two statements agree. For a file of a run
directory, this page states the digest.

### The two digests of a run

The check gives two digests for a run directory that conforms. Each is the evidence
index's set digest: the SHA-256 over the sorted lines `<sha256>  <repository path>`.

| Digest | Taken over |
|---|---|
| Raw evidence | The files with a raw role. A run that names no raw file has none. |
| Evidence set | The manifest and every evidence file. |

No correction is in either digest. **No document stores either digest.** A later record
that quotes one can be compared with the command's output. (Since `V2-S5-004-PR2`
[a run analysis](analysis-replay.md) states the raw evidence digest of its run, and
its replay compares the two.)

## Roles: raw and derived

Each evidence file has a registered role. The ExperimentRun schema holds no role
vocabulary, and this layout adds one for a file of a run directory.

| Role | Kind | What a file with the role holds |
|---|---|---|
| `caller` | raw | The caller's own record of its requests, as the reliability runner writes it. |
| `endpoints` | raw | Readings of the Service endpoints, each with its time. |
| `pods` | raw | Readings of the pods, each with its time. |
| `deployments` | raw | Readings of the Deployments, each with its time. |
| `argo` | raw | Readings of the delivery controller's Application, each with its time. |
| `telemetry` | raw | Readings of the metrics that the frozen record registers. |
| `resources` | raw | Readings of resource use, each with its time. |
| `operator-events` | raw | The events that the control of the run and an operator recorded, each with its time. |
| `transcript` | raw | What the commands printed, with each exit status. |
| `commands` | raw | The commands of the run, in order, or the driver. |
| `environment` | raw | The environment identity as the run read it. |
| `release` | raw | The release and its provenance as the run read them. |
| `analysis` | derived | Figures that are computed from raw files. |
| `result` | derived | The result page: each criterion and its verdict. |

- **A raw file is what a run read or wrote as it executed.** A derived file is computed
  or written from raw files.
- **A generated summary is downstream of raw evidence.** A run that names a derived file
  names at least one raw file. A result page with no raw file beside it is refused.
- **A corrected summary does not move the raw digest.** The raw digest is taken over the
  raw files alone.
- **A run can name several files with one role.** A run can name no file with a role. The
  layout requires no role and no file: a `REFUSED` run with no evidence file conforms.
  The ExperimentRun rules require a `caller` file for a `PASSED` or `FAILED` run under a
  caller profile.
- **The form of a raw file is not defined here, except for `caller`.** A file with a
  raw role other than `caller` is held to its form, its digest, and the two text rules,
  and it is not read for its meaning. The role table says what such a file holds, and no
  rule checks it. (Until `V2-S5-003-PR1` this paragraph also said that no tool writes a
  file with a raw role of this layout. Since that change
  [the timeline collector](../environment/experiment-timelines.md) writes a file for
  each of the roles `endpoints`, `pods`, `deployments`, and `argo`, from what its tool
  prints, and that tool defines and checks their form. This check does not call that
  tool. No run directory holds such a file. Since `V2-S5-003-PR2`
  [the telemetry collector script](../environment/experiment-telemetry.md) writes a file
  for each of the roles `telemetry` and `resources`, and
  [the operator event log](../environment/experiment-operator-events.md) is a file with
  the role `operator-events`. Each of the two tools defines and checks the form of its
  files, and this check calls neither. No run directory holds such a file. Since
  `V2-S5-006-PR1` each of the two attempts of the integration validation holds a file
  of each of these seven roles, and the sentences above that say that no run directory
  holds such a file no longer hold.)
- **The tool's code does not name the delivery controller's product.** The role is
  `argo`, and its description says "the delivery controller". A suite of the
  architecture refuses a sixth build file that names the product, and the first
  commit of this change was such a file. (Since `V2-S5-003-PR1` the suite admits a
  sixth file and refuses a seventh: the collector of the timelines names the product on
  the two lines that read the one Application.)
- **A role that is not in the table is refused.** A run that needs another role needs a
  change to the vocabulary. `V2-S5-003-PR2` made one such change: it added the raw role
  `operator-events`, and the vocabulary went from 13 roles to 14. Until then no role
  could name a log of operator events.
- **The pages follow the module.** Since `V2-S5-007-PR1` a test compares the role
  vocabulary of the module with four places: this table, the count row at the top
  of this page, the count in [the index of the testing pages](README.md), and
  [the ExperimentRun page](../contracts/experiment-run.md), which links to this
  table and states no number of roles. It refuses a missing, extra, duplicate,
  renamed, or reclassified role, a row out of the order of the module, and a count
  that differs. A change to the vocabulary must change these places in the same
  change. The test reads no other page, and it does not read a validation record.

### The caller record

A file with the role `caller` is read, whether the manifest or a correction names it. It
must be a caller record that
[the reliability runner's reader](../serving/reliability-runner.md) accepts. Its header
must name the experiment, the run, the caller profile with its revision and digest, and
the concurrency of the manifest. It must not be a rehearsal. The manifest must state a
caller profile. When the record declares a release identifier, the identifier is the
manifest's. A record whose plan declared no release names none, and the check then
compares none.

For a run directory whose manifest names a caller file, this closes one item that the
ExperimentRun contract lists as checked by nothing: that the two documents of a run name
one experiment and one run.

## Corrections

A committed run directory is evidence, and it is not edited. A correction is a new JSON
file beside the `runs` directory, at
`corrections/<runId>/correction-<n>.v1alpha1.json`. A file that a correction adds is at
`corrections/<runId>/correction-<n>/<path>`.

| Member | Form | Meaning |
|---|---|---|
| `schemaVersion` | `inferops.io/v1alpha1` | The version of this form. |
| `kind` | `ExperimentRunCorrection` | The document kind. |
| `experimentId` | String | The experiment of the run. It equals the manifest's. |
| `runId` | String | The run. It equals the manifest's. |
| `number` | Integer, 1 to 9999 | The number of the correction. It is the number in the file name, written with no leading zero. |
| `recordedAt` | UTC instant | When the correction was written. |
| `manifestSha256` | SHA-256 | The digest of the run's manifest. |
| `previousCorrectionSha256` | SHA-256 or `null` | The digest of the correction before this one. `null` for the first. |
| `corrects[]` | Path and SHA-256, one or more | Each file that the correction bears on, with its digest. No path twice. |
| `statements[]` | Statement, one or more | What is corrected, in prose of 1 to 2000 characters each, not white space alone. |
| `files[]` | Role, evidence path, SHA-256 | Each file that the correction adds. The list can be empty. No path twice. |

The eleven members are all required, and no other member is permitted. No JSON Schema
file defines the form. The tool holds it in code, as `tools/experiment_run` holds the
form of the pre-schema register.

- **A correction is additive.** It moves no file of the run directory and neither
  digest of the run.
- **A correction of an edited file is refused, while the correction is unchanged.**
  `corrects[]` states the digest of each file it bears on. A path of `corrects[]` is
  `run.v1alpha1.json`, an evidence path of the manifest, the file name of an earlier
  correction, or `correction-<k>/<path>` for a file that an earlier correction adds. The
  check compares each digest with the file that is present.
- **A correction states the digest of the manifest.** `manifestSha256` is compared with
  the manifest that is present. So a manifest that is replaced with new digests is
  refused, while the correction is unchanged.
- **Corrections are a chain.** They are numbered from 1 with no gap, and each one after
  the first states the digest of the one before it. An edit of an earlier correction is
  refused at the next one, while the next one is unchanged.
- **The chain is not a lock.** A run directory and each of its corrections, replaced
  together, conform. So does a run whose last correction, or whose corrections
  directory, is removed. [The measured gaps](#measured-gaps) state each.
- **The files that a correction adds are held as the files of a run are**: to the
  presence, form, digest, text, role, and caller rules. A file in the corrections
  directory of a run that no correction names is refused.
- **A correction does not change a result state.** The manifest keeps the state it
  states. No rule reads a statement of a correction for its meaning, and no tool applies
  a correction. The two text rules read a correction as text.
- **The review gate is not ended by a correction.** A review record states the digest of
  each file of a run directory. A correction is outside that directory.

## What a run directory must not hold

The layout requires no file. So it requires no file that holds a credential, a prompt, a
response body, or a path of a host. Two text rules read each evidence file and each
correction. They do not read the manifest: the ExperimentRun validator holds the manifest
to its own two rules.

- **No published prefix of a credential format, after a character that is not a letter
  or a digit.** The list of prefixes is the WorkloadContract validator's. The rule reads
  the text as it is, and again with each escape of a JSON string replaced, so a prefix
  after a line break that JSON wrote as a backslash and a letter is read.
- **No path under a user directory of a host.** The rule refuses a drive letter before
  `Users` or `home`, and `Users` or `home` after a separator and before a name, in any
  letter case. It follows the pattern of the security baseline suite and is wider: it
  needs no separator after the name, and it reads a separator that JSON wrote twice.
- **Both rules were measured on the committed proof files.** The corpus is each text
  file of `docs/proof/` that is not a Markdown page. No file holds a path under a user
  directory. One file holds a published prefix:
  `docs/proof/testing/v1-s5-012-pr2-migration.v1alpha1.json`, a ledger that names the
  prefix in a sentence. The suite holds both counts.
- **The shape heuristic of the ExperimentRun rules is not applied**, to an evidence file
  or to a correction. It refuses a long word in mixed case with a digit. Committed raw
  evidence holds identifiers and encoded values of that shape, and a rule that refuses
  them would require an edit of raw evidence.
- **No rule reads a file for a prompt or a response.** The reader of a caller record
  requires the header to state that the record holds no prompt text and no completion
  text, and it gives each line an exact set of members. A file with another role is not
  read for its meaning.
- **A refusal repeats no text of an evidence file or of a correction.** It states the
  rule, a path, and a fixed message. One message holds a count of findings, and one
  holds a rule identifier of the reliability runner.

## Rules

Each rule has an identifier. The output of a command names the rule and the path.

| Rule | Statement |
|---|---|
| `evidence-manifest-missing` | A run directory holds one run manifest, named run.v1alpha1.json. |
| `evidence-manifest-refused` | The manifest of a run directory validates as an ExperimentRun. |
| `evidence-run-directory-misplaced` | A run directory is named by its run identifier, in the runs directory beside the freeze record that its manifest names, and that record is a file of one directory of docs/proof/experiments. |
| `evidence-freeze-record-differs` | The freeze record that a manifest names is present, it is one JSON object with no member stated twice, and it has the integer revision and the content digest that the manifest states. |
| `evidence-file-missing` | Each evidence file that a manifest or a correction names is present. |
| `evidence-file-unlisted` | Each file of a run directory is the manifest or an evidence file that the manifest names, each file of the corrections directory of a run is a correction or a file that a correction names, and each entry of a runs directory and of a corrections directory is a directory. |
| `evidence-entry-is-a-link` | No entry of the proof tree that the check reads is a symbolic link or a directory junction. |
| `evidence-file-form-unsupported` | An evidence file is UTF-8 text with no NUL character, under a file suffix that the evidence index hashes as text, and it does not have the name of a run manifest. |
| `evidence-file-digest-differs` | The digest stated for an evidence file is the SHA-256 of the file's content with each CRLF replaced by LF. |
| `evidence-file-credential-prefix` | No evidence file and no correction holds the published prefix of a credential format after a character that is not a letter or a digit. |
| `evidence-file-personal-path` | No evidence file and no correction holds a path under a user directory of a host. |
| `evidence-role-unregistered` | Each evidence file has a registered role. |
| `evidence-summary-without-raw` | A run that names a derived file names at least one raw file. |
| `evidence-caller-record-refused` | A file with the role caller is a caller record that the reliability runner's reader accepts. |
| `evidence-caller-record-identity-differs` | A caller record names the experiment, the run, the caller profile with its revision and digest, and the concurrency of its manifest, it names the release of its manifest or none, it is not a rehearsal, and its manifest states a caller profile. |
| `evidence-correction-run-unknown` | A corrections directory of a run has the name of a run directory of this layout in the same experiment directory, and it is a directory. |
| `evidence-correction-unreadable` | A correction is one JSON object with exactly the registered members, each in its form. |
| `evidence-correction-number-out-of-sequence` | The corrections of a run are numbered from 1 with no gap, and the number in each correction is the number in its file name. |
| `evidence-correction-identity-differs` | A correction names the experiment, the run, and the present manifest digest of the run it corrects. |
| `evidence-correction-chain-broken` | The first correction of a run names no earlier one, and each later one states the content digest of the correction before it. |
| `evidence-correction-target-differs` | A correction names each file it corrects by its path and its present digest: the manifest, an evidence file of the manifest, an earlier correction, or a file that an earlier correction adds. |

**The order of the check.** A directory with no manifest gets one finding. A manifest
that the ExperimentRun validator refuses gets one finding, and the check reads nothing
else of the directory: the findings of the manifest are those of
`python -m tools.experiment_run check`. Every other rule of a run directory is applied to
a manifest that validates, and each finding is reported. The corrections of a run are
read only when the run directory is in its place.

**What the `repository` command adds.** It applies three statements that the check of one
run directory does not: an entry of a `runs` or `corrections` directory that is not a
directory, a link above a run directory, and a corrections directory of a run with the
name of no run directory of this layout. A corrections directory beside a run directory
that is refused gets no finding of its own. A directory of
`docs/proof/experiments/v2-q1/runs` is listed as a qualification and is not held to a
manifest: see [the Q1 qualifications](#the-q1-qualifications).

**The names are compared as text.** A file system that ignores letter case opens a file
under a name in another case. The check compares the name of the manifest, of each
evidence file, of each segment of the freeze record's path, of the `corrections`
directory, and of the corrections directory of the run with the names that a directory
lists. A directory named `Corrections` is not the `corrections` directory on any host,
and no rule refuses it. The check opens the run directory by the path it is given.

## Compatibility

### The ExperimentRun contract

The layout adds no member to the schema and changes no rule of its validator. A
manifest that validated before this change validates now.

The contract lists statements about a run that no code checked. For a run directory, the
check now holds four of them:

| Statement of the contract | Held by |
|---|---|
| An evidence file exists and has its stated digest. | `evidence-file-missing`, `evidence-file-digest-differs` |
| An evidence file that is present is listed. | `evidence-file-unlisted` |
| The freeze record exists, has the stated revision, and has the stated digest. | `evidence-freeze-record-differs` |
| The experiment and run identifiers equal those of the caller record. | `evidence-caller-record-identity-differs`, when a file with the role `caller` is named |

The check also refuses one manifest that the contract lists as a measured gap: a manifest
that names two evidence paths that one directory cannot hold. One of the two files is
absent.

`python -m tools.experiment_run check` still opens no evidence file. A manifest outside a
run directory, such as a fixture, is held to none of these.

**One role of the committed fixtures is not registered.** A valid fixture of the schema
names a file with the role `completion`. The schema holds no role vocabulary, so the
fixture validates. No fixture is a run directory, and the suite measures the difference.

### The evidence index and the result review gate

- **The digest is the index's.** The tool imports the index's function and its set of
  text suffixes. The suite holds that the suffix set is the same object, and that the
  two functions give one digest for each file it compares.
- **The run directory is where the review gate reads one.** The gate reads a run at
  `docs/proof/experiments/<experiment>/runs/<runId>/`, and a review record at
  `<experiment>/reviews/`. This layout puts a run in that place.
- **The gate reads the freeze record of a manifest in both shapes.** The gate compares
  the freeze record of a review with the one the run's manifest names. A manifest of the
  published schema names it in `metadata.spec.freezeRecord`. The three earlier manifests
  name it in `metadata.freezeRecord`. Before this change the gate read the second member
  only, and it would have refused a review of each run of the published schema. Now the
  gate reads `metadata.spec.freezeRecord` when `metadata` has a `spec` member, and
  `metadata.freezeRecord` when it has none. It refuses a manifest that has both.
- **The gate's verdicts are unchanged.** None of the three committed manifests has a
  `spec` member, so the gate reads the member it read before. The suite of the gate and
  `python -m tools.evidence_index --check` pass.
- **The index is not changed.** No evidence record, claim, or ledger was added. The
  index's two digests are unchanged.

### The three earlier run directories

Three run directories were committed before the ExperimentRun schema:
`20261002-e01-abc-1`, `20261003-e01-abc-1`, and `20261006-e01-d-1`, under
`docs/proof/experiments/v2-e01/runs/`.
[The pre-schema register](../contracts/experiment-run.md#compatibility-with-the-manifests-committed-before-the-schema)
names the manifest of each by path and content digest.

- **They are not edited and not moved.** They are in the place that this layout gives a
  run.
- **The `repository` command lists each as `pre-schema` and does not check it.** The
  schema refuses each manifest, so no rule of this layout can be applied to one.
- **The `check` command, given one of them, refuses it at its manifest and exits 3.** The
  suite holds that for the E01-D directory.
- **Three mechanisms that existed before this change still hold them.** The register
  holds each manifest to its digest. `python -m tools.experiment_e01 --check` judges the
  two static runs. The review gate holds the files of the second static run and of the
  E01-D run to the digests that their review records state.
- **This layout gives them no correction.** A corrections directory of a run with the
  name of one of them is refused. The dated notes of those runs are in
  [the experiments page](../proof/experiments/README.md), which this layout does not
  change.

### The Q1 qualifications

`docs/proof/experiments/v2-q1/runs/` holds the directories of
[Q1, the environment and identity qualification](../environment/environment-qualification.md).
A qualification is not a run of an experiment, and it has no ExperimentRun manifest.
Since `V2-S6-001-PR2`, which committed the first one, `q1-1`:

- **The `repository` command lists each directory with no manifest as
  `qualification`.** It requires the record, `record.v1alpha1.json`, applies the
  credential-prefix rule and the personal-path rule to each file, and refuses a link
  and a file that is unreadable, holds a NUL character, or is not UTF-8 text. It
  applies no other rule of this layout. It refuses a corrections directory with the
  name of a qualification. A directory there with a manifest is checked as a run.
- **`python -m tools.environment_qualification --check` holds each to its record.** It
  builds the record again from the directory and compares the bytes.
- **Only that one directory holds qualifications.** A directory with no manifest under
  the `runs` directory of any other experiment is refused at its manifest.

(Until `V2-S6-001-PR2` the `repository` command refused every directory of a `runs`
directory with no manifest, and it would have refused `q1-1` with
`evidence-manifest-missing`. Until then it also followed a link at the `runs` or the
`corrections` directory of an experiment; it now refuses the link and reads nothing
through it.)

## Measured gaps

The suite asserts each, so closing one is a visible change.

- **A file and its digest in the manifest, replaced together, conform.** The check reads
  one tree and not Git. With no correction, nothing that the check reads pins the
  manifest. A review record states the manifest's digest, and the result review gate
  reads that record. This check does not.
- **A run directory and its corrections, replaced together, conform.** So does a run
  whose earlier correction is edited and whose later correction is rewritten to match.
- **A run whose last correction, or whose corrections directory, is removed conforms.**
  Nothing in the tree states how many corrections a run has.
- **A corrections directory under another letter case is not read.**
- **A derived file that was not computed from the raw files conforms.** The rule asks
  for a raw file beside a derived file. No rule reads a derived file. (Since
  `V2-S5-004-PR2` [the replay of an analysis](analysis-replay.md) computes a run analysis
  again and refuses one that differs. This check does not call it, so a run
  directory with such a file still conforms.)
- **A raw file other than a caller record is not read for its meaning.** A file with the
  role `pods` that holds no reading of a pod conforms.
- **A secret with no published prefix passes.** So does a word of the shape that the
  ExperimentRun rules refuse in a statement, a published prefix directly after a letter
  or a digit, and so a prefix after a percent escape such as `%20`.
- **An ordinary name that starts with a published prefix is refused.** A path segment
  that starts with `hf_` and a word that starts with `sk-` after a space are refused. A
  writer must rename such a thing, or the file is not evidence of this layout.
- **A host path that is not under a user directory passes.** `/var/lib/...`, `/root/...`,
  and a drive path outside `Users` and `home` are not refused.
- **Some forms of a user directory pass.** A path written with `~`, with an environment
  variable, with percent escapes, with no separator before `home`, or with each
  backslash written four times is not refused. Nor is a user directory with no name
  after it.
- **A container path under a home directory is refused.** The rule cannot tell a path in
  a container from a path of a host. So is a URL whose host is `home`.
- **A request text passes.** No rule reads a file for a prompt or a response.
- **A caller record that declares no release is compared with none.**
- **The recorded time of a correction is compared with no other time.** It is held to
  its form and to a real calendar date.
- **An empty directory, an empty file, a byte order mark, and a lone carriage return are
  each in a run directory that conforms.**
- **`describe_file` returns an entry that the check can refuse.** The helper reads one
  file and knows no manifest. It does not read a caller record.

## Rules that nothing applies

Each of these is a statement about a run directory that this tool does not check. The
first names code elsewhere that checks a part of it. No code in this repository checks
the others.

- **That the freeze record is registered.** The check compares the record with the
  digest in the manifest and reads no registry.
  `python -m tools.experiment_freeze --check` holds each file named `freeze-r*.json` to
  the freeze registry. A freeze record under another file name is held by neither.
- **That a run directory was committed, or that it was not replaced as a whole.** The
  check reads the files of a tree, tracked or not.
- **That a run executed.** A directory that conforms holds files with their stated
  digests. It does not show where a file came from.
- **That a derived file follows from the raw files.** No analysis reads a run directory.
  (Since `V2-S5-004-PR1` [the reliability analysis](reliability-analysis.md) prints a document
  from files that it is given. A person can store it under the role `analysis`,
  and no such file exists. The tool does not read a run directory or a manifest,
  and this check does not compute its document again. Since `V2-S5-004-PR2`
  [the replay tool](analysis-replay.md) reads a run directory and its manifest, and
  it computes a run analysis again. This check still does not. Since
  `V2-S5-006-PR1` each of the two attempts of the integration validation holds a
  file with the role `analysis`, a run analysis of the replay tool.)
- **That a raw file is complete.** No rule requires a role, and no rule compares the
  times of two files.
- **That the release, the binding, the runtime image, and the model of the manifest are
  those a cluster ran.** The check reads no release and no cluster.
- **That the result state is the one the criteria give.**
- **That a correction is true, or that a reader applies it.**
- **That two run identifiers of one experiment differ by more than letter case.** Two
  such directories cannot both exist on a file system that ignores case.
- **That a run identifier is used in one experiment only.**
- **What an experiment directory holds beside `runs` and `corrections`.**

## Commands

```sh
# Check every run directory under docs/proof/experiments.
uv run --locked python -m tools.experiment_evidence repository
# Check one run directory.
uv run --locked python -m tools.experiment_evidence check docs/proof/experiments/<experiment>/runs/<runId>
# Print the layout's digest of each file of a directory, for the writer of a manifest.
uv run --locked python -m tools.experiment_evidence digests path/to/a/directory
# The layout, the rules, the corrections, the gaps, and this page.
uv run --locked python -m pytest tests/testing/test_experiment_evidence_layout.py -q
```

`repository` prints `pre-schema` for a directory whose manifest the register names,
`qualification` for a Q1 qualification that no text rule refuses, `ok` with the two
digests for a directory that conforms, and `REFUSED` with each finding otherwise. It
prints three `pre-schema` lines, one `qualification` line, for `q1-1`, and two `ok`
lines, one for each attempt of the integration validation, and exits 0. (Until
`V2-S5-006-PR1` it printed three `pre-schema` lines only, and until `V2-S6-001-PR2` it
printed no `qualification` line.)

`digests` prints one line for each file of a directory that has the form of an evidence
file and that neither text rule refuses, in the order of the paths as text. It prints no
line for the manifest. A link, a file of another form, a file that a text rule refuses,
and a path that names no directory are each a finding.

Each command exits 0 when nothing is refused, 3 when a rule refuses a directory or a
file, 2 when its arguments are not usable, and 4 when it fails in a way that no rule
names. Each reads files and writes nothing.

The suite is in the default lane. It is static evidence, C0: it reads committed files and
files it writes under a temporary directory. It executes no run.
[The validation record](../proof/testing/v2-s5-002-pr2-validation.md) states what was run
for this change, and what two independent reviews of its first commit found.

## What this layout does not do

- **It is not evidence of a run.** A run directory is the evidence, and the layout is
  not. The two run directories of this layout that exist are of attempts of a
  non-result integration validation, and no claim cites either. (Until
  `V2-S5-006-PR1` this item said that no run directory of this layout exists.)
- **No tool writes a run directory.** A person or a later tool writes one. No experiment
  runner in this repository produces this layout. The two that exist were assembled by
  scripts run by hand, which are not committed. (Until `V2-S5-006-PR1` this item said
  that nothing writes a run directory.) The E01 runner writes the earlier
  shape, as [the ExperimentRun contract](../contracts/experiment-run.md) states.
- **Nothing reads a run directory for analysis.** No tool computes a result from one.
  (Since `V2-S5-004-PR1` [the reliability analysis](reliability-analysis.md) computes figures
  from evidence files that a command names. It decides no result. Since
  `V2-S5-004-PR2` [the replay tool](analysis-replay.md) reads a run directory for
  those figures. It decides no result. Since `V2-S5-006-PR1` it reads the two
  attempts of the integration validation. Until then the proof tree held no run
  directory of this layout for it to read.)
- **It defines no file form but the caller record's.** The roles name what a file holds.
  The tools of this repository that read a cluster write their own records, and none
  writes a file of this layout.
- **It registers no claim.** The claim and evidence register is unchanged, and no claim
  cites this layout.
- **It changes no evidence level.** The meanings of C0 to C4 are those of
  [InferOps Evidence Levels](evidence-levels.md). The layout assigns no level, and a
  directory that conforms is not evidence at a level.
- **It does not establish runtime behaviour.** A C0 record does not establish that a
  release serves, that a fault was survived, or that a caller saw an answer.
