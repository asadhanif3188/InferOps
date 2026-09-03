# `V1-S2-005` local serving baseline experiment

Date registered: 2026-09-03
Date executed: 2026-09-03

## Classification and certification

Evidence class: `local-real-cpu`. Executed on an authorized CPU host on
2026-09-03, on the second attempt after a first attempt (`V1-S2-005-PR2`, not
merged at the time of this run) found the registered method could not succeed.
See [Correction to the registered fixture](#correction-to-the-registered-fixture)
below before reading the results.

Ceiling this class carries: `C2`, per
[the certification document](../../testing/certification.md).

Level this record actually supports: **`C2`.** All thirty measured requests
succeeded, all five pre-registered thresholds are met, and the full evidence —
raw records, provenance hashes, independently recomputed percentiles — is in
[the raw result record](v1-s2-005-baseline-raw-results.md).

Claim boundary: this record establishes the load time, per-request latency,
throughput, and resource use of one fixed request against one pinned image, one
hash-verified model, on one CPU host, at concurrency one, on one day. It
establishes nothing about a second host, a second model, concurrent serving,
sustained load, GPU or cloud execution, or any other configuration. **No figure
here is a benchmark, and none may be published as one.**

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision at registration | `965f66971a3a46182c8216bc3de9b0bd8b2a6572` (the base `V1-S2-005-PR1` branched from) |
| Repository revision at execution | `d60407741101e3a2516870e40c869c91ab77ce40` (branch `fix/v1-s2-005-baseline-tooling-defects`, a descendant of the row above) |
| Container image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model artifact | `Qwen/Qwen3-1.7B-GGUF`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, `Qwen3-1.7B-Q8_0.gguf`, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Runtime source revision | `70adb1b4cea5ee39f867792c78dc59320921eda7` |
| Baseline descriptor as executed | `deploy/serving/baseline/local-baseline.v1.json`, `sha256:ea98ce3f6cb5d0d94c1de6ad55e211ccaf3c75b01bfa3099e218a100eecdddea` |
| Tooling | `uv` with `--locked`; `pytest 8.x`, `ruff 0.16.x`, `mypy 2.x` as `pyproject.toml` pins them |

Every pin above is read from a committed record at load time rather than copied
here by hand; `tools.serving_baseline` refuses to load a descriptor that disagrees
with any of them.

## Correction to the registered fixture

**The fixture below is not the one this record originally registered.** The
original registered `fixture.messages` carried a `system` message and a `user`
message. `V1-S2-005-PR2` executed that fixture on 2026-09-03 and found every one
of thirty measured requests refused by the InferOps API with `contract-invalid`,
because the API accepts exactly one message, whose role must be `user`, by
design — the frozen serving-adapter interface carries a single `prompt` and has
no parameter a conversation could be passed through without inventing a prompt
format. The full evidence for that failure is on branch
`docs/v1-s2-005-local-baseline-results` (commit `39c6237`), not yet merged.

The fixture is corrected here, on a separate branch
(`fix/v1-s2-005-baseline-tooling-defects`), to fold the system instruction into
the single user message the API accepts:

```text
Before:
  system: "You are a terse assistant. Answer in at most two sentences."
  user:   "Name three things a Kubernetes readiness probe is for."

After:
  user:   "You are a terse assistant. Answer in at most two sentences. Name
           three things a Kubernetes readiness probe is for."
```

This is disclosed here rather than silently carried forward, because correcting
a pre-registered experiment after seeing it fail is exactly the kind of change
pre-registration exists to make visible. It is defended on one narrow ground:
the correction is a **binary acceptance gate**, not a measured value. Nothing
about the generation settings, the warm-up count, the measured count, the
concurrency, the duration bound, or any threshold below changed — the fixture
was corrected to be answerable, not to be answered faster or more favourably.
`load_experiment` was also changed, on the same branch, to call
`inferops.api.validation.parse_chat_completion` against the committed fixture at
load time, so a fixture the API would refuse now fails offline `check` rather
than reaching an authorized run again.

## Environment

Captured by `tools.serving_baseline environment` on the executing host and
carried in the raw result set's header:

| Property | Value |
|---|---|
| Host | `AMD64`, 20 logical CPUs |
| Memory and disk | 16,836,890,624 bytes physical memory; 85,906,444,288 bytes free disk at run start |
| Operating system | Windows 11 |
| Container engine | 29.7.2 |
| Cluster | none |
| Accelerator | none; CPU only — the profile pins `accelerator.kind` to `none` |
| Model storage path | Windows filesystem, reached by the container through Docker Desktop's virtual-machine bind mount |

The last row is not part of the captured record; it is added here because it
explains why model load measures in minutes rather than seconds on this host.

Number of hosts this was executed on: **one**. Every claim drawn from it
inherits that.

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
one user message (the system instruction folded into it — see
[the correction](#correction-to-the-registered-fixture) above), `stream: false`,
at most 128 output tokens, temperature 0, 4,096-token context, one parallel
slot; three warm-up requests discarded from every distribution; thirty measured
requests at concurrency one; a 120,000 ms per-request timeout; a 900-second stop
condition; a container resource sample every five measured requests.

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

**Executed on 2026-09-03, and the hypothesis holds.** Full evidence — raw
records, independently recomputed percentiles, provenance hashes — is in
[the raw result record](v1-s2-005-baseline-raw-results.md).

| Threshold | Verdict | Measured or observed | Note |
|---|---|---|---|
| `T1` | **Met** | 30 of 30 measured requests succeeded, HTTP 200 | |
| `T2` | **Met** | Every one of 33 records (warm-up and measured) carries `adapterKind: real`, `modelRef: qwen3-1-7b-q8-0` | |
| `T3` | **Met** | 0 failures | |
| `T4` | **Met** | 269,079 ms, against the 300,000 ms budget — 30.9 s of margin | The same host measured a 358,735 ms cold load in `V1-S2-005-PR2`'s attempt; this margin is real but not comfortable |
| `T5` | **Met** | P99/P50 = 3.66×, inside the 10× informational bound | |

The hypothesis was that thirty sequential requests would complete without
error, with P50 and P99 within one order of magnitude. Both held: latency
ranged 3,062–23,516 ms (P50 6,422 ms, P95 17,718 ms, P99 23,516 ms), throughput
was 121 requests/1000s and 2,067 output tokens/1000s over the 246,734 ms
measured window, and every completion carried exactly 17 output tokens —
expected at `temperature: 0` against one fixed prompt.

Commands that failed, and their output:

```text
None. `check`, `environment`, `run --confirm-real-runtime`, and `summarize`
all succeeded on this execution.
```

Unexpected observations:

1. Periodic CPU sampling read at or near 0% at every one of six samples, while
   a live `docker stats` poll during generation read 801.97%. The sampling
   cadence measures the container between requests, not during them — a
   property of when it runs, not a fault in this run. See the raw result
   record's [Results](v1-s2-005-baseline-raw-results.md#resources) for the
   full explanation.
2. Individual request latencies ranged 3.06 s to 23.5 s (7.68×) even though the
   pre-registered `T5` ratio (P99/P50, 3.66×) stayed well inside its bound.
   What drives that per-request range is not established by this record.

## Limitations

- This record establishes latency, throughput, load time, and token figures for
  **one run on one host on one day**, and no claim of any kind beyond that about
  the selected runtime's general performance.
- Nothing varied between requests deliberately; the fixture, settings, and
  environment were held fixed throughout, as registered.
- The periodic CPU sample materially understates actual load; see
  [the raw result record](v1-s2-005-baseline-raw-results.md#resources).
- The result describes one host, one model, one runtime, one quantization, one
  parallel slot, and one request shape. It does not describe concurrent
  serving, sustained load, GPU execution, or Kubernetes.
- `T4`'s margin (30.9 s against a 300 s budget) should not be read as a
  statement that this configuration reliably starts within budget: the same
  host measured a cold load 58.7 s **over** budget in the prior attempt.
- The fixture executed here is a corrected version of what was originally
  registered; see [the correction](#correction-to-the-registered-fixture).
- **No claim may cite this record for a performance figure**, and no figure
  here may be published as a benchmark. See
  [the project boundaries](../../architecture/project-boundaries.md).

## Authorisation

Required: **yes**, because execution operates a container, reads the selected
model's bytes from the verified cache, and occupies the host's CPU for the
duration of the measured phase.

Granted by: the host owner, in the session that ran it, on 2026-09-03. The same
authorization that covered `V1-S2-005-PR2`'s failed attempt covered this one; no
new grant was sought because no new class of action was taken — only the
fixture and the tooling changed.

Cleanup verified: yes. `docker ps -a` reports no `inferops-` container after the
run. The composition log's own lifecycle events confirm ordered teardown —
`composition.api.stopped` (`drained: true`) followed by
`composition.runtime.removed` (`removed: true`) — reached because `execute`
returned normally, not because the process was interrupted. No image was
pulled; the pinned digest was already local. The model artifact remains in the
ignored workspace cache and was not committed.
