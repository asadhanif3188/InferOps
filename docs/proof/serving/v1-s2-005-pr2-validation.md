# V1-S2-005-PR2 change validation

| Field | Value |
|---|---|
| Date | 2026-09-03 |
| Scope | Execute the registered local serving baseline, preserve the evidence, publish the analysis |
| Source branch | `docs/v1-s2-005-local-baseline-results` |
| Base revision | `fbf34f1328760e2c4ad1f026fa96beb13575b624` |
| Evidence produced here | `local-real-cpu`, and it is a **negative** result |
| Real-runtime execution | **Authorized and performed.** A model was downloaded and hash-verified, the pinned runtime was started, and real requests were sent |
| Measured baseline published | **None.** The experiment failed; there is no baseline |

## What this change is

Documentation and evidence only. No source file, descriptor, test, or
configuration is modified. The change records what happened when the experiment
registered by `V1-S2-005-PR1` was executed for the first time on an authorized
host, and it publishes the two defects that execution found.

The headline is not the one this PR was scoped to produce. The experiment did not
yield a slow baseline or a noisy baseline; it yielded no baseline at all, because
every request was refused before it reached the runtime. The instruction covering
that case is explicit — do not invent data, document the blocker, leave the story
incomplete — and that is what this change does.

## What was executed

Authorization was granted by the host owner in the session that ran it, after
being told the download size, its source, and the expected CPU cost.

| Command | Result |
|---|---|
| `python -m tools.model_acquisition check` | `state absent (0 bytes present)`; 1,834,426,016 bytes required |
| `python -m tools.model_acquisition acquire` | `verified download verified; 1834426016 bytes` |
| `python -m tools.model_acquisition verify` | `Qwen3-1.7B-Q8_0.gguf (1834426016 bytes, SHA-256 matched)` |
| `python -m tools.serving_baseline check` | Exit `0` — and this is itself a finding; see `B1` |
| `python -m tools.serving_baseline environment` | Sanitized host record captured |
| `python -m tools.serving_baseline run --confirm-real-runtime` (cold) | **Exit `3`** — `the runtime did not become ready within the startup budget` |
| `python -m tools.runtime_packaging start --confirm-real-runtime` | Diagnostic; runtime log recorded `model loaded` at 358,735 ms |
| `python -m tools.runtime_packaging stop --confirm-real-runtime` | `runtime stopped and removed` |
| `python -m tools.serving_baseline run --confirm-real-runtime` (warm) | Runtime ready 284,406 ms; API ready 297 ms; **33 of 33 requests refused HTTP 400**; then hung indefinitely and produced no exit code |
| `python -m tools.runtime_packaging stop --confirm-real-runtime` | `runtime stopped and removed`; cleanup confirmed after the hung run was terminated |

The full evidence is in
[the raw result record](v1-s2-005-baseline-raw-results.md).

## Findings

### `B1` — the registered fixture cannot be accepted by the API

The committed fixture sends a `system` message and a `user` message. The InferOps
API accepts exactly one message, whose role must be `user`, and refuses anything
else with `contract-invalid` naming `messages`. The restriction is deliberate,
documented in the module docstring of
[`src/inferops/api/validation.py`](../../../src/inferops/api/validation.py), and
tied to the frozen serving-adapter interface, which carries a single `prompt`.

The experiment therefore could not have succeeded on any host, with any model, at
any speed. It reproduces offline and deterministically by handing the committed
fixture to the API's own validator — no container, no model, no network.

Why offline validation and the test suite both missed it:

- `tools/serving_baseline/` never imports `inferops.api.validation`. `check`
  cross-checks the fixture against the composition, the runtime profile, and the
  model record, but never against the surface that has to accept it.
- `tests/serving/test_serving_baseline.py` contains zero references to
  `parse_chat_completion`. Every request in that suite is answered by an injected
  seam, so the real validator never meets the real fixture.

`V1-S2-005-PR1`'s own validation record states that `check` "cross-checks … the
request envelope against the composition". That is accurate as written and was
not enough, because the composition is not the thing that refuses the request.

### `B2` — the `run` command cannot terminate

