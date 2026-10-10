# V2-S5-001-PR1 validation

Status: **RP-1, the caller workload for reliability experiments, is defined as one
versioned profile, and a tool refuses a drift of it. This is static evidence at
C0.** The profile reuses the fixture, the generation settings, the client deadline,
and four of the five members of the success rule of the V1 load profile. It changes
the target, the levels, and the boundary sentence, and it fixes the concurrency at
2. No request was sent under RP-1, no runner reads the profile, no cluster was
read, and no claim was registered. Two independent reviews read the first commit.
They found that one test could not fail, that the loader accepted four kinds of
file that it must refuse, and that several sentences said more than the repository
shows: see [what the independent reviews found](#what-the-independent-reviews-found).

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
| Commits | `c77c49d5`: the profile, the tool, the suite, the pages, and the correction of one stale statement. A second commit: the corrections of the two independent reviews, and the default lane |
| Host | One Windows workstation, Git Bash (GNU bash 5.2.26); Python 3.12.12 from `uv` 0.9.16 |
| Evidence level | C0. Every check reads committed files, or sends a request to a loopback server on the same host |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, or experiment freeze record was added or changed |

## What was inspected in the V1 load harness

The V1 load harness is [`tools/llm_load`](../../../tools/llm_load/), and its
profile is
[`deploy/serving/load/llm-load-profile.v1.json`](../../../deploy/serving/load/llm-load-profile.v1.json),
version `1.0.0`. Each value below was read from that file or from that code. The
last column says whether the suite of this change holds the V1 value. A row that
says "Read" was read by a person and by a reviewer, and no test of this change
holds it.

| Semantics | V1 value | Where it is | RP-1 | Held by the suite |
|---|---|---|---|---|
| Prompt fixture | `llm-load-single-turn-v1`, one `user` message | `fixture` in the profile | Reused, member for member | Yes |
| Request | `POST /v1/chat/completions`, body of `model`, `messages`, and `stream: false` | `fixture` in the profile, and `send_one` in the code | Reused | Yes |
| Content type | `application/json` | `http_transport` in the code | Reused | Yes, since the second commit |
| Request headers | `X-InferOps-Request-ID` and `X-InferOps-Correlation-ID` | `send_one` in the code | The names are reused. The values are not fixed | Yes |
| Output-token target | `maxOutputTokens` 128 | `generation` in the profile. The request does not send it | Reused | Yes |
| Randomness | `temperature` 0. No sampling seed | `generation` in the profile, and the runtime arguments | Reused. The profile states `samplingSeed: not-set` | Yes |
| Context and slots | `contextSizeTokens` 4096, `parallelSlots` 1 | `generation` in the profile | Reused | Yes |
| Client deadline | 150,000 ms | `timeouts` in the profile | Reused | Yes |
| The deadline is above the API's 120,000 ms | A rule of the V1 loader | `validate_profile` in the code | Through the V1 loader | Read. The driver holds one case |
| Late answer | `timeout` from the required adapter, and `identity-refused` from another adapter | `classify` in the code | Stated as `answerAfterDeadline: not-a-success` | Yes, one case of each |
| Success | HTTP 200, adapter `real`, the served model, usage counts | `success` in the profile | Reused. `requiredRuntimeName` is not carried | Yes |
| A success has a first choice | In the code | `classify` in the code | Stated as `requireChoice: true`, since the second commit | Yes |
| Connection | A new connection for each request, no redirect, no proxy variable, no retry | `http_transport` in the code | Reused, as four stated values | Yes. The retry case is one `503` |
| Loop | Closed | `run_phase` in the code | Reused | Read |
| Concurrency | Levels at 1, 2, and 4 | `levels` in the profile | Changed: one fixed concurrency, 2 | The level `c2` only |
| Target | A loopback forward on `127.0.0.1` | `target` in the profile | Changed: the API Service, from inside the cluster | Read |
| Warm-up, duration, request ceiling | 3 requests; 180 s or 60 requests for each level | `warmup` and `measured` in the profile | Not carried | Read |
| Stop after five transport errors in a row | `MAXIMUM_CONSECUTIVE_TRANSPORT_ERRORS`, 5 | A constant in the code | Not carried | Read |

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
| [`tests/serving/test_reliability_profile.py`](../../../tests/serving/test_reliability_profile.py) | New. 107 tests at the first commit, and 122 at the second |
| [`docs/serving/reliability-workload-rp-1.md`](../../serving/reliability-workload-rp-1.md) | New. Each value, its origin, the dispositions, the rules, and the limits |
| [`v2-s5-001-pr1-profile-cases-driver.txt`](v2-s5-001-pr1-profile-cases-driver.txt), [`v2-s5-001-pr1-profile-cases.json`](v2-s5-001-pr1-profile-cases.json) | New. One driver and its output: the committed files and seven changed copies |
| `tools/baseline_profile/core.py`, its committed comparison record, [its page](../../environment/single-runtime-baseline-profile.md), and `README.md` | Seven places said that no caller profile exists: three in the tool, three on the page, and one in the README. This change makes that false. Six now say that the tool, or the comparison, reads no caller profile, and one row of the page names RP-1. The record was written again by `python -m tools.baseline_profile --write`, and two lines of it differ |
| `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, [the load generation guide](../../serving/llm-load-generation.md), [the proof index](../README.md), the test inventory and its page | One row or one paragraph each for the profile, the tool, and the suite |
| `tests/testing/test_test_inventory.py` | The table of written numbers ended at eighty. The inventory now counts eighty-one modules that defend no claim, so the table goes to ninety |

## What the change was asked to reach, and what it reached

| Criterion of the story | State in this change |
|---|---|
| The exact prompt, output, timeout, randomness, and request settings of RP-1 are versioned | Reached, at C0. The profile states each one, with `profileRevision: 1` and a registered content digest. The suite holds each one against the V1 load profile or the V1 code |
| Concurrency is fixed at 2 unless formally revised | Reached, at C0. The value is a constant of the tool, the rule `rp1-concurrency-not-fixed` refuses 1, 3, and 4, and [the page](../../serving/reliability-workload-rp-1.md#if-the-v1-load-profile-changes) states the steps of a revision. The registered digest is a tripwire and not a lock |
| The runner targets the API Service, and not a pod or a backend that a port-forward selects | Pending. No runner exists. The profile states the target, and the rule `rp1-target-not-api-service` holds the statement. No check inspects a runner |
| Caller results are machine-readable and safe to publish | Pending. No result exists. The profile states that a result holds no prompt text and no completion text |
| The runner is scoped to an experiment, and is not a permanent serving dependency | Pending. No runner exists. This change adds no chart template, no value, and no desired-state file |

## Decisions taken in this change

1. **RP-1 is a new file, and the V1 profile is not edited.** The V1 profile is
   released at `v1.0.0`, and its digest is in committed raw records. RP-1 pins it.
2. **RP-1 states no warm-up, no duration, and no request ceiling.** The V1 harness
   keeps its warm-up requests out of every level. RP-1 has no phase that is kept
   out. The duration belongs to the experiment that selects the profile.
3. **RP-1 states no stop rule and no abort.** The V1 harness stops after five
   transport errors in a row, and it aborts when an answer names another adapter.
   The experiment that selects the profile states its abort conditions.
4. **RP-1 fixes what a success is, and not the names of the failures.** The format
   of a caller result is not decided here.
5. **`requiredRuntimeName` is not carried.** The V1 harness requires it of the
   identity probe before any load, and not of an answer.
6. **The sampling seed is stated as `not-set`.** No committed runtime argument and
   no chart file sets one. The text of two completions was not compared.
7. **A revision is registered by digest in the tool.** The profile cannot hold its
   own digest. A change that edits the profile and the digest together passes.
8. **The connection behaviour and plain HTTP are stated as what a runner must
   meet.** They are the behaviour of the V1 transport: a new connection for each
   request, no redirect, no proxy variable, and no retry. A new connection for
   each request bears on how a Service selects a pod for a request. No run
   observed that.
9. **`requireChoice` is a member that the V1 file does not have.** The V1
   classification requires a first choice of a success, in code. The second commit
   states it in the profile, so that the success rule of the profile is the whole
   V1 rule for one answer.

## The negative controls

**The driver.** [`v2-s5-001-pr1-profile-cases-driver.txt`](v2-s5-001-pr1-profile-cases-driver.txt)
gives the loader the committed files and seven changed copies. It was given an
empty directory under the temporary directory of the host, and it edits no
committed file. Its output is
[`v2-s5-001-pr1-profile-cases.json`](v2-s5-001-pr1-profile-cases.json). The
driver ran again on the tree of the second commit, and its output is the same
bytes.

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

**The suite.** One parametrized test replaces one member of the profile, or adds
one, and requires the rule that names the drift. It has 65 cases at the second
commit, and it had 57 at the first:

| Rule | Cases |
|---|---:|
| `rp1-members-unsupported` | 4 |
| `rp1-identity-unsupported` | 4 |
| `rp1-purpose-overstated` | 8 |
| `rp1-source-pin-differs` | 4 |
| `rp1-concurrency-not-fixed` | 5 |
| `rp1-target-not-api-service` | 4 |
| `rp1-request-differs` | 11 |
| `rp1-generation-differs` | 8 |
| `rp1-connection-differs` | 5 |
| `rp1-timeout-differs` | 2 |
| `rp1-success-differs` | 8 |
| `rp1-results-hold-content` | 2 |

Other tests hold the four remaining rules: `rp1-profile-unreadable` with five
files, `rp1-source-refused` with two changed V1 files, `rp1-disposition-incomplete`
in five cases, and `rp1-revision-digest-differs` with one changed reason. One of
the five disposition cases calls a helper of the loader directly, because the V1
loader of this tree refuses the V1 file that the case needs. An unknown member is
refused in each of the 10 sections, and a member that the file states twice is
refused in two cases.

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

The default lane was not run at the first commit.

## What the independent reviews found

Two reviews read the first commit, and neither wrote it. One read the tool and
the suite, changed one line of the V1 transport or of the loader at a time in a
copy, and ran the suite on each copy. One checked each sentence of the pages, the
record, the changelog, and the commit message against the files. Neither found a
wrong value in the profile, a wrong count of rules, cases, or tests, a wrong
digest, a private text, or work of another change. The digest of revision 1 moved
in the second commit, from `853b6e92…deb22` to `ff3cbab5…1c1c3`, because the
profile gained one member. No run used the first digest.

### What the suite got wrong

| Finding | Correction |
|---|---|
| The proxy test could not fail. The V1 transport builds its opener when its module is imported, and the test set the variables after that. The review removed the handler that ignores proxies, and the test passed | The test now sends each request from a new interpreter that starts with the variables set. The first interpreter is a control: the default opener of the standard library reads the variable, and its request does not arrive. The V1 suite has a test of the same shape, and this change does not edit it: see [noted, and not changed](#noted-and-not-changed) |
| The test named for the content type compared the profile with itself. The review changed the header of the V1 transport, and the test passed | The loopback server records the `Content-Type` header, and the test compares it with the profile |
| The count of two connections proved nothing. The loopback server spoke HTTP/1.0, which closes each connection whatever the client asks | The server speaks HTTP/1.1. The test holds the `Connection: close` header of each request and the count |
| The test of a V1 member with no registered disposition passed when its branch was removed: another branch gave the same rule and the same member name | The loader has one branch for the case, and the test requires the text of that branch |
| Three checks of a disposition entry had no test: the member set of an entry, a reason that is empty, and a value that is not a list | One test gives the loader four such values |
| Three test names said more than the test holds: "sends nothing", "ran as a level", and "a refused request". The seed test read exact arguments only, and one test had a parameter that it did not use | The three are renamed. The seed test also refuses an argument that starts with `--seed`, and the parameter is removed |

### What the tool got wrong

| Finding | Correction |
|---|---|
| The body was compared with Python equality. `"stream": 0` equals `false`, and `"temperature": 0.0` equals `0`. A profile with one of them was refused only by the revision digest | The body, the four generation values, and four success values are compared with the V1 file in value and in JSON type |
| A file that states one member twice was accepted, and the last one was used | The reader refuses it, with `rp1-members-unsupported` |
| A number of 5,000 digits and a file of 100,000 nested brackets raised `ValueError` and `RecursionError`, and not a refusal. So did such a V1 file | Each is `rp1-profile-unreadable`, or `rp1-source-refused` for the V1 file |
| The command had no answer for a failure that no rule names. It printed a traceback | Exit status 4, with one line and no detail of the failure |
| The command printed "stream false" and "usage required" as fixed text | It prints the two values of the loaded profile |
| Two conditions could not be false: a concurrency above the V1 ceiling, which 2 is not, and a request path that the V1 loader already holds | Both are removed |
| The profile did not state that a success has a first choice. The V1 classification requires one, so "RP-1 fixes what a success is" was not whole | `success.requireChoice`, a constant of the tool, held by a test against the V1 classification |

### What the first commit said, and what is true

| The first commit said | What is true |
|---|---|
| The profile "changes no value" of the V1 profile, and reuses "the success rule" | It registers three members as changed and one as reused in part. It reuses four of the five members of the success rule |
| "A change of one byte of the V1 file refuses RP-1", in five places | The digest is taken after each CRLF is replaced by LF. A change of line endings is accepted, and the review gave the loader such a file |
| A late answer gets "the outcome `timeout`, whatever the answer says" | A late answer that names another adapter gets `identity-refused`. The V1 classification reads the adapter first. No late answer is a success |
| "The suite holds each one", of 16 rows of V1 values | The review named seven values that no test held: the content type, the closed loop, the levels other than `c2`, the warm-up and the bounds, the transport stop, the loopback target, and the API deadline. The table above now says which rows a test holds |
| "Two rules of the V1 harness are in its code and not in its profile" | The review named four more. The page lists the ones that were read, and it says that the list is not a complete reading |
| "A result names the fixture identifier" | No result format exists, and the same page said that none is decided |
| Each member has one disposition: "reused, pinned, changed, or not carried" | There are five dispositions. `reused-in-part` was left out |
| "The loader applies 16 rules in this order" | A member of a wrong type is refused when the loader reads it, which can be after an earlier rule accepted the rest. The review gave the loader two drifts at one time, and a later rule answered |
| Rule 2 refuses a member of another type "in each section" | A `connection` value of another type is refused by rule 11, and an unknown member of the body by rule 9 |
| "One sentence", "a sentence", and "three sentences" said that no caller profile exists | Seven places said it, and two record lines repeat the tool |
| `check` "prints the same values" as the table, and "each value" | It prints the identity, both digests, and the main values |
| "The default lane … is recorded below", with no section below | The section is below since the second commit |
| With two runtime replicas, "a request can also wait when both requests reach one replica", and one slow request "does not stop every caller observation" | No record shows either. Both sentences are removed |
| "A warm-up would leave caller requests out of the caller record" | The V1 harness writes its warm-up requests to the raw record, and keeps them out of every level. The decision is restated |
| The loader "reads committed files and nothing else" | It reads the files that its arguments name. The default arguments name committed files |
| The registered connection values and plain HTTP were not listed as a decision | Decision 8 |

### Noted, and not changed

- **The V1 suite has a proxy test that sets the variables after the import.** The
  review showed that a test of that shape cannot fail. This change does not edit
  the V1 suite. The test of this change holds the same property of the V1
  transport in a new interpreter.
- **Three sentences say that the baseline record "lists each input that no
  committed file resolves"**, of the caller profile: two in the baseline tool and
  its page, and one in its suite. A committed file now states a caller profile.
  No committed file gives one revision of it to both sides, which is what the
  record lists as unresolved. The sentences are left as they are.
- **The loader reads a member when a rule needs it.** A profile with two drifts
  can be refused by the later rule. The page and the tool now say so. The order
  is not changed.
- **The retry case is one status.** The test gives the V1 transport a `503` and
  counts one request. It gives no connection failure and no timeout.
- **`ReliabilityProfile` takes some fields from the loaded V1 profile.** The loader
  has compared each of them with the profile document first.

## Validation at the second commit

| Command | Result |
|---|---|
| `uv run --locked python -m tools.reliability_profile check` | Exit 0. RP-1 revision 1, with the digest `ff3cbab5…1c1c3` |
| `uv run --locked python -m tools.llm_load check` | Exit 0 |
| `uv run --locked python -m tools.baseline_profile --check` | Exit 0. Six lines, each `OK` |
| `uv run --locked python -m tools.generated_release --check` | Exit 0 |
| `uv run --locked python -m tools.gitops_desired_state --check` | Exit 0 |
| `uv run --locked python -m pytest -q tests/serving/test_reliability_profile.py` | 122 passed |
| The driver of the negative controls | Exit 0. The output is the committed bytes |
| `uv run --locked ruff check .` | `All checks passed!` |
| `uv run --locked ruff format --check .` | `695 files already formatted` |
| `uv run --locked python -m mypy` | `Success: no issues found in 379 source files` |
| `git diff --check` | No output |

## The default lane

The lane ran once, on the tree of the second commit before this section was
written. After it ran, only this record changed: the section below and nothing
else.

```sh
uv run --locked python -m pytest -q -p no:cacheprovider
```

| Result | Value |
|---|---|
| Passed | 20,236 |
| Skipped | 37 |
| Deselected | 14: the layers that need a cluster or a model |
| Failed | 0 |
| Duration | 3,497.79 s |
| Exit | 0 |

The skipped tests were not read one by one in this change. A skip is not a pass.
After this section was written, `uv run --locked python -m pytest -q tests/testing
tests/security` ran again on this text, before its own result was written here:
9146 passed, 1 skipped.

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
second review compared the wording with the requirements that are not public,
and it found no copied text and no identifier of later work. The profile repeats
one prompt, which the V1 profile already publishes. The output of the driver
holds no path.

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
- **That the list of V1 rules in code is complete.** It names the rules that were
  read for this change.
