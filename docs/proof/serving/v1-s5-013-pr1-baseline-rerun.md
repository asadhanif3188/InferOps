# V1-S5-013-PR1 — the local serving baseline, run again at a named revision

Date captured: 2026-09-26

Classification: **local real evidence**, `C2`. The registered local serving baseline
was executed again, from a fresh clone of `main` at a named commit with nothing
uncommitted before the first command or after the last, and every one of its five
pre-registered thresholds was met. Nothing here is mock, synthetic, or estimated.

This run exists to close release blocker `b1-local-baseline-code-unidentified`. The
[2026-09-03 baseline](v1-s2-005-baseline-raw-results.md) names
`d60407741101e3a2516870e40c869c91ab77ce40` as its revision, and the repository's history
dates that commit after the run, so nothing identifies the API and adapter code it
measured. That record stays exactly as it is and stays cited for what it did. **This
run does not recover what that one ran.** It is a second execution of the same
registered method, and it identifies its own code.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `bcad343133ba6fddfe38832a2694e71777cdd006`, the tip of `main` when this change began, in a fresh clone of the public repository; `git status --porcelain --untracked-files=all` printed nothing before the first command and after the last |
| Baseline descriptor | `deploy/serving/baseline/local-baseline.v1.json` at that revision, unchanged since `d604077`; SHA-256 of its committed content `03ea54d5eb321dacd95637484c6727e95f3c2c2cd52c00e58fe088e9d72a9c7c` |
| Container image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model artifact | `Qwen/Qwen3-1.7B-GGUF`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, `Qwen3-1.7B-Q8_0.gguf`, 1 834 426 016 bytes, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Runtime source revision | `70adb1b4cea5ee39f867792c78dc59320921eda7` |
| Raw result file | [`v1-s5-013-pr1-baseline-raw.jsonl`](v1-s5-013-pr1-baseline-raw.jsonl), 8 127 bytes, SHA-256 `06adba2f043f5cd70824056239a9b9b88b7b5959cfc9333ed01f4653ff963bda` |
| Summary file | [`v1-s5-013-pr1-baseline-summary.json`](v1-s5-013-pr1-baseline-summary.json), 2 098 bytes, SHA-256 `b4c95b9184f2e0fe163b7ed485e1ff15cbe42d1eef2ef18e1bbecc7081dea8c5` |
| Transcript | [`v1-s5-013-pr1-baseline-transcript.txt`](v1-s5-013-pr1-baseline-transcript.txt): the output of every command in the procedure below, the revision and the status before and after, and a UTC stamp before each step |
| Operating scripts | [the driver and the cluster-reading script](../environment/v1-s5-013-pr1-operating-scripts.txt) that printed the stamps, the revision, the status, and the cluster readings in the transcripts: not repository code, committed as evidence so the transcripts can be traced and repeated |

**The descriptor is the one the 2026-09-03 run registered.** Its last change is
`d604077`, the commit that corrected the fixture, and the 2026-09-03 record's hash of
it, `ea98ce3f…eecdddea`, is the SHA-256 of the same content with CRLF line endings — a
Windows checkout's bytes rather than the committed ones. So the thresholds, the
warm-up, the measured count, and the fixture are the same as that run's. The fixture
is the rewritten one, not the one first registered, for the reason that record gives.

**How the model reached the clone.** The artifact was copied from this host's
workspace cache into the clone's ignored `.cache/inferops/models/`, and its SHA-256 was
compared with the pin in the operating shell before the run; that copy and comparison
are not in the transcript. The same cached file was verified again, by byte count and
SHA-256, by the seed-image build minutes after the run, which
[the preparation transcript](../environment/v1-s5-013-pr1-cluster-prepare-transcript.txt)
records. Nothing was downloaded.

## Procedure

```text
git rev-parse HEAD && git status --porcelain --untracked-files=all
uv run --locked python -m tools.serving_baseline check
uv run --locked python -m tools.serving_baseline environment
uv run --locked python -m tools.serving_baseline run --confirm-real-runtime
uv run --locked python -m tools.serving_baseline summarize
git rev-parse HEAD && git status --porcelain --untracked-files=all
```

