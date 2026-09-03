# V1-S2-007-PR1 change validation

| Field | Value |
|---|---|
| Date | 2026-09-03 |
| Scope | Model lifecycle state model, cache classification, and a bounded cold/warm start comparison |
| Source branch | `feat/v1-s2-007-model-lifecycle` |
| Evidence produced here | `local-static` and `synthetic` for the suite; `local-real-cpu` for the executed comparison |
| Real-runtime execution | **Authorized and run.** Three full comparisons — six container starts — on this contributor host. Recorded in [the cold and warm start record](v1-s2-007-pr1-cold-warm-start.md) |

## Implemented boundary

The committed
[`model-lifecycle.v1.json`](../../../deploy/serving/lifecycle/model-lifecycle.v1.json)
and [`tools.model_lifecycle`](../../../tools/model_lifecycle/) command add one
ordered state model above the existing acquisition workflow and container
package. Eight states — three describing what the cache holds, five describing a
process — each carry the answer every probe gives while a deployment is in them,
alongside the transitions between them and the startup, shutdown, and restart
ordering.

No value another record owns is restated without being compared to its owner —
including this module's own model-cache constant, which `_validate_cache` holds to
the model source record so that it cannot become a second silent answer to where
the cache is. Loading refuses drift from the
container package's liveness kind and port, readiness path, ready and loading
statuses, startup budget, poll interval, and stop timeout; from the model source
record's cache root; and from
[`inferops.api.lifecycle`](../../../src/inferops/api/lifecycle.py)'s own default
drain budget. The `readyStatus` and `loadingStatus` an observation record carries
are copied onto it from the loaded record rather than written into the module, for
the same reason.

The record's central invariant is enforced rather than described: **the states
`runtime-loading` and `runtime-draining` must pass liveness while reporting
readiness false.** A record letting the two agree there describes a deployment a
liveness probe restarts mid-load, which is precisely what a probe pointed at the
runtime's `503`-while-loading health endpoint would do. `runtime-ready` is the
only state that may report ready, and a state accepts work if and only if it
reports ready.

Cache hit, miss, and partial are classified with no network connection and only a
hit may proceed without one. A measured start from a miss refuses and names the
explicit `acquire` that would repair it; it never downloads. Integrity
verification is opt-in on the `cache` command because reading 1.71 GiB warms the
host file cache that a cold observation is trying not to disturb.

The measurement requires `--confirm-real-runtime`, refuses to run beside an
existing container carrying the package's own name, samples liveness and
readiness *together* so their disagreement is directly observable, and stops and
removes its container in a `finally` — on the failure path too, so an
observation that failed *and* leaked its container reports the leak rather than
only the first fault. `clean` reaches `.cache/inferops/lifecycle` and nothing
else: it has no path override, refuses a symbolic link in or above the managed
tree, refuses a directory resolving outside the checkout, and refuses the model
cache. That last refusal is ordered **first**, ahead of the pinned-directory
equality; behind it the check would never fire, and an unreachable guard is one
nobody can test. Independent review found it in exactly that state and it was
reordered, with both entry points now asserting the model-cache message
specifically rather than the generic one they would also have produced.

## Validation results

| Command | Result | Evidence boundary |
|---|---|---|
| `uv run --locked python -m tools.model_lifecycle check` | Passed; `inferops-local-model-lifecycle`, 8 states, 13 transitions, agreement with the package, the model source record, and the API drain budget | `local-static`; contacted no engine, runtime, or model |
| `uv run --locked python -m tools.model_lifecycle states` | Passed; the eight-row probe table printed from the data | `local-static` |
| `uv run --locked python -m tools.model_lifecycle cache` | Passed; `hit`, 1,834,426,016 of 1,834,426,016 bytes, mapping to `artifact-verified`, digest not read | `local-static`; opened no socket |
| `uv run --locked python -m tools.model_lifecycle measure --confirm-real-runtime` | Passed, three times; six container starts | **`local-real-cpu`**; see [the comparison record](v1-s2-007-pr1-cold-warm-start.md) |
| `uv run --locked ruff check .` | Passed; all checks passed | Repository-static |
| `uv run --locked ruff format --check .` | Passed; 262 files already formatted | Repository-static |
| `uv run --locked python -m mypy` | Passed; 146 source files checked | Repository-static |
| `uv run --locked python -m pytest tests/serving/test_model_lifecycle.py -q` | Passed; 74 tests, **2 skipped** | Controlled synthetic lifecycle path; the two skips are the symbolic-link cleanup refusals, which this host does not permit creating a link to exercise |
| `uv run --locked python -m pytest tests/api/test_api_lifecycle.py -q` | Passed; 17 tests | Mock-integration; API restart and drain ordering |
| `uv run --locked python -m pytest tests/testing -q` | Passed; 1,025 tests | Repository-static; inventory and strategy agreement |
| `uv run --locked python -m pytest -q` | Passed; 5,541 passed, 27 skipped, 14 deselected | Default lane; real-runtime tests remained deselected. Two of the 27 skips are new and are named above |
| `git diff --check main...HEAD` | No trailing-whitespace or hard-tab match | Repository-static |
| Markdown trailing-whitespace and hard-tab sweep | No match in any file this change touches | Repository-static |
| Relative Markdown link sweep | No broken target | Repository-static |
| `gitleaks detect --config .gitleaks.toml --no-banner` | **Not run**; `gitleaks` is not installed on this host | Reported, not claimed |

