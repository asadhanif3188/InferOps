# ADR 0010: V1 inference API compatibility surface

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-08-27 |
| Date accepted | 2026-08-27, for D1 through D8 only |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | None |
| Superseded by | None |

> [!IMPORTANT]
> This record decides the **shape** of an API that does not exist. Nothing in this
> repository listens on a port, registers a route, or answers a request, and this
> change adds nothing that does. No OpenAPI document is published, no request or
> response schema is added to [`contracts/`](../../../contracts/), and no client may
> bind to anything here. `V1-S1-005` implements this surface; this record decides it,
> and the gap between those two sentences is the whole of what is being claimed.
>
> Every shape below was read from **the response bodies the runtime actually
> returned** in
> [the feasibility record](../../proof/serving/v1-s0-003-pr2-runtime-feasibility.md)
> on 2026-08-24. No vendor documentation was read for any of it. Where the trial did not observe
> something, this record says so rather than filling the gap from a published
> reference. That applies to streaming, to every error condition but one, and to
> most of the runtime's own endpoint surface.
>
> **D9 is not decided.** Whether this surface is ever published as a contract
> artifact, and by what mechanism, is left open rather than answered in passing.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | Compatibility target: the OpenAI HTTP API shape, restricted to a frozen subset, at the `/v1` prefix | **Accepted** | The runtime already returns this shape, recorded verbatim in the feasibility record; the specification's own preference for it; and the bounded-subset construction below, which answers the objection that compatibility is a promise to track someone else's surface |
| D2 | Five endpoints in V1 scope; everything else recorded out of scope with a reason | **Accepted** as a scope rule | Review, plus a test that the endpoint set and the serving contract's required roles agree |
| D3 | The request and response shapes of each in-scope endpoint | **Accepted** as a specification for unwritten code | The observed response bodies for every field marked observed; nothing serves any of it |
| D4 | Unknown request members are refused, not ignored | **Accepted** | Argument, and the specification's requirement that a policy be declared. The cost is stated rather than hidden |
| D5 | Extension namespace: the `x_inferops` body member, and the `X-InferOps-` header prefix beside it | **Accepted** | Review. The two namespaces are named separately because they carry different things |
| D6 | Streaming is a declared capability and its V1 value is `false` | **Accepted** | The telemetry catalog already defers time-to-first-token because V1 has no streaming path. **No runtime evidence either way**, and the record says so |
| D7 | The declared capability set: token usage `true` and never estimated, deterministic sampling `true` as an observation rather than a promise, multi-model `false` | **Accepted** | The trial's recorded `usage` object and ADR 0002 `T5` for the first; three byte-identical runs for the second; ADR 0002's single-model single-process finding for the third |
| D8 | The runtime-to-canonical-error mapping, and the request counter InferOps owns because the runtime has none | **Accepted in the one row the trial observed; specified in the other eight** | One 503 recorded verbatim from the control plane. Every other row is a specification, marked as such, and the failure lane that would test them does not exist |
| D9 | Whether this surface is published as a contract artifact, and by what mechanism | **Not decided** | Nothing. The integration specification leaves the publication mechanism open, and this record does not close it |

The machine-readable form of all of it is
[`inference-api-surface.v1alpha1.json`](../../serving/inference-api-surface.v1alpha1.json),
checked by [`tests/serving/`](../../../tests/serving/). The document a reader reaches
first is [the inference API surface](../../serving/inference-api-surface.md).

## Context

Nine decision records exist — two accepted outright, six accepted in part, and one
accepted with a recorded exception — one contract is published, and one runtime and
model have been proven once. What does not exist is any statement of what the
platform's own inference API looks like from outside.

That gap is not neutral, and its cost is specific. `V1-S1-002` freezes a
runtime-neutral serving adapter interface, and `V1-S1-005` builds the API on top of
it. Whether the inference endpoint is shaped like a widely-implemented target decides
the request and response types, whether a streaming method appears on the interface,
and what the token-count fields are called — and it decides all of that **one story
before** the API is written. Getting it wrong is not something a later commit tidies
up: it is an interface that callers have already bound to, and this project has
already written down that nothing published can be withdrawn.

The requirement is external. The integration specification is explicit that this
choice needs a record before anything is built against it, and no record existed. The
same gap was already known and tracked as work that had to be done before Sprint 1
could start.

