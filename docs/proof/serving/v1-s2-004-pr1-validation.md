# V1-S2-004-PR1 change validation

| Field | Value |
|---|---|
| Date | 2026-09-03 |
| Scope | C2 real-runtime smoke certification workflow for the composed serving path |
| Source branch | `test/v1-s2-004-real-runtime-certification` |
| Evidence produced here | `local-static` and `synthetic` only |
| Real-runtime execution | Not authorized and not run |

## Implemented boundary

The committed
[`c2-smoke.v1.json`](../../../deploy/serving/certification/c2-smoke.v1.json) and
[`tools.runtime_certification`](../../../tools/runtime_certification/) command
add the certification step above the existing local composition. The composition
still owns starting the pinned runtime before the loopback InferOps API, waiting
for both readiness boundaries inside the profile's budgets, and tearing down in
reverse order.

The workflow refuses before anything is created: the container engine's own CPU
and memory figures and the free space on the model-cache volume are read first,
and only a host that passes them pays for the hash verification of the cached
model. It then observes identity through `GET /v1/models`, sends one fixed,
neutral, public request to `POST /v1/chat/completions`, and refuses an answer
whose adapter kind is not `real`, whose runtime or model identity carries `mock`,
whose model revision is not the pinned one, whose content is empty, or whose
token counts are absent or inconsistent. The mock adapter's unsupported
token-counting declaration is refused explicitly, so mock capability metadata
cannot reach a `C2` record.

A certified run writes `local-real-cpu` evidence labelled `local real runtime`.
A refusal or failure exits non-zero and writes a diagnostics record naming the
stage — `load`, `prerequisites`, `compose`, `identity`, `inference`, or
`cleanup`. Neither record retains the prompt, the completion, a runtime response
body, a hostname, a username, or a personal filesystem path; both live under the
ignored `.cache/inferops/certification/` path.

## Validation results

| Command | Result | Evidence boundary |
|---|---|---|
| `uv run --locked python -m tools.runtime_certification check` | Passed; C2 identity, `local-real-cpu` class, `real-runtime` lane, prerequisites, budgets, request paths, assertions, and evidence location printed | `local-static`; contacted no engine, runtime, or model |
| `uv run --locked ruff check .` | Passed; all checks passed | Repository-static |
| `uv run --locked ruff format --check .` | Passed; 243 files already formatted | Repository-static |
| `uv run --locked python -m mypy` | Passed; 138 source files checked | Repository-static |
| `uv run --locked python -m pytest tests/serving/test_runtime_certification.py -q` | Passed; 50 tests | Controlled synthetic certification path |
| `uv run --locked python -m pytest -q` | Passed; 5,305 passed, 25 skipped, 14 deselected | Default lane; real-runtime tests remained deselected |
| `git diff --check main...HEAD` | No trailing-whitespace or hard-tab match | Repository-static |
| Markdown trailing-whitespace and hard-tab sweep | No match | Repository-static |
| Relative Markdown link sweep | No broken target | Repository-static |
| `gitleaks detect --config .gitleaks.toml --no-banner` | **Not run**; `gitleaks` is not installed on this host | Reported, not claimed |

The committed test strategy now names the certification command as a third way
into the `real-runtime` lane, and records in the same sentence that it has not
been run against a runtime.

The focused suite verifies the committed descriptor against the composition,
package, profile, and model pins; refuses twenty-one weakened or unsafe descriptor
mutations, including a lowered certification level, a relabelled evidence class, a
waived assertion, a reduced prerequisite, and an evidence path outside the ignored
directory; proves that the hardware refusal names every unmet check and runs
before the artifact hash; proves the mock-identity and mock-capability
prohibitions at both the identity and the completion boundary; proves that a
mid-run refusal still stops the attached server; and proves that the record it
writes contains neither the prompt nor the completion.

## Real execution deliberately absent

No `certify --confirm-real-runtime` invocation was made. No image was pulled or
inspected, no model was downloaded or hashed, no container was created, no
runtime socket was opened, and no inference reached a real model. Consequently
this record contains no readiness duration, completion, token count, resource
figure, or real cleanup result, and this change makes no new `C2` claim. The
`local-real-cpu` label the workflow writes is truthful only for an authorized run
on a capable host; the seam-driven suite exercises the label's mechanics and can
certify nothing.

## Public-information review

The reviewed change is confined to the public repository. It contains public
project identifiers and the immutable public model and runtime pins already
present on `main`; it contains no planning path or identifier, credential, prompt
or completion from a user, personal filesystem path, model artifact, host
inventory, private URL, or runtime response body. The host facts the workflow may
publish are limited to operating system, release, machine architecture, Python
version, engine CPU count, engine memory, and free disk on the model-cache
volume, and a test asserts that set exactly. Generated records remain under an
ignored, workspace-scoped path.

## Independent second-eye review

An independent reviewer examined the first commit against the complete PR brief
before push. The findings and their disposition are recorded in the pull request
and in the follow-up commit on this branch.

## Limitations

This change adds a workflow, not a result. It does not run a real model, does not
raise any claim's certification level, adds no Kubernetes resource, measures no
latency or throughput, and makes no production statement. A single fixed request
is not a benchmark and the workflow refuses to be used as one: it sends exactly
one request, records no rate, and publishes no figure a capacity claim could rest
on. Failure and recovery behaviour against a real runtime remains `C3` and out of
V1 scope.
