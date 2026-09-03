# `V1-S2-005` local serving baseline raw results

Date produced: 2026-09-03

## Classification and certification

Evidence class: `local-real-cpu`. A real pinned runtime was started from a
hash-verified model artifact on a real CPU host, and 33 real HTTP requests were
sent through the real InferOps API to it.

Ceiling this class carries: `C2`.

Level this record actually supports: `C2`, and for the first time this record
carries an actual measurement. All 33 requests — 3 warm-up, 30 measured —
succeeded with HTTP 200, an explicitly real adapter identity, and the pinned
model reference. The success criteria the descriptor fixed before any run
(`minimumSuccessfulRequests: 30`, `maximumFailedRequests: 0`) are met exactly.

Claim boundary: this record establishes the load time, per-request latency,
throughput, token counts, and periodically-sampled resource use of one fixed
request against one pinned image, one hash-verified model, on one CPU host, at
concurrency one, on one day. It establishes nothing about a second host, a
second model, concurrent serving, sustained load, GPU or cloud execution, or any
other configuration. **No figure here is a benchmark, and none may be published
as one.**

## Why this run succeeded where the first attempt did not

The experiment registered by `V1-S2-005-PR1` was first executed by
`V1-S2-005-PR2` and failed: every request was refused by the InferOps API before
reaching the runtime, and the tooling could not have returned a result even had
the requests succeeded. That execution and its full evidence are recorded on
branch `docs/v1-s2-005-local-baseline-results`
(commit `39c6237`), not yet merged at the time this record was produced.

Two defects caused that failure, and a third was found in the same session by
running the full suite with the model actually present. All three are fixed on
this branch, commit `d604077`, before this run:

- **The registered fixture sent two messages; the API accepts one.** The
  descriptor's `fixture.messages` carried a `system` message and a `user`
  message. `src/inferops/api/validation.py` accepts exactly one message, whose
  role must be `user`, by design — the frozen serving-adapter interface carries
  a single `prompt` and has no parameter a conversation could be passed through
  without inventing a prompt format. The fixture is corrected to fold the system
  instruction into the single user message it is now allowed to send. This is a
  disclosed departure from the letter of pre-registration, and it is defended on
  one narrow ground: the correction is a **binary acceptance gate**, not a
  measured value. It does not touch temperature, token limit, context size,
  warm-up count, measured count, concurrency, duration bound, or any success
  threshold — the fixture was corrected to be *answerable*, not to be answered
  faster or more favourably. `load_experiment` now calls
  `inferops.api.validation.parse_chat_completion` against the committed fixture
  at load time, so a future fixture the API would refuse fails `check` before it
  can reach an authorized run again.
- **The command that executes the run could not return.** `execute` composes the
  runtime and API through `tools.local_composition.run_foreground`, which is
  written to stay attached until its server is stopped — correct for the
  interactive `local_composition start` command, wrong for a bounded run with no
  interrupt coming. `execute`'s `on_ready` callback now requests its own
  server's stop before returning, the same pattern
  `tools.runtime_certification.certify` already used for the same reason.
- **A security test could not see this run's own evidence correctly.** Unrelated
  to whether the fixture succeeds, but blocking to the full validation lane: the
  test that refuses a committed model artifact walked the filesystem without
  consulting `.gitignore` and did not know `.cache/` — where the model this run
  needed actually lives — was ignored. Fixed by adding it to the test's own
  ignore list.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `d60407741101e3a2516870e40c869c91ab77ce40` (branch `fix/v1-s2-005-baseline-tooling-defects`, based on `main` at `fbf34f1328760e2c4ad1f026fa96beb13575b624`) |
