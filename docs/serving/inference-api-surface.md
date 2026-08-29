# The V1 inference API surface

Status: **decided, and served in part.** Every endpoint below is registered and
answered by [the InferOps API](inference-api.md), which `V1-S1-005-PR1` built.
Three parts of the shape are deliberately unfinished, and each is named where it
applies: the canonical error body is served in a subset, `/metrics` publishes no
series, and two accepted request members are validated and not forwarded.

The decision behind it is
[ADR 0010](../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md),
written while nothing served any of it and left dated rather than rewritten. Its
checkable form is
[`inference-api-surface.v1alpha1.json`](inference-api-surface.v1alpha1.json);
[`tests/serving/`](../../tests/serving/) compares the record with the documents
around it and with the code that now implements it, and
[`tests/api/`](../../tests/api/) exercises that code against the mock adapter.

> [!IMPORTANT]
> **This is still not a published interface.** No OpenAPI document exists, nothing
> has been added to [`contracts/`](../../contracts/), and whether this surface is
> ever published as a contract artifact is `D9`, which stays undecided. Serving a
> shape and publishing it as something a client may bind to are different acts, and
> only the first has happened.
>
> **Nothing here has answered a network request.** The API implements the ASGI
> calling convention and this repository ships no server, so every result behind
> this document was produced by driving the application through its own interface.

## The compatibility target

The API is shaped like the **OpenAI HTTP API**, at the `/v1` path prefix, restricted
to a **frozen subset**: the field lists in this document and nowhere else.

Two version identifiers travel together, and reading either one as the other is the
mistake this section exists to prevent.

| Identifier | Value | What it means |
|---|---|---|
| Path prefix | `/v1` | Belongs to the borrowed shape. **Not an InferOps version claim** |
| `contractVersion` | `inferops.io/v1alpha1` | InferOps's own version for this surface. Travels in the extension namespace and moves independently of the path |

The shape was read from the response bodies the selected runtime actually returned in
[the feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) on
2026-08-24. No vendor documentation was read for any of it. Compatibility here is a shape borrowed on a
date and written down; it is not a commitment to track what the upstream surface does
next.

## Endpoints

| Method | Path | Origin | Serving-contract role |
|---|---|---|---|
| `POST` | `/v1/chat/completions` | compatibility target | inference |
| `GET` | `/v1/models` | compatibility target | model and runtime metadata |
| `GET` | `/health/live` | InferOps-native | liveness |
| `GET` | `/health/ready` | InferOps-native | readiness |
| `GET` | `/metrics` | InferOps-native | metrics |

The health paths are InferOps-native because the compatibility target defines no
health surface at all.

`/health/live` deliberately has no runtime counterpart. InferOps being alive and
InferOps being able to serve are different questions, and only readiness is allowed to
depend on the runtime — the same reasoning ADR 0002's proven probe mapping applies one
layer down, where liveness watches a TCP socket rather than the endpoint that returns
503 during a model load.

**Graceful shutdown is met by an equivalent, not an endpoint**: `SIGTERM` handling
that flips readiness false, drains what is in flight, and exits. An HTTP endpoint that
stops a process would be an unauthenticated remote-stop control on a surface with no
authentication in V1.

### What is not served

| Not served | Why |
|---|---|
| `/v1/completions` | The legacy text-completion shape. It doubles the request surface for one runtime and one chat model, and the chat shape answers the same question |
| `/v1/embeddings` | The pinned model is a chat model. Embeddings need a second model and a second Deployment, because the runtime serves one model per process. Neither is decided |
| `/v1/responses` | A newer upstream shape, still moving. Adopting it is what the frozen subset refuses |
| `/v1/models/{id}` | Answers the same question as the list, for a deployment serving exactly one model |
| `/v1/audio`, `/v1/images`, `/v1/moderations`, `/v1/files`, `/v1/batches`, `/v1/fine_tuning`, `/v1/assistants`, `/v1/vector_stores`, and everything under them | No model, no component, and no storage exists for any of them |
| The runtime's own paths — `/props`, `/completion`, `/slots`, `/infill`, `/tokenize`, `/detokenize`, `/embedding` | **The runtime's surface is not proxied.** A runtime-specific path in front of callers defeats the runtime-neutral adapter. Only `/props` was observed in the trial; the rest were not enumerated there and nothing relies on them |

## `POST /v1/chat/completions`

### Request