Three constraints come from decisions already accepted:

- **ADR 0002 `T5`** was a blocking threshold demanding that
  `POST /v1/chat/completions` return a body carrying `choices[0].message.content`,
  `model`, and a `usage` token count, and that `GET /v1/models` report the pinned
  model. It passed. The selected runtime therefore already speaks the shape this
  record is deciding whether to adopt.
- **ADR 0002 `T7`** was a blocking threshold demanding request and token counters,
  and it **failed** on the request half: the runtime has no cumulative request
  counter at all. The record was accepted with that argued, and the argument was that
  InferOps is the component that receives the requests and is therefore the right
  place to count them. This record is where that obligation lands.
- **ADR 0004** puts the serving runtime in its own Deployment behind its own Service,
  and forbids the platform domain from importing a runtime SDK or an HTTP framework.
  That decides *where* any translation between an external shape and an internal one
  is allowed to happen.

## Decision criteria

Stated before the comparison, so that the comparison can be checked against them.

1. **Reach.** How many callers can use it without writing an adapter first?
2. **Distance from what the runtime already serves.** Every shape the platform
   invents is a translation someone maintains.
3. **What a break costs once published.** This is asymmetric. A break in a shape the
   project controls is scheduled; a break in a shape it does not control is not.
4. **Whether it hides required platform behaviour.** The specification permits a
   compatible API only on this condition.
5. **Whether it can express a declared capability.** V1 must be able to say
   "no streaming" in a place a caller can read, rather than by failing.
6. **Whether it survives the runtime being replaced.** ADR 0002 records plainly that
   the contract must survive the swap and the runtime will not.

## Decision

### D1 — Compatibility target: a frozen subset of the OpenAI HTTP API shape

The user-facing inference API is shaped like the OpenAI HTTP API, at the `/v1` path
prefix, restricted to the field lists in
[the surface record](../../serving/inference-api-surface.v1alpha1.json).

Two things about that sentence carry the decision, and both are easy to skim past.

**The `/v1` prefix is not an InferOps version claim.** It belongs to the shape being
borrowed. InferOps versions this surface through `contractVersion`, which is
`inferops.io/v1alpha1`, travels in the extension namespace, and moves independently
of the path. A reader who takes `/v1` as a stability promise from this project has
been misled, so the two version identifiers are stated together everywhere the
surface is described.

**The subset is frozen, and the freeze is what makes the target defensible.** The
serious objection to adopting a compatibility target is criterion 3: it is
compatibility with a surface this project does not control and cannot version, so an
upstream change leaves the project choosing between following a shape it did not pick
and breaking its own callers. That objection is correct, and the answer is not to
wave it away. It is to adopt a **shape read on a date and written down**, not a
commitment to track what that shape does next. The date is 2026-08-24, the source is
the response bodies in the feasibility record, and the field lists are enumerated
rather than incorporated by reference. Anything upstream adds later is an upstream
addition; it arrives here only if a superseding record decides it should.

### The alternative: a project-native API

Compared rather than dismissed, because it is a genuinely reasonable choice and
criterion 3 favours it.

| Criterion | Frozen compatible subset (**selected**) | Project-native API |
|---|---|---|
| Reach | Existing clients, SDKs, and command-line recipes work against it unchanged | Zero callers on day one. Every one of them writes an adapter first |
| Distance from the runtime | The runtime already returns this shape; the trial's recorded response is the shape | InferOps translates native-in and compatible-out to reach the same runtime, so the shape exists anyway — twice |
| Cost of a break | **Worse.** The shape is not the project's to version, so upstream movement is a decision imposed on it | **Better.** A break is scheduled by the project that caused it |
| Hides platform behaviour? | Not once the extension namespace carries what the target has no place for. That is D5's job, and it is the condition the specification attaches | No. It can be designed around the platform's needs from the start |
| Declared capability | Not natively. The target has no capability descriptor, so declaring one is an extension | Natively, if designed for it |
| Survives a runtime swap | Yes. It is an edge shape, and the adapter interface behind it is runtime-neutral by D8's first consequence | Yes, equally |