| Producing command | `python -m tools.serving_baseline run --confirm-real-runtime` |
| Container image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model artifact | `Qwen/Qwen3-1.7B-GGUF`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, `Qwen3-1.7B-Q8_0.gguf`, 1,834,426,016 bytes, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Runtime source revision | `70adb1b4cea5ee39f867792c78dc59320921eda7` |
| Baseline descriptor (as run) | `deploy/serving/baseline/local-baseline.v1.json`, `sha256:ea98ce3f6cb5d0d94c1de6ad55e211ccaf3c75b01bfa3099e218a100eecdddea` |
| Raw result file | `raw.jsonl`, 8,137 bytes, `sha256:53b4a70da67d62841eef1450ba898a6e0b9a086d00a14c4980c65646f0773077` |
| Summary file | `summary.json`, 2,100 bytes, `sha256:12df2311f3d033814bc769eeb97ee93687210c911728a47a2e42af1fc3ad3ea5` |

Both files were produced by `tools.serving_baseline run` and regenerated
identically by `tools.serving_baseline summarize` against the same `raw.jsonl`,
confirming the summary is a pure function of the raw records rather than a
value carried alongside them.

## Environment

Captured by the run itself and carried in both files' headers:

```json
{
  "accelerator": "none; CPU only",
  "architecture": "AMD64",
  "containerEngineVersion": "29.7.2",
  "freeDiskBytes": 85906444288,
  "imageReference": "ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384",
  "logicalCpus": 20,
  "modelArtifactSha256": "sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a",
  "modelRepository": "Qwen/Qwen3-1.7B-GGUF",
  "modelRevision": "90862c4b9d2787eaed51d12237eafdfe7c5f6077",
  "operatingSystem": "Windows",
  "processorFamily": "AMD64",
  "pythonVersion": "3.12.12",
  "release": "11",
  "runtimeSourceRevision": "70adb1b4cea5ee39f867792c78dc59320921eda7",
  "totalMemoryBytes": 16836890624
}
```

The model artifact reaches the container through Docker Desktop's
virtual-machine bind mount, as it did in the prior failed attempt; that path is
why model load takes minutes rather than seconds on this host, and it is
recorded here for the same reason.

Number of hosts this was executed on: **one**. Every figure below inherits that.

## Method

Schema of the raw result set (JSON Lines, UTF-8, one record per line):

| Field | Type | Units | Meaning |
|---|---|---|---|
| `record` | string | — | `run` (one header), `request` (one per warm-up/measured request), `resource` (one per sample) |
| `sequence` | integer | — | Request or sample order, `0`-indexed across warm-up then measured |
| `phase` | string | — | `warmup` or `measured` |
| `outcome` | string | — | `success`, `refused`, or `transport-error` |
| `status` | integer | HTTP status | `200` for every request in this set |
| `latencyMs` | integer | milliseconds | Wall clock around one full request through the InferOps API |
| `outputTokens` / `inputTokens` | integer | tokens | From the completion's own `usage` |
| `adapterKind` / `modelRef` | string | — | Identity the API attached to the answer |
| `cpuPercent` / `memoryBytes` | number / integer | percent / bytes | One `docker stats --no-stream` sample against the owned container |

Collection procedure, exactly as configured:

```text
Descriptor: deploy/serving/baseline/local-baseline.v1.json (corrected fixture)
Fixture:    single-turn-fixed-v1, one user message, stream=false
Generation: maxOutputTokens=128, temperature=0, context=4096, parallelSlots=1
Execution:  3 warm-up requests, 30 measured requests, concurrency 1,
            requestTimeoutMs=120000, maxDurationSeconds=900,
            resource sample every 5 measured requests
Success:    30 successes, at most 0 failures, adapter kind real,
            model ref qwen3-1-7b-q8-0, completion status 200
```

What was removed before committing, and how: nothing needed removing. The raw
record schema above is the complete field set the API's emission path produces
for a request; it carries no prompt and no completion by construction, and this
record's own excerpts below are reproduced in full for the same reason the prior
failure record's were — so a reader confirms the absence rather than trusts it.
The environment capture above carries no hostname, user name, network identity,
or absolute path.

## Results

| Summary | Value |
|---|---|
| Records | 40: 1 run header, 33 request records, 6 resource samples |
| Successes / failures | **30 / 0** (measured phase); 3 of 3 warm-up requests also succeeded |
| Span covered | Composition start to teardown: `2026-09-03T14:55:03.739Z` to `2026-09-03T14:59:42.090Z` (4 min 38 s). Measured window alone: 246,734 ms |
| Model load | 269,079 ms, against a 300,000 ms `startupBudgetMs` |
| API ready | 47 ms after runtime readiness |

