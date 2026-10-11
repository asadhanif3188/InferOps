# ExperimentRun examples

Fixtures for [the ExperimentRun v1alpha1 schema](../experiment-run.v1alpha1.schema.json).
Every file under `valid/` must validate, and every file under `invalid/` must be
refused. A failure either way is a defect in the schema, the validator, the fixture, or
the change that broke one of them.

These are **contract examples, not records of a run.** Each was written by hand. No run
executed, no evidence file sits beside a fixture, and no fixture is evidence about the
environment, the release, or the model it names. A fixture is JSON and cannot hold a
comment, so each valid fixture says this in its first limitation, and
[`invalid/expected-rejections.json`](invalid/expected-rejections.json) says what each
invalid fixture is refused for.

**The identities are placeholders.** The experiment identifiers begin with `EXAMPLE-`.
The freeze record path names no committed file. Every digest and every commit is one
repeated character. One identity is real: the caller profile is
[RP-1](../../../docs/serving/reliability-workload-rp-1.md) revision 1 with its
registered content digest, because a semantic rule refuses any other.

## Valid fixtures

| Fixture | Result state | What it demonstrates |
|---|---|---|
| [`valid/fault-injected-passed.json`](valid/fault-injected-passed.json) | `PASSED` | A registered fault, injected, under RP-1, with a caller record, and a verified cleanup |
| [`valid/fault-injected-failed.json`](valid/fault-injected-failed.json) | `FAILED` | The same run with a criterion that did not hold. The intended level is still `C2`: a failed run is not a lower level |
| [`valid/refused-before-the-procedure.json`](valid/refused-before-the-procedure.json) | `REFUSED` | A precondition failed. The fault is registered and not injected, no evidence file exists, and no cleanup is required |
| [`valid/aborted-after-the-fault.json`](valid/aborted-after-the-fault.json) | `ABORTED` | An abort condition after the fault, with an incomplete cleanup that states what it left |
| [`valid/inconclusive-without-a-caller-record.json`](valid/inconclusive-without-a-caller-record.json) | `INCONCLUSIVE` | A run under RP-1 whose caller record was lost. It decides no criterion, so the caller-evidence rule does not bind it |
| [`valid/no-fault-and-no-caller-profile.json`](valid/no-fault-and-no-caller-profile.json) | `PASSED` | A run whose frozen record registers no fault and no caller profile, each with its reason |

## Invalid fixtures

Every file under `invalid/` must be refused for exactly the canonical error code, rule
identifier, and field location that
[`invalid/expected-rejections.json`](invalid/expected-rejections.json) records. The
suite compares them field by field on every run.

### Refused by the schema alone

The suite runs one draft 2020-12 validator, the Python one.

