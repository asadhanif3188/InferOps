# Configuring and inspecting the selected runtime

Status: **implemented**, in [`src/inferops/adapters/llama_cpp/`](../../src/inferops/adapters/llama_cpp/).
It is the configuration and inspection half of connecting InferOps to the runtime
[ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md)
selected. The other half — the transport seam, the inference client, the bounded
deadlines, the canonical error mapping, and the `ServingAdapter` implementation —
arrived with `V1-S1-004-PR2` and is described in
[executing real inference through the adapter](real-runtime-inference.md). This
document covers the six modules that adapter composes.

Everything here is derived from two accepted records — the runtime decision and
[the feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md)
that executed it. Nothing in *these six modules* has run a model, opened a socket,
or read a file, and their own evidence class is `local-static`.

## What it is

Six modules, each with one job, all of them holding the runtime's vocabulary
inside a package that the platform domain does not import.

| Module | What it holds |
|---|---|
| `pins.py` | The runtime image digest, and the model repository, revision, file, size, and published hash |
| `settings.py` | The operator-supplied runtime settings, their environment variables, and the refusals |
| `configuration.py` | Platform configuration translated into runtime configuration, and a workload document checked against the pins |
| `readiness.py` | The health-status mapping, and a readiness that is false until an observation makes it true |
| `metadata.py` | What the runtime says about itself, read narrowly |
| `capabilities.py` | What the runtime supports, declared with the basis for each entry |

## What was deliberately absent, and what has since arrived

**The `ServingAdapter` implementation was withheld from the first half**, on the
ground that a class satisfying the protocol's shape while its `infer` could not
generate anything would be a mock wearing a real adapter's name — and boundary
rule 4 in [the mock and real boundary](mock-and-real-boundary.md) is explicit that
substituting a mock result for a missing real one is a defect and not a fallback.
It arrived with `V1-S1-004-PR2`, together with the inference client, the timeouts,
and the runtime-error mapping. What has still **not** arrived is the executed
record of one real generated response: the `real-runtime` lane is manual and
authorization-gated and has not been entered for this adapter, and that record —
not this document and not that code — is what supports the story's remaining
criterion.

**The inference path was absent for the same reason and is published now.**
`/v1/chat/completions` was not among the runtime paths `settings.py` would build a
URL for while nothing issued the call; the door was not put in the wall before the
room existed. The room exists, so the set of published paths grew from four to
five and a test asserts it is exactly those five.

**The generic adapter has no default for anything ADR 0002 left undecided.** The context length,
the KV budget, the concurrency limit, and the sampling defaults are recorded there
as undecided, and the 4096 context and 6 threads the trial ran were stated inputs
so its numbers could be interpreted rather than recommended values. So the context
size and the thread count are required inputs with no default: an operator
supplies them and owns them. A default written here would be read back later as a
project recommendation nobody made. The later
[local runtime profile](local-runtime-profile.md) now supplies one explicit,
versioned set of local values. That is a deployment selection passed into this
adapter, not a fallback hidden inside it.

## The pins, and what a pin is worth

| | |
|---|---|
| Runtime | llama.cpp `llama-server`, `ghcr.io/ggml-org/llama.cpp`, pinned by index digest |
| Model | `Qwen/Qwen3-1.7B-GGUF`, pinned by revision, file name, byte size, and published SHA-256 |
| Artifact format | `gguf`, the only format this runtime loads without a conversion step |
| Registered as | `llama-cpp-server`, in [the compatibility matrix](../../contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json) |
| Serving capability | `inferops-native-serving` |
| Adapter kind | `real` |

Every one of those values is copied from an accepted record, and
`tests/adapters/test_llama_server_pins.py` reads the record and fails when a copy
drifts. That is the only part of the question a repository-only check can answer:
it establishes that the decision and the code say the same thing, **not** that the
pinned bytes are the right ones.

**Holding a hash is not having verified one.** What ties a running process to the
pinned bytes is the SHA-256 computed on the file before it was ever mounted, the
file being mounted read-only, and the runtime's self-reported parameter count and
quantisation agreeing with the published model. The runtime exposes no hash of the
file it loaded, so no single check closes that gap — which is worth knowing rather
than worth hiding.

## Configuration, in both directions

**Downwards.** An `AdapterConfiguration` — model identity, request timeout, an
optional generation bound — is joined to the operator's settings and to the pins.
Three things are refused: a mock-labelled model identity, a generation bound
larger than the context the runtime was started with, and a weight file that is
not the pinned one.

The mock-labelled refusal is the mirror of the mock adapter refusing a real model
identity. Together they mean a transcript cannot name the wrong kind of provider
in either direction — and that mutual guarantee holds only while both adapters
look for the same prefix, so `tests/adapters/test_llama_server_agreement.py`
compares the two copies rather than trusting them. Neither adapter may import the
other, so a compared copy is what a shared constant would otherwise be.

