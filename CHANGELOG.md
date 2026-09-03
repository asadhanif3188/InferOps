# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project intends to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once versioned releases begin.

## [Unreleased]

### Added

- **A repeatable local serving baseline experiment, registered before it is
  run.** The versioned
  [baseline descriptor](deploy/serving/baseline/local-baseline.v1.json) and
  [`tools.serving_baseline`](tools/serving_baseline/) command fix the request
  fixture, generation settings, warm-up, measured request count, concurrency,
  timeouts, and success criteria; capture a sanitized environment and the
  immutable model, image, and runtime pins; and turn one authorized run into a
  JSON Lines raw record set plus a deterministic summary that can be regenerated
  from it. Latency percentiles use nearest rank, so every reported figure is a
  value a request actually produced, and warm-up requests are recorded and then
  excluded from every distribution. Loading refuses a descriptor that drifts from
  the composition, the runtime profile, or the model record, and any answer
  carrying mock identity aborts a run rather than being recorded. The method is
  pre-registered in
  [the experiment record](docs/proof/serving/v1-s2-005-local-baseline-experiment.md)
  and documented in [the baseline guide](docs/serving/local-serving-baseline.md).
  **The experiment was not executed by this change and this repository holds no
  measured baseline.** The baseline is descriptive and may never be published as
  a benchmark.

- **A repeatable C2 real-runtime smoke certification for the composed serving
  path.** The versioned
  [certification descriptor](deploy/serving/certification/c2-smoke.v1.json) and
  [`tools.runtime_certification`](tools/runtime_certification/) command refuse a
  host below the selected package's engine CPU, engine memory, and free-disk
  needs before any container exists, wait for both bounded readiness boundaries
  through the existing local composition, send one fixed public request through
  the InferOps API, and refuse any answer carrying mock identity or mock
  capability metadata. A certified run writes a `local-real-cpu` record labelled
  `local real runtime`; a failure exits non-zero and stores diagnostics naming
  the stage. Neither record retains a prompt, a completion, or a host identifier.
  Default tests drive the workflow through injected seams only. **No authorized
  real run was performed by this change, so no `C2` claim is made.**

- **One guarded host-local workflow composes the InferOps API with the selected
  real runtime.** The versioned
  [composition descriptor](deploy/serving/local/composition.v1.json) and
  [`tools.local_composition`](tools/local_composition/) command validate exact
  real-adapter configuration, start and ready the pinned runtime before the
  loopback API, keep the process attached, and drain the API before
  ownership-scoped runtime cleanup. Default tests cover rendering and lifecycle
  through controlled seams, including a loopback HTTP request to the real adapter
  type over a synthetic transport. No real runtime or model was executed by this
  change.

- **A repeatable standalone package for the selected local runtime.** The
  [package descriptor](deploy/serving/runtime/container-package.v1.json) and
  [`tools.runtime_packaging`](tools/runtime_packaging/) command pin the image and
  process, mount only the hash-verified external model, publish only loopback,
  constrain resources and process privileges, and provide guarded startup,
  readiness, bounded inference smoke, and ownership-scoped shutdown. Repository
  tests exercise the lifecycle through synthetic seams; this change did not pull
  the image, download the model, or execute the real runtime.
- **A digest-pinned local CPU profile for the selected LLM runtime.** The
  [machine-readable profile](docs/serving/runtime-profile.local.v1.json) fixes the
  `llama-server` executable and arguments, external read-only model mount, port,
  CPU and memory envelope, context and generation defaults, timeouts, readiness,
  liveness, metrics, and no-embedded-secret boundary. The offline
  [`tools.runtime_configuration`](tools/runtime_configuration/) check validates
  the record against the runtime/model pins and the real adapter without pulling
  an image, reading model bytes, or starting a process. Runtime packaging and
  local-real startup/readiness evidence remain deferred.
- **Revision-pinned, resumable acquisition for the selected open model.** The new
  [model source record](docs/serving/model-source.v1.json) makes the upstream
  repository, immutable revision, Apache-2.0 licence reference, expected byte
  count, SHA-256, and workspace cache layout explicit. The
  [`tools.model_acquisition`](tools/model_acquisition/) command checks prerequisites
  without network access, safely resumes a `.part` transfer, verifies size and hash
  before atomic promotion, reports verified cache hits, and removes only the
  documented cache after explicit confirmation. Model artifacts are ignored by
  Git, and repository tests exercise the workflow with tiny synthetic bytes; this
  change does not download the selected model or package its serving runtime.
- **A verified Sprint 1 developer quick start.**
  [`docs/developer-quick-start.md`](docs/developer-quick-start.md) gives the shortest
  repository setup, workload scaffolding, validation, generated-contract test, and
  mock API workflow. It also publishes the optional real-adapter smoke boundary:
  the run is manual and authorization-gated, a skip is not a pass, and this change
  did not download a model, start a runtime, or produce real-runtime evidence.
  Cleanup and platform-specific shell forms are included.
- **The InferOps API emits telemetry. It is the first component here that emits
  anything at all.** The accepted catalog assigns nine metrics to the
  `inferops-api` emitter and, until now, every one of them was a specification for
  a component that did not instrument itself: `emissionStatus` read `nothing-emits`
  and the `/metrics` endpoint served a body of comments explaining why. Eight of
  those metrics are now produced — the request counter, the error counter, the
  latency histogram, the in-flight gauge, the readiness-failure counter, the token
  counter, the process CPU counter, and the identity metric — rendered on
  `GET /metrics` in the Prometheus text exposition format, and the API writes the
  structured log record the catalog specifies for every request it receives and
  every request it closes. [What it emits](docs/telemetry/api-instrumentation.md)
  is published with a real scrape, real records, and the variables a deployment
  states its identity in.
- **`ADR 0002`'s `T7` obligation is discharged.** The selected runtime exposes no
  cumulative request counter; that was measured, it is the threshold the record
  documents as failed, and the compensating plan was that the component receiving
  the requests would count them. `inferops_inference_requests_total` now does.
  Nothing about the runtime is fixed, and the limitation saying so stays.
- **A refused request is counted like any other.** The close is in a `finally`, so
  a body outside the frozen subset, a refusal from the adapter, a drain, and an
  unexpected failure each increment the counter, decrement the in-flight gauge, and
  produce a latency observation. A counter that only counts the paths somebody
  remembered is a success rate that flatters the platform. A timeout is a separate
  outcome from a server error, decided by the condition rather than the status,
  because a caller's deadline and a runtime's deadline carry different statuses and
  are the same operational event.
- **The placement rules stopped being a property of a document.** A metric
  declaration naming a label the catalog does not permit — a correlation
  identifier, a request identifier, a workload version, an owner, a pod, a measured
  duration, or any identity attribute — is refused when the metric is declared,
  before a series can exist. A label value that could inject a series into the
  exposition is refused too.
- **Redaction stopped being a rule and became a sink.** A log record is built
  through an allowlist of the attribute names the catalog publishes, and there is
  no name in it for a prompt, a completion, a provider error body, a secret, an
  authorization header, or a value read out of a submitted document — no message
  field, no `extra` mapping, no pass-through to the encoder. A rejected field is
  named in the refusal and its value never is. The suites now drive the application
  with a real prompt and a real adapter message and assert that neither reaches any
  record or any series, which is the check
  [the redaction rules](docs/telemetry/redaction.md) previously recorded as absent.
- **Mock telemetry says it is mock, in three places.** The exposition opens with a
  comment naming the mock adapter and stating that it certifies no serving runtime,
  the identity metric carries `inferops.adapter.kind="mock"`, and every operational
  series and every record carries the mock runtime's registered identifier. The
  adapter kind is derived from the adapter selection and never configured beside
  it: a second variable carrying that label would be a way to compose a real
  adapter and publish `mock`.
- **A deployment states its own identity, and an unstated one stays empty.** Ten
  optional variables carry the service version, environment, capability, release,
  pod, model revision, runtime image digest, workload, workload version, and owner.
  A deployment that states none of them still starts, still serves, and still
  emits, with its identity labels visibly empty — because a `service.version` of
  `unknown` sorts, groups, and reads like a release somebody shipped. The workload
  identity is configuration and **not** a caller's header: a workload identifier
  read off a request would be an unbounded metric label wearing a bounded one's
  name.
- **The catalog and the code are compared in both directions.**
  [`tests/telemetry/test_api_telemetry_agreement.py`](tests/telemetry/test_api_telemetry_agreement.py)
  reads the accepted record and the distribution's declarations and fails when they
  disagree on a name, an instrument, a label set, a bucket count, or which metrics
  are emitted at all.
  [`tests/api/test_api_observability.py`](tests/api/test_api_observability.py)
  drives the application and asserts on what it actually emitted.

- **The three surfaces that read a WorkloadContract are compared, not just each
  checked.** The published JSON Schema, the offline validator, and the platform
  domain each had a correct suite of its own and nothing compared two of them,
  which is where drift actually appears: a rule tightened on one side, an
  identifier renamed on another, a supported version added to one constant.
  [`tests/contracts/test_platform_contract_regression.py`](tests/contracts/test_platform_contract_regression.py)
  asserts that all three accept every valid fixture and every generated workload,
  that the platform refuses every invalid one, that the layer recorded for each
  refusal is the layer that actually produces it, that every rule identifier the
  domain cites is a published semantic rule and every published semantic rule is
  one it implements, and that the three constants naming the supported contract
  version agree. One divergence is recorded rather than hidden: the domain does
  not refuse the mock-dressed-as-real fixture, the schema does, and a two-way set
  assertion means that fact cannot change silently in either direction.
- **A generated mock workload cannot be edited into real serving.** The four
  edits the contract document names — the environment, the serving capability, the
  accelerator, and a cited real-runtime proof — were already refused on the
  *committed* mock fixture. They are now refused on the scaffolder's own output,
  which is the document most likely to be edited after generation and the one
  nobody reviewed.