`tools.serving_baseline.execute` does its measurement inside an `on_ready`
callback passed to `tools.local_composition.run_foreground`. After the callback
returns, `run_foreground` calls `server.join()`
([`tools/local_composition/core.py:627`](../../../tools/local_composition/core.py#L627)),
which joins the thread running `serve_forever`
([`tools/local_composition/http_server.py:251`](../../../tools/local_composition/http_server.py#L251)).
That thread ends only when `request_stop` is called from the `finally` block —
after an exception or a signal.

`run_foreground` is correct for the composition command it was written for, whose
job is to stay attached until interrupted. It is the wrong primitive for a
bounded measurement that must return. `write_raw`, `summarize`, and
`write_summary` all sit downstream of the blocking call and are unreachable on a
successful run.

Observed directly: the warm attempt finished its last request at
`12:29:53.053Z` and was still running fourteen minutes later, runtime container
healthy, runner process pinned at 11.3 s of CPU, no established TCP connection,
and no `raw.jsonl`.

### `B3` — a security test fails on any host that has acquired the model

`tests/security/test_security_baseline.py::test_no_committed_file_is_a_model_artifact`
fails on this host:

```text
E   assert not ['.cache/inferops/models/Qwen--Qwen3-1.7B-GGUF/90862c4b.../Qwen3-1.7B-Q8_0.gguf']
```

The test walks the filesystem and never consults git. Its `IGNORED_PREFIXES`
list omits `.cache/`, which `.gitignore:45` does ignore, so it reports a file
that git will not publish and cannot publish. Confirmed:

```text
$ git check-ignore -v .cache/inferops/models/.../Qwen3-1.7B-Q8_0.gguf
.gitignore:45:.cache   .cache/inferops/models/.../Qwen3-1.7B-Q8_0.gguf
$ git ls-files --error-unmatch .cache/inferops/models
NOT TRACKED
$ git ls-files | grep -c gguf
0
```

This is pre-existing and unrelated to this change, and that was measured rather
than argued: stashing this change entirely and re-running the suite against the
base tree produces **the same single failure** (1 failed, 5,426 passed). It has
been invisible until now because no host had previously run the documented model
acquisition. The test's intent is right and its name is right; only its ignore
list is out of step with `.gitignore`.

## Validation results

| Command | Result | Evidence boundary |
|---|---|---|
| `uv run --locked ruff check .` | Passed; all checks passed | Repository-static |
| `uv run --locked ruff format --check .` | Passed; 252 files already formatted | Repository-static |
| `uv run --locked python -m mypy` | Passed; no issues in 142 source files | Repository-static |
| `uv run --locked python -m pytest tests/serving/test_serving_baseline.py -q` | Passed; 107 tests | Controlled synthetic baseline path |
| `uv run --locked python -m pytest -q` | **1 failed, 5,428 passed, 25 skipped, 14 deselected** | The one failure is `B3`, pre-existing and caused by the acquired model, not by this change |
| `uv run --locked python -m pytest -q --deselect …test_no_committed_file_is_a_model_artifact` | Passed; 5,428 passed, 25 skipped, 15 deselected | Two more than this tree's own baseline, one per new proof record |
| `uv run --locked python -m pytest -q` on the **unmodified base tree** | **1 failed, 5,426 passed, 25 skipped, 14 deselected** | Measured by stashing this change; the identical failure proves `B3` is pre-existing |
| `uv run --locked python -m tools.serving_baseline check` | Exit `0` | Reported as a finding rather than as reassurance; see `B1` |
| `git diff --check` | Passed; no whitespace defect | Repository-static |
| Trailing-whitespace and hard-tab sweep of changed Markdown | Passed; 0 lines in 3 files | Repository-static |
| Relative Markdown link sweep across changed documents | Passed; 127 links checked, all resolve | Repository-static |
| `gitleaks detect --config .gitleaks.toml` | **Not run**; `gitleaks` is not installed on this host | Reported, not claimed |

The full-suite figure is reported as it came out, and the failure is not set
aside — it is measured. The base tree was restored by stashing this change and
the suite re-run against it: **the same single test fails there, with this change
absent entirely.** That is what establishes `B3` as pre-existing rather than
introduced, and it is a stronger statement than the reasoning that this change
adds only Markdown.

The pass count moves from 5,426 to 5,428. Both added tests are the parameterized
documentation checks that each new proof record brings with it, confirmed by
collecting with the two records removed (5,452 collected) and present (5,454). No
existing test changed state.

## Public-information review

The reviewed change is confined to the public repository and contains Markdown
only. A pattern sweep across the working diff and the new record returned zero
matches for personal filesystem paths, Windows drive letters, the private
planning repository's name, host or account identifiers, and credential-shaped
strings.

The evidence quoted in the raw result record was reviewed line by line rather
than in bulk. It carries no prompt and no completion, because the API's emission
path records identity, outcome, status, and duration only; the refusal records
are quoted verbatim and in full so that a reader can confirm the absence instead
of taking it on trust. The environment capture is the tooling's sanitized record
— operating system, release, architecture, logical CPUs, memory, free disk,
Python version, engine version, accelerator, and the committed pins — and carries
no hostname, user name, network identity, or absolute path.

The model artifact is 1.71 GiB in the ignored workspace cache. It is untracked,
`.gitignore:45` ignores it, and no `.gguf` file is tracked anywhere in the
repository.

## Acceptance criteria

Against the parent story `V1-S2-005`:

| Criterion | Status |
|---|---|
| Environment, model/runtime, request shape, warm-up, and duration are recorded | **Met.** All are in the experiment and raw result records |
| P50/P95/P99, throughput, errors, load time, CPU/memory, and tokens where available are reported | **Partly met, and cannot be fully met.** Errors are reported in full (33 refusals, one error code, one status). Model-load time is reported cold and warm. **No percentile, throughput, token, or per-request resource figure exists**, because no request was answered. "Where available" is doing no work here: nothing was available |
| Raw and summarized results are retained | **Met by substitution, not as designed.** The tooling wrote no `raw.jsonl` or `summary.json` — see `B2` — so the composition's own structured log was promoted into a committed record with its hash, quoted verbatim |
| Report states why results are not production benchmarks | **Met.** Stated in the guide, the experiment record, and the raw result record. It is also, this time, moot |

**The parent story is not complete.** It cannot be closed until `B1` and `B2` are
fixed and the experiment is re-run.

## Deferred, and what has to happen next

None of the following is in this PR's boundary, and none of it is started here.

1. **Fix `B1`.** The minimal correction is to make the fixture a single `user`
   message. That changes a pre-registered experiment after its failure has been
   seen, which is exactly the move pre-registration exists to make visible, so it
   belongs in its own reviewed change that re-registers the method and says why.
   The alternative — widening the API's accepted surface to carry a conversation
   — is an ADR-level change to the frozen adapter interface and is a great deal
   more than a fixture fix.
2. **Fix `B2`.** `run_foreground` needs a bounded variant that returns after
   `on_ready`, or `execute` needs to stop the server itself. Either is a product
   change and neither is a documentation edit.
3. **Close the gap that let `B1` through.** `tools.serving_baseline check` should
   validate the committed fixture against `inferops.api.validation`, and the
   suite should exercise the real validator against the real fixture at least
   once. An offline check that passes on a fixture the API will refuse is worse
   than no check, because it was trusted.
4. **Fix `B3`** by aligning the test's `IGNORED_PREFIXES` with `.gitignore`.
5. **Re-run the experiment** once `B1` and `B2` are fixed, and publish the
   baseline this PR could not.

## Independent second-eye review

An independent review of the first commit on this branch verified the change
against the repository rather than against the records' own prose. It
re-derived `B1` by calling `parse_chat_completion` on the committed fixture and
confirmed the quoted refusal reason is byte-for-byte identical to
`SINGLE_MESSAGE_REASON`; confirmed `B2` by reading `run_foreground`,
`LocalApiServer.join`, and `execute`, checking both cited line numbers, and
establishing that no success path calls `request_stop`; and reproduced `B3` live.
It cross-checked every numeric figure against the profile, the descriptor, and
the model source record, confirmed the diff touches only Markdown and leaves the
fixture byte-identical, found no personal path or planning reference, confirmed
all relative links resolve including the two line-anchored source links, and
confirmed the seven required section headings are present, in order, without
duplication.

It raised no critical, high, or medium finding, and one low one.

| Finding | Resolution |
|---|---|
| The experiment record's provenance table gave `965f669` as "the base this change branches from" while the raw result record gave `fbf34f1`. Both are correct and the second is a descendant of the first, but a reader comparing the two tables could read them as contradicting each other | Split into two rows — revision **at registration** and revision **at execution** — so the two records state the same fact in the same words. The ancestry was verified with `git merge-base --is-ancestor` rather than assumed |

The reviewer also independently confirmed the coherence this record's
classification depends on: `local-real-cpu` carries `C2` per
[the certification document](../../testing/certification.md), a `C2` record must
name the image digest and the model revision and hash, and this one does — while
still supporting no performance claim, because the run answered nothing. No
sentence in the change reads as a performance or benchmark claim.

## Risks, assumptions, and limitations

- The warm model load fits the 300,000 ms budget by 15.6 s, and only after a
  previous attempt has pulled the model through Docker Desktop's virtual-machine
  bind mount. A cold load on this host takes 358,735 ms and fails. Any future
  run on this class of host should expect to fail the first time.
- `B1` and `B3` are established by reproduction and by direct check. `B2` is
  established by reading the source and by one observation of the hang; no
  timeout exists that would have ended it, so it was ended by terminating the
  process.
- Because the warm attempt was force-terminated, its ownership-scoped cleanup did
  not run. The container was removed afterwards by an explicit
  `tools.runtime_packaging stop`, and its absence was confirmed. The cold
  attempt's cleanup ran correctly on its own.
- `gitleaks` was not run because it is not installed here. The secret-scan gate
  is therefore unverified on this host rather than passed.
- Everything here describes one host, on one day, with one model, one runtime,
  one quantization, one parallel slot, and one request shape.
