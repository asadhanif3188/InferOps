# `V1-S2-005` baseline tooling fix — change validation

| Field | Value |
|---|---|
| Date | 2026-09-03 |
| Scope | Fix the two defects that blocked the registered baseline, fix a third the acquired model exposed, execute the corrected experiment |
| Source branch | `fix/v1-s2-005-baseline-tooling-defects` |
| Base revision | `fbf34f1328760e2c4ad1f026fa96beb13575b624` |
| Fix commit | `d60407741101e3a2516870e40c869c91ab77ce40` |
| Evidence produced here | `local-real-cpu`, and it is a **positive** result |
| Real-runtime execution | Authorized and performed; all 33 requests succeeded |
| Measured baseline published | **Yes.** All five pre-registered thresholds met |

## Why this branch exists

`V1-S2-005-PR2` executed the experiment `V1-S2-005-PR1` registered and found it
could not succeed: every request was refused by the InferOps API before
reaching the runtime, and the command that runs the experiment could not have
returned a result even had the requests succeeded. That PR is documentation and
evidence only, by its own scope, and correctly did not touch product code; its
full failure evidence stands on branch `docs/v1-s2-005-local-baseline-results`
(commit `39c6237`), not yet merged.

This branch is the deliberate follow-up: fix what PR2 found, then execute the
corrected experiment for real. It is a separate branch from PR2's on purpose,
so PR2's record of the failure — and the reasoning behind it — is not disturbed
by the fix that came after it.

## What was fixed

### `B1` — the registered fixture violated the API's accepted surface

`deploy/serving/baseline/local-baseline.v1.json`'s `fixture.messages` carried a
`system` message and a `user` message.
[`src/inferops/api/validation.py`](../../../src/inferops/api/validation.py)
accepts exactly one message, whose role must be `user`, by design — the frozen
serving-adapter interface carries a single `prompt` and has no parameter a
conversation could be passed through without inventing a prompt format. The
experiment could not have succeeded on any host, with any model, at any speed.

