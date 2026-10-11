# V2-S5-002-PR1 validation

Status: **ExperimentRun `v1alpha1` is a published schema with fixtures, an offline
validator, and a register of the three run manifests that were committed before it. No
run executed in this change, and no run produced a manifest of the schema.** Nothing
writes a manifest, and nothing reads one for analysis. The evidence is static, C0: the
suite reads committed files and files that it writes under a temporary directory. No
claim was registered.

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
| Host | One Windows workstation, Git Bash (GNU bash 5.2.26); Python 3.12.12 from `uv` 0.9.16 |
| Container engine and cluster | Not used. No cluster was contacted |
| Evidence level | C0, static |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, or experiment freeze record was added or changed |

## What changed

| Path | Change |
|---|---|
| [`contracts/experiment/experiment-run.v1alpha1.schema.json`](../../../contracts/experiment/experiment-run.v1alpha1.schema.json) | New. The schema: 15 top-level members and 47 leaves |
| [`contracts/experiment/examples/`](../../../contracts/experiment/examples/README.md) | New. 6 valid fixtures, 33 invalid fixtures, the manifest of expected refusals, and a page |
| [`contracts/experiment/compatibility/pre-schema-experiment-runs.v1alpha1.json`](../../../contracts/experiment/compatibility/pre-schema-experiment-runs.v1alpha1.json) | New. The register of the three run manifests committed before the schema |
| [`tools/experiment_run/core.py`](../../../tools/experiment_run/core.py), `__main__.py`, `__init__.py` | New. The validator, the repository listing, and the command `check` and `repository` |
| [`tests/contracts/test_experiment_run_v1alpha1.py`](../../../tests/contracts/test_experiment_run_v1alpha1.py) | New. 91 test functions, 291 cases |
| [`docs/contracts/experiment-run.md`](../../contracts/experiment-run.md) | New. The contract document |
| `contracts/README.md`, `contracts/CHANGELOG.md`, `docs/contracts/README.md`, `CHANGELOG.md`, `README.md`, `docs/proof/README.md`, `docs/proof/experiments/README.md` | One row, one entry, or one paragraph each |
| `docs/contracts/rendered-workload-release.md` | One word: "three contracts now share" the `apiVersion` became "four" |
| `docs/testing/test-inventory.md` and `.v1alpha1.json` | One row, and two written counts: eighty-three modules with no claim, and nine modules in the contract layer |
| `.github/secret-scanning-allowlist.md` | The new suite and the one fixture that hold a published placeholder. The count of suites became twelve. `.gitleaks.toml` is not changed |

Not changed: the three run manifests of E01, their freeze records, the freeze registry,
their review records, `tools/experiment_e01`, `tools/experiment_freeze`,
`tools/evidence_index`, the claim and evidence register, every ledger, the evidence
index, the dashboard, the RP-1 profile and its registered digest, the runner, the
canonical error model in `tools/contract_validation`, the chart, and the desired state.

## What the change was asked to reach, and what it reached

| Asked | Reached | How it is held |
|---|---|---|
| The experiment, the run, and the spec revision | `metadata.experimentId`, `metadata.runId`, `metadata.spec` (freeze record path, revision number, content digest), and `metadata.executingRevision` | Required by the schema. No rule reads the freeze registry |
| The provider and the environment | `environment.binding`, `environment.provider`, `environment.kubernetesVersion`, `environment.nodeCount` | Required by the schema. The provider is a name with no vocabulary |
| The contract, render, Git, runtime, and model identities | `release.contractSha256`, `release.releaseId`, `release.helmValuesSha256`, `release.desiredStateRevision`, `runtime.image`, `model` | Required by the schema, each in an immutable form. No rule compares one with a release |
| The RP profile | `callerProfile`: RP-1, its revision, its content digest, and its concurrency, or a reason why none applies | The schema, and three semantic rules that hold the values to the registered revision |
| The fault type, target, and time | `fault`: registered or not, the type, injected or not, the target, and the time | The schema's conditions, and three semantic rules |
| The result state | `result.state`, one of five | The schema |
| Evidence references | `evidence.files`: role, path inside the run's directory, and SHA-256 | The schema, and three semantic rules. No rule opens a file |
| Limitations | `limitations` and `doesNotEstablish`, each with at least one statement | The schema |
| The cleanup state | `cleanup.state`, with a reason when it is not verified | The schema |
| Fixtures | 6 valid and 33 invalid | The suite holds each to its published refusal |
| Compatibility rules | The three classes of change, and the rules for the three earlier manifests | The contract document. The register and the listing hold the second |
| Claim status and evidence level separate from the run result | Three vocabularies with no shared value; one member for the state, one for the intended level, none for a claim | The suite: 5 levels refused as a state, 5 states refused as a level, 4 claim statuses refused as a state and as a member at 4 positions, and 25 pairs accepted |
| `FAILED` and `INCONCLUSIVE` are not evidence levels | The schema refuses each in `evidenceLevel.intended`. A valid fixture is `FAILED` and intends `C2` | The suite, and the fixture `result-state-as-evidence-level.json` |

### The criteria of the parent change

