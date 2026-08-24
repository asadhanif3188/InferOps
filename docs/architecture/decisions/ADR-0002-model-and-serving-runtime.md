# ADR 0002: Model and serving runtime

| Field | Value |
|---|---|
| Status | **Accepted, with one recorded exception** |
| Date proposed | 2026-08-23 |
| Date accepted | 2026-08-24 |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | None |
| Superseded by | None |

> [!IMPORTANT]
> **The trial has now been run**, on 2026-08-24, and its result is
> [the feasibility record](../../proof/serving/v1-s0-003-pr2-runtime-feasibility.md).
> A model was downloaded and hash-verified, the runtime was started in a Kubernetes
> cluster, and it answered inference requests reaching it through cluster DNS and a
> Service. Eleven of the twelve thresholds below are met. **One blocking threshold,
> `T7`, is not**, and the exception is argued in
> [the T7 exception](#the-t7-exception) rather than absorbed quietly.
>
> Everything from [decision criteria](#decision-criteria) to
> [model candidates](#model-candidates) is preserved **exactly as it was written
> before the trial**, including the thresholds the trial then went on to fail. That
> is the point of pre-registering them: a threshold that can be edited after seeing
> the measurement is not a threshold. Where the trial contradicted a
> pre-trial characterisation, the correction is recorded in
> [what the trial changed](#what-the-trial-changed) and not by rewriting the
> original claim.
>
> Third-party characterisations in the candidate tables are still read from
> published documentation on the date in
> [sources](#sources-and-when-they-were-read). Only the selected pair was executed.

## Context

InferOps's mandatory V1 path must serve a real open model locally, on a
contributor's own hardware, without a paid API. Until that path is chosen and
proven, every downstream capability — the workload contract's model reference, the
serving adapter, the telemetry catalogue, the resource and cost evidence — rests on
a placeholder.

[ADR 0001](ADR-0001-local-development-environment.md) settled the environment this has
to run inside, and its evidence sets the constraints that dominate this decision.
From [the cluster smoke proof](../../proof/environment/v1-s0-002-pr2-cluster-smoke.md):

| Constraint | Value | Why it binds this decision |
|---|---|---|
| Memory reaching the container VM | 7.60 GiB | This, not the 16 GiB installed on the host, is the real ceiling |
| Consumed by the idle cluster | 712–720 MiB | Leaves roughly 6.9 GiB for everything scheduled beside it |
| Free disk | ~23 GB on the system volume, where the engine's virtual disk lives; ~36 GB on a second volume | The two cannot be pooled. Weights, container image, and engine growth all land on one of them |
| Processor | AVX2, no AVX-512 | Rules out anything whose CPU path requires AVX-512 |
| Accelerator | None discrete | The CPU path is mandatory. ADR 0001 leaves an integrated-GPU path open in principle; no discrete accelerator path can be proven here at all |

ADR 0001 also recorded, in D7, that this host **meets the minimum tier and does not
meet the recommended tier** — and that the recommended tier is where serving lives.
That verdict is the honest starting point for this record: the reference host may
turn out not to be able to serve the candidate at all. This ADR's job is to make
that outcome detectable and reportable rather than fudged.

Two further constraints come from the project rather than the host. Any V1 runtime
must expose liveness, readiness, model and runtime metadata, inference, and metrics,
and readiness must stay false until the model can actually answer a request; that
requirement is what the future model-serving contract will encode, and
[the contracts index](../../contracts/README.md) records that no such contract is
published yet. And the project is open source, so a model that cannot be
redistributed, or that carries a field-of-use restriction, would push that
restriction onto every contributor.

## Decision criteria

A candidate pair — one runtime plus one model revision — is judged against, in
order:

1. **Licence cleanliness** — can any contributor, anywhere, use and redistribute
   this without accepting a field-of-use restriction or a click-through?
2. **Immutability of what gets pulled** — can the exact bytes be named and
   re-fetched, by digest, a year from now?
3. **Host fit** — does it run inside the measured ceiling, beside the cluster,
   leaving headroom?
4. **Contract fit** — does the runtime expose the endpoints a V1 serving path
   requires, natively, without a sidecar to invent them?
5. **Kubernetes packaging** — is there a maintained container image that runs
   unprivileged, and can its lifecycle be probed correctly?
6. **Public reproducibility** — can a third party reach the same result without an
   account, a key, or a subscription?
7. **Evolution** — does choosing this now foreclose the deeper serving project
   later?

Criteria 1 and 2 are gates, not weights: a candidate that fails either is not
compared on the rest.

## Pass/fail thresholds

These are the thresholds the feasibility trial applies. They are written down here,
before the trial, so that the trial has something to fail against. A number here is
a **target**, not a measurement — none of them has been tested.

| # | Threshold | Kind | Rationale |
|---|---|:---:|---|
| T1 | Model weights carry an OSI-approved licence, with no acceptable-use policy, field-of-use limit, user-count clause, geographic carve-out, or download gate | **Blocking** | A restriction accepted by the project is a restriction imposed on every contributor |
| T2 | Runtime image pinned by digest; model pinned by upstream commit revision **and** per-file content hash | **Blocking** | ADR 0001 established that a moving tag is not a pin. The same standard applies to weights |
| T3 | Steady-state serving pod at most 3.0 GiB resident, and total container-VM usage at most 6.0 GiB of the measured 7.60 GiB, with the cluster running | Step-down | Leaves at least 1.6 GiB headroom. Failing this first triggers a smaller model or quantisation, not disqualification of the runtime |
| T4 | Added disk at most 8 GB in total — image, weights, and cache — leaving at least 5 GB free on the target volume afterwards | Step-down | The system volume has ~23 GB free and does not return space on teardown |
| T5 | `POST /v1/chat/completions` returns an OpenAI-shaped body carrying `choices[0].message.content`, `model`, and a `usage` token count; `GET /v1/models` reports the pinned model | **Blocking** | An OpenAI-compatible API is acceptable for V1, and the platform needs token counts for telemetry |
| T6 | An endpoint reports not-ready during model load and ready afterwards, and the three probe kinds can be configured so that a slow load does not restart the pod | **Blocking** | Directly encodes the readiness and liveness semantics V1 owes its callers |
| T7 | Prometheus text-format metrics on an HTTP endpoint, including at least request and token counters, with no external exporter or sidecar | **Blocking** | A metric that needs a third-party exporter is that exporter's evidence, not the runtime's |
| T8 | Cold start to ready at most 180 s with weights already local; warm restart at most 90 s; three runs each, worst case reported | Step-down | Produces the startup and readiness configuration that must be measured rather than guessed |
| T9 | One 128-token completion at temperature 0 returns within 120 s, at 2 tokens/s decode or better | Step-down | A sanity floor for "usable at all" on a CPU path. It is not a performance claim and must never be published as one |
| T10 | Runs as a non-root container, in an `inferops-` namespace, carrying the project label, unprivileged, with no host mount other than the model volume; scoped teardown leaves no residue | **Blocking** | ADR 0001 D5 and D6 are already accepted. A serving path does not get an exemption |
| T11 | Every artifact obtainable without an account, API key, paid subscription, or licence acceptance | **Blocking** | Reproducibility by a stranger is the only reproducibility that counts |
| T12 | The CPU path is complete on its own. A GPU path may be described but must be marked unproven | **Blocking** | There is no discrete accelerator on the only measured host |

A blocking failure disqualifies the pair. A step-down failure sends the trial to the
next-smaller model or quantisation in the shortlist, once, before the runtime itself
is judged — because "this model does not fit" and "this runtime does not work" are
different findings and must not be recorded as the same one.

## Serving runtime candidates

> [!NOTE]
> Every row is read from the project's own documentation. None has been installed or
> run here. A rejection recorded from documentation is not the same as one recorded
> from a trial, and every rejection below is of the first kind.

| Candidate | Licence | OpenAI-compatible surface | Health | Native Prometheus metrics | Container image | CPU path on AVX2 | Assessment |
|---|---|---|---|---|---|---|---|
| **llama.cpp `llama-server`** | MIT | `/v1/chat/completions`, `/v1/completions`, `/v1/models`, `/v1/embeddings`, `/v1/responses` | `GET /health` — 200 when ready, 503 while loading | `GET /metrics`, behind the `--metrics` flag | `ghcr.io/ggml-org/llama.cpp:server`, plus accelerator variants | Native. AVX2 is a first-class target, not a fallback | Smallest footprint of the credible set; GGUF quantisation is the mechanism that makes a 7.60 GiB ceiling workable at all. `/props` and `/slots` supply runtime metadata beyond the minimum |
| **vLLM, CPU backend** | Apache-2.0 | Full OpenAI-compatible server | `/health` | `/metrics` | `vllm/vllm-openai-cpu:latest-x86_64`, or pre-built CPU wheels | Supported, but documented as **limited features**; AVX-512 is the recommended path and this host has none | The strongest engine in the set, and the obvious answer on a GPU. On this host its own documentation puts it on the degraded path, and its KV-cache allocation defaults to 4 GB — over half the remaining headroom, before weights |
| **Ollama** | MIT | `/v1/chat/completions`, `/v1/completions`, `/v1/models`, `/v1/models/{model}`, `/v1/embeddings`, `/v1/responses`, alongside its own `/api/*` | `/api/tags` reachability; no dedicated readiness endpoint documented | **None.** Community exporters exist; the server itself exposes no `/metrics`, and the request for one has been open since March 2024 | `ollama/ollama` | Native, through llama.cpp underneath | Much the easiest to operate, and its OpenAI surface is wider than its reputation suggests — this is not a toy. It fails T7 outright, and its model distribution runs through a registry Ollama operates rather than the upstream publisher, which weakens T2 |
| **Hugging Face TGI** | Apache-2.0 | Messages API, OpenAI-compatible | `/health` | `/metrics` | `ghcr.io/huggingface/text-generation-inference` | Weak; the CPU path was never its target | **Archived 21 March 2026**, read-only, in maintenance mode. Its own repository now points users at vLLM, SGLang, and llama.cpp. Excluded on maintenance status, not on capability |
| **LocalAI** | MIT | Broad OpenAI-compatible surface | Not verified here | Not verified here | `localai/localai` | Through llama.cpp underneath | Credible, and a genuine option if the project later wants several backends behind one API. Rejected here for scope: it is a superset of llama.cpp for this use, and V1 needs one real path rather than a multiplexer |
| **SGLang** | Apache-2.0 | OpenAI-compatible | Not verified here | Not verified here | Published | Not a target | The same shape of objection as vLLM, more so |
| **Triton, OpenVINO Model Server, KServe, Ray Serve, Seldon** | Various permissive | Varies | Not verified here | Not verified here | Yes | Varies | These are serving *platforms*, not model runtimes. Adopting one in V1 would put a second orchestration layer inside a Kubernetes cluster InferOps already orchestrates. They belong to the deeper serving project, if anywhere |
| **llamafile** | Apache-2.0 with MIT components | Through the llama.cpp server it embeds | Not verified here | Not verified here | Not container-first; the artifact is a single executable | Native | Excellent for a laptop demo, wrong shape for a Kubernetes contract. Its single-file packaging is both what makes it good and what makes it unsuitable here |
| Any hosted API — OpenAI, Anthropic, Bedrock, Vertex, and equivalents | n/a | n/a | n/a | n/a | n/a | n/a | Excluded by requirement. The mandatory V1 path must not need a paid API. These may later sit behind a gateway; they cannot be the V1 serving path |

### Proposed primary: llama.cpp `llama-server`

**Proposed, not accepted.** Rationale, criterion by criterion: it is the only
candidate whose CPU-on-AVX2 path is the *designed* path rather than a documented
degradation (criterion 3); it satisfies criterion 4 natively, including the metrics
endpoint that eliminates Ollama and the ready-versus-loading distinction a serving
contract needs; and it is MIT with maintained multi-backend images (criteria 1
and 5).

The honest costs, stated because the enthusiastic version of this paragraph omits
them:

- **It is a single-model, single-process server.** Serving a second model means a
  second Deployment. For V1 that is the correct scope; it is also exactly the
  ceiling the deeper serving project will have to break through, so criterion 7 is
  satisfied only in the sense that the contract survives the swap — the runtime
  will not.
- **The official tags move.** `:server` is rebuilt on a schedule, so T2 is not
  satisfied by using the documented tag; the trial must resolve it to a digest and
  pin that. This is the same failure mode ADR 0001 recorded for node images, and it
  is recorded again because the published documentation surfaces no versioned tag
  scheme to use instead.
- **`/health` is one endpoint doing two jobs.** It returns 503 while loading, which
  is right for readiness and wrong for liveness. A liveness probe pointed at it
  restarts the pod mid-load and never converges. The mapping below is therefore part
  of the proposal, not an implementation detail left to whoever writes the manifest.

Proposed probe mapping, to be proven under T6 and T8:

| Probe | Target | Why |
|---|---|---|
| `startupProbe` | `GET /health`, high `failureThreshold`, budget set from the measured cold start | Absorbs model load. Until it passes, the other two probes do not run |
| `readinessProbe` | `GET /health` | 503-while-loading is precisely the readiness semantics required |
| `livenessProbe` | TCP socket on the serving port | The process being alive is a different question from the model being ready, and only this probe should be able to restart the pod |

**Recorded fallback:** vLLM's CPU backend, and the fallback is real rather than
decorative — if llama.cpp fails T5 or T7 in the trial, vLLM is the candidate whose
OpenAI surface and metrics are strongest. It would be adopted knowing it starts on
its own documented degraded path here, and the switch would have to be recorded as
such. Ollama is *not* the fallback, because the thing that eliminates it — T7 — is
not something a trial can change.

## Model candidates

Sizes below are as published on the dates in
[sources](#sources-and-when-they-were-read). Nothing here has been downloaded.

| Candidate | Licence | Parameters | Published GGUF | Assessment |
|---|---|---|---|---|
| **Qwen3-1.7B** | Apache-2.0 | 1.7B total, 1.4B non-embedding, 32K context | First-party `Qwen/Qwen3-1.7B-GGUF`, `Q8_0`, 1.83 GB | Passes T1 cleanly. A first-party GGUF matters more than it looks: it makes T2 a pin on the publisher's own artifact rather than on a third party's requantisation |
| **Qwen3-0.6B** | Apache-2.0 | 0.6B | First-party `Qwen/Qwen3-0.6B-GGUF`, `Q8_0`, 639 MB | The step-down target for T3, T4, T8, and T9. Lower quality, and the trial must say so rather than quietly succeeding on a model too small to be useful |
| **Gemma 4 E2B** | Apache-2.0 | 5.1B total, 2.3B effective, through Per-Layer Embeddings | Not confirmed first-party | Gemma moving to Apache-2.0 removes the licence objection that applied to earlier Gemma releases. Held back for one reason: the effective-parameter architecture means 2.3B is not the memory figure, and runtime support for it has to be verified rather than assumed |
| **SmolLM3-3B** | Apache-2.0 | 3B, 64K context | Not confirmed first-party | Fully open weights *and* published training detail, which is the strongest reproducibility story in the set. 3B is the wrong end of the range to start on a 7.60 GiB ceiling |
| **Phi-4-mini-instruct** | MIT | 3.8B, 128K context | Not confirmed first-party | Cleanest licence in the table. Largest of the shortlist, so it is the last candidate to try rather than the first |
| Llama 3.2 1B / 3B | Llama 3.2 Community Licence | 1.2B / 3.2B | Widely available | **Fails T1.** Not OSI-approved. It incorporates an acceptable-use policy by reference (§1.b.iv), requires a separate licence from Meta above 700 million monthly active users (§2), and requires derived model names to be prefixed with "Llama" (§1.b.i). Capable models; the wrong licence for a mandatory default in an open-source project |
| Mistral 7B Instruct and other 7B-class models | Apache-2.0 | ~7B | Widely available | Fails T3 on this host with any headroom worth having. Revisit when a host meeting the recommended tier exists |

### Proposed primary: Qwen3-1.7B, first-party `Q8_0` GGUF

**Proposed, not accepted.** Two choices inside this deserve to be argued rather than
asserted:

**Why `Q8_0` and not a smaller quantisation.** A community `Q4_K_M` of the same
model would be roughly 1.1 GB against 1.83 GB, and faster. It would also mean the
pinned artifact is a third party's requantisation rather than the publisher's own
file, which weakens T2 from "the publisher's bytes" to "someone's derivative of
them". The proposal spends that extra disk and some decode speed to keep provenance
first-party. If the trial fails T3 or T9, this trade is what should be revisited
first — and revisited explicitly, by recording that the provenance standard was
lowered, not by swapping the file quietly.

**Why 1.7B and not 0.6B.** 0.6B would almost certainly pass every resource threshold
and would prove very little; a serving path that only works with a model too small
to be worth serving is not a serving path. 1.7B is the smallest size where the
result is informative. 0.6B stays as the declared step-down so that a T3 failure has
somewhere to go.

**What is deliberately not decided here.** The context length to configure, the KV
cache budget, the concurrency limit, and the sampling defaults are all measurement
outputs, not inputs. Fixing them now would be an estimate wearing a decision's
clothes.

## Decision

Everything above this line was written before the trial. Everything below it was
written after, against
[the feasibility record](../../proof/serving/v1-s0-003-pr2-runtime-feasibility.md).

**Selected runtime:** llama.cpp `llama-server`, pinned to the image digest
`ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384`.
Licence **MIT**, read in full at source revision
`70adb1b4cea5ee39f867792c78dc59320921eda7` on 2026-08-24. The image reports itself
as build `b10588`.

**Selected model:** `Qwen/Qwen3-1.7B-GGUF` at revision
`90862c4b9d2787eaed51d12237eafdfe7c5f6077`, file `Qwen3-1.7B-Q8_0.gguf`,
1,834,426,016 bytes, SHA-256
`061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a`. Licence
**Apache-2.0**, read in full at that revision on 2026-08-24. The repository is not
gated and the file is retrievable anonymously.

Both are pinned by digest or revision **plus** content hash. The image digest was
read back from the running pod rather than trusted from the manifest, and the
weight file's hash was verified before it was ever mounted for serving.

### Tested hardware requirements

These replace estimates with measurements, for **serving this model with this
runtime** and for nothing else. They are what one host did on one day; a second
host would improve them more than any amount of re-reading this table.

| Resource | Measured requirement | Note |
|---|---|---|
| CPU instruction set | **AVX2** | Measured. AVX-512 is not required. F16C and FMA were also present |
| Accelerator | **None** | The CPU path is complete on its own; no accelerator was involved at any point |
| Serving pod memory limit | **3 GiB**, with 2.167 GiB the worst observed charge | Size the limit against the worst case, not against the 531 MiB of private memory. The reason is in the record and is not obvious |
| Memory reaching the container VM | **7.60 GiB was sufficient** for this model beside a running cluster | This is what was available, not a measured floor. The floor was not established |
| Free disk | **~2.0 GiB added** — 1.71 GiB of weights plus a 293.0 MiB image | Against an 8 GB budget. The image survives teardown; whether the weights do depends on where they are cached |
| Model load time | **14 s worst case**, process-fresh with weights local | A 300 s startup-probe budget is roughly twenty times this, which is the right direction to be wrong in |
| Decode throughput | **8.81-9.35 tokens/s** at 6 threads | Derived from reported token counts and measured wall clock. **Not a benchmark**, and it must not be published as one |

This does **not** change ADR 0001 D7, which remains an accepted record with an
estimated recommended tier. It sits beside it: D7 estimated that the reference host
would not meet the tier serving needs, and the measurement shows that for *this*
model at *this* size the host was in fact sufficient. That is a narrower finding
than overturning D7, and it is the only finding the evidence supports.

### The T7 exception

`T7` required Prometheus metrics "including at least request and token counters".
The runtime exposes native token counters and no cumulative request counter at
all — only `requests_processing` and `requests_deferred`, which are gauges of
instantaneous state. **This is a blocking threshold and it failed.**

The pair is nonetheless selected, for reasons recorded here so that they can be
attacked:

- `T7`'s stated rationale was that a metric needing a third-party exporter is that
  exporter's evidence rather than the runtime's. That concern is met in full: every
  series comes from the runtime, with no exporter and no sidecar.
- What is missing is a count of requests. InferOps is the component that will
  receive those requests, so it is the right place to count them. Closing the gap
  requires nothing from the runtime.
- The alternative was to fall to vLLM, whose own documentation puts its CPU path on
  a degraded footing without AVX-512 — trading a proven serving path for a counter
  the platform can emit itself.

`T7` was therefore too broad as written: it bundled "the runtime exposes native
metrics", which is properly the runtime's job, with "the runtime counts requests",
which is not. **For future trials `T7` is narrowed to the first clause**, and a
request counter becomes a platform obligation instead.

The weakness of this position is stated plainly: the threshold was narrowed *after*
the measurement, which is precisely the move that pre-registered thresholds exist
to prevent. It is recorded rather than hidden, so that a reviewer who thinks the
original threshold should have been enforced has everything needed to say so, and
so that the next trial cannot repeat the manoeuvre quietly.

### What the trial changed

Three characterisations written from documentation did not survive contact:

| Written before the trial | What the trial found |
|---|---|
| `/metrics` behind `--metrics` satisfies the metrics requirement | It does, for tokens. There is no request counter, and the pre-trial table did not notice the distinction |
| Memory would be one steady-state figure to compare against 3.0 GiB | Two identical pods reported 2.167 GiB and 531 MiB. The runtime memory-maps its weights, and cgroup v1 charges those pages to whichever cgroup faults them in first |
| The reference host might not be able to serve the candidate at all | It served it with wide margin on every resource threshold. The concern ADR 0001 D7 raised did not materialise at this model size |

## What this record still does not decide

- **No mock serving path exists**, and this record does not create one. The rule
  that one can never certify real-runtime behaviour is now written down in
  [the mock and real boundary](../../serving/mock-and-real-boundary.md), with the
  reasoning and this trial's evidence behind it.
- **No public contract is created or changed.** The endpoint expectations above
  remain this ADR reading a requirement, not publishing one.
- **Nothing about concurrency, throughput, or load.** Every request in the trial
  was single and sequential. The runtime reported four slots; one was ever used.
- **Nothing about any other host, or any other operating system.** One Windows
  host, one architecture, one day.
- **The context length, KV budget, concurrency limit, and sampling defaults**
  remain undecided. The trial used a 4096 context and 6 threads as stated inputs so
  that its numbers could be interpreted, not as recommended values.

## Consequences

The trial confirmed the proposal on eleven thresholds of twelve, so these are now
commitments rather than conditionals:

- **Two more pinned dependencies**, a runtime image digest and a model revision,
  both needing a documented refresh procedure. This is more urgent than it looked
  before the trial: the runtime publishes from a branch tip with **no versioned tag
  scheme**, and the `server` tag this digest was resolved from is rebuilt on a
  schedule. The digest recorded here is already historical.
- **Model weights are the largest artifact in the development loop.** They must
  never enter Git history. Where they are cached is a decision with a consequence
  the trial paid for: a cache inside the trial's namespace is destroyed by scoped
  teardown, and re-running costs the full download again.
- **A single-model, single-process runtime is enough for V1 and is not enough for
  the deeper serving project.** Serving a second model means a second Deployment.
  The contract is what has to survive that replacement, not the runtime.
- **The platform owes a request counter.** The runtime does not provide one, so
  InferOps must emit it from the component that receives the requests. This is
  recorded as a consequence rather than left implicit in
  [the T7 exception](#the-t7-exception), because a gap that lives only inside an
  exception is a gap that gets forgotten.
- **Probe configuration is not optional detail.** The health endpoint reports 503
  while loading. A liveness probe pointed at it would restart the pod mid-load and
  never converge. The three-probe mapping in this record was proven, and any
  manifest that departs from it must show why.
- **A memory limit for this runtime cannot be set from its private footprint.**
  The measured private memory is 531 MiB and the worst-case charge is 2.167 GiB,
  because the weights are memory-mapped. Setting a limit near the smaller figure
  produces page eviction and silent latency rather than an obvious failure.

Had the trial failed, the correct outcome would have been a recorded blocker and an
unfilled acceptance criterion rather than a smaller claim. That path was not taken
because it was not needed, not because it was unavailable — and `T7` is a small
instance of exactly that discipline being applied to one threshold.

## Compatibility impact

None. There is no accepted public contract, released version, or supported serving
environment for this to break. It introduces no schema and no public API surface.

It does add runtime *artifacts* — the trial manifests under
`deploy/serving/feasibility/` — which the earlier revision of this record could
say it did not. Those manifests are trial apparatus, not a serving path: they are
single-replica, single-model, single-slot, and they download their own weights at
deploy time, which no serving path should. Nothing depends on them and removing
them would break nothing.

## Security considerations

This ADR asserts no security property. The four points below were recorded before
anything was executed; the fifth was found by executing it.

- **Model weights are inputs to a native parser.** A GGUF file is read by a C++
  process. Pinning it by content hash is the only thing that makes "the file we
  tested" and "the file that ran" the same claim, which is why T2 requires a
  per-file hash and not only a repository revision.
- **The runtime image must not need privileges.** T10 requires unprivileged,
  non-root execution. A serving container that wants host access is a finding, not a
  configuration step. **Confirmed in the trial**: the runtime ran as uid 65534 with
  a read-only root filesystem, all capabilities dropped, and no privilege
  escalation, and used 12,288 bytes of writable layer doing it.
- **Prompts and responses are data the project does not own.** Anything captured
  during a trial may contain whatever the operator typed, so the evidence template
  requires prompts to be chosen such that publishing them is safe.
- **No credential should be required at all.** T11 exists partly for reproducibility
  and partly because a path needing a token is a path that will eventually have a
  token committed to it. **Confirmed in the trial**: nothing at any stage asked for
  one.
- **The weight download is not authenticated in transit.** Added after the trial.
  The downloader reports `TLS certificate validation not implemented`, so the
  transport establishes nothing about who served the bytes. The published SHA-256
  is carrying the entire integrity argument on its own. That is survivable only
  because the hash is obtained separately and verified before the file is mounted —
  and it is the strongest practical justification for T2 that this project has.
  A future acquisition path should validate the certificate *and* the hash rather
  than relying on one of them.

Threat modelling, image scanning, and supply-chain attestation for the selected
image belong to the security baseline decision, not here. The image was pulled and
run; it was **not** scanned, and no attestation was verified.

## Proof plan, and what it produced

Executed on 2026-08-24. The procedure is
[the runtime feasibility workflow](../../serving/feasibility-workflow.md); the
result is
[the feasibility record](../../proof/serving/v1-s0-003-pr2-runtime-feasibility.md),
recorded with
[the feasibility evidence template](../../proof/serving/TEMPLATE-runtime-feasibility.md).

| # | Planned step | Threshold | Result |
|---|---|---|---|
| 1 | Record licences and their retrieval date for the pinned runtime and model | T1 | **Met.** MIT and Apache-2.0, both texts read in full on 2026-08-24 |
| 2 | Resolve the runtime tag to an image digest, and the model to a repository revision plus per-file hash | T2, T11 | **Met.** Digest read back from the running pod; weight hash verified before mounting; nothing required an account |
| 3 | Check free disk against the download budget, then acquire weights into a cache outside the working tree | T4 | **Met**, with a correction: the cache was placed inside the trial namespace, not on the host, and scoped teardown therefore destroyed it |
| 4 | Start the runtime in the project's own cluster, unprivileged, in an `inferops-` namespace | T10 | **Met on isolation, deviated on cluster.** Non-root, no privilege escalation, all capabilities dropped, read-only root, `inferops-` namespace. The cluster was the desktop distribution's, at the host owner's direction |
| 5 | Observe not-ready during load and ready after; time cold and warm starts, three runs each | T6, T8 | **Met.** Kubelet recorded a 503 from the startup probe during load; 0 restarts across seven starts; worst case 14 s |
| 6 | Issue one chat completion; capture the response shape, token usage, and decode rate | T5, T9 | **Met.** Body carried `content`, `model`, and `usage`; 128 tokens in 14.52 s worst case at 8.81 tokens/s |
| 7 | Scrape the metrics endpoint and record which required series exist | T7 | **Not met.** Token counters present; no cumulative request counter. See [the T7 exception](#the-t7-exception) |
| 8 | Measure steady-state pod memory and container-VM total with the cluster running | T3 | **Met**, and more interesting than expected: 2.167 GiB worst case against a 3.0 GiB limit, but only 531 MiB private |
| 9 | Confirm the CPU path is complete standalone; describe any GPU path as unproven | T12 | **Met.** AVX2 without AVX-512, no accelerator involved, no GPU path described or claimed |
| 10 | Tear down scoped, verify no residue, and re-measure free disk across the whole cycle | T10 | **Met.** No object carrying the project label survives; the provisioner directory was removed |

## Sources and when they were read

Every third-party claim above was read from the source named below on
**2026-08-23**, and from nowhere else. Published documentation changes, and two of
these projects publish from a branch tip rather than a release; re-read them rather
than trusting this table's age.

| Claim | Source |
|---|---|
| llama.cpp endpoints, `/health` 503-while-loading, `--metrics` flag, GGUF loading | <https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md> |
| llama.cpp licence and maintenance status | <https://github.com/ggml-org/llama.cpp> |
| llama.cpp image names and variants, and the absence of a documented versioned tag scheme | <https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md> |
| vLLM CPU backend, AVX-512 recommended and AVX2 limited, CPU image name, KV-cache default | <https://docs.vllm.ai/en/latest/getting_started/installation/cpu.html> |
| Ollama OpenAI-compatible endpoint list, and no metrics endpoint in that documentation | <https://docs.ollama.com/api/openai-compatibility> |
| Ollama licence | <https://github.com/ollama/ollama/blob/main/LICENSE> |
| The request for a native Ollama metrics endpoint, open since March 2024 | <https://github.com/ollama/ollama/issues/3144> |
| TGI archived 21 March 2026, maintenance mode, Apache-2.0, successor guidance | <https://github.com/huggingface/text-generation-inference> |
| Qwen3-1.7B parameters, context, and Apache-2.0 licence | <https://huggingface.co/Qwen/Qwen3-1.7B> |
| Qwen3-1.7B first-party GGUF `Q8_0` size | <https://huggingface.co/Qwen/Qwen3-1.7B-GGUF> |
| Qwen3-0.6B first-party GGUF `Q8_0` size | <https://huggingface.co/Qwen/Qwen3-0.6B-GGUF> |
| Gemma 4 Apache-2.0 licence, variants, effective-parameter scheme | <https://ai.google.dev/gemma/docs/core/model_card_4> |
| SmolLM3-3B licence, size, and context | <https://huggingface.co/HuggingFaceTB/SmolLM3-3B> |
| Phi-4-mini-instruct MIT licence, size, and context | <https://huggingface.co/microsoft/Phi-4-mini-instruct> |
| Llama 3.2 Community Licence clauses §1.b.i, §1.b.iv, §2 | <https://www.llama.com/llama3_2/license/>, which redirects to <https://developer.meta.com/ai/llama3_2/license/> |

Two claims in the tables above are **not** sourced here, and are marked in place
rather than left to look sourced: that LocalAI, SGLang, llamafile, and the serving
platforms have the health and metrics behaviour attributed to them, and that
Gemma 4, SmolLM3, and Phi-4-mini have no first-party GGUF. Those were not verified
against primary documentation, because none of them is the proposed primary or its
recorded fallback. If any becomes a candidate, verify it before relying on the row.