| Field | Type | Required | V1 behaviour | Observed in the trial |
|---|---|---|---|---|
| `model` | string | yes | Compared against the served model identifier. A mismatch is refused with `contract-invalid`; it does not select a model | yes |
| `messages` | array of `{role, content}` | yes | `role` is one of `system`, `user`, `assistant`. `content` is a string; the array-of-parts form is outside the subset | yes |
| `max_tokens` | integer | no | Upper bound on generated tokens. Above the deployment's ceiling it is refused, not silently clamped | yes |
| `temperature` | number | no | Passed to the adapter. `0` is the value the determinism observation was made at | yes |
| `stream` | boolean | no | Accepted only as `false`. `true` is refused with `capability-unavailable` | no |

**Anything else is refused** with `contract-invalid`, and the refusal names the
member.

That is the strict policy, chosen because silently ignoring a parameter that changes
the result is worse than refusing it: a caller who sends `n` and receives one choice,
or sends `stop` and receives text past the stop sequence, has been handed a wrong
answer rather than an error. The cost is real and is not hidden — clients sending
upstream defaults such as `top_p`, `n`, `presence_penalty`, or `stop` are refused
until they stop sending them.

### Response

| Field | V1 behaviour | Observed in the trial |
|---|---|---|
| `id` | The completion identifier, generated by InferOps rather than passed through | yes |
| `object` | The literal `chat.completion` | yes |
| `created` | Unix seconds at which InferOps produced the response | yes |
| `model` | The served model identifier | yes |
| `choices` | Exactly one element: `index`, `message` with `role` and `content`, and `finish_reason`. Never more than one, because `n` is outside the subset | yes |
| `usage` | `prompt_tokens`, `completion_tokens`, `total_tokens` where the adapter supplied them; `null` where it did not. **Never estimated and never zero-filled** | yes |
| `x_inferops` | `requestId`, `correlationId`, `contractVersion`, `adapterKind`, `modelRef` | no |

### Three fields the runtime returns and InferOps does not forward

| Field | Seen as | Why it stops here |
|---|---|---|
| `system_fingerprint` | `b10588-70adb1b4c` | A runtime build string on every response. Runtime identity belongs in the runtime descriptor and the build-info metric, published once |
| `timings` | `prompt_ms`, `predicted_ms`, `predicted_per_second` | A per-request timing figure on a public response is a throughput claim by another route, and this project has refused to publish the decode rate it measured |
| `prompt_tokens_details` | `cached_tokens` | A prompt-cache statistic of the runtime's, outside the subset for V1 |

## `GET /v1/models`

| Field | V1 behaviour | Observed in the trial |
|---|---|---|
| `object` | The literal `list` | no |
| `data` | Exactly one element: `id`, `object`, `created`, `owned_by` | no |
| `x_inferops` | The runtime descriptor the model-serving contract requires, plus the declared capability set below | no |

**Nothing in that table was observed, and the reason is worth stating.** The trial did
call this endpoint, and the record shows what came back — but what it shows is the
runtime's own model metadata, printed as text, not a list envelope. So the endpoint is
evidenced and its response shape is not. Every field above is a specification.

## The extension namespace

Two namespaces, named together because confusing them is the likely mistake.

| Namespace | Form | Carries |
|---|---|---|
| `x_inferops` | One object-valued member of a JSON body | What the compatibility target has no place for |
| `X-InferOps-` | An HTTP header prefix | Transport metadata: request id, correlation id, workload id, workload version, environment |

`snake_case` matches the surrounding body, and the `x_` prefix marks the member as an
extension without colliding with anything observed in the runtime's own responses.

**V1 defines no request-body extension member.** Correlation and workload metadata
travel in headers, and security-sensitive values must be validated or injected by a
trusted component rather than trusted because a client sent them.

`adapterKind` is on every response for a reason that is not cosmetic: which adapter
served a response decides what that response may be used to claim, and
[the mock and real boundary](mock-and-real-boundary.md) makes that a rule. Leaving it
to deployment configuration hides the boundary at the one place a reader looks.

## Declared capabilities

Declared, not assumed. Each one is published at `/v1/models` under
`x_inferops.capabilities` and each says what supports it.

| Capability | V1 value | What supports it |
|---|---|---|
| `streaming` | `false` | V1 has no streaming path, and the telemetry catalog already defers time-to-first-token for exactly that reason. **Whether the runtime can stream was never exercised**, and nothing here asserts it either way |
| `tokenUsage` | `true` | The trial's recorded `usage` object, and the blocking threshold ADR 0002 set before the trial ran |
| `deterministicSampling` | `true` | Three runs at temperature 0 returned byte-identical content. One model, one host, one day — observed, not guaranteed |
| `multiModel` | `false` | The runtime serves one model per process, and the trial's `/v1/models` reported exactly one |