| Criterion | State |
|---|---|
| ExperimentRun `v1alpha1` or an equivalent is versioned and validated | Reached. The schema is versioned by `apiVersion` and `kind`, and the default lane validates each fixture |
| It records the experiment, the spec, the environment, the release, the profile, the fault, the result, the evidence, and the limitations | Reached, as members of the schema. No run has recorded one |
| The raw evidence layout is deterministic, hashable, and public-safe | **Pending. Not in this change.** This change names an evidence file by a path inside the run's directory and by a digest. It defines no layout, and nothing computes or compares a digest of an evidence file |
| `PASSED`, `FAILED`, `INCONCLUSIVE`, `REFUSED`, and `ABORTED` are explicit run states | Reached. They are the vocabulary of `result.state`, and the valid fixtures hold each |

## Decisions taken in this change

Each of these is a choice that this change made. Each is stated in
[the contract document](../../contracts/experiment-run.md).

1. **The schema takes `inferops.io/v1alpha1` and `ExperimentRun`, which three committed
   manifests already state.** The three E01 run manifests were written with no schema.
   They do not conform, and they are evidence, so they are not edited. A register names
   each by path and content digest, and every other run manifest must validate. The
   other choice was a new `apiVersion` for the first published schema, which would
   leave `v1alpha1` with no definition. The cost of the choice taken is that
   `apiVersion` and `kind` do not tell the two shapes apart.
2. **The schema is in `contracts/experiment/`, and its validator is a tool of its own,
   `tools/experiment_run`.** The structural layer reuses the canonical error model of
   `tools/contract_validation` and does not edit it. The 13 semantic rules and the 4
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
12. **Fixtures are JSON.** The fixtures of the three earlier contracts are YAML. A run
    manifest is JSON, as the three committed ones are.
13. **The fixture for the host-path rule holds a drive-letter path and a path under
    `/root/`.** The security baseline refuses a path under a user directory in any
    committed file, so the suite joins those two forms at run time.

## The negative controls

Each line is a case that the suite gives, and what must refuse it.

| Case | Refused by |
|---|---|
| Each of 5 evidence levels as a result state | `value-not-permitted` at `$.result.state` |
| Each of 5 result states as an evidence level | `value-not-permitted` at `$.evidenceLevel.intended` |
| Each of 4 claim statuses as a result state, and as a `claimStatus` member at 4 positions | `value-not-permitted`, and `field-unknown` |
| 20 structural fixtures | The bare schema, and the validator with the published code, rule, and field |
| 13 semantic fixtures | The validator only. The bare schema accepts each |
| 6 times of the right form that name no instant | `run-time-not-an-instant` |
| A run that ends before it starts, by half a second | `run-time-order-inverted` |
| A fault one millisecond before the run starts | `run-fault-time-outside-run` |
| A `FAILED` run under a caller profile with no caller record | `run-caller-evidence-missing` |
| A profile `RP-2` with another digest and concurrency | `run-caller-profile-unregistered`, once |
| JSON `true` as a revision number, and `1` as a flag | `value-wrong-type` |
| 5 statements with a credential-shaped word | `run-value-credential-shaped`, and the message repeats no long word |
| A run identifier that is a published placeholder key | `run-value-credential-shaped` |
| 5 statements with a host path | `run-text-host-path` |
| 9 files: 2 that state a member twice, and 7 that are not a JSON object or are not JSON. An absent file, and a file that is not UTF-8 | `run-document-unreadable` |
| An edited pre-schema manifest, and an absent one | `run-pre-schema-record-edited`, `run-pre-schema-record-missing` |
| A fourth manifest of the earlier shape | The schema: it is not registered |
| 12 defects of the register, and an absent register | `run-pre-schema-register-unreadable` |
| 4 argument lists that the command cannot use | Exit status 2 |

**What the suite measures and does not refuse.** A lowercase secret with no published
prefix, a published prefix behind an asterisk or an equals sign, four forms of host
path, a `FAILED` run whose registered fault was not injected, and a register that gains
a record together with a manifest. Each is a test that asserts the case passes.

## Validation

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

**The default lane started before the tree was final.** While it ran, the formatter
rewrote the three new Python files, one assertion had its two operands exchanged for
the linter, and the `CHANGELOG.md` entry and this record were written. So that run did
not read the final text of those two pages. After it, the four test directories that
read pages and committed data ran again. The result rows of this record were written
during and after that second run, so no run read them:

| Command | Result |
|---|---|
| `uv run --locked python -m pytest tests/testing tests/security tests/contracts tests/architecture -q` | 13,641 passed, 0 failed, 14 skipped, in 31 min 37 s |

The lane ran on the Windows host above. It contacts no cluster and reads no model
byte. This record does not list the reason of each skip. The hosted lane on Linux ran
no part of this change before the push.

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
- **One published placeholder.** `credential-shaped-value.json` holds
  `AKIAIOSFODNN7EXAMPLE`, the key identifier of the AWS documentation, which an
  existing pattern rule of `.gitleaks.toml` covers. The suite is under
  `tests/contracts/`, which the path allowlist covers. `.gitleaks.toml` is not
  changed. **The scanner was not run on this host**, so that the existing rule covers
  the new fixture is read from the configuration and is not observed.
- **No prompt, completion, or response text.** One invalid fixture holds two short
  invented strings in members that the schema refuses.

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
- Anything about `C3` or `C4`. The schema accepts both values and checks no condition
  of either.
- Runtime behaviour. A C0 record does not establish that a release serves, that a
  fault was survived, or that a caller saw an answer.
- Availability, a service-level objective, tolerance of the loss of a pod, a node, a
  zone, or a region, an overload threshold, or a cost.
