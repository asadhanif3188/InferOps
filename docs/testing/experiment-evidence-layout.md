# Experiment evidence layout

Status: **published layout with an offline check**, added by `V2-S5-002-PR2`. The layout,
its rules, its role vocabulary, its correction form, and a command that checks a run
directory are published here and checked on every change. **No run directory of this
layout exists.** No run produced one, and no tool writes one. Each directory that the
suite checks is built by the suite, with a synthetic caller record and placeholder
identities. The three run directories that are committed were written before the
[ExperimentRun schema](../contracts/experiment-run.md). The check lists them and does not
check them: [the compatibility section](#the-three-earlier-run-directories) says how they
are held.

| Property | Value |
|---|---|
| Proof tree | `docs/proof/experiments/` |
| Run directory | `docs/proof/experiments/<experiment>/runs/<runId>/` |
| Manifest | `run.v1alpha1.json`, an [ExperimentRun](../contracts/experiment-run.md) |
| Corrections | `docs/proof/experiments/<experiment>/corrections/<runId>/` |
| Digest | SHA-256 of a file's content with each CRLF replaced by LF |
| Evidence file suffixes | `.csv`, `.json`, `.jsonl`, `.md`, `.txt`, `.yaml`, `.yml` |
| Roles | 13: 11 raw and 2 derived |
| Rules | 21 |
| Check | [`tools/experiment_evidence`](../../tools/experiment_evidence/core.py) |
| Suite | [`tests/testing/test_experiment_evidence_layout.py`](../../tests/testing/test_experiment_evidence_layout.py) |

## What it is for

An [ExperimentRun](../contracts/experiment-run.md) names each evidence file of a run by
role, path, and digest. Its validator reads the manifest and opens no evidence file. So a
manifest can validate when a file it names is absent, or has another content.

This layout says where a run directory is, which files it holds, and how each file is
hashed. The check opens the files. It holds a run directory to its manifest in both
directions: each file that the manifest names is present with its stated digest, and
each file that is present is named.

A reader of a result can then recompute each digest with a tool that this repository did
not write. `sha256sum` gives the same value for a file that holds LF line endings.

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
    |-- reviews/                         review records, as before
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
  the name does not.
- **A run directory is closed.** It holds the manifest and the files the manifest names,
  and no other file. A file that Git ignores is a file of the directory to the check.
- **A committed run directory is not edited.** A change to a run is a
  [correction](#corrections), outside the run directory.

## Hashing

A digest is the SHA-256 of a file's content with each CRLF replaced by LF, as 64
lowercase hexadecimal characters.

- **It is the digest of the evidence index.**
  [`tools/evidence_index`](../../tools/evidence_index/core.py) hashes a text file in this
  form, and the check calls that function. So a file of a run directory has one digest in
  the manifest, in a review record, and in [the evidence index](../proof/v1-evidence-index.md).
- **It is the digest of the content that Git stores.** The repository stores a text file
  with LF. A Windows checkout can hold the same file with CRLF. The digest does not move
  between the two, and the suite converts a run directory to CRLF to hold that.
- **An evidence file is text of a known suffix.** The index hashes seven suffixes as
  text and every other file byte for byte. A file under another suffix could have two
  digests on two hosts. So an evidence file must have one of the seven suffixes, be
  UTF-8, and hold no NUL character. An image, an archive, and a model artifact are
  refused.
- **A writer computes the digest with the same function.**
  `python -m tools.experiment_evidence digests <directory>` prints one
  `<sha256>  <path>` line for each file, and `describe_file` returns one
  `evidence.files` entry. A writer that hashes the raw bytes of a file that holds CRLF
  states a digest that the check refuses.

The ExperimentRun contract says that `evidence.files[].sha256` is the SHA-256 of the
file's bytes. For a file that holds LF line endings the two statements agree. This page
is the precise one for a file of a run directory.

### The two digests of a run

The check prints two digests for a run directory that conforms. Each is the evidence
index's set digest: the SHA-256 over the sorted lines `<sha256>  <repository path>`.

| Digest | Taken over |
|---|---|
| Raw evidence | The files with a raw role. A run that names no raw file has none. |
| Evidence set | The manifest and every evidence file. |

No correction is in either digest. **No document stores either digest.** A later record
that quotes one can be checked against the command's output.

## Roles: raw and derived

Each evidence file has a registered role. The ExperimentRun schema holds no role
vocabulary, and this layout adds one for a file of a run directory.

| Role | Kind | What a file with the role holds |
|---|---|---|
| `caller` | raw | The caller's own record of its requests, as the reliability runner writes it. |
| `endpoints` | raw | Readings of the Service endpoints, each with its time. |
| `pods` | raw | Readings of the pods, each with its time. |
| `deployments` | raw | Readings of the Deployments, each with its time. |
| `argo` | raw | Readings of the Argo CD Application, each with its time. |
| `telemetry` | raw | Readings of the metrics that the frozen record registers. |
| `resources` | raw | Readings of resource use, each with its time. |
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
- **The form of a raw file is not defined here, except for `caller`.** No collector of
  endpoint, pod, Deployment, Argo CD, or resource readings for an experiment exists yet.
  A file with one of those roles is held to its digest and to the text rules, and it is
  not read for its meaning.
- **A role that is not in the table is refused.** A run that needs another role adds it
  to the vocabulary in a change that a reviewer reads.

### The caller record

A file with the role `caller` is read. It must be a caller record that
[the reliability runner's reader](../serving/reliability-runner.md) accepts. Its header
must name the experiment, the run, the caller profile revision with its digest, and the
concurrency of the manifest. It must not be a rehearsal. When the record declares a
release identifier, the identifier is the manifest's.

This closes one item that the ExperimentRun contract lists as checked by nothing: that the
two documents of a run name one experiment and one run. A record whose plan declared no
release names none, and the check then compares none.

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
| `number` | Integer, 1 or more | The number of the correction. It is the number in the file name. |
| `recordedAt` | UTC instant | When the correction was written. |
| `manifestSha256` | SHA-256 | The digest of the run's manifest. |
| `previousCorrectionSha256` | SHA-256 or `null` | The digest of the correction before this one. `null` for the first. |
| `corrects[]` | Path and SHA-256, one or more | Each file that the correction bears on, with its digest. |
| `statements[]` | Statement, one or more | What is corrected, in prose of 1 to 2000 characters each. |
| `files[]` | Role, evidence path, SHA-256 | Each file that the correction adds. The list can be empty. |

The eleven members are all required, and no other member is permitted. No JSON Schema
file defines the form: the check holds it in code, as it holds the pre-schema register.

- **A correction is additive.** It moves no file of the run directory and neither
  digest of the run.
- **A correction of an edited file is refused.** `corrects[]` states the digest of each
  file it bears on: the manifest, an evidence file that the manifest names, or an
  earlier correction. The check compares each with the file that is present.
- **The first correction pins the manifest.** `manifestSha256` is compared with the
  manifest that is present. After a correction exists, a manifest that is replaced with
  new digests is refused. Before one exists, it is not:
  [the measured gaps](#measured-gaps) state that.
- **Corrections are a chain.** They are numbered from 1 with no gap, and each one after
  the first states the digest of the one before it. An edit of an earlier correction is
  refused at the next one. An edit of the last one is not refused by the chain.
- **A correction does not change a result state.** The manifest keeps the state it
  states. No rule reads a statement of a correction, and no tool applies one.
- **The review gate is not ended by a correction.** A review record states the digest of
  each file of a run directory. A correction is outside that directory.

## What a run directory must not hold

The layout requires no file. So it requires no file that holds a credential, a prompt, a
response body, or a path of a host. Two text rules read each evidence file and each
correction.

- **No word starts with the published prefix of a credential format.** The list of
  prefixes is the WorkloadContract validator's. A word ends at white space and at the
  punctuation of JSON, of YAML, and of a shell assignment. The rule was measured on the
  committed text files of `docs/proof/` that are not Markdown pages: none of them starts
  a word with such a prefix.
- **No file holds a path under a user directory of a host.** The rule refuses a drive
  letter before `Users` or `home`, and `Users` or `home` before a name and a separator.
  It is the pattern of the security baseline suite, and it also reads a separator that
  JSON wrote twice.
- **The shape heuristic of the ExperimentRun rules is not applied to an evidence file.**
  It refuses a long word in mixed case with a digit. Committed raw evidence holds
  identifiers and encoded values of that shape, and a rule that refuses them would
  require an edit of raw evidence.
- **No rule reads a file for a prompt or a response.** A caller record holds neither:
  its reader gives each line an exact set of members. A file with another role is not
  read for its meaning.
- **A refusal repeats no text read out of a file.** It states the rule, the path, and a
  fixed message.

## Rules

Each rule has an identifier. The output of the check names the rule and the path.

| Rule | Statement |
|---|---|
| `evidence-manifest-missing` | A run directory holds one run manifest, named run.v1alpha1.json. |
| `evidence-manifest-refused` | The manifest of a run directory validates as an ExperimentRun. |
| `evidence-run-directory-misplaced` | A run directory is named by its run identifier, in the runs directory beside the freeze record that its manifest names, and that record is a file of one directory of docs/proof/experiments. |
| `evidence-freeze-record-differs` | The freeze record that a manifest names is present, and it has the revision and the content digest that the manifest states. |
| `evidence-file-missing` | Each evidence file that a manifest or a correction names is present. |
| `evidence-file-unlisted` | Each file of a run directory is the manifest or an evidence file that the manifest names, and each file of a corrections directory is a correction or a file that a correction names. |
| `evidence-file-not-regular` | An evidence file is a regular file and not a link. |
| `evidence-file-form-unsupported` | An evidence file is UTF-8 text with no NUL character, under a file suffix that the evidence index hashes as text. |
| `evidence-file-digest-differs` | The digest stated for an evidence file is the SHA-256 of the file's content with each CRLF replaced by LF. |
| `evidence-file-credential-prefix` | No word of an evidence file or of a correction starts with the published prefix of a credential format. |
| `evidence-file-personal-path` | No evidence file and no correction holds a path under a user directory of a host. |
| `evidence-role-unregistered` | Each evidence file has a registered role. |
| `evidence-summary-without-raw` | A run that names a derived file names at least one raw file. |
| `evidence-caller-record-refused` | A file with the role caller is a caller record that the reliability runner's reader accepts. |
| `evidence-caller-record-identity-differs` | A caller record names the experiment, the run, the caller profile revision, the concurrency, and the release of its manifest, and it is not a rehearsal. |
| `evidence-correction-run-unknown` | A corrections directory names a run directory of this layout in the same experiment directory. |
| `evidence-correction-unreadable` | A correction is one JSON object with exactly the registered members, each in its form. |
| `evidence-correction-number-out-of-sequence` | The corrections of a run are numbered from 1 with no gap, and each file name states its number. |
| `evidence-correction-identity-differs` | A correction names the experiment, the run, and the present manifest digest of the run it corrects. |
| `evidence-correction-chain-broken` | The first correction of a run names no earlier one, and each later one states the content digest of the correction before it. |
| `evidence-correction-target-differs` | A correction names each file it corrects by its path and its present digest: the manifest, an evidence file of the manifest, or an earlier correction. |

**The order of the check.** A directory with no manifest gets one finding. A manifest
that the ExperimentRun validator refuses gets one finding, and the check reads nothing
else of the directory: the findings of the manifest are those of
`python -m tools.experiment_run check`. Every other rule is applied to a manifest that
validates, and each finding is reported.

**The names are compared as text.** A file system that ignores letter case opens a file
under a name in another case. The check compares each name with the names the directory
lists. So one tree has one verdict on each host.

## Compatibility

### The ExperimentRun contract

The layout adds no member to the schema and changes no rule of its validator. A
manifest that validated before this change validates now.

The contract lists statements about a run that no code checked. For a run directory, the
check now holds five of them:

| Statement of the contract | Held by |
|---|---|
| An evidence file exists and has its stated digest. | `evidence-file-missing`, `evidence-file-digest-differs` |
| An evidence file that is present is listed. | `evidence-file-unlisted` |
| The freeze record exists, has the stated revision, and has the stated digest. | `evidence-freeze-record-differs` |
| The experiment and run identifiers equal those of the caller record. | `evidence-caller-record-identity-differs` |
| Two evidence paths are paths that one directory can hold. | `evidence-file-missing` |

`python -m tools.experiment_run check` still opens no evidence file. A manifest outside a
run directory, such as a fixture, is held to none of these.

**One role of the committed fixtures is not registered.** A valid fixture of the schema
names a file with the role `completion`. The schema holds no role vocabulary, so the
fixture validates. No fixture is a run directory, and the suite measures the difference.

### The evidence index and the result review gate

- **The digest is the index's.** The check imports the index's function and its list of
  text suffixes. The suite holds that they are the same objects.
- **The run directory is where the review gate reads one.** The gate reads a run at
  `docs/proof/experiments/<experiment>/runs/<runId>/`, and a review record at
  `<experiment>/reviews/`. This layout puts a run in that place.
- **The gate reads the freeze record of a manifest in both shapes.** The gate compares
  the freeze record of a review with the one the run's manifest names. A manifest of the
  published schema names it in `metadata.spec.freezeRecord`. The three earlier manifests
  name it in `metadata.freezeRecord`. Before this change the gate read the second member
  only, and it would have refused a review of each run of the published schema. This
  change makes the gate read either. The gate's verdict on each committed ledger is
  unchanged.
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
- **The check lists each as `pre-schema` and does not check it.** The schema refuses
  each manifest, so no rule of this layout can be applied to one. The suite measures
  that a copy of the E01-D directory is refused at its manifest.
- **Other mechanisms hold them, as before.** The register holds each manifest to its
  digest. `python -m tools.experiment_e01 --check` judges the two static runs. The
  review gate holds the files of the second static run and of the E01-D run to the
  digests that their review records state.
- **This layout gives them no correction.** A corrections directory for one of them is
  refused. The dated notes of those runs are in
  [the experiments page](../proof/experiments/README.md), as before.

## Measured gaps

The suite asserts each, so closing one is a visible change.

- **A file and its digest in the manifest, replaced together, conform.** The check reads
  one tree and not Git. Before a correction or a review record states the manifest's
  digest, nothing in the tree pins the manifest. Git history is the record.
- **A derived file that was not computed from the raw files conforms.** The rule asks
  for a raw file beside a derived file. No rule reads a derived file.
- **A raw file other than a caller record is not read for its meaning.** A file with the
  role `pods` that holds no reading of a pod conforms.
- **A lowercase secret with no published prefix passes.** So does a published prefix
  that is not at the start of a word, and a word of the shape that the ExperimentRun
  rules refuse in a statement.
- **A host path that is not under a user directory passes.** `/var/lib/...`, `/root/...`,
  and a drive path outside `Users` and `home` are not refused.
- **A container path under a home directory is refused.** The rule cannot tell a path in
  a container from a path of a host. The security baseline suite refuses the same text in
  each committed file.
- **A request text passes.** No rule reads a file for a prompt or a response.
- **A caller record that declares no release is compared with none.**

## Rules that nothing applies

Each of these is a statement about a run directory that no code in this repository
checks.

- **That a run directory was committed, or that it was not replaced as a whole.** The
  check reads the files of a tree, tracked or not.
- **That a run executed.** A directory that conforms holds files with their stated
  digests. It does not show where a file came from.
- **That a derived file follows from the raw files.** No analysis reads a run directory.
- **That a raw file is complete.** No rule requires a role, and no rule compares the
  times of two files.
- **That the freeze record is registered.** The check compares the record with the
  digest in the manifest. [`tools/experiment_freeze`](../../tools/experiment_freeze/core.py)
  holds a record to the freeze registry.
- **That the release, the binding, the runtime image, and the model of the manifest are
  those a cluster ran.** The check reads no release and no cluster.
- **That the result state is the one the criteria give.**
- **That a correction is true, or that a reader applies it.**
- **That two run identifiers of one experiment differ by more than letter case.** Two
  such directories cannot both exist on a file system that ignores case.
- **That a run identifier is used in one experiment only.**

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

`repository` prints `pre-schema` for a directory whose manifest the register names, `ok`
with the two digests for a directory that conforms, and `REFUSED` with each finding
otherwise. In this change it prints three `pre-schema` lines and exits 0.

Each command exits 0 when nothing is refused, 3 when a rule refuses a directory or a
file, 2 when its arguments are not usable, and 4 when it fails in a way that no rule
names. Each reads files and writes nothing.

The suite is in the default lane. It is static evidence, C0: it reads committed files and
files it writes under a temporary directory. It executes no run.
[The validation record](../proof/testing/v2-s5-002-pr2-validation.md) states what was run
for this change.

## What this layout does not do

- **It is not evidence of a run.** No run directory of this layout exists.
- **Nothing writes a run directory.** A person or a later tool writes one. No experiment
  runner in this repository produces this layout. The E01 runner writes the earlier
  shape, as [the ExperimentRun contract](../contracts/experiment-run.md) states.
- **Nothing reads a run directory for analysis.** No tool computes a result from one.
- **It defines no collector and no file form but the caller record's.** The roles name
  what a file holds. A later change that adds a collector defines the form of its file.
- **It registers no claim.** The claim and evidence register is unchanged, and no claim
  cites this layout.
- **It changes no evidence level.** The meanings of C0 to C4 are those of
  [InferOps Evidence Levels](evidence-levels.md). The layout assigns no level, and a
  directory that conforms is not evidence at a level.
- **It does not establish runtime behaviour.** A C0 record does not establish that a
  release serves, that a fault was survived, or that a caller saw an answer.