> [!WARNING]
> V1 publishes no throughput, latency, capacity, or benchmark figure from these
> results. The figures below are reported as **descriptive measurements of this
> one run** — recorded because the acceptance criteria require them, not offered
> as a characterization of the runtime's general performance. See
> [the project boundaries](../../architecture/project-boundaries.md).

### Threshold verdicts

Against the thresholds `V1-S2-005-PR1` pre-registered:

| ID | Threshold | Blocking? | Verdict | Measured |
|---|---|---|---|---|
| `T1` | All 30 measured requests succeed with HTTP 200 | yes | **Met** | 30/30 |
| `T2` | Every answer carries `adapterKind: real` and `modelRef: qwen3-1-7b-q8-0` | yes | **Met** | Every one of 33 records, warm-up and measured |
| `T3` | Zero measured requests fail | yes | **Met** | 0 failures |
| `T4` | The model loads within the profile's 300,000 ms startup budget | yes | **Met** | 269,079 ms |
| `T5` | P99 is within 10× P50 | no | **Met** | 3.66× |

All five thresholds are met, including the one that failed in `V1-S2-005-PR2`'s
attempt (`T4`, then measured cold at 358,735 ms). This run's load was not
deliberately warmed; it is simply what the host produced this time. `T4`'s
margin is real but not wide — 30.9 s against a 300 s budget — and the earlier
cold-load figure stands as evidence that this budget is not comfortably met on
every attempt on this host.

### Latency (30 measured requests, milliseconds)

| P50 | P95 | P99 | min | max | mean |
|---|---|---|---|---|---|
| 6,422 | 17,718 | 23,516 | 3,062 | 23,516 | 7,952 |

Nearest-rank percentiles, independently recomputed from the 30 measured
latencies in `raw.jsonl` rather than trusted from `summary.json`: `P50 = 6422`,
`P95 = 17718`, `P99 = 23516` — all three match exactly. Every reported figure is
a latency some request actually produced, by construction of the method.