**Why the compatible subset wins.** Criterion 3 is the only criterion that favours
the native API, and freezing the subset converts it from a standing exposure into a
one-time reading. What is left is criterion 1, where the gap is not close: a platform
whose selling point is that a stranger can reproduce it should not require that
stranger to write a client first. Criterion 2 then compounds it — the native option
does not avoid the compatible shape, it adds a second one, because the runtime speaks
the compatible shape whatever the platform's front door looks like.

**What the native option would have bought, stated so it is not lost.** A native API
would let the request carry workload identity, correlation, and a declared capability
set as first-class fields rather than as an extension member, and its evolution would
be the project's to schedule. If a future record finds the extension namespace is
carrying more of the request than the borrowed shape is, that is the signal this
decision was wrong, and it should be reopened rather than patched.

### D2 — The endpoint subset

Five endpoints, covering every role the model-serving contract requires except
graceful shutdown, which is met by an equivalent rather than an endpoint.

| Method | Path | Origin | Role | Runtime counterpart observed in the trial |
|---|---|---|---|---|
| `POST` | `/v1/chat/completions` | compatibility target | inference | `POST /v1/chat/completions` |
| `GET` | `/v1/models` | compatibility target | model and runtime metadata | `GET /v1/models` |
| `GET` | `/health/live` | InferOps-native | liveness | none, and deliberately so |
| `GET` | `/health/ready` | InferOps-native | readiness | `GET /health` |
| `GET` | `/metrics` | InferOps-native | metrics | `GET /metrics` |

The health paths are InferOps-native because the compatibility target defines no
health surface at all. They are not extensions to a borrowed shape; they are
endpoints in a space the borrowed shape leaves empty, which is a different thing from
what D5 governs.

`/health/live` has no runtime counterpart on purpose. ADR 0002's proposed probe
mapping — proven under `T6` with zero restarts across seven starts — points liveness
at a TCP socket precisely because the runtime's `/health` returns 503 while loading,
and a liveness probe pointed at that restarts the pod mid-load and never converges.
The same reasoning applies one layer up: InferOps being alive and InferOps being able
to serve are different questions, and only readiness is allowed to depend on the
runtime.

**Graceful shutdown is met by an equivalent, not an endpoint.** The serving contract
permits either. The equivalent is `SIGTERM` handling that flips readiness false,
drains what is in flight, and exits. An HTTP endpoint that stops a process would be an
unauthenticated remote-stop control, on a surface where ADR 0008 D4 accepts no
authentication in V1 — which is a hole this record declines to open.

### What is out of scope, and why

Recorded rather than unmentioned, because an endpoint nobody mentioned is
indistinguishable from an endpoint somebody forgot.

| Not served | Why |
|---|---|
| `/v1/completions` | The legacy text-completion shape. It doubles the request surface the adapter must satisfy, for one runtime and one chat model, and the chat shape answers the same question |
| `/v1/embeddings` | The pinned model is a chat model. Embeddings need a second model and — because ADR 0002 records the runtime as a single-model single-process server — a second Deployment. Neither is decided |
| `/v1/responses` | A newer upstream shape, still moving. Adopting it is the thing D1's freeze refuses |
| `/v1/models/{id}` | Retrieving one model by identifier answers the same question as the list, for a deployment serving exactly one model |
| `/v1/audio`, `/v1/images`, `/v1/moderations`, `/v1/files`, `/v1/batches`, `/v1/fine_tuning`, `/v1/assistants`, `/v1/vector_stores`, and everything under them | No model, no component, and no storage exists for any of them |
| The runtime's own paths — `/props`, `/completion`, `/slots`, `/infill`, `/tokenize`, `/detokenize`, `/embedding` | **The runtime's surface is not proxied.** Passing a runtime-specific path through the platform API puts a runtime shape in front of callers and defeats the runtime-neutral adapter. Of these, only `/props` was observed in the trial; the rest were not enumerated there, and nothing here relies on them existing |

That last row is the one worth arguing with, and the argument is criterion 6. Every
runtime path the platform proxies is a path that has to be reproduced by whatever
replaces the runtime, or removed from callers who came to depend on it.

### D3 — The shapes

Stated per endpoint in
[the surface document](../../serving/inference-api-surface.md), and committed as data
beside it. Two properties of the tables there matter more than the field names.

