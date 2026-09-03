# Local serving baseline

Status: **registered and validated offline; the experiment has not been executed
and this repository holds no measured baseline yet**.

The versioned
[`local-baseline.v1.json`](../../deploy/serving/baseline/local-baseline.v1.json)
and [`tools.serving_baseline`](../../tools/serving_baseline/) command register a
repeatable serving experiment against the
[local real composition](local-real-composition.md), and turn one authorized run
into a raw record set plus a summary that can be regenerated from it.

The method is registered **before** the run on purpose. Registering the fixture,
the warm-up, the duration bound, and the success criteria in advance is what
separates a measurement from a search for a number that supports what was already
believed. The pre-registered record is
[`v1-s2-005-local-baseline-experiment.md`](../proof/serving/v1-s2-005-local-baseline-experiment.md).

> [!WARNING]
> **This baseline is not a benchmark and can never become one.** It is a
> descriptive measurement of one single-slot CPU deployment on one host.
> [The project boundaries](../architecture/project-boundaries.md) forbid
> publishing a throughput, latency, or capacity figure from V1, and that rule
> covers every figure this tooling produces. The descriptor, the raw records, and
> the summary each carry `productionBenchmark: false`, and the loader refuses a
> descriptor that says otherwise.

## What is measured

| Quantity | How it is obtained |
|---|---|
| Model-load time | Runtime readiness, as the composition already measures it |
| API readiness | API readiness after the runtime is ready |
| Request latency | Wall-clock around one full request through the InferOps API |
| P50, P95, P99 | Nearest rank over the successful **measured** requests |
| Throughput | Successful measured requests over the measured window |
| Errors | Every measured request that was not a success, by outcome |
| CPU and memory | `docker stats --no-stream` against the owned container |
| Tokens | `usage` from the completion, where the adapter supplies it |

Latency is measured at the InferOps API, not at the runtime. It therefore includes
whatever the API itself costs. That is the number a caller of InferOps
experiences, and it is the one this project is entitled to describe.

### Nearest rank, and why not interpolation

`percentile_ms` sorts the successful measured latencies and returns the value at
rank `ceil(p × n / 100)`. The returned figure is always a latency some request
actually produced. An interpolated P99 over thirty requests is a number no request
produced, and a record whose headline figure is synthetic is exactly the confusion
the [evidence classes](../testing/certification.md) exist to prevent.

### Why warm-up is discarded

The first requests after a cold start measure the cache, the allocator, and the
first prompt-processing pass. They are recorded — they are in the raw file, phase
`warmup` — and then excluded from every distribution. A percentile that includes
them describes the start-up, not the steady state.

### Why concurrency is one

The selected runtime is pinned to a single parallel slot. Sending more than one
request at a time would queue them inside the runtime, and the resulting
distribution would be a measurement of that queue. The loader refuses a descriptor
whose concurrency does not equal the profile's `parallelSlots`.

## Validate without execution

From the repository root:

```text
uv run --locked python -m tools.serving_baseline check
```

The check reads only committed files. It cross-checks the fixture against the
served model and the frozen request subset, the generation settings against the
runtime profile, the request envelope against the composition, the concurrency
against the runtime's parallel slots, the duration bound against the request
sequence it must be able to stop, the success criteria against the real adapter
selection, and the result layout against the workspace-scoped path it is allowed
to write. It contacts no Docker daemon, reads no model byte, binds no port, and
sends no request.

To see the environment record a run would capture, without running one:

```text
uv run --locked python -m tools.serving_baseline environment
```

This executes one `docker version` command and reads host properties. It records
the operating system, release, architecture, logical CPUs, memory, free disk,
Python version, container engine version, accelerator, and the immutable image,
model, and runtime revisions. **It records no hostname, user, network identity, or
absolute path**, because an environment record is committed and those are what
would turn it into a statement about somebody's machine.

## Execute on an explicitly authorized capable host

First satisfy the composition's prerequisites: the pinned image digest must
already be local and the selected model must already exist in the verified
workspace cache. This command downloads neither.

```text
uv run --locked python -m tools.serving_baseline run --confirm-real-runtime
```

Without `--confirm-real-runtime` the command refuses and exits `3`, having started
nothing. With it, the run composes the runtime and the API through
[`tools.local_composition`](../../tools/local_composition/) — so readiness
ordering, drain, and ownership-scoped cleanup stay owned in one place — then sends
the warm-up, then the measured phase, sampling container resources periodically.
Any answer carrying mock identity aborts the run rather than being recorded.

Exit codes: `0` the criteria were met, `3` refused before or during a bounded
step, `4` an unexpected local failure, `6` the run completed and its success
criteria were not met, `130` interrupted.

## Regenerate the summary from the records

```text
uv run --locked python -m tools.serving_baseline summarize
```

Summarizing is a pure function of the raw record set: no clock, no network, no
container, integer arithmetic throughout. The same raw file always produces the
same summary. That is what lets a published summary be checked against the records
it claims to describe rather than trusted.

## Outputs

Both files are written under `.cache/inferops/baseline/`, which is ignored by Git.
Neither is a committed record until a reviewed change promotes it into
[`docs/proof/serving/`](../proof/serving/) under the
[raw-result template](../proof/templates/TEMPLATE-raw-result.md).

| File | Format | Contents |
|---|---|---|
| `raw.jsonl` | JSON Lines | One `run` header, one `request` record per request, one `resource` record per sample |
| `summary.json` | JSON | The deterministic reduction of `raw.jsonl` |

A raw request record carries a sequence number, phase, outcome, HTTP status,
latency, token counts, adapter kind, model reference, and error code. **It never
carries the prompt or the completion.** The baseline records how long an answer
took and how many tokens it carried; a committed transcript of what a model said
is a different artifact with different rules.

## What this cannot establish

- Nothing about concurrent serving, queueing behaviour, or capacity.
- Nothing about GPU, cloud, or Kubernetes execution.
- Nothing about a second model, a second deployment, or a second host.
- Nothing about sustained load: the `load` test layer is deferred out of V1.
- No comparison against another runtime, another model, or another platform.