`P99` is 3.66× `P50` — inside the pre-registered `T5` informational threshold of
ten times, so `T5` is met. The individual requests still range widely in
absolute terms (3,062 ms to 23,516 ms, a 7.68× spread from min to max), which
`T5` does not measure; that range is noted in
[Unexpected observations](#unexpected-observations) without reading a `T5`
failure into it, because there is none.

### Throughput

| Measured window | Requests/second | Output tokens/second |
|---|---|---|
| 246,734 ms | 0.121 | 2.067 |

Reported as `requestsPerSecondMilli: 121` and `outputTokensPerSecondMilli: 2067`
in the committed files — thousandths of a unit per second, as integers, so nothing
here differs between platforms that read it back. Both independently recomputed
from the raw records and confirmed exact.

Both are computed by **integer floor division**
(`(count * 1_000_000) // window_ms`), not rounding: the true ratio is
`30 / 246.734 s ≈ 121.588` requests/1000s, which floors to `121`, not the `122`
a rounded figure would show. The `0.121` and `2.067` decimal forms above are for
readability only; the committed, exact values are the integer millirates.

### Tokens

Every one of the 30 measured completions carried exactly 17 output tokens —
expected at `temperature: 0` against one fixed prompt, since greedy decoding of
an unchanged input produces the same token count run over run. 1,050 input
tokens and 510 output tokens total across the measured phase.

### Resources

| Samples | CPU max (reported) | Memory max |
|---|---|---|
| 6 | 0.83% | 706,949,939 bytes (~674 MiB) |

**The CPU figure understates the runtime's actual load, and that is recorded
here rather than smoothed over.** All six samples — taken after requests 8, 13,
18, 23, 28, and 33 — read at or near 0% CPU:

```text
{"cpuPercent":0.01,"memoryBytes":703699353,"sequence":7}
{"cpuPercent":0.0, "memoryBytes":704643072,"sequence":12}
{"cpuPercent":0.01,"memoryBytes":705062502,"sequence":17}
{"cpuPercent":0.27,"memoryBytes":705796505,"sequence":22}
{"cpuPercent":0.07,"memoryBytes":706740224,"sequence":27}
{"cpuPercent":0.83,"memoryBytes":706949939,"sequence":32}
```

`sample_resources` runs synchronously immediately after the request it is
attached to has already completed, so every sample lands in the gap between one
request finishing and the next one being dispatched — not during generation.
During this same session, a manual `docker stats --no-stream` poll taken while a
request was actively generating read **801.97%** CPU against the same container.
The periodic samples above are real, unaltered readings; they describe the
container between requests, and that is a different quantity from the container
while answering one. Memory grew slowly and monotonically across the run, from
671.1 MiB at the first sample to 674.2 MiB at the last, consistent with
KV-cache state accumulating slightly across the session; it stayed well inside
the runtime package's 3 GiB limit throughout.

## Limitations

- **CPU utilization is not meaningfully captured by this run.** The sampling
  cadence, inherited unchanged from the registered method, measures the
  container between requests rather than during them. `cpuPercentMax: 0.83%`
  must not be read as this workload's CPU cost; a live observation during
  generation showed two orders of magnitude more. This is a property of when
  sampling happens relative to the request loop, not a defect fixed on this
  branch, and it was not in scope to change here.
- The result describes one host, one model, one runtime, one quantization, one
  parallel slot, and one request shape, on one day. It does not describe
  concurrent serving, sustained load, GPU execution, or Kubernetes.
- Individual request latencies range from 3.06 s to 23.5 s (7.68×) even though
  `P99`/`P50` (3.66×) stays inside the pre-registered `T5` bound. Nothing in
  this record isolates whether the range comes from the model, host thermal or
  scheduling variance, or another process sharing the CPU.
- The fixture that produced this result is not the one `V1-S2-005-PR1`
  registered; it is that fixture corrected for an API contract violation the
  first execution discovered. The correction and its justification are stated
  above and are not repeated here to keep this section short — see
  [Why this run succeeded](#why-this-run-succeeded-where-the-first-attempt-did-not).
- **No claim may cite this record for a performance figure.** It supports
  exactly the acceptance criteria the parent story states, and nothing about
  general runtime performance.

## Unexpected observations

Two, both worth carrying forward rather than treated as noise:

1. **The CPU-sampling gap described above.** A future change to the sampling
   cadence — sampling during a request rather than only after it — would close
   this, but that is a tooling change beyond this record's scope, not a
   correction to what is reported here.
2. **The wide latency spread** (3.06 s to 23.5 s, a nearly 8× range) on a host
   with 20 logical CPUs and no other declared workload during the run. Whether
   this is normal variance for CPU-bound decoding on this hardware, contention
   from something outside this project's visibility, or an artifact of the
   Docker Desktop virtualization layer is not established by this record.

## Authorisation

Required: **yes** — execution operates a container, reads the selected model's
bytes, and occupies the host's CPU for the duration of the measured phase.

Granted by: the host owner, in the session that ran it, on 2026-09-03. The same
authorization that covered the earlier failed attempt covered this one; no new
grant was sought because no new class of action was taken.

Retention: the unredacted source is
`.cache/inferops/composition/local-real.jsonl` on the executing host, under an
ignored path, overwritten by the next composition run. `raw.jsonl` and
`summary.json` are likewise under the ignored `.cache/inferops/baseline/` path
and are not retained beyond this host; this record and its quoted excerpts are
the retained form.

Cleanup verified: yes. `docker ps -a` reports no `inferops-` container after the
run. The composition log's own lifecycle events confirm ordered teardown:
`composition.api.stopped` (`drained: true`) followed by
`composition.runtime.removed` (`removed: true`), both reached without the
process being interrupted — the first time in this experiment's history that
cleanup completed as a consequence of the run finishing rather than of being
killed.
