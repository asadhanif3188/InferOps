# V1-S1-003-PR1 — deterministic mock serving, change validation

The record behind the `adapter` test layer becoming `implemented`. It records what
was run, on what, and what it may be used to claim — which is less than a reader
skimming a green test session might assume, and the [limitations](#limitations)
section is the part that says so.

## Classification

| | |
|---|---|
| Evidence class | `mock` for the adapter suite; `local-static` for every other check here |
| Ceiling | `C1` for the adapter suite; `C0` for the rest |
| What ran | The committed test suites, the linter, the formatter, and the type checker, from a checkout |
| What did not run | Any real model, runtime image, container engine, cluster, network call, paid service, or scanner |
| Claims certified by this record | none |

`mock` is the weakest label the adapter suite supports and it is the correct one.
The suite exercises a consumer against a contract, and the provider on the other
side of the call is a fixture replayer written from that same contract. Per
[the certification levels](../../testing/certification.md) that ceilings at `C1`, and
per [the boundary rule](../../serving/mock-and-real-boundary.md) no amount of
faithfulness raises it.

**No claim moves to `certified` in this change.** The claim this work exists under —
`the-mock-serving-path-identifies-itself-as-a-mock` — cites two layers, `adapter` and
`mock-integration`. The second needs a platform API that does not exist, and the
strategy suite refuses a certified claim resting on a layer that is not implemented.
The claim therefore stays `planned`, and it stays `planned` on purpose.

## Provenance

| Input | Value |
|---|---|
| Repository revision at branch point | `5b2cd99` |
| Branch | `feat/v1-s1-003-deterministic-mock-serving` |
| Distribution code added | `src/inferops/adapters/` |
| Tests added | `tests/adapters/`, `tests/support/serving_conformance.py` |
| Response fixture replayed | [`mock-llm-chat-completion.response.json`](../../../contracts/workload/fixtures/mock-llm-chat-completion.response.json) |
| Runtime identity used | `inferops-mock-serving`, from [the compatibility matrix](../../../contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json) |
| Model artifact | none |
| Container image | none |

## Environment

| | |
|---|---|
| Host | One Windows workstation, contributor-owned |
| Operating system | Windows 11, build 10.0.26200 |
| Python | 3.12.12 (CPython, MSC v.1944, 64-bit) |
| uv | 0.9.16 |
| pytest | 8.4.2 |
| ruff | 0.16.4 |
| mypy | 2.3.1 |
| Cluster | none |
| Network | not used by any check recorded here |

Every dependency version came from the committed [`uv.lock`](../../../uv.lock) by way
of `--locked`, which fails rather than re-resolving. A run whose inputs were resolved
fresh measures the package index as much as it measures the repository.

## Method

The commands, in the order they were run:

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m mypy
uv run --locked python -m pytest -q
uv run --locked python -m pytest -m adapter -q
uv run --locked python -m pytest tests/adapters -q
uv run --locked python -m pytest tests/domain -q
uv run --locked python -m pytest tests/architecture -q
uv run --locked python -m pytest tests/testing -q
uv run --locked python -m pytest tests/contracts -q
git diff --check main...HEAD
```

`ruff check` reported five findings on the first attempt — four Yoda comparisons and
one nested conditional, all in the new adapter suite — and `ruff format` reformatted
two new files. Both were corrected before the results below, and the sequence is
recorded because a record that lists only the passing run describes a result rather
than a method.

## Results

| Check | Result |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 119 files already formatted |
| `python -m mypy` | Success: no issues found in 42 source files |
| `python -m pytest -q` | 3032 passed, 25 skipped |
| `python -m pytest -m adapter -q` | 76 passed, 2981 deselected |
| `python -m pytest tests/adapters -q` | 76 passed |
| `python -m pytest tests/domain -q` | 398 passed, 18 skipped |
| `python -m pytest tests/architecture -q` | 394 passed |
| `python -m pytest tests/testing -q` | 498 passed |
| `python -m pytest tests/contracts -q` | 191 passed, 7 skipped |
| `git diff --check main...HEAD` | no output |

The 18 domain skips and the 7 contract skips are the pre-existing structural-layer
fixture skips this change does not touch.

### The mock identifying itself

Produced by constructing the adapter and calling it, on the host above. Request
identifiers are illustrative values supplied by the caller, not values the adapter
invented:

```json
{
  "telemetryIdentity": {
    "inferops.runtime.id": "inferops-mock-serving",
    "inferops.capability.id": "inferops-mock-serving",
    "inferops.model.id": "mock-fixed-fixture"
  },
  "mockIdentity": {
    "isMock": true,
    "notice": "Deterministic mock fixture. No model produced this. It is not evidence of real serving behaviour, latency, token accounting, or model quality.",
    "boundaryRule": "docs/serving/mock-and-real-boundary.md",
    "adapterKind": "mock",
    "runtimeId": "inferops-mock-serving",
    "determinism": "fixed-fixture",
    "fixtureRef": "contracts/workload/fixtures/mock-llm-chat-completion.response.json",
    "evidenceClass": "mock",
    "maxCertification": "C1"
  }
}
```

All three telemetry keys are attributes the committed
[telemetry catalog](../../telemetry/telemetry-catalog.md) already publishes, and each
is permitted in a log field and in an evidence field. The adapter suite asserts that
membership against the catalog rather than against a list it wrote itself.

### One successful response

```json
{
  "content": "This is a deterministic InferOps mock fixture, not model output.",
  "model": "mock-fixed-fixture",
  "adapterKind": "mock",
  "usage": null,
  "finishReason": "stop"
}
```

`usage` is absent rather than zero. A real runtime's token counts come from its own
tokeniser; a mock's would be numbers its author chose, so token counting is declared
an unsupported capability and no number is produced.

### One injected failure

Scenario `rate-limited`, with the telemetry mapping the adapter reports alongside it:

```json
{
  "errorCode": "rate-limited",
  "tokenUsage": false,
  "platformMetricIds": []
}
```

```json
{
  "code": "rate-limited",
  "message": "injected mock scenario",
  "requestId": "req-example-0001",
  "correlationId": "corr-example-0002"
}
```

The message names the condition and quotes nothing from the request. The correlation
identifiers are the ones the caller supplied. `platformMetricIds` is empty because
ADR 0002 leaves the request counter to InferOps, and an adapter reporting it would be
the platform reading its own number back.

### The failure matrix

| Scenario | Error raised | Code carried | Readiness |
|---|---|---|---|
| `success` | none | none | true |
| `model-not-ready` | `ModelNotReadyError` | `model-not-ready` | false |
| `request-timeout` | `RequestTimeoutError` | `request-timeout` | true |
| `upstream-timeout` | `UpstreamTimeoutError` | `upstream-timeout` | true |
| `rate-limited` | `RateLimitedError` | `rate-limited` | true |
| `internal-error` | `InternalError` | `internal-error` | true |

Each row is a parameterised test asserting the error type, the code, the preserved
request context, and that the message repeats nothing from the prompt.

### Safeguards asserted

| Safeguard | How it is enforced |
|---|---|
| A result cannot claim to be real | `adapter_kind` is a constant `mock`, from a vocabulary the domain validates |
| A transcript cannot name a real model | `initialize()` refuses a model identity that is not mock-labelled, and the refusal repeats no value |
| Token figures cannot be invented | `token-counting` is declared unsupported; `usage` is always `None` |
| A model revision cannot be invented | `get_model_metadata()` reports no revision |
| The mock cannot nominate its own strength | The declared evidence class and ceiling are asserted against the committed strategy data |
| A `C2` claim cannot rest on this layer alone | Asserted from the strategy: every claim citing `adapter` above `C1` also cites a layer that loads a model |
| No credential or network reaches it | The module's imports and names are read from its parse tree; no socket, environment read, or file access appears |

## Limitations

- **It establishes nothing about a serving runtime.** Every property that makes real
  serving hard lives outside the response body: model load, resident memory, token
  accounting, decode rate, weights, and the failure modes a real process actually
  produces. A mock has none of them.
- **It is not a latency, throughput, or capacity result.** The adapter's latency is a
  setting. No figure here was measured, and V1 publishes none from any source.
- **The failure scenarios are anticipated, not observed.** They prove that the
  canonical error a caller must handle is reachable and correctly shaped. They do not
  prove the selected runtime produces the condition, or produces it this way. That is
  the `failure-and-resilience` layer, which has no code and runs on a capable host.
- **`capability-unavailable` is not exercised.** V1's protocol has no
  optional-capability call site to fail: streaming is not a method, and absent token
  usage is `None` rather than an error. Injecting it would mean inventing a call in
  order to fail it.
- **One host, one operating system, one Python.** Nothing here depends on a clock, a
  random source, the network, or the file system from inside the distribution, so the
  result should reproduce anywhere the lockfile installs — but it has been run on one
  machine, and that is what this record says.
- **No scanner ran.** No secret scanner, image scanner, or dependency auditor was
  executed for this change; the diff was inspected by eye and by
  `git diff --check`.

## Authorisation

Not required. Every command above runs from a checkout on a contributor's own
machine, downloads no model, allocates no paid capacity, provisions nothing, and
touches no cluster.

## Related records

- [The deterministic mock serving adapter](../../serving/mock-serving-adapter.md) —
  what it is, what it declares, and what it cannot support.
- [The mock and real serving boundary](../../serving/mock-and-real-boundary.md) — the
  accepted rule.
- [Certification levels and evidence classes](../../testing/certification.md) — why
  this record stops at `C1`.
- [The test and CI strategy](../../testing/test-strategy.md) — the `adapter` layer,
  its lane, and its marker.
- [V1-S1-002-PR1 cumulative review fixes](v1-s1-002-pr1-cumulative-review-fixes.md) —
  the contract this adapter implements.