**Every field is marked with whether the trial observed it.** On
`/v1/chat/completions`, `model`, `messages`, `max_tokens`, and `temperature` were sent
to the runtime and accepted, and `id`, `object`, `created`, `model`, `choices`, and
`usage` came back — each of them inside a response body the record quotes verbatim.
`stream` and the extension member were never exercised and are marked unobserved.

**No field of `/v1/models` is marked observed, and that is not an oversight.** The
trial did call the endpoint, and the record shows what came back — but what it shows
is the runtime's own model metadata printed as text, not a list envelope. The
endpoint is evidenced; its response shape is not, and marking the envelope observed
because the endpoint was called is exactly the slippage this column exists to catch.

The distinction is kept because a shape read from a recorded response and a shape
written from expectation are different kinds of claim, and it is enforced at the
granularity that matters: a field claiming observation has to appear as a **JSON
member key inside a fenced block** of the record, not merely as a word somewhere in
its prose.

**Three fields the runtime returned are deliberately not passed through.**
`system_fingerprint` is a runtime build string, and runtime identity belongs in the
runtime descriptor and the build-info metric where it is published once rather than
on every response. `timings` is runtime-specific, and a per-request timing figure on a
public response is a throughput claim by another route — ADR 0002 already refuses to
publish the decode rate it measured, and this is the same refusal applied to the same
number arriving through a different door. `prompt_tokens_details` is a prompt-cache
statistic of the runtime's, left outside the subset for V1.

### D4 — Unknown request members are refused

A member of a request body that is not in the frozen subset is refused with
`contract-invalid`, and the refusal names the member.

The specification requires that unknown fields be handled according to a **declared**
policy. This is the declaration, and it is the strict one.

**Why refuse.** Silently ignoring a parameter that changes the result is worse than
refusing it. A caller who sends `n: 4` and receives one choice, or sends `stop` and
receives text past the stop sequence, has been handed a wrong answer rather than an
error — and has no way to find out. The failure is silent, plausible, and on the
caller's side of the boundary.

**What it costs, stated rather than hidden.** Clients that send upstream defaults
such as `top_p`, `n`, `presence_penalty`, or `stop` are refused until they stop
sending them. That is a real reduction in exactly the reach criterion 1 chose this
target for, and it is the weakest point of this record. It is accepted because the
alternative fails in a direction that cannot be detected from outside.

**The alternative that was rejected**: accept unknown members and echo the ignored
ones back in the extension namespace. Rejected because it makes the wrong answer the
default outcome for every caller who does not read the echo, which is most of them.

### D5 — The extension namespace

Two namespaces, named together because confusing them is the likely failure.

| Namespace | Form | Carries |
|---|---|---|
| `x_inferops` | One object-valued member of a JSON body | What the compatibility target has no place for: `requestId`, `correlationId`, `contractVersion`, `adapterKind`, `modelRef` on a completion; the runtime descriptor and the declared capability set on `/v1/models` |
| `X-InferOps-` | An HTTP header prefix | Transport metadata the specification already names: request id, correlation id, workload id, workload version, environment |

`snake_case` matches the surrounding body. The `x_` prefix marks the member as an
extension and collides with no member observed in the runtime's own responses.

**V1 defines no request-body extension member.** Correlation and workload metadata
travel in headers, and the specification requires that security-sensitive values be
validated or injected by a trusted component rather than trusted because a client
sent them. A request member a caller fills in would be the wrong place for all of it.

**`adapterKind` on every response is not decoration.** Which adapter served a response
decides what that response may be used to claim, and
[the mock and real boundary](../../serving/mock-and-real-boundary.md) makes that a
rule rather than a preference. Leaving it to deployment configuration makes the
boundary invisible at the one place a reader actually looks.

### D6 — Streaming: declared `false`

Streaming is a **capability the surface declares**, published at
`/v1/models` as `x_inferops.capabilities.streaming`, and its V1 value is `false`. A
request setting `stream: true` is refused with `capability-unavailable` and an
explicit `retryable: false`.

**The retryable override is deliberate.** The canonical error contract gives
`capability-unavailable` a retryable default of true, which is right for a capability
that is temporarily gone and wrong for one that was never built. Retrying does not
make a capability appear. The override is recorded here so that a reader comparing
this surface against the specification's default column finds an argued difference
rather than a discrepancy.

