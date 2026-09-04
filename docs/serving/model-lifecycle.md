# Model lifecycle: startup, cache, readiness, restart, and shutdown

Status: **the state model is implemented and validated offline; both start
comparisons have been executed for real on an authorized host** — the cold/warm
one three times, the restart one once. Every ordering property held every time,
and **no timing difference was established by either comparison** — the spread
between runs of one experiment exceeds every difference measured inside one.
The measured results are in
[the cold and warm comparison record](../proof/serving/v1-s2-007-pr1-cold-warm-start.md)
and [the restart record](../proof/serving/v1-s3-003-pr1-restart-reload.md).

Three records already decided pieces of this. [ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md)
selected the model and the runtime; [model acquisition](model-acquisition.md)
owns the cache; the [local runtime package](local-runtime-package.md) owns the
startup budget, the readiness path, and the liveness probe. What none of them
held was the single ordered answer to *which state is this deployment in, and
what does each probe say while it is there*.

[`model-lifecycle.v1.json`](../../deploy/serving/lifecycle/model-lifecycle.v1.json)
is that answer, and [`tools.model_lifecycle`](../../tools/model_lifecycle/) is
the command that reads it, classifies the cache, and — with explicit
authorization — measures two real starts.

## The states

Eight states, in the order a deployment reaches them. The three `artifact` states
describe what the cache holds; the five `runtime` states describe a process.

| State | Liveness | Readiness | Accepts work |
|---|---|---|---|
| `artifact-absent` | not applicable | false | no |
| `artifact-partial` | not applicable | false | no |
| `artifact-verified` | not applicable | false | no |
| `runtime-starting` | not applicable | false | no |
| `runtime-loading` | **pass** | false | no |
| `runtime-ready` | pass | **true** | **yes** |
| `runtime-draining` | **pass** | false | no |
| `runtime-stopped` | fail | false | no |

Read the table for the two rows in bold and the reason for the whole record is
visible: **`runtime-loading` and `runtime-draining` are states in which a healthy
process must pass liveness while reporting itself not ready.**

`uv run --locked python -m tools.model_lifecycle states` prints it from the data.

## Why liveness and readiness must disagree

The runtime answers `503` on `/health` while it loads the model and `200` once it
can answer. That was the most consequential thing the
[Sprint 0 feasibility trial](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md)
found: it is *correct readiness reporting and wrong liveness reporting*. A
liveness probe pointed at `/health` fails throughout the load, restarts the pod
before it finishes, and never converges — the process is killed for being busy
doing the one thing it was started to do.

So the liveness probe is a TCP connection to the published port and nothing else.
It distinguishes a live process from a dead one, which is the only question
liveness is entitled to ask. The package
[pins it that way](../../deploy/serving/runtime/container-package.v1.json), and
`load_lifecycle` refuses a lifecycle record in which `runtime-loading` reports
anything other than *liveness passes, readiness false*.

Readiness is the other half. It is false until an observation says otherwise —
[`ReadinessTracker`](../../src/inferops/adapters/llama_cpp/readiness.py) starts in
`not-probed` and only an observed `200` moves it — and a ready runtime that later
answers `503` becomes not-ready again rather than latching, because a replaced pod
is a fresh process with a fresh load.

## Cache hit, miss, and partial

The cache states map one-to-one onto the three artifact states, and the mapping
carries the fact that matters operationally: **only a hit proceeds without a
network connection.**

| Cache state | Lifecycle state | Needs a network | What a start does |
|---|---|---|---|
| `miss` | `artifact-absent` | yes | refuses; an explicit `acquire` is the only way forward, and it transfers 1,834,426,016 bytes |
| `partial` | `artifact-partial` | yes | refuses; a resumed `acquire` requests the remaining range and never promotes unverified bytes |
| `hit` | `artifact-verified` | no | proceeds; the artifact is bind-mounted read-only and loaded with no network connection at all |

Classify the cache without opening a socket:

```text
uv run --locked python -m tools.model_lifecycle cache
```

It reports the state, the bytes present against the pinned byte count, and the
lifecycle state it maps to. It exits `0` on a hit and `3` otherwise, so it is
usable as a precondition check.

Add `--verify` to read the artifact end to end and compare its SHA-256. That is
off by default on purpose: the read is 1.71 GiB and it warms the host's own file
cache, which is exactly the variable a cold start measurement is trying not to
disturb.

