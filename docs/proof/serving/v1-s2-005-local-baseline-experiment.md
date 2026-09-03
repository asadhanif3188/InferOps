# `V1-S2-005` local serving baseline experiment

Date registered: 2026-09-03
Date executed: not executed

## Classification and certification

Evidence class: `documented-unexecuted`. The registered experiment declares
`local-real-cpu` as the class its results will carry; until it is executed, this
record is a method and carries nothing.

Ceiling this class carries: `none` today. The registered experiment's
`local-real-cpu` class carries `C2` once a run exists, per
[the certification document](../../testing/certification.md).

Level this record actually supports: **none**. It contains no measurement. It is
the pre-registration of a method, and the only thing it establishes is what will
be measured and what would count as a failure.

Claim boundary: this record establishes that a fixed request fixture, a warm-up,
a bounded measured phase, a metric set, a percentile method, and a success
condition were registered before any result was seen, and that the tooling
implementing them is consistent with the composition it will measure. It
establishes nothing whatsoever about latency, throughput, resource use, or the
behaviour of the selected runtime. No performance claim may cite it.

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

**Not filled in, deliberately.** The experiment has not been executed, so there is
no host to record. `tools.serving_baseline environment` captures this table's
contents at run time and writes them into the raw result set's header, so the
environment travels with the results rather than being transcribed alongside them.

| Property | Value |
|---|---|
| Host | To be captured at execution: architecture, logical CPUs |
| Memory and disk | To be captured at execution: total physical memory, free disk at start |
| Operating system | To be captured at execution: system and release |
| Container engine | To be captured at execution: engine server version |
| Cluster | none |
| Accelerator | none; CPU only — the profile pins `accelerator.kind` to `none` |

Number of hosts this was executed on: **zero**. When it is executed it will be
one, and every claim drawn from it will inherit that.

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

**Not executed.** No command in the procedure above that touches a real runtime
has been run.

| Threshold | Verdict | Measured or observed | Note |
|---|---|---|---|
| `T1` | not executed | — | Requires an authorized run on a capable host |
| `T2` | not executed | — | Requires an authorized run on a capable host |
| `T3` | not executed | — | Requires an authorized run on a capable host |
| `T4` | not executed | — | Requires an authorized run on a capable host |
| `T5` | not executed | — | Requires an authorized run on a capable host |

Commands that failed, and their output:

```text
None. The two commands that were run — `check` and `environment` — both
succeeded, and neither executes the experiment. No command requiring
--confirm-real-runtime was invoked.
```

Unexpected observations: none; nothing was observed, because nothing was run.

## Limitations

- This record establishes no latency, throughput, resource, or capacity figure,
  and no claim of any kind about the selected runtime's performance.
- Nothing varied between runs, because there were no runs.
- The measured phase, the resource sampling, and the model-load timing were not
  executed; a real run requires the pinned image and the verified model artifact
  on a capable host, and explicit authorization.
- When executed, the result will describe one host, one model, one runtime, one
  quantization, one parallel slot, and one request shape. It will not describe
  concurrent serving, sustained load, GPU execution, or Kubernetes.
- **No claim may cite this record for a performance figure**, and no figure the
  registered experiment eventually produces may be published as a benchmark. See
  [the project boundaries](../../architecture/project-boundaries.md).

## Authorisation

Required: **yes**, because execution operates a container, reads the selected
model's bytes from the verified cache, and occupies the host's CPU for the
duration of the measured phase.

Granted by: **not obtained**. The following stages were therefore not run: the
authorized composition start, the model load, the warm-up phase, the measured
phase, container resource sampling, raw result production, and summary generation
from real records.

Cleanup verified: not applicable; nothing was started, so nothing was left behind.
No container was created, no image was pulled, no model byte was read, and no
result file was written outside the ignored workspace cache.