**What supports the value.** The telemetry catalog already defers
`inferops_inference_time_to_first_token_seconds`, and its stated reason is that V1 has
no streaming path — without one, time to first token is the same measurement as
request duration, and publishing it as a second signal would be a fabrication. This
record does not create the path that would un-defer it.

**What does not support it, and must not be read into it.** Whether the selected
runtime *can* stream was **not exercised by the feasibility trial**. This record
asserts nothing about it in either direction. The value is `false` because InferOps
has no streaming path, not because the runtime was found to lack one.

### D7 — The rest of the declared capability set

Three capabilities beside streaming, each published at `/v1/models` under
`x_inferops.capabilities` and each carrying what supports it. A capability the surface
publishes and this record does not decide would be a flag with nobody behind it, so
all four are covered between D6 and here.

#### Token usage: declared `true`, and never estimated

Token usage is published at `x_inferops.capabilities.tokenUsage`, and its V1 value is
`true`.

It is supported by an observation rather than an expectation: the trial's recorded
response carried `usage` with `prompt_tokens`, `completion_tokens`, and
`total_tokens`, and ADR 0002 `T5` made that a blocking threshold before the trial ran.

**The rule that travels with it.** `usage` carries the counts the adapter supplied and
is `null` where it did not. It is never estimated and never zero-filled. A count
InferOps derives by tokenising a prompt itself is an estimate, and the telemetry
catalog already records that an estimate certifies nothing. The mock and real boundary
names token accounting explicitly as a property a mock cannot honestly reproduce — a
mock reports numbers its author chose — so a mock adapter either counts its own
synthetic tokens honestly or declares the capability false.

`null` rather than zero is the same rule the cost method applies to a missing input,
and for the same reason: a zero is a measurement, and an absence is not.

#### Deterministic sampling: declared `true`, as an observation

Published at `x_inferops.capabilities.deterministicSampling`, and its V1 value is
`true` on the strength of three runs at temperature 0 that returned **byte-identical
content** in the trial.

The flag is worth having because determinism is what makes a serving path testable at
all — a response that differs run to run cannot be asserted against. It is also the
capability most likely to be over-read, so the limit is part of the declaration: it
was observed for one model, one quantisation, one thread count, one runtime build, one
host, one day. It is **not** a guarantee across any of those, and a caller may not
treat it as one. Nothing in V1 pins the sampling defaults that would make it one,
because ADR 0002 left them undecided.

#### Multi-model: declared `false`

Published at `x_inferops.capabilities.multiModel`, and its V1 value is `false`.

ADR 0002 records the selected runtime as a single-model, single-process server: a
second model is a second Deployment. So one InferOps deployment fronts one model, the
`model` field on a request is **checked against the served model rather than used to
select one**, and a mismatch is `contract-invalid` rather than a lookup that fails.

The consequence a caller feels is that `/v1/models` will always list exactly one
entry, which is why retrieving a model by identifier is out of scope. The consequence
the project feels is that multi-model serving is not a configuration change here; it
is the ceiling ADR 0002 already said the deeper serving work would have to break
through.

### D8 — Error mapping, and the counter InferOps owns

The mapping from observable runtime behaviour to the canonical codes. **One row was
observed. Eight are specified.** The distinction is in the table because the failure
lane that would exercise the other eight is deselected by default and has no code.

| Condition | Observed | Code | Retryable |
|---|---|---|---|
| The runtime reports not-ready while the model loads | **Yes** — the control plane recorded a startup probe failing with statuscode 503 | `model-not-ready` | yes |
| The runtime's Service or pod does not accept a connection | No | `capability-unavailable` | yes |
| The runtime does not answer within the adapter's deadline | No | `upstream-timeout` | yes |
| The caller's own deadline expires first | No | `request-timeout` | yes |
| A request member outside the subset, a bad role, a non-string content, a model that is not the served model, or `max_tokens` above the ceiling | No | `contract-invalid` | no |
| `stream: true` | No | `capability-unavailable` | **no** — overridden, see D6 |
| A contract or API version this deployment does not support | No | `version-unsupported` | no |
| The runtime answers non-2xx, and not the 503 that means loading | No | `internal-error` | yes |
| The runtime answers 2xx with a body the adapter cannot read into the shape above | No | `internal-error` | yes |

**Six canonical codes are recorded as not emitted by this API**, each with a reason,
because a code listed without a condition is a claim that something checks for it:

| Code | Why V1 never emits it |
|---|---|
| `authentication-required` | ADR 0008 D4 accepts least exposure at the caller boundary with no authentication in V1 |
| `authorization-denied` | As above. There is no identity to authorize |
| `policy-denied` | No policy engine is selected; the specification leaves it open and this record does not close it |
| `rate-limited` | V1 has no rate limiter. The runtime's deferral series is a gauge of instantaneous state, not a limit InferOps enforces |
| `budget-exceeded` | No budget is enforced anywhere, and ADR 0007 records that every cost figure this project can produce has confidence `none` |
| `evaluation-failed` | A release-gate outcome, not an inference-time condition |

#### The `T7` consequence: InferOps counts the requests

ADR 0002 `T7` failed on exactly one thing: the runtime exposes **no cumulative request
counter**. The two series carrying `requests` in their names —
`llamacpp:requests_processing` and `llamacpp:requests_deferred` — are gauges of
instantaneous state, and a gauge reading zero between requests cannot be summed,
rated, or alerted on the way a counter can.

InferOps receives the requests, so InferOps counts them. The metric already exists in
the telemetry catalog as `inferops_inference_requests_total`, carrying that exact
reason in its own notes, and `inferops_inference_errors_total` labelled by
`error-code` is what makes the mapping above observable rather than merely written
down.

**This record adds no metric.** It binds two entries that already exist to this
surface and to these codes. What it does add is the consequence that closes the `T7`
argument: the counter is not optional platform polish, it is the compensation the
exception was accepted on, and an API built without it leaves a blocking threshold
failed with nothing in its place.

### What the adapter interface must expose

`V1-S1-002` freezes the adapter interface one story before the API is written, which
is why this record has to state the consequences rather than leave them to be
inferred.

| Consequence | Why |
|---|---|
| The API is shaped like the compatibility target **at its edge**; the adapter interface is runtime-neutral, and the translation happens in the API layer | An adapter interface taking a compatibility-target request type puts that shape inside the platform domain. The architecture's dependency rule forbids exactly that leak, and the domain that knows about the target cannot be tested without it |
| One synchronous, non-streaming generate call | Streaming is declared `false`. An interface carrying a streaming method nothing implements is an assumption dressed as a capability |
| Token usage returned as an **optional** value | A required field forces a mock to invent numbers, and the boundary rule names token accounting as a property a mock cannot honestly reproduce |
| The adapter **declares** its capability set; the API publishes what the selected adapter declared, not a constant | A capability that is a constant in the API is an assumption. One the adapter declares is a fact about the thing that will serve the request |
| Every response names the adapter kind that served it | See D5. It is the mock and real boundary made visible where a reader looks |

### D9 — Publication as a contract artifact is not decided

Whether this surface is ever published as a contract artifact — an OpenAPI document, a
JSON Schema, an entry in [`contracts/`](../../../contracts/) — and by what mechanism, is
**not decided here**. The specification's open decision on a contract artifact
publication mechanism stays open, and this record does not narrow it.

The reason is the rule this whole record is built around: nothing is published until
something serves it. A schema in `contracts/` is a thing clients bind to. A decision
record is a thing reviewers argue with. Until `V1-S1-005` serves a request, only the
second is honest.

## Consequences

- **`V1-S1-002` can freeze an adapter interface against a decided surface** rather
  than against a guess. That is the whole point of the story, and it is the
  consequence that clears the blocker.
- **`V1-S1-005` inherits a strict input policy it must implement**, including the
  refusal of unknown members, which is more work than accepting them and will
  generate support questions from callers sending upstream defaults.
- **The API layer owns a translation.** Compatibility at the edge plus a
  runtime-neutral adapter means the mapping lives in one place, and that place is now
  named. It is also a place that can drift from this record, which is what the test
  beside it exists to catch.
- **The request counter is now load-bearing.** ADR 0002 was accepted with a blocking
  threshold failed, on the argument that the platform would count requests. This
  record makes that a stated obligation of the API rather than an intention recorded
  in a metric's notes.
- **Six of the thirteen canonical codes are recorded as never emitted in V1.** A reader
  comparing this API against the canonical error contract will find nearly half the
  code list unreachable, which is an accurate description of a platform with no
  authentication, no policy engine, no rate limiter, and no budget enforcement.
