# `V1-S2-005` local serving baseline experiment

Date registered: 2026-09-03
Date executed: 2026-09-03

## Classification and certification

Evidence class: `local-real-cpu`. The experiment was executed on an authorized
CPU host on 2026-09-03 against the pinned image and the hash-verified model.

Ceiling this class carries: `C2`.

Level this record actually supports: **none for any performance claim.** The run
answered zero requests, so it produced no latency, throughput, token, or resource
figure. What it does support, at `C2`, is a negative finding: the experiment as
registered here cannot succeed, for reasons that reproduce deterministically.

Claim boundary: this record establishes what was registered before any result was
seen, and — since 2026-09-03 — that executing it failed. It establishes nothing
whatsoever about latency, throughput, resource use, or the behaviour of the
selected runtime. **No performance claim may cite it.** The results and the
evidence behind them are in
[the raw result record](v1-s2-005-baseline-raw-results.md).

> [!IMPORTANT]
> **The registered method is not merely unproven; it is wrong.** The fixture
> below carries two messages, and the InferOps API accepts exactly one `user`
> message. Correcting it is a change to a pre-registered experiment and belongs
> in its own reviewed change, not in the record that reports the failure. The
> fixture is therefore left exactly as it was registered.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `965f66971a3a46182c8216bc3de9b0bd8b2a6572` (the base this change branches from) |
| Container image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model artifact | `Qwen/Qwen3-1.7B-GGUF`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, `Qwen3-1.7B-Q8_0.gguf`, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Runtime source revision | `70adb1b4cea5ee39f867792c78dc59320921eda7` |
| Tooling | `uv` with `--locked`; `pytest 8.x`, `ruff 0.16.x`, `mypy 2.x` as `pyproject.toml` pins them |

Every pin above is read from a committed record at load time rather than copied
here by hand; `tools.serving_baseline` refuses to load a descriptor that disagrees
with any of them.

## Environment

Captured by `tools.serving_baseline environment` on the executing host on
2026-09-03. The same capture is reproduced in full, as JSON, in
[the raw result record](v1-s2-005-baseline-raw-results.md).

| Property | Value |
|---|---|
| Host | `AMD64`, 20 logical CPUs |
| Memory and disk | 16,836,890,624 bytes physical memory; 85,907,136,512 bytes free disk after the model was cached |
| Operating system | Windows 11 |
| Container engine | 29.7.2 |
| Cluster | none |
| Accelerator | none; CPU only — the profile pins `accelerator.kind` to `none` |
| Model storage path | Windows filesystem, reached by the container through Docker Desktop's virtual-machine bind mount |

The last row is not part of the captured record and is added here because it is
the property that decides `T4`. The model's bytes cross a virtualized mount, and
that crossing — not the model's size — is what puts a cold load over budget.

Number of hosts this was executed on: **one**. Every finding drawn from it
inherits that, and nothing here describes a second host.

## Method

**Registered before the run.**

Question: on one CPU host, with one parallel slot, how long does a single fixed
request through the InferOps API to the selected real runtime take, how much does
the runtime cost while answering it, and how long does the model take to load?

Hypothesis: after a three-request warm-up, thirty sequential requests of the fixed
fixture complete without error, and their latencies form a distribution narrow
enough that P50 and P99 are within one order of magnitude of each other. A wider
spread than that would mean something other than the model is dominating the
measurement — thermal behaviour, another process, or the API itself.

Procedure:

```text
uv run --locked python -m tools.serving_baseline check
uv run --locked python -m tools.serving_baseline environment
uv run --locked python -m tools.serving_baseline run --confirm-real-runtime
uv run --locked python -m tools.serving_baseline summarize
```

Fixed by [`local-baseline.v1.json`](../../../deploy/serving/baseline/local-baseline.v1.json):
one system message and one user message, `stream: false`, at most 128 output
tokens, temperature 0, 4,096-token context, one parallel slot; three warm-up
requests discarded from every distribution; thirty measured requests at
concurrency one; a 120,000 ms per-request timeout; a 900-second stop condition; a
container resource sample every five measured requests.

Pre-registered thresholds:

| ID | Threshold | Blocking? | Rationale |
|---|---|---|---|
| `T1` | All 30 measured requests succeed with HTTP 200 | yes | A baseline drawn from a partially failing run describes the failures |
| `T2` | Every answer carries `adapterKind: real` and `modelRef: qwen3-1-7b-q8-0` | yes | An answer from anything else is not evidence about this deployment |
| `T3` | Zero measured requests fail | yes | The descriptor sets `maximumFailedRequests` to 0 |
| `T4` | The model loads within the profile's 300,000 ms startup budget | yes | Beyond it the composition itself refuses, so no results exist |
| `T5` | P99 is within 10× P50 | no | Informational: a wider spread means the measurement is dominated by something other than the model, and the record must say so |

Failure condition: the hypothesis is wrong if any measured request fails, if any
answer carries mock identity or another model's reference, or if the runtime does
not become ready within its budget. Any of these means there is no baseline to
publish — not a weaker baseline.