Fix: fold the system instruction into the single user message the API accepts.
This is a correction to a pre-registered experiment, made after seeing it fail,
and it is disclosed as one — see
[the experiment record's correction section](v1-s2-005-local-baseline-experiment.md#correction-to-the-registered-fixture)
for the full reasoning. It is defended on one ground: the correction changes
whether the request is accepted, not what is measured once it is. No
generation setting, warm-up count, measured count, concurrency, duration bound,
or threshold changed.

Fix, closing the gap that let this reach an authorized run in the first place:
`load_experiment` now calls `inferops.api.validation.parse_chat_completion`
against the committed fixture body at load time — the same reader the API uses
at request time — and raises `BaselineError` if the API would refuse it. A
fixture the API would refuse now fails offline `check`
([`tools/serving_baseline/core.py`](../../../tools/serving_baseline/core.py),
`_validate`) rather than reaching an authorized run. Two tests were added: one
pins the committed fixture against the real validator directly
(`test_the_committed_fixture_is_accepted_by_the_real_api_validator`), one
confirms a two-message fixture is refused at load time
(`test_a_fixture_the_real_api_would_refuse_is_refused_offline`).

### `B2` — the run command could not terminate

`execute` runs its measurement inside an `on_ready` callback passed to
`tools.local_composition.run_foreground`. After the callback returns,
`run_foreground` calls `server.join()`
([`tools/local_composition/core.py:627`](../../../tools/local_composition/core.py#L627)),
which blocks until the server is stopped externally — correct for the
interactive `local_composition start` command, whose caller stops it by
interrupting the process, and wrong for a bounded run with no interrupt coming.

Fix: rather than change the shared composition module —
`tools.runtime_certification.certify` already depends on `run_foreground`'s
current attached-until-stopped behaviour for its own interactive use, and so
does `local_composition`'s own `start` command — `execute` now follows the
pattern `certify` already established for exactly this problem. `execute` wraps
the `server_factory` it hands to `compose` to capture the server(s)
`run_foreground` builds, and `on_ready`'s `finally` block requests each
captured server's stop before returning. When `run_foreground` reaches its own
`server.join()` afterward, the server is already stopping, so the call returns
instead of blocking.

Two tests were changed to inject a fake `server_factory` and assert
`request_stop` was called before `on_ready` returned — a hang would fail to
demonstrate this, so the assertion is meaningful rather than decorative.

Not touched, and deliberately: `tools/local_composition/core.py` itself.
`tools.runtime_certification` and `tests/api/test_local_real_composition.py`
depend on `run_foreground`'s existing behaviour and neither was touched or
needed to be; both pass unchanged (63 tests).

### `B3` — a security test could not see this run's own evidence

`tests/security/test_security_baseline.py::test_no_committed_file_is_a_model_artifact`
walks the filesystem and refuses a committed model-shaped file. Its
`IGNORED_PREFIXES` list omitted `.cache/`, which is exactly where the model
this branch needed to acquire lives, so the test reported the hash-verified
model artifact as a candidate for publication on the first host that had
actually run the documented acquisition — this session's earlier attempt on
`docs/v1-s2-005-local-baseline-results` found the same failure independently.

Fix: add `.cache/` to `IGNORED_PREFIXES`, and align `.gitignore`'s existing
bare `.cache` entry to the trailing-slash convention every sibling directory
entry in that file already uses (`.venv/`, `.mypy_cache/`, `dist/`, and so on).
The ignore behaviour is unchanged — a bare `.cache` pattern already ignored the
directory and everything under it — only the two files' conventions now match,
which is what `test_no_committed_file_is_generated_host_state` requires
(`prefix in ignore_rules`, an exact string match).

## What was executed, after the fix

| Command | Result |
|---|---|
| `python -m tools.serving_baseline check` | Exit `0`, and this time the offline check actually validates the fixture against the real API surface |
| `python -m tools.serving_baseline run --confirm-real-runtime` | **Exit `0`.** 33 of 33 requests succeeded; `raw.jsonl` and `summary.json` written; ordered cleanup completed with no interrupt |
| `python -m tools.serving_baseline summarize` | Regenerated `summary.json` from `raw.jsonl` identically |

Full results, provenance hashes, and the raw evidence are in
[the raw result record](v1-s2-005-baseline-raw-results.md). Headline: model load
269,079 ms (300,000 ms budget), 30 of 30 measured requests successful, P50
6,422 ms / P95 17,718 ms / P99 23,516 ms, 0.121 requests/s, 2.067 output
tokens/s. All five pre-registered thresholds (`T1`–`T5`) are met.

## Validation results

| Command | Result | Evidence boundary |
|---|---|---|
| `uv run --locked ruff check .` | Passed; all checks passed | Repository-static |
| `uv run --locked ruff format --check .` | Passed; 250 files already formatted | Repository-static |
| `uv run --locked python -m mypy` | Passed; no issues in 142 source files | Repository-static |
| `uv run --locked python -m tools.serving_baseline check` | Exit `0`, before and after the real fixture is proven to reach the API validator | `local-static`; confirmed by deliberately reintroducing the two-message fixture and observing `check` refuse it with the new error, then restoring the fix |
| `uv run --locked python -m pytest tests/serving/test_serving_baseline.py -q` | Passed; 109 tests (105 unchanged, 2 changed to assert `B2`'s fix, 2 new for `B1`) | Controlled synthetic baseline path |
| `uv run --locked python -m pytest tests/security/test_security_baseline.py -q` | Passed; 628 tests, with the model artifact present in the cache | Repository-static; confirms `B3`'s fix against the exact condition that exposed it |
| `uv run --locked python -m pytest tests/serving/test_runtime_certification.py tests/api/test_local_real_composition.py -q` | Passed; 63 tests, unchanged | Confirms `run_foreground` and `certify` are unaffected by the `B2` fix, which touches neither |
| `uv run --locked python -m pytest -q` | Passed; 5,431 passed, 25 skipped, 14 deselected | Full suite, model cache present; zero failures |
| `git diff --check` | Passed; no whitespace defect | Repository-static |

Both the security-suite and full-suite counts above are the state at this
commit — with this record's own file and the raw result record both present.
An intermediate run, taken after the code fix (`d604077`) but before this
documentation commit added those two files, read 626 and 5,429; the two extra
tests in each figure are a parametrized documentation check
(`test_a_reserved_term_appears_only_where_it_is_denied`) that discovers new
Markdown files under `docs/proof/`, not a change to any test file. The
independent review that follows re-ran both counts directly against this
commit and confirmed 628 and 5,431 exactly, which is why the final numbers
here match the review rather than the intermediate ones. `5,431` is four
higher than `V1-S2-005-PR1`'s recorded 5,427: two fixture tests this branch
adds directly, plus the two discovered by the parametrized check. Every
existing test that ran before this branch still passes; none was weakened to
make the fixes fit.

## Independent verification performed before publishing

Two claims in this record were checked rather than assumed, because an
unverified figure in a record like this is exactly the kind of overclaim this
project's evidence culture treats as a defect:

- **Percentile and throughput arithmetic.** `summary.json`'s `P50`, `P95`,
  `P99`, `requestsPerSecondMilli`, and `outputTokensPerSecondMilli` were
  independently recomputed from the 30 measured records in `raw.jsonl` using
  nearest-rank arithmetic and plain integer division, matching the algorithm in
  `tools/serving_baseline/core.py::summarize` without importing it. All five
  figures matched exactly.
- **The `T5` threshold.** A first draft of the raw result record stated `P99`
  was "more than seven times" `P50` and read that as exceeding the
  pre-registered ten-times bound. Recomputing the ratio directly
  (`23516 / 6422 = 3.66`) showed this was wrong in both the number and the
  conclusion: `T5` is met, with meaningful margin, not exceeded. The error was
  in prose written before the arithmetic was actually run, and it was caught
  before publication by doing the computation rather than trusting the
  sentence. All references to this ratio in both proof records were corrected
  to `3.66×`, `T5` **Met**.

## Public-information review

The reviewed change touches source, test, and configuration files in addition
to Markdown — unlike `V1-S2-005-PR2`, which was documentation-only by scope.
Every source and test change is reviewed above by defect (`B1`, `B2`, `B3`)
with its exact mechanism and line references; none introduces a personal
filesystem path, credential, prompt, completion, or private planning
reference. A pattern sweep of the full diff for Windows drive letters, the
private planning repository's name, host or account identifiers, and
credential-shaped strings returned zero matches.

The model artifact acquired for this run remains in the ignored workspace
cache (`.cache/inferops/models/`), untracked, and — as of this branch — that
directory is finally consistently ignored across both `.gitignore` and the
security suite's own filesystem walk.

## Acceptance criteria

Against the parent story `V1-S2-005`:

| Criterion | Status |
|---|---|
| Environment, model/runtime, request shape, warm-up, and duration are recorded | **Met** |
| P50/P95/P99, throughput, errors, load time, CPU/memory, and tokens where available are reported | **Met, with one named limitation.** All figures are reported; the CPU figure is reported alongside the explanation of why it understates actual load rather than omitted or silently accepted |
| Raw and summarized results are retained | **Met as designed**, for the first time — `raw.jsonl` and `summary.json` exist because `B2` no longer prevents `execute` from returning |
| Report states why results are not production benchmarks | **Met** |

**The parent story `V1-S2-005` can be considered complete once this branch and
`V1-S2-005-PR2`'s failure record both merge.** The failure record documents
what pre-registration is for; this branch documents the correction and the
measurement it enabled. Neither alone tells the whole story.

## Independent second-eye review

An independent review of both commits verified rather than trusted the fix and
the evidence. It called the real `inferops.api.validation.parse_chat_completion`
against the committed fixture directly and confirmed it is genuinely accepted;
reconstructed the two-message fixture in a scratch file (never touching the
committed descriptor) and confirmed `load_experiment` refuses it with the exact
error text this record quotes, proving the new offline gate is live rather than
decorative; confirmed `tools/local_composition/core.py` and `http_server.py`
carry no diff from `main`, so `B2`'s fix genuinely does not touch the shared
composition module; confirmed `tools.runtime_certification.certify` really does
use the identical capture/`request_stop`-in-`finally` pattern this fix claims as
precedent; confirmed the two modified tests would raise `TypeError` against the
pre-fix code, so they are regression tests rather than decoration; and
independently recomputed every percentile, hash, and token figure in the raw
result record from the files still present on this host, all exact.

It raised no critical, high, or medium finding, and one low one: the reported
throughput figures (121 req/1000s, 2067 tokens/1000s) are computed by integer
floor division rather than rounding, and a reader could mistake 121 for a
rounded 121.588 rather than a floored one. The convention was already stated
once, in [Throughput](v1-s2-005-baseline-raw-results.md#throughput); a second
mention was added there for a reader who starts elsewhere in the document.

The reviewer also flagged, correctly, that the security-suite and full-suite
counts this table originally reported (626, 5,429) were measured after the
code-fix commit but before this documentation commit added two new files that
a parametrized security test discovers — a real inconsistency between an
intermediate measurement and the committed state, now corrected above to the
counts the reviewer verified directly at this commit (628, 5,431). One thing
the reviewer explicitly could not verify and said so: the 801.97% live CPU
observation quoted in the raw result record has no artifact to check it
against, being a one-time reading from the original session; the reviewer
confirmed only that `sample_resources` is mechanically called between requests
rather than during them, which is consistent with the record's explanation
without proving the specific figure.

## Risks, assumptions, and limitations

- `T4`'s margin is real but not comfortable: 30.9 s against a 300 s budget on
  this run, against a cold-load figure 58.7 s **over** budget measured on the
  same host in the prior attempt. A future run on a cold page cache should be
  expected to fail `T4` again; this is a host storage-path property, not
  something this branch changed or could change within its scope.
- The CPU-sampling gap (periodic samples read near-zero; a live poll during
  generation read 801.97%) is a property of when `sample_resources` runs
  relative to the request loop, not a defect this branch fixes. It is named in
  both proof records so a reader does not mistake `cpuPercentMax: 0.83%` for
  this workload's actual cost.
- The wide per-request latency range (3.06 s to 23.5 s) is reported and not
  explained; nothing here establishes whether it reflects the model, host
  variance, or contention this project cannot observe.
- Fixing `B1` and `B2` required touching product code, which
  `V1-S2-005-PR2`'s own brief correctly refused to do. This branch is scoped
  narrowly to the three defects PR2 found and named; it implements no other
  story, no other PR, and no accepted-architecture change.
