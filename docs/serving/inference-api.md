# The InferOps inference API

Status: **implemented, and it has answered no network request.**
[`src/inferops/api/`](../../src/inferops/api/) registers the five endpoints
[the accepted surface](inference-api-surface.md) decided and answers each of them
through the serving adapter **configuration selected**. What it is not is a
running service: the application implements the ASGI calling convention and
**this repository ships no ASGI server**, so every result behind this document was
produced by driving the application through its own interface. No socket has been
bound and no byte has crossed a network.

This document is what the API does. [ADR 0010](../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md)
is why its shape is what it is, and this document does not restate the argument.

## What is served

| Route | Served | Deliberate limit |
|---|---|---|
| `POST /v1/chat/completions` | Validation, translation to the adapter, the completion body, and the canonical error body in full | Caller generation controls the adapter cannot carry are refused, not ignored |
| `GET /v1/models` | The list envelope, the runtime descriptor, and the declared capability set | `deterministicSampling` is published as `null` — see [declared capabilities](#declared-capabilities) |
| `GET /health/live` | Whether this process is alive | — |
| `GET /health/ready` | This API accepting work **and** the selected adapter reporting itself able | — |
| `GET /metrics` | The route, in the Prometheus exposition content type, and the eight metrics the telemetry catalog assigns to this API | Five active metrics are not emitted — four belong to the adapter or the validator, and one has no source this distribution may read. See [what the API emits](../telemetry/api-instrumentation.md) |

## How it is composed

The API is the composition point, and it has no default adapter. Which adapter is
live comes from configuration, and the rule
[the mock and real boundary](mock-and-real-boundary.md) states is what shapes the
reader: rule 5 forbids a mock that could become the live adapter by omission, and
rule 4 says substituting a mock result for a missing real one is a defect and not
a fallback. So there is nothing to omit and nothing to fall back to.

```python
import os

from inferops.api import build

api = build(os.environ)
```

`build` reads a mapping rather than the process environment, so a selection made
in a test and one made at startup take the same path; passing `os.environ` is how
ambient state legally enters. Constructing performs no I/O — the adapter is
initialized on lifespan startup and released after the drain on lifespan
shutdown.

### The variables

| Variable | Required | What it does |
|---|---|---|
| `INFEROPS_SERVING_ADAPTER` | yes | `mock` or `real`. **There is no default.** Unset, empty, or anything else selects nothing |
| `INFEROPS_MODEL_IDENTIFIER` | yes | The one model this deployment serves. A `mock` deployment's must be mock-labelled and a `real` deployment's must not be |
| `INFEROPS_REQUEST_TIMEOUT_MS` | yes | How long one inference request may take. Required because ADR 0002 decides no deadline, and a number invented here would be read back as a recommendation nobody made |
| `INFEROPS_MAX_OUTPUT_TOKENS` | no | Deployment-wide maximum output tokens passed to the adapter. It is an operator setting, not a caller request field; absent leaves the adapter without an InferOps-configured limit |
| `INFEROPS_DRAIN_TIMEOUT_MS` | no | The budget a graceful shutdown gives in-flight work. Defaults to 15000, which is itself a default rather than a decision |

Every number above is a duration or a token count, so **zero and below are
refused** rather than accepted — and the two optional variables take their default
only when they are *absent*. A supplied value is never quietly replaced by a
different one, which is the failure an `or` between a parsed number and a default
produces: a supplied `0` reads as an unset variable, and an operator who typed a
number gets one they did not.

A `real` selection reads the six `INFEROPS_LLAMA_SERVER_*` variables
[the runtime configuration document](real-runtime-configuration.md) publishes as
well. A `mock` selection reads none of them, and there is **no variable for the
mock's failure injection or latency**: those are test inputs, and a variable that
made a deployment produce a canonical error on demand would be reachable in
whatever environment the deployment ran in.

### What a refusal here protects

| Configuration | What happens |
|---|---|
| `INFEROPS_SERVING_ADAPTER` unset | Refused. **It does not select the mock** |
| `INFEROPS_SERVING_ADAPTER=Mock`, `mocked`, empty | Refused. Near-misses are the ones somebody actually types |
| `real`, with a runtime variable missing or malformed | Refused. **Never answered with a mock** |
| `real`, with a mock-labelled model alias | Refused by the runtime settings, which is the mirror of the mock adapter refusing a real identity |
| A second variable naming the adapter kind | Ignored. The kind is derived from the selection, so a real adapter cannot be labelled `mock` |
| A number that is not one, or is zero or below | Refused, **naming the variable an operator set** rather than a constructor parameter nobody typed |

A refusal names the variable and states the constraint. **It never repeats the
value it refused** — an endpoint is exactly where a credential arrives, and an
error message is exactly where one gets published.

`adapterKind` is derived from the selection rather than configured beside it, and
it is **checked against every result the adapter produces**. A deployment composed
as `mock` whose adapter returns a `real`-labelled result is refused with
`internal-error` rather than served, because a response whose `adapterKind` cannot
be trusted is a response nobody can use to claim anything.

**A successful `real` selection is not evidence that a runtime exists.** Nothing
is contacted while composing. What a real deployment actually does is answered by
the `real-runtime` lane, which is manual and authorization-gated.

## Identifiers

Two headers are read, and both are validated rather than trusted:

| Header | Behaviour |
|---|---|
| `X-InferOps-Request-ID` | Accepted when it matches `[A-Za-z0-9][A-Za-z0-9._:-]{0,63}`; replaced with a generated UUID version 4 otherwise |
| `X-InferOps-Correlation-ID` | The same |

A malformed identifier is **replaced, not refused**. Refusing an inference request
because its observability metadata was ill-formed would turn a header nobody is
required to send into a way to fail. The replacement is what stops a
newline-carrying header value reaching a response header, which is a
response-splitting attempt rather than an identifier.

Both identifiers travel three places: the `RequestContext` the adapter receives,
the response headers of **every** response including a refusal, and the
`x_inferops` member of a completion body.

## Request validation

The accepted policy for a member outside the frozen subset is **refuse**, and the
refusal names the member and never its value. Clients that send upstream defaults
such as `top_p`, `n`, `presence_penalty`, or `stop` are refused until they stop
sending them; that cost is real and is the one the decision accepted openly.

| Condition | Code | Status |
|---|---|---|
| A member outside `model`, `messages`, `stream` | `contract-invalid` | 400 |
| A member outside `role`, `content` inside a message | `contract-invalid` | 400 |
| `model` that is not the served model | `contract-invalid` | 400 |
| `role` outside `system`, `user`, `assistant` | `contract-invalid` | 400 |
| `content` that is not a string | `contract-invalid` | 400 |
| More than one message, or one whose role is not `user` | `contract-invalid` | 400 |
| `stream: true` | `capability-unavailable` | 400 |
| A body that is not a JSON object | `contract-invalid` | 400 |
| A body above 1 MiB | `contract-invalid` | 413 |

### One message, not a conversation

A request carrying more than one message, or a single message whose role is not
`user`, is refused. The serving adapter interface `V1-S1-002` froze carries a
single `prompt` string, and flattening a conversation into it would apply a prompt
format no runtime chat template agreed to — silently. Refusing is the honest half
of the strict policy: a caller finds out, rather than receiving an answer built
from a prompt nobody designed.

**This is a reduction in what the accepted surface publishes**, and removing it
needs a conversation-carrying parameter on the adapter interface, which is a
superseding decision rather than a patch.

### Generation controls are refused rather than ignored

`max_tokens` and `temperature` are outside the accepted request subset. The
frozen adapter interface has no per-request parameter for either, so accepting
them would advertise controls the implementation cannot honour. ADR 0010's
2026-09-01 amendment formally narrows the subset: callers receive
`contract-invalid`, naming the unsupported member, under the same strict policy
as `top_p` or `stop`. The deployment-wide `INFEROPS_MAX_OUTPUT_TOKENS` operator
setting remains available and is passed to the adapter.

## Errors

Every refusal carries the canonical error body the accepted record decided:

```json
{
  "code": "contract-invalid",
  "message": "temperature: this member is outside the frozen request subset this API accepts",
  "requestId": "…",
  "correlationId": "…",
  "retryable": false,
  "details": {
    "conditionId": "request-outside-subset",
    "adapterKind": "mock",
    "member": "temperature"
  }
}
```

`retryAfterMs` is the one optional member, and it is present for exactly one
condition — see [below](#retryafterms-is-served-once).

### A condition is the unit, not a code

`retryable` and the HTTP status are decided by **where the failure happened**,
not by the code alone, and the accepted record's own mapping is why: it maps
`capability-unavailable` twice, once to a runtime that cannot be reached and once
to a caller asking for streaming. The first is retryable and a server state; the
second is not retryable and a client error. A table keyed by the code would have
to pick one and be wrong for the other.

So each refusal site names a **condition**, and the code, the flag, the status,
and the message travel together from there. The condition identifier is published
in `details.conditionId`, so a caller holding one can find the row that decided
their refusal.

**Nine conditions are copied from the accepted record. Seven are this API's own**,
because the record maps request and runtime conditions and covers neither routing,
nor a body above this deployment's bound, nor a deployment that has stopped
accepting work, nor an adapter whose result contradicts the kind the deployment
was composed with — none of which existed when it was written. **No row of the
accepted record was edited**; the added rows are marked as added in
[`errors.py`](../../src/inferops/api/errors.py) and the agreement suite fails if a
copied row drifts from the record.

| Condition | Code | Retryable | Status | From |
|---|---|---|---|---|
| `model-loading` | `model-not-ready` | yes | 503 | the record |
| `runtime-unreachable` | `capability-unavailable` | yes | 503 | the record |
| `runtime-timeout` | `upstream-timeout` | yes | 504 | the record |
| `caller-deadline` | `request-timeout` | yes | 504 | the record |
| `request-outside-subset` | `contract-invalid` | no | 400 | the record |
| `streaming-requested` | `capability-unavailable` | **no**, overridden | 400 | the record |
| `unsupported-contract-version` | `version-unsupported` | no | 400 | the record |
| `runtime-error-response` | `internal-error` | yes | 500 | the record |
| `runtime-unparseable-response` | `internal-error` | yes | 500 | the record |
| `path-not-served` | `contract-invalid` | no | 404 | this API |
| `method-not-served` | `contract-invalid` | no | 405 | this API |
| `request-too-large` | `contract-invalid` | no | 413 | this API |
| `deployment-draining` | `capability-unavailable` | yes | 503 | this API |
| `adapter-kind-disagreement` | `internal-error` | **no**, overridden | 500 | this API |
| `adapter-rate-limited` | `rate-limited` | yes | 429 | this API |
| `unexpected-failure` | `internal-error` | yes | 500 | this API |

**Two `retryable` overrides, both argued.** `streaming-requested` is the accepted
record's own: retrying does not make a capability appear. `adapter-kind-disagreement`
is this change's: a deployment whose adapter contradicts the kind it was composed
with is misconfigured, and a misconfiguration does not resolve itself between one
request and the next.

**`version-unsupported` is reachable, and only from a path.** A request to
`/v2/chat/completions` names an API version this deployment does not serve, which
is a different refusal from `/healthz` — a path nobody publishes, which is
`path-not-served`. The path is the only place a caller can name a version: this
surface reads no version header, and the accepted record defines no request-body
extension member.

**`rate-limited` is mapped and never originated.** InferOps enforces no rate
limit, and the accepted record's reason for listing the code among those V1 does
not emit stays true. The mapping exists because the serving adapter contract
publishes `RateLimitedError` as a code an adapter may raise, and reporting a
backend's own limit as an internal error would be worse than reporting it as what
it is. The selected real adapter raises it nowhere — it maps a runtime's 429 to
`internal-error` by its own accepted record.

### `retryAfterMs` is served once

A deployment that has begun draining knows how long its own drain budget is, so
`deployment-draining` publishes it. **Nothing else here has a decided delay** —
ADR 0002 decides no concurrency limit, no deployment sets a termination grace
period, and no measurement exists to derive a backoff from. A number invented for
the other conditions would be a recommendation nobody made, arriving in the one
field a client library reads automatically, so the member is absent instead.

### What a message may not carry

A message names a member and states a constraint in this API's own vocabulary. It
never carries a value read out of the request, a runtime's own words, a stack
trace, or a path.

**A canonical error raised below this edge is answered with this API's message for
its condition, not with the adapter's.** `V1-S1-005-PR1` forwarded the adapter's
message, which was safe because every canonical message in this repository happens
to be a constant — safe by review rather than by construction. An adapter is the
component closest to a runtime's error text, a mounted weight-file path, an
endpoint, and a prompt, and
[the redaction rules](../telemetry/redaction.md) name a provider error body as the
surface most likely to be logged, pasted into a ticket, and kept. So the adapter's
message stops at this edge.

`details` carries three values this API produced — the condition identifier, the
adapter kind, and the member a refusal is about — and **no value read out of the
request**. The member *name* is there because the accepted refusal policy requires
a refusal to name the offending member; the value beside it is never read.

`adapterKind` is in `details` because a refusal is a response, and the accepted
record's rule is that every response names the kind that served it. A refusal that
did not would be the one response where the mock and real boundary is invisible at
the place a reader actually looks.

## Health

`/health/live` answers `{"status": "alive"}` while the model is loading and while
the API is draining. That is the point of it: InferOps being alive and InferOps
being able to serve are different questions, and only readiness is allowed to
depend on the backend.

`/health/ready` is the conjunction of this API accepting work and the selected
adapter reporting itself able, and it is 503 when either half is false —
including when the adapter raises while being asked, because a backend that
cannot answer the readiness question has answered it.

Neither response carries an endpoint, a credential, a path, a runtime message, or
any configuration. A readiness probe is the surface most likely to be reachable by
something that should not see any of them.

## Declared capabilities

`/v1/models` publishes the four capability identifiers the accepted surface names,
and it publishes **what the selected adapter declared** rather than a constant:

| Capability | Where its value comes from |
|---|---|
| `streaming` | The adapter's `streaming` declaration |
| `tokenUsage` | The adapter's `token-counting` declaration. The mock declares it `false`, and the API publishes `false` |
| `multiModel` | Derived from the list this endpoint returns, which is one entry |
| `deterministicSampling` | **`null`.** The frozen adapter interface declares nothing about it |

`deterministicSampling` is the one worth reading twice. `ADR 0010` declares it
`true` on the strength of three Sprint 0 runs at temperature 0 that returned
byte-identical content. That is an observation of a runtime on one host on one
day, not a declaration the selected adapter makes about itself, and publishing it
as this deployment's own declaration would be exactly the assumption the
"declared, not assumed" rule exists to prevent. `null` is the honest value for a
question nothing this API can ask answers, and it is the same rule `usage` follows.

## Graceful shutdown

There is no shutdown endpoint, and the accepted record explains why: an HTTP route
that stops a process would be an unauthenticated remote-stop control on a surface
with no authentication in V1. The equivalent is a state machine, and its order is
the property:

1. `begin_shutdown` flips readiness false. **Before** anything drains, so a probe
   stops routing new work while the work already accepted is still running.
2. In-flight requests finish, under a bounded budget. A drain that runs out of
   budget reports that it did not finish rather than pretending it did.
3. The adapter is released. Last, because releasing a backend under in-flight work
   turns a graceful shutdown into a batch of internal errors.

`install_termination_handlers` registers `SIGTERM` and `SIGINT` on a running loop
where the platform supports it, and **reports which signals it installed** — on
Windows, `add_signal_handler` supports none, and a caller finds that out rather
than assuming a handler is in place. Nothing installs it by importing the module:
a library that takes a process-wide signal handler on import takes a decision away
from the program that imported it.

## What has and has not been executed

| Claim | How it was established | Class |
|---|---|---|
| The five routes are registered and answer | Driving the application through the ASGI interface, under `tests/api` | mock |
| A completion is produced end to end | The same, against the committed mock adapter replaying a fixture | mock |
| Identifiers reach the adapter and come back out | The same, with a controlled recording double | mock |
| The refusals above are produced | The same | mock |
| Every canonical code an adapter may raise is mapped, and every condition carries its flag and status | The same, with adapter doubles raising each one | mock |
| An adapter's own message never reaches a caller | The same, with a double raising a message carrying a path, a host, and a prompt fragment | mock |
| Readiness follows the selected backend | The same | mock |
| The shutdown order holds | The same | mock |
| A `mock` selection composes the mock and a `real` selection composes the real adapter | Composing from configuration mappings, under `tests/api/test_api_adapter_selection.py` | mock |
| An unstated selection, and a `real` selection with missing settings, refuse rather than fall back | The same | mock |
| A real selection reaches a runtime | Established by the opt-in real-runtime API suite against the pinned local Kubernetes runtime | local-real-cpu |
| This API answers an HTTP request over a socket | **Not established.** No server ships here and none was run | — |
| This API serves a real model | Established through the in-process ASGI application, real adapter, loopback Kubernetes tunnel, pinned runtime, and hash-verified model in the [Sprint 1 closure run](../proof/serving/v1-s1-real-runtime-closure.md) | local-real-cpu |

The evidence class of the repository-only group is `mock`, which ceilings at
`C1` in [the certification levels](../testing/certification.md). The two
real-runtime rows are `local-real-cpu`, ceiling `C2`, and retain the closure record's
one-host and no-network-served-API limitations.

## Related

- [The decided surface](inference-api-surface.md) and
  [ADR 0010](../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md).
- [The mock and real boundary](mock-and-real-boundary.md), which is why
  `adapterKind` is on every response.
- [Executing real inference through the adapter](real-runtime-inference.md), which
  is what would be composed behind this API for a real deployment.
- [The test and CI strategy](../testing/test-strategy.md), for what the
  `mock-integration` layer may and may not certify.
- [The V1-S1-005-PR2 validation record](../proof/serving/v1-s1-005-pr2-validation.md),
  for what this change ran and what it did not.