Run from the clone's root with the clone's own locked environment, after `uv sync
--locked`. The run step began at `2026-09-26T01:47:20.843Z` and the summarize step at
`2026-09-26T01:53:25.004Z`, both stamped by the operating shell.

## Environment

Captured by the run and carried in both result files:

| | |
|---|---|
| Host | One Windows 11 machine, AMD64, 20 logical CPUs, 16 836 890 624 bytes of memory, CPU only |
| Container engine | Docker 29.7.2 |
| Python | 3.12.12, from the locked environment |
| Cluster | none |

## Results

| Threshold | Registered before the run | Measured | Verdict |
|---|---|---|---|
| `T1` | All 30 measured requests succeed with HTTP 200 | 30 of 30, and 3 of 3 warm-up | **Met** |
| `T2` | Every answer carries `adapterKind: real` and `modelRef: qwen3-1-7b-q8-0` | Every one of 33 records | **Met** |
| `T3` | Zero measured requests fail | 0 | **Met** |
| `T4` | The model loads within the 300 000 ms startup budget | 221 000 ms | **Met** |
| `T5` | P99 within 10 times P50 (informational) | 3.47 times | **Met** |

| Figure | Value |
|---|---|
| Model load | 221 000 ms |
| API ready after the runtime | 187 ms |
| Measured latency, nearest rank | P50 2 703 ms, P95 8 860 ms, P99 9 375 ms; range 2 219 to 9 375 ms; mean 3 756 ms |
| Measured window | 121 859 ms |
| Output tokens | 17 on every one of 33 completions; 510 across the measured phase, 1 050 input |
| Resource samples | 6, CPU at most 0.01 %, memory at most 590 558 003 bytes |

Every percentile above was recomputed from the 30 measured latencies in the raw file
rather than read from the summary, and each matches.

> [!WARNING]
> **Not a benchmark.** These are descriptive figures of one run. V1 publishes no
> throughput, latency, capacity, or benchmark figure from them, and nothing may
> compare them with the 2026-09-03 run as a speed-up: the two ran on the same host
> weeks apart with whatever else that host was doing, and neither controlled for it.

**The processor samples understate the load, as they did on 2026-09-03.** The sampler
runs after a request has completed, so it reads the container between requests. Its
0.01 % is not this workload's processor use.

## Cleanup

The composition's own log recorded `composition.api.stopped` with `drained: true` and
then `composition.runtime.removed` with `removed: true`, and no `inferops-` container
remained on the engine afterwards. Both were read in the operating shell, from a log
that is host state under an ignored path and from the engine, and neither reading is
in the transcript. The clone's status, which the transcript does show, was still
empty.

## Limitations

- **One run, one host, one day, CPU only, concurrency one, one request shape.** It
  describes nothing about concurrent serving, sustained load, a GPU, Kubernetes, or
  another host or model.
- **It identifies its own code, not the 2026-09-03 run's.** The claim now rests on
  this run for its code identity; the earlier record says what it says, at a revision
  nothing identifies.
- The model load's margin, 79 s against a 300 s budget, is one observation. The same
  host was 58.7 s over that budget in the attempt before the 2026-09-03 run, so the
  budget is not reliably met on this host.
- The processor figure is not captured, for the sampling reason above.
- The run was made by the author of this change, an AI coding agent, in the session
  that wrote this record; no second engineer has repeated it.

## Authorisation

Required: **yes**. The run starts a real runtime container, loads a real model, and
occupies the host's processors.

Granted by: the host owner, in the session that ran it, for this rerun and the three
Docker Desktop reruns beside it. No model was downloaded; the artifact already on the
host was copied into the clone and verified.

Sensitive values removed before committing: none needed removing. The raw record set
carries no prompt and no completion by construction, and the transcript carries no
host name, account, or absolute path.
