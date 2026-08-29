# V1-S1-004-PR2 — real runtime inference, change validation

The record behind
[the inference half of the runtime adapter](../../serving/real-runtime-inference.md).
It records what was run, on what, and what it may be used to claim — which is
again less than a reader skimming a green test session would assume, because
**this change did not run the runtime it now knows how to call**. The
[limitations](#limitations) section and the
[acceptance criteria](#acceptance-criteria) section are the parts that say so.

## Classification

| | |
|---|---|
| Evidence class | `local-static` for every check here |
| Ceiling | `C0` |
| What ran | The committed test suites, the linter, the formatter, and the type checker, from a checkout — plus three reproductions listed under [method](#method), two of which opened a loopback socket |
| What did not run | Any real model, runtime image, container engine, cluster, inference request, paid service, or scanner |
| Claims certified by this record | none |

`local-static` is the weakest label these checks support and it is the correct
one. The adapter added here is real, and every check in the committed suites drove
it against a **controlled transport** supplied by the test file — an object that
answers what the test decided. That establishes the adapter's own logic and
establishes **nothing** about `llama-server`, about the pinned model, about
latency, about token accounting, or about any failure mode nobody anticipated.

**Two of the reproductions below opened a socket**, to a listener written for the
reproduction or to a closed local port. That is stated rather than folded into
"no network", because the classification table above would otherwise be wrong —
but it changes nothing about the class: a loopback socket answering a script is
not a runtime, and neither reproduction loaded a model, pulled an image, or
touched a cluster. They are not part of the committed suites and no lane runs
them.

**The same imprecision the previous record noted still applies.** The suites live
under `tests/adapters/`, whose layer carries the evidence class `mock` and a `C1`
ceiling in [the committed strategy](../../testing/test-strategy.v1alpha1.json).
These checks produce `local-static` results, which is weaker, and the vocabulary
rule is to pick the weakest label the record supports. Whether the `adapter` layer
should distinguish the two remains open and is still listed under
[deferred work](#deferred-work).

**No claim moves to `certified` in this change**, and no layer changes status. The
claims this work sits under — `a-model-that-is-not-ready-is-a-canonical-error`,
`an-unreachable-runtime-is-a-canonical-error`, and
`the-platform-serves-a-workload-the-contract-describes` — all require a capable
host and a real model, and all stay `planned`.

## Provenance

| Input | Value |
|---|---|
| Repository revision at branch point | `55a1ea4` |
| Branch | `feat/v1-s1-004-real-runtime-inference` |
| Distribution code added | `src/inferops/adapters/llama_cpp/{transport,http_transport,inference,adapter}.py` |
| Distribution code changed | `src/inferops/adapters/llama_cpp/{settings,__init__}.py`, `src/inferops/adapters/__init__.py` |
| Tests added | `tests/adapters/test_llama_server_{transport,inference,adapter}.py`, `tests/realruntime/test_llama_server_real_smoke.py` |
| Tests changed | `tests/adapters/test_llama_server_settings.py` |
| Records the error mapping was copied from | [ADR 0010](../../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md) and [the accepted surface data](../../serving/inference-api-surface.v1alpha1.json) |
| Record the request and response shapes were copied from | [the feasibility record](v1-s0-003-pr2-runtime-feasibility.md) |
| Model artifact | none. No weight file was downloaded, mounted, hashed, or read |
| Container image | none. No image was pulled, inspected, or run |
| Cluster | none |
| Network | no remote host. Two reproductions under [method](#method) opened a loopback socket; the committed suites open none |

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
uv run --locked python -m pytest -m adapter -q
uv run --locked python -m pytest tests/adapters -q
uv run --locked python -m pytest tests/domain -q
uv run --locked python -m pytest tests/architecture -q
uv run --locked python -m pytest tests/testing -q
uv run --locked python -m pytest tests/contracts -q
uv run --locked python -m pytest tests/security -q
uv run --locked python -m pytest tests/serving -q
uv run --locked python -m pytest tests/realruntime -q
uv run --locked python -m pytest tests/realruntime -m realruntime -q
git diff --check
```

`ruff check` and `ruff format` each corrected findings on the first attempt — an
unsorted import block, an aliased `socket.timeout` the linter reads as
`TimeoutError`, an unused unpacked variable, and four files reformatted. `mypy`
reported six findings in the new suites, all in test code: two assertions on a
function that returns `None`, two attribute accesses on an over-wide caught
exception type, and one narrowing that made an assertion unreachable. All were
corrected before the results below. The sequence is recorded because a record that
lists only the passing run describes a result rather than a method.

Three checks were run **outside** the committed suites, because each answers a
question no repository-only assertion can. Each is reproducible and none touches a
model, an image, or a cluster.

| Check | Why it was run | Result |
|---|---|---|
| The `realruntime` suite against a closed local port, with the six settings set | Its fixture had never executed — it always skips — so nothing established that the fixture, its teardown, or the settings-to-socket path work at all | The async fixture ran, `initialize` succeeded, the transport dialled and was refused, and each test failed with the canonical error its stage produces. One test, which needs no runtime, passed |
| The deadline race, against the real transport over a real socket that answers readiness and then goes silent | To confirm the reported race and that the grace fixes it | With the two clocks equal: `request-timeout` after 1.016 s. With the grace: `upstream-timeout` after 1.032 s |
| `asyncio.wait_for` over `asyncio.to_thread`, in isolation | To confirm that a fired deadline does not stop a worker thread | The deadline fired at 0.098 s; the worker ran to completion afterwards. This is what the cancellation close in the transport exists for |

## Results

| Check | Result |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 145 files already formatted |
| `python -m mypy` | Success: no issues found in 64 source files |
| `python -m pytest -q` | 3547 passed, 25 skipped, 7 deselected |
| `python -m pytest -m adapter -q` | 565 passed, 3014 deselected |
| `python -m pytest tests/adapters -q` | 565 passed |
| `python -m pytest tests/domain -q` | 398 passed, 18 skipped |
| `python -m pytest tests/architecture -q` | 416 passed |
| `python -m pytest tests/testing -q` | 498 passed |
| `python -m pytest tests/contracts -q` | 191 passed, 7 skipped |
| `python -m pytest tests/security -q` | 599 passed |
| `python -m pytest tests/serving -q` | 184 passed |
| `python -m pytest tests/realruntime -q` | 7 deselected |
| `python -m pytest tests/realruntime -m realruntime -q` | **7 skipped** |
| `git diff --check` | no output |

The adapter layer grew from 303 checks to 565. The architecture suite grew from
408 to 416 because it parametrises over every module under `src/inferops/`, and
this change added four. The security suite grew from 598 to 599 because it
parametrises over every committed Markdown file, and this change added one.

**The two `tests/realruntime` rows are the important ones**, and they are recorded
separately from everything else because they are the mock-versus-real split this
project's boundary rule asks for. The first shows the suite is deselected by the
committed default marker expression: a real-model test cannot arrive in the
default lane by accident. The second shows that naming the marker *still* did not
run it — the seven checks skipped because the runtime settings were unset, which
is what the suite does when nobody has asked for a real run. **No real inference
was executed by this change.**

## What the added checks establish

### The error mapping agrees with the record that decided it

| Value | Compared against |
|---|---|
| Every condition identifier the adapter holds | The `errorMapping` rows in the accepted surface data |
| The canonical code each condition produces | The `code` on the same row, field by field |
| Whether each condition was ever observed | The `observedInTrial` flag on the same row |
| The three conditions the adapter does **not** hold | Asserted to be exactly the API-layer rows: a request outside the frozen subset, a streaming request, and an unsupported contract version |
| `rate-limited` | Asserted absent from the adapter's mapping, and present in the accepted `codesNotEmitted` list with its reason |

One of six conditions was ever observed happening, and the table in the code says
which. The other five are mappings, and calling them that is the difference
between a mapping and a claim.

### Canonical errors are produced by the conditions that name them

| Condition | Code | How it is provoked in the suite |
|---|---|---|
| The runtime answers `503` to a probe | `model-not-ready` | A controlled `503` on `/health` |
| The runtime answers `503` to a completion | `model-not-ready` | A controlled `503` on the completion path, which also updates the readiness tracker |
| The transport cannot connect | `capability-unavailable` | A transport failure on the probe, and separately on the completion |
| The runtime does not answer in time | `upstream-timeout` | A transport timeout |
| The transport ignores its budget | `request-timeout` | A transport that sleeps past a 20 ms deadline |
| Any other non-2xx, including `429` and a `3xx` | `internal-error` | Seven statuses, parametrised |
| A 2xx body the adapter cannot read | `internal-error` | Sixteen mutations of the recorded completion shape, one at a time |

Each produced error is asserted to carry the `requestId` and `correlationId` the
caller supplied, and to carry no status code, host, port, path, or body fragment.

### Readiness is false until the model accepts requests

| Situation | `is_ready` |
|---|---|
| Not initialized | false, and nothing is probed |
| Shut down | false, and nothing is probed |
| After an observed `503` | false |
| After a status the mapping does not publish | false |
| After a transport failure of any of the three kinds | false, recorded as `unreachable`, and **not** raised |
| After re-initialization | false |
| After an observed `200` | **true** |
| After an observed `200` followed by a `503` | false |

Inference is gated on the same state: an adapter that has observed nothing probes
once before its first request, refuses when the probe says not ready, and does not
re-probe on a second request.

### Safeguards asserted

| Safeguard | How it is enforced |
|---|---|
| A prompt cannot reach an error | Asserted against a prompt carrying an account-number-shaped string, through a runtime error body that echoes it back |
| A prompt cannot be retained | Every attribute of the adapter except the test's own transport is swept after a completion |
| A runtime's words cannot reach a caller | The three transport failures take no argument, and a source sweep over `src/` fails if any construction site passes one |
| A runtime's words cannot reach a canonical error | An unrecognised error's message is dropped rather than wrapped, asserted with a container path in it |
| A request cannot be aimed anywhere | Every URL the adapter dials is asserted to come from the settings' closed path set; six unpublished paths, one traversal, and one absolute URL are refused |
| A redirect cannot move a request body to another host | `http.client` follows none, and a `3xx` is asserted to map to `internal-error` |
| A peer cannot decide how much memory this process allocates | The response body is asserted to be read under a 1 MiB bound |
| A socket cannot leak on failure | The connection is asserted closed on success and on failure |
| A credential cannot be added to a request by habit | The header set is asserted to be exactly `Accept`, with no authorization header |
| A real path cannot serve a mock identity | The adapter's refusal of a mock-labelled model identity is exercised through `initialize` |
| A token count cannot be invented | Absent `usage` is `None`; a malformed one is a refusal; a boolean, a string, and a negative count are each refused |
| A sampling default cannot arrive by accident | Seven sampling members are asserted absent from the request body |
| A rate limit cannot be claimed | No status and no transport failure produces `rate-limited` |
| A runtime serving a different model cannot pass unnoticed | Recorded as a reason code, not raised, and asserted to clear when the runtime agrees again |
| A transport that ignores its deadline cannot stall the process | The outer deadline is exercised directly |
| Runtime vocabulary cannot reach a domain result | A completion result is swept for a context length, a port, a host, a mount path, and a thread count |

### Conformance

`LlamaServerAdapter` is held to
[the shared conformance suite](../../../tests/support/serving_conformance.py) —
the same one the mock adapter and the in-memory double inherit — so "it implements
the contract" means the contract and not a version of it edited until this adapter
passed.

### Isolation

The architecture suite parses every module under `src/inferops/` and fails on any
import outside the standard library and this distribution. It covers the four new
modules exactly as it covers the domain. The transport is built from
`http.client`, which is the standard library's own HTTP rather than a client
library, and it is the only module in the distribution that can open a socket. No
module reads a file or an environment variable of the running process: the
environment is read only by `tests/realruntime/`, at the edge where ambient state
legally enters.

## What review changed

The change was reviewed twice before the second commit — once for correctness and
contract conformance, once for security — and the findings are recorded here
rather than smoothed away, because a record that shows only the corrected state
hides how much of it review produced. Two of the findings are defects the author
did not find.

| Finding | Severity | Disposition |
|---|---|---|
| The readiness probe had no outer deadline, and `infer` reaches it implicitly on its first call. A stalled probe was therefore an unbounded stretch inside a call whose whole contract is that it is bounded | must fix | Every runtime call now goes through one bounded helper. Three checks assert **elapsed time** rather than only the error code, and each fails against the previous behaviour |
| Both deadlines were set to the same duration while the outer one starts first, so the outer won by the dispatch cost every time. Every genuinely slow runtime would have been reported `request-timeout`, and `upstream-timeout` would have been a code nothing could produce | must fix | The backstop is now the budget plus a grace. Reproduced against the real transport over a real socket before and after: `request-timeout` at 1.016 s became `upstream-timeout` at 1.032 s |
| A fired deadline cannot stop a worker thread, so the socket and the pool slot were held until the far side chose to answer. The socket timeout does not close the gap: it bounds each read rather than the request, so a peer trickling bytes never trips it | must fix | The connection is built on the event loop and closed there when the call is cancelled, which unparks the blocked worker. The check fails against the previous behaviour |
| An out-of-range port survived construction, because `urlsplit` parses a port lazily, and surfaced inside a caller's first request as a `ValueError` no canonical mapping covers | should fix | Refused at construction, which is what this class already promised. The transport refuses one too, so a URL assembled another way cannot reach a caller uncanonicalised |
| A `close` that raised inside the `finally` replaced the mapped transport failure with its own, so a refusal would have reached the caller as a raw `OSError` carrying the far side's text | should fix | Closed quietly. Both the failure and the success paths are asserted |
| An oversized response body was truncated and then reported as unreadable, which is the wrong fact about a well-formed body that was merely too large | should fix | One byte past the bound is read, so oversized is distinguishable. A body exactly at the bound is still read whole |
| A transport is a value a caller supplies and may raise anything, but `infer` publishes a closed list of canonical failures | should fix | Anything unexpected maps to `internal-error` with its message dropped. `CancelledError` is not an `Exception` and still propagates, which is correct |
| `__all__` exported `annotations`, the `__future__` feature object, because it was generated from the module's import statements | should fix | Removed |
| An endpoint carrying a control character was refused only by two later defences | nit | Refused at construction as well |
| Three headline counts in this record were wrong, because the suites were run before the last document was added and the security suite parametrises over every Markdown file | must fix | Re-run and corrected. The counts above are from a full run of the final tree |
| `get_model_metadata` before `initialize` raises here and returns a fallback in the mock adapter, and the protocol is silent about which is right | should fix | **Not fixed.** Settling it means either editing the mock adapter or adding an obligation to the shared conformance suite, and both belong to the protocol rather than to this adapter. Recorded under deferred work |

## Limitations

- **No inference was executed against a real model, and none was attempted.** The
  acceptance criterion requiring one real generated response through the adapter
  is **not met by this change** and is not claimed to be. What the change adds is
  the code that can produce it and the marked suite that would record it.
- **Every executed check ran against a controlled transport.** The adapter is
  real; the far side is a test double. Nothing here establishes anything about
  `llama-server`, the pinned model, latency, decode rate, memory, token accuracy,
  or any failure the runtime actually produces.
- **The `/props`, `/v1/models`, and completion response shapes are still inferred,
  not observed by this change.** They are copied from the feasibility record,
  which preserved field names and values rather than a full JSON envelope for the
  first two. The previous record listed confirming them as the first task of the
  change that issues the calls; that change is this one, and it did not confirm
  them, because the lane was not entered.
- **The `enable_thinking` chat-template argument is a decision this change makes.**
  It is sent because the trial's request carried it and the response shape
  normalised here is the shape that request produced. It is not a sampling
  parameter, so ADR 0002's deferral does not reach it, but it is a value this
  adapter adds to a caller's request and a reviewer should see it named.
- **`temperature` is not sent, and the accepted surface says it is "passed to the
  adapter".** The frozen adapter protocol has no parameter to pass one through, so
  there is a gap between the API surface's intent and what the adapter can accept
  today. Closing it belongs to `V1-S1-005`, which builds the API. One consequence:
  the determinism the trial observed was observed at temperature 0, and this
  adapter does not set it, so nothing here may be read as a determinism guarantee.
- **`request-timeout` and `upstream-timeout` are split on a reading of the
  accepted mapping.** That record calls "the runtime does not answer within the
  adapter's deadline" `upstream-timeout` and reserves `request-timeout` for a
  caller's own deadline. The `ServingAdapter` protocol docstring instead describes
  `request-timeout` as "the request exceeds the configured timeout". The split
  adopted here follows the accepted mapping and gives `request-timeout` to the
  adapter's outer backstop; it is a judgement, it is reachable and tested, and it
  is stated here so a reviewer can dispute it rather than discover it.
- **`capability-unavailable` for an unreachable runtime reads oddly** and is what
  the accepted record decided, on the ground that the canonical vocabulary has no
  member meaning *unavailable*. The readiness path continues to report an
  unreachable runtime as not ready, which is a different question with a different
  answer, and the two are reconciled deliberately rather than by accident.
- **Concurrency is untested and undecided.** The transport opens a connection per
  request, the adapter is documented as unsafe to share across event loops, and
  ADR 0002 decides no concurrency limit. Nothing here measures behaviour under a
  second simultaneous request.
- **The outer deadline's grace is a chosen number.** It is one second. It is not a
  runtime setting and it never lengthens a budget a caller configured — it bounds
  only this adapter's own wait on a transport that has already broken its promise
  — but its size was chosen as a comfortable margin over the cost of handing work
  to a worker and opening a socket, and that cost was measured once, on one
  machine, in the reproduction recorded above.
- **A blocked worker is unparked by closing its socket, not by cancelling it.**
  Python cannot cancel a running thread. The transport closes the connection from
  the event loop when a call is cancelled, which makes the blocked read fail and
  lets the worker unwind — but the worker exits a moment after the caller does,
  not with it.
- **`get_model_metadata` before `initialize` diverges between the two adapters.**
  This one raises; the mock returns a fallback identity. The protocol states no
  precondition, and the shared conformance suite only ever calls it after
  initialization, so nothing holds the two to the same answer. Recorded rather
  than settled here, because settling it changes the protocol or the mock.
- **No scanner ran.** No secret scanner, image scanner, or dependency auditor was
  executed for this change; the diff was inspected by eye and by
  `git diff --check`.
- **One host, one operating system, one Python.** Nothing here depends on a clock,
  a random source, the network, or the file system from inside the distribution,
  so the result should reproduce anywhere the lockfile installs — but it has been
  run on one machine, and that is what this record says.

## Acceptance criteria

The parent story's criteria, and where each stands after this change.

| Criterion | Status | Where |
|---|---|---|
| Adapter pins or reports runtime and model revision | **Met** | `get_model_metadata` reports the configured identity and the pinned revision; `get_runtime_metadata` reports the observed build string or the pinned image digest. The revision is configured rather than attested, and the code says so |
| Readiness remains false until the model accepts requests | **Met** for the adapter's own behaviour | A tracker with no observation is not ready, has no setter, and reaches ready only through an observed `200`. What has not been shown is that a real runtime drives it that way |
| One response is generated by the real selected model through the adapter | **Not met** | The code and the marked suite exist. The lane is authorization-gated and was not entered, and no real completion was produced |
| Model-not-ready, timeout, and runtime failure map to canonical errors | **Met** for the mapping; **not met** for the provocation | Every condition is mapped, sourced to the accepted record, and exercised against a controlled transport. None has been provoked against a real runtime; that is the `failure-and-resilience` layer, still `planned` |
| Runtime-specific configuration remains isolated | **Met** | The dependency rule is enforced by the architecture suite over every new module, and a completion result is asserted to carry no runtime vocabulary |

## Deferred work

- **The executed record of one real generated response**, which is what closes the
  story's third criterion. It needs the `real-runtime` lane, a capable host,
  authorization, the pinned image, and the hash-verified model artifact.
- Confirming the `/props`, `/v1/models`, and completion response shapes against a
  live runtime.
- A serving deployment that sets the six environment variables, and the manifest
  that carries the argument list the configuration half generates.
- Provoking each canonical error against a real runtime rather than a controlled
  transport. That is the `failure-and-resilience` layer, which is `planned`.
- Wiring a caller's `temperature` through, which needs the API `V1-S1-005` builds
  and possibly a change to the frozen adapter configuration.
- Concurrency: whether the per-request connection, the single readiness tracker,
  and the adapter's shared state hold up under simultaneous requests.
- Whether the mock prefix and the capability names should be promoted into the
  domain's published vocabulary instead of being held twice and compared. Carried
  forward from the previous record; the real adapter now exists, and the question
  is still worth answering somewhere other than in passing.
- Whether the `adapter` test layer should distinguish `local-static` checks from
  `mock` ones. Carried forward, and this change added 262 more checks that sit
  below the layer's declared class.
- Whether `get_model_metadata` before `initialize` should raise or report a
  fallback, and whether the protocol should say so. Both concrete adapters answer
  it differently today and the shared conformance suite cannot see the difference,
  because it only calls the method after initialization. Settling it means editing
  the protocol and one of the two adapters, both outside this PR's boundary.
- A total elapsed-time budget for a runtime call, rather than the per-read socket
  timeout the standard library gives. A peer that trickles bytes just under the
  budget never trips a per-read timeout; the adapter's backstop bounds the
  *caller's* wait, and the worker is unparked by closing the socket rather than by
  a deadline of its own.

## Authorisation

Not required, and none was sought. Every command above runs from a checkout on a
contributor's own machine, downloads no model, allocates no paid capacity,
provisions nothing, and touches no cluster. The `real-runtime` lane is manual and
authorization-gated and **was not entered**; the suite written for it skipped
because the runtime settings it needs were unset.

## Related records

- [Executing real inference through the adapter](../../serving/real-runtime-inference.md) —
  what the adapter is, what it sends, and what it refuses to claim.
- [Configuring and inspecting the selected runtime](../../serving/real-runtime-configuration.md) —
  the first half, and the six modules this one composes.
- [V1-S1-004-PR1 validation](v1-s1-004-pr1-validation.md) — the record this one
  continues, including the limitations it carried forward.
- [ADR 0010, inference API compatibility surface](../../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md) —
  where the error mapping and the response subset were decided.
- [ADR 0002, model and serving runtime](../../architecture/decisions/ADR-0002-model-and-serving-runtime.md) —
  the runtime, the model, and everything it left undecided.
- [The V1-S0-003-PR2 feasibility record](v1-s0-003-pr2-runtime-feasibility.md) —
  the only record in this project that observed the runtime.
- [The mock and real serving boundary](../../serving/mock-and-real-boundary.md) —
  the rule that makes a missing real record an unmet criterion rather than an
  opportunity for a controlled transport.
- [Certification levels and evidence classes](../../testing/certification.md) — why
  this record stops at `C0`.