Nothing in this tool ever downloads. A miss is reported, not repaired.

## Startup order

1. Verify the pinned image is local. Never pull implicitly.
2. Establish the cache state of the pinned artifact.
3. Create the ownership-labelled container with the artifact bind-mounted
   read-only.
4. Poll liveness and readiness *together* until readiness reports `200`, bounded
   by the 300,000 ms startup budget.

Step 4 is where the measurement comes from. Polling the two probes separately
cannot show the property the record claims: a readiness trace alone cannot
establish that the process was alive during the load, and a liveness trace alone
cannot establish that readiness was still false. Asked together, each sample is a
pair, and the window in which they disagree is directly visible.

## Shutdown order

1. Stop accepting new work and report readiness false.
2. Drain accepted work inside the drain budget, recording whether it finished.
3. Close the adapter transport.
4. Stop and remove only the ownership-labelled container.

Step 1 comes before step 2 and the ordering is the whole property: a process that
drains first and reports itself unready second spends the drain window receiving
exactly the requests it was trying to finish without. The API half of this is
[`inferops.api.lifecycle`](../../src/inferops/api/lifecycle.py), whose 15,000 ms
default drain budget the lifecycle record is checked against; the container half
is the package's 15-second stop timeout.

A drain is bounded and it reports whether it finished. A truncated drain is
recorded rather than hidden, because the requests it abandoned were real.

There is no shutdown endpoint. [ADR 0010](../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md)
declined one: an HTTP route that stops a process would be an unauthenticated
remote-stop control on a surface [ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md)
accepts with no authentication in V1.

## Restart

A stop removes the container and nothing else.

- **The artifact survives.** It lives in the workspace cache, outside every
  runtime state, so the next start is a cache hit and loads with no network
  connection.
- **Readiness resets.** A restarted deployment begins at `not-probed` and
  reaches ready only through a fresh observation. Nothing inherits the previous
  process's answer.
- **A restart against a missing artifact reacquires rather than serves nothing.**
  It refuses until an explicit `acquire` has run; it never downloads implicitly.

The `runtime-stopped` → `runtime-starting` transition is declared in the record
and `load_lifecycle` refuses a record without it.

### Measuring a restart, which is not the warm start

There are two comparisons and one read separates them.

```text
uv run --locked python -m tools.model_lifecycle restart --confirm-real-runtime
```

`measure` reads the artifact end to end *between* its two starts, so its second
start finds the host's own file cache warm — that is the variable it exists to
introduce. `restart` adds no read of its own there: the classification it takes
between the starts stats the file without opening it, and its digest read waits
until after both starts.

**That is not the same as the interval being read-free**, and saying it was is a
claim this document made and withdrew. The start procedure hash-verifies the
artifact before it creates a container — that is
[`runtime_packaging.preflight`](../../tools/runtime_packaging/core.py), and it is
a safety property of starting a runtime rather than anything this comparison
chose. So a full read precedes **every** start here, which means two things a
reader of any figure below needs:

- **no start this tool measures is cache-cold.** The artifact was read end to end
  moments before it.
- **`createMs` and `readyMs` include that read**, because the observation starts
  its clock before the start procedure. They are not container creation and
  model load on their own.

The preflight read is not wasted: it means the bytes were hash-verified
immediately before the restart as well as after it, so the surviving artifact is
established either side of the stop rather than only afterwards.

Each of the three restart properties above is measured rather than restated:

- **the artifact survives** — the byte count is compared at the three points it
  is taken at, before each start and between them; the digest is verified before
  each start by the start procedure and re-read in full at the end by the
  comparison;
- **readiness resets** — the *first* probe sample of the restarted runtime is
  read, so a process that came back already ready would be visible rather than
  assumed away. It establishes that the restarted runtime began not-ready, which
  is what a reset means here; on its own it does not separate that from the fact
  that every fresh start begins not-ready;
- **the restart needs no network** — it proceeds from a hit, which is the only
  state a start may proceed from without one.

Results are written beside the other comparison's under their own two names,
`restart-raw.jsonl` and `restart-summary.json`, because a restart summary written
over a cold/warm summary would not be a corrupted file — it would be a readable
one describing an experiment that was never run. What the executed run found, and
what it does not support, is in
[the restart record](../proof/serving/v1-s3-003-pr1-restart-reload.md).

