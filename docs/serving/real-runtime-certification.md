# C2 real-runtime smoke certification

Status: **workflow implemented and validated offline and through controlled
seams; no real runtime or model was executed by this change, so no `C2` record
exists yet**.

The versioned
[`c2-smoke.v1.json`](../../deploy/serving/certification/c2-smoke.v1.json) and
[`tools.runtime_certification`](../../tools/runtime_certification/) command are
the repeatable `C2` smoke path for the selected runtime. They compose nothing
new: the [local real composition](local-real-composition.md) still starts the
pinned runtime before the loopback InferOps API and tears both down in reverse.
What this workflow adds is the part between the second readiness and the
teardown — the prerequisite refusal in front of it, the fixed request, the
identity assertions, and the machine-readable record that comes out.

Read [the certification levels](../testing/certification.md) before citing
anything this produces. `C2` means *real controlled*, it is the highest level V1
may claim, and a `C2` claim requires an executed record rather than a passing
suite.

## What it certifies, and what it refuses

| Step | What it does |
|---|---|
| Prerequisites | Reads the container engine's own CPU and memory figures, the free space on the model-cache volume, the pinned image, and the hash-verified model artifact. Any unmet check is a refusal **before** a container exists |
| Composition | Starts the runtime, waits for runtime `GET /health` `200`, starts the API, waits for API `GET /health/ready` to return the exact real-adapter identity — each inside the budget the profile already publishes |
| Identity | `GET /v1/models` must report `adapterKind` `real`, the selected runtime, the configured model identifier, the pinned model revision, and `tokenUsage` **declared supported** |
| Inference | One fixed, neutral, public request to `POST /v1/chat/completions`, with non-empty content, runtime-derived and self-consistent token counts, and the two identifiers echoed |
| Mock prohibition | Any identity value carrying `mock`, any `adapterKind` other than `real`, and the mock adapter's unsupported token-counting declaration are each a refusal |
| Evidence | One `local-real-cpu` record, labelled `local real runtime`, naming the image digest, model revision and hash, safe host facts, both readiness durations, and the observations |
| Failure | A non-zero exit, plus a diagnostics record naming the stage it stopped in |

Capacity is measured before the artifact hash on purpose. Verifying the cached
model reads nearly two gigabytes, and a host that cannot serve the workload
should learn that first.

## Validate without execution

From the repository root:

```text
uv run --locked python -m tools.runtime_certification check
```

The check reads only committed configuration. It cross-checks the descriptor
against the local composition, the runtime package, the runtime profile, and the
selected model's source record, and it refuses a descriptor that lowers its own
certification level, relabels its evidence class, waives an assertion, drops a
prerequisite below the selected package's needs, or writes outside the ignored
evidence directory. It contacts no container engine, reads no model byte, binds
no port, and starts nothing.

## Run on an authorized capable host

This is the `real-runtime` lane, and it is **outside the default check lane** by
construction: there is no marker to forget, because the command refuses to run
without its confirmation flag and refuses again when the host is not capable.

Satisfy the runtime package's
[prerequisites](local-runtime-package.md#prerequisites-for-a-real-run) first —
the exact image digest already local, and the selected model already in the
verified workspace cache. Neither is ever acquired implicitly. Then:

```text
uv run --locked python -m tools.runtime_certification certify --confirm-real-runtime
```

Exit codes are the same three the neighbouring tooling uses: `0` certified, `3`
refused before or during the guarded steps, `4` ran and did not certify.

The pytest suites in [`tests/realruntime/`](../../tests/realruntime/) remain the
separate, marker-gated way to drive the adapter and the API against a runtime you
are already operating. This command is the whole path in one bounded, cleaned-up
invocation, and it is what produces a record.

## The record and the diagnostics

Both are written under `.cache/inferops/certification/`, an ignored,
workspace-scoped path:

| File | Written when |
|---|---|
| `c2-smoke.json` | The run certified |
| `c2-smoke-diagnostics.json` | The run refused or failed after the descriptor loaded |

The record carries the certification identity and level, the evidence class and
label, safe host facts, every prerequisite with its required and observed value,
the immutable provenance, both readiness durations, the observed identity, and
the inference observation. It **never** carries the prompt, the completion, a
runtime response body, a credential, a hostname, a username, or a personal
filesystem path. Only the length of the completion and the counts the runtime
derived are retained.

The diagnostics record carries the stage the run stopped in — `load`,
`prerequisites`, `compose`, `identity`, `inference`, or `cleanup` — the safe
reason, the host facts where they were measured, and the prerequisite checks.

Committing a `C2` claim means copying the relevant figures into a record under
[`docs/proof/`](../proof/README.md) that also names the environment, the exact
commands, the limitations, and the authorization. The generated JSON is an input
to that record, not the record itself.

## Evidence boundary

The default test lane drives this workflow through injected command, HTTP,
capacity, and server seams. It creates no container, inspects no image, reads no
model byte, and contacts no runtime, so those results are `local-static` and
synthetic and stop at `C0`. They establish that the mechanism refuses what it
must and records what it observes. They establish nothing about a real model.

**No authorized run has been performed.** The `local-real-cpu` label this
workflow writes is truthful only for a run against the real runtime on a capable
host, and this change makes no new real-serving, startup-duration, latency,
throughput, capacity, or production claim.
