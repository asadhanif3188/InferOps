# Executing real inference through the adapter

Status: **implemented**, in [`src/inferops/adapters/llama_cpp/`](../../src/inferops/adapters/llama_cpp/).
It is the second half of connecting InferOps to the runtime
[ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md)
selected. The first half is
[the configuration and inspection package](real-runtime-configuration.md); this
half adds the transport seam, the inference client, the bounded deadlines, the
canonical error mapping, and the `ServingAdapter` implementation that composes
all of it.

**The adapter has not been run against a runtime by the change that added it.**
The `real-runtime` lane is manual and authorization-gated, and it was not
entered. Every executed check behind this document ran against a controlled
transport, which establishes the shape of the call and nothing about the thing on
the other end of it. What that means for the story's acceptance criteria is in
[the validation record](../proof/serving/v1-s1-004-pr2-validation.md), which says
plainly which criterion is still unmet.

The later [Sprint 1 real-runtime closure run](../proof/serving/v1-s1-real-runtime-closure.md)
entered the authorization-gated lane against the pinned runtime and verified
model. All seven adapter checks passed; the combined adapter and API lane passed
all 14 checks after correcting the runtime-identity telemetry boundary it exposed.

## What it is

Four modules were added beside the six the configuration half already held.

| Module | What it holds |
|---|---|
| `transport.py` | The seam a request crosses: a protocol, a response value, and three failure kinds that carry no text from the far side |
| `http_transport.py` | That seam implemented with `http.client`, the standard library's own HTTP |
| `inference.py` | The request body sent, the response body read, and the accepted mapping from a condition to a canonical error code |
| `adapter.py` | `LlamaServerAdapter`, the `ServingAdapter` implementation |

## Why a transport is a parameter

`LlamaServerAdapter` is constructed with settings **and a transport**. It does not
build one. Three consequences follow, and none of them is testability on its own.

**Composing an adapter is where the decision to open sockets is made.** A
transport that is a value can be refused, replaced, or closed by whoever composed
it; one that is a private method cannot.

**A suite exercising the adapter against a controlled response exercises the
adapter.** The moment the socket is inside the adapter, that suite has to
intercept the standard library, and what it then tests is the interception.

**The label on a result stays honest.** A completion this adapter produces
declares `adapter_kind` of `real`, because the adapter is the real one and a value
object may not misreport which class produced it. The controlled transport that
makes such a result possible without a runtime therefore lives in the test file
that uses it, never in the distribution — so an artifact carrying that label can
only come from code a reader is looking at.

## Why the standard library carries the request

[ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)'s
dependency rule forbids an HTTP framework or client library anywhere in this
distribution, and `tests/architecture/test_domain_dependency_boundary.py` enforces
it by reading every module. `http.client` is the standard library's own HTTP, it
is not a framework, and it does what an adapter talking to one known endpoint
needs. Three properties of that choice are decisions rather than details.

| Property | What it does | Why |
|---|---|---|
| No redirect is followed | A `3xx` is a status like any other and maps to `internal-error` | Following one would send a request body to a host the settings never validated. `urllib.request` and its opener would have followed it |
| The response body is read under a 1 MiB bound | A peer cannot decide how much this process allocates | The serving pod's memory limit is 3 GiB, and an unbounded read puts that limit at the mercy of the far side. One byte past the bound is read, so a body that is merely too large is reported as such rather than truncated into an unreadable one |
| A connection is opened per request and closed in a `finally` | No shared mutable state, no keep-alive | ADR 0002 records the trial as single and sequential and decides no concurrency limit, so there is no measurement to trade against |

## The request

```text
POST /v1/chat/completions
{"model": <the runtime alias>,
 "messages": [{"role": "user", "content": <the prompt>}],
 "chat_template_kwargs": {"enable_thinking": false},
 "max_tokens": <only when one was configured>}
```

**`model` is the runtime's alias, not the platform identifier.** This is the
runtime's own API, and the alias is the name the process was started with and
answers to. The platform identifier is what the *result* reports.