- **`retryable` is overridden once**, against the specification's default column, and
  a consumer written from the default table alone will retry a request that can never
  succeed unless it reads the field rather than the code.
- **Nothing here is defended.** The surface assumes a caller reaching it inside the
  cluster. ADR 0008 D4 accepts that with no authentication in V1, and this record adds
  no control and claims none.

## Compatibility impact

- **No published contract changes.** `contracts/` is untouched, the workload contract
  schema is untouched, and no existing fixture, identifier, or error code is
  redefined.
- **ADR 0002 is not weakened.** `T5` and `T7` are read as they stand, including the
  failure, and the `T7` exception is carried forward as an obligation rather than
  quietly discharged.
- **ADR 0006 is not amended.** Two metrics are cited; neither is redefined, and the
  streaming decision here agrees with the deferral reason already recorded there
  rather than overriding it.
- **ADR 0008 is not amended.** The absence of authentication is read from D4 and
  reflected in the codes this API cannot emit.
- **ADR 0004 is not amended.** The dependency rule is applied, not changed: the
  compatibility target is admitted at the edge and kept out of the domain.
- **One accepted record is edited in a way that must be visible.** The documentation
  test layer in the test strategy adds `tests/serving` to the directories it covers.
  That is a widening of an existing layer to include a new suite of the same kind,
  not a change to the layer's meaning, its marker, or its evidence class.

## Security considerations

- **No authentication and no authorization are introduced**, and none is claimed. The
  surface is reachable by anything that can reach it, which in the accepted local
  cluster means anything inside it.
- **The error body carries no value from the request.** The canonical contract already
  forbids messages that expose secrets, stack traces, prompts, or policy detail, and
  D4's refusals name the offending **member**, never its value.
- **No prompt and no completion is placed anywhere the telemetry catalog forbids.**
  This record introduces no telemetry field, and the content classes it would fall
  under have an empty placement list.
- **Three runtime-supplied fields are dropped rather than forwarded**, one of them —
  `timings` — specifically because forwarding it would publish per-request
  performance figures the project has refused to publish elsewhere.
- **The runtime's own surface is not proxied**, so no runtime path becomes reachable
  through the platform by default.
- **`adapterKind` in every response** is what stops a mock-served answer being read as
  a real one. That is a property of honest reporting rather than a control, and it is
  worth nothing until something implements it.

## Evidence

| Claim | Evidence | Class |
|---|---|---|
| The runtime returns a body carrying `choices[0].message.content`, `model`, and `usage` | [Feasibility record](../../proof/serving/v1-s0-003-pr2-runtime-feasibility.md), stage 5, recorded verbatim | Local real runtime, one host, one day |
| `GET /v1/models` reports the served model | Same record, stage 4. **The endpoint only** — the record prints the runtime's model metadata, not a list envelope, so no field of the response shape is evidenced | Local real runtime |
| The runtime reports 503 while the model loads | Same record, stage 4, quoted from the control plane | Local real runtime |
| Temperature 0 returned byte-identical content across three runs | Same record, stage 5 | Local real runtime, and explicitly not a guarantee |
| The runtime exposes no cumulative request counter | Same record, stage 6, with the complete series list | Local real runtime |
| Every other error row, the extension namespace, and every response shape not marked observed | **None.** They are specifications for unwritten code and are marked as such | Documented expectation |
| This record and its data agree | [Change validation](../../proof/serving/v1-s0-012-pr1-validation.md), and [`tests/serving/`](../../../tests/serving/) | Machine check over committed files |

## What this record does not decide

- **The context length, KV budget, concurrency limit, and sampling defaults.**
  ADR 0002 left all four undecided; this record does not fill them in, and the
  `max_tokens` ceiling D4 refuses above depends on the first of them.
- **Authentication, authorization, rate limiting, and quota** at the caller boundary.
- **Any asynchronous or event-carried inference shape.** V1 serves one synchronous
  request at a time and decides nothing about any other form.
- **How a caller outside the cluster reaches the API.** The accepted local cluster
  ships no ingress controller and no load-balancer implementation, and ADR 0004 D7
  leaves both unowned.
- **Whether this surface is ever published as a contract artifact.** D9, above.
- **Anything about how any of it behaves.** No component serves a request, so this
  record has produced no measurement of its own and cites none.
