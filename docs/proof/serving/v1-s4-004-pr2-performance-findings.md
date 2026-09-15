# V1-S4-004-PR2 — performance findings for one single-replica release on `docker-desktop`

Date analysed: 2026-09-15

Classification: **analysis of local real evidence.** Evidence class `local-real-cpu`. No
new load was sent, no cluster was contacted, and no figure below was measured for this
document. Every figure is taken from, or computed from, the record of
[the V1-S4-004-PR1 run](v1-s4-004-pr1-validation.md), its
[performance record](v1-s4-004-pr1-performance-record.v1alpha1.json), and the six
committed inputs that record regenerates from. The computed figures are in
[`v1-s4-004-pr2-findings.v1alpha1.json`](v1-s4-004-pr2-findings.v1alpha1.json), which
`python -m tools.performance_findings` derives only after the record has regenerated
byte for byte from its inputs.

> [!WARNING]
> **Everything here describes one experiment.** One release of the real profile,
> with one API replica and one runtime replica, on Docker Desktop's single-node
> cluster, on one host, serving one model through one runtime build with one parallel
> slot, driven by one fixed prompt, twice, in one 15-minute window. The degradation
> point below is a property of **that setup**. It is not InferOps's capacity, the
> chart's, the model's, or the runtime's. It is not a production SLO, and it is not a
> benchmark of Kubernetes, Docker Desktop, llama.cpp, or Qwen3. Nothing here says
> anything about `kind`, another host, a GPU, a second replica, another runtime
> configuration, or a different prompt
> ([ADR 0013](../../architecture/decisions/ADR-0013-bounded-local-performance-observations.md)
> D2).

## The setup every finding is bound to

| Setting | Value |
|---|---|
| Provider | `docker-desktop`: one node, Kubernetes `v1.34.3`, containerd `2.2.0`, kernel `5.15.146.1-microsoft-standard-WSL2`, cgroup v1; allocatable 12 CPU and 10188024Ki |
| Host | Docker Desktop `29.7.2` with 12 processors and 10 432 536 576 bytes. The load generator ran on Windows 11 with 20 logical processors and reached the API through a loopback port-forward. 12 pods of 3 other namespaces shared the node |
| Model | `qwen3-1-7b-q8-0`, `Qwen/Qwen3-1.7B-GGUF` revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077` |
| Runtime | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` with `--parallel 1 --threads 6 --ctx-size 4096 --n-predict 128 --temp 0`; one replica; limits 6 CPU and 3Gi |
| Release | Chart `inferops-llm-0.3.0`, revision 1; one API replica; request deadline 120 000 ms; output-token limit 128 |
| Workload | Load profile `sha256:4dc0fe4a4217f035875fcddbdb99b75246f3a74188d5eca8b4dbbec8f57081c5`: one fixture of 35 input tokens, a 3-request warm-up, then 60 requests each at concurrency 1 (`c1`, the baseline), 2 (`c2`), and 4 (`c4`), closed loop, through a loopback port-forward to the one API pod |
| Matrix | Descriptor `sha256:cae87607cd65fe3152f68fb487e723e0b085148abbabe99252ec0d9c153e4fc1`; two repetitions on 2026-09-14 between 16:17:27 and 16:29:50 UTC |
| Source record | `v1-s4-004-pr1-performance-record.v1alpha1.json`, usable, all eight checks passed; the findings file carries its LF-normalized SHA-256 |

## Method

- **Latency** is nearest-rank over successful requests, measured by the load generator,
  and includes the port-forward. **Rates** are successful requests over each phase's own
  window. Both are copied from the record.
- **A ratio to baseline** divides a phase's figure by the same run's `c1` figure.
- **A completion gap** is the time between two successive completions inside one phase.
  With one request in service at a time and more waiting, it is how long the next
  request took to serve.
- **Collector gauges** are the largest reading at a 15-second range step inside a phase
  window. The collector scrapes every 30 seconds, so a shorter excursion can be missed.
- **CPU** is the runtime pod's cgroup counter increase over the phase. **CPU throttling
  was not sampled**, so nothing here can say whether the 6-CPU limit held the runtime
  back.
- Warm-up phases are excluded from every comparison. They hold 3 requests and two
  resource samples each.

## Findings

### 1. Latency grew in proportion to concurrency; completed requests did not