**There is no sampling parameter.** ADR 0002 records the sampling defaults as
undecided, [the accepted API surface](inference-api-surface.md) repeats it, and
the frozen adapter protocol has no parameter to pass a caller's temperature
through. So the runtime's own defaults apply, and wiring a request-time
temperature belongs to `V1-S1-005`, which builds the API that would receive one.
One consequence is worth stating: the determinism the trial observed was observed
at temperature 0, and this adapter does not set it, so nothing here may be read as
a determinism guarantee.

**There is one message, and it is the caller's.** A system message would be
content this adapter authored, turning up in a completion nobody asked for it in.

**`chat_template_kwargs` is the one member sent that the caller did not supply.**
It turns off the selected model's reasoning block, and it is sent because the
trial's request carried it: the response shape this adapter normalises is the
shape *that* request produced, and dropping the field would mean parsing a
response nobody in this project has ever seen. It is not a sampling parameter, so
ADR 0002's deferral does not reach it — but it is a decision this change makes,
and it is recorded rather than left implicit.

## The response

Read narrowly: `choices[0].message.content`, `choices[0].finish_reason`, `model`,
and `usage`. Everything else the runtime returns is left where it is —
`system_fingerprint`, `timings`, and `prompt_tokens_details` are each recorded in
the accepted surface as fields this platform does not pass through, and a value
nobody keeps is a value nobody has to redact.

**Absence is preserved and never filled in.** A missing `usage` becomes `None`; a
token count is never estimated, and never zero-filled. A `usage` that is *present
and malformed* is a refusal, because a count nobody can read is not a count that
is missing.

**A completion that names a different model is recorded, not raised on.** The
adapter keeps a `completion-model-differs-from-configured-alias` reason code an
operator can read. Failing the request that discovered it would hide the fact
behind an error nobody could explain.

## Errors, and where the mapping comes from

The mapping is not invented here.
[ADR 0010](../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md)
decided which condition produces which canonical code, and
[the accepted surface data](inference-api-surface.v1alpha1.json) publishes it.
`inference.py` holds a copy carrying the same condition identifiers, and
`tests/adapters/test_llama_server_inference.py` reads the accepted file and fails
when a copy drifts.

| Condition | Canonical code | Observed |
|---|---|---|
| The runtime answers `503`, which means the model is loading | `model-not-ready` | Yes, by the Sprint 0 trial |
| No connection to the runtime could be established | `capability-unavailable` | No |
| The runtime did not answer within the deadline this adapter gave it | `upstream-timeout` | No |
| This adapter's own outer deadline elapsed | `request-timeout` | No |
| The runtime answered a status other than 2xx and other than the loading `503` | `internal-error` | No |
| The runtime answered 2xx with a body this adapter cannot read | `internal-error` | No |

Only the first row was ever observed happening. The other five are mappings, and
the table above says so rather than presenting six equal facts.

**`rate-limited` is never produced.** The accepted record lists it among the codes
V1 does not emit: there is no rate limiter in V1, and the runtime's own deferral
series is a gauge of instantaneous state rather than a limit InferOps enforces. A
runtime answering `429` is therefore an `internal-error` like any other unexpected
status, and not an observation of a limiter that does not exist.

**An unreachable runtime is `capability-unavailable` rather than
`model-not-ready`.** The canonical vocabulary has no member meaning *unavailable*
and the accepted record picks the one it has. The readiness *question* is
different and is answered differently: `is_ready` reports a runtime it cannot
reach as not ready, and returns `False` rather than raising, because unreachable
is an answer to that question and not a fault in the platform.

## Two deadlines, and why there are two

| Deadline | What elapsing means | Code |
|---|---|---|
| The budget handed to the transport | The runtime ran out of time | `upstream-timeout` |
| The adapter's own backstop — that budget **plus a grace** | The transport outlasted its own budget and the grace on top of it | `request-timeout` |

The backstop exists because a transport is a value a caller supplies, and a
protocol cannot enforce the promise it asks for.

