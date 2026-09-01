# V1-S1-005-PR2 — API errors and adapter selection, change validation

The record behind the second half of
[the InferOps inference API](../../serving/inference-api.md). It records what was
run, on what, and what it may be used to claim — which is less than a reader
skimming a green test session would assume, for the same two reasons the first
half's record gave and which **this change did not remove**: nothing here answered
a network request, and nothing here reached a runtime. The API can now be composed
from configuration and told to serve the real adapter, and a configuration that
composes is not a runtime that answered. The [limitations](#limitations) and
[acceptance criteria](#acceptance-criteria) sections are the parts that say so.

> [!NOTE]
> **Post-record resolution (2026-09-01):** ADR 0010 now designates
> `docs/serving/inference-api-surface.v1alpha1.json` as the canonical, versioned,
> tested API snapshot. It also narrows the request subset so `max_tokens` and
> `temperature` are refused rather than accepted and ignored. This closes those
> two recorded gaps; the authorized real-runtime output remains outstanding. The
> original run and its claims below are preserved as historical evidence.

## Classification

| | |
|---|---|
| Evidence class | `local-static` for every check here |
| Ceiling | `C0` |
| What ran | The committed test suites, the linter, the formatter, and the type checker, from a checkout |
| What did not run | Any HTTP server, socket, network request, real model, runtime image, container engine, cluster, paid service, or scanner |
| Claims certified by this record | none |

`local-static` is the weakest label these checks support and it is the correct
one. Every check drove the API against the committed **mock** adapter, against a
controlled double supplied by the test file, or — for the selection rows — against
the real adapter composed over a transport whose every method raises. That last
one is worth naming precisely: it establishes the **shape of the composition** and
establishes nothing whatever about a runtime.

**The same imprecision earlier records noted applies again.** The suites under
`tests/api/` carry the evidence class `mock` and a `C1` ceiling in
[the committed strategy](../../testing/test-strategy.v1alpha1.json). These checks
produce `local-static` results, which is weaker, and the vocabulary rule is to
pick the weakest label the record supports.

**No claim moves to `certified` in this change**, and no layer's status changes.
`mock-integration` was already `implemented`; what changed is that its
canonical-error obligation is now met rather than partly met, and its cited record
moves to this one. The claims this work sits under —
`the-platform-serves-a-workload-the-contract-describes`,
`a-model-that-is-not-ready-is-a-canonical-error`,
`an-unreachable-runtime-is-a-canonical-error`,
`no-prompt-response-or-secret-reaches-a-log-or-a-metric`, and
`deployment-values-derive-only-from-a-validated-document` — all remain `planned`.
Four of the five need a capable host and a real model; the fifth needs the
telemetry work that does not exist.

## Provenance

| Input | Value |
|---|---|
| Repository revision at branch point | `8786620` |
| Branch | `feat/v1-s1-005-api-errors-adapter-selection` |
| Distribution code added | `src/inferops/api/selection.py` |
| Distribution code changed | `src/inferops/api/{__init__,errors,application,responses,surface,validation}.py` |
| Tests added | `tests/api/{test_api_error_contract,test_api_adapter_selection,test_api_end_to_end_mock}.py`, `tests/realruntime/test_api_real_adapter_smoke.py` |
| Tests changed | `tests/api/test_api_request_validation.py`, `tests/serving/test_inference_api_implementation_agreement.py` |
| Accepted records updated to stay true | `docs/serving/inference-api-surface.{md,v1alpha1.json}` (status prose only), `docs/testing/test-strategy.{md,v1alpha1.json}` |
| Accepted records **not** changed | `ADR 0010`, `ADR 0004`, `ADR 0002`, `ADR 0008`, the telemetry catalog, the workload contract, and everything under `contracts/`. **No row of the accepted error mapping was edited, added to, or removed** |
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
uv run --locked python -m pytest tests/adapters -q
uv run --locked python -m pytest tests/serving -q
uv run --locked python -m pytest tests/contracts -q
uv run --locked python -m pytest tests/realruntime -m realruntime -q
git diff --check main...HEAD
```

The whitespace and link checks in [CONTRIBUTING](../../../CONTRIBUTING.md) were run
over the changed Markdown as well.

## Results

| Command | Result |
|---|---|
| `ruff check .` | `All checks passed!` |
| `ruff format --check .` | `170 files already formatted` |
| `python -m mypy` | `Success: no issues found in 86 source files` |
| `python -m pytest -q` | `3856 passed, 25 skipped, 14 deselected` |
| `python -m pytest tests/api -q` | `227 passed` |
| `python -m pytest -m mockintegration -q` | `227 passed, 3668 deselected` |
| `python -m pytest tests/adapters -q` | `565 passed` |
| `python -m pytest tests/serving -q` | `243 passed` |
| `python -m pytest tests/contracts -q` | `191 passed, 7 skipped` |
| `python -m pytest tests/realruntime -m realruntime -q` | **`14 skipped`** — see below |
| `git diff --check main...HEAD` | no output |
| Markdown trailing whitespace and hard tabs | no matches |
| Relative Markdown links in changed files | all resolve |

The fourteen deselected tests in the default lane are the `realruntime` suites,
which the committed marker expression removes because they need the pinned model on
a capable host. **Running that lane explicitly produced fourteen skips, not
fourteen passes.** Every one of them skipped because the required environment
variables are unset, which is what the suites do when nobody asked for a real run.
The lane was **not** entered by this change, no runtime was reached, and **no
result in this record supports any claim about a real model.**

## What the added checks establish

### The canonical error body is served in full

`tests/api/test_api_error_contract.py` asserts the whole body on every refusal
path: `code`, `message`, `requestId`, `correlationId`, `retryable`, and `details`,
with `retryAfterMs` present only where a delay was decided. The member list is
compared against `ERROR_BODY_FIELDS` rather than restated, and
`tests/serving/test_inference_api_implementation_agreement.py` compares that
constant against the accepted record.

### `retryable` follows a condition, and the pair that proves it must

The suite asserts both halves of `capability-unavailable` in the same file: a
streaming request is `400` and not retryable, and an unreachable backend is `503`
and retryable. That pair is the whole argument for keying refusals on a condition
rather than a code — a code-keyed table would have to answer one of them wrongly,
and the accepted record contains both rows.

### Every condition the accepted record maps is reachable, and each copy is checked

The agreement suite reads the record's nine `errorMapping` rows and asserts, per
row, that this API has a condition with that identifier, that it carries the code
the record publishes, that it carries the `retryable` the record publishes, and
that it carries the record's own `retryableOverride`. It also asserts that every
condition **this API added** is absent from the record's list, so a copied row and
an added one cannot be confused.

Three of the nine were unreachable before this change — the record reserved
`request-outside-subset`, `streaming-requested`, and `unsupported-contract-version`
for an API layer, and the real adapter's own table says so in as many words.
`version-unsupported` is reached by a path naming another API version, which is
the only place a caller can name one: this surface reads no version header and the
accepted record defines no request-body extension member.

### An adapter's own message never reaches a caller

A double raising a canonical error whose message carries a `.gguf` path, a prompt
fragment, and a host and port is asserted to produce a response containing none of
them, for four different codes including an unmapped one. The same is asserted for
an uncaught `RuntimeError`. This is a **hardening over `V1-S1-005-PR1`**, which
forwarded the adapter's message — safe at the time because every canonical message
in this repository happens to be a constant, and safe by review rather than by
construction. [The redaction rules](../../telemetry/redaction.md) name a provider
error body as the surface most likely to be logged, pasted into a ticket, and
kept.

### No configuration this API accepts silently produces a mock

`tests/api/test_api_adapter_selection.py` is mostly refusals, and that is
deliberate. An unset selection is refused. An empty, whitespace, differently-cased,
or misspelled one is refused. A `real` selection missing any one of the six runtime
variables is refused **and named**, per variable, and none of those cases produces
a mock adapter. A malformed endpoint is refused, and a mock-labelled model alias on
a real selection is refused. A refusal carrying a canary in the position a naive
implementation would echo is asserted not to contain it.

The accepted selection values are asserted equal to the domain's own closed adapter
vocabulary, so a third selection cannot be introduced without the domain admitting
a third kind first. A second variable naming the adapter kind is asserted to be
ignored: the kind is derived from the selection, so a real adapter cannot be
labelled `mock` by configuration.

### A supplied configuration value is never quietly replaced by a different one

Every numeric variable is refused at zero and below, **naming the variable an
operator actually set** rather than a constructor parameter nobody typed, and the
two optional ones take their default only when absent. Both properties came out of
[the independent review](#independent-review) below: a supplied `INFEROPS_DRAIN_TIMEOUT_MS=0`
was silently replaced by the default, and a negative value was refused by a value
object downstream with a different exception type from the one this module's
callers are told to catch. Both are now refused here, and the suite covers `0`,
`-1`, and `-9000` for all three numeric variables.

### The mock's failure injection is not deployment configuration

A `mock` selection composes an adapter with the default scenario and zero latency
whatever the environment carries, and there is no variable for either. A variable
that made a deployment produce a canonical error on demand would be reachable in
whatever environment the deployment ran in.

### The API answers end to end, for a success and for every failure the mock has

`tests/api/test_api_end_to_end_mock.py` drives the whole path from a configuration
mapping to a response. Its failure parametrisation reads
`MockScenario`'s own members rather than repeating them — each failing member's
value **is** the canonical code it produces — so a code the domain gains and the
mock can raise will fail this suite until the API has a condition for it. For each
one it asserts the code, the whole error contract, the identifiers on the way back,
and that the prompt that produced the failure is absent from the response.

### Correlation survives every path, including the failing ones

The identifiers a caller supplied are asserted on the response headers and in the
body for a success and for **each** injected failure. Propagation into the adapter
is asserted against the committed mock subclassed to keep what it was handed, so
what is exercised is the adapter a mock deployment actually composes.

## Limitations

**Nothing here crossed a socket.** The API implements the ASGI calling convention,
this repository ships no server, and none was installed or run. A result from these
suites establishes routing, reading, validation, translation, status codes,
headers, the error contract, and composition — and establishes nothing about HTTP
request parsing, header folding, chunked transfer, connection reuse, proxies, or a
client disconnecting mid-request. **No result here may be cited as evidence that
this API answers a network request.**

**No runtime was reached, and a real selection is not a real run.** The selection
rows compose `LlamaServerAdapter` over a transport whose every method raises, which
is what makes them safe to run in the default lane and is exactly what makes them
weak: they establish that configuration produces the right object with the right
label, and nothing about a runtime existing, being reachable, or answering.

**The real-adapter smoke suite has not been run.**
`tests/realruntime/test_api_real_adapter_smoke.py` was added by this change and
skipped on every run of it, because the lane is authorization-gated and was not
entered. The parent story's evidence list asks for real end-to-end test output;
this change produces the suite and **not** the output.

**`retryAfterMs` is served for one condition only.** A draining deployment
publishes its own drain budget, which is configured. Nothing else here has a
decided delay — `ADR 0002` decides no concurrency limit, no deployment sets a
termination grace period, and no measurement exists to derive a backoff from — so
the member is absent elsewhere rather than filled with a number nobody chose.

**Seven conditions are this API's own and are not in any accepted record.**
`path-not-served`, `method-not-served`, `request-too-large`,
`deployment-draining`, `adapter-kind-disagreement`, `adapter-rate-limited`, and
`unexpected-failure` fill the gap `V1-S1-005-PR1`'s record named: the accepted
mapping covers request and runtime conditions and does not cover routing, a body
above this deployment's bound, a deployment that has stopped accepting work, or an
adapter contradicting its own deployment. They are marked as added in the code, a
test asserts they are absent from the record's list, and they are published in
[the API document](../../serving/inference-api.md#errors). **Whether any of them
belongs in the accepted record is an open question this change does not settle.**

**One `retryable` override is this change's rather than the record's.**
`adapter-kind-disagreement` is not retryable, against the record's `true` for
`internal-error`, on the argument that a misconfigured deployment does not fix
itself between requests. It is recorded as an override rather than presented as
the default.

**`rate-limited` is a recorded tension with the accepted record.** The record lists
the code among those V1 does not emit, because V1 has no rate limiter. The serving
adapter contract publishes `RateLimitedError` as a code an adapter may raise, and
the mock can be made to raise it. This API therefore **maps** the code and
**originates** none — a test asserts that no refusal site of this API's own names
it — and the reason the record gives stays true. The selected real adapter raises
it nowhere. The tension is reported rather than resolved by editing either record.

**The error body is flat rather than enveloped.** `V1-S1-005-PR1` served
`{code, message, requestId, correlationId}` at the top level and recorded that
choice as a subset rather than a variant so that this change would add members
instead of renaming them, which is what happened. The accepted surface enumerates
the members and does not decide the envelope. A reader comparing this body against
a specification that wraps it in an `error` member will find a difference, and
moving to an envelope now would rename what PR1 published; **it needs a decision
rather than a patch**, and it is listed under [deferred work](#deferred-work).

**Correlation reaches no log, because there is no logger.**
[The redaction rules](../../telemetry/redaction.md) record that no logger, no
formatter, and no redacting sink exists in this repository, and the telemetry
catalog records `emissionStatus` as `nothing-emits`. The identifiers propagate
through the API, into the `RequestContext` the adapter receives, into every error
body, and onto every response header — and there is nothing here that writes a log
record, so **the log half of correlation is not implemented and is not claimed.**
It belongs to the telemetry work, which owns instrumenting this API.

**`/metrics` still publishes no series**, so `ADR 0002` `T7`'s compensating
obligation is **not discharged by this change** either.

**Two accepted request members are still validated and not forwarded**, and a
conversation is still refused. Both are the same interface gap `V1-S1-005-PR1`
recorded and neither is this change's to close.

**Neither `authentication` nor `authorization` exists**, and this change adds none
and claims none. `ADR 0008` `D4` accepts that for V1.

**No security scanner was run.** `gitleaks` is configured in this repository and
was not executed for this record, so the security-scan layer stays `planned` and
this record claims nothing from it.

**The API is not deployed.** No Dockerfile, no manifest, no Service, and no
Deployment exists for it. It cannot be started by anything in this repository —
which is worth stating beside a change that adds environment-variable
configuration, because configuration that nothing reads at startup is
configuration for a deployment that does not exist yet.

## Acceptance criteria

Applied to this PR's boundary and to the parent story.

| Criterion | Status | Where |
|---|---|---|
| Inference, live, ready, and metrics endpoints exist | **met** by `V1-S1-005-PR1`, with `/metrics` publishing no series | `tests/api/`, `tests/serving/` |
| Request/correlation IDs propagate to the adapter | **met**, and now asserted on every failure path as well as the success path | `tests/api/test_api_end_to_end_mock.py` |
| Readiness reflects selected backend state | **met** | `tests/api/test_api_health_models_and_metrics.py` |
| Graceful shutdown stops accepting work before termination | **met** | `tests/api/test_api_lifecycle.py` |
| API returns canonical, non-sensitive errors | **met.** The whole body, every mapped condition, and a message no adapter can supply | `tests/api/test_api_error_contract.py`, `tests/serving/test_inference_api_implementation_agreement.py` |
| Mock and real selection is explicit configuration | **met.** Required, no default, and no fallback | `tests/api/test_api_adapter_selection.py` |

Parent story `V1-S1-005` has **all six acceptance criteria met and is still not
complete**, and the distinction matters. Its evidence list also requires an
OpenAPI or API snapshot and **real end-to-end test output**. Neither exists: `D9` —
whether this surface is published as a contract artifact at all — is still
undecided, and the real-adapter suite added here has not been run against a
runtime. A story whose criteria are met and whose evidence is missing is not a
completed story.

## Deferred work

| Item | Owner | Why it is not here |
|---|---|---|
| Running the real-adapter smoke suite and producing the record | the `real-runtime` lane, manual and authorization-gated | Needs the pinned model and runtime on a capable host, and authorization this change did not have |
| An OpenAPI or API snapshot artifact, and `D9` | needs a decision | Serving a shape is not publishing it, and whether this surface is ever a contract artifact is undecided |
| Whether the canonical error body should be enveloped in an `error` member | needs a decision | The accepted surface enumerates the members and decides no envelope; changing it now would rename what `V1-S1-005-PR1` published |
| Whether the seven API-local conditions belong in the accepted error mapping | needs a decision on `ADR 0010` | They fill a gap the record leaves; adding rows to an accepted record is not a change this PR may make on its own |
| The log half of correlation propagation | the telemetry work | No logger, formatter, or redacting sink exists in this repository, and the accepted redaction document records that as a fact rather than an omission |
| Emitting `inferops_inference_requests_total` and `inferops_inference_errors_total`, and moving the catalog off `nothing-emits` | the telemetry work | Instrumenting this API is that work |
| A per-request bound and a sampling parameter on the serving adapter interface | needs a superseding decision on `V1-S1-002`'s frozen interface | `max_tokens` and `temperature` are accepted by the surface and cannot be forwarded |
| A conversation-carrying parameter on the same interface | as above | A multi-message request is refused rather than flattened |
| A capability declaration for deterministic sampling | as above | Published as `null` rather than assumed |
| An ASGI server, a container image, and a manifest for this API | not yet scheduled | Nothing here can be started, and no lane exists that would run it |
| A `failure` lane exercising the specified error conditions against a real runtime | `failure-and-resilience` layer, still `planned` | Needs a real runtime |
| Whether the `adapter` and `mock-integration` layers should distinguish `local-static` from `mock` evidence | open | Carried forward from `V1-S1-004-PR2` and `V1-S1-005-PR1` |

## Independent review

The change was reviewed by a second reader before it was finalised, against
`CONTRIBUTING.md`, [the mock and real boundary](../../serving/mock-and-real-boundary.md),
[the redaction rules](../../telemetry/redaction.md), and
[the test strategy](../../testing/test-strategy.md), with every command in
[Results](#results) re-run independently. The reviewer reported no critical and no
high finding — specifically none in the mock-and-real boundary, in leakage paths,
in the version-detection boundaries, in the condition table's agreement with the
accepted record, in test quality, in scope, or in what the documents claim — and
two findings in the new configuration reader:

| Finding | Severity | Disposition |
|---|---|---|
| `INFEROPS_DRAIN_TIMEOUT_MS=0` was silently replaced by the default, because `_optional_int(...) or DEFAULT` cannot tell a supplied zero from an unset variable | medium | **Fixed.** Absence is now an explicit `None` check, and zero is refused |
| A negative but parseable number was refused by a value object downstream, raising `InvalidValueError` rather than the `InvalidAdapterConfigError` `select`'s own contract documents | low | **Fixed.** Every number is checked in the selection module, naming the environment variable |

Both fixes and the tests covering them are in this change, and the results above
were re-run after them.

## Authorisation

No authorisation-gated action was taken. No real model was downloaded, no runtime
image was pulled, no cluster was created, no paid service was used, no destructive
operation was run, and no socket was opened. The `realruntime` lane was invoked and
**skipped**, which is the behaviour a lane nobody asked to enter is supposed to
have.

## Related records

- [The InferOps inference API](../../serving/inference-api.md) — what was built.
- [V1-S1-005-PR1 validation](v1-s1-005-pr1-validation.md) — the first half, and the
  record whose deferred-work rows this change closes.
- [The V1 inference API surface](../../serving/inference-api-surface.md) and
  [ADR 0010](../../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md)
  — the shape it implements.
- [The mock and real boundary](../../serving/mock-and-real-boundary.md) — rules 4
  and 5, which the selection module exists to hold.
- [Configuring and inspecting the selected runtime](../../serving/real-runtime-configuration.md)
  — the six variables a `real` selection reads.
- [V1-S1-004-PR2 validation](v1-s1-004-pr2-validation.md) — the adapter a `real`
  selection composes, and the record that says it has not run.
- [The test and CI strategy](../../testing/test-strategy.md) — what the
  `mock-integration` layer may and may not certify.