This side matches the prefix case-insensitively while the mock matches it exactly.
The asymmetry is deliberate: the mock *requires* the prefix, so a strict match is
the safe direction there, and this one *refuses* it, so the permissive match is the
safe direction here.

**Upwards.** A `WorkloadContract` naming this runtime is checked against the pins
before anything acts on it: the profile, the serving capability, the image
digest, and every field of the model artifact. ADR 0002 records that this
publisher ships from a branch tip with **no versioned tag scheme** and rebuilds
its moving tag on a schedule, which is exactly the situation in which the digest
in a document and the digest that is running drift apart quietly.

A refusal carries the field path the contract publishes, the constraint that was
not met, and the caller's correlation identifiers. **It never repeats the value it
refused**, which is asserted directly: a mismatch is the most tempting place to
print both sides, and a workload document is a place a reader's own names appear.

### The arguments it generates

`model_serving_arguments()` produces `--model`, `--alias`, `--ctx-size`,
`--threads`, and `--metrics` when metrics are enabled. It generates **no bind
address and no port**: where the runtime listens is a property of the deployment
that runs it, and deriving a server's binding from the address its client dials
is a coincidence in the trial manifest rather than a rule. It generates **no
sampling parameter**, for the reason above.

The [local runtime profile](local-runtime-profile.md) completes the command with
the bind address and port, one-slot concurrency, and generation defaults. Its
offline validator reconstructs the adapter environment and refuses a profile
that this package cannot parse, which keeps the deployment selection compatible
without moving deployment concerns into the generic adapter.

## Required configuration

| Variable | Required | What it is |
|---|---|---|
| `INFEROPS_LLAMA_SERVER_ENDPOINT` | yes | Base URL of the runtime. No path, query, fragment, or credentials |
| `INFEROPS_LLAMA_SERVER_MODEL_PATH` | yes | Absolute path of the `.gguf` file **inside the serving container** |
| `INFEROPS_LLAMA_SERVER_MODEL_ALIAS` | yes | The label the runtime is started with and echoes back |
| `INFEROPS_LLAMA_SERVER_CONTEXT_SIZE` | yes | Context length. No default; ADR 0002 decides none |
| `INFEROPS_LLAMA_SERVER_THREADS` | yes | Thread count. No default; ADR 0002 decides none |
| `INFEROPS_LLAMA_SERVER_STARTUP_BUDGET_MS` | yes | How long the model may take to become ready |
| `INFEROPS_LLAMA_SERVER_METRICS_ENABLED` | no | Whether the runtime exposes its own metrics endpoint. Defaults to on |

None of these carries a credential, and the endpoint is refused outright if it
tries to: a credential in a URL is a credential in every line that logs the URL.
The model path is a container path and never a contributor's own path, which is
the difference between a value that can be committed and one that cannot.

The endpoint must also contain no `?`, `#`, or backslash — **including an empty
query or fragment**. An empty delimiter passes every structural check while still
capturing the path this adapter appends: `http://host?` plus `/health` is a
request for `/` carrying `/health` as its query string, which is a readiness probe
aimed at the wrong resource and a silent one. A backslash is refused because
`urlsplit` leaves it inside the authority while some HTTP clients read it as a
separator, and a value two parsers disagree about is one neither should be trusted
on. The URL a runtime path is appended to is rebuilt from the parsed scheme and
authority rather than trimmed from the string supplied, so what survives a check
cannot survive into a request.

`metrics_enabled` is the one setting with a default, and the default is on
because ADR 0002's `T7` exception is argued on the runtime exposing its own
metrics with no exporter and no sidecar. Turning it off is the deviation, so
turning it off is what has to be written down.