| Fixture | Refused for |
|---|---|
| [`invalid/unsupported-api-version.json`](invalid/unsupported-api-version.json) | A version this schema does not define. The one fixture with the code `version-unsupported` |
| [`invalid/not-an-experiment-run.json`](invalid/not-an-experiment-run.json) | Another `kind` |
| [`invalid/missing-required-values.json`](invalid/missing-required-values.json) | Five required members left out |
| [`invalid/evidence-level-as-result-state.json`](invalid/evidence-level-as-result-state.json) | `C2` as a result state |
| [`invalid/result-state-as-evidence-level.json`](invalid/result-state-as-evidence-level.json) | `FAILED` as an evidence level |
| [`invalid/claim-status-in-run.json`](invalid/claim-status-in-run.json) | A claim status in two places, and an achieved evidence level |
| [`invalid/content-in-run.json`](invalid/content-in-run.json) | A prompt, a response body, and the content of an evidence file |
| [`invalid/mutable-revisions.json`](invalid/mutable-revisions.json) | A branch name, an abbreviated commit, and an image tag |
| [`invalid/malformed-digests.json`](invalid/malformed-digests.json) | A prefix, uppercase hexadecimal, and a digest of 40 characters |
| [`invalid/evidence-outside-the-run.json`](invalid/evidence-outside-the-run.json) | A parent segment, a leading slash, and a backslash in an evidence path |
| [`invalid/times-not-in-utc-form.json`](invalid/times-not-in-utc-form.json) | An offset, a time with no zone, and a date alone |
| [`invalid/injected-fault-without-target.json`](invalid/injected-fault-without-target.json) | An injected fault with no target and no time |
| [`invalid/no-fault-with-a-target.json`](invalid/no-fault-with-a-target.json) | No registered fault, and a fault type and a target |
| [`invalid/fault-not-injected-without-reason.json`](invalid/fault-not-injected-without-reason.json) | A registered fault that was not injected, with no reason |
| [`invalid/states-without-reason.json`](invalid/states-without-reason.json) | An `INCONCLUSIVE` result and an incomplete cleanup, each with no reason |
| [`invalid/caller-profile-in-part.json`](invalid/caller-profile-in-part.json) | A caller profile with no revision and no digest |
| [`invalid/caller-profile-absent-and-named.json`](invalid/caller-profile-absent-and-named.json) | No caller profile applies, and one is named |
| [`invalid/wrong-json-types.json`](invalid/wrong-json-types.json) | Four values of the wrong JSON type |
| [`invalid/values-out-of-range.json`](invalid/values-out-of-range.json) | Four values outside a bound |
| [`invalid/unsupported-vocabulary.json`](invalid/unsupported-vocabulary.json) | An environment, a result state, and a cleanup state outside their vocabularies |
| [`invalid/cleanup-not-required-with-items-left.json`](invalid/cleanup-not-required-with-items-left.json) | A cleanup that was not required, and an item that it left |
| [`invalid/values-with-a-final-line-feed.json`](invalid/values-with-a-final-line-feed.json) | Three values that end with a line feed. The first commit of this change accepted each |

### Refused by a semantic rule

The schema accepts each of these. [`tools/experiment_run`](../../../tools/experiment_run/core.py)
refuses it. A consumer that holds only the schema file does not get these refusals.

| Fixture | Rule |
|---|---|
| [`invalid/time-that-is-no-instant.json`](invalid/time-that-is-no-instant.json) | `run-time-not-an-instant` |
| [`invalid/run-ends-before-it-starts.json`](invalid/run-ends-before-it-starts.json) | `run-time-order-inverted` |
| [`invalid/fault-outside-the-run.json`](invalid/fault-outside-the-run.json) | `run-fault-time-outside-run` |
| [`invalid/passed-without-the-fault.json`](invalid/passed-without-the-fault.json) | `run-passed-without-registered-fault` |
| [`invalid/refused-after-the-fault.json`](invalid/refused-after-the-fault.json) | `run-refused-after-fault` |
| [`invalid/caller-profile-unregistered.json`](invalid/caller-profile-unregistered.json) | `run-caller-profile-unregistered` |
| [`invalid/caller-profile-digest-differs.json`](invalid/caller-profile-digest-differs.json) | `run-caller-profile-digest-differs` |
| [`invalid/caller-concurrency-differs.json`](invalid/caller-concurrency-differs.json) | `run-caller-concurrency-differs` |
| [`invalid/caller-evidence-missing.json`](invalid/caller-evidence-missing.json) | `run-caller-evidence-missing` |
| [`invalid/decided-without-evidence.json`](invalid/decided-without-evidence.json) | `run-decided-without-evidence` |
| [`invalid/evidence-path-twice.json`](invalid/evidence-path-twice.json) | `run-evidence-path-duplicated` |
| [`invalid/manifest-as-its-own-evidence.json`](invalid/manifest-as-its-own-evidence.json) | `run-evidence-names-the-manifest` |
| [`invalid/credential-shaped-value.json`](invalid/credential-shaped-value.json) | `run-value-credential-shaped` |
| [`invalid/host-path-in-text.json`](invalid/host-path-in-text.json) | `run-text-host-path` |

**`credential-shaped-value.json` holds no credential.** It holds `AKIAIOSFODNN7EXAMPLE`,
the placeholder key identifier of the AWS documentation, which grants nothing, and one
ordinary word behind the prefix `sk-`. **`host-path-in-text.json` holds no real path.**
Both of its paths are invented.

The rules, what each establishes, and what no rule holds are in
[the contract document](../../../docs/contracts/experiment-run.md).