The Kubernetes half of this is a different experiment and has not been run. A
container restart is not a pod restart: no InferOps API image is published and
the model cache claim is Terraform-owned and unwritten, so nothing has scheduled
a replacement pod against a surviving claim. What the chart does about it — the
revision-scoped mount and the integrity check every replacement pod re-runs — is
in [the storage document](../environment/model-cache-storage.md).

## Measuring a cold and a warm start

This operates a real container and requires explicit authorization:

```text
uv run --locked python -m tools.model_lifecycle measure --confirm-real-runtime
```

It runs, in order: a cold start, a full SHA-256 re-read of the artifact, a warm
start, and a second full re-read. Each start creates a fresh container, samples
both probes together until ready, issues one bounded single-token inference
probe, and stops and removes the container in a `finally`.

**Both starts are cache hits, and the record says so.** What differs between them
is that the artifact is read end to end between the two, so the warm start finds
the host's own file cache warm. That is the only cold/warm variable this
comparison controls. A real cache *miss* is a 1.71 GiB download, which this tool
never performs and never simulates.

Two honest limits travel with any number it produces:

- The host page-cache state *before* the cold start is observed, not controlled.
  Another process may have read the artifact first. The record reports the
  measurement, not a claim that the page cache was empty. On the host this was
  executed on, the artifact also crosses a virtual-machine bind mount, so warming
  the host's cache may not warm what the container reads at all.
- Three starts of each kind, on one host, on one day, is not a distribution. It
  is enough to establish the ordering properties the acceptance criteria name, and
  it was enough to establish that this host's run-to-run spread swamps any
  cold/warm difference. No percentile may be derived from it, and no cold-start
  cost may be quoted from it.

**What the three executed comparisons actually showed:** every ordering property
held in all six starts, and the warm start was *slower* than the cold one every
time — by 234 ms, 16,032 ms, and 68,532 ms, which is a range of over two orders of
magnitude. The cold arm alone spread 82,157 ms between runs, more than any of
those deltas, so **no cold/warm effect is established in either direction**. The figures, and why the host cannot resolve
one, are in [the comparison record](../proof/serving/v1-s2-007-pr1-cold-warm-start.md).

Results are written to `.cache/inferops/lifecycle`, an ignored workspace-scoped
path: `raw.jsonl` holds the two observations with every probe sample, and
`summary.json` holds the derived comparison. The restart comparison writes
`restart-raw.jsonl` and `restart-summary.json` beside them. None of the four
carries a prompt, a completion, a runtime response body, or a model byte.

`results` reports each comparison separately and says `not run` for one that has
no result, exiting `3` only when neither has been run. A result that exists and
cannot be read — a malformed line, or an observation the record does not
declare — is **not** reported as `not run`: it refuses with its own message, so
that a corrupt file is never printed over with one that reads like a clean empty
state. Read them back with:

```text
uv run --locked python -m tools.model_lifecycle results
```

## Scoped cleanup

```text
uv run --locked python -m tools.model_lifecycle clean
uv run --locked python -m tools.model_lifecycle clean --confirm
```

`clean` reaches `.cache/inferops/lifecycle` and nothing else. It has no path
override, refuses a symbolic link in or above the managed tree, and refuses a
directory that resolves outside the checkout or that is the model cache. The
model-cache refusal runs **first**, before the check that the directory is the
pinned one — behind that check it could never fire, and a guard that cannot fire
is a guard nobody can test. It compares against the cache root the record carries,
which is itself held to the model source record.

**It cannot delete the model.** Removing the artifact is
[the acquisition workflow's](model-acquisition.md#workspace-scoped-cleanup) own
confirmed operation, and a lifecycle tool that could reach it would be one bad
path away from turning a measurement into a 1.71 GiB re-download. It also does
not touch `.cache/inferops/baseline`, `.cache/inferops/composition`,
`.cache/inferops/certification`, the pinned image, or any Docker state.

## Evidence boundary

The default test lane drives every branch of this tool through injected command,
HTTP, TCP, and clock seams. It starts no container, reads no model byte, and
contacts no runtime; those results are `local-static` and stop well below any
serving claim.

The executed comparisons are `local-real-cpu` evidence with a `C2` ceiling. They
were produced on one contributor host, on CPU, on one day. They support the
ordering properties above and nothing else: no figure in them is a production
benchmark or a capacity measurement, and they say nothing about GPU, cluster, or
concurrent behaviour.