The pre-existing trailing-whitespace matches in
[`v1-s1-002-pr1-cumulative-review-fixes.md`](v1-s1-002-pr1-cumulative-review-fixes.md)
are unchanged by this branch and are left alone; that file is a record of a past
moment and rewriting it here would be an unrelated edit.

## What the focused suite establishes, and what it does not

`tests/serving/test_model_lifecycle.py` holds 76 tests in three groups: the
record against the package, the model source record, and the API drain budget;
the invariants inside the record, each proved by a mutation that must be refused;
and the measurement's refusals, its always-removed container, and its scoped
cleanup.

**Two of the 76 skip on this host and did not run.** They are the two that create
a symbolic link — one above the managed tree, one inside it — to prove that
`clean` refuses a link rather than following it. Windows refused to create the
link, the tests skip with that reason rather than passing vacuously, and the two
refusals they cover are therefore **published but not exercised here**. The other
two `clean` refusals — the model cache and a directory resolving outside the
checkout — are exercised.

**Every timing it asserts is arithmetic on a fake clock.** Each start runs
through injected command, HTTP, TCP, and clock seams over a synthetic cache
holding 21 bytes. No container is started, no image is inspected, no model byte is
read, and no socket is opened. That result is `local-static` and certifies nothing
about a runtime. The suite is inventoried under the `documentation` layer with the
`docs` marker, defends no published claim, and carries its reason in the data.

The cleanup test is the one worth naming on its own: it writes a result set, a
model cache, and a serving-baseline directory side by side under one temporary
root, confirms a cleanup, and asserts that the model bytes and the baseline
summary both survive it.

Two others are worth naming because independent review created them. The
model-cache refusal is now asserted by its own message rather than by the generic
one the same document would also have produced — without that, the guard could be
deleted and the test would still pass. And `readinessFalseUntilReady` is now
derived from the loading count rather than from "no early sample said ready": the
sampling loop returns on the first ready answer, so the weaker form was true of
every observation by construction, and a property that cannot fail is not worth
publishing. A test now drives an unreachable-socket sample through it and asserts
that it reports `false`.

## Sprint 1 and Sprint 2 work this did not duplicate

Three properties the parent story names were already implemented and tested
before this change, and this PR extends rather than rebuilds them:

- **Readiness is false until an observation says otherwise.**
  [`ReadinessTracker`](../../../src/inferops/adapters/llama_cpp/readiness.py)
  starts in `not-probed` and offers no way to assert a state.
  `tests/adapters/test_llama_server_readiness.py` already covered that and its
  reset; nothing was added there.
- **Shutdown reports unready before it drains.**
  [`ApplicationLifecycle`](../../../src/inferops/api/lifecycle.py) has held that
  ordering since `V1-S1-005-PR2`.
- **A `503` during load is not a liveness failure.** The container package has
  pointed liveness at the TCP socket since `V1-S2-003-PR1`.

Three tests were added to `tests/api/test_api_lifecycle.py` for the one property
that had no coverage: a drained lifecycle refuses to begin serving again, a
restarted lifecycle inherits nothing from the drained one beside it, and a
restarted API is not ready until its own startup has run.

## Acceptance criteria

| Criterion | Status | Where |
|---|---|---|
| Cache hit/miss behaviour is documented and measurable | **Met** for hit; **partially met** for miss | The three cache states are published and mapped; `cache` classifies them offline and exits non-zero on anything but a hit. Both measured starts recorded `hit`. A real *miss* is a 1.71 GiB download and was not performed; the miss and partial paths remain synthetic-only, as the acquisition suite already covered them |
| Liveness does not restart a healthy loading process | **Met**, and measured | Refused as a record invariant, and observed directly: 413 and 450 consecutive samples in the first comparison in which liveness passed while readiness answered `503` |
| Readiness remains false until inference is possible | **Met**, and measured | `readinessFalseUntilReady` was true in every measured start, and each start's bounded inference probe returned HTTP 200 immediately after the first `200` readiness observation |
| Shutdown drains or rejects new work safely | **Met** | Ordering enforced in the record and in `ApplicationLifecycle`; every measured container was verified stopped and removed |
| Restart behaviour preserves or reacquires artifacts predictably | **Met** | The artifact verified by SHA-256 unchanged after every start; both starts were cache hits; a restart against a missing artifact refuses rather than downloading |

## Deferred, and reported rather than implemented

- **A real cache miss was not measured.** It costs a 1.71 GiB download and no such
  authorization was given. The record documents the miss path; it is not
  evidenced.
- **A page-cache-controlled cold start was not achieved.** See the limitation
  section of [the comparison record](v1-s2-007-pr1-cold-warm-start.md); the host's
  file cache state before a run is observed, not controlled.
- **No Kubernetes probe manifest was changed.** This PR publishes the state model
  a probe configuration should follow. Applying it to a chart is later work; no
  chart exists.
- **`V1-S2-008` (local runtime troubleshooting) is untouched.** It depends on this
  story and remains the next PR's scope.

## Observation for a follow-up, not fixed here

[`README.md`](../../../README.md) still describes the local serving baseline as
"the experiment was not executed and no measured baseline exists". That became
untrue when `V1-S2-005-PR2` merged and a measured baseline was published. It is
outside this PR's boundary and is recorded here rather than corrected in an
unrelated edit.
