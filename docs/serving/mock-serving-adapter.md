# The deterministic mock serving adapter

Status: **implemented**, in [`src/inferops/adapters/`](../../src/inferops/adapters/),
and CI only. It exists so that the serving contract is exercised on every change on a
machine with no model, no container engine, no cluster, and no network. It certifies
nothing about a serving runtime, and this document is as much about that half as
about the first.

The rule it lives under is [the mock and real serving boundary](mock-and-real-boundary.md),
which is accepted and older than this adapter. Nothing here amends it.

## What it is

One implementation of the `ServingAdapter` protocol the platform domain owns. It
replays [one committed response fixture](../../contracts/workload/fixtures/mock-llm-chat-completion.response.json),
answers the same way every time, and reaches nothing outside its own process.

| | |
|---|---|
| Adapter kind | `mock` |
| Runtime identity | `inferops-mock-serving`, the row [the compatibility matrix](../../contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json) publishes |
| Serving capability | `inferops-mock-serving` |
| Determinism | `fixed-fixture` |
| Model artifact | none, of any format |
| Network, credential, container engine, cluster | none required, and none used |
| Evidence class | `mock` |
| Certification ceiling | `C1` — see [the certification levels](../testing/certification.md) |

The workload side of the same pairing is
[the `mock-llm` example](../../contracts/workload/examples/valid/mock-llm-ci.yaml):
the schema pins that profile to the `ci` environment, to the `inferops-mock-serving`
capability, to `fixed-fixture` determinism, and to zero proof references. The adapter
is the half that answers.

## How normal CI selects it

The default lane is pytest with no marker expression, and the adapter layer is inside
it:

```sh
python -m pytest -q             # the default lane, which now includes the mock
python -m pytest -m adapter -q  # the adapter layer alone
```

Nothing selects the mock in preference to a real runtime, because there is no real
adapter to prefer it over: the adapter for the runtime ADR 0002 selected is not
written. When it exists, the composition point chooses one — see
[the component boundaries](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
— and the rule that governs the choice is already fixed: a mock may never be the
default in the mandatory serving path.

## What it declares

Capabilities are declared, never assumed, and two of the four are declarations of
absence:

| Capability | Supported | Why |
|---|---|---|
| `streaming` | no | V1's protocol is synchronous and has no streaming method at all |
| `token-counting` | no | A real runtime's counts come from its own tokeniser. A mock's would be numbers its author chose |
| `deterministic-fixture-replay` | yes | What it actually does |
| `real-model-inference` | no | The capability layer saying what `adapter_kind` says |

`usage` on a result is therefore always absent rather than zero, and
`get_model_metadata()` reports no revision: there is no model, so there is no
revision, and absence is what the domain publishes for a value that was not provided.

## Failure injection

Each canonical error a caller has to handle is reachable by construction. The
scenario's value **is** the error code, so the two cannot drift apart — there is only
one string.

| Scenario | Error raised | Canonical code |
|---|---|---|
| `success` | none | none |
| `model-not-ready` | `ModelNotReadyError` | `model-not-ready` |
| `request-timeout` | `RequestTimeoutError` | `request-timeout` |
| `upstream-timeout` | `UpstreamTimeoutError` | `upstream-timeout` |
| `rate-limited` | `RateLimitedError` | `rate-limited` |
| `internal-error` | `InternalError` | `internal-error` |

The `model-not-ready` scenario makes readiness false as well as making inference
raise. An adapter that reports itself ready and then refuses every request is a state
no runtime produces and no caller should be written against.

`capability-unavailable` is deliberately not injectable. It is raised when a caller
asks for a capability an adapter does not support, and V1's protocol has no
optional-capability call to make: streaming is not a method, and absent token usage is
`None` rather than a failure. Injecting it would mean inventing a call site in order
to fail it.

Latency is a setting, applied by sleeping for it, and it defaults to zero. It is an
input to a test and never an observation. One rule connects it to the platform
configuration: a configured latency that reaches the configured request timeout
produces `request-timeout` — checked before the sleep rather than after, because a
mock that burns the whole timeout to report one makes the default lane slower for
nothing.

## What it cannot support

This is the half that matters most, and it is mechanical rather than advisory.

- **It cannot certify real serving behaviour.** Its evidence class is `mock`, whose
  ceiling is `C1`. No configuration of it reaches `C2`. The ceiling lives in
  [the committed strategy data](../testing/test-strategy.v1alpha1.json), and the
  adapter suite asserts the adapter's declared class and ceiling against it rather
  than restating them.
- **It cannot be configured with a real model identity.** `initialize()` refuses a
  model identifier that is not mock-labelled, and refuses it before a result exists to
  carry it. A transcript naming the model in ADR 0002 is exactly the artifact somebody
  later cites as real-runtime evidence.
- **It cannot report token counts**, so no record it contributes to can carry a token
  figure that came from nowhere.
- **It cannot support a latency, throughput, or capacity figure.** V1 publishes none
  of those from any source; a mock could not support one in any case, because the
  number would be the one somebody typed into the settings.
- **It says nothing about model quality**, and the fixture says so in its own
  contents.

The reason none of this is fixed by making the mock better is in
[the boundary document](mock-and-real-boundary.md): certification asks whether the
contract matches reality, and a mock is built from the contract. Pointing one at the
other tests the author's understanding against itself.

## How the label survives being copied

Boundary rule 6 requires a mock artifact to be identifiable from its own contents
rather than from the directory it sits in. Four places carry the label:

1. every result declares `adapter_kind: mock`, from a closed vocabulary the domain
   validates;
2. runtime metadata names `inferops-mock-serving`, the registered runtime identity;
3. `telemetry_identity()` carries `inferops.runtime.id`, `inferops.capability.id`, and
   `inferops.model.id` — attributes [the telemetry catalog](../telemetry/telemetry-catalog.md)
   already publishes, permitted in a log field and in an evidence field. The catalog's
   own note on `inferops.runtime.id` is the mechanism being used: the registered
   runtime identifier includes the mock runtime, which is how a mock result stays
   visibly a mock result;
4. `mock_identity()` returns the same self-describing block the committed fixture
   carries, notice and boundary-rule reference included.

## What is checked, and where

Everything above is a test in [`tests/adapters/`](../../tests/adapters/), run in the
default lane. The conformance half is inherited from the shared suite rather than
copied, so the mock is held to the same assertions as the in-memory double and any
adapter written later. The commands are in [CONTRIBUTING](../../CONTRIBUTING.md), and
the run behind this document is
[the validation record](../proof/serving/v1-s1-003-pr1-validation.md).

## What this document does not do

- It does not authorise a mock result to stand in for a real one anywhere. Where a
  real record does not exist, the correct output is an unmet criterion and a recorded
  blocker.
- It does not describe the platform API. Nothing in this repository listens on a port
  or answers a request; the shape a caller will eventually see is
  [the inference API surface](inference-api-surface.md), which is a decision rather
  than an interface.
- It does not describe the real adapter, which does not exist.

## Related records

- [The mock and real serving boundary](mock-and-real-boundary.md) — the accepted rule.
- [Certification levels and evidence classes](../testing/certification.md) — why a
  mock stops at `C1`.
- [The test and CI strategy](../testing/test-strategy.md) — the layer, the lane, and
  the marker.
- [The WorkloadContract](../contracts/workload-contract.md) — the `mock-llm` profile
  and what the schema pins about it.
- [ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md) — the
  runtime the real adapter will implement, and the request counter InferOps owns
  because that runtime exposes none.
