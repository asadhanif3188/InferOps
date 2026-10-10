# V2-S5-001-PR1 validation

Status: **RP-1, the caller workload for reliability experiments, is defined as one
versioned profile, and a tool refuses a drift of it. This is static evidence at
C0.** The profile reuses the fixture, the generation settings, the client deadline,
and the success rule of the V1 load profile, and it changes none of them. It fixes
the concurrency at 2. No request was sent under RP-1, no runner reads the profile,
no cluster was read, and no claim was registered.

> [!IMPORTANT]
> **A profile is not evidence about a caller.** It states what a run sends. It
> does not state what a caller saw, because no caller ran. RP-1 is a reliability
> workload. It is not a representative production workload, an overload test, or
> a benchmark, and a run under it cannot support C3.

| Property | Value |
|---|---|
| Date | 2026-10-10 |
| Base | `fbd4b36af0a3eb6ef7efa55a41eac39ebe826438`, the merge of pull request #135 |
| Branch | `test/v2-s5-001-rp1-profile` |
| Commits | The first commit: the profile, the tool, the suite, the pages, and the correction of one stale sentence. A second commit: the corrections of an independent review, and the default lane |
| Host | One Windows workstation, Git Bash (GNU bash 5.2.26); Python 3.12.12 from `uv` 0.9.16 |
| Evidence level | C0. Every check reads committed files, or sends a request to a loopback server in the same process |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, or experiment freeze record was added or changed |

## What was inspected in the V1 load harness

The V1 load harness is [`tools/llm_load`](../../../tools/llm_load/), and its
profile is
[`deploy/serving/load/llm-load-profile.v1.json`](../../../deploy/serving/load/llm-load-profile.v1.json),
version `1.0.0`. Each value below was read from that file or from that code, and
the suite holds each one.

| Semantics | V1 value | Where it is | RP-1 |
|---|---|---|---|
| Prompt fixture | `llm-load-single-turn-v1`, one `user` message | `fixture` in the profile | Reused, member for member |
| Request | `POST /v1/chat/completions`, body of `model`, `messages`, and `stream: false` | `fixture` in the profile, and `send_one` in the code | Reused |
| Content type | `application/json` | `http_transport` in the code | Reused |
| Request headers | `X-InferOps-Request-ID` and `X-InferOps-Correlation-ID` | `send_one` in the code | The names are reused. The values are not fixed |
| Output-token target | `maxOutputTokens` 128 | `generation` in the profile. The request does not send it | Reused |
| Randomness | `temperature` 0. No sampling seed | `generation` in the profile, and the runtime arguments | Reused. The profile states `samplingSeed: not-set` |
| Context and slots | `contextSizeTokens` 4096, `parallelSlots` 1 | `generation` in the profile | Reused |
| Client deadline | 150,000 ms, above the API's 120,000 ms | `timeouts` in the profile | Reused |
| Late answer | The outcome `timeout`, whatever the answer says | `classify` in the code | Stated as `answerAfterDeadline: not-a-success` |
| Success | HTTP 200, adapter `real`, the served model, usage counts | `success` in the profile | Reused. `requiredRuntimeName` is not carried |
| Connection | A new connection for each request, no redirect, no proxy variable, no retry | `http_transport` in the code | Reused, as four stated values |
| Loop | Closed | `run_phase` in the code | Reused |
| Concurrency | Levels at 1, 2, and 4 | `levels` in the profile | Changed: one fixed concurrency, 2 |
| Target | A loopback forward on `127.0.0.1` | `target` in the profile | Changed: the API Service, from inside the cluster |
| Warm-up, duration, request ceiling | 3 requests; 180 s or 60 requests for each level | `warmup` and `measured` in the profile | Not carried |
| Stop after five transport errors in a row | `MAXIMUM_CONSECUTIVE_TRANSPORT_ERRORS`, 5 | A constant in the code | Not carried |

**The V1 fixture did not change.** The pinned digest of the V1 file is
`4dc0fe4a4217f035875fcddbdb99b75246f3a74188d5eca8b4dbbec8f57081c5`. The file at
the `v1.0.0` tag has that digest:

```sh
git show v1.0.0:deploy/serving/load/llm-load-profile.v1.json | tr -d '\r' | sha256sum
```

This change does not edit the V1 file, the V1 tool, or the V1 suite.

## What changed

