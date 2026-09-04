# V1-S3-003-PR1 — measured restart and reload

**Evidence class: `local-real-cpu`. Certification ceiling: `C2`.** One
contributor host, on CPU, on 2026-09-04. Two real starts of the pinned runtime
against the real 1.71 GiB artifact, with a real single-token inference probe in
each. Nothing here is a performance figure, a percentile, or a capacity
measurement, and nothing here happened inside Kubernetes.

Produced by:

```text
uv run --locked python -m tools.model_lifecycle restart --confirm-real-runtime
```

## What this comparison is, and what it is not

It is the [cold and warm start comparison](v1-s2-007-pr1-cold-warm-start.md) with
that comparison's one variable taken back out. `measure` reads the artifact end
to end **between** its two starts, deliberately, so the second start finds the
host file cache warm. `restart` reads nothing in between — the classification
taken between the starts stats the file and does not open it — so **the only
thing that changed between these two starts is that a runtime stopped and another
one began against the bytes it left behind.** The digest is re-read after both
starts, where a 1.71 GiB read can no longer move a figure.

It is **not a pod restart.** No InferOps API image is published and the model
cache claim is Terraform-owned and unwritten, so nothing has scheduled a
replacement pod against a surviving claim. This is the same property one layer
down: a container stopped, and the next one loaded from what survived.

## Environment

| | |
|---|---|
| Host | Windows 11, AMD64 |
| Engine | Docker 29.7.2 |
| Python | 3.12.12 |
| Image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model revision | `90862c4b9d2787eaed51d12237eafdfe7c5f6077` |
| Model SHA-256 | `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Started | 2026-09-04T12:37:30Z |

**A warm-up start preceded this comparison and was not part of it.** It is
recorded below with the rest of the day's attempts, and it matters: both arms
here ran against a host and a virtual-machine cache that a full model load had
just warmed. The lifecycle record already says the pre-start cache state is
observed rather than controlled; this is that disclosure made specific.

## The measurement

| | cold (first start) | restart (after the stop) |
|---|---:|---:|
| container created | 8,500 ms | 4,859 ms |
| first liveness pass | 8,829 ms | 4,984 ms |
| **ready** | **154,891 ms** | **129,328 ms** |
| inference probe | 391 ms, HTTP 200 | 391 ms, HTTP 200 |
| stop and remove | 1,328 ms | 1,296 ms |
| probe samples | 401 | 344 |
| samples while loading | 400 | 343 |
| cache state | `hit` | `hit` |
| artifact bytes | 1,834,426,016 | 1,834,426,016 |

Between the two starts: cache `hit`, 1,834,426,016 bytes, **stat only, not read**.
After both starts: SHA-256 re-read in 3,500 ms, matching the pinned digest.

`readyMsDelta` is **−25,563 ms**, the restart minus the first start.

### What that delta is worth

**Nothing on its own.** It is one pair of starts on one host on one day, and this
project's own attempts at the same experiment today spread from 129,328 ms to
338,375 ms — an order of magnitude more variance than the delta. The
[cold and warm comparison](v1-s2-007-pr1-cold-warm-start.md) reached the same
conclusion from three executions and recorded that no cold/warm effect could be
established in either direction. **No restart effect is established here either**,
and no figure in this record may be quoted as a restart cost.

The implied read rate is the number that explains the spread, and it is not a
model-loading rate: 1,834,426,016 bytes in 129,328 ms is 14.2 MB/s, and in
338,375 ms it is 5.4 MB/s. Every load this project has recorded on this host sits
between those, which is the throughput range of a Docker Desktop bind mount from
the Windows filesystem rather than anything about the model or the runtime.

## The properties the record claims about a restart

All five were measured. None is restated from the document.

| Property | Result | How it was established |
|---|---|---|
| The artifact survives the stop | **true** | The byte count matched at all three points — before the first start, between the two, and after the second — and the digest was re-read afterwards and matched |
| Readiness resets | **true** | The **first** probe sample of the restarted runtime reported `503`. A process that came back already ready would have reported `200` here and the property would have been false |
| The restart needs no network | **true** | It proceeded from a cache `hit`, which is the only state the record permits a start to proceed from without one |
| Liveness held while loading | **true** in both | 400 and 343 samples respectively in which liveness passed while readiness answered `503` |
| Readiness false until ready | **true** in both | Every sample but the last carried the loading status, and the last carried the ready status |

The second row is the one worth reading twice. It is the property that can fail,
and the suite proves it can: a scripted restart that answers `200` on its first
sample is reported as **not** a reset rather than passed over.

## Every attempt made today, including the ones that were refused

Five authorized executions and two no-budget diagnostics. The refusals are
recorded because they are the finding below.

| # | What was run | Outcome |
|---:|---|---|
| 1 | `restart --confirm-real-runtime` | **Refused** — not ready inside the 300,000 ms budget |
| 2 | `restart --confirm-real-runtime` | **Refused** — same |
| 3 | Diagnostic start, no budget | **Ready at 305,296 ms** |
| 4 | `restart --confirm-real-runtime` | **Refused** — same |
| 5 | Diagnostic start, no budget (the warm-up above) | **Ready at 338,375 ms** |
| 6 | `restart --confirm-real-runtime`, immediately after 5 | **Succeeded** — the measurement in this record |

The diagnostics were a scratch script outside the repository that used the
committed packaging code to start the container and polled readiness with no
budget. They exist to turn a refusal into a number and are not part of the
tooling; they produced no committed artefact.

Every attempt removed its container. `docker ps -a` was empty after each.

## A conflict this found, and did not resolve

**The accepted 300,000 ms `startup.budgetMs` is below loads this host produces.**
It is carried by
[`model-lifecycle.v1.json`](../../../deploy/serving/lifecycle/model-lifecycle.v1.json),
held to the container package by `load_lifecycle`, and it refused four of the six
runs above. Two no-budget diagnostics measured 305,296 ms and 338,375 ms; the
`V1-S2-005` first attempt had already recorded 358,735 ms.

The chart does not share that budget. `runtime.probes.startup.budgetMs` is
600,000 ms and the values file says why: *the measured loads do not fit inside
the smaller number.* So the release layer and the accepted runtime record
disagree about what a plausible load is, and the smaller of the two is the one
that decides whether this measurement can run at all.

**Nothing here changes it.** Raising a budget the container package pins is a
change to an accepted decision, it is outside this PR's boundary, and it is
reported rather than made. What made this measurement possible instead was a
warm-up start immediately before it, which is disclosed above rather than hidden
in the method.

## What this does not support

- **It is not a Kubernetes pod restart.** It says nothing about a replacement
  pod, a bound claim, a kubelet, or the init container this change added — that
  container has never been scheduled.
- **It is not a cold start.** Both arms were cache hits, both followed a full
  model load minutes earlier, and neither controlled the host page cache.
- **It establishes no restart effect.** The delta is smaller than the run-to-run
  spread of the same experiment on the same host on the same day.
- **It certifies no serving performance.** One single-token inference probe per
  start establishes that the runtime answered, and nothing about throughput,
  latency distribution, or concurrency.
