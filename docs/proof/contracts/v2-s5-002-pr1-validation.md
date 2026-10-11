# V2-S5-002-PR1 validation

Status: **ExperimentRun `v1alpha1` is a published schema with fixtures, an offline
validator, and a register of the three run manifests that were committed before it. No
run executed in this change, and no run produced a manifest of the schema.** Nothing
writes a manifest, and nothing reads one for analysis. The evidence is static, C0: the
suite reads committed files and files that it writes under a temporary directory. No
claim was registered. Two independent reviews read the first commit. They found that
each pattern accepted a value with a final line feed under the Python validator, that
a `PASSED` run could name no evidence file, that the page called its authoring form
the decision's when it departs from it, and that several sentences said more than the
code does: see [what the independent reviews found](#what-the-independent-reviews-found).

> [!IMPORTANT]
> **Nothing here is a result of an experiment.** Each fixture is a hand-written document
> with placeholder identities. The suite shows that the schema, the fixtures, the
> validator, the register, and the pages agree. It does not show that a run happened,
> that an evidence file exists, or that an identity in a manifest is the identity of
> anything.

| Property | Value |
|---|---|
| Date | 2026-10-11 |
| Base | `a82e4b7`, the merge of pull request #137 |
| Branch | `feat/v2-s5-002-experiment-run-schema` |
| Commits | `833b91c`: the schema, the fixtures, the validator, the register, the suite, and the pages. A second commit: the corrections of the two independent reviews, and the default lane on the final tree |
| Host | One Windows workstation, Git Bash (GNU bash 5.2.26); Python 3.12.12 from `uv` 0.9.16 |
| Container engine and cluster | Not used. No cluster was contacted |
| Evidence level | C0, static |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, or experiment freeze record was added or changed |

## What changed

The counts are of the second commit.

| Path | Change |
|---|---|
| [`contracts/experiment/experiment-run.v1alpha1.schema.json`](../../../contracts/experiment/experiment-run.v1alpha1.schema.json) | New. The schema: 15 top-level members, 47 leaves, and 12 patterns |
| [`contracts/experiment/examples/`](../../../contracts/experiment/examples/README.md) | New. 6 valid fixtures, 36 invalid fixtures, the manifest of expected refusals, and a page |
| [`contracts/experiment/compatibility/pre-schema-experiment-runs.v1alpha1.json`](../../../contracts/experiment/compatibility/pre-schema-experiment-runs.v1alpha1.json) | New. The register of the three run manifests committed before the schema |
| [`tools/experiment_run/core.py`](../../../tools/experiment_run/core.py), `__main__.py`, `__init__.py` | New. The validator, the repository listing, and the commands `check` and `repository`. 14 semantic rules, and 4 rules of reading and listing |
| [`tests/contracts/test_experiment_run_v1alpha1.py`](../../../tests/contracts/test_experiment_run_v1alpha1.py) | New. 103 test functions, 318 cases |
| [`docs/contracts/experiment-run.md`](../../contracts/experiment-run.md) | New. The contract document |
| `CHANGELOG.md`, `contracts/CHANGELOG.md`, `README.md`, `docs/proof/README.md`, `docs/proof/experiments/README.md` | One entry or one sentence each |
| `contracts/README.md` | Two table rows, two paragraphs, a layout block, a command, and two added sentences |
| `docs/contracts/README.md` | One table row, one paragraph, and three changed sentences |
| `docs/contracts/rendered-workload-release.md`, `contracts/release/examples/invalid/not-a-rendered-release.yaml` | One word each: "three contracts" share the `apiVersion` became "four". The second is a comment in a fixture, and the second commit corrected it |
| `docs/testing/test-inventory.md` and `.v1alpha1.json` | One row, and two written counts: eighty-three modules with no claim, and nine modules in the contract layer |
| `.github/secret-scanning-allowlist.md` | The new suite and the three files that hold a published placeholder. The count of suites became twelve. `.gitleaks.toml` is not changed |

Not changed: the three run manifests of E01, their freeze records, the freeze registry,
their review records, `tools/experiment_e01`, `tools/experiment_freeze`,
`tools/evidence_index`, the claim and evidence register, every ledger, the evidence
index, the dashboard, the RP-1 profile and its registered digest, the runner, the
canonical error model in `tools/contract_validation`, the schemas of the three earlier
contracts, ADR 0003, the chart, and the desired state.

## What the change was asked to reach, and what it reached

| Asked | Reached | How it is held |
|---|---|---|
| The experiment, the run, and the spec revision | `metadata.experimentId`, `metadata.runId`, `metadata.spec` (freeze record path, revision number, content digest), and `metadata.executingRevision` | Required by the schema. No rule reads the freeze registry |
| The provider and the environment | `environment.binding`, `environment.provider`, `environment.kubernetesVersion`, `environment.nodeCount` | Required by the schema. The provider is a name with no vocabulary |
| The contract, render, Git, runtime, and model identities | `release.contractSha256`, `release.releaseId`, `release.helmValuesSha256`, `release.desiredStateRevision`, `runtime.image`, `model` | Required by the schema. Each digest, each commit, and the image is in a form that names one content. No rule compares one with a release |
| The RP profile | `callerProfile`: RP-1, its revision, its content digest, and its concurrency, or a reason why none applies | The schema, and three semantic rules that hold the values to the registered revision |
| The fault type, target, and time | `fault`: registered or not, the type, injected or not, the target, and the time | The schema's conditions, and three semantic rules |
| The result state | `result.state`, one of five | The schema |
| Evidence references | `evidence.files`: role, path inside the run's directory, and SHA-256 | The schema, and four semantic rules. No rule opens a file |
| Limitations | `limitations` and `doesNotEstablish`, each with at least one statement | The schema |
| The cleanup state | `cleanup.state`, with a reason when it is not verified | The schema |
| Fixtures | 6 valid and 36 invalid | The suite holds each to its published refusal |
| Compatibility rules | The three classes of change, and the rules for the three earlier manifests | The contract document. The register and the listing hold the second |
| Claim status and evidence level separate from the run result | Three vocabularies with no shared value; one member for the state, one for the intended level, none for a claim | The suite: 5 levels refused as a state, 5 states refused as a level, 4 claim statuses refused as a state and as a member at 4 positions, and 25 pairs accepted. A claim status as a word in a role or a statement is not refused |
| `FAILED` and `INCONCLUSIVE` are not evidence levels | The schema refuses each in `evidenceLevel.intended`. A valid fixture is `FAILED` and intends `C2` | The suite, and the fixture `result-state-as-evidence-level.json` |

### The criteria of the parent change

| Criterion | State |
|---|---|
| ExperimentRun `v1alpha1` or an equivalent is versioned and validated | Reached. The schema is versioned by `apiVersion` and `kind`, and the default lane validates each fixture |
| It records the experiment, the spec, the environment, the release, the profile, the fault, the result, the evidence, and the limitations | Reached, as members of the schema. No run has recorded one |
| The raw evidence layout is deterministic, hashable, and public-safe | **Pending. Not in this change.** This change names an evidence file by a path inside the run's directory and by a digest. It defines no layout, and nothing computes or compares a digest of an evidence file |
| `PASSED`, `FAILED`, `INCONCLUSIVE`, `REFUSED`, and `ABORTED` are explicit run states | Reached. They are the vocabulary of `result.state`, and the valid fixtures hold each |

## Decisions taken in this change

Each of these is a choice that this change made.
[The contract document](../../contracts/experiment-run.md) states each, except the
reason of decision 5 and decision 13, which are stated here only.

1. **The schema takes `inferops.io/v1alpha1` and `ExperimentRun`, which three committed
   manifests already state.** The three E01 run manifests were written with no schema.
   They do not conform, and they are evidence, so they are not edited. A register names
   each by path and content digest, and every other file named `run.v1alpha1.json`
   under `docs/proof/experiments/` must validate. The other choice was a new
   `apiVersion` for the first published schema, which would leave `v1alpha1` with no
   definition. The cost of the choice taken is that `apiVersion` and `kind` do not tell
   the two shapes apart.
2. **The schema is in `contracts/experiment/`, and its validator is a tool of its own,
   `tools/experiment_run`.** The structural layer reuses the canonical error model of
   `tools/contract_validation` and does not edit it. The 14 semantic rules and the 4
   rules of reading and listing are in the new tool, so the canonical rule table, which
   a test holds to the WorkloadContract document, did not change.
3. **The manifest describes a run against a delivered release.** The environment, the
   release, the runtime image, and the model are required. A run that deploys nothing
   cannot be described. The two static E01 runs are of that kind.
4. **The run states an intended evidence level and assigns none to itself.** The frozen
   record intends a level. The register states the level of an evidence record. The
   schema has no member for an achieved level.
5. **The frozen record is named by path, revision number, and content digest, and the
   executing commit is a separate member.** A freeze record cannot name the commit that
   merges it, so one Git revision cannot stand for both.
6. **The caller profile and the fault are never left out.** Each is a required member
   that either names its subject or states, with a reason, that none applies. An absent
   member cannot be told from a forgotten one.
7. **A manifest that names RP-1 is held to the registered digest and to a concurrency
   of 2.** The rule reads the revisions that `tools/reliability_profile` registers.
8. **Only `PASSED` and `REFUSED` are bound to the injection of the fault.** A `PASSED`
   run injected its registered fault, and a `REFUSED` run injected none. A `FAILED`,
   `INCONCLUSIVE`, or `ABORTED` run is not bound: the frozen record decides.
9. **No rule binds the result state to the cleanup state.** The frozen record decides
   whether an incomplete cleanup bears on a result.
10. **One role has a meaning: `caller`.** A `PASSED` or `FAILED` run under a caller
    profile names a file with that role. No other role vocabulary is defined.
11. **The semantic layer runs only on a document that the schema accepts.**
12. **A manifest is authored as JSON, and that departs from ADR 0003.** The decision
    accepts YAML as the authoring form and rejects JSON authoring. The fixtures of the
    three earlier contracts are YAML. A run manifest is written by a run, beside JSON
    evidence, and the three committed ones are JSON. ADR 0003 is not edited, and no
    decision record states the departure. The first commit said "applied unchanged".
13. **The fixture for the host-path rule holds a drive-letter path and a path under
    `/root/`.** The security baseline refuses a path under a user directory in any
    committed file, so the suite joins those two forms at run time.
14. **Each pattern ends with `$(?!\n)`.** Since the second commit. Python's `$` also
    matches before a final line feed. The schemas of the three earlier contracts end
    their patterns with `$` alone, have the same property, and are not edited here.
15. **A cleanup that was not required lists nothing that it left, and a verified
    cleanup states no reason.** Since the second commit. A verified cleanup can list
    what it left.
16. **A `PASSED` or `FAILED` run names at least one evidence file.** Since the second
    commit.

## The negative controls

Each line is a case that the suite gives, and what must refuse it. The counts are of
the second commit.

| Case | Refused by |
|---|---|
| Each of 5 evidence levels as a result state | `value-not-permitted` at `$.result.state` |
| Each of 5 result states as an evidence level | `value-not-permitted` at `$.evidenceLevel.intended` |
| Each of 4 claim statuses as a result state, and as a `claimStatus` member at 4 positions | `value-not-permitted`, and `field-unknown` |
| 22 structural fixtures | The bare schema, and the validator with the published code, rule, and field |
| 14 semantic fixtures | The validator only. The bare schema accepts each |
| A final line feed after each of 33 values of one valid manifest, in 27 members | `value-malformed`, by the bare schema too |
| A model digest with a `sha256:` prefix | `value-malformed` |
| 8 times of the right form that name no instant | `run-time-not-an-instant` |
| A run that ends before it starts, by half a second | `run-time-order-inverted` |
| A fault one millisecond before the run starts | `run-fault-time-outside-run` |
| A `PASSED` and a `FAILED` run with no evidence file | `run-decided-without-evidence` |
| A `FAILED` run under a caller profile with no caller record | `run-caller-evidence-missing` |
| A profile `RP-2` with another digest and concurrency | `run-caller-profile-unregistered`, once |
| A verified cleanup with a reason | `value-not-permitted` at `$.cleanup` |
| JSON `true` as a revision number, and `1` as a flag | `value-wrong-type` |
| 5 statements with a credential-shaped word | `run-value-credential-shaped`, and the message repeats no word of 12 characters or more |
| A run identifier that is a published placeholder key | `run-value-credential-shaped` |
| 5 statements with a host path | `run-text-host-path` |
| 9 files: 2 that state a member twice, and 7 that are not a JSON object or are not JSON. An absent file, and a file that is not UTF-8 | `run-document-unreadable` |
| An edited pre-schema manifest, and an absent one | `run-pre-schema-record-edited`, `run-pre-schema-record-missing` |
| A fourth manifest of the earlier shape | The schema: it is not registered |
| 12 defects of the register, and an absent register | `run-pre-schema-register-unreadable` |
| 4 argument lists that the command cannot use | Exit status 2 |

**What the suite measures and does not refuse.** Each of these is a test that asserts
that the case passes:

- a lowercase secret with no published prefix, and a `glpat-` value behind an asterisk
  or behind an equals sign. A placeholder key behind an equals sign is refused, by its
  opaque shape;
- six host paths that are not one of the four refused forms: under `/var/lib`, under
  `/mnt`, under `~`, a network share, `/root.` with no slash after it, and a drive
  letter with no separator;
- a claim status as the name of a role, as the name of a provider, and as words in a
  statement, and a statement that holds a prompt and a response;
- a `FAILED`, `INCONCLUSIVE`, or `ABORTED` run whose registered fault was not injected;
- a verified cleanup that lists an item that it left;
- two evidence paths that one directory cannot hold together;
- a model digest in the form of this schema, which is not the WorkloadContract's form;
- a register that gains a record together with a manifest.

One test asserts two cases of ordinary text that the heuristics refuse: a long word in
mixed case with a digit, and one letter before `:/`.

## Validation at the first commit

Each command ran in Git Bash on the host above, from the repository root.

| Command | Result |
|---|---|
| `uv run --locked python -m pytest tests/contracts/test_experiment_run_v1alpha1.py -q` | 291 passed |
| `uv run --locked python -m tools.experiment_run repository` | Exit 0. Three `pre-schema` lines, and `manifests  3: 3 pre-schema, 0 conforming, 0 refused` |
| `uv run --locked python -m tools.experiment_run check contracts/experiment/examples/valid/*.json` | Exit 0. Six `ok` lines |
| `uv run --locked ruff format --check .` | 709 files already formatted |
| `uv run --locked ruff check .` | All checks passed |
| `uv run --locked python -m mypy` | No issues found in 388 source files |
| `uv run --locked python -m pytest -q` | 20,738 passed, 0 failed, 40 skipped, 14 deselected by the default marker expression, in 48 min 6 s. See the note below |
| `uv run --locked python -m tools.ci_gates expected-failures` | Exit 0 |
| `git diff --check` | No output |

**That default lane started before the tree was final.** While it ran, the formatter
rewrote the three new Python files, one assertion had its two operands exchanged for
the linter, and the `CHANGELOG.md` entry and this record were written. So that run did
not read the final text of those two pages. After it, the four test directories that
read pages and committed data ran again. The result rows of this record were written
during and after that second run, so no run read them:

| Command | Result |
|---|---|
| `uv run --locked python -m pytest tests/testing tests/security tests/contracts tests/architecture -q` | 13,641 passed, 0 failed, 14 skipped, in 31 min 37 s |

## What the independent reviews found

Two reviews read commit `833b91c`, read-only, on 2026-10-11. One read the schema, the
validator, and the suite, and ran cases against them. One read each statement against
the code and recounted each figure. Each reviewer is a separate session of the
automated assistant that wrote the change. It is not a person, and it is not
independent of the tooling. The second review reported that the working tree changed
while it read: the corrections of the first review were being made. It checked its
findings again against an export of `833b91c`.

### What the schema and the code got wrong

| Finding | Correction |
|---|---|
| **Each pattern accepted a value with a final line feed.** The Python validator applies a pattern by search, and Python's `$` matches before a final line feed. A digest, a commit, a run identifier, an image, and a path each validated with one. An evidence path of the manifest's name and a line feed passed the rule against the manifest as its own evidence, and a repeated path with a line feed passed the rule against a repeated path. An ECMA-262 engine refuses the same documents, so two validators gave two verdicts | Each of the 12 patterns ends with `$(?!\n)`. One fixture, and one test over 33 values of a valid manifest |
| **A `PASSED` or `FAILED` run under no caller profile could name no evidence file** | A fourteenth semantic rule, `run-decided-without-evidence`, with one fixture |
| **A cleanup that was not required could list what it left, and a verified cleanup could state a reason** | The schema refuses both. One fixture and one test. A verified cleanup that lists what it left validates, and the page says so |
| **The listing found a manifest by a pattern that ignores letter case on Windows and not on Linux.** One tree gave two listings on two hosts | The name is compared as text. One test |
| **`check` printed a path with a line break as two lines** | A character that is not printable is printed as a question mark |
| **The command's page said that exit status 2 covers arguments that are "not usable".** A path that names no file gives 3 | The page states which case gives which status |

### What the suite got wrong

| Finding | Correction |
|---|---|
| `test_the_command_writes_nothing` called the listing function and compared file names | It runs both commands and compares the bytes of each file |
| The test of the structural rule table read no fixture column | It holds each named fixture to its rule |
| `test_an_absent_register_is_refused` asserted no rule | It asserts the rule |
| A test named "only a passed run is bound to the injection". A `REFUSED` run is bound too | Renamed |
| A test's description said that it measures that a new E01 run is refused. It compares three constants | The description says what it compares |
| A test named for "what the document names" read no document | Renamed |
| No test gave a leap second or year 0000 | Two cases added. The validator refuses both |

### What the first commit said, and what is true

| The first commit said | What is true |
|---|---|
| "ADR 0003, applied unchanged", beside "Authoring form: JSON" | ADR 0003 accepts YAML authoring and rejects JSON authoring. The manifest departs from it, and the page now says so and why |
| "Any draft 2020-12 validator reaches the same verdict" | False at the first commit, by the line feed. The suite runs one validator. The page says that another is expected to agree |
| "A claim status is refused wherever it is written" | A `claimStatus` member is refused in each object. A role named `certified` and a statement that says a claim is certified validate. A test measures it |
| "No prompt, no completion, and no response body" | No member is defined for one. No rule reads a statement for one. A test measures it |
| The model is recorded "by the identities the WorkloadContract pins", and "every identity agrees with the document it is copied from" | The contract writes the artifact digest with a `sha256:` prefix, and the manifest writes it without. A test measures it |
| "`C3` needs an accepted representative preregistration and a qualifying execution" | Those words are not on the evidence-levels page. The contract page now cites that page and restates no condition |
| "A refusal never repeats a value read out of the document" | The suite holds it for each value of 12 characters or more of each invalid fixture |
| The time form is "the reliability caller record's" | The schema accepts no fraction or one to six digits. The caller record writes three |
| A repository path "cannot carry a personal filesystem path" | It cannot hold an absolute path. A relative path that names a user directory validates |
| "Every other run manifest under `docs/proof/experiments` must validate" | Every other file named exactly `run.v1alpha1.json` there. A manifest under another name is not listed |
| The suite measures "a published prefix behind an asterisk or an equals sign" as not refused | That holds for the `glpat-` value. The placeholder key behind an equals sign is refused |
| This record said "one row, one entry, or one paragraph each" for seven pages | `contracts/README.md` gained more, and so did `docs/contracts/README.md`. The table above states each |
| This record said that each decision is stated in the contract document | Two were stated here only |
| This record said "each in an immutable form" of the identities | The model identifier is a name |
| This record said that one file holds the placeholder key | Three files hold it: the fixture, the manifest of expected refusals, and the page of the examples. The pattern rule covers each |
| A fixture comment of the RenderedWorkloadRelease said that three contracts share the `apiVersion` | Four. Corrected |
| `docs/contracts/README.md` called two schemas "the two schemas published before their consumer", beside a third | "The first two" |
| The valid `INCONCLUSIVE` fixture gave the reason that its caller record "ends before the fault", and listed no caller record | The reason says that the record was lost |

### Noted, and not changed

- **The text heuristics refuse some ordinary text.** A long word in mixed case with a
  digit, and one letter before `:/`. A writer must reword the statement. The page and
  one test state both.
- **Two evidence paths that one directory cannot hold validate, and so does a path
  that is a device name on Windows.** The evidence layout is a later change.
- **`check` prints the path that it was given.** An absolute path that a caller types
  is printed back.
- **A finding for an absent registered manifest prints the path from the register.**
  The register's own check holds that path to the form of a repository path.
- **The refusal test reads values of 12 characters or more.** A shorter value, such as
  a state, is also a word of the schema, and a message that names a permitted value
  would match it.
- **The schemas of the three earlier contracts accept a final line feed** under the
  Python validator. This change does not edit them.

The reviews could not verify: the figures of the default lane, which they did not run;
that a symbolic link is handled, for want of the privilege on the host; anything on
Linux; and that the secret scanner reports nothing.

## Validation at the second commit

Each command ran on the tree of the second commit, before it was committed.

| Command | Result |
|---|---|
| `uv run --locked python -m pytest tests/contracts/test_experiment_run_v1alpha1.py -q` | 318 passed |
| `uv run --locked python -m tools.experiment_run repository` | Exit 0. Three `pre-schema` lines, and `manifests  3: 3 pre-schema, 0 conforming, 0 refused` |
| `uv run --locked ruff format --check .` | 709 files already formatted |
| `uv run --locked ruff check .` | All checks passed |
| `uv run --locked python -m mypy` | No issues found in 388 source files |
| `uv run --locked python -m tools.ci_gates expected-failures` | Exit 0 |
| `git diff --check` | No output |

## The default lane

`uv run --locked python -m pytest -q`, from the repository root, on the tree of the
second commit before it was committed, with each correction above in place:

| Result | Count |
|---|---:|
| Passed | 20,769 |
| Failed | 0 |
| Skipped | 40 |
| Deselected by the default marker expression | 14 |
| Time | 35 min 59 s |

The figures of this table and of the table before it were written after the lane
started, so the lane did not read them. The lane ran on the Windows host above. It
contacts no cluster and reads no model byte. This record does not list the reason of
each skip. The hosted lane on Linux ran no part of this change before the push.

Not run: the Helm, Terraform, and image gates of the workflow. This change edits no
chart, no Terraform file, no image file, and no script. The secret scanner was not run
on this host: see [privacy and publicability](#privacy-and-publicability).

## Privacy and publicability

- **No private planning text is in the change.** The diff was read for planning file
  names, private prompts, later change identifiers, and host paths. It names one change
  identifier, `V2-S5-002-PR1`. It names later work as "a later change".
- **No experiment that is not published is named.** The fixtures use the identifiers
  `EXAMPLE-E1` and `EXAMPLE-E2`. The one real experiment that the change names is
  V2-E01, whose records are committed.
- **No host path.** The security baseline's test of personal paths passes over the new
  files.
- **One published placeholder, in three files outside the exempted paths.**
  `credential-shaped-value.json`, the manifest of expected refusals, and the page of
  the examples hold `AKIAIOSFODNN7EXAMPLE`, the key identifier of the AWS
  documentation. An existing pattern rule of `.gitleaks.toml` covers that value in any
  path. The suite is under `tests/contracts/`, which the path allowlist covers.
  `.gitleaks.toml` is not changed. **The scanner was not run on this host**, so that
  the existing rule covers the new files is read from the configuration and is not
  observed.
- **No prompt, completion, or response text.** One invalid fixture holds two short
  invented strings in members that the schema refuses, and one test holds two more in
  a statement.

## What this does not establish

- That a run executed, on any provider.
- That a manifest of this schema can be written by a tool. Nothing writes one.
- That an evidence file exists, or has the digest that a manifest states.
- That an identity in a manifest is the identity of a release, a binding, a runtime
  image, a model, or a freeze record.
- That a result state is the one that the frozen criteria give.
- That a run under RP-1 sent RP-1. The rule compares a stated digest with a registered
  one.
- That a caller's result is independent of readiness or of the delivery controller.
  The manifest holds no readiness state and no state of the delivery controller, and
  it names the caller's own record by a role. It observes nothing.
- That a validator in another language gives the verdicts of the suite. The suite runs
  one.
- Anything about `C3` or `C4`. The schema accepts both values and checks no condition
  of either.
- Runtime behaviour. A C0 record does not establish that a release serves, that a
  fault was survived, or that a caller saw an answer.
- Availability, a service-level objective, tolerance of the loss of a pod, a node, a
  zone, or a region, an overload threshold, or a cost.