- **Every serving adapter this repository ships is discovered and held to the
  shared conformance suite.** The two subclasses existed; nothing asserted that
  the set of adapters covered was the set of adapters shipped, so an adapter added
  without a suite would have passed every check here.
  [`tests/adapters/test_adapter_contract_regression.py`](tests/adapters/test_adapter_contract_regression.py)
  walks the adapters package for classes that structurally implement the protocol,
  fails when one has no conformance suite, and compares the adapter-kind
  vocabulary across the three places it is written down — the kinds the domain
  accepts, the kinds the adapters declare, and the kinds the API can compose.
- **Every condition the API can refuse on is provoked, or recorded as unreachable
  with a reason.** The refusal sites were each exercised by hand, which left a
  condition added and never provoked passing every check in the repository.
  [`tests/api/test_api_contract_regression.py`](tests/api/test_api_contract_regression.py)
  drives the published table instead: fifteen of sixteen conditions are provoked
  and held to the code, flag, status, and identifier their own row declares, the
  sixteenth carries the reason no request can reach it, and the mapping is
  asserted exhaustive in both directions before any of it runs. Every published
  route is driven for the success shape, the correlation identifier, and the
  adapter kind.
- **A test inventory, and the checks that stop it going stale.**
  [The inventory](docs/testing/test-inventory.md) lists every pytest module in the
  repository, the layer and lane it belongs to, and the claim it protects — the
  answer to "if this claim stopped being true, which suite would fail", which
  previously meant reading forty modules and guessing.
  [`tests/testing/test_test_inventory.py`](tests/testing/test_test_inventory.py)
  compares it with the test tree and the committed strategy in both directions: a
  module absent from it fails, a module filed under a layer whose paths do not
  contain it fails, a module credited with a claim its layer cannot support fails,
  and a claim that no module names and no recorded gap explains fails.
- **Two published counts are now compared with the data that decides them.**
  Independent review of this change found the new inventory document saying "five"
  modules defend no published claim while its own section listed six, and found
  `docs/testing/README.md` saying seven of eleven test layers exist while the
  strategy document and its data said eight. Both are corrected and both are now
  checked: the inventory's two counts against the inventory data, and the layer
  count across the five living documents that state it, in both forms they use.
  Records under `docs/proof/` and changelog entries are deliberately excluded —
  both are statements about a moment that has passed, and rewriting one to match
  today would falsify a record rather than fix a document.
- **What the inventory found is published rather than quietly fixed.** Six claims
  have no pytest module behind them — two of them certified, defended by a shell
  check and by a manual download step — and six suites defend no published claim at
  all. Both lists are in the document with a reason each.

- **The command that generates a workload, and validates the one it wrote.**
  `python -m tools.workload_scaffold` gathers the parameter set, renders the
  template, and writes three files — then reads all three back, compares them to
  what was rendered, and validates the written contract *from disk* through the
  same function every committed fixture goes through. "A generated workload
  validates without a source edit" is now a statement about files rather than
  about the strings that produced them. Documented in
  [the template document](docs/scaffolding/workload-template.md), with a mock and
  a real example.
- **Nothing is written before a refusal, and nothing is overwritten.** The order
  is refuse, render, validate, plan, write, read back, so an invalid name,
  profile, or resource declaration fails while there is nothing to clean up — and
  the check for it asserts that the destination directory was never *created*,
  not merely that it is empty. An occupied destination is refused with its
  contents untouched: a generated workload is an ordinary committed directory the
  moment it exists, and there is no flag that would overwrite one.
- **A write that fails partway leaves what it found.** Every directory and file
  the command creates is recorded as it is created and removed in reverse order
  on any failure, including a failure of the read-back, taking back only what the
  command itself made. A rollback that cannot remove something says so rather
  than reporting a clean undo it did not achieve.
- **The generated project is proven by running it.** The suite executes the
  generated test skeleton under a real `python -m pytest` subprocess, against the
  directory the command created, from a working directory outside this
  repository, with no file edited in between. An import proves a module is
  importable; only a subprocess proves the command a generated quick start
  prints.
- **The command line is generated from a published option table**, so the flags
  and the template's parameter set cannot disagree — in either direction,
  including which parameters are required and what each default is. A closed
  vocabulary is deliberately not enforced by `argparse`: a `choices=` would turn
  a mistyped environment into a usage error that exits before the other ten
  parameters are read, and the whole point of the validator is that an author
  learns every reason in one pass. Exit status says which stage refused, so the
  command is usable as a gate.

- **A reusable LLM workload template, in two profiles, with a declared parameter
  set in front of it.** A generated workload is three files — the contract it
  declares, the quick start a second engineer reads, and a test skeleton that
  reads the contract back — and the same three whatever profile it is on, because
  a profile-shaped filename becomes a profile-shaped build step downstream.
  Rendering returns text: `render_workload` validates the whole parameter set,
  refuses it with **every** reason at once, and then produces a mapping of path to
  content. There is no partial result to clean up because this half has no file to
  write; the command that writes one is `V1-S1-006-PR2`. Described in
  [the template document](docs/scaffolding/workload-template.md).
- **What the template renders is held to the published contract, not to a copy of
  it.** The suite puts every rendered document through
  `tools.contract_validation` — the same function every committed fixture goes
  through — and then through `inferops.domain.workload`'s own validation pipeline,
  so "generated output validates without a source edit" is a checked property
  rather than a claim. Every format, vocabulary, and bound the parameter set
  applies is imported from the domain's value objects, which are themselves
  compared against the schema, so the template cannot accept a value the contract
  would refuse.
- **A generated mock says it is a mock in three places, and a generated workload
  cites no evidence it has not produced.** The profile block, the workload's own
  name — a `mock-llm` name must end in `-mock`, refused rather than silently
  appended — and the prose a reader meets first. `evidence.proofRefs` is absent
  from **both** profiles: a generated workload has executed nothing, and
  pre-filling it with the feasibility record would hand every generated workload a
  result produced by a different one. The mock and real quick starts stay distinct
  in both directions, and a check asserts the mock does not offer the
  real-runtime lane.
- **Three rules stricter than the schema, each a refusal rather than a silent
  correction**: the mock name suffix, an accelerator declaration that contradicts
  itself, and a required `description`. Each is documented as a tightening, because
  a tightening nobody wrote down is a tightening nobody can argue with. No refusal
  repeats the value it refused, for the reason the domain's errors give.
- **The one free-text parameter is escaped for each format it lands in, and
  gated in front of that.** `description` is prose, and prose substituted raw
  into YAML is YAML: a colon makes the document unparseable, a `#` truncates it
  silently, and a newline followed by an indented key adds a `metadata.annotations`
  entry nobody declared to a document that then **validates with zero findings**.
  All three were reachable and are now not. `substitutions()` publishes
  `description_yaml`, `description_markdown`, and `description_python` and never
  the raw string, so there is no key that would render prose unescaped; and the
  parameter gate refuses a description that is not a single line of printable
  text, so an author is told rather than handed a document with a `\n` in the
  middle of a sentence. A suite asserts the round trip character for character,
  over both profiles, for eleven descriptions a person would plausibly type — six
  of which fail without the emitters.
- **The runtime image digest and the model bytes are template-owned, not typed by
  an author.** A digest an author pastes is a digest nobody checked, so a generated
  `synchronous-llm` workload carries the pair ADR 0002 selected, and a test
  compares every pinned value against the committed compatibility matrix and the
  committed valid fixture. `modelRef` is a closed set for the same reason: the
  catalogue holds one entry per serving capability, and naming the other profile's
  identity is a single-word edit away from a document that would put a mock label
  on a real serving path.
