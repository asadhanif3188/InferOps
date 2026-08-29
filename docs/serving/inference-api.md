# The InferOps inference API

Status: **implemented, and it has answered no network request.**
[`src/inferops/api/`](../../src/inferops/api/) registers the five endpoints
[the accepted surface](inference-api-surface.md) decided and answers each of them
through the serving adapter it is composed with. What it is not is a running
service: the application implements the ASGI calling convention and **this
repository ships no ASGI server**, so every result behind this document was
produced by driving the application through its own interface. No socket has been
bound and no byte has crossed a network.

This document is what the API does. [ADR 0010](../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md)
is why its shape is what it is, and this document does not restate the argument.

## What is served, and what is deliberately unfinished

| Route | Served | Unfinished, and who owns it |
|---|---|---|
| `POST /v1/chat/completions` | Validation, translation to the adapter, and the completion body | The canonical error body is served in a subset — `V1-S1-005-PR2`. `max_tokens` and `temperature` are validated and not forwarded — see [the gap below](#the-two-members-that-are-validated-and-not-forwarded) |
| `GET /v1/models` | The list envelope, the runtime descriptor, and the declared capability set | `deterministicSampling` is published as `null` — see [declared capabilities](#declared-capabilities) |
| `GET /health/live` | Whether this process is alive | — |
| `GET /health/ready` | This API accepting work **and** the selected adapter reporting itself able | — |
| `GET /metrics` | The route, in the Prometheus exposition content type | It publishes **no series**. Instrumenting this API is the telemetry work |

## How it is composed

The API is the composition point, and it has no default adapter. One is handed to
it, and a mock that could become the live adapter by omission is what
[the mock and real boundary](mock-and-real-boundary.md) rule 5 forbids — so there
is nothing to omit. Selecting an adapter from configuration is `V1-S1-005-PR2`'s.

```python
from inferops.adapters import MockServingAdapter
from inferops.api import ApiConfiguration, InferOpsApi
from inferops.domain.serving import AdapterConfiguration

api = InferOpsApi(
    adapter=MockServingAdapter(),
    adapter_configuration=AdapterConfiguration(
        model_identifier="mock-fixed-fixture",
        timeout_ms=5_000,
    ),
    configuration=ApiConfiguration(adapter_kind="mock"),
)
```

Constructing it performs no I/O. The adapter is initialized on lifespan startup
and released after the drain on lifespan shutdown, so a composition point cannot
fail halfway through building an object.

`adapter_kind` is supplied here because the serving adapter protocol publishes no
method for it — and it is **checked against every result the adapter produces**.
A deployment composed as `mock` whose adapter returns a `real`-labelled result is
refused with `internal-error` rather than served, because a response whose
`adapterKind` cannot be trusted is a response nobody can use to claim anything.

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
| A member outside `model`, `messages`, `max_tokens`, `temperature`, `stream` | `contract-invalid` | 400 |
| A member outside `role`, `content` inside a message | `contract-invalid` | 400 |
| `model` that is not the served model | `contract-invalid` | 400 |
| `role` outside `system`, `user`, `assistant` | `contract-invalid` | 400 |
| `content` that is not a string | `contract-invalid` | 400 |
| More than one message, or one whose role is not `user` | `contract-invalid` | 400 |
| `max_tokens` that is not a positive integer, or above the configured ceiling | `contract-invalid` | 400 |
| `temperature` that is not a number | `contract-invalid` | 400 |
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

### The two members that are validated and not forwarded

`max_tokens` and `temperature` are in the frozen subset, they are checked here,
and **the frozen adapter interface has no parameter for either**. What actually
bounds generation is the `max_tokens` on the adapter's own configuration, set at
composition time; the runtime's own sampling defaults apply to temperature.

That is a conflict between two accepted records rather than a choice made in the
code. The surface says both members are passed to the adapter; the adapter
interface has nowhere to pass them. Neither record was edited: the members are
accepted because the published subset accepts them, they are validated because a
member outside its stated type is still a refusal, and the gap is recorded here
and in the change's validation record. **It needs a superseding decision on the
adapter interface**, and until there is one, a caller setting `temperature: 0.9`
gets the runtime's default and no indication that they did.

## Errors

The body served today is a deliberate subset of the canonical error body
`ADR 0010` decided:

```json
{
  "code": "contract-invalid",
  "message": "temperature: this member must be a number",
  "requestId": "…",
  "correlationId": "…"
}
```

`retryable`, `retryAfterMs`, and `details` are **not** served yet.
`V1-S1-005-PR2` standardises the error contract, and this is a subset rather than
a variant so that PR2 adds members instead of renaming them.

A message names a member and states a constraint in this API's own vocabulary. It
never carries a value read out of the request, a runtime's own words, a stack
trace, or a path — including when an adapter raises an exception whose message
carries one, which is dropped rather than wrapped.

The HTTP status is decided by **where the failure happened**, not by the code
alone: `capability-unavailable` is 400 when a caller asked for streaming and 503
when the backend cannot serve, because those are a client error and a server state
respectively. That mapping is provisional. The accepted record maps conditions to
codes and says nothing about statuses, and closing that gap is `V1-S1-005-PR2`'s.

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
| Readiness follows the selected backend | The same | mock |
| The shutdown order holds | The same | mock |
| This API answers an HTTP request over a socket | **Not established.** No server ships here and none was run | — |
| This API serves a real model | **Not established.** No real adapter was composed and no runtime was reached | — |

The evidence class of everything in the first group is `mock`, which ceilings at
`C1` in [the certification levels](../testing/certification.md). It proves the
consumer and the contract, and it proves nothing about a provider.

## Related

- [The decided surface](inference-api-surface.md) and
  [ADR 0010](../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md).
- [The mock and real boundary](mock-and-real-boundary.md), which is why
  `adapterKind` is on every response.
- [Executing real inference through the adapter](real-runtime-inference.md), which
  is what would be composed behind this API for a real deployment.
- [The test and CI strategy](../testing/test-strategy.md), for what the
  `mock-integration` layer may and may not certify.
