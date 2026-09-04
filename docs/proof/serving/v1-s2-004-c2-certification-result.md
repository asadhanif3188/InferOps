# `V1-S2-004` C2 real-runtime certification result

Date produced: 2026-09-04

Produced from [the raw-result template](../templates/TEMPLATE-raw-result.md).

This is the executed result the `V1-S2-004` story asked for and its implementation
PR could not supply. That PR built the certification workflow and said so plainly:
"This change adds a workflow, not a result." This record is the result. It is a
separate document because the workflow and the run it certifies are separate
claims, and collapsing them would let the workflow's tests be read as the run's
evidence.

## Classification and certification

| Field | Value |
|---|---|
| Evidence class | `local-real-cpu` |
| Ceiling this class carries | `C2` |
| Level this record supports | `C2`, for the smoke path it exercised and nothing wider |
| Evidence owner | serving |
| Evidence label written by the run | `local real runtime` |
| Outcome | `certified` |

The run loaded the pinned model artifact into the pinned runtime image on a real
CPU host, observed the runtime's own identity, and obtained one real completion
through the InferOps API. No mock adapter, no simulated response, and no synthetic
clock took part.

**Claim boundary.** This record establishes, for one image digest and one
hash-verified model revision, on one contributor CPU host, on one day, in **one**
run:

- that the workflow's hardware prerequisites were evaluated against the container
  engine's own figures and passed before anything was created;
- that the runtime reached measured readiness inside its budget, and the InferOps
  API reached readiness after it;
- that `GET /v1/models` reported a `real` adapter, the pinned model revision, and a
  runtime identity carrying no `mock` substring;
- that `POST /v1/chat/completions` returned HTTP 200 with non-empty content and
  runtime-derived token counts;
- that teardown drained the API and removed the runtime container.

It establishes **nothing** about throughput, capacity, concurrency, failure
recovery, any second host, any second run, or any deployed system. One request is
not a benchmark, and the workflow refuses to be used as one.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `47478a49848f98a590016cd4bb693a5bc799277c` on `main`, the Sprint 2 head |
| Branch | `fix/sprint-2-completion-remediation` |
| Producing command | `uv run --locked python -m tools.runtime_certification certify --confirm-real-runtime` |
| Certification descriptor | [`c2-smoke.v1.json`](../../../deploy/serving/certification/c2-smoke.v1.json) |
| Composition descriptor | [`composition.v1.json`](../../../deploy/serving/local/composition.v1.json) |
| Container image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model artifact | `Qwen/Qwen3-1.7B-GGUF`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, file `Qwen3-1.7B-Q8_0.gguf`, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Result file | `.cache/inferops/certification/c2-smoke.json` on the executing host, under an ignored path, overwritten by each run |
| Dependencies | The committed `uv.lock`, consumed with `--locked` |

The model hash was not taken on trust. The workflow verifies the cached artifact
end to end before it pays for anything else, and the same artifact was independently
re-verified by `tools.model_acquisition verify` and by `tools.model_lifecycle cache
--verify` on the same day; both matched the published digest.

## Environment

Where this ran: `capable-host`.

| Field | Value |
|---|---|
| Operating system | Windows 11 |
| Machine architecture | `AMD64` |
| Python | 3.12.12 |
| Container engine | Docker 29.7.2 |
| Engine logical CPUs | 20 |
| Engine memory | 8,158,400,512 bytes |
| Free disk on the model-cache volume | 85,894,676,480 bytes |
| Accelerator | None used; CPU only |
| API base | `http://127.0.0.1:8090`, loopback only |
| Runtime base | `http://127.0.0.1:8080`, loopback only |

No hostname, username, absolute local path, credential, prompt, completion, or
runtime response body is recorded here or in the generated result file. The host
facts above are exactly the set the workflow is permitted to publish, and a test
asserts that set.

## Method

Run from the public repository root, with the pinned image already present and the
model already cached and verified:

```text
uv run --locked python -m tools.runtime_certification check
uv run --locked python -m tools.runtime_certification certify --confirm-real-runtime
```