| File | Change |
|---|---|
| [`deploy/serving/reliability/rp-1-profile.v1.json`](../../../deploy/serving/reliability/rp-1-profile.v1.json) | New. The profile, revision 1 |
| [`tools/reliability_profile/`](../../../tools/reliability_profile/) | New. The loader, 16 rules, the registered digest of revision 1, and the `check` command |
| [`tests/serving/test_reliability_profile.py`](../../../tests/serving/test_reliability_profile.py) | New. 107 tests |
| [`docs/serving/reliability-workload-rp-1.md`](../../serving/reliability-workload-rp-1.md) | New. Each value, its origin, the dispositions, the rules, and the limits |
| [`v2-s5-001-pr1-profile-cases-driver.txt`](v2-s5-001-pr1-profile-cases-driver.txt), [`v2-s5-001-pr1-profile-cases.json`](v2-s5-001-pr1-profile-cases.json) | New. One driver and its output: the committed files and seven changed copies |
| `tools/baseline_profile/core.py`, its committed comparison record, [its page](../../environment/single-runtime-baseline-profile.md), and `README.md` | Three sentences said that no caller profile exists in this repository. This change makes that false, so they now say that the tool reads no caller profile. The record was written again by `python -m tools.baseline_profile --write`, and two lines of it differ |
| `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, [the load generation guide](../../serving/llm-load-generation.md), [the proof index](../README.md), the test inventory and its page | One row or one paragraph each for the profile, the tool, and the suite |
| `tests/testing/test_test_inventory.py` | The table of written numbers ended at eighty. The inventory now counts eighty-one modules that defend no claim, so the table goes to ninety |

## What the change was asked to reach, and what it reached

| Criterion of the story | State in this change |
|---|---|
| The exact prompt, output, timeout, randomness, and request settings of RP-1 are versioned | Reached, at C0. The profile states each one, with `profileRevision: 1` and a registered content digest. The suite holds each one against the V1 load profile and the V1 code |
| Concurrency is fixed at 2 unless formally revised | Reached, at C0. The value is a constant of the tool, the rule `rp1-concurrency-not-fixed` refuses 1, 3, and 4, and [the page](../../serving/reliability-workload-rp-1.md#if-the-v1-load-profile-changes) states the steps of a revision. The registered digest is a tripwire and not a lock |
| The runner targets the API Service, and not a pod or a backend that a port-forward selects | Pending. No runner exists. The profile states the target, and the rule `rp1-target-not-api-service` holds the statement. No check inspects a runner |
| Caller results are machine-readable and safe to publish | Pending. No result exists. The profile states that a result holds no prompt text and no completion text |
| The runner is scoped to an experiment, and is not a permanent serving dependency | Pending. No runner exists. This change adds no chart template, no value, and no desired-state file |

## Decisions taken in this change

1. **RP-1 is a new file, and the V1 profile is not edited.** The V1 profile is
   released at `v1.0.0`, and its digest is in committed raw records. RP-1 pins it.
2. **RP-1 states no warm-up, no duration, and no request ceiling.** A warm-up
   would leave caller requests out of the caller record. The duration belongs to
   the experiment that selects the profile.
3. **RP-1 states no stop rule.** The V1 stop after five transport errors in a row
   would end a record at the moment a reliability experiment observes.
4. **RP-1 fixes what a success is, and not the names of the failures.** The format
   of a caller result is not decided here.
5. **`requiredRuntimeName` is not carried.** The V1 harness requires it of the
   identity probe before any load, and not of an answer.
6. **The sampling seed is stated as `not-set`.** No committed runtime argument and
   no chart file sets one. The text of two completions was not compared.
7. **A revision is registered by digest in the tool.** The profile cannot hold its
   own digest. A change that edits the profile and the digest together passes.

## The negative controls

**The driver.** [`v2-s5-001-pr1-profile-cases-driver.txt`](v2-s5-001-pr1-profile-cases-driver.txt)
gives the loader the committed files and seven changed copies, in an empty
directory outside the working tree. It edits no committed file. Its output is
[`v2-s5-001-pr1-profile-cases.json`](v2-s5-001-pr1-profile-cases.json).

```sh
PYTHONPATH=. uv run --locked python -B docs/proof/serving/v2-s5-001-pr1-profile-cases-driver.txt <empty directory>
```

| Case | Result | Rule that refuses |
|---|---|---|
| The committed files | `ACCEPTED` | None |
| One space after the last byte of the V1 file | `REFUSED` | `rp1-source-pin-differs` |
| Another prompt in the V1 file | `REFUSED` | `rp1-source-pin-differs` |
| A V1 client deadline of 100,000 ms, below the API's | `REFUSED` | `rp1-source-refused`: the V1 loader refuses the file |
| RP-1 with concurrency 4 | `REFUSED` | `rp1-concurrency-not-fixed` |
| RP-1 with `representativeWorkload: true` | `REFUSED` | `rp1-purpose-overstated` |
| RP-1 with `target.portForward: true` | `REFUSED` | `rp1-target-not-api-service` |
| RP-1 with `maxOutputTokens` 64 | `REFUSED` | `rp1-generation-differs` |

**The suite.** One parametrized test replaces one member of the profile and
requires the rule that names the drift, in 57 cases:

| Rule | Cases |
|---|---:|
| `rp1-members-unsupported` | 3 |
| `rp1-identity-unsupported` | 4 |
| `rp1-purpose-overstated` | 8 |
| `rp1-source-pin-differs` | 4 |
| `rp1-concurrency-not-fixed` | 5 |
| `rp1-target-not-api-service` | 4 |
| `rp1-request-differs` | 10 |
| `rp1-generation-differs` | 6 |
| `rp1-connection-differs` | 5 |
| `rp1-timeout-differs` | 2 |
| `rp1-success-differs` | 4 |
| `rp1-results-hold-content` | 2 |

Other tests hold the four remaining rules: `rp1-profile-unreadable` with three
files, `rp1-source-refused` with one changed V1 file, `rp1-disposition-incomplete`
in five cases, and `rp1-revision-digest-differs` with one changed
reason. An unknown member is refused in each of the 10 sections.

**Each refusal above is an expected refusal.** It is recorded apart from the
positive control: the committed files load, and `check` exits 0.

## Validation at the first commit

From the repository root, in Git Bash.

| Command | Result |
|---|---|
| `uv run --locked python -m tools.reliability_profile check` | Exit 0. RP-1 revision 1, both digests, 2 closed-loop workers |
| `uv run --locked python -m tools.reliability_profile run` | Exit 2. The command has one mode |
| `uv run --locked python -m tools.llm_load check` | Exit 0. The V1 profile is accepted by its own loader |
| `uv run --locked python -m tools.baseline_profile --check` | Exit 0. Six lines, each `OK` |
| `uv run --locked python -m tools.generated_release --check` | Exit 0 |
| `uv run --locked python -m pytest -q tests/serving/test_reliability_profile.py tests/serving/test_llm_load.py` | 305 passed |
| `uv run --locked python -m pytest -q tests/domain/test_baseline_profile.py` | 191 passed |
| `uv run --locked python -m pytest -q tests/testing tests/security` | 9146 passed, 1 skipped |
| `uv run --locked ruff check .` | `All checks passed!` |
| `uv run --locked ruff format --check .` | `695 files already formatted` |
| `uv run --locked python -m mypy` | `Success: no issues found in 379 source files` |
| `git diff --check` | No output |

The default lane was not run at the first commit. It is recorded below.

## What stayed as it was

- **The V1 load profile, the V1 load tool, and the V1 load suite.** No byte of
  them changed.
- **Released V1 evidence and history.** No file under `docs/proof/` that an
  earlier change added is edited, except one row of
  [the proof index](../README.md), which gains a link.
- **The experiment freeze records, their registry, and each committed run.**
- **The chart, the contracts, the bindings, the desired-state files, the Argo CD
  files, and the scripts.** This change adds no template and no value.
- **The comparison of the single-runtime baseline.** Its result is still
  `COMPARABLE`, it still lists the caller profile as unresolved, and its
  eligibility is still `not-established`. Two sentences of its record changed.

The comparison command is `git diff --stat fbd4b36af0a3eb6ef7efa55a41eac39ebe826438`,
with the same base for `git diff --name-status`.

## Privacy and publicability

The diff was read for private planning text, future work that is not public,
local paths, secrets, account identifiers, and generated machine state. The
profile repeats one prompt, which the V1 profile already publishes. The driver
writes its copies outside the working tree, and its output holds no path.

## What this does not establish

- **Nothing about a caller.** No request was sent under RP-1.
- **Nothing about a runner.** No tool sends RP-1. The target, the caller location,
  and the connection behaviour are statements, and no check inspects a runner.
- **That a delivered release holds the generation settings.** The V1 loader
  compares them with the chart defaults and the real-profile values. No check
  reads the values of an environment's desired state.
- **A deterministic output.** The settings are fixed. No two completions were
  compared.
- **Capacity, overload, or a threshold.** Concurrency 2 is a choice.
- **A representative workload.** A run under RP-1 cannot support C3.
- **That the registered digest prevents a change.** It makes a change visible in
  two files.
- **Eligibility of the single-runtime baseline for an experiment.** No check
  gives both sides one revision of RP-1.