Stop condition: 900 seconds of measured phase, or the first answer carrying mock
identity, which aborts immediately rather than being recorded.

## Results

**Executed on 2026-09-03, and the hypothesis is refuted.** The full evidence,
including the verbatim refusal records and the offline reproduction, is in
[the raw result record](v1-s2-005-baseline-raw-results.md).

| Threshold | Verdict | Measured or observed | Note |
|---|---|---|---|
| `T1` | **Failed** | 0 of 30 measured requests succeeded; all returned HTTP 400 | Blocking |
| `T2` | **Not evaluable** | No answer was produced to carry an identity | The refusals do carry `adapter.kind: real`, so nothing mock was involved |
| `T3` | **Failed** | 30 of 30 measured requests failed | Blocking; the descriptor allows 0 failures |
| `T4` | **Failed cold, met warm** | Cold 358,735 ms; warm 284,406 ms | Blocking. Budget is 300,000 ms |
| `T5` | **Not evaluable** | No latency distribution exists | Informational threshold |

The hypothesis was that thirty sequential requests would complete without error.
Thirty completed with error, every one of them refused by the InferOps API before
it reached the runtime, with `contract-invalid` naming `messages`.

**The cause is this record's own fixture.** The API accepts exactly one message,
whose role must be `user`; the fixture registered above carries a `system`
message and a `user` message. The experiment could not have succeeded on any
host. A second defect would have prevented a result file even had the fixture
been accepted: the `run` command blocks after its final request and never writes
one. Both are characterized in the raw result record as `B1` and `B2`.

Commands that failed, and their output:

```text
$ uv run --locked python -m tools.serving_baseline run --confirm-real-runtime
REFUSED serving baseline: the runtime did not become ready within the startup budget
exit 3
    (attempt 1, cold page cache; ownership-scoped cleanup ran and removed the
     container)

$ uv run --locked python -m tools.serving_baseline run --confirm-real-runtime
    (attempt 2, warm page cache; runtime ready in 284,406 ms, API ready in
     297 ms, 33 requests sent and all 33 refused with HTTP 400, then the process
     hung indefinitely without writing raw.jsonl or summary.json and was
     terminated. No exit code was produced, because the command cannot produce
     one.)
```

Unexpected observations, all three of them:

1. **The warm-up phase failed silently as far as the operator could see.** The
   command emits nothing until it finishes, and it never finishes, so 33 refusals
   were only visible in the composition log. An operator watching the terminal
   sees an indefinite hang and no indication that every request was rejected.
2. **`tools.serving_baseline check` exits `0` on this fixture.** Offline
   validation cross-checks the fixture against the composition, the profile, and
   the model record, but never against the API surface that has to accept it.
3. **The runtime was never asked to do any work.** `docker stats` sampled the
   container at 0.00–0.17% CPU throughout the request phase, and the runtime's
   log records no inference. The experiment measured the API's refusal path.

## Limitations

- This record establishes no latency, throughput, resource, or capacity figure,
  and no claim of any kind about the selected runtime's performance. It was
  executed, and it still establishes none, because nothing was answered.
- Nothing varied deliberately between the two attempts. The difference in
  model-load time is page-cache state, which was observed rather than controlled.
- The resource sampling and the measured latency distribution do not exist. The
  only real timings produced are the two model-load figures.
- The result describes one host, one model, one runtime, one quantization, one
  parallel slot, and one request shape. It does not describe concurrent serving,
  sustained load, GPU execution, or Kubernetes.
- `T4`'s warm verdict rests on 15.6 s of margin against a 300 s budget on one
  host on one day. It should not be read as a statement that this configuration
  starts within budget in general; the cold measurement says the opposite.
- **No claim may cite this record for a performance figure**, and no figure the
  registered experiment eventually produces may be published as a benchmark. See
  [the project boundaries](../../architecture/project-boundaries.md).

## Authorisation

Required: **yes**, because execution operates a container, reads the selected
model's bytes from the verified cache, and occupies the host's CPU for the
duration of the measured phase.

Granted by: the host owner, on 2026-09-03, in the session that ran it, after
being told the model download size (1.71 GiB), its source, and the expected CPU
cost. The grant covered acquiring the model and executing the baseline.

Stages that ran: model acquisition and hash verification, the authorized
composition start, the model load, the warm-up phase, and the measured phase.

Stages that did not run: container resource sampling beyond the first interval,
raw result production, and summary generation — none of them reachable, because
the requests were refused and the command never returned. See `B1` and `B2` in
[the raw result record](v1-s2-005-baseline-raw-results.md).

Cleanup verified: yes. `docker ps -a` reports no `inferops-` container. Attempt
one's ownership-scoped cleanup ran on its own; attempt two was force-terminated
past its `finally` block, so its container was removed afterwards by an explicit
`tools.runtime_packaging stop --confirm-real-runtime`, and that removal was
confirmed rather than assumed. No image was pulled — the pinned digest was
already local. The model artifact was downloaded into the ignored workspace cache
and was not committed. No result file was written anywhere.