**These six are read only when a deployment selects this adapter.**
`INFEROPS_SERVING_ADAPTER=real` is what makes the InferOps API compose it, and
[the API document](inference-api.md#the-variables) publishes that variable and the
three beside it. Two properties of that selection matter here: the selection is
required and has no default, and a `real` selection whose settings above are
missing or malformed is **refused rather than answered with a mock** — which is
boundary rule 4 held at the one place a deployment is assembled.

## Readiness

The runtime's health endpoint returns **503 while the model loads** and **200
once it can answer**. That behaviour is the single most consequential thing the
Sprint 0 trial found, and no mock could have surfaced it: it is correct readiness
reporting and wrong liveness reporting, so a liveness probe aimed at it restarts
the pod mid-load and never converges.

| Observation | State | Ready |
|---|---|---|
| nothing yet | `not-probed` | no |
| `503` | `loading` | no |
| `200` | `ready` | **yes** |
| any other status | `unexpected-status` | no |
| no answer at all | `unreachable` | no |

**Readiness is false until the runtime has said otherwise.** A tracker starts in
`not-probed`, only an observed `200` moves it to `ready`, there is no setter, and
a subsequent `503` takes readiness away again — because a replaced pod is a fresh
process with a fresh load, and a tracker that latched `ready` would keep sending
requests to a runtime that has just said it cannot serve them.

An unrecognised status is *not* folded into `loading`. Treating an unknown answer
as a temporary one is how a permanently broken runtime gets waited on forever.

Every not-ready state produces the canonical `model-not-ready` error, carrying
the caller's correlation identifiers and neither the status code nor the
endpoint.

## Metadata, and the line an observation may not cross

`/v1/models` echoes the alias the process was started with; `/props` describes
the process and the file it loaded. The feasibility record is explicit about what
that echo is worth:

> The `id` is the alias this trial passed on the command line, so the runtime
> echoing it proves the flag was accepted and nothing more.

So an observation is never promoted into a pin:

- the **model identifier** reported through the domain's `ModelMetadata` is the
  platform's, not the runtime's alias. They are different strings by construction
  — the contract's model reference is kebab-case, the runtime's alias is whatever
  the operator passed — and `identity_disagreements()` is where the question of
  whether they still describe the same thing is asked;
- the **model revision** is the configured pin. The runtime attests no revision,
  so no response can supply one;
- the **runtime version** is the build string the process reported when it
  reported one, and the pinned image digest when it did not. Both identify real
  bytes; neither is invented;
- the container path in `/props` is reduced to the file's own name and the
  directory is discarded. A value this adapter does not keep is a value it cannot
  leak into a log line or an evidence record.

**The exact JSON shape of these two responses was not captured verbatim by the
trial** — what the record preserves is the field names and their values. The
parsers therefore read a small number of members, treat an absent one as absence,
and refuse a payload whose shape they cannot read rather than guessing at it.
Confirming the shape against a live runtime belongs to the change that first
issues these calls. `V1-S1-004-PR2` added the code that issues them; the
`real-runtime` lane it would be confirmed in has not been entered, so the shape
is still inferred rather than observed.

## Capabilities

| Capability | Supported | Basis |
|---|---|---|
| `streaming` | no | V1's protocol publishes no streaming method. A statement about the contract, not the runtime |
| `token-counting` | yes | The runtime derives counts from its own tokeniser and returned them in the trial |
| `real-model-inference` | yes | The pinned pair answered inference requests in a cluster during the trial |
| `deterministic-fixture-replay` | no | Replaying a fixture is the mock's capability, and the two stay apart |

**A supported capability cites a committed record; an unsupported one cites
none.** Declaring an absence needs no evidence and declaring a presence does, and
a test enforces both directions. Every supported entry rests on the Sprint 0
trial, which is the only record this project has that observed the runtime at
all.

A declaration is not an execution. These say what the runtime and model can do;
whether this project's adapter reaches it is a different question with a
different record.

## What is checked, and where

```sh
uv run --locked python -m pytest tests/adapters -q      # this package
uv run --locked python -m pytest tests/architecture -q  # the dependency rule
uv run --locked python -m mypy
```

The adapter layer runs in the default lane. Every check reads files from this
repository and objects from this distribution — no network, no cluster, no model,
no credential, no clock, no randomness — and the pins, capabilities, and status
mappings are compared against the committed records they were copied from rather
than against constants the same suite wrote.

The architecture suite is the one that enforces the isolation: it parses every
module under `src/inferops/` and fails if one imports anything outside the
standard library and this distribution, which covers this package as fully as it
covers the domain.

## What this document does not do

It does not claim that InferOps ships a network service. Nothing in this
repository listens on a port as a shipped API service. The adapter that can issue
the call is described in
[executing real inference through the adapter](real-runtime-inference.md). The
original change did not run it; the later
[Sprint 1 closure run](../proof/serving/v1-s1-real-runtime-closure.md) did, through
the adapter and in-process API against the local Kubernetes runtime. It does not amend
[the mock and real boundary](mock-and-real-boundary.md), which is an accepted
rule and older than this package. It does not certify the runtime: the executed
record that does is the Sprint 0 feasibility trial, and its scope is one Windows
host on one day.

## Related records

- [ADR 0002, model and serving runtime](../architecture/decisions/ADR-0002-model-and-serving-runtime.md) — the decision every pin is copied from.
- [The V1-S0-003-PR2 feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) — the trial that executed it.
- [The mock and real serving boundary](mock-and-real-boundary.md) — the rule that says a mock may not stand in for what is missing here.
- [The deterministic mock serving adapter](mock-serving-adapter.md) — the other side of the same pairing.
- [ADR 0004, component and ownership boundaries](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md) — the dependency rule this package's isolation obeys.
- [The V1-S1-004-PR1 validation record](../proof/serving/v1-s1-004-pr1-validation.md) — what was run, and what it did not establish.
- [Executing real inference through the adapter](real-runtime-inference.md) — the second half, which composes these six modules.