| Run | Level | Concurrency | P50 ms | P95 ms | P99 ms | P50 / baseline | P95 / baseline | Successful requests/s | Rate / baseline |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `c1` | 1 | 1744 | 2258 | 2689 | 1.000 | 1.000 | 0.554 | 1.000 |
| 1 | `c2` | 2 | 3504 | 4100 | 4433 | 2.009 | 1.816 | 0.557 | 1.005 |
| 1 | `c4` | 4 | 6908 | 7244 | 7311 | 3.961 | 3.208 | 0.575 | 1.038 |
| 2 | `c1` | 1 | 1700 | 2074 | 2365 | 1.000 | 1.000 | 0.573 | 1.000 |
| 2 | `c2` | 2 | 3411 | 4437 | 4765 | 2.006 | 2.139 | 0.554 | 0.967 |
| 2 | `c4` | 4 | 6775 | 8614 | 9311 | 3.985 | 4.153 | 0.567 | 0.990 |

Median latency at concurrency 2 was 2.006–2.009 times its run's baseline, and at
concurrency 4 it was 3.961–3.985 times. Every measured phase of both runs completed
between 0.554 and 0.575 successful requests per second. The higher-load phases read
0.967–1.038 of their own baseline, below it in run 2 and above it in run 1. The largest
difference between the two runs at the **same** level is 0.019 per second, at `c1`. That
is about the size of the whole spread across levels, 0.021.

### 2. Nothing failed, and the deadline was never approached

All 360 measured requests and all 6 warm-up requests answered HTTP 200 with finish
reason `stop`. No timeout, transport error, or refusal occurred at any level. The
slowest request took 9 311 ms against a 120 000 ms request deadline. This matrix
therefore says nothing about how this setup fails. A queue long enough to reach the
deadline was never built.

### 3. The runtime served one request at a time, and the rest waited inside it

| Run | Level | Completion gap min / median / max ms | Runtime processing, max | Runtime deferred, max | API in flight, max | Collector steps | Fastest request position |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | `c1` | 1584 / 1743 / 2689 | 1 | 0 | 1 | 7 | 20 |
| 1 | `c2` | 1603 / 1753 / 2223 | 1 | 1 | 2 | 7 | 1 |
| 1 | `c4` | 1544 / 1726 / 1977 | 1 | 3 | 4 | 7 | 1 |
| 2 | `c1` | 1580 / 1701 / 2365 | 1 | 0 | 1 | 7 | 1 |
| 2 | `c2` | 1579 / 1721 / 2446 | 1 | 1 | 2 | 7 | 0 |
| 2 | `c4` | 1578 / 1710 / 2735 | 1 | 3 | 4 | 7 | 0 |

Four pieces of evidence agree:

- **The collector's gauges.** The runtime's `requests_processing` never read above 1 in
  any phase. Its `requests_deferred` read at most 0, 1, and 3 at concurrency 1, 2, and 4,
  one fewer than the callers. The API's in-flight gauge read at most the concurrency.
  The API held every caller's request open while the runtime held all but one of them
  deferred.
- **The completion gaps.** Across all four higher-load phases, no two requests completed
  less than 1 544 ms apart, and the median gap was 1 710–1 753 ms, close to the
  baseline's median latency of 1 700–1 744 ms. If the runtime had served two requests
  together, some completions would have landed close together. None did.
- **The fastest request.** In every `c2` and `c4` phase the fastest request was the
  first or second dispatched, at position 0 or 1. The request that found the slot free
  was one of the first dispatched; the others queued behind it.
- **The configuration.** The runtime was started with `--parallel 1`.

The latency ratios in finding 1 are what this arrangement produces. A caller waits for
the requests ahead of it, then for its own service of about 1.7 s.

### 4. The runtime used nearly all of its CPU limit at every level, including the baseline

| Run | Level | Runtime CPU m | Of 6-CPU limit | Runtime peak working set bytes | Of 3Gi limit | Node outside release m |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `c1` | 5944 | 99.1% | 546287616 | 17.0% | 518 |
| 1 | `c2` | 5993 | 99.9% | 546414592 | 17.0% | 541 |
| 1 | `c4` | 5992 | 99.9% | 546312192 | 17.0% | 520 |
| 2 | `c1` | 5952 | 99.2% | 546349056 | 17.0% | 477 |
| 2 | `c2` | 5989 | 99.8% | 555487232 | 17.2% | 536 |
| 2 | `c4` | 5994 | 99.9% | 557223936 | 17.3% | 513 |

Serving one request, the runtime's six threads kept its container at 99.1–99.9% of its
6-CPU limit in every measured phase, whatever the concurrency. The node had CPU the
runtime was not allowed to use: allocatable 12 CPU, and at most 541 millicores used
outside the release. Runtime memory stayed flat, at no more than 17.3% of its limit;
nothing in the memory readings points to memory as a limit here.

