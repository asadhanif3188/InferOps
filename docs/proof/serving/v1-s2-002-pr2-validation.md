# V1-S2-002-PR2 runtime packaging validation

| Field | Value |
|---|---|
| Date | 2026-09-03 |
| Evidence class | `local-static` and synthetic |
| Environment | Repository checkout, Python 3.12 locked environment |
| Model downloaded or read | **No** |
| Image pulled or container started | **No** |
| Runtime endpoint contacted | **No** |

## What was implemented

The selected `llama.cpp` runtime now has a versioned standalone Docker package
and one repository command that validates or deliberately operates it. The
package consumes the accepted runtime profile, requires the immutable image to
already be local, verifies the externally cached model before startup, and
supplies explicit start, TCP liveness, bounded readiness, direct-runtime smoke,
and ownership-scoped stop operations.

The package fixes loopback exposure, CPU and memory assumptions, process count,
non-root identity, a read-only root filesystem and model mount, bounded temporary
space, dropped capabilities, no privilege gain, and no automatic restart. It
does not compose the InferOps API or add a cluster deployment.

## Results

All commands ran from the repository root.

| Command | Result | Classification |
|---|---|---|
| `uv run --locked python -m tools.runtime_packaging check` | Passed. Printed the immutable image, container identity, loopback port, resource request/limit pairs, external read-only model boundary, and `not started` execution state | `local-static` |
| `uv run --locked python -m pytest tests/serving/test_runtime_packaging.py tests/testing -q` | 1,017 passed | `local-static`; runtime lifecycle responses and model verification are synthetic |
| `uv run --locked ruff check .` | Passed | `local-static` |
| `uv run --locked ruff format --check .` | 230 files already formatted | `local-static` |
| `uv run --locked python -m mypy` | Passed; 129 source files checked | `local-static` |
| `uv run --locked python -m pytest -q` | 5,219 passed, 25 skipped, 14 deselected | `local-static`, `mock`, and repository-only checks according to each existing lane |
| Changed-file whitespace, staged-diff whitespace, and relative Markdown link checks | Passed | `local-static` |

The focused suite proves descriptor validation and lifecycle mechanics by
injecting command and HTTP seams. It does not contact Docker, read the selected
model artifact, or make a network request.

The repository-wide Markdown trailing-whitespace check also reported existing
lines in `docs/proof/serving/v1-s1-002-pr1-cumulative-review-fixes.md`, which this
change does not modify. The changed-file check is clean; the pre-existing result
is recorded here rather than silently treated as a pass or expanded into this
change's scope.

## Selected package metadata

| Item | Value |
|---|---|
| Package | `llama-cpp-local-runtime` on Docker |
| Runtime | `llama.cpp` `llama-server` at the profile's immutable image digest |
| Entrypoint | `/app/llama-server` plus the profile's exact argument vector |
| Model | Profile-selected, hash-verified workspace cache artifact mounted read-only |
| Port | `127.0.0.1:8080` to container port `8080` |
| CPU | request 1 core; limit 6 cores |
| Memory | request 2,048 MiB; limit 3,072 MiB |
| Accelerator | none |
| Context / parallel | 4,096 tokens / one slot |
| Startup / request / stop | 300,000 / 120,000 / 15,000 ms |

## Startup, readiness, and shutdown behavior

- Startup requires `--confirm-real-runtime`, a reachable Docker engine, the
  already-local pinned image, and the complete model artifact matching its
  recorded SHA-256.
- Container running state guards the load. TCP port `8080` is the independent
  liveness check selected by the profile.
- Readiness permits an initially unopened socket and HTTP `503` only within the
  300-second startup budget. HTTP `200` is the only ready result. A stopped
  container or any other HTTP status fails.
- The smoke request permits one output token, temperature zero, and a 120-second
  deadline. It requires non-empty completion content but never returns or prints
  that content.
- Shutdown acts only on the exact package-owned container name and label, waits
  up to 15 seconds, and removes the container. It does not delete the model cache
  or image.

## Commands deliberately not executed

- `tools.model_acquisition acquire`: not run because it downloads the selected
  large model and no authorization was given.
- An explicit Docker pull of the pinned image: not run because network and image
  acquisition were not authorized.
- `tools.runtime_packaging start`, `live`, `ready`, `smoke`, or `stop` with
  `--confirm-real-runtime`: not run because real model inspection and runtime
  execution require explicit authorization.
- InferOps API composition, Kubernetes, load, paid-service, and production
  commands: not run and outside this change boundary.

## Acceptance status

| Criterion | PR status | Evidence and limitation |
|---|---|---|
| Runtime version and command are pinned | **Met** | Package/profile agreement and exact command-vector tests; no image execution |
| Model remains external | **Met** | Only the profile-selected cache artifact can be mounted, and only read-only |
| Ports, resources, context, concurrency, and defaults are explicit | **Met** | Package descriptor plus selected runtime profile |
| Startup is bounded and readiness waits for inference capability | **Met for workflow mechanics** | Synthetic unavailable, loading, ready, timeout, and process-exit paths; no real load observed |
| Liveness does not turn model loading into restart failure | **Met for configuration and workflow mechanics** | Independent TCP rule, no automatic restart, and 503 treated as loading; no real orchestrator run |
| Startup, smoke, and shutdown commands exist | **Met** | Authorization-gated CLI and synthetic lifecycle tests |
| No credential or model artifact is embedded | **Met for this diff** | Empty embedded-value field, external mount, ignore policy, and public-diff inspection |

## Limitations

- No local-real startup duration, readiness transition, completion, memory use,
  or shutdown result was produced by this change.
- Docker applies limits but has no scheduler-style request reservation; request
  values remain explicit sizing assumptions copied from the profile.
- The TCP liveness command proves socket acceptance only. Readiness remains the
  separate inference-capability signal.
- The package is standalone. It does not prove InferOps API-to-runtime
  composition, WorkloadContract deployment, cluster behavior, concurrency under
  load, or production suitability.

## Independent review

An independent second-eye review is performed after the first implementation
commit. Its findings and the follow-up commit are recorded here before push.
