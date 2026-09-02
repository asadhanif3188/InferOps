# Local LLM runtime profile

Status: **configured and validated offline; not packaged or started**.

The machine-readable source is
[`runtime-profile.local.v1.json`](runtime-profile.local.v1.json). Validate it
without downloading a model, resolving an image tag, opening a socket, or
starting a container:

```text
uv run --locked python -m tools.runtime_configuration check
```

This profile is one explicit local CPU selection for the generic real adapter.
It does not change the adapter's rule that runtime-specific settings have no
implicit defaults. Instead, later packaging and composition work can translate
this versioned record into the adapter environment and the runtime command.

## Pinned process and external model

| Setting | Selected value |
|---|---|
| Runtime | `llama.cpp` `llama-server` |
| Image | `ghcr.io/ggml-org/llama.cpp` pinned by multi-architecture digest |
| Source revision | `70adb1b4cea5ee39f867792c78dc59320921eda7` |
| Executable | `/app/llama-server` |
| Model source | [`model-source.v1.json`](model-source.v1.json) |
| Cache | `.cache/inferops/models`, outside the image and ignored by Git |
| Container model path | `/models/Qwen3-1.7B-Q8_0.gguf`, mounted read-only |

The validator compares the image and model identities with the accepted adapter
pins. It also requires the exact revision-scoped cache path from the model source
record. The profile contains no model bytes and no mechanism for putting the
artifact into an image.

The pinned command is `/app/llama-server` followed by the exact `arguments`
array in the JSON record. The executable is the selected server image's
entrypoint; spelling it out makes the process identity independent of an
implicit container default. The generic adapter still generates only the model,
alias, context, thread, and metrics arguments it owns. Bind, concurrency, and
generation defaults belong to this local deployment profile.

## Selected local CPU envelope

| Setting | Value | Basis and limitation |
|---|---:|---|
| CPU request / limit | 1 / 6 cores | The same bounded envelope used by the local-real feasibility trial |
| Memory request / limit | 2,048 / 3,072 MiB | The 3 GiB limit bounded a measured worst observation of 2.167 GiB on one host |
| Accelerator | none, count 0 | The selected V1 path is CPU-only; no GPU behaviour is claimed |
| Context | 4,096 tokens | An explicit local selection, not a universal recommendation |
| Threads / parallel slots | 6 / 1 | Single-slot V1 execution; concurrency and sustained load remain unmeasured |
| Default output / temperature | 128 tokens / 0 | Matches the bounded deterministic request used in the feasibility trial |
| Startup / request / drain | 300,000 / 120,000 / 15,000 ms | Startup and request budgets retain the trial's conservative bounds; drain matches the API lifecycle default |

These are minimum assumptions for this one profile, not production sizing and
not a benchmark. The evidence for the resource envelope is `local-real` on one
host; the act of selecting and validating the profile is `local-static`.

## Network, health, and metrics

The process binds `0.0.0.0:8080`. The adapter endpoint is explicitly
`http://llama-server:8080`; the service name is a local composition value and not
an address inferred by the adapter.

Startup and readiness use `GET /health`. Status `503` means model loading and
must remain not-ready; status `200` means the model can accept inference.
Liveness is a TCP check on port `8080`, so a healthy load does not become a
liveness failure. Runtime metrics are enabled at `GET /metrics` on the same
port. Packaging must implement these semantics and live verification must prove
them; this profile and its tests do not do either.

## Secrets and validation boundary

The profile requires secrets to remain external and permits no embedded value.
The selected model is publicly retrievable and the runtime endpoint contains no
credential. Future environment-specific credentials, if any, must be injected
outside this file and outside the image.

`tools/runtime_configuration` refuses drift from the runtime/model pins, a
mutable image tag, an alternate executable, a model inside the image, a writable
mount, unsafe cache paths, resources whose request exceeds their limit, an output
bound larger than the context, readiness that reports loading as ready, liveness
coupled to model readiness, inconsistent ports or arguments, embedded secret
values, and settings the real adapter cannot parse.

## Deferred to runtime packaging

No container or composition manifest is added here. No image was pulled, no
model was downloaded, and no runtime was started. The packaging change must
consume this profile, run the process without embedding the model or credentials,
exercise startup/readiness/shutdown, and record the resulting local-real trace.