`c1` reads 40–50 millicores below `c2` and `c4` in both runs. **A hypothesis, not
established:** at concurrency 1 the runtime is idle between one response and the next
request, while at 2 and 4 a deferred request starts at once.

### 5. Tokens: one fixed shape, and a prompt cache that served nearly all of it

| Run | Requests | Input tokens sent | API input counter increase | Output tokens recorded | Runtime prompt tokens increase |
|---:|---:|---:|---:|---:|---:|
| 1 | 183 | 6405 | 6405 (absent before, read as 0) | 3111 | 217 |
| 2 | 183 | 6405 | 6405 | 3111 | 183 |

Every request sent 35 input tokens and received 17 output tokens, so every figure here
is for that shape alone. The API's input-token counter rose by exactly the tokens the
raw sets sent, in both runs. The record did not reconcile input tokens (its item 9);
this agreement is read from the collector's range series at 15-second steps, not from
the instant reads the record reconciles output tokens with.

The runtime's prompt-token counter rose by 183 in run 2, one per request, and by 217 in
run 1. This fits the release's first request evaluating its whole 35-token prompt, and
every later request evaluating one token after reusing the cached rest. That split is
**consistent with the totals, not observed per request**: the counter is a total.
Service times here reflect a prompt the runtime had almost entirely cached.

### 6. Model load was outside this matrix; the first request was slower

The model was loaded before the idle baseline began, so no load duration falls inside any
phase. The dashboard's model-load panel is not emitted and read empty at all eight
captures. The warm-up latencies, in dispatch order, were 2663, 1827, and 1672 ms in run 1
and 1838, 1688, and 1714 ms in run 2. The first request of the release was 0.8–1.0 s
slower than the other two in its warm-up. Its prompt evaluation (finding 5) is one
difference; the record does not isolate any other.

### 7. The two runs agree on medians and differ at the `c4` tail

| Level | P50 range ms | P95 range ms | P99 range ms | Rate range, successful requests/s |
|---|---|---|---|---|
| `c1` | 1700–1744 | 2074–2258 | 2365–2689 | 0.554–0.573 |
| `c2` | 3411–3504 | 4100–4437 | 4433–4765 | 0.554–0.557 |
| `c4` | 6775–6908 | 7244–8614 | 7311–9311 | 0.567–0.575 |

Medians differ by at most 133 ms between runs. The `c4` tail differs by 1 370 ms at P95
and 2 000 ms at P99. Run 2's `c4` phase had the longest completion gap of any higher-load
phase, 2 735 ms, against 1 977 ms in run 1's. With three requests deferred, one slow
service lengthens the wait of every request queued behind it. That is consistent with
the wider tail. **What made that service slow is not in the evidence.** Slow services
also happened at concurrency 1, up to 2 689 ms, where nothing queued behind them. Two
repetitions do not bound a tail, and with 60 requests a nearest-rank P99 is the slowest
single request of its phase.

### 8. The dashboard's latency and rate panels at a phase end are not that phase's figures

| Run | Phase end | Panel P50 ms | Panel P95 ms | Panel P99 ms | Raw P50 ms | Raw P95 ms | Raw P99 ms | Panel requests/s | Raw successful requests/s |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `c1` | 1777 | 2476 | 4278 | 1744 | 2258 | 2689 | 0.206 | 0.554 |
| 1 | `c2` | 2279 | 4698 | 4940 | 3504 | 4100 | 4433 | 0.405 | 0.557 |
| 1 | `c4` | 3914 | 9230 | 9846 | 6908 | 7244 | 7311 | 0.559 | 0.575 |
| 2 | `c1` | 2297 | 9407 | 9881 | 1700 | 2074 | 2365 | 0.378 | 0.573 |
| 2 | `c2` | 2266 | 4693 | 4939 | 3411 | 4437 | 4765 | 0.400 | 0.554 |
| 2 | `c4` | 3975 | 9255 | 9851 | 6775 | 8614 | 9311 | 0.563 | 0.567 |

Both panels take a five-minute window, and the phases last under two minutes, so a
phase-end reading mixes that phase with what came before it. These latencies fall in
the duration histogram's (1, 2.5], (2.5, 5], and (5, 10] second buckets, and a quantile
is interpolated inside one. At run 2's `c1` end the panel read a P95 of 9 407 ms while no `c1` request
took more than 2 365 ms, because the window reached back into run 1's `c4`. At run 2's
warm-up end it read P50 5 259 ms. The panels behave as
[their descriptions](../../telemetry/inference-operations-dashboard.md) say. For a
level's own distribution, the raw sets are the source, and the dashboard's
`queue-wait-p95` panel is not emitted, so the queueing in finding 3 is visible only
through the runtime's gauges.

