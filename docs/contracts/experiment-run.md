# ExperimentRun v1alpha1

Status: **published schema**, at `v1alpha1` maturity, added by `V2-S5-002-PR1`. The
schema, its identifier, its compatibility rules, its valid and invalid fixtures, and an
offline validator are published here and checked on every change. **No run produced a
manifest of this schema.** No tool writes one, no experiment runner reads one, and no
analysis consumes one. The fixtures are hand-written documents with placeholder
identities. Three run manifests that were committed before the schema state the same
`apiVersion` and `kind` and do not conform:
[the compatibility section](#compatibility-with-the-manifests-committed-before-the-schema)
says how they are held. Since `V2-S5-002-PR2`,
[the experiment evidence layout](../testing/experiment-evidence-layout.md) says where the directory of a run is, and
a separate check opens the evidence files of one. This validator still opens none.
Since `V2-S5-004-PR2`, [the replay of an analysis](../testing/analysis-replay.md) reads the
manifest of a run directory for the evidence files and the result state of its run.
No run produced a manifest of this schema for it to read. Its gate in the evidence
index reads the three earlier manifests for the role of each file, and they name none.

| Property | Value |
|---|---|
| Schema | [`contracts/experiment/experiment-run.v1alpha1.schema.json`](../../contracts/experiment/experiment-run.v1alpha1.schema.json) |
| Dialect | JSON Schema draft 2020-12 |
| Schema `$id` | `https://inferops.io/contracts/experiment/experiment-run.v1alpha1.schema.json` |
| `apiVersion` | `inferops.io/v1alpha1` |
| `kind` | `ExperimentRun` |
| Authoring form | JSON. This departs from ADR 0003: see [the authoring form](#the-authoring-form) |
| File name | `run.v1alpha1.json`, in the directory of the run |
| Unknown fields | Rejected |
| Validator | [`tools/experiment_run`](../../tools/experiment_run/core.py): the schema, 14 semantic rules, and the repository listing |
| Fixtures | [`contracts/experiment/examples/`](../../contracts/experiment/examples/README.md) |
| Pre-schema register | [`contracts/experiment/compatibility/pre-schema-experiment-runs.v1alpha1.json`](../../contracts/experiment/compatibility/pre-schema-experiment-runs.v1alpha1.json) |
| Tooling decision | [ADR 0003](../architecture/decisions/ADR-0003-workload-contract-schema-tooling.md) for the schema language and the validator library. The authoring form is not that decision's |

## What it is for

An experiment is fixed by a [freeze record](../proof/experiments/README.md) before its
first result-bearing run. A run then produces evidence files. An ExperimentRun is the one
document that binds the two: it says which frozen record the run answers, which commit
it executed, on which environment, against which release, runtime image, and model,
with which caller profile and which fault, and it names each evidence file by digest.

A reader of a result needs those identities in one place and in one form. Without them,
a result page states a number and the reader cannot say what was measured.

The manifest describes a run **against a delivered release in a cluster**. It requires
an environment, a release, a runtime image, and a model. A run that deploys nothing has
no value for those members, and this version cannot describe it.
[What this contract does not do](#what-this-contract-does-not-do) states that limit.

## A repository document, not a cluster resource

An ExperimentRun has `apiVersion` and `kind` because every contract in this repository
does. It is not a Kubernetes resource. No custom resource definition, controller, or
cluster reads one. It has no `spec` and no `status`. It is written once, beside the
evidence files it names, and committed.

## The authoring form

[ADR 0003](../architecture/decisions/ADR-0003-workload-contract-schema-tooling.md)
accepts YAML as the authoring form of a contract and JSON as its wire form, and it
rejects JSON authoring because JSON holds no comment. **An ExperimentRun is authored as
JSON, and that departs from the decision.** The reasons: a person does not write a run
manifest as a person writes a workload contract. A run writes it, beside evidence files
that are JSON, and the three run manifests already committed are JSON. A digest of a
JSON file needs no rule for how YAML is read. The cost is the one the decision names: a
fixture cannot explain itself in a comment. So each valid fixture says what it is in
its first limitation, and one file states what each invalid fixture is refused for.
ADR 0003 is not edited, and no decision record states this departure.

## Three separate things

A run has a **result state**. Evidence has a **level**. A claim has a **status**. This
contract keeps them apart, as [InferOps Evidence Levels](../testing/evidence-levels.md)
do.

| Thing | Values | Where this document holds it |
|---|---|---|
| Result state | `PASSED`, `FAILED`, `INCONCLUSIVE`, `REFUSED`, `ABORTED` | `result.state` |
| Evidence level | `C0`, `C1`, `C2`, `C3`, `C4` | `evidenceLevel.intended` |
| Claim status | `certified`, `planned`, `deferred`, `not-claimed` | No member. The [claim and evidence register](../testing/claim-evidence-matrix.md) holds it |

- **`FAILED` and `INCONCLUSIVE` are not evidence levels.** They are states of a run. A
  `FAILED` run that intends `C2` is runtime evidence of a failure. The schema refuses an
  evidence level in `result.state` and a result state in `evidenceLevel.intended`.
- **Each state validates at each level.** The suite holds all 25 pairs. The state of a
  run does not bound the level of its evidence, and a level does not imply a state.
- **The run does not assign a level to itself.** `evidenceLevel.intended` is the level
  that the frozen record intends. The level of an evidence record is stated in the
  register, when a change registers the record. The schema has no member for an
  achieved level.
- **The meanings of C0 to C4 are unchanged.** The schema names the five levels and
  defines none. No rule here admits a run to `C3` or `C4`:
  [the rules nothing applies](#rules-that-nothing-applies) says so.
- **No member holds a claim status.** Every object is closed, so a `claimStatus`
  member is an unknown field in each object. A value is not read for the words: a
  role named `certified`, or a statement that says that a claim is certified,
  validates.

The five result states:

| State | Meaning |
|---|---|
| `PASSED` | Every frozen criterion held. |
| `FAILED` | A frozen criterion did not hold. |
| `INCONCLUSIVE` | The evidence does not decide a criterion. A reason is required. |
| `REFUSED` | A precondition failed, and the run did not start its procedure. A reason is required. |
| `ABORTED` | The run started, and an abort condition stopped it. A reason is required. |

A run keeps its manifest whatever its state. A run is not repeated to obtain another
state: a second attempt is a second run, with another `runId`, and both stay.

## Structure

Fifteen top-level members, all required. `Required` says `yes` when the member's object
always requires it, and `no` when a condition decides. The conditions follow the table.

| Field | Required | Form | Meaning |
|---|---|---|---|
| `apiVersion` | yes | `inferops.io/v1alpha1` | The contract group and version. |
| `kind` | yes | `ExperimentRun` | The document kind. |
| `metadata.experimentId` | yes | Identifier | The experiment the run belongs to. |
| `metadata.runId` | yes | Identifier | The identifier of this run. |
| `metadata.spec.freezeRecord` | yes | Repository path | The freeze record the run answers. |
| `metadata.spec.freezeRevision` | yes | Integer, 1 to 9999 | The revision number of that record. |
| `metadata.spec.freezeContentSha256` | yes | SHA-256 | The content digest of that record. |
| `metadata.executingRevision` | yes | Git commit, 40 characters | The commit the run executed. |
| `metadata.startedAt` | yes | UTC instant | When the run started. |
| `metadata.finishedAt` | yes | UTC instant | When the run ended. |
| `environment.binding.environment` | yes | `ci`, `local`, `dev`, `staging`, `production` | The binding's environment. |
| `environment.binding.name` | yes | DNS label | The binding's name. |
| `environment.binding.sha256` | yes | SHA-256 | The digest the release records for the binding. |
| `environment.provider` | yes | DNS label | The cluster provider the run observed. |
| `environment.kubernetesVersion` | yes | `v` and a version | The server version the run observed. |
| `environment.nodeCount` | yes | Integer, 1 to 10000 | The number of nodes the run observed. |
| `release.releaseId` | yes | SHA-256 | The release's `metadata.releaseId`. |
| `release.contractSha256` | yes | SHA-256 | The release's `source.contract.sha256`. |
| `release.helmValuesSha256` | yes | SHA-256 | The release's `output.helmValues.sha256`. |
| `release.desiredStateRevision` | yes | Git commit, 40 characters | The commit that held the desired state. |
| `runtime.image` | yes | Image reference with a digest | The serving runtime image. |
| `model.identifier` | yes | DNS label | The identifier the API serves the model under. |
| `model.revision` | yes | 40 to 64 hexadecimal characters | The revision of the model's source repository. |
| `model.sha256` | yes | SHA-256 | The digest of the model artifact. |
| `callerProfile.applies` | yes | Boolean | Whether the run sent a caller profile. |
| `callerProfile.reason` | no | Statement | Why no caller profile applies. |
| `callerProfile.profileId` | no | Profile identifier | The profile, such as `RP-1`. |
| `callerProfile.profileRevision` | no | Integer, 1 to 9999 | The profile's revision number. |
| `callerProfile.contentSha256` | no | SHA-256 | The content digest of the profile file. |
| `callerProfile.concurrency` | no | Integer, 1 to 1024 | The number of concurrent callers. |
| `fault.registered` | yes | Boolean | Whether the frozen record registers a fault. |
| `fault.type` | no | DNS label | The registered fault type. |
| `fault.injected` | no | Boolean | Whether the run injected the fault. |
| `fault.target` | no | Lowercase segments with slashes | The recorded identity of the target. |
| `fault.injectedAt` | no | UTC instant | When the run injected the fault. |
| `fault.reason` | no | Statement | Why no fault is registered, or why it was not injected. |
| `result.state` | yes | One of the five states | The result state of the run. |
| `result.reason` | no | Statement | Why the run has this state. |
| `evidenceLevel.intended` | yes | `C0` to `C4` | The level the frozen record intends. |
| `evidence.files[].role` | yes | DNS label | What the file is evidence of. |
| `evidence.files[].path` | yes | Evidence path | The file, relative to the run's directory. |
| `evidence.files[].sha256` | yes | SHA-256 | The SHA-256 of the file's bytes. |
| `cleanup.state` | yes | `verified`, `incomplete`, `not-required` | The state of the cleanup. |
| `cleanup.reason` | no | Statement | Why the cleanup is incomplete or not required. |
| `cleanup.left[]` | no | Statement | One item that the cleanup left in place. |
| `limitations[]` | yes | Statement | One limitation of the run. At least one. |
| `doesNotEstablish[]` | yes | Statement | One conclusion the run does not support. At least one. |

**The conditions.** The schema states each, so a consumer that holds only the schema
file gets them.

- If `callerProfile.applies` is `false`, `reason` is required and no other member is
  permitted. Otherwise `profileId`, `profileRevision`, `contentSha256`, and
  `concurrency` are required and `reason` is not permitted.
- If `fault.registered` is `false`, `reason` is required and no other member is
  permitted. Otherwise `type` and `injected` are required.
- If `fault.injected` is `true`, `target` and `injectedAt` are required and `reason` is
  not permitted. If it is `false`, `reason` is required and `target` and `injectedAt`
  are not permitted.
- If `result.state` is `INCONCLUSIVE`, `REFUSED`, or `ABORTED`, `result.reason` is
  required.
- If `cleanup.state` is `incomplete` or `not-required`, `cleanup.reason` is required.
  If it is `verified`, `reason` is not permitted. If it is `not-required`, `left` is
  not permitted.

**The forms.**

- **Identifier.** 1 to 63 characters: a letter or digit, then letters, digits, dots,
  underscores, and hyphens. It is the form that the
  [reliability caller record](../serving/reliability-runner.md) accepts for the same two
  identifiers. So one run can carry one `experimentId` and one `runId` in both
  documents. Nothing compares the two documents.
- **UTC instant.** `YYYY-MM-DDTHH:MM:SSZ`, with an optional fraction of one to six
  digits. An offset other than `Z` is refused. The caller record writes this form with
  three digits.
- **SHA-256.** 64 lowercase hexadecimal characters, with no prefix. The
  WorkloadContract writes the digest of the model artifact with a `sha256:` prefix.
  `model.sha256` holds the same digest without the prefix, and the suite measures the
  difference.
- **Evidence path.** Lowercase segments separated by forward slashes. Each segment
  starts and ends with a letter or digit. So a leading slash, a drive letter, a
  backslash, and a parent segment are refused.
- **The end of a pattern.** Each of the 12 patterns ends with `$(?!\n)`. Python's `$`
  also matches before a final line feed, and an ECMA-262 engine's does not. Without
  the lookahead, a digest or a path that ends with a line feed validates under one
  engine and is refused under the other. The first commit of this change had that
  defect. The schemas of the three earlier contracts end their patterns with `$`
  alone, and this change does not edit them.
- **Statement.** 1 to 2000 characters of prose. It is the only free text in the
  document. Seven members hold statements, and the suite holds that no other string
  member is free text.

## What a manifest must not hold

- **No member for a prompt, a completion, or a response body.** The schema defines
  none, and every object is closed. An evidence file is named by path and digest, and
  no member holds its content. **No rule reads a statement for a prompt or a
  response.** A statement is prose of up to 2000 characters, and a writer can put
  such text in one.
- **No credential.** No member is defined for one. A string value, or a word of a
  statement, that has the shape of a credential is refused by a
  [semantic rule](#semantic-rules), within the limits that
  [the measured gaps](#measured-gaps) state.
- **No absolute host path.** A repository path and an evidence path cannot hold one,
  by their patterns. A relative path that names a user directory is not refused. A statement that holds a drive-letter path, or a path under `/home/`,
  `/Users/`, or `/root/`, is refused by a semantic rule.
- **No member for a claim status or for an achieved evidence level.**

A refusal of a manifest repeats no value read out of the manifest. The suite holds
that for each value of 12 characters or more of each invalid fixture.

## Rejection and canonical errors

A refusal has a canonical error code, a rule identifier, and a field location, as
[the WorkloadContract's](workload-contract.md) have. Every rule here has the code
`contract-invalid`, except the version rule.

The validator applies two layers. **The semantic layer runs only on a document that the
schema accepts.** A document with a structural finding reports no semantic finding.

### Structural rules

The published schema alone refuses the document. A draft 2020-12 validator in another
language is expected to reach the same verdict: the suite runs one validator, the
Python one, and [the end of a pattern](#structure) closes the one difference between
engines that a review found. The rule identifiers are those of the canonical error
model.

| Rule | Code | A fixture that is refused by it |
|---|---|---|
| `contract-version-unsupported` | `version-unsupported` | `unsupported-api-version.json` |
| `field-required` | `contract-invalid` | `missing-required-values.json` |
| `field-unknown` | `contract-invalid` | `claim-status-in-run.json` |
| `value-not-permitted` | `contract-invalid` | `evidence-level-as-result-state.json` |
| `value-malformed` | `contract-invalid` | `mutable-revisions.json` |
| `value-out-of-range` | `contract-invalid` | `values-out-of-range.json` |
| `value-wrong-type` | `contract-invalid` | `wrong-json-types.json` |
| `contract-structure-invalid` | `contract-invalid` | None. It is the fallback for a schema keyword with no rule, and no fixture reaches it |

### Semantic rules

`tools/experiment_run` applies these, and the schema does not. **A consumer that holds
only the schema file does not get them.** Each has one invalid fixture.

| Rule | Statement | Field |
|---|---|---|
| `run-time-not-an-instant` | A time that has the form of a UTC instant is a real instant. | The time |
| `run-time-order-inverted` | A run does not end before it starts. | `$.metadata.finishedAt` |
| `run-fault-time-outside-run` | A fault is injected between the start and the end of its run. | `$.fault.injectedAt` |
| `run-passed-without-registered-fault` | A run whose frozen record registers a fault is PASSED only when it injected the fault. | `$.result.state` |
| `run-refused-after-fault` | A REFUSED run did not start its procedure, so it injected no fault. | `$.result.state` |
| `run-caller-profile-unregistered` | A caller profile a run names is a registered revision of a registered profile. | `$.callerProfile.profileRevision` |
| `run-caller-profile-digest-differs` | The content digest a run states for a caller profile revision is the registered digest of that revision. | `$.callerProfile.contentSha256` |
| `run-caller-concurrency-differs` | The concurrency a run states is the concurrency its caller profile fixes. | `$.callerProfile.concurrency` |
| `run-caller-evidence-missing` | A PASSED or FAILED run that names a caller profile names at least one evidence file with the role caller. | `$.evidence.files` |
| `run-decided-without-evidence` | A PASSED or FAILED run names at least one evidence file. | `$.evidence.files` |
| `run-evidence-path-duplicated` | A run names each evidence path once. | The later path |
| `run-evidence-names-the-manifest` | A run does not list its own manifest as evidence. | The path |
| `run-value-credential-shaped` | No string value, and no word of a statement, has the shape of a credential. | The value |
| `run-text-host-path` | No statement holds an absolute path of a host. | The value |

**The caller profile.** One profile is registered:
[RP-1](../serving/reliability-workload-rp-1.md), revision 1, with the content digest
that [`tools/reliability_profile`](../../tools/reliability_profile/core.py) registers
and a concurrency of 2. A run that names RP-1 revision 1 with another digest, or with
another concurrency, is refused. So a manifest cannot state another concurrency under
RP-1 than the profile fixes. A later profile revision is registered there before a run
can name it. The rule compares the manifest with the registered digest. It does not
read the profile file, and it does not show that a run sent the profile.

**The caller record.** A run that is `PASSED` or `FAILED` under a caller profile decided
its criteria. The rule requires that it names the caller's own record, by the role
`caller`. It does not open the file. A run that is `INCONCLUSIVE`, `REFUSED`, or
`ABORTED` can have no caller record, and the rule does not bind it.

### Rules of reading and of the repository listing

| Rule | Statement |
|---|---|
| `run-document-unreadable` | A run manifest is one JSON object, with no member stated twice. |
| `run-pre-schema-register-unreadable` | The register of pre-schema run manifests is a JSON object that names each manifest once, by repository path and content digest. |
| `run-pre-schema-record-missing` | Every registered pre-schema run manifest is present. |
| `run-pre-schema-record-edited` | A registered pre-schema run manifest has its registered content. |

A member stated twice is refused because a JSON reader keeps the last one. A reader of
the file and the validator could then see two documents.

### Measured gaps

The suite asserts each, so closing one is a visible change.

- **A lowercase secret with no published prefix passes.** The credential rule is the
  WorkloadContract's heuristic over shape, applied to each word. It reads the start of a
  word and one opaque shape.
- **A credential behind a character that is not white space, a quotation mark, or an
  opening bracket can pass.** A published prefix behind an asterisk or an equals sign
  is not at the start of a word.
- **A host path outside the four refused forms passes.** `/var/lib/...`, `/mnt/...`,
  `~/...`, and a network share are not refused. Nor is an account root with no slash
  after it, such as `/root.` at the end of a sentence, or a drive letter with no
  separator.
- **Some ordinary text is refused.** A long word in mixed case with a digit has the
  opaque shape, and one letter before `:/` reads as a drive. A writer must reword
  such a statement.
- **A claim status as a word passes.** So does a statement that holds a prompt or a
  response.
- **A verified cleanup that lists an item it left validates.** A cleanup can be
  verified and leave an image in a node.
- **Two evidence paths that one directory cannot hold validate.** `pods` and
  `pods/a.json` cannot both be files. The check of a run directory refuses such a
  manifest, because one of the two files is absent.
- **A `FAILED`, `INCONCLUSIVE`, or `ABORTED` run whose registered fault was not
  injected validates.** Only `PASSED` and `REFUSED` are bound to the injection.
- **The schema accepts `2026-02-29T10:00:00Z`.** The form is checked by the schema and
  the date by the semantic rule.

### Rules that nothing applies

Each of these is a statement about a run that this validator does not check.
**Since `V2-S5-002-PR2`, another check holds some of them for a manifest in a run
directory.** [The experiment evidence layout](../testing/experiment-evidence-layout.md#the-experimentrun-contract)
lists four: that an evidence file exists and has its digest, that a present file is
listed, that the freeze record exists with its revision and digest, and that a caller
record which the manifest names states the same experiment and run. That check also
refuses one manifest of the measured gaps above: one with two evidence paths that one
directory cannot hold. `python -m tools.experiment_run check` holds none of these, and
no code in this repository checks the other statements of this list.

- **That an evidence file exists and has its stated digest.** The validator opens no
  evidence file. The check of a run directory opens each one.
- **That an evidence file that is present is listed.**
- **That the freeze record exists, has the stated revision, and has the stated
  digest.** The validator does not read the freeze registry.
- **That the release, the binding, the runtime image, and the model are the ones of the
  executing commit, or the ones a cluster ran.**
- **That `metadata.experimentId` and `metadata.runId` equal those of the caller
  record.** The forms agree. Nothing compares the values.
- **That `desiredStateRevision` is what the delivery controller applied.** What the
  controller reported is evidence, in an evidence file.
- **That the result state is the one the criteria give.** A manifest that says `PASSED`
  validates whether or not the criteria held.
- **That the cleanup state is true.** The frozen record decides whether an incomplete
  cleanup bears on a result. No rule binds `result.state` to `cleanup.state`.
- **That a run identifier is used once.** The validator reads one document.
- **That an intended level is permitted.**
  [InferOps Evidence Levels](../testing/evidence-levels.md) states the conditions of
  `C3` and of `C4`. The schema accepts both values and checks no condition of
  either.
- **What a statement says.** No rule reads a statement for a prompt, a response, or a
  claim.
- **That `environment.provider` is a provider the repository supports.** The schema
  holds no provider vocabulary. Naming a provider does not raise an evidence level.

## Compatibility with the manifests committed before the schema

Three run manifests were committed before this schema existed. Each is named
`run.v1alpha1.json` and states `apiVersion: inferops.io/v1alpha1` and
`kind: ExperimentRun`. No schema defined their shape, and each run wrote the members it
needed. **The schema refuses each.**

| Manifest, under `docs/proof/experiments/` | Content digest |
|---|---|
| `v2-e01/runs/20261002-e01-abc-1/run.v1alpha1.json` | `96b75bf78db35805fd16c8b71218bc7eeac3626aeac7129277e2067b0db0f393` |
| `v2-e01/runs/20261003-e01-abc-1/run.v1alpha1.json` | `ae2e005b5f68bc3ed017c9c3e4c2c0508390306a784c2860b6c59ed5dafb5461` |
| `v2-e01/runs/20261006-e01-d-1/run.v1alpha1.json` | `62255edaa5c078f6a1f67af140b923d2ef63e8b40d24c8919691aa37653c5733` |

The digest is the SHA-256 of the file's bytes with every CRLF replaced by LF.

The rules:

1. **A pre-schema manifest is evidence and is not edited.** It is not migrated to the
   schema, and it is not validated against it. The claims, the evidence index, and the
   review records that cite its bytes stay true.
2. **Each is registered by path and content digest**, in
   [the pre-schema register](../../contracts/experiment/compatibility/pre-schema-experiment-runs.v1alpha1.json).
   A registered manifest whose content differs from its digest is refused.
3. **The list is closed.** A manifest named `run.v1alpha1.json` under
   `docs/proof/experiments/` that the register does not name must validate. A fourth
   manifest of the earlier shape is refused: the shape is admitted by name and digest,
   and not by form.
4. **`apiVersion` and `kind` do not tell the two shapes apart.** A reader tells them
   apart by the register. This is a cost of publishing the schema under a pair of
   values that three documents already used. The other choice was a new `apiVersion`
   for the first published schema. That choice would leave `v1alpha1` with no
   definition.

```sh
uv run --locked python -m tools.experiment_run repository
```

The command reads every run manifest under `docs/proof/experiments/`. It prints
`pre-schema` for a registered manifest with its registered content, `ok` for a manifest
that validates, and `REFUSED` with each finding otherwise. In this change it prints
three `pre-schema` lines and exits 0. The default-lane suite runs the same listing.

**What the register does not do.**

- **It is a tripwire and not a lock.** A change that adds a manifest and a register
  record together passes the listing. The suite writes the three records out
  literally, so such a change shows in review as a changed test.
- **It reads the files of the tree and not Git.** An untracked manifest is listed.
- **It lists a file by the exact name `run.v1alpha1.json`.** A manifest under another
  name, or under that name in another letter case, is not listed and not validated.
- **It does not judge a pre-schema manifest.** `tools.experiment_e01 --check` judges
  the two static runs, as before. No command judges the E01-D run again.
- **The E01 runner still writes the earlier shape.** `tools/experiment_e01` writes a
  manifest with this name and kind, in the shape of the first two. This change does not
  edit the runner, which two freeze revisions pin. So a new run of that runner would
  commit a manifest that the listing refuses. No such run can start today: the E01
  freeze refuses a new run until a later revision classifies an earlier edit. The
  change that next runs a static part must change the runner, add a schema version that
  describes a static run, or name its manifest otherwise.

## Versioning and compatibility

`apiVersion` and `kind` together are the compatibility axis. Four contracts now share
`inferops.io/v1alpha1`, and each is versioned independently. The classes are the
WorkloadContract's:

- **Compatible** - adding an optional member; adding a value to a vocabulary where the
  existing values behave as before; relaxing a pattern or raising a bound; adding a
  fixture for an existing rule; editorial changes to descriptions.
- **Conditionally compatible** - adding a semantic rule that refuses a document the
  schema accepts; registering or removing a caller profile revision; changing a
  canonical code, a rule identifier, or a field location of an existing refusal. A
  committed valid fixture stays valid unless the change says otherwise.
- **Breaking** - adding a required member; removing or renaming a member; removing a
  value from a vocabulary; narrowing a pattern or a bound so that a committed valid
  fixture fails; adding a result state or removing one; any member that lets a
  manifest carry a claim status, an achieved evidence level, a prompt, a response, or
  the content of an evidence file. The last is breaking although it accepts more
  documents, because it removes the separation that the document exists to keep.

A breaking change requires a new `apiVersion`, even at alpha maturity. A committed
manifest of a run is evidence: a later version does not rewrite it. Only one version
exists, so the support window has nothing to apply to yet.

## Fixtures

[`contracts/experiment/examples/`](../../contracts/experiment/examples/README.md) holds
6 valid fixtures and 36 invalid ones. The valid fixtures together hold each of the five
result states. Of the invalid fixtures, the schema alone refuses 22, and a semantic rule
refuses 14.
[`expected-rejections.json`](../../contracts/experiment/examples/invalid/expected-rejections.json)
states the code, the rule, and the field of each refusal, and the suite compares it
field by field.

**No fixture describes a run that executed.** Each valid fixture says so in its first
limitation. Each digest is one repeated character, except the caller profile digest,
which is the registered digest of RP-1 revision 1.

## Validation

```sh
# The schema, the fixtures, the validator, the listing, and this page.
uv run --locked python -m pytest tests/contracts/test_experiment_run_v1alpha1.py -q
# Validate a manifest that is not a committed fixture.
uv run --locked python -m tools.experiment_run check path/to/run.v1alpha1.json
```

The command exits 0 when nothing is refused, 3 when a rule refuses a manifest or the
register, 2 when its arguments are not usable, and 4 when it fails in a way that no rule
names. It reads files and writes nothing.

The suite is in the default lane. It is static evidence, C0: it reads committed files
and files it writes under a temporary directory. It executes no run.
[The validation record](../proof/contracts/v2-s5-002-pr1-validation.md) states what was
run for this change.

## What this contract does not do

- **It is not evidence of a run.** A manifest states what a run was. The evidence is in
  the files it names.
- **Nothing writes a manifest.** A person or a later tool writes one. No experiment
  runner in this repository produces this shape.
- **Nothing reads one for analysis.** No tool computes a result from a manifest and its
  evidence files. (Since `V2-S5-004-PR2` [the replay tool](../testing/analysis-replay.md)
  computes figures from a manifest and its evidence files. It decides no result.)
- **It does not define the evidence layout.** It names evidence files by a path inside
  the run's directory. Which files a run holds, where run directories are, and how a
  directory is checked are not decided here. [The experiment evidence layout](../testing/experiment-evidence-layout.md)
  decides them, since `V2-S5-002-PR2`.
- **It does not define a role vocabulary.** One role has a meaning to a rule: `caller`.
  Every other role is a name that the writer chose. The evidence layout registers 13
  roles for a file of a run directory. The schema still accepts any role.
- **It does not describe a run that deploys nothing.** The environment, the release, the
  runtime image, and the model are required. The two static E01 runs have no value for
  them.
- **It does not describe a run of several parts.** One manifest has one experiment
  identifier and one result state.
- **It holds one fault and one caller profile.** A run with two faults is not
  describable in this version.
- **It registers no claim.** The claim and evidence register is unchanged, and no claim
  cites this schema.
- **It does not establish runtime behaviour.** A C0 record does not establish that a
  release serves, that a fault was survived, or that a caller saw an answer.
