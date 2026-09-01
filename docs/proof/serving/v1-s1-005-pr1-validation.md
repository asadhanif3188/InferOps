# V1-S1-005-PR1 — inference and lifecycle API, change validation

The record behind [the InferOps inference API](../../serving/inference-api.md).
It records what was run, on what, and what it may be used to claim — which is less
than a reader skimming a green test session would assume, because **this change
did not answer a network request.** The API implements the ASGI calling
convention, this repository ships no server, and every result below was produced
by driving the application through its own interface. The
[limitations](#limitations) and [acceptance criteria](#acceptance-criteria)
sections are the parts that say so.

> [!NOTE]
> **Post-record resolution (2026-09-01):** the gap this historical validation
> record reports for `max_tokens` and `temperature` is closed by ADR 0010's
> amendment. Both fields are now outside the accepted request subset and are
> refused rather than silently ignored. The original run and its claims below are
> preserved as they were recorded.

## Classification

| | |
|---|---|
| Evidence class | `local-static` for every check here |
| Ceiling | `C0` |
| What ran | The committed test suites, the linter, the formatter, and the type checker, from a checkout |
| What did not run | Any HTTP server, socket, network request, real model, runtime image, container engine, cluster, paid service, or scanner |
| Claims certified by this record | none |

`local-static` is the weakest label these checks support and it is the correct
one. The API added here is real, and every check drove it either against the
committed **mock** adapter — which replays a fixture and loads no model — or
against a controlled double supplied by the test file. That establishes what the
application decides and establishes **nothing** about HTTP, about a runtime, about
a model, about latency, or about token accounting.

**The same imprecision earlier records noted applies again.** The new suites live
under `tests/api/`, whose layer carries the evidence class `mock` and a `C1`
ceiling in [the committed strategy](../../testing/test-strategy.v1alpha1.json).
These checks produce `local-static` results, which is weaker, and the vocabulary
rule is to pick the weakest label the record supports.

**No claim moves to `certified` in this change**, and the only layer whose status
changes is `mock-integration`, which moves from `planned` to `implemented` because
it now has a suite and something for that suite to run against. The claims this
work sits under — `the-platform-serves-a-workload-the-contract-describes`,
`a-model-that-is-not-ready-is-a-canonical-error`,
`an-unreachable-runtime-is-a-canonical-error`,
`no-prompt-response-or-secret-reaches-a-log-or-a-metric`, and
`deployment-values-derive-only-from-a-validated-document` — all remain `planned`.
Four of the five need a capable host and a real model; the fifth needs the
telemetry work that does not exist.

## Provenance

| Input | Value |
|---|---|
| Repository revision at branch point | `eccc5fe` |
| Branch | `feat/v1-s1-005-inference-lifecycle-api` |
| Distribution code added | `src/inferops/api/{__init__,surface,identifiers,validation,responses,errors,metrics,lifecycle,application}.py` |
| Distribution code changed | none |
| Tests added | `tests/api/{conftest,test_api_inference,test_api_request_validation,test_api_health_models_and_metrics,test_api_lifecycle}.py`, `tests/serving/test_inference_api_implementation_agreement.py`, `tests/support/{asgi_client,api_composition}.py` |
| Tests changed | `tests/serving/test_inference_api_surface.py` |
| Accepted records updated to stay true | `docs/serving/inference-api-surface.{md,v1alpha1.json}`, `docs/testing/test-strategy.{md,v1alpha1.json}` |
| Accepted records **not** changed | `ADR 0010`, `ADR 0004`, `ADR 0002`, `ADR 0008`, the telemetry catalog, the workload contract, and everything under `contracts/` |
| Record the shapes were copied from | [the accepted surface data](../../serving/inference-api-surface.v1alpha1.json) |
| Model artifact | none. No weight file was downloaded, mounted, hashed, or read |
| Container image | none |
| Cluster | none |
| Network | none. No socket was opened, by the suites or by anything run for this record |
| New runtime dependency | none. `pyproject.toml` still declares `dependencies = []` |

## Environment

| | |
|---|---|
| Host | One Windows workstation, contributor-owned |
| Operating system | Windows 11, build 10.0.26200 |
| Python | 3.12.12 (CPython) |
| uv | 0.9.16 |
| pytest | 8.4.2 |
| ruff | 0.16.4 |
| mypy | 2.3.1 |

Every dependency version came from the committed [`uv.lock`](../../../uv.lock) by
way of `--locked`, which fails rather than re-resolving.

## Method

The commands, in the order they were run:

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m mypy
uv run --locked python -m pytest -q
uv run --locked python -m pytest tests/api -q
uv run --locked python -m pytest -m mockintegration -q
uv run --locked python -m pytest tests/serving -q
git diff --check main...HEAD
```

The whitespace and link checks in [CONTRIBUTING](../../../CONTRIBUTING.md) were run
over the changed Markdown as well.

## Results

| Command | Result |
|---|---|
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `164 files already formatted` |
| `python -m mypy` | `Success: no issues found in 81 source files` |
| `python -m pytest -q` | `3695 passed, 25 skipped, 7 deselected` |
| `python -m pytest tests/api -q` | `103 passed` |
| `python -m pytest -m mockintegration -q` | `103 passed, 3624 deselected` |
| `python -m pytest tests/serving -q` | `209 passed` |
| `git diff --check main...HEAD` | no output |
| Markdown trailing whitespace and hard tabs | no matches |
| Relative Markdown links in changed files | all resolve |

The seven deselected tests are the `realruntime` suite, which the default marker
expression removes because it needs the pinned model on a capable host. That lane
was **not** entered by this change.

## What the added checks establish

### The five routes are the five the record decided

`tests/serving/test_inference_api_implementation_agreement.py` reads
[the accepted surface data](../../serving/inference-api-surface.v1alpha1.json) and
compares it with the route table in `src/inferops/api/surface.py` in both
directions: every in-scope endpoint is registered, every registered route is an
in-scope endpoint, and no path the record puts out of scope — including every
runtime-native path the record refuses to proxy — is registered. The same suite
compares the request subset, the required members, the accepted roles, the
extension namespace, the completion extension members, the contract version, the
path prefix, and the dropped runtime fields.

### A completion is produced end to end, against a mock that says it is one

`tests/api/test_api_inference.py` drives a request through routing, validation,
the adapter, and the response builder, and asserts the borrowed shape: one choice,
`chat.completion`, the served model, an InferOps-generated identifier, and the
extension member carrying exactly the five values the record lists. `usage` is
`null` because the mock declares token counting unsupported — never zero-filled,
never estimated — and the same suite asserts that an adapter which does supply
counts has them published.

### `adapterKind` is checked, not just printed

A controlled double configured to return a `real`-labelled result from a
deployment composed as `mock` is refused with `internal-error` rather than served.
That is the one check that makes `adapterKind` worth publishing: a response whose
kind cannot be trusted is a response nobody can use to claim anything.

### Identifiers reach the adapter, and a malformed one does not

A supplied `X-InferOps-Request-ID` and `X-InferOps-Correlation-ID` reach the
`RequestContext` the adapter receives, the response headers, and the completion
body. A value carrying a carriage return and a newline — a response-splitting
attempt rather than an identifier — is replaced by a generated one and reaches
neither.

### Every refusal names a member and no refusal repeats a value

`tests/api/test_api_request_validation.py` exercises the strict policy over the
upstream defaults a client library sends by habit (`top_p`, `n`,
`presence_penalty`, `stop`, `frequency_penalty`, `tools`), over every malformed
member inside the subset, and over the body itself. Three cases carry a canary
value in the position a naive implementation would echo — a rejected model, a
rejected role, a rejected temperature — and assert the canary is absent from the
response. Every refusal carries a request identifier and a correlation identifier.

### Readiness follows the selected backend, and liveness does not

Readiness is false before startup, true once the adapter reports itself able,
false again when the adapter says it is not, and false when the adapter raises
while being asked. Liveness answers `200` through all of it, including while the
API is draining, which is why the accepted record gives it no runtime counterpart.
Neither health body carries a scheme, a credential word, or a filesystem path.

### The shutdown order holds

Readiness goes false **before** anything drains; a new request during the drain is
refused with `capability-unavailable`; the drain waits for in-flight work and
reports whether it finished inside its budget; and the adapter is released only
after the in-flight request completed. That last one is asserted by recording the
adapter's shutdown count from inside the in-flight call.

### The metrics endpoint publishes nothing, and says so

Every line of the exposition is a comment, there is no `HELP` line, no `TYPE` line
and no sample, and the body names the two metrics the accepted surface binds to
this endpoint and the story that owns emitting them.

## Limitations

**Nothing here crossed a socket.** This is the limitation that governs every other
one. The application implements the ASGI calling convention; this repository ships
no ASGI server and none was installed or run. A result from these suites
establishes routing, reading, validation, translation, status codes, headers, and
lifecycle ordering — and establishes nothing about HTTP request parsing, header
folding, chunked transfer, connection reuse, timeouts, proxies, or a client
disconnecting mid-request. **No result here may be cited as evidence that this API
answers a network request.**

**No real adapter was composed.** Everything ran against the committed mock or a
controlled double. The `llama-server` adapter exists and was not put behind this
API in any check, so nothing here says the two compose.

**The canonical error body is a subset.** `retryable`, `retryAfterMs`, and
`details` are not served, and the condition-to-status mapping is this change's
provisional one — the accepted record maps conditions to codes and says nothing
about statuses. `V1-S1-005-PR2` standardises it.

**`/metrics` publishes no series**, so `ADR 0002` `T7`'s compensating obligation —
that InferOps counts the requests the runtime cannot — is **not discharged by this
change**. It is bound to an endpoint that now exists, and the telemetry work
owns emitting it.

**Two accepted request members are validated and not forwarded.** `max_tokens` and
`temperature` are in the frozen subset and the serving adapter interface
`V1-S1-002` froze has no parameter for either. A caller sending `temperature: 0.9`
receives the runtime's default and no indication that they did. This is a conflict
between two accepted records, it is recorded rather than resolved here, and it is
listed under [deferred work](#deferred-work).

**A conversation is refused.** More than one message, or a single message whose
role is not `user`, is refused with `contract-invalid` — a narrower surface than
the accepted record publishes, taken because flattening a conversation into the
adapter's single prompt would apply a prompt format no chat template agreed to,
silently. It is a refusal rather than an invention, and it is the second half of
the same interface gap.

**`deterministicSampling` is published as `null`.** The frozen adapter interface
declares nothing about it, and `ADR 0010`'s `true` rests on a Sprint 0 observation
of a runtime rather than on a declaration the selected adapter makes.

**Neither `authentication` nor `authorization` exists**, and this change adds
none and claims none. `ADR 0008` `D4` accepts that for V1. The surface is
reachable by anything that can reach it, and since nothing serves it over a
socket, that is currently nothing.

**No security scanner was run.** `gitleaks` is configured in this repository and
was not executed for this record, so the security-scan layer stays `planned` and
this record claims nothing from it.

**The API is not deployed.** No Dockerfile, no manifest, no Service, and no
Deployment exists for it. It cannot be started by anything in this repository.

## Acceptance criteria

Applied to this PR's boundary. Criteria the next PR owns are listed as deferred
rather than claimed.

| Criterion | Status | Where |
|---|---|---|
| Inference, live, ready, and metrics endpoints exist | **met**, with `/metrics` publishing no series | `tests/api/`, `tests/serving/test_inference_api_implementation_agreement.py` |
| Request/correlation IDs propagate to the adapter | **met** | `tests/api/test_api_inference.py` |
| Readiness reflects selected backend state | **met** | `tests/api/test_api_health_models_and_metrics.py` |
| Graceful shutdown stops accepting work before termination | **met** | `tests/api/test_api_lifecycle.py` |
| API returns canonical, non-sensitive errors | **partly met.** Non-sensitive is asserted; the canonical body is a subset | `tests/api/test_api_request_validation.py` |
| Mock and real selection is explicit configuration | **deferred to PR2.** The adapter is handed to the API in code, and there is no default and no configuration reader | — |

Parent story `V1-S1-005` is therefore **not complete**. Its evidence list also
requires an OpenAPI or API snapshot and a real end-to-end test output; neither
exists, and `D9` — whether this surface is published as a contract artifact at all
— is still undecided.

## Deferred work

| Item | Owner | Why it is not here |
|---|---|---|
| The canonical error body: `retryable`, `retryAfterMs`, `details`, and the condition-to-status mapping | `V1-S1-005-PR2` | Named in the PR boundary |
| Configuration-driven mock/real adapter selection | `V1-S1-005-PR2` | Named in the PR boundary |
| End-to-end tests over the real adapter | `V1-S1-005-PR2` | Named in the PR boundary |
| A status for a route outside the surface and for a method mismatch | `V1-S1-005-PR2` | The accepted record maps request conditions and does not cover routing; this change answers `404` and `405` with `contract-invalid` and records that as provisional |
| A status for `version-unsupported`, and for `contract-invalid` raised from below the edge | `V1-S1-005-PR2` | `STATUS_FOR_CANONICAL_CODE` maps the six codes an adapter can raise today. Neither of these is reachable through any path this change adds — nothing here raises them from below the edge — and an unmapped code falls back to `500`, which is the answer that invents no meaning for it |
| Emitting `inferops_inference_requests_total` and `inferops_inference_errors_total`, and moving the catalog off `nothing-emits` | the telemetry work | Instrumenting this API is that work, and it depends on this API existing |
| A per-request bound and a sampling parameter on the serving adapter interface | needs a superseding decision on `V1-S1-002`'s frozen interface | `max_tokens` and `temperature` are accepted by the surface and cannot be forwarded |
| A conversation-carrying parameter on the same interface | as above | A multi-message request is refused rather than flattened |
| A capability declaration for deterministic sampling | as above | Published as `null` rather than assumed |
| An ASGI server, a container image, and a manifest for this API | not yet scheduled | Nothing here can be started, and no lane exists that would run it |
| A `failure` lane exercising the eight specified error conditions | `failure-and-resilience` layer, still `planned` | Needs a real runtime |
| Whether the `adapter` and `mock-integration` layers should distinguish `local-static` from `mock` evidence | open | Carried forward from `V1-S1-004-PR2` |

## Authorisation

No authorisation-gated action was taken. No real model was downloaded, no runtime
image was pulled, no cluster was created, no paid service was used, no destructive
operation was run, and no socket was opened. The `realruntime` lane was not
entered.

## Related records

- [The InferOps inference API](../../serving/inference-api.md) — what was built.
- [The V1 inference API surface](../../serving/inference-api-surface.md) and
  [ADR 0010](../../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md)
  — the shape it implements.
- [The mock and real boundary](../../serving/mock-and-real-boundary.md) — why
  `adapterKind` is on every response and why the API has no default adapter.
- [V1-S1-004-PR2 validation](v1-s1-004-pr2-validation.md) — the adapter this API
  would compose for a real deployment, and the record that says it has not run.
- [V1-S1-003-PR1 validation](v1-s1-003-pr1-validation.md) — the mock adapter these
  suites run against.
- [The test and CI strategy](../../testing/test-strategy.md) — what the
  `mock-integration` layer may and may not certify.