## The degradation statement

**For this setup only** — `docker-desktop` on the host above, one API replica and one
runtime replica, `qwen3-1-7b-q8-0` at revision `90862c4b`, llama.cpp at image
`sha256:100de626…` with one parallel slot, six threads, and a 6-CPU limit, and the fixed
35-in, 17-out prompt of load profile `sha256:4dc0fe4a…`, run twice on 2026-09-14:

> **The observed degradation point is concurrency 2, the first level above the
> baseline.** From concurrency 1 to 2 and to 4, successful requests per second stayed
> between 0.554 and 0.575, a spread no larger than the difference between the two runs,
> while median latency rose about twofold and fourfold. Every added concurrent caller
> added waiting time and no completed work. No request failed at any level.

**The likely bottleneck, from correlated evidence:** the runtime's single parallel slot.
The runtime never processed more than one request at once, it deferred the rest, no two
completions landed closer than 1.54 s apart at any level, and it was configured with
`--parallel 1`. Within that slot, each request kept the runtime at 99.1–99.9% of its 6-CPU
limit for about 1.7 s.

**What this does not establish:**

- **Where this setup would degrade with other settings.** More slots, more threads, a
  different CPU limit, a second replica, or another prompt were not run. Whether any of
  them would raise the completed rate is unknown. On the same 6 CPUs, more slots might
  share the CPU and lengthen every service.
- **Whether the CPU limit throttled the runtime.** Throttling counters were not sampled.
  "Used 99.9% of its limit" and "was held back by its limit" are different claims, and
  only the first is recorded.
- **A capacity figure.** 0.554–0.575 requests per second is what this setup completed
  while serving one prompt of one shape. It is not a rate InferOps, the chart, the model,
  or the runtime "supports", and it must not be quoted without the setup above.
- **An SLO.** No latency here is a target, and no error budget follows from zero errors in
  366 requests.
- **Anything about another provider or host.** `docker-desktop` evidence says nothing
  about `kind`, and the host's other workloads were measured, not controlled.

## Why these results are not universal

- **The prompt was cached.** Nearly every request evaluated one prompt token (finding 5).
  An uncached or longer prompt changes every service time and every figure.
- **The output was short and identical.** 17 tokens, far below the 128-token limit.
  Longer generations lengthen each service and the queue behind it.
- **The node and virtual machine were shared.** 12 other pods ran, and 477–541
  millicores were used outside the release during measured phases.
- **The observer was inside the measurement.** The sampler's `docker exec` ran in the
  node, and every latency includes a port-forward.
- **One run pair.** Two repetitions in one window on one day. Nothing here measured how
  the figures move between days, with other background work, or under other Docker
  Desktop resource settings.
- **Closed-loop load.** Callers send the next request only after a response. An open
  arrival process would build a queue differently.

## Follow-up hypotheses, not implemented

Each needs a new, authorized run under a changed descriptor or profile. None is part of
this change, and none is a recommendation to change the release's defaults.

1. **Slots against CPU.** A run with `--parallel 2` at the same 6-CPU limit would show
   whether batching the two requests raises completed requests per second, or only
   splits the same CPU between them.
2. **Throttling.** Sampling the runtime cgroup's `cpu.stat` would separate "busy at its
   limit" from "held back by its limit".
3. **An uncached prompt mix.** Varied fixtures, or output lengths nearer the limit, would
   show how much of the 1.7 s service time the cached prompt hides.
4. **Queue wait as a signal.** `queue-wait-p95` is not emitted. The queueing here had to be
   inferred from runtime gauges and completion gaps.
5. **More repetitions.** Three or more would say whether run 2's `c4` tail is typical.

## Reproduce the computed figures

From Git Bash at the repository root, inside the locked environment. Neither command
contacts anything.

```text
python -m tools.performance_scenarios verify --dir docs/proof/serving --prefix v1-s4-004-pr1-
python -m tools.performance_findings verify --dir docs/proof/serving --record-prefix v1-s4-004-pr1- --findings docs/proof/serving/v1-s4-004-pr2-findings.v1alpha1.json
```

The second refuses a record that does not regenerate, is not usable, or claims a
benchmark, capacity, or a saturation judgement. The tables in this document are checked
against the findings file by
[`tests/serving/test_performance_findings.py`](../../../tests/serving/test_performance_findings.py).
The prose around them is checked by review only.