- **The canonical error contract, served in full and keyed on a condition rather
  than a code.** Every refusal now carries `code`, `message`, `requestId`,
  `correlationId`, `retryable`, and `details`, and `retryAfterMs` where a delay was
  decided. The unit is a **condition** because the accepted record maps
  `capability-unavailable` twice — to a runtime that cannot be reached, which is
  retryable and a `503`, and to a caller asking for streaming, which is not and is
  a `400` — so a code-keyed table would have to answer one of them wrongly. Nine
  conditions are copied from
  [the accepted record](docs/serving/inference-api-surface.v1alpha1.json) and
  compared against it by a test; seven are this API's own, for routing, an
  oversized body, a draining deployment, and an adapter contradicting its own
  deployment, and each is marked as added rather than presented as accepted.
  Described in [the API document](docs/serving/inference-api.md#errors).
- **An adapter's own message no longer reaches a caller.** The previous change
  forwarded it, which was safe because every canonical message in this repository
  happens to be a constant — safe by review rather than by construction. An adapter
  is the component closest to a runtime's error text, a mounted weight-file path,
  an endpoint, and a prompt, and
  [the redaction rules](docs/telemetry/redaction.md) name a provider error body as
  the surface most likely to be logged, pasted into a ticket, and kept. A canonical
  error raised below the edge is now answered with this API's own message for its
  condition, and a suite raises messages carrying a path, a host, and a prompt
  fragment to assert none of it comes back.
- **Configuration-driven adapter selection, with no default and no fallback.**
  `INFEROPS_SERVING_ADAPTER` is required and takes `mock` or `real`; unset, empty,
  and unrecognised all select **nothing**, and a `real` selection whose runtime
  settings are missing or malformed is **refused rather than answered with a
  mock**. That is boundary rules 5 and 4 held at the one place a deployment is
  assembled, and the suite for it is mostly refusals for that reason. The adapter
  kind is **derived** from the selection rather than configured beside it, so no
  configuration can compose a real adapter and label it `mock`; the existing check
  that every adapter result declares the deployment's own kind catches the rest.
  The mock's failure injection and latency get no variable at all — those are test
  inputs, and a variable that made a deployment produce a canonical error on demand
  would be reachable wherever the deployment ran.
- **`version-unsupported` is reachable, from the only place a caller can name a
  version.** A request to `/v2/chat/completions` names an API version this
  deployment does not serve, which is a different refusal from `/healthz` — a path
  nobody publishes. This surface reads no version header and the accepted record
  defines no request-body extension member, so the path is where it is decided.
- **End-to-end suites for both halves of the boundary.**
  [`tests/api/test_api_end_to_end_mock.py`](tests/api/test_api_end_to_end_mock.py)
  drives configuration to response for a success and for every failure the mock
  can produce — reading the scenarios from the mock's own enumeration, whose
  failing members *are* the canonical codes, so a code the domain gains will fail
  the suite until this API maps it. Its real counterpart,
  [`tests/realruntime/test_api_real_adapter_smoke.py`](tests/realruntime/test_api_real_adapter_smoke.py),
  puts the API in front of the real adapter composed from configuration and is
  **deselected by default**. **It has not been run against a runtime**: the lane is
  authorization-gated and was not entered, and
  [the validation record](docs/proof/serving/v1-s1-005-pr2-validation.md) says so
  rather than presenting a skipped session as a green one.

- **The user-facing InferOps API, which is the first component here that answers a
  request.** [`src/inferops/api/`](src/inferops/api/) registers the five endpoints
  [ADR 0010](docs/architecture/decisions/ADR-0010-inference-api-compatibility-surface.md)
  decided a story earlier and answers each of them through the serving adapter it
  is composed with: a synchronous chat completion, the model list with the runtime
  descriptor beside it, liveness, readiness, and metrics. The compatibility shape
  is admitted at the edge and translated there, so nothing compatibility-shaped
  crosses into the platform domain and nothing runtime-shaped crosses back out.
  Described in [the InferOps inference API](docs/serving/inference-api.md).
- **It imports no HTTP framework, because the dependency rule leaves no room for
  one.** The application implements the ASGI calling convention directly — a
  callable over a scope, a receive, and a send — which is a convention rather than
  a package, so
  [ADR 0004](docs/architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
  is obeyed without a framework-shaped hole in the design, and the distribution
  still declares no runtime dependency at all. **This repository ships no ASGI
  server**, so nothing here has bound a socket: the suites drive the application
  through its own interface, which establishes what the application decides and
  nothing about HTTP, and
  [the validation record](docs/proof/serving/v1-s1-005-pr1-validation.md) says so
  rather than presenting a green session as a served API.
- **A composition point with no default adapter.** The adapter is handed to the
  application in code. A mock that could become the live adapter by omission is
  what [the boundary rule](docs/serving/mock-and-real-boundary.md) forbids, so
  there is nothing to omit — and the kind the deployment was composed with is
  checked against every result the adapter returns, so a `mock` deployment serving
  a `real`-labelled result is refused rather than published with a label nobody
  can rely on. Selecting that adapter from configuration is the entry above.
- **The strict unknown-member policy, enforced rather than described.** A member
  outside the frozen subset is refused and the refusal names the member and never
  its value — including the upstream defaults a client library sends by habit,
  which is the cost the accepted record chose openly. Three refusal suites carry a
  canary value in the position a naive implementation would echo, and assert it is
  absent from the response.
- **Graceful shutdown as the equivalent the record chose over an endpoint.**
  Readiness goes false *before* anything drains, in-flight work finishes under a
  bounded budget that reports whether it ran out, and the adapter is released last.
  An HTTP route that stopped the process would be an unauthenticated remote-stop
  control on a surface with no authentication in V1.
- **The `mock-integration` test layer, which was registered and empty since
  `V1-S0-006`.** [`tests/api/`](tests/api/) now runs the API end to end against the
  labelled mock adapter and against controlled doubles, under the `mockintegration`
  marker the default lane already selects. A request stays counted until its
  response has been handed to the server rather than until the adapter answered,
  because a drain that returned in the gap between those two would report a clean
  shutdown over a response nobody received — and the suite reads the in-flight
  count from inside the send, which is the only place that distinction is visible.

- **The serving adapter for the selected real runtime, which generates text or
  fails.** The previous change deliberately shipped no `ServingAdapter` for
  `llama-server`, on the ground that a class satisfying the protocol's shape while
  its `infer` could not generate anything would be a mock wearing a real adapter's
  name. `LlamaServerAdapter` is the other half: it composes the pins, settings,
  configuration translation, readiness mapping, metadata parsers, and capability
  declaration that package already held, and adds a transport seam, an inference
  client, two bounded deadlines, and the mapping from a runtime failure to a
  canonical error. It is held to the same conformance suite the mock adapter and
  the in-memory double inherit. Described in
  [executing real inference through the adapter](docs/serving/real-runtime-inference.md).
- **A transport that is a parameter rather than a private method.** The adapter is
  constructed with one, so composing an adapter is where the decision to open
  sockets is made, a suite can exercise every branch against controlled responses
  without intercepting the standard library, and the object that could manufacture
  a `real`-labelled result without a runtime lives in the test file that uses it
  rather than in the distribution. The concrete transport is built from
  `http.client` — the standard library's own HTTP, not a client library — because
  [the dependency rule](docs/architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
  forbids anything else, and that constraint produced three properties worth
  having: no redirect is followed, so a request body cannot be moved to a host the
  settings never validated; a response body is read under a 1 MiB bound, so a peer
  cannot decide how much a 3 GiB pod allocates; and a connection is opened per
  request and closed in a `finally`.
- **An error mapping copied from the record that decided it, not invented.** Every
  condition the adapter can reach carries the identifier
  [the accepted API surface](docs/serving/inference-api-surface.v1alpha1.json)
  publishes for it, and a test reads that file and fails when a copy drifts. One
  of the six was ever observed happening — the `503` the runtime answers while it
  loads — and the table says which, because five mappings and one observation are
  not six equal facts. `rate-limited` is never produced: V1 has no rate limiter,
  the accepted record lists the code among those this platform does not emit, and
  a runtime answering `429` is an `internal-error` like any other unexpected
  status rather than an observation of a limiter that does not exist.
- **Two deadlines, and the outer one is deliberately the longer.** The transport is
  handed the configured budget; the call is wrapped in a backstop of that budget
  plus a grace. The inner produces `upstream-timeout` — the runtime ran out of
  time — and the backstop produces `request-timeout`, and it exists because a
  transport is a value a caller supplies and a protocol cannot enforce the promise
  it asks for. The grace is what makes the pair work: both clocks would otherwise
  be set to the same duration while the outer one starts first, so it would win by
  the dispatch cost every time and `upstream-timeout` would be a code nothing
  could produce. Every runtime call is under both, the readiness probe included,
  because that probe is reached implicitly by the first inference call. A fired
  deadline closes the socket, since a thread cannot be cancelled and the worker
  would otherwise hold its socket until the far side chose to answer.
- **A real-runtime smoke suite that has not been run.**
  [`tests/realruntime/`](tests/realruntime/) drives the adapter against a live
  `llama-server` holding the pinned model, under the `realruntime` marker the
  default expression deselects. It reads its settings from the process environment
  and **skips** when they are unset, because a missing endpoint means nobody asked
  for a real run rather than that a real run failed. The lane is manual and
  authorization-gated and was not entered, so the story's criterion requiring one
  real generated response through the adapter is **still unmet** and
  [the validation record](docs/proof/serving/v1-s1-004-pr2-validation.md) says so
  rather than presenting the code as the proof.
- **The configuration and inspection half of connecting InferOps to the selected
  runtime — and no adapter, deliberately.**
  [`src/inferops/adapters/llama_cpp/`](src/inferops/adapters/llama_cpp/) holds the
  runtime image digest and the model revision, file, size, and published hash from
  ADR 0002; the operator settings and environment variables that configure a
  `llama-server` deployment; the translation from platform configuration into
  runtime configuration and back; the health-status mapping; the metadata parsers;
  and the capability declaration. There is no `ServingAdapter` implementation in
  it, because a class satisfying the protocol's shape while its `infer` could not
  generate anything would be a mock wearing a real adapter's name — and
  substituting a mock for a missing real result is a defect under
  [the boundary rule](docs/serving/mock-and-real-boundary.md) rather than a
  fallback. Described in
  [the runtime configuration document](docs/serving/real-runtime-configuration.md).
- **Readiness that is false until the runtime says otherwise.** The selected
  runtime answers `503` while it loads its weights and `200` once it can serve, and
  that is the behaviour the Sprint 0 trial found which no mock could have
  surfaced. A readiness tracker starts in `not-probed`, exposes no setter, and
  reaches `ready` only through an observed `200`; a later `503` takes readiness
  away again, because a replaced pod is a fresh process with a fresh load. Any
  other status is `unexpected-status` rather than `loading`, since treating an
  unknown answer as temporary is how a permanently broken runtime gets waited on
  forever.
- **Pins that are compared to their sources instead of trusted.** Every constant
  copied out of ADR 0002, the feasibility record, and the compatibility matrix is
  asserted against the file it came from, including field by field against the
  committed `synchronous-llm` example, so a drift between the accepted decision and
  the code is a failing assertion rather than something a reader has to notice. A
  workload document naming a different image digest, model revision, weight file,
  size, or hash is refused with the field path the contract publishes and without
  the value it refused.
- **Nothing ADR 0002 left undecided acquired a default.** The context length and
  the thread count are required inputs with no default, because that record states
  they remain undecided and that the values the trial ran were stated inputs rather
  than recommendations. Omitting one is a refusal naming the variable. The single
  setting that does default is the runtime's own metrics endpoint, which defaults
  to on because ADR 0002's `T7` exception is argued on its existence — so turning
  it off is the deviation, and the deviation is what gets written down.
- **A deterministic mock serving adapter, and the safeguards that stop it being
  read as a real one.** [`src/inferops/adapters/`](src/inferops/adapters/) holds the
  first implementation of the serving interface the domain owns. It replays
  [one committed response fixture](contracts/workload/fixtures/mock-llm-chat-completion.response.json),
  requires no model file, credential, container engine, cluster, or network, and
  produces the same answer every time. Each canonical failure a caller has to handle
  — `model-not-ready`, `request-timeout`, `upstream-timeout`, `rate-limited`,
  `internal-error` — is reachable by construction, and the scenario's name *is* the
  code it produces, so the two cannot drift apart. What it refuses to do is the other
  half: it declines a model identity that is not mock-labelled, declares real model
  inference and token counting unsupported rather than inventing either, reports no
  model revision, and carries its own `mock` label in every result, in its runtime
  identity, in its telemetry attributes, and in a self-describing block that matches
  the one the fixture already carries. Described in
  [the mock serving adapter document](docs/serving/mock-serving-adapter.md).
- **The `adapter` test layer, registered and empty since `V1-S0-006`, now runs.**
  Seven of eleven layers exist. Its 76 checks live in
  [`tests/adapters/`](tests/adapters/) under the `adapter` marker rather than beside
  the domain suite, because the two layers carry different evidence classes and a
  mock result filed under a `local-static` layer is a misfiled result. Its ceiling is
  `C1` and the suite asserts that ceiling against the committed strategy data rather
  than restating it, so making the mock more faithful still raises nothing.
- **A conformance suite that is inherited rather than copied.** The obligations the
  `ServingAdapter` protocol publishes are written once in
  `tests/support/serving_conformance.py`; the in-memory double and the mock adapter
  each subclass it and supply an adapter. A new obligation is added in one place and
  every adapter is held to it in the same commit, which is what "reusable harness"
  had to mean to be worth the name.
- **The first InferOps-owned code that is part of the distribution**, in
  [`src/inferops/domain/workload/`](src/inferops/domain/workload/) and described in
  [the workload domain model](docs/domain/workload-domain-model.md). A
  `WorkloadContract v1alpha1` document becomes a tree of frozen, typed platform
  objects — workload identity, owner, profile, model and runtime reference,
  resources, scaling, integrations, security classification, attribution, and
  evidence references — with every identifier and formatted value carrying its own
  type rather than being a string that looked right when it was read.
- **The architecture's dependency rule, checked from the source instead of at review
  time.** `tests/architecture/test_domain_dependency_boundary.py` parses every
  module under `src/inferops/` and fails if one imports anything outside the
  standard library and this distribution. It is an allowlist rather than a list of
  forbidden packages, because the rule is about everything the domain is not,
  including whatever ships next year; a second check names the Kubernetes, Helm,
  Terraform, runtime-SDK, and HTTP-framework families in ADR 0004's own words. The
  domain declares no runtime dependency and reads no file, so a domain object is
  constructible from a wheel with no repository around it.
- **A round-trip property that makes "the domain loses nothing" checkable.**
  `WorkloadContract.as_document()` rebuilds the wire form, and a test asserts over
  every committed valid fixture that it rebuilds the document it was given exactly.
  A field the parser forgot to read is a field missing from the result; a field it
  defaulted is one that appears where the author wrote none. Absence is preserved
  for the same reason: an absent `proofRefs` and a declared empty one are different
  documents, both comply, and rendering one as the other would make a document say
  something its author did not write.
- **Contract-version handling that is explicit and first.** The supported
  `apiVersion` set is a constant with one entry, and a document declaring another
  version — or none — is refused before any field below it is read, because every
  field path this package knows is a path in `v1alpha1`.
- **A drift test between the published schema and the domain's copy of it.** The
  domain cannot import a JSON Schema validator, so the patterns, vocabularies, and
  bounds are written twice; `tests/domain/test_workload_schema_agreement.py` reads
  the schema and fails if a single one of them disagrees in either direction, and
  additionally deletes each *unconditionally* required field from a committed
  fixture in turn and requires a refusal at that field's own address. The
  conditionally required profile block is a cross-field rule and is deliberately
  not enforced.
- **The `unit` test layer, which was registered and empty since `V1-S0-006`, now
  runs.** Six of eleven layers exist. Its 271 checks cover what parses, what is
  refused, and what a refusal is allowed to say — including that no message repeats
  a value read out of the document, asserted over every string of eight characters
  or more in a refused document, and that a refusal carries the `requestId` and
  `correlationId` a caller supplied and invents neither.
- **A stated boundary, with tests that assert the absence rather than leaving it to
  be discovered.** This change implements **no** semantic validation rule: the
  profile and its block are not paired, an inverted replica range is not refused, a
  duplicate secret name is not detected, and no canonical error code or rule
  identifier is assigned. Those are the published semantic layer and they remain the
  complete property of
  [`tools/contract_validation/`](tools/contract_validation/) until `V1-S1-001-PR2`
  brings them into the domain. Two tests parse documents that the published rules
  refuse, so that the line cannot move quietly in either direction.

- **A decided inference API surface, one story before anything freezes against it**,
  in [ADR 0010](docs/architecture/decisions/ADR-0010-inference-api-compatibility-surface.md)
  and [the surface document](docs/serving/inference-api-surface.md). The user-facing
  API is a **frozen subset** of the OpenAI HTTP API shape at the `/v1` prefix: five
  endpoints, the request and response fields of each, and everything outside it
  recorded as out of scope with a reason rather than left unmentioned. This is the
  decision `V1-S1-002` would otherwise have made by guessing an adapter signature and
  `V1-S1-005` would have made by typing a route.
- **A compatibility target that is a shape read on a date, not a promise to track
  one.** The strongest objection to adopting a compatible surface is that it is not
  this project's to version, so upstream movement becomes a break imposed on it. The
  answer is the freeze: the field lists are enumerated here, read from the response
  bodies the runtime actually returned on 2026-08-24 rather than from vendor
  documentation, and anything upstream adds later arrives only if a superseding record
  decides it should. The project-native alternative is compared on six criteria rather
  than dismissed, and the criterion it wins is recorded as won.
- **Streaming and token usage as declared capabilities rather than assumptions.**
  Streaming is `false`, published where a caller can read it, and refused with an
  explicit `retryable: false` because retrying does not make a capability appear.
  Token usage is `true` on the strength of the `usage` object the trial recorded, and
  it is `null` rather than estimated or zero-filled when an adapter does not supply
  it. Whether the selected runtime *can* stream was never exercised by the trial, and
  the record asserts nothing about it in either direction.
- **A canonical error mapping in which one row was observed and eight are
  specifications**, marked either way, plus **six of the thirteen canonical codes
  recorded as never emitted in V1** — each with a reason, because a code listed with
  no condition behind it is a claim that something checks for it. A test refuses a
  code that is neither mapped nor refused, refuses one that is both, and refuses a row
  claiming an observation the feasibility record does not contain.
- **ADR 0002's `T7` exception carried forward as an obligation rather than discharged.**
  The selected runtime exposes no cumulative request counter, so InferOps owes one.
  This record binds `inferops_inference_requests_total` and
  `inferops_inference_errors_total` — which already exist in the telemetry catalog
  with that reason in their notes — to this surface and to these codes. It adds no
  metric, and neither is emitted by anything.
- **An extension namespace, and the two halves of it kept apart.** `x_inferops` is one
  object-valued body member carrying what the compatibility target has no place for;
  `X-InferOps-` is the header prefix carrying transport metadata. No request-body
  extension member is defined, because correlation and workload metadata belong in
  headers a trusted component validates. Every response names the `adapterKind` that
  served it, which is the mock and real boundary made visible at the one place a
  reader looks.
- **`tests/serving/test_inference_api_surface.py`**, 184 checks over the committed
  surface, the decision, the document, the feasibility record, and the telemetry
  catalog. It also refuses a contract artifact for this surface appearing under
  `contracts/`, which is the rule the whole record is built around: **nothing is
  published until something serves it.** Nothing in this
  repository listens on a port, registers a route, or answers a request.

- **A Python toolchain that was executed before it was accepted**, in
  [ADR 0009](docs/architecture/decisions/ADR-0009-python-toolchain.md). A packaging
  layout, a dependency manager, a lockfile policy, a linter, a formatter, and a type
  checker are each named, each configured in a committed file, and each run on this
  repository with its command and result recorded. This is the decision Sprint 1
  would otherwise have made by writing its first package, and the two halves of
  ADR 0001 that proposed a task runner and a dependency manager and never installed
  either are superseded by it.
- **A distribution that exists rather than a layout that is described.**
  `src/inferops/` is a deliberately empty package, and a wheel and a source
  distribution were built from it and their contents inspected. The wheel contains
  `inferops/__init__.py` and its metadata and nothing else; `tools/` and `tests/`
  stay outside it on purpose, and the source distribution's include patterns are
  anchored to the repository root because an unanchored one ships whatever it found
  at any depth.
- **A committed `uv.lock` with 136 artifact hashes**, resolved across environment
  markers rather than for the platform that ran the resolver, plus a
  `requires-python` constraint on the 3.12 series and a `.python-version` that pins
  the series rather than a patch release. The recorded way to run a check is
  `uv run --locked`, which fails rather than silently re-resolving.
- **A rejection recorded as a decision.** No task runner is adopted. ADR 0009 D7
  argues it out — ADR 0001's own record said the margin between its candidates was
  preference rather than capability, `uv run --locked` already supplies the command
  prefix a runner would have wrapped, and a runner does not ship the utilities its
  recipes call — and a test refuses a `Taskfile`, a `justfile`, a `Makefile`, a
  `noxfile.py`, or a `tasks.py` appearing without that record changing.
- **The record is checked against the configuration it decided.**
  `tests/testing/test_toolchain.py` reads the two tables ADR 0009 publishes and
  compares them against `pyproject.toml` and `uv.lock`. A dependency bumped without
  updating the record fails; a version typed into the record that the lockfile does
  not pin fails. It also asserts what did **not** move: `pyproject.toml` declares no
  pytest table, and the eleven markers and the default marker expression are still
  in `pytest.ini`.

- **A threat model in which a control cannot claim enforcement it does not have**, in
  [ADR 0008](docs/architecture/decisions/ADR-0008-v1-security-baseline.md) and three
  documents under `docs/security/`. Every control declares how it is verified and
  where it acts, and its status is the value a committed table gives for that pair —
  never a word somebody typed. A control naming an automated test names the file and
  the function, and the suite fails if the function is not defined; a control claiming
  an implemented status names an evidence record, and the suite fails if the record is
  not committed. The failure this exists for is not a false claim: it is a list of
  twenty controls, four of which have tests, being counted as twenty by a reader six
  months later.
- **Thirty-two controls, twenty-two of them enforced by something, and the split
  published.** Ten act over committed documents, ten over manifests, two on the host
  through the environment scripts, three by review alone, three are specified for
  components that do not exist, and four are deferred outright. The distribution is
  the finding, and no status that may be called implemented exists without a record
  behind it.
- **Eight pod-security assertions and a digest pin, promoted from habit to property.**
  Every YAML document under `deploy/` was already non-root, read-only-rooted,
  capability-dropped, seccomp-profiled, token-free, escalation-free, and pinned by
  digest. A test now parses every one of them and fails if that stops being true. What
  it establishes is stated exactly: these are properties of five committed files that
  are smoke and trial apparatus, and this platform deploys none of them.
- **Least exposure at the caller boundary, and no pretence that it is access
  control.** No manifest here declares an Ingress, a NodePort, or a LoadBalancer, and
  a test refuses one that would. Reaching anything needs a deliberate port-forward
  from a machine that already holds the cluster's credential. It identifies nobody and
  limits nothing once something is inside, which is why authentication and rate
  limiting are register entries rather than paragraphs.
- **A sixth trust boundary, for publication.** The architecture maps the five a
  running system crosses; this project crosses a sixth on every commit, and it is the
  only one whose failures cannot be undone. Four properties are tested at it: nothing
  generated is committed, no file carries a personal filesystem path, no file carries
  a model artifact extension, and the secret-scan allowlist resolves. The fifth thing
  a reader would assume is tested is not — **no run of the scanner is recorded**, and
  a configuration file is not a result.
- **A deferred-risk register that is long on purpose.** Twelve risks V1 carries rather
  than reduces — no authentication, no rate limit, no tenant validation, no network
  policy, no admission control, an unauthenticated artifact transport, no dependency
  lockfile, no image scanning, no artifact availability, no secret lifecycle, no
  recorded scanner run, and nothing logged at all. Ten of the twelve block production
  use. Each declares why, what would have to be true, and — the field that does the
  work — what may not be claimed while it stands.
- **Four exceptions argued rather than absorbed.** The model download's transport
  reports certificate validation as disabled; the cluster identity guard is satisfied
  by a second cluster given this project's name; the secret-scan allowlist covers two
  directories wholesale; and the pod-security properties hold over apparatus rather
  than over a serving path. Each names a compensating control that exists, what
  remains undefended anyway, and when it should be revisited.
- **Twelve reserved terms that may appear only inside a denial.** The adjectives of a
  posture rather than the names of properties, refused by a sentence-level test over
  **every Markdown document committed here** and the committed data. The first version
  read only the security documents, which would have passed while the top-level README
  or `SECURITY.md` described a posture this project does not have — the exact failure
  the baseline exists to prevent, occurring inside the control against it. A second
  test now fails if that coverage narrows.
- **Every count these documents state in prose is recomputed from the data.** A table
  row was already compared by identifier; a sentence saying "twenty-two of thirty-two"
  was compared by nothing. Ten such sentences now fail the suite if the data moves
  underneath them, which is the rule the cost method already applies to a figure.
- **Three trust boundaries that pointed forward now point at a record.** `B3`, `B4`,
  and `B5` in the system architecture were owned by "the security baseline decision".
  That decision now exists, and a test compares the two documents verbatim so they
  cannot drift.
- **One new public claim, at the narrowest level that is honest.** The claim and test
  matrix gains `a-security-control-cannot-claim-enforcement-it-does-not-have`,
  certified at C0 by the documentation layer and owned by security. It certifies a
  committed baseline and nothing about whether anything is defended. Two existing
  security claims stay `planned`, and a test now holds them there.

- **A cost method in which an estimate cannot become a bill by accident**, in
  [ADR 0007](docs/architecture/decisions/ADR-0007-inference-cost-method.md) and two
  documents under `docs/cost/`. Every amount declares a basis — an invoice, an
  allocation, or an estimate — and only an invoice-backed basis may carry the
  vocabulary or the reference of one. Two of the three bases are unreachable here and
  the method says why: `actual` needs a provider account this project has never had,
  and `estimated` needs utilisation telemetry no component emits.
- **Allocation by what a workload reserved, with the honest cost written down.** A
  workload is charged for its processor, memory, and accelerator requests times its
  replicas times the window, because reserved capacity is what the scheduler withholds
  from everything else and because it is the only quantity a validated workload
  document can supply. A workload reserving four cores and using a tenth of one is
  charged what a workload saturating four is charged, which makes these figures
  capacity accounting and not efficiency accounting.
- **Idle capacity as a line rather than an absence.** Capacity nobody reserved is
  reported separately, and the workload lines plus that residual must close against
  the machine exactly — a test requires it. In the worked example the residual is 69
  per cent of the node, the largest number on the page and the one both alternative
  treatments would have hidden inside a unit cost.
- **Confidence that is derived rather than asserted.** Four levels, six ceiling rules,
  and a derivation the suite recomputes from each record's own inputs. The consequence
  is stated rather than softened: every cost figure this project can produce today has
  confidence `none`, because the reachable basis is an allocation and the only rate
  card committed here is synthetic.
- **Prices committed, versioned, dated, and invented.** Nothing fetches a price at
  runtime, because a price that moves makes a figure irreproducible. One rate card is
  published, `synthetic-illustrative-v1`, whose every rate is made up and which says so
  inside the artifact rather than in the directory holding it. A provider card would be
  a number with the shape of evidence for a provider this project has never used, and a
  development host has no hourly price at all.
- **A missing input as a null with a reason, never a zero.** Six reason codes, a
  correspondence checked in both directions, and a minimum denominator — 100 requests
  or 10,000 tokens — below which a unit cost is null rather than a rate. Both minimums
  are recorded as declared rather than derived, because they are.
- **A worked synthetic example that is arithmetic rather than typing.** One hour, one
  node, two workloads, a residual, and a prerequisite storage line; every amount,
  share, and unit cost recomputed in exact decimal by
  [`tests/cost/`](tests/cost/). Money is a decimal string at a scale of six, rounded
  half-even once, and a test walks the whole method to establish that not one binary
  float appears in it.
- **A tenant identifier that cannot reach a committed record, by derivation.** Whether
  a cost-record field may appear in a record committed here is read from the
  sensitivity class the telemetry catalog already gave it, so `identity.tenantId` is
  absent from the worked example because its class has no evidence placement — not
  because somebody remembered to remove it.
- **One new public claim, at the narrowest level that is honest.** The claim and test
  matrix gains `a-cost-figure-cannot-be-presented-as-a-bill`, certified at C0 by the
  documentation layer. It certifies a committed method and nothing about what anything
  costs, because no component computes a cost record and no invoice has ever been read.

- **A telemetry catalog in which a field's placement is derived rather than chosen**,
  in [ADR 0006](docs/architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md)
  and two documents under `docs/telemetry/`. Every attribute declares a sensitivity
  class and a cardinality class, and its permitted placements are the intersection of
  what those two allow. The two content classes have an **empty** placement list, so
  "no prompt in telemetry" is arithmetic rather than a rule a reviewer applies to the
  seventh field somebody adds.
- **Thirteen metrics for seven required signal families, and a budget that is
  counted.** Availability, errors, latency, throughput, model load, tokens, and
  resource use each have at least one active metric; an eighth family, identity, is
  carried by a single `_build_info` gauge so that immutable versions are recorded
  without multiplying every other series by them. Each metric's maximum series count
  is recomputed by the suite from its labels and bucket count — 5,519 against a
  ceiling of 10,000 — so adding a label is a visible number in a diff.
- **Five fields refused as metric labels, each for a stated reason.** A correlation
  identifier because uniqueness is its purpose; a tenant identifier because a metrics
  store labelled by tenant is a customer list; a pod name and a workload version
  because both grow without bound over a retention window; a duration because a
  measurement is a value and never a key. Three of them are bounded and safe-looking,
  which is why the class does the deciding.
- **A log record with no free-form message field.** Records are identified by a
  bounded event identifier and carry named fields. Prose that varies per request is
  the field into which a caller's data eventually arrives, and the field no query can
  match on reliably.
- **The runtime's measured series, mapped, including the one that is absent.** Fifteen
  native series from the selected serving runtime are published with what each maps
  to, and a test compares every name against
  [the trial that measured them](docs/proof/serving/v1-s0-003-pr2-runtime-feasibility.md).
  The missing cumulative request counter — the threshold ADR 0002 records as failed —
  is recorded as absent, with the platform metric that covers it named beside it.
- **Content capture that has no flag to turn it on.** Prompts and responses are not
  captured, and enabling capture would need a classification, a redaction
  specification, a retention window, an access control, and a lawful basis with a
  deletion path. None exists, and a flag would have been the whole decision delegated
  to whoever set it during an incident.
- **Four evidence templates with seven mandatory sections**, under
  `docs/proof/templates/`, indexed by a new [`docs/proof/README.md`](docs/proof/README.md).
  Classification, provenance, environment, method, results, limitations, and
  authorisation, each checked by a test that reads the template. The experiment
  template registers the method and the failure condition before the run.
- **Two rules that admit they are enforced by review alone.** That an upstream error
  body is not passed through verbatim, and that no operating figure is published as a
  benchmark. Thirteen others name a test, and the suite fails if a rule names a test
  that does not exist.
- **One new public claim, at the narrowest level that is honest.** The claim and test
  matrix gains `the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label`,
  certified at C0 by the documentation layer. It certifies a committed document and
  nothing about a running system, because nothing in this repository emits a single
  signal.

- **A test and certification strategy that decides what a passing test may be used
  to claim**, in [ADR 0005](docs/architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
  and three documents under `docs/testing/`. Eleven test layers, four lanes,
  certification at C0 to C2, and a claim/test matrix in which every public claim names
  a test layer, an environment, a required level, and an evidence owner. Nine of
  eighteen claims are certified today and each cites a record already in this
  repository.
- **The mock boundary as a mechanism rather than a rule.** Each layer declares what it
  runs against as an evidence class, and each class carries a hard ceiling on the
  certification level a result from it may support. A mock stops at C1. Three tests
  enforce it: no layer may certify above its class, no claim requiring C2 may be
  satisfied by a mock or a simulation, and a layer labelled with an unreal class may
  not also declare that it needs a real model. The rule was already accepted in words;
  this is the first time it holds without anybody remembering it.
- **A committed pytest configuration whose default lane cannot run a real model.**
  [`pytest.ini`](pytest.ini) registers a marker for every layer, refuses an
  unregistered one, and deselects `cluster`, `realruntime`, `failure`, and `load` by
  default. A test compares that expression against the strategy in both directions: a
  marker belonging to a layer outside the default lane must be excluded, and a marker
  belonging to a layer inside it must not be. Seven of the ten markers currently select
  nothing, because the layers behind them have no code, and the strategy says so
  rather than implying otherwise.
- **A check that catches the mistake the other checks cannot.** Every test module under
  a layer's declared paths must carry that layer's marker at module level, because a
  marker nothing is marked with selects nothing, silently. The markers and the strategy
  can agree perfectly while `pytest -m contract` collects zero tests.
- **An evidence retention rule with a boundary in it.** A lane's raw output expires —
  30 days for the cheap lanes, 90 for the expensive ones — and may never be cited as
  the evidence for a published claim. A record that certifies a claim is committed
  under `docs/proof/` and kept for as long as the claim stands. Raw output a claim
  depends on is promoted into such a record, redacted, before the window closes. Two
  tests hold the line: a claim may cite a record only when it is certified, and a
  certified claim may rest only on layers that are actually implemented.
- **A capacity lane that is defined precisely so that it stays shut.** V1 may publish
  no throughput, latency, capacity, or benchmark figure. The load layer, its lane, and
  the claim it would support are all written down and all deferred, so publishing a
  capacity figure means deleting a deferral in three places rather than adding a test.
- **Two deliberate refusals to overclaim.** A lane may call itself automated only by
  naming a workflow file that exists, and no workflow file exists — so every lane is
  recorded as run by hand. And the security-scan layer is recorded as `planned` rather
  than `implemented`, because a committed scan configuration is not a recorded run.
- **Forty-three deliberate corruptions, each refused.** Mutations across the strategy
  data, the pytest configuration, the three published documents, and an existing test
  module were applied one at a time; every one failed the suite. They are listed by
  category in
  [the change validation record](docs/proof/testing/v1-s0-006-pr1-validation.md).

- **A V1 system architecture**, in six diagrams with the narrative behind each:
  system context, components and the direction dependencies may point, the
  inference request flow including what happens when the model is not ready, the
  workload deployment flow with ownership bands, the telemetry and evidence flow,
  and a trust boundary map. Every component below the contract layer is marked
  unbuilt, because it is.
- **A resource ownership inventory as data, not prose**, under
  `docs/architecture/`. Thirty resources, each with exactly one owner, a lifecycle,
  what creates and destroys it, which teardown operations it survives, who
  references it without owning it, and the handoff rule that applies at its edge.
- **A test suite that makes the ownership boundary a property rather than an
  intention.** It asserts single ownership, that the Terraform and Helm sets do not
  intersect, that a resource's lifecycle is one its owner actually has, that no
  resource claims to survive the operation that destroys it, that a survival list is
  a prefix of the teardown blast-radius ordering — the check that catches a
  plausible-looking claim rather than a malformed one — that prerequisites outlive
  releases and release resources do not outlive prerequisites, that a derived object
  has no tool owner, that a resource with no owner is deferred out of V1, that
  evidence is cited only by rows marked implemented, and that the ownership document
  and the data publish the same identifiers in both directions.
- **ADR 0004**, deciding component decomposition and dependency direction, the
  serving runtime as a separate deployment rather than a sidecar, the
  Terraform/Helm/controller ownership split, the model cache as a prerequisite, the
  trust boundary map, and where this project stops — after comparing a
  Helm-owns-everything layout, a Terraform-owns-everything layout, a GitOps
  controller, Kustomize, a Kubernetes controller with a custom resource, and four
  placements for the model cache.
- **An explicit non-decision inside that record.** Nobody owns a telemetry
  collector, and nobody owns an ingress controller or load-balancer implementation.
  Both are recorded with an `undecided` owner and deferred, and a test refuses to
  let an unowned resource sit inside V1 scope.
- **An overlap found by drawing the boundary, and specified rather than fixed.** The
  accepted cleanup rules let a label-scoped teardown delete any project-labelled
  object, which would put a Terraform-owned prerequisite inside the blast radius of
  a routine partial teardown. It is not a live defect — the implemented teardown is
  bound to one smoke-test namespace — and the resolution, a lifecycle label a sweep
  must exclude, is written down as a constraint on work that has not started. It is
  implemented nowhere, the environment scripts are unchanged, and it is carried as
  an open risk rather than as a fix.
- **A project boundaries document**, stating that this project owns exactly two
  serving capabilities, that standing in front of a choice of providers is gateway
  work, that engineering the runtime's own behaviour is deeper serving work, and
  that V1 may publish no throughput, latency, capacity, or benchmark figure at all.
- **A boundary review checklist** of twenty-six questions across ownership,
  component boundaries, serving and evidence claims, scope, and public safety — the
  human half of a boundary whose mechanical half is a test.
- **Enforcement of the workload-contract rules JSON Schema cannot express.** A
  semantic validation layer above the published schema now applies replica-range
  ordering, a runtime and model compatibility matrix, duplicate secret names, the
  rule that a mock may not declare a credential, and a heuristic that refuses a
  secret pasted into a locator field. Two of these were published as *not enforced*
  when the schema landed and are enforced now; the pasted-secret rule was published
  as *partly* enforced and is now enforced as far as a shape heuristic can reach,
  with the remaining gap measured and tested rather than described. Rules that
  remain unenforced are still named in the same table that states them.
- **A published rejection interface for the contract.** Every refusal carries a
  canonical error code, a stable rule identifier, and a field location such as
  `$.spec.security.secretRefs[1].name`. All fifteen rules are listed in the
  contract document, and a test fails if the validator can cite one the document
  does not publish.
- **Sixteen invalid fixtures**, each with its expected code, rule, field, and
  validation layer committed beside it. The manifest is compared field by field on
  every run, so a change to what a consumer is told fails the build instead of
  passing as a refactor.
- **A test that checks which layer refuses each fixture.** A fixture marked
  `semantic` must be *accepted* by the bare schema; if the schema ever grows strict
  enough to refuse one, that is a strengthening and a compatibility event rather
  than a silent improvement. Seven of the sixteen fixtures are semantic-only
  today, which is the measured cost of validating against the raw schema alone.
- **A runtime and model compatibility matrix**, as data rather than code. It
  records what each serving runtime loads, marks vLLM's CPU backend as a recorded
  fallback nobody has run, deliberately omits vLLM's experimental GGUF path
  because no trial supports listing it, and carries exactly one executed pair —
  the runtime digest and model revision ADR 0002 selected, tied to its feasibility
  record by a test.
- **Compatibility classes for contract changes: compatible, conditionally
  compatible, and breaking.** The middle class is the addition. It names the
  changes that get merged as harmless and discovered later — a new semantic rule, a
  narrowed matrix row, a moved error code — and requires each to be announced.
- **Fixture ownership rules.** A fixture belongs to the rule it demonstrates: a new
  semantic rule must add one, a removed rule takes its own with it, and a valid
  fixture is never edited to make a change pass.
- A command-line entry point, `python -m tools.contract_validation`, for validating
  a document that is not a committed fixture. Sorted output, exit `1` on refusal.
- A change-validation record for this change, listing all sixteen refusals with
  their layer, measuring the credential heuristic in both directions — what it
  catches, what it deliberately leaves alone, and what it still misses — examining
  every credential-shaped string the change commits, and recording the seven
  defects a second review found in its own first draft.
- Identical findings are collapsed, and findings sort by array index as a number,
  so `secretRefs[10]` follows `secretRefs[2]` rather than preceding it.
- An offending annotation key is named in a field location only when it is short
  and does not itself look like a credential. `metadata.annotations` is the
  contract's one open map, so its keys are as author-controlled as any value.

- **The first public contract: WorkloadContract `v1alpha1`.** A JSON Schema draft
  2020-12 document under `contracts/workload/` covering workload identity, owner,
  profile, environment, model and runtime reference, resources, replica bounds,
  platform integrations, security classification, secret references, attribution,
  and evidence links. It describes a workload; nothing in this repository reads one.
- A closed additional-property policy on every object in that schema, so an unknown
  field is a validation error rather than a silently accepted typo, and a test that
  fails if any object is ever added without declaring its policy.
- Structural pinning for the real serving profile: the runtime image by digest, and
  the model by upstream revision **and** per-file content hash. The valid fixture
  carries the exact digest and revision ADR 0002 selected, and a test fails if the
  fixture and the accepted decision ever disagree.
- A `mock-llm` profile that cannot be edited into something that reads as real
  serving: the schema confines it to the `ci` environment and the mock serving
  capability, requires it to label itself in its own contents, and caps its
  real-runtime proof references at zero. Three tests assert each rejection.
- A secret-reference block requiring a provider, a locator, an owner, and a rotation
  responsibility — and no field anywhere in the schema that a secret value could be
  written into.
- `metadata.annotations` as the contract's single, explicitly non-normative
  extension point, with keys namespaced to a DNS domain.
- Published versioning and compatibility rules for the contract, including the
  deliberate refusal of the usual alpha licence to break compatibility freely: a
  breaking change gets a new `apiVersion` even at alpha maturity.
- A rejection table that names, for every rule the platform must enforce, whether it
  is enforced by the schema today or is not yet enforced at all, and maps each to its
  canonical error code.
- Valid fixtures for the `synchronous-llm` and `mock-llm` profiles, a
  secret-reference shape example, and a deterministic mock chat-completion response
  fixture that identifies itself as a mock from its own contents.
- A deterministic contract test suite under `tests/contracts/`, reading only files in
  this repository: no network, no cluster, no model, no clock, no randomness.
- ADR 0003, selecting JSON Schema draft 2020-12, YAML authoring restricted to the
  JSON-representable subset, an off-the-shelf conformant validator, and no code
  generation in V1 — after comparing CUE, OpenAPI schema objects, Protocol Buffers,
  Kubernetes CRD schemas, and draft-07.
- A contract-package changelog, versioned separately from the project.
- A change-validation record for this change, including a thirty-four-mutation
  rejection spot check whose three accepted mutations are the three rules the
  contract document already declares unenforced, and a measurement of how much of
  the secret-locator gap the schema's pattern already closes — which turned out to
  be more than the first draft claimed for padded base64 and less than it claimed
  for alphanumeric credentials.
- Public repository purpose and status without functional capability claims.
- MIT license and contribution, review, commit, conduct, and release conventions.
- Public indexes for prerequisites, contracts, architecture decisions, and governance.
- Security-reporting expectations, including the unresolved private-channel blocker.
- Reproducible POSIX and PowerShell documentation link checks in the contribution guide.
- A pull-request template covering scope, decision impact, validation, and evidence.
- An explicit record that no public maintainer roster or `CODEOWNERS` file exists yet.
- A decision-record convention and index under `docs/architecture/decisions/`.
- ADR 0001, comparing alternatives for the container runtime, the local Kubernetes
  distribution, the task runner, how dependencies are installed, how the project's
  workspace stays isolated, how it is torn down, and what a host needs. Added as a
  proposal; see **Changed** below for the status it now holds.
- A redacted inventory of the one development host measured for that decision, with
  every row marked as either measured or documented.
- Minimum and recommended CPU, memory, and disk figures, kept separate from the
  prerequisites this repository actually supports.
- A stated verdict that the one measured host does not meet the recommended tier,
  rather than an estimate left unchecked against the evidence beside it.
- A reproducible local development cluster: prerequisite checks, cluster creation
  from a digest-pinned node image, a hello-world smoke test verified from inside
  the cluster, scoped teardown, and residue verification, under
  `scripts/environment/` and `deploy/`.
- A runbook for that cluster, including what it creates, what survives teardown,
  and what it does not establish.
- Real-runtime evidence that the cluster can be created, exercised, and removed
  repeatably on one Windows host, including four attempts to make the teardown act
  outside its own cluster, all of which were refused.
- ADR 0002, comparing serving runtimes and open models against the memory, disk,
  and instruction-set limits the cluster evidence measured. Added as a proposal
  that selects nothing: it names a proposed primary and a recorded fallback for
  both runtime and model, and states what would have to be measured to accept
  either.
- Twelve numbered pass/fail thresholds, fixed before any candidate is run, and
  separated into those that disqualify a candidate outright and those that send the
  trial to a smaller model first.
- A dated source table behind every third-party claim in ADR 0002, so that a reader
  can tell a vendor-documented characterisation from a tested one.
- A bounded feasibility workflow for the trial that would settle ADR 0002:
  authorisation gate, download and free-space budgets, a stage-by-stage procedure,
  a one-step step-down rule, explicit abort conditions, and a statement of what the
  workflow cannot establish even when it passes.
- An evidence template for recording that trial, requiring an explicit verdict
  against every threshold, both attempts when a step-down occurs, and a section for
  what went wrong.
- **A real inference, served locally.** A serving runtime was started in a
  Kubernetes cluster, loaded an open model whose bytes were verified against the
  publisher's published SHA-256, and answered chat-completion requests reaching it
  through cluster DNS and a Service. Recorded in the V1-S0-003-PR2 feasibility
  record with the runtime's verbatim response, its reported token counts, and every
  measurement behind the verdicts.
- Trial manifests under `deploy/serving/feasibility/` — namespace, weight-cache
  claim, a resumable and hash-verifying acquisition job, the runtime Deployment
  pinned by image digest, its Service, and an in-cluster probe job. They are
  apparatus for the trial, not a serving path, and say so in their own comments.
- Tested hardware requirements for serving this model with this runtime, replacing
  estimates: AVX2 without AVX-512, no accelerator, a 3 GiB pod memory limit against
  a 2.167 GiB worst-case charge, ~2.0 GiB of disk, and a 14 s worst-case model load.
- A change-validation record for this change, kept separate from the runtime
  evidence so that a static check can never be mistaken for a served request.
- A published rule for the boundary between mock and real serving evidence,
  explaining why a mock can never certify real runtime behaviour, what a mock is
  legitimately for, and five boundary rules that make the distinction operational.

### Changed

- The architecture summary, claim/test matrix, and root status table now describe
  the API's emitted metrics, structured records, and enforced redaction boundary
  without overstating them as deployed or real-runtime evidence.
- **Unsupported caller generation controls are now refused rather than silently
  ignored.** ADR 0010 narrows the V1 chat request subset to `model`, `messages`,
  and optional `stream`; `max_tokens` and `temperature` now follow the strict
  unknown-member policy. The deployment-wide `INFEROPS_MAX_OUTPUT_TOKENS` setting
  remains an adapter configuration. The versioned surface JSON is formally
  designated and tested as the canonical API snapshot without claiming OpenAPI,
  JSON Schema, generated-client compatibility, or an artifact under `contracts/`.
- The four broken relative links in the V1-S1-001 PR2 validation record now resolve,
  and the contributor guide accurately describes the repository's narrowly coded
  test-only `# type: ignore[...]` directives.
- **The telemetry catalog moved off `nothing-emits`.** `emissionStatus` now reads
  `partially-emits`, names the emitter and the transport, and every metric carries
  an `emission` field so that a reader learns what is really there from the record
  rather than by scraping and comparing. Five active metrics are marked
  `not-emitted` with a reason each: four belong to the serving-runtime adapter or
  the contract validator, neither of which is instrumented, and
  `inferops_process_resident_memory_bytes` is the API's own and has no source this
  distribution may read — the only per-process memory figure the standard library
  exposes is a file, and no module under `src/inferops` may read one. The endpoint
  names that absence in a comment rather than publishing a zero, because a zero
  would be a measurement claiming the process holds no memory.
- **The catalog gained two attributes it did not have, because it predates the
  API.** `inferops.request.id` — the identifier the API mints at the edge and
  echoes in a header and in every response body — was unpublished, so a record
  could not be joined to the response a caller holds; it is classified like the
  correlation identifier, so it is a log field and never a label.
  `inferops.adapter.kind` is a two-valued identity attribute, so it reaches metrics
  only through the identity metric. Neither changes the cardinality budget.
- **Three rules the catalog previously stated are now enforced by a test**, and are
  recorded that way rather than left claiming less than they do: an emitted signal
  agrees with the catalog, an emitted label is one the catalog permits, and an
  emitted record carries only published fields. The two rules enforced by review
  alone stay review-only, including the one about upstream error bodies — the API
  already refuses to forward an adapter's words, and the rule is about an adapter
  that is not instrumented yet.
- **`DR-12` in the deferred-risk register is narrowed rather than closed.** A
  logger, a formatter, and a redacting sink now exist and real records are
  inspected. No log store, shipper, retention window, or access rule does, so
  nothing is reconstructible and no auditability property is claimed.
- **`DR-01` in the deferred-risk register records what the absent authentication
  boundary now costs.** `/metrics` sits behind it and published nothing at all
  before this change; it now publishes the build, capability, release, environment,
  adapter kind, model identity, runtime identity, and image digest of the
  deployment, plus live operational counters. No control is added and the entry is
  not reopened — a register that describes what a missing control costs has to be
  updated when the cost grows, not only when it is paid.
- Three living documents that said this repository emits nothing —
  `CONTRIBUTING.md`, the inference API document, and the API surface document — are
  corrected. `ADR 0006` is deliberately **not** edited: an ADR is a decision at a
  date, and the catalog's `emissionStatus` is where that record itself said the
  question would be settled.

- **The contributor guide no longer says two markers select nothing.**
  `mockintegration` acquired code in `V1-S1-005-PR1` and `realruntime` in
  `V1-S1-004-PR2`, and the test-lane section still listed both as empty. The
  correction says which story gave each one code, and it says of `realruntime`
  what the strategy already says: the suite is written and has never been run
  against a runtime. The same section now records that a new test module must be
  inventoried, and that a change adding, renaming, moving, or removing any test
  module anywhere in the tree has to pass `tests/testing`.

- **The accepted inference API surface no longer says nothing serves it**, because
  something does. `implementationStatus` moves from `nothing-serves` to
  `served-in-part`, each endpoint names what serves it and what about it is
  unfinished, and the suite that checked "nothing serves this" now checks the
  record against the code that implements it, in both directions. What has not
  changed is the part that matters most: no OpenAPI document, no request or
  response schema, and nothing added to [`contracts/`](contracts/). Serving a shape
  and publishing it as something a client may bind to are different acts, and only
  the first has happened.
- **`DR-07` is narrowed rather than retired, and its control stays deferred.** The
  register entry used to say no dependency lockfile and no packaging manifest
  existed; both now exist, so that half is gone. The half that remains is stated
  instead: nothing here observes which inputs a check actually resolved, the
  non-Python tools are pinned by prose rather than by the lockfile, and no
  dependency scanner has ever been run. `pin-every-dependency-with-a-committed-lockfile`
  therefore keeps its `deferred` status, because a committed file is not a result.
  Twelve risks, thirty-two controls, and every published count are unchanged.
- **The publication boundary now knows about `.venv/`, `build/`, and `dist/`.** The
  security suite walked all three as candidates for publication, so a project
  virtual environment created by the newly adopted dependency manager would have
  failed two of its checks on files belonging to third-party packages. All three are
  ignored by version control and the test that says so now covers them.
- **Four Python files were edited to satisfy the linter and the type checker**, and
  none of them changed behaviour: two list concatenations, one if-else assignment, a
  generator annotated as returning `object`, a `sum()` with no typed start value, and
  a validator keyword the stubs type as possibly unset being used as a dictionary
  key. The suite passes with the same test count it had before.
- **Four records that a second review found disagreeing with themselves.** Narrowing
  `DR-07` left the threat that references it, `T-19`, still saying that no lockfile
  and no packaging manifest exist — a single machine-checked JSON document
  contradicting itself, with no test cross-checking a threat's prose against the risk
  it links to. The architecture index's status line said "one accepted" above a table
  listing two. The governance index still reported ADR 0001 D3 and D4 as proposed and
  unrun, and now carries two rows because the two halves are decided in opposite
  directions. And the toolchain validation record contradicted its own command
  output by one test. ADR 0009 D9 is also relabelled from "Not decided" to "Accepted
  as a boundary", the status ADR 0003 D6 already established for a scope statement,
  with the record saying why its own status is `Accepted` rather than `Accepted in
  part`. The service behind D9 remains undecided.
- **`uv.lock` is pinned to LF in `.gitattributes`**, for the same reason the
  existing shell-script rule is there: `uv` writes it with LF on every platform, and
  a Windows checkout under `text=auto` would receive CRLF and have the whole file
  rewritten by the next `uv lock`.
- **`pytest.ini` and `conftest.py` carry accurate reasons.** Both explained
  themselves by reference to a packaging decision that had not been made. Both now
  explain themselves by reference to the one that has: the pytest configuration
  stays where it is because ADR 0005 made it load-bearing, and the root `conftest.py`
  stays because `tools/` is deliberately outside the distribution.

- Two deferrals in the telemetry catalog keep their status and lose a reason that is no
  longer true. `inferops.cost.record.id` and `inferops_cost_records_total` were
  deferred on the grounds that no cost method existed;
  [ADR 0007](docs/architecture/decisions/ADR-0007-inference-cost-method.md) defines
  one, so both are now deferred on the accurate grounds that nothing computes or emits
  a cost record. No name, class, placement, or budget changes, and neither signal
  becomes active.
- Three existing test modules now declare the marker of the layer that owns them.
  No assertion in them changed, and `python -m pytest tests -q` collects and reports
  exactly what it did before, plus this change's own suite.
- CONTRIBUTING gains a lane and marker section, a strategy-suite section, and a
  pointer from its evidence vocabulary to the ceiling each label carries. The two
  vocabularies are reconciled where they differ rather than left to contradict each
  other: `local-static` is added for a deterministic check over repository files, and
  `production experience` is recorded as a label V1 cannot reach rather than silently
  dropped. The statement that no continuous-integration lane is selected is unchanged,
  because it is still true.
- The governance decision table records the test and certification strategy as
  accepted in part, and records the continuous-integration service and capable-runner
  labelling as not selected rather than leaving them unmentioned.

- The architecture index no longer says that no infrastructure ownership boundary
  and no application architecture is selected. Both are now selected, for components
  that do not exist, and the index says that too.
- The governance decision table records the component and ownership boundary as
  accepted in part, and records telemetry collection and ingress ownership as not
  selected rather than leaving them unmentioned.
- The contribution guide gains the architecture suite, what it checks, and the
  explicit statement that it checks a design commitment rather than an
  implementation.
- **A contract validation message no longer repeats any value read out of the
  document.** The underlying validator embeds the offending value in its own
  message; the contract validator now writes its own text instead, because the
  field most likely to be refused for looking wrong is the field most likely to
  hold a secret, and an error body is the surface most likely to be logged, pasted
  into a ticket, and kept. A test asserts it for every invalid fixture.
- The workload-contract rejection table gains a layer column and a rule
  identifier for every row. Of its five incompletely enforced entries, the replica
  range and the runtime and model combination move from "not yet" to enforced, and
  the pasted secret moves from "partly" to a semantic check whose limits are
  measured. The remaining two — undeclared required capability and policy
  exception — are unchanged, and are now stated as blocked on a named missing
  capability rather than merely deferred.
- The contracts index no longer lists a compatibility matrix among the artifacts
  that do not exist, and says how the matrix that now exists is narrower than the
  cross-project one the integration specification calls for.
- The contracts index moves from "no public contract accepted" to indexing one
  accepted contract, and now requires an entry to state which of its rules are not
  yet enforced in the same place it states the rule.
- The repository entry points and status banner record one published contract schema
  and keep saying that no component consumes it.
- The decision-record conventions now name the `ADR-NNNN-short-slug.md` filename
  form the records already use.
- The contribution guide gains the contract-schema validation commands and the
  packages they need, alongside the existing shell and manifest checks.
- ADR 0002 moves from proposed to **accepted, with one recorded exception**. One
  runtime image digest and one immutable model revision are selected, with source
  and licence for each, on executed proof. Everything written before the trial is
  preserved unedited, including the thresholds the trial went on to fail.
- The decision-record conventions define `Accepted, with one recorded exception`,
  which requires the failed criterion to be named in the record's status banner,
  argued where a reader will find it, and listed among the consequences.
- The feasibility workflow moves from "never been run" to executed, and four parts
  of it were corrected by running it: the cluster bound now permits a single-node
  local cluster the host already runs; the 30-minute stage bound is split so that a
  bulk transfer is bounded by size and retries rather than by a wall clock; the
  free-space bound now requires measuring the host volume rather than a container's
  view of a sparse virtual disk; and the claim that cached weights survive teardown
  is corrected to say that where the cache lives decides it.
- The architecture index, repository entry points, and prerequisites now describe a
  selected runtime and model instead of an unexecuted comparison, and the
  prerequisites carry measured serving figures with their limits stated.
- The two architecture decision records are renamed to an `ADR-` filename prefix.
  Contents are unchanged by the rename and every reference to them was updated.
- ADR 0001 moves from proposed to **accepted in part**. The container runtime, the
  local Kubernetes distribution, the isolation rules, the cleanup rules, and the
  minimum host tier are accepted on executed evidence. The task runner, the
  dependency installation approach, and the recommended host tier are not, and stay
  proposed.
- The minimum host tier's CPU, memory, and disk figures are now measured rather
  than estimated, and its description no longer mentions a mock serving path that
  does not exist. The recommended tier remains an estimate.
- The container virtual machine's memory ceiling is measured at 7.60 GiB, replacing
  the assumed platform default, and the risk that recorded it as unmeasured is
  closed.
- Prerequisites now state a supported local development environment alongside the
  documentation path, and separate both from serving, which remains unsupported.
- The decision-record conventions define `Accepted in part`, which requires a
  per-decision status table.
- The architecture index, the repository entry points, and the prerequisites now
  point at the model and serving-runtime evaluation and say plainly that it selects
  nothing. Serving remains unsupported, and the prerequisites gain no new tool.

### Fixed

- **A caller-supplied identifier ending in a newline was accepted and echoed into
  a response header.** Python's `$` matches at the end of a string *or immediately
  before a single trailing newline*, so `IDENTIFIER.match()` against a `^...$`
  pattern accepted `"req-abc123\n"` and returned it unchanged — into
  `X-InferOps-Request-ID`, which is a header injection rather than an identifier,
  and which that module's own docstring said the pattern existed to prevent. The
  defect predates this change; it is fixed here because this change is what began
  writing those identifiers into every log record. The pattern lost its anchors and
  is matched with `fullmatch`.
- **The same defect in the metric-label validator**, which every telemetry
  environment variable and every label value passes through. A value ending in one
  newline was written raw between quotes into the exposition, splitting a sample
  line in two — and a scraper rejects the whole target rather than the one series,
  so a trailing newline in `INFEROPS_RELEASE_ID` would have blacked out a
  deployment's metrics for the life of the process. Same fix, and both patterns are
  now anchorless and matched in full so the two cannot drift apart.
- **A failing log sink stranded the in-flight gauge and failed the request.** The
  gauge was raised outside the `try` whose `finally` lowers it, so a sink raising
  between the two left it raised forever and took the request with it. The
  increment moved inside the guarded region, and — the load-bearing half — a sink
  failure is now caught, counted, and not raised: a deployment that refused every
  caller because its log destination went away would be telemetry deciding
  availability. A record that fails to *build* still raises, because the allowlist
  refusing a forbidden field is the error that may never be swallowed. The scrape
  names a non-zero drop count.
- **A scrape read the live series rather than a snapshot**, so a scrape concurrent
  with an observation could publish a histogram whose `count` had advanced past the
  `sum` beside it. `Metric.samples()` now takes an immutable reading inside the
  lock, and `series_count` no longer reads outside it.
- **The registry enforced the placement rule on operational metrics and claimed
  both kinds.** An identity metric skipped the label check entirely, so
  `MetricSpec(identity=True, labels=(CORRELATION_ID,))` would have constructed —
  while the module said a correlation identifier "cannot become a label by being
  passed to a constructor". It was an overclaim before it was a bug: nothing
  emitted such a label. The permitted set is now derived per metric kind and both
  are checked.
- **A test that could not fail.** The latency check advanced its clock by zero and
  asserted a duration was non-negative, which the production code guarantees by
  clamping. It now drives an adapter that advances the monotonic clock while
  serving and asserts the histogram sum, the record's duration, and the buckets the
  observation lands in.

- Threshold `T7` was too broad as written. It bundled "the runtime exposes native
  metrics", which is the runtime's job, with "the runtime counts requests", which is
  not. The selected runtime provides native token counters and no cumulative request
  counter, so the threshold failed; it is narrowed for future trials and the
  request count becomes an obligation on this platform. The narrowing happened after
  the measurement, and ADR 0002 records that weakness rather than hiding it.
- Two teardown claims that the evidence contradicted: the engine's virtual disk
  does not return space to the host when a cluster is deleted, and a cluster
  identity check based on a Kubernetes node label does not work, because the label
  is on the node container rather than on the node object.
- Defects in the environment scripts that review found and that every passing run
  had hidden: the diagnostics collector could never run, because an `ERR` trap is
  not reached when a failure occurs inside a shell function; the residue verifier
  certified a clean teardown when the container engine was merely unreachable; the
  cluster identity guard did not cover the default teardown path; and the node
  image digest read-back compared the pin against a value that is only
  incidentally equal to it.
- Slow and nondeterministic failure behaviour in the smoke test: a failed
  verification now reports in about 25 seconds rather than after a 180-second
  timeout, and job retries are disabled so the assertion always reads the log it
  was meant to read.
- Argument handling on the destructive scripts: a second, ignored argument and a
  valueless `--cycles` are now refused rather than silently doing something other
  than what was asked.

ADR 0001 is accepted only for what was executed, on one Windows host, one
architecture, one point in time. Linux and macOS remain untested. No model, serving
runtime, inference, benchmark, ingress, or load-balancing behaviour is proven by
any entry above, and no V1 product capability or versioned release is included.
