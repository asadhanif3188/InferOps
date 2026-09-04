# Local runtime package

Status: **packaged and validated offline; real execution remains opt-in and was
not performed by this change**.

The machine-readable package is
[`container-package.v1.json`](../../deploy/serving/runtime/container-package.v1.json).
It translates the selected [local runtime profile](local-runtime-profile.md) into
one standalone Docker container. The separate
[local real composition](local-real-composition.md) composes this package with the
InferOps API. This package does not create a Kubernetes resource, download a model,
or pull an image.

Validate the descriptor, its runtime/profile agreement, and the command it would
run without contacting Docker or reading model bytes:

```text
uv run --locked python -m tools.runtime_packaging check
```

## Package boundary

| Setting | Selected value |
|---|---|
| Engine | Docker |
| Image | The profile's immutable `llama.cpp` digest; `--pull never` |
| Process | `/app/llama-server` plus the profile's exact arguments |
| Identity | container `inferops-llama-server`; user and group `65534:65534` |
| Model | Hash-verified workspace cache artifact bind-mounted read-only at `/models/Qwen3-1.7B-Q8_0.gguf` |
| Exposure | `127.0.0.1:8080` to container port `8080` |
| Resources | 1/6 CPU request/limit, 2,048/3,072 MiB memory request/limit, 256 processes, no accelerator |
| Writable space | 64 MiB `/tmp` temporary filesystem only |
| Restart | disabled so an invalid load does not loop |
| Engine command deadline | 30 seconds per Docker client invocation |

The root filesystem is read-only, Linux capabilities are dropped, privilege
gain is disabled, and only a loopback port is published. The descriptor carries
no credential field or value. The selected public model needs no credential;
future authenticated sources remain outside this package and image.

The package label `io.inferops.package=llama-cpp-local-runtime` is its cleanup
ownership boundary. Shutdown refuses to act when the selected container name
does not carry that exact label. An immediately exited container is removed only
after the same ownership check succeeds.

## Prerequisites for a real run

Real execution is deliberately separate from offline validation. Before opting
in, provide both prerequisites explicitly:

1. acquire and verify the model with the
   [model acquisition workflow](model-acquisition.md); and
2. pull the exact digest printed by the offline check using Docker.

The lifecycle command checks that Docker is available, that the pinned image is
already local, and that the cached model's complete SHA-256 matches its source
record. It performs no implicit pull, login, build, model transfer, or cache
cleanup.

## Startup, readiness, and shutdown

Each command that touches Docker or the selected model bytes requires the
explicit execution flag:

```text
uv run --locked python -m tools.runtime_packaging start --confirm-real-runtime
uv run --locked python -m tools.runtime_packaging live --confirm-real-runtime
uv run --locked python -m tools.runtime_packaging ready --confirm-real-runtime
uv run --locked python -m tools.runtime_packaging stop --confirm-real-runtime
```

`start` proves only that the container process remained running after creation.
`ready` then polls `GET /health` for at most 300 seconds. HTTP `503` means the
process is alive and the model is still loading; it is not readiness and it does
not trigger a restart. HTTP `200` is the only ready state. Container running
state guards startup, while the `live` command applies the profile's independent
TCP liveness check. An initially unopened socket is allowed only within the same
startup budget. Any other health status, process exit, or elapsed budget fails
clearly.

`stop` gives the owned process 15 seconds to stop and then removes its container.
Every Docker client invocation also has a 30-second deadline. An inspection error
is not treated as absence: absence is reported only after a successful filtered
container inventory finds no matching name. No command deletes the model cache
or pinned image.

The state these commands move a deployment through — and the answer each probe
gives while it is in each one — is published as
[the model lifecycle](model-lifecycle.md), whose record is checked against the
values this package pins. When one of them refuses or fails,
[the troubleshooting guide](local-runtime-troubleshooting.md) maps the symptom
and the exit code to the check that localizes it.

## Bounded direct-runtime smoke

On a capable and explicitly authorized host, the complete standalone lifecycle
is one command:

```text
uv run --locked python -m tools.runtime_packaging smoke --confirm-real-runtime
```

The smoke command starts the package, waits through loading until readiness,
sends one deterministic `/v1/chat/completions` request with a one-token maximum
and 120-second request budget, validates that a completion choice exists, and
attempts shutdown in a `finally` block. An unverified or incomplete shutdown
fails the smoke command. Generated content and runtime response bodies are never
printed. The output is limited to readiness duration and observation count,
inference HTTP status, and shutdown status.

This is a probe of the standalone serving runtime only. It is not evidence that
the InferOps API has been composed with that runtime, that a WorkloadContract has
been deployed, or that the package is production-ready.

## Validation and evidence limits

The default test lane uses injected Docker and HTTP seams. It verifies descriptor
drift checks, the exact command boundary, loading/readiness separation, bounded
timeouts, inference request bounds, explicit authorization, and ownership-scoped
cleanup without starting Docker or reading a model artifact. Those results are
`local-static` and synthetic.

A real smoke run would produce `local-real` observations for one host. No such
run was authorized or executed in this change, so no startup duration, resident
memory, real completion, or real shutdown result is claimed here. The earlier
feasibility record remains separate evidence and is not relabelled as output of
this package.
