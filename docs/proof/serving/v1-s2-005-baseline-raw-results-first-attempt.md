# `V1-S2-005` local serving baseline raw results

Date produced: 2026-09-03

Produced from [the raw-result template](../templates/TEMPLATE-raw-result.md).

## Classification and certification

Evidence class: `local-real-cpu`. A real pinned runtime was started from a
hash-verified model artifact on a real CPU host, and real HTTP requests were sent
through the real InferOps API to it.

Ceiling this class carries: `C2`.

Level this record actually supports: **none for any performance claim**, and `C2`
only for the negative finding it does establish. The run produced **zero
successful inference requests**. Every measured request was refused by the
InferOps API before it reached the runtime, so this record contains no latency,
no throughput, no token, and no per-request resource figure — because none was
produced, not because none may be published.

Claim boundary: this record establishes that the experiment registered in
[`v1-s2-005-local-baseline-experiment.md`](v1-s2-005-local-baseline-experiment.md)
was executed on an authorized host and **failed**, that the failure is
deterministic and reproducible offline, and that it is caused by two defects in
the `V1-S2-005-PR1` tooling rather than by the host, the model, the image, or the
runtime. It establishes **nothing whatsoever** about how fast the selected
runtime answers a request. No performance claim may cite it.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `fbf34f1328760e2c4ad1f026fa96beb13575b624` |
| Producing commands | `python -m tools.serving_baseline run --confirm-real-runtime` (twice); `python -m tools.runtime_packaging start/stop --confirm-real-runtime` (diagnostic) |
| Container image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model artifact | `Qwen/Qwen3-1.7B-GGUF`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, `Qwen3-1.7B-Q8_0.gguf`, 1,834,426,016 bytes, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` (verified by `tools.model_acquisition verify`) |
| Runtime source revision | `70adb1b4cea5ee39f867792c78dc59320921eda7` |
| Baseline descriptor | `deploy/serving/baseline/local-baseline.v1.json`, `sha256:11195084596ba9b1327092d8cfcbf3da8eb8b10748a3a27b1d91a96991e54db1` |
| Result file | **None produced.** See [the second defect](#b2-the-run-command-cannot-terminate) |
| Observation source | `.cache/inferops/composition/local-real.jsonl`, 46,516 bytes, `sha256:d8c0e237cb064b4924f0d179fad59a8499f479bfd586d06b2d33648b7a3f2179` |

The result file row is the important one. `raw.jsonl` and `summary.json` were
**never written**, so the artifacts the experiment was designed to produce do not
exist. The observations below come from the composition's own structured log,
which the API writes as it serves. That log lives under an ignored workspace path
and expires with the lane; the redacted excerpts here are what promote it into a
citable record.

## Environment

Captured by `python -m tools.serving_baseline environment` on the executing host,
immediately after the run:

```json
{
  "accelerator": "none; CPU only",
  "architecture": "AMD64",
  "containerEngineVersion": "29.7.2",
  "freeDiskBytes": 85907136512,
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

Number of hosts this was executed on: **one**. Every finding inherits that.

One environment property matters to the results and is not in the record above:
the model artifact is stored on the Windows filesystem and reaches the container
through Docker Desktop's virtual-machine bind mount. That path, not the model
size alone, is what produces the load times in [Results](#results).

## Method

Schema of the observation set (the composition log, one JSON object per line):

| Field | Type | Units | Meaning |
|---|---|---|---|
| `timestamp` | string | RFC 3339, UTC | When the API emitted the event |
| `inferops.event` | string | — | `deployment.started`, `request.received`, `request.refused` |
| `inferops.request.id` | string | — | `baseline-single-turn-fixed-v1-NNNN`, supplied by the baseline runner |
| `inferops.correlation.id` | string | — | `baseline-inferops-local-serving-baseline` |
| `inferops.outcome` | string | — | `client-error` for every request in this set |
| `inferops.error.code` | string | — | `contract-invalid` for every request in this set |
| `http.response.status_code` | integer | — | `400` for every request in this set |
| `inferops.duration.ms` | number | milliseconds | Time inside the API |
| `inferops.adapter.kind` | string | — | `real` throughout; no mock answered anything |

Format: JSON Lines, UTF-8, one record per API event. Composition lifecycle events
(`composition.starting`, `composition.runtime.ready`, `composition.api.ready`)
share the file and carry `elapsedMs` instead.

Collection procedure, exactly as configured:

```text
Descriptor: deploy/serving/baseline/local-baseline.v1.json
Fixture:    single-turn-fixed-v1, two messages (system + user), stream=false
Generation: maxOutputTokens=128, temperature=0, context=4096, parallelSlots=1
Execution:  3 warm-up requests, 30 measured requests, concurrency 1,
            requestTimeoutMs=120000, maxDurationSeconds=900,
            resource sample every 5 measured requests
Success:    30 successes, at most 0 failures, adapter kind real,
            model ref qwen3-1-7b-q8-0, completion status 200
```

What was removed before committing, and how:

```text
Nothing needed removing from the excerpts below, and that was established by
reading rather than asserted. The composition log's request records carry no
prompt and no completion by construction: the API's emission path records
identity, outcome, status, and duration only. Every line quoted below is
reproduced verbatim and in full, so a reader can confirm the absence rather
than take it on trust.

The one host-identifying value in the file is the deployment.started event's
correlation id, a per-process UUID. It is quoted below because it identifies a
process, not a person or a machine.

The environment record above is the sanitized capture the tooling produces: it
carries no hostname, user name, network identity, or absolute path.
```

## Results

| Summary | Value |
|---|---|
| Records | 70 lines: 3 composition lifecycle events, 1 `deployment.started`, 33 `request.received`, 33 `request.refused` |
| Successes / failures | **0 successful / 33 refused** |
| Span covered | `2026-09-03T12:29:43.072Z` to `2026-09-03T12:29:53.053Z` (9.98 s for all 33 requests) |
| Aggregates | None publishable and none produced. There is no latency distribution, because no request was answered |

> [!WARNING]
> V1 publishes no throughput, latency, capacity, or benchmark figure. Nothing in
> this record is one — not because a figure was withheld, but because the run
> produced none. See
> [the project boundaries](../../architecture/project-boundaries.md).

### Three execution attempts

| # | Command | Outcome |
|---|---|---|
| 1 | `tools.serving_baseline run --confirm-real-runtime` | **Refused, exit 3**: `the runtime did not become ready within the startup budget`. Cold model load exceeded the profile's 300,000 ms `startupBudgetMs`. Ownership-scoped cleanup ran and removed the container |
| 2 | `tools.runtime_packaging start --confirm-real-runtime` (diagnostic) | Readiness reached; the runtime's own log recorded `srv llama_server: model loaded` at `5.58.735` — **358.7 s**, against a 300 s budget. Stopped and removed with `tools.runtime_packaging stop` |
| 3 | `tools.serving_baseline run --confirm-real-runtime`, page cache warm | Runtime ready in **284,406 ms** across 243 readiness observations; API ready in **297 ms**; 33 requests sent; **all 33 refused with HTTP 400**; the command then hung and never wrote a result file |

Attempt 2 exists because attempt 1's refusal did not say how far past the budget
the load was, and a blocker report that cannot quantify the thing it blames is a
guess. It is a diagnostic measurement of model-load time, and it is the only
number in this record that came from a command other than the baseline's own.

### Model-load time against its budget

| Measurement | Value | Budget | Verdict |
|---|---|---|---|
| Cold load (attempt 2, measured) | 358,735 ms | 300,000 ms | **Over budget by 58.7 s** |
| Warm load (attempt 3, measured by the composition) | 284,406 ms | 300,000 ms | Inside budget, by 15.6 s |

The warm figure is inside the budget with roughly 5% of margin, and it is only
achievable because a previous attempt had already pulled the model through the
Docker Desktop bind mount. A first run on a cold host fails. This is a property
of the host's storage path, not of the model or the runtime.

### Every request was refused before reaching the runtime

All 33 requests — the 3 warm-up and the 30 measured — were refused identically.
One `request.refused` record, verbatim and complete:

```json
{"timestamp":"2026-09-03T12:29:43.432Z","level":"warn","inferops.event":"request.refused","service.name":"inferops-api","service.version":"0.0.0","deployment.environment":"local","inferops.capability.id":"inferops-native-serving","inferops.model.revision":"90862c4b9d2787eaed51d12237eafdfe7c5f6077","inferops.runtime.image.digest":"sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384","inferops.adapter.kind":"real","inferops.correlation.id":"baseline-inferops-local-serving-baseline","inferops.request.id":"baseline-single-turn-fixed-v1-0000","inferops.model.id":"qwen3-1-7b-q8-0","inferops.runtime.id":"llama-cpp-server","inferops.outcome":"client-error","inferops.error.code":"contract-invalid","http.response.status_code":400,"inferops.duration.ms":0.0}
```

Aggregated over the file:

```text
33  "inferops.event":"request.received"
33  "inferops.event":"request.refused"
33  "inferops.outcome":"client-error"
33  "inferops.error.code":"contract-invalid"
33  "http.response.status_code":400
     observed "inferops.duration.ms" values: 0.0, 15.0, 16.0
```

Request ids run `baseline-single-turn-fixed-v1-0000` through
`baseline-single-turn-fixed-v1-0032`, so the whole registered sequence was
attempted; nothing stopped early. The maximum time any request spent inside the
API is 16 ms, which is what refusing a body costs. The runtime's container
recorded no inference request at all, and `docker stats` sampled it at 0.00–0.17%
CPU throughout the request phase.

### `B1`: the registered fixture is outside the API's accepted surface

The refusal is deterministic, and it reproduces with no runtime, no container,
and no model — by handing the committed fixture to the API's own validator:

```text
fixture body : {"messages": [{"content": "You are a terse assistant. Answer in at most two sentences.", "role": "system"}, {"content": "Name three things a Kubernetes readiness probe is for.", "role": "user"}], "model": "qwen3-1-7b-q8-0", "stream": false}
message count: 2
roles        : ['system', 'user']
RESULT: REFUSED
  code   = contract-invalid
  member = messages
  reason = this deployment forwards exactly one user message; the serving adapter
           interface carries a single prompt and has no parameter a conversation
           could be passed through without inventing a prompt format
```

[`src/inferops/api/validation.py`](../../../src/inferops/api/validation.py)
documents this in its module docstring and enforces it in `_prompt`: a request
carrying more than one message, or a single message whose role is not `user`, is
refused with `contract-invalid`. The restriction is deliberate and tied to the
frozen serving-adapter interface, which carries one `prompt` string.

The registered fixture carries a `system` message **and** a `user` message. The
experiment as registered therefore cannot succeed against this API — not on this
host, not on any host, and not with any model.

Two things let this reach an authorized run:

- `tools/serving_baseline/` never imports `inferops.api.validation`, so
  `tools.serving_baseline check` validates the fixture against the composition,
  the profile, and the model record, but never against the surface that actually
  has to accept it. `check` exits `0` on the tree that produced 33 refusals.
- `tests/serving/test_serving_baseline.py` contains **zero** references to
  `parse_chat_completion`. Every request in that suite is answered by an injected
  seam, so the real validator never sees the real fixture.

### `B2`: the `run` command cannot terminate

Even with a fixture the API accepts, the run would not have produced a result
file. `tools.serving_baseline.execute` passes its measurement work to
`tools.local_composition.run_foreground` as an `on_ready` callback. After that
callback returns, `run_foreground` calls `server.join()`
([`tools/local_composition/core.py:627`](../../../tools/local_composition/core.py#L627)),
and `LocalApiServer.join` joins the thread running `serve_forever`
([`tools/local_composition/http_server.py:251`](../../../tools/local_composition/http_server.py#L251)).
That thread only ends when `request_stop` is called, which happens in the
`finally` block — that is, after an exception or a signal.

`run_foreground` is correct for the composition command it was written for, whose
job is to stay attached until interrupted. It is the wrong primitive for a
bounded measurement that must return.

Observed directly: attempt 3 finished its last request at `12:29:53.053Z` and was
still running 14 minutes later with the runtime container healthy, the runner
process pinned at 11.3 s of CPU, no established TCP connection, and no
`raw.jsonl`. `write_raw`, `summarize`, and `write_summary` are all downstream of
the `compose(...)` call and were never reached.

Every test that exercises `execute` injects a `compose` seam that returns after
calling `on_ready`, so no test observes the real `run_foreground` blocking.

### Threshold verdicts

Against the thresholds pre-registered in
[the experiment record](v1-s2-005-local-baseline-experiment.md):

| ID | Threshold | Blocking? | Verdict |
|---|---|---|---|
| `T1` | All 30 measured requests succeed with HTTP 200 | yes | **Failed.** 0 succeeded; 30 measured requests returned HTTP 400 |
| `T2` | Every answer carries `adapterKind: real` and `modelRef: qwen3-1-7b-q8-0` | yes | **Not evaluable.** No answer was produced. The refusals do carry `adapter.kind: real`, so nothing mock was involved |
| `T3` | Zero measured requests fail | yes | **Failed.** All 30 measured requests failed |
| `T4` | The model loads within the 300,000 ms startup budget | yes | **Failed cold** (358,735 ms), **met warm** (284,406 ms) |
| `T5` | P99 within 10× P50 | no | **Not evaluable.** No latency distribution exists |

Three blocking thresholds failed and one is not evaluable. The pre-registration
states the consequence plainly: *"Any of these means there is no baseline to
publish — not a weaker baseline."* No baseline is published.

## Limitations

- **This record contains no performance measurement of any kind.** No latency,
  no percentile, no throughput, no token rate, no per-request CPU or memory
  figure. Not one request was answered.
- The two model-load figures are the only real timings here. They describe one
  host's storage path on one day, they were produced by two different commands,
  and neither is a benchmark of anything.
- Nothing varied deliberately between attempts. The difference between the cold
  and warm load figures is page-cache state, which was not controlled — it was
  observed after the fact, and attempt 3's warm state is a consequence of
  attempts 1 and 2 having run first.
- The warm load's 15.6 s of margin against a 300 s budget is thin enough that
  attributing it to anything but this host on this day would be unsound.
- `B1` is fully characterized and reproduces offline and deterministically. `B2`
  is characterized by reading the source and by one direct observation of the
  hang; the hang was ended by terminating the process rather than by waiting for
  a timeout that does not exist.
- Because attempt 3 was force-terminated, its ownership-scoped cleanup did not
  run and the container was removed afterwards by an explicit
  `tools.runtime_packaging stop`. Attempt 1's cleanup, which was not interrupted,
  ran correctly on its own.
- **No claim may cite this record for a performance figure.** It supports exactly
  two claims: that the registered experiment fails as registered, and why.

## Authorisation

Required: **yes** — execution downloads and reads the selected model's bytes,
operates a container, and occupies the host's CPU.

Granted by: the host owner, in the session that ran it on 2026-09-03, after being
told the download size (1.71 GiB), its source, and the expected CPU cost. The
grant covered the model acquisition and the real baseline execution.

Retention: the unredacted source is
`.cache/inferops/composition/local-real.jsonl` on the executing host only. It is
under an ignored path, it is overwritten by the next composition run, and it is
not retained anywhere else. The excerpts above are the retained form; they are
quoted in full rather than summarized precisely because the source will not
survive.

Cleanup verified: yes. `docker ps -a` reports no `inferops-` container. No image
was pulled during these attempts — the pinned digest was already local. The model
artifact remains in the ignored workspace cache and was not committed.
