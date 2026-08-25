# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project intends to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once versioned releases begin.

## [Unreleased]

### Added

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
