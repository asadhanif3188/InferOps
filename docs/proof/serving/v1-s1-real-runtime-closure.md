# Sprint 1 real-runtime evidence closure

Date: 2026-09-02

This record closes the missing execution evidence for `V1-S1-004` and
`V1-S1-005`. It runs the committed, opt-in real-runtime suites against the
pinned llama.cpp image holding the hash-verified Qwen model. It also records the
runtime-only defect the first API run exposed and the passing run after that
defect was corrected.

## Classification

| Field | Value |
|---|---|
| Evidence class | `local-real` |
| Ceiling | `C2` |
| What ran | The seven adapter real-runtime checks and seven API real-runtime checks against a model-serving process in local Kubernetes |
| Claims supported | The pinned runtime and verified model answer through the real adapter; the InferOps API composition selects that adapter, reports readiness and model metadata, returns a non-empty real completion with runtime-derived usage, preserves identifiers, and retains its refusal boundary |
| Claims not supported | Production readiness, model quality, determinism, throughput, capacity, a network-served InferOps API process, or deployment derived from a `WorkloadContract` |

## Provenance

| Input | Value |
|---|---|
| Repository base revision | `96503868fcbcbf3e473f136989708ebc94892504` |
| Branch | `fix/sprint-1-evidence-closure` |
| Runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Resolved pod image ID | The same repository and digest requested by the manifest |
| Runtime build reported by `/props` | `b10588-70adb1b4c` |
| Model repository revision | `90862c4b9d2787eaed51d12237eafdfe7c5f6077` |
| Model file | `Qwen3-1.7B-Q8_0.gguf` |
| Expected and observed size | `1,834,426,016` bytes |
| Expected and observed SHA-256 | `061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Runtime settings | model path `/models/Qwen3-1.7B-Q8_0.gguf`; alias `qwen3-1.7b-q8_0`; context `4096`; threads `6`; startup budget `300000` ms |

The run used the working-tree correction described under [Results](#results).
The eventual reviewed commit containing this record and that correction is the
immutable source revision for the run; the base revision is retained here so the
change boundary is reproducible before that commit exists.

## Environment

| Field | Value |
|---|---|
| Host class | Contributor-owned Windows workstation |
| Operating system | Windows 11 Enterprise, `10.0.26200` |
| Processor | Intel Core i7-13700H, 20 logical processors |
| Host memory | 16,836,890,624 bytes |
| Docker client/server | `29.7.2` / `29.7.2` |
| Kubernetes client/server | `v1.36.1` / `v1.34.3` |
| Node | Debian 12, WSL2 kernel `5.15.146.1`, containerd `2.2.0` |
| Namespace | `inferops-serving-feasibility` |
| Deployment state at capture | one ready pod, zero restarts |
| Runtime reachability from pytest | temporary loopback-only Kubernetes port-forward |

The selected host volume had 89,322,881,024 free bytes before the run and
87,880,032,256 afterwards. No hostname, username, personal path, credential,
prompt, completion, or environment-variable value is retained here.

## Method

1. Inspect the contributor-provided external model cache and existing Docker
   storage for the pinned file. Neither contained it; the already-pinned runtime
   image was present.
2. With explicit host-owner authorization, apply
   `deploy/serving/feasibility/weights.yaml`.
3. Allow the bounded, resumable transfer to complete, then require the committed
   byte-count and SHA-256 checks to emit `WEIGHTS_VERIFIED_OK`.
4. Apply `deploy/serving/feasibility/llama-server.yaml` and wait up to 300 seconds
   for the deployment rollout.
5. Open `kubectl port-forward` from loopback port 8080 to the scoped Service.
6. Set the six committed runtime variables and three committed API-selection
   variables, then run:

   ```text
   uv run --locked python -m pytest tests/realruntime -m realruntime -q
   ```

7. Diagnose the first run, which exposed that the API sent the runtime's display
   name to the bounded telemetry label instead of its registered runtime ID.
8. Add the optional registered identifier to `RuntimeMetadata`, publish it from
   the built-in adapters, bind telemetry to it with a backward-compatible name
   fallback, and add focused regression coverage.
9. Run the focused regressions, then rerun the exact real-runtime command.
10. Run the full repository gates and inspect the resulting documentation links
    and diff.

The API suite drives the ASGI application in process. Its requests to
`llama-server` cross a real loopback socket and Kubernetes Service tunnel; the
InferOps API itself is not claimed to have listened on a socket.

## Results

| Check | Result |
|---|---|
| Model acquisition | completed in 866 seconds over three bounded resume attempts |
| Weight byte verification | passed: `1,834,426,016` observed |
| Weight SHA-256 verification | passed: observed value matched the committed hash |
| Runtime rollout | passed; one ready pod, zero restarts |
| First real-runtime run | 8 passed, 6 setup errors |
| First-run defect | the observed display name `llama.cpp llama-server` was not a well-formed value in the telemetry label vocabulary |
| Focused regressions after correction | 72 passed |
| Final real-runtime run | **14 passed in 14.57 seconds** |
| Final real-runtime verification | **14 passed in 16.77 seconds** |
| Default repository suite on the final working tree | 5,122 passed, 25 skipped, 14 deliberately deselected |
| Ruff lint | passed |
| Ruff formatting | passed |
| Strict mypy | passed; 117 source files checked |

The 14 final passes include a non-empty response from the real model through the
adapter and through the InferOps API, runtime-derived token counts, model and
runtime metadata, readiness, identifier propagation, and the API's unsupported
member refusal. Generated content was neither asserted verbatim nor retained.

## Limitations

- This is one local CPU host, one runtime image, one model revision, and one day.
- The elapsed pytest time is recorded only to reproduce the run; it is not a
  latency or performance claim.
- The API was exercised through ASGI in process. No ASGI server, API container,
  API Deployment, or API Service exists in this repository.
- The runtime was deployed from its feasibility manifest, not from a generated
  `WorkloadContract`; the broader platform deployment claim therefore remains
  `planned`.
- Failure-and-resilience and capacity layers were not run.
- The Kubernetes client/server minor-version skew warning was observed and did
  not prevent this scoped run; it is not evidence of cross-version support.

## Authorisation

The host owner explicitly authorized the pinned 1.71 GiB model download and the
local real-runtime workload on 2026-09-02. The run used no account, credential,
paid service, remote deployment, or unpinned model/runtime input. The namespace
and PVC are deliberately retained at handoff so the verified model is not lost
before review. The deployment was scaled to zero and the loopback tunnel was
closed after verification; the retained objects are disclosed rather than
presented as teardown evidence.
