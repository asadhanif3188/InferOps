# V1-S1-004-PR1 — real runtime configuration, change validation

The record behind
[the runtime configuration package](../../serving/real-runtime-configuration.md).
It records what was run, on what, and what it may be used to claim — which is a
good deal less than a reader skimming a green test session might assume, because
**nothing in this change touched the runtime it configures**. The
[limitations](#limitations) section is the part that says so.

## Classification

| | |
|---|---|
| Evidence class | `local-static` for every check here |
| Ceiling | `C0` |
| What ran | The committed test suites, the linter, the formatter, and the type checker, from a checkout |
| What did not run | Any real model, runtime image, container engine, cluster, network call, inference request, paid service, or scanner |
| Claims certified by this record | none |

`local-static` is the weakest label these checks support and it is the correct
one. Every assertion compares a value in this repository against another value in
this repository. Nothing observed a runtime, and the runtime facts this package
encodes — the health status codes, the build string, the token counts — are
*copied* from
[the Sprint 0 feasibility record](v1-s0-003-pr2-runtime-feasibility.md), whose
evidence class is that record's and not this one's.

**One imprecision is recorded rather than hidden.** The suites added here live
under `tests/adapters/`, whose layer carries the evidence class `mock` and a `C1`
ceiling in
[the committed strategy](../../testing/test-strategy.v1alpha1.json). These checks
produce `local-static` results, which is weaker than that ceiling, and the
vocabulary rule is to pick the weakest label the record supports — so this record
says `local-static` and `C0`. The layer's ceiling is a maximum and not a claim,
and nothing here approaches it. Whether the `adapter` layer should carry more than
one evidence class is a question for the change that adds the real adapter, and it
is listed under [deferred work](#deferred-work) rather than settled in passing.

**No claim moves to `certified` in this change**, and no layer changes status.
The claims this work sits under — `a-model-that-is-not-ready-is-a-canonical-error`
and `the-platform-serves-a-workload-the-contract-describes` — both require a
capable host and a real model, and both stay `planned`.

## Provenance

| Input | Value |
|---|---|
| Repository revision at branch point | `0dbfea3` |
| Branch | `feat/v1-s1-004-real-runtime-configuration` |
| Distribution code added | `src/inferops/adapters/llama_cpp/` |
| Tests added | `tests/adapters/test_llama_server_*.py` |
| Records the pins were copied from | [ADR 0002](../../architecture/decisions/ADR-0002-model-and-serving-runtime.md), [the feasibility record](v1-s0-003-pr2-runtime-feasibility.md), [the compatibility matrix](../../../contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json) |
| Workload fixture read | [`synchronous-llm-local.yaml`](../../../contracts/workload/examples/valid/synchronous-llm-local.yaml) |
| Model artifact | none. No weight file was downloaded, mounted, hashed, or read |
| Container image | none. No image was pulled, inspected, or run |
| Cluster | none |

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
| Network | not used by any check recorded here |

Every dependency version came from the committed [`uv.lock`](../../../uv.lock) by
way of `--locked`, which fails rather than re-resolving.

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
uv run --locked python -m pytest tests/security -q
uv run --locked python -m pytest tests/serving -q
git diff --check
```

`ruff check` reported seven findings on the first attempt — all Yoda comparisons
in the new suites, where an assertion compared a module constant against a value
read from a committed file — and `ruff format` reformatted four files. Both were
corrected before the results below. The sequence is recorded because a record that
lists only the passing run describes a result rather than a method.

## Results

| Check | Result |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 134 files already formatted |
| `python -m mypy` | Success: no issues found in 55 source files |
| `python -m pytest -q` | 3245 passed, 25 skipped |
| `python -m pytest -m adapter -q` | 273 passed, 2997 deselected |
| `python -m pytest tests/adapters -q` | 273 passed |
| `python -m pytest tests/domain -q` | 398 passed, 18 skipped |
| `python -m pytest tests/architecture -q` | 408 passed |
| `python -m pytest tests/testing -q` | 498 passed |
| `python -m pytest tests/contracts -q` | 191 passed, 7 skipped |
| `python -m pytest tests/security -q` | 597 passed |
| `python -m pytest tests/serving -q` | 184 passed |
| `git diff --check` | no output |

The adapter layer grew from 76 checks to 273. The architecture suite grew from 394
to 408 because it parametrises over every module under `src/inferops/`, and this
change added seven.

## What the added checks establish

### The pins agree with the records that decided them

| Value | Compared against |
|---|---|
| Runtime image repository and index digest | The executed pair in the compatibility matrix, and ADR 0002's own text |
| Registered runtime identifier, name, serving capability, status | The matrix row for `llama-cpp-server` |
| Model repository, revision, file, size, published SHA-256 | The executed pair, ADR 0002, and the committed `synchronous-llm` example, field by field |
| Artifact format | The formats the matrix says this runtime accepts |
| Adapter kind `real` | The closed vocabulary the domain publishes |
| The observed build string | The feasibility record that observed it |

This establishes that the decision and the code say the same thing. It establishes
**nothing** about whether the pinned bytes are the right ones; no repository-only
check can.

### Readiness is false until an observation makes it true

| Situation | Readiness |
|---|---|
| A newly constructed tracker | false |
| After an observed `503` | false |
| After an observed status the mapping does not publish | false |
| After the runtime could not be reached | false |
| After `reset()` | false |
| After an observed `200` | **true** |
| After an observed `200` followed by a `503` | false |

There is no setter and no way to assert a state; every entry point records an
observation. An unrecognised status is `unexpected-status` rather than `loading`,
because treating an unknown answer as temporary is how a permanently broken
runtime gets waited on forever.

### Safeguards asserted

| Safeguard | How it is enforced |
|---|---|
| An endpoint cannot carry a credential | Userinfo in the URL is refused at construction, and the refusal repeats no part of the value |
| A refusal cannot leak a document's contents | Asserted directly against a secret-shaped endpoint and against a workload document field |
| A real path cannot serve a mock identity | Both the runtime alias and the platform model identity are refused when mock-labelled |
| A number ADR 0002 left undecided cannot acquire a default | Omitting the context size, the thread count, or the startup budget is a refusal naming the variable |
| An unreadable boolean cannot silently disable metrics | Refused rather than read as `false` |
| The URL builder cannot be aimed anywhere | Only the four published runtime paths build a URL; the inference path is asserted absent |
| A runtime's answer cannot become a pin | The reported revision is the configured pin; a `revision` member in a response reaches nothing |
| A container path cannot reach a record | `/props` is reduced to the weight file's own name and the directory is discarded |
| A supported capability cannot be declared without a record | Every supported entry cites a committed record and every unsupported one cites none |
| A document naming different bytes cannot be served | Six fields of the committed example are mutated one at a time and each refusal names its own field path |

### Isolation

The architecture suite parses every module under `src/inferops/` and fails on any
import outside the standard library and this distribution. It covers the seven new
modules exactly as it covers the domain, so the runtime's vocabulary staying
inside its own package is checked rather than reviewed. No module in the package
opens a file, reads an environment variable of the running process, or constructs
a socket: the environment is passed in as a mapping, and the payloads the metadata
parsers read are supplied by their caller.

## Limitations

- **It establishes nothing about the runtime.** No image was pulled, no model was
  downloaded or hashed, no process was started, no port was opened, and no request
  was issued. Every runtime fact encoded here was copied from a record produced in
  Sprint 0 on one Windows host on one day.
- **No inference was executed, and none was attempted.** The acceptance criterion
  requiring one real generated response through the adapter is **not met by this
  change** and is not claimed to be. It belongs to the pull request that adds the
  inference client.
- **There is no serving adapter.** This package implements no
  `ServingAdapter`, so the conformance suite does not run against it and cannot.
  What is checked is the configuration and inspection layer that adapter will
  compose.
- **The `/props` and `/v1/models` payload shapes are inferred, not observed.** The
  feasibility record preserves the field names and values it read, not the JSON
  envelope around them. The parsers read a small number of members and refuse a
  shape they cannot read, but a live response could still disagree with the shape
  assumed here. Confirming it is the first task of the change that issues these
  calls.
- **The health-status mapping rests on two observed codes.** `503` during load was
  captured once, from the control plane, on the first start of the trial; `200`
  when ready is the steady state that trial ran in. Any other status is mapped to
  `unexpected-status` by construction rather than by observation, because nothing
  else was ever seen.
- **Timeout and runtime-failure mapping are absent.** Only `model-not-ready`, and
  only as it arises from readiness, is produced here. `request-timeout`,
  `upstream-timeout`, and the mapping of an arbitrary runtime failure to
  `internal-error` require a call to fail, and there is no call.
- **The environment variable names are introduced by this change and have no
  consumer.** Nothing reads them yet, and no deployment manifest sets them.
- **One host, one operating system, one Python.** Nothing here depends on a clock,
  a random source, the network, or the file system from inside the distribution,
  so the result should reproduce anywhere the lockfile installs — but it has been
  run on one machine, and that is what this record says.
- **No scanner ran.** No secret scanner, image scanner, or dependency auditor was
  executed for this change; the diff was inspected by eye and by
  `git diff --check`.

## Deferred work

- The `ServingAdapter` implementation, the inference client, the request timeout,
  the runtime-error mapping, and the executed record of one real generated
  response.
- Confirming the `/props` and `/v1/models` response shapes against a live runtime.
- A serving deployment that sets these environment variables, and the manifest
  that carries the argument list this package generates.
- Whether the `adapter` test layer should distinguish `local-static` checks from
  `mock` ones. It carries one evidence class today; this change added checks that
  are weaker than that class, and the question is worth answering when the real
  adapter's own suite arrives beside them.

## Authorisation

Not required, and none was sought. Every command above runs from a checkout on a
contributor's own machine, downloads no model, allocates no paid capacity,
provisions nothing, and touches no cluster. The `real-runtime` lane is manual and
authorization-gated and **was not entered**.

## Related records

- [Configuring and inspecting the selected runtime](../../serving/real-runtime-configuration.md) —
  what the package is, and what it deliberately is not.
- [ADR 0002, model and serving runtime](../../architecture/decisions/ADR-0002-model-and-serving-runtime.md) —
  the decision every pin is copied from.
- [The V1-S0-003-PR2 feasibility record](v1-s0-003-pr2-runtime-feasibility.md) —
  the only record in this project that observed the runtime.
- [The mock and real serving boundary](../../serving/mock-and-real-boundary.md) —
  the rule that makes a missing real record an unmet criterion rather than an
  opportunity for a mock.
- [Certification levels and evidence classes](../../testing/certification.md) — why
  this record stops at `C0`.
- [V1-S1-003-PR1 validation](v1-s1-003-pr1-validation.md) — the mock adapter, the
  other half of the same pairing.
