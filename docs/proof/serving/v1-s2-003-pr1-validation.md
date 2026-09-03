# V1-S2-003-PR1 change validation

| Field | Value |
|---|---|
| Date | 2026-09-03 |
| Scope | Host-local InferOps API plus selected real runtime composition |
| Source branch | `feat/v1-s2-003-local-real-composition` |
| Evidence produced here | `local-static`, `mock`, and `synthetic` only |
| Real-runtime execution | Not authorized and not run |

## Implemented boundary

The committed descriptor and command compose the existing digest-pinned runtime
package on `127.0.0.1:8080` with an explicitly real InferOps API on
`127.0.0.1:8090`. Validation refuses a mock selection, fallback, non-loopback API,
configuration drift, embedded secret values, or lifecycle-order drift.

`start` creates and readies the runtime before starting and readying the API. It
stays attached in the foreground. Exit drains and closes the API before stopping
the ownership-labelled runtime container. `status`, bounded structured `logs`, and
residual `cleanup` are separate documented commands. No command implicitly
downloads a model or pulls an image.

## Validation results

| Command | Result | Evidence boundary |
|---|---|---|
| `uv run --locked python -m tools.local_composition check` | Passed; real selection, loopback endpoints, readiness URL, local log path, and unexecuted status printed | `local-static`; contacted no runtime or Docker |
| `uv run --locked ruff check .` | Passed | Repository-static |
| `uv run --locked ruff format --check .` | Passed; 237 files already formatted | Repository-static |
| `uv run --locked python -m mypy` | Passed; 134 source files checked | Repository-static |
| `uv run --locked python -m pytest tests/api/test_local_real_composition.py -q` | Passed; 10 tests | Controlled synthetic composition path |
| `uv run --locked python -m pytest -q` | Passed; 5,244 passed, 25 skipped, 14 deselected | Default lane; real-runtime tests remained deselected |

The focused composition suite verifies the exact descriptor, refusal of mock and
unsafe mutations, runtime-before-API readiness, API-before-runtime cleanup, and
the explicit execution gate. Its lightweight end-to-end test binds an ephemeral
loopback API port and reaches the real adapter type using generated runtime
responses through an injected transport. It starts no container, opens no runtime
socket, and reads no model byte; its result cannot certify real serving.

## Real execution deliberately absent

No `start`, `status`, or `cleanup` command carrying `--confirm-real-runtime` was
run. No image was pulled, no model was downloaded or read, no container was
created, and no inference was sent to the selected runtime. Consequently this
record contains no new startup duration, completion, resource, performance, or
real cleanup result.

## Public-information review

The reviewed change is confined to the public repository. It contains public
project identifiers and immutable public model/runtime pins already present on
`main`; it contains no planning path or identifier, credential, prompt or
completion from a user, personal filesystem path, model artifact, host inventory,
private URL, or runtime response body. Generated logs remain under an ignored,
workspace-scoped path and record structured operational fields only.

## Independent second-eye review

An independent reviewer examined first commit `3371eda` against the complete PR
brief and found two cleanup-boundary defects before push. First, resolved-path
comparison could follow a pre-existing linked log-path component outside the
workspace. Second, an API teardown or log-write exception could skip the runtime
cleanup attempt. The follow-up fixes refuse symlink and junction components before
each read or write, independently attempt every teardown action, and add regressions
for linked parent and leaf paths plus a teardown-time log failure. The reviewer also
reported no private-information leakage and confirmed that no real execution
occurred.

## Limitations

The tooling HTTP carrier is deliberately local and narrow. It has no TLS, caller
authentication, proxy support, multi-process supervision, or remote exposure and
is not production deployment packaging. This change adds no Kubernetes resource
and does not connect the WorkloadContract reconciliation path to serving.