## Errors

Every refusal uses the canonical error body: a `code`, a safe `message`, a
`requestId`, a `correlationId`, a `retryable` flag, and optional `retryAfterMs` and
`details`. A message never carries a secret, a stack trace, a prompt, or a policy
detail, and a refusal names the offending member rather than its value.

**One row below was observed. Eight are specifications**, because the failure lane
that would exercise them is deselected by default and has no code.

| Condition | Observed | Code | Retryable |
|---|---|---|---|
| The runtime reports not-ready while the model loads | **yes** — a startup probe recorded failing with statuscode 503 | `model-not-ready` | yes |
| The runtime's Service or pod refuses a connection | no | `capability-unavailable` | yes |
| The runtime does not answer within the adapter's deadline | no | `upstream-timeout` | yes |
| The caller's own deadline expires first | no | `request-timeout` | yes |
| A member outside the subset, a bad role, non-string content, a model that is not the served model, or `max_tokens` above the ceiling | no | `contract-invalid` | no |
| `stream: true` | no | `capability-unavailable` | **no** — overridden |
| A contract or API version this deployment does not support | no | `version-unsupported` | no |
| The runtime answers non-2xx, and not the 503 that means loading | no | `internal-error` | yes |
| The runtime answers 2xx with a body the adapter cannot read | no | `internal-error` | yes |

The `stream: true` override is deliberate. `capability-unavailable` defaults to
retryable, which is right for a capability that is temporarily gone and wrong for one
that was never built.

### Codes this API never emits in V1

Listed because a code with no condition behind it is a claim that something checks
for it.

| Code | Why not |
|---|---|
| `authentication-required` | There is no authentication in V1 |
| `authorization-denied` | There is no identity to authorize |
| `policy-denied` | No policy engine is selected |
| `rate-limited` | V1 has no rate limiter |
| `budget-exceeded` | No budget is enforced anywhere, and every cost figure this project can produce has confidence `none` |
| `evaluation-failed` | A release-gate outcome, not an inference-time condition |

## The request counter InferOps owns

The selected runtime exposes **no cumulative request counter**. That is the one
blocking threshold ADR 0002 failed, and it was accepted with the failure argued rather
than absorbed. The two series carrying `requests` in their names —
`llamacpp:requests_processing` and `llamacpp:requests_deferred` — are gauges of
instantaneous state, and a gauge reading zero between requests cannot be summed,
rated, or alerted on the way a counter can.

InferOps receives the requests, so InferOps counts them:

| Metric | Role |
|---|---|
| `inferops_inference_requests_total` | The cumulative request count the runtime does not have |
| `inferops_inference_errors_total` | Labelled by `error-code`, which is what makes the mapping above observable rather than merely written down |

Both already exist in [the telemetry catalog](../telemetry/telemetry-catalog.md). This
surface adds no metric; it binds those two to these endpoints and these codes. Neither
is emitted by anything today.

## What this decides about the adapter interface

`V1-S1-002` freezes the serving adapter interface one story before this API is
written, so the consequences are stated rather than left to be inferred.

| Consequence | Why |
|---|---|
| The API is shaped like the compatibility target **at its edge**; the adapter interface is runtime-neutral, and the translation lives in the API layer | An adapter taking a compatibility-target request type puts that shape inside the platform domain, which the dependency rule forbids |
| One synchronous, non-streaming generate call | Streaming is declared `false`, and an interface carrying a method nothing implements is an assumption dressed as a capability |
| Token usage returned as an **optional** value | A required field forces a mock to invent numbers, and token accounting is named as a property a mock cannot honestly reproduce |
| The adapter **declares** its capability set; the API publishes what the selected adapter declared | A capability that is a constant in the API is an assumption |
| Every response names the adapter kind that served it | It is the mock and real boundary made visible where a reader looks |

## What is not decided here

- The context length, KV budget, concurrency limit, and sampling defaults, all four of
  which ADR 0002 left open — and therefore the `max_tokens` ceiling that depends on
  the first.
- Authentication, authorization, rate limiting, and quota.
- Any asynchronous or event-carried inference shape. V1 serves one synchronous
  request at a time and decides nothing about any other form.
- How a caller outside the cluster reaches the API. The accepted local cluster ships
  no ingress controller and no load-balancer implementation.
- Whether this surface is ever published as a contract artifact, and by what
  mechanism.
