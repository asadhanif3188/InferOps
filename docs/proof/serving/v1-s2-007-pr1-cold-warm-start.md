# `V1-S2-007` cold and warm start comparison

Date produced: 2026-09-03

Produced from [the raw-result template](../templates/TEMPLATE-raw-result.md).

## Classification and certification

Evidence class: `local-real-cpu`. The pinned runtime container was started from a
hash-verified model artifact on a real CPU host, six times, and each start was
polled to readiness and answered one real inference request before being stopped
and removed.

Ceiling this class carries: `C2`.

Level this record actually supports: `C2` for the **ordering** properties it
measured, and **nothing at all** for the cold/warm timing comparison it is named
after.

Claim boundary. This record establishes, for one pinned image and one
hash-verified model on one contributor CPU host on one day:

- that a TCP liveness probe passed continuously while the readiness endpoint
  answered `503` throughout every model load;
- that readiness stayed false until the runtime answered `200`, after which a
  bounded inference request succeeded immediately;
- that the model artifact verified byte-identical after every restart, so every
  start was a cache hit and none needed a network connection;
- that every container was stopped and removed.

It establishes **no cold/warm start difference.** The measured deltas do not
reproduce — they range over two orders of magnitude — and the spread between runs
(82,157 ms across the cold arm alone) exceeds every delta measured within a single
comparison. The reason is diagnosed in [Limitations](#limitations). No
latency, throughput, or load-time figure here is a benchmark and none may be
published as one.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | the working tree of `feat/v1-s2-007-model-lifecycle`, whose base is `639f4639edee4804aa424b87e9cba00fa5872c8f` on `main`. The command does not exist at that base — it is introduced by this branch — so the runs are attributable to the branch, not to a merged revision |
| Producing command | `uv run --locked python -m tools.model_lifecycle measure --confirm-real-runtime` |
| Container image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model artifact | `Qwen/Qwen3-1.7B-GGUF`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, file `Qwen3-1.7B-Q8_0.gguf`, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Lifecycle record | [`deploy/serving/lifecycle/model-lifecycle.v1.json`](../../../deploy/serving/lifecycle/model-lifecycle.v1.json) |
| Result files | `.cache/inferops/lifecycle/raw.jsonl` and `summary.json` on the executing host, under an ignored path, overwritten by each run |

The artifact hash was not taken on trust. Each comparison re-reads all
1,834,426,016 bytes and recomputes SHA-256 twice — once between the two starts and
once after the second — and both comparisons matched the published value every
time.

Three comparisons were run, six container starts in total. **Comparisons 1 and 2
were produced before the observation record gained its `readyStatus` and
`loadingStatus` fields; comparison 3 was produced by the code as committed.** Those
two fields copy the container package's pinned statuses onto the record so the
module does not restate them; they changed no timing, no sample, and no acceptance
value. Comparisons 1 and 2 are retained here because the point of this record is
the spread between runs, and discarding two of three runs would hide it.

## Environment

| Fact | Value |
|---|---|
| Operating system | Windows 11, AMD64 |
| Hardware class | 20 logical CPUs, 16,057 MiB total physical memory; **CPU only, no accelerator** |
| Free physical memory during the runs | between 904 MiB and 1,725 MiB, observed |
| Container engine | Docker Desktop, server 29.7.2 |
| Engine VM allocation | 8,158,400,512 bytes, 20 CPUs |
| Python | 3.12.12 |
| Container limits applied | 6 CPUs, 3,072 MiB memory, `--read-only`, `--cap-drop ALL`, non-root `65534:65534` |

Number of hosts this was executed on: **one**. Every figure below inherits that.

The model artifact reaches the container through Docker Desktop's virtual-machine
bind mount. [The `V1-S2-005` baseline record](v1-s2-005-baseline-raw-results.md#environment)
already identified that path as the reason model load takes minutes rather than
seconds on this host. It is also, as [Limitations](#limitations) explains, the
reason a host-side page-cache warm-up cannot be expected to show up in these
numbers.

## Method

Each comparison runs, in this order:

```text
1. refuse if a container already carries the package's own name
2. capture the engine version and the image and model identifiers
3. COLD START  — create the container, sample liveness and readiness together
                 until ready, issue one bounded inference probe, stop and remove
4. VERIFY      — read all 1,834,426,016 artifact bytes and recompute SHA-256
5. WARM START  — the same start again, against the same artifact
6. VERIFY      — read and recompute SHA-256 a second time
```

Step 4 is the only variable deliberately changed between the two arms: it is a
full end-to-end read of the artifact immediately before the warm start.

Sampling: liveness and readiness are asked **at the same moment**, with a 250 ms
sleep between samples, bounded by the package's 300,000 ms startup budget. The
250 ms is the sleep and not the period: each sample also runs a container-status
command and both probes, so the observed period was 355–400 ms
(`(readyMs − firstLivenessMs) / (samples − 1)` over the six starts below). Asking them together is the
whole point — a readiness trace alone cannot establish that the process was alive
during the load, and a liveness trace alone cannot establish that readiness was
still false. Liveness is a TCP connection to `127.0.0.1:8080`; readiness is
`GET /health`, where `200` is ready and `503` is loading.

The inference probe is the package's own: one message, `max_tokens` 1,
`temperature` 0, thinking disabled. Only its HTTP status is retained.

Schema of the result set:

| Field | Type | Units | Meaning |
|---|---|---|---|
| `observationId` | string | — | `cold` or `warm` |
| `cacheState` | string | — | `hit`, `miss`, or `partial` at the moment the start began |
| `artifactBytes` | integer | bytes | size of the cached artifact |
| `readyStatus` / `loadingStatus` | integer | HTTP | the statuses the package pins, copied onto the record |
| `createMs` | integer | ms | `docker run` returning, from the start of the observation |
| `firstLivenessMs` | integer or null | ms | first sample in which the TCP probe connected |
| `readyMs` | integer | ms | first sample in which readiness answered `200` |
| `inferenceMs` | integer | ms | the bounded probe's round trip |
| `inferenceStatus` | integer | HTTP | the probe's status; its body is discarded |
| `stopMs` | integer | ms | stop plus remove |
| `loadingObservations` | integer | count | samples in which readiness answered `503` |
| `livenessHeldWhileLoading` | boolean | — | liveness passed in at least one loading sample |
| `livenessNeverDroppedAfterItPassed` | boolean | — | liveness never failed again after first passing |
| `readinessFalseUntilReady` | boolean | — | no sample before the last reported ready |
| `samples[]` | array | — | `{elapsedMs, liveness, readinessStatus}` per poll |

Format: JSON Lines, UTF-8, one record per observation, plus a JSON summary derived
from the two.

What was removed before committing, and how. Nothing was removed, because nothing
sensitive is collected: the record's fields are the sixteen above — fifteen rows,
one of which names two — and a sample list of three scalars. The prompt and the completion never enter it — only the
probe's HTTP status is retained — and
`tests/serving/test_model_lifecycle.py::test_an_observation_record_carries_no_prompt_completion_or_model_byte`
asserts that a serialized observation contains none of `prompt`, `content`,
`message`, `choices`, or the artifact bytes. The result files themselves are not
committed; they live under the ignored `.cache/inferops/lifecycle/` path, and the
figures quoted below are the retained form.

## Results

Six starts, three comparisons. All times in milliseconds.

| Comparison | Arm | `createMs` | `firstLivenessMs` | `readyMs` | `inferenceMs` | `stopMs` | samples | liveness pass **and** readiness `503` |
|---|---|---|---|---|---|---|---|---|
| 1 | cold | 4,218 | 4,390 | 151,187 | 594 | 1,672 | 414 | 413 |
| 1 | warm | 4,906 | 5,047 | 167,219 | 484 | 1,234 | 451 | 450 |
| 2 | cold | 4,984 | 5,156 | 215,672 | 1,812 | 1,610 | 527 | 526 |
| 2 | warm | 5,937 | 6,140 | 215,906 | 547 | 1,531 | 529 | 528 |
| 3 | cold | 4,609 | 4,828 | 133,515 | 422 | 1,375 | 343 | 342 |
| 3 | warm | 6,688 | 6,938 | 202,047 | 469 | 1,531 | 495 | 494 |

Every acceptance property the lifecycle record defines held in every comparison:

| Property | Comparison 1 | Comparison 2 | Comparison 3 |
|---|---|---|---|
| `cacheHitInBothStarts` | true | true | true |
| `livenessHeldWhileLoading` | true | true | true |
| `readinessFalseUntilReady` | true | true | true |
| `artifactSurvivedRestart` | true | true | true |

**Liveness never failed, once, in any sample of any start.** Across all six
starts, all 2,759 probe samples connected, and the readiness endpoint answered
`503` on all but the final sample of each — **2,753 observations, across six
independent starts, in which a healthy process was loading a model and a liveness
probe pointed at its health endpoint would have been failing.** Within each start
the loading observations are consecutive: liveness passed from the first sample to
the last, with no drop in any of the six. The artifact SHA-256 re-verification
took 2,828 ms, 3,453 ms, and 4,781 ms.

### The result that disagrees with the expectation

The warm start was not faster. It was slower in every comparison, and by wildly
different amounts:

| Comparison | `readyMs` delta, warm minus cold |
|---|---|
| 1 | **+16,032** |
| 2 | **+234** |
| 3 | **+68,532** |

The between-comparison spread is what settles it. The cold arm alone ranged from
133,515 ms to 215,672 ms across the three comparisons — a spread of 82,157 ms,
larger than every delta measured within a comparison: 1.2 times the largest of
them, 5.1 times the next, and 351 times the smallest — and the same
host recorded 358,735 ms and 284,406 ms model-load times in
[the `V1-S2-005` run](v1-s2-005-baseline-raw-results.md) — both larger than every
figure here. **A cold/warm effect, if one exists on this host, is smaller than the
noise this host produces between identical runs.** No such effect is claimed.

The three deltas being positive is not evidence of a warm penalty either. Three
paired observations on one host, with a between-run spread of this size, support
no sign claim in either direction.

## Limitations

- **The cold arm was not cold.** The host's file-cache state before a comparison
  begins is observed, not controlled. The tool deliberately avoids reading the
  artifact before a cold start, but it cannot evict what a previous process — a
  previous comparison included — already put there. Windows offers no supported
  page-cache drop, and the runs were not spaced to let one occur naturally.
- **A host-side page cache may not reach the container anyway.** The artifact
  crosses Docker Desktop's virtual-machine bind mount. Warming the Windows page
  cache does not obviously warm what the guest reads through that boundary, so
  step 4 of the method may be changing less than its name suggests. This is a
  plausible mechanism, not a measured one; nothing here isolates it.
- **The host was memory-constrained throughout.** Between 904 MiB and 1,725 MiB of
  16,057 MiB physical memory was free. Load times of two to four minutes for a
  1.7 B-parameter Q8 model are consistent with that and not with the model's size.
- **A real cache miss was never measured.** Both arms of every comparison were
  cache hits. A miss is a 1,834,426,016-byte download; it was not authorized and
  was not performed. The miss and partial rows of the cache model are proved only
  by the synthetic-byte tooling suite.
- **`runtime-starting` was never observed in a sample.** The first probe of every
  start already found the TCP socket accepting, roughly 4 to 6 seconds in, because
  `llama-server` binds its port before it loads the model. The window in which the
  socket is not yet bound fell inside the `docker run` call. That the state exists
  is a property of the record; that a probe would see it is not evidenced.
- **One host, one day, six starts, CPU only.** Nothing here says anything about a
  second host, a GPU, a cluster, concurrency, or sustained load.
- **The `runtime-starting` state and the symbolic-link cleanup refusals are
  published but not exercised.** The first was never caught by a sample (above);
  the second are two tests that skip on this host because Windows would not let
  them create a link. Both are recorded in
  [the change-validation record](v1-s2-007-pr1-validation.md) rather than counted
  as evidence.
- **These figures must not be cited** by any claim about serving performance,
  capacity, cold-start cost, or model-load cost. They may be cited for the
  ordering properties in [Results](#results) and for nothing else.

## Corrections independent review made to this record

An independent review of the first commit checked every figure here against the
tables beside it and found four statements stronger than the data:

- **"the spread between runs is several times larger than the largest delta"** —
  the ratio is 1.2, not "several". The conclusion (no cold/warm effect) survives;
  the magnitude did not. Both the claim boundary above and the guide were
  corrected, and the ratios are now stated explicitly.
- **"every 250 ms"** — 250 ms is the sleep between samples, not the period. The
  sample counts in the results table imply 355–400 ms, and the method section now
  says so and shows the arithmetic.
- **"the record's fields are the fourteen above"** — the record emits sixteen
  keys; `inferenceStatus` was missing from the schema table. That table is what
  the no-leakage argument rests on, so an incomplete enumeration weakened it. The
  row was added.
- **"larger than two of the three deltas and comparable to the third"** — 82,157
  is larger than all three. An understatement, corrected for the same reason.

Two further corrections were factual rather than presentational: the provenance
row named the branch base, at which the producing command does not yet exist, and
the CHANGELOG said the comparison ran twice. Both are fixed.

Nothing in the measured data changed. No timing, sample count, or acceptance
value in this record was altered by the review.

## Authorisation

Required: **yes** — each comparison operates containers, reads the selected model's
bytes end to end, and occupies the host's CPU for several minutes.

Granted by: the host owner, in the session that ran it, on 2026-09-03, explicitly
and in advance of the first run, on the stated basis that the pinned image and the
verified artifact were already local so that no download and no paid infrastructure
were involved.

Retention: the unredacted source is `.cache/inferops/lifecycle/raw.jsonl` and
`summary.json` on the executing host, under an ignored path, overwritten by the
next `measure`. Comparisons 1 and 2 have already been overwritten by comparison 3
on that host. This record and its quoted figures are the retained form.

Cleanup verified: yes. Each start stops and removes its container in a `finally`,
and a start that could not verify the removal fails. After all three comparisons,
`docker ps -a --filter name=inferops-` reported no container. No image was pulled,
no model byte was downloaded, and the model cache was not touched by any command
in this record.