**The grace is what makes the pair work.** Both clocks would otherwise be set to
the same duration while the outer one *starts first*: it begins when the call is
made, and the inner cannot begin until the work has been handed to a worker and a
socket opened. Set equal, the outer wins by the dispatch cost every time, every
genuinely slow runtime is reported `request-timeout`, and `upstream-timeout`
becomes a code nothing can produce. That was measured against the real transport
over a real socket, and it is why the grace is there rather than a matter of
taste.

The grace never lengthens a budget a caller configured. It bounds only this
adapter's own wait on a transport that has already broken its promise, and the
transport is handed the configured budget unchanged.

**Every runtime call is under both**, the readiness probe included. The probe is
reached implicitly by the first inference call, so a probe outside the deadlines
would be an unbounded stretch inside a call whose whole contract is that it is
bounded.

**A fired deadline closes the socket.** A thread cannot be cancelled, so when the
backstop fires the worker is still parked inside a read. The connection is built
on the event loop and closed there, which makes that read fail and lets the worker
unwind — otherwise the socket and its pool slot would be held until the far side
chose to answer. The socket's own timeout does not close that gap: it bounds each
individual read rather than the request, so a peer trickling bytes just under the
budget never trips it.

## Readiness gates inference

A tracker that has observed nothing refuses the request and probes, rather than
optimistically sending one. ADR 0002 records a load window of up to 14 s during
which the process is up and answers `503`, so *the socket is open* and *the model
can answer* are different facts and the adapter does not conflate them. A second
request does not re-probe: readiness is a state, not a per-request question. A
completion that comes back `503` updates the tracker there and then, rather than
waiting for the next probe to notice.

Identity — `/v1/models` and `/props` — is **not** read on the request path.
Paying two round trips per completion to re-answer an operational question would
charge every caller for it. `observe_identity` is a separate call.

## The prompt

It is built into one request body, sent, and forgotten. It is not stored on the
adapter, not logged, not echoed into a result, and not attached to any error, and
`tests/adapters/test_llama_server_adapter.py` asserts each of those directly. That
is [the redaction rule](../telemetry/redaction.md) holding at the one place in
this distribution that currently receives a prompt.

No canonical error message repeats a status code, a response body, a host name, a
path, or a port either. Each names its condition in the adapter's own vocabulary,
which is the same division of labour the domain's errors already use.

## What has been executed, and what has not

| | |
|---|---|
| Run in the default lane | The adapter, the inference client, and the transport, against controlled responses |
| Evidence class of those results | `local-static`, which is weaker than the `mock` class the `adapter` layer carries |
| Run against a runtime | Nothing. No image was pulled, no model downloaded or hashed, no process started, and no request issued |
| The `real-runtime` lane | Not entered. It is manual and authorization-gated |
| Claims certified | None. No claim moves status in this change |

`tests/realruntime/test_llama_server_real_smoke.py` is the executable half of the
real-runtime lane for this adapter. It is deselected by the committed default
marker expression, reads its runtime settings from the process environment, and
skips when they are unset — because a missing endpoint means nobody asked for a
real run, not that a real run failed. Running it is one input to an evidence
record, never the record itself.

## Related records

- [Configuring and inspecting the selected runtime](real-runtime-configuration.md) —
  the first half, and the modules this one composes.
- [The mock and real serving boundary](mock-and-real-boundary.md) — the rule that
  makes a missing real record an unmet criterion rather than an opportunity.
- [The inference API surface](inference-api-surface.md) — where the error mapping
  and the response subset were decided.
- [ADR 0002, model and serving runtime](../architecture/decisions/ADR-0002-model-and-serving-runtime.md) —
  the runtime, the model, and everything it left undecided.
- [The V1-S0-003-PR2 feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) —
  the only record in this project that observed the runtime.
- [V1-S1-004-PR2 validation](../proof/serving/v1-s1-004-pr2-validation.md) — what
  this change ran, and what it may be used to claim.