The first command is the offline descriptor validation and contacts nothing. The
second is the certifying run. It reads the engine's CPU, memory, and free-disk
figures and refuses before creating anything if any is short; verifies the cached
artifact's SHA-256; starts the runtime container; waits for the runtime's measured
readiness inside a 300,000 ms budget; starts the loopback InferOps API and waits for
its readiness inside a 122,000 ms budget; observes identity through `GET /v1/models`;
sends one fixed, neutral, public request to `POST /v1/chat/completions` inside a
120,000 ms budget; then tears down in reverse order.

What would have falsified the certification: an unmet prerequisite, a digest
mismatch, a readiness budget overrun, an adapter kind other than `real`, a `mock`
substring in the runtime or model identity, an unpinned model revision, empty
content, or absent or inconsistent token counts. Any of these exits non-zero and
writes a diagnostics record instead of a result.

## Results

Verdict: **supported**. The run certified.

| Observation | Value | Kind |
|---|---|---|
| Outcome | `certified` | measured |
| Certification level | `C2` | derived from the descriptor |
| Evidence class | `local-real-cpu` | derived from the descriptor |
| Evidence label | `local real runtime` | derived from the descriptor |
| Runtime readiness | 285,828 ms | measured |
| Runtime readiness budget | 300,000 ms | pinned |
| API readiness | 203 ms | measured |
| API readiness budget | 122,000 ms | pinned |
| Inference status | HTTP 200 | measured |
| Inference elapsed | 3,140 ms | measured |
| Prompt tokens | 20 | measured, runtime-derived |
| Completion tokens | 23 | measured, runtime-derived |
| Total tokens | 43 | measured, runtime-derived |
| Completion characters | 123 | measured |
| Generated text retained | `false` | asserted |
| API drained on teardown | `true` | measured |
| Runtime container removed | `true` | measured |

Prerequisite evaluation, all satisfied before anything was created:

| Prerequisite | Required | Observed |
|---|---|---|
| Engine logical CPUs | 6 | 20 |
| Engine memory | 4,294,967,296 bytes | 8,158,400,512 bytes |
| Free disk on the model-cache volume | 2,147,483,648 bytes | 85,894,676,480 bytes |

Identity observed through `GET /v1/models`:

| Field | Value |
|---|---|
| Adapter kind | `real` |
| Model identifier | `qwen3-1-7b-q8-0` |
| Model revision | `90862c4b9d2787eaed51d12237eafdfe7c5f6077` |
| Runtime name | `llama.cpp llama-server` |
| Runtime version | `sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Token usage declared | `true` |

### The results that disagree with the expectation

Two observations are recorded here because they are the ones a reader would
otherwise have to discover independently.

**The runtime readiness margin is thin.** 285,828 ms against a 300,000 ms budget
leaves 14,172 ms of headroom, under five per cent. This run passed; a run on a
busier host, or one competing for the same 20 logical CPUs, could plausibly exceed
the budget and refuse. The budget is not comfortable and this record should not be
read as evidence that it is. Nothing here establishes a distribution: one sample
cannot.

**Neither correlation nor request identifier was echoed.** The result records
`requestIdEchoed: false` and `correlationIdEchoed: false`. The descriptor sends
both, the assertions do not require them back, and the run certified without them.
That is the workflow behaving as written rather than a defect discovered here, but
it means this record carries **no** evidence that the API propagates a caller's
correlation identifier through the real adapter. Any such claim needs its own
evidence.

### The generated result file

The full content of `.cache/inferops/certification/c2-smoke.json`, which holds no
prompt, no completion, and no host identity beyond the published set:

```json
{
  "certificationId": "inferops-c2-real-runtime-smoke",
  "certificationLevel": "C2",
  "cleanup": { "apiDrained": true, "runtimeRemoved": true },
  "evidenceClass": "local-real-cpu",
  "evidenceLabel": "local real runtime",
  "host": {
    "engineLogicalCpus": 20,
    "engineMemoryBytes": 8158400512,
    "machine": "AMD64",
    "modelCacheFreeDiskBytes": 85894676480,
    "operatingSystem": "Windows",
    "pythonVersion": "3.12.12",
    "release": "11"
  },
  "identity": {
    "adapterKind": "real",
    "modelIdentifier": "qwen3-1-7b-q8-0",
    "modelRevision": "90862c4b9d2787eaed51d12237eafdfe7c5f6077",
    "runtimeName": "llama.cpp llama-server",
    "runtimeVersion": "sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384",
    "tokenUsageDeclared": true
  },
  "inference": {
    "completionCharacters": 123,
    "completionTokens": 23,
    "correlationIdEchoed": false,
    "elapsedMs": 3140,
    "generatedTextRetained": false,
    "promptTokens": 20,
    "requestIdEchoed": false,
    "status": 200,
    "totalTokens": 43
  },
  "outcome": "certified",
  "prerequisites": [
    { "name": "engine-logical-cpus", "observed": 20, "required": 6, "satisfied": true },
    { "name": "engine-memory-bytes", "observed": 8158400512, "required": 4294967296, "satisfied": true },
    { "name": "model-cache-free-disk-bytes", "observed": 85894676480, "required": 2147483648, "satisfied": true }
  ],
  "provenance": {
    "apiBaseUrl": "http://127.0.0.1:8090",
    "compositionId": "inferops-local-real",
    "modelFile": "Qwen3-1.7B-Q8_0.gguf",
    "modelRepository": "Qwen/Qwen3-1.7B-GGUF",
    "modelRevision": "90862c4b9d2787eaed51d12237eafdfe7c5f6077",
    "modelSha256": "sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a",
    "runtimeBaseUrl": "http://127.0.0.1:8080",
    "runtimeImage": "ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384"
  },
  "readiness": { "apiReadyMs": 203, "runtimeReadyMs": 285828 }
}
```

No diagnostics record was written, because nothing failed. The workflow's failure
path — a stage-named diagnostics record and a non-zero exit — therefore remains
**exercised only synthetically**, by the focused suite. This record is not evidence
that the failure path works against a real runtime.

## Limitations

- **One host, one run, one day.** Windows 11 on `AMD64`, CPU only, 20 logical CPUs
  visible to the engine. No other operating system, hardware class, or accelerator
  is covered, and a single run establishes no variance.
- **The readiness margin is under five per cent** and is stated above rather than
  buried. This record does not establish that the 300,000 ms budget is adequate in
  general.
- **One fixed request.** No concurrency, no duration, no rate, and no second
  prompt. Nothing here may be cited for latency, throughput, or capacity. The
  separate [baseline raw results](v1-s2-005-baseline-raw-results.md) are the only
  measurement record, and they make no production claim either.
- **The failure path was not exercised against a real runtime.** No diagnostics
  record exists from this run because none was earned.
- **Correlation and request identifiers were not echoed**, so no propagation claim
  rests on this record.
- **Not a cluster.** This is the local loopback composition, not Kubernetes. The
  matrix claim `the-selected-runtime-serves-a-real-completion-in-a-cluster` rests on
  [the feasibility trial](v1-s0-003-pr2-runtime-feasibility.md), not on this record.
- **This is not production.** Nothing here is deployed, exposed beyond loopback,
  authenticated, authorized, or defended.
- **This record stops being true** if the image digest, the model revision, the
  certification descriptor, or the prerequisite figures change. Each is named above
  by an immutable identifier so that a change is visible rather than silent.

## Authorisation

Required: **yes** — the run reads 1.71 GiB of real model bytes, operates a local
container, and occupies the host's CPUs for roughly five minutes.

Granted by: the host owner, on 2026-09-04, in the Sprint 2 completion review that
directed this run by name. No cost was incurred: no cloud capacity was allocated,
no paid service was contacted, and the image and model artifact were already present
on the host, so nothing was downloaded.

Cleanup: verified by the run itself and re-checked afterwards. The API was drained,
the runtime container was stopped and removed, and `docker ps -a` listed no
container after the run.

Review: recorded in
[the Sprint 2 completion review](sprint-2-completion-review.md), together with the
independent second-eye review of this change.
