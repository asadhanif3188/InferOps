# ADR 0003: Workload contract schema tooling

| Field | Value |
|---|---|
| Status | **Accepted** |
| Date proposed | 2026-08-24 |
| Date accepted | 2026-08-24 |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | None |
| Superseded by | None |

## Context

The project is about to publish its first machine-readable contract. Before a
schema file exists there is a decision to make that is easy to make accidentally:
what language the schema is written in, what form authors write instances in, how
instances are validated, and whether code is generated from the schema.

Making that choice by typing a file extension would be the wrong way to make it.
Once a contract is published, its schema language is load-bearing for every
consumer that validates against it, and changing it later is a migration rather
than a refactor.

Two constraints come from outside this record. The contract has to be validatable
without a cluster, a model, or a network, because a contract check that needs any
of those will be skipped. And [the contribution guide](../../../CONTRIBUTING.md)
records that no repository task runner or continuous-integration lane is selected
yet, so whatever is chosen here has to be runnable by hand today.

## Decision

### D1 — Schema language: JSON Schema, draft 2020-12

**Accepted.** Contract schemas are JSON Schema documents at draft 2020-12.

### D2 — Authoring form YAML, wire form JSON

**Accepted.** Instances are authored in YAML, restricted to the JSON-representable
subset: no anchors required for meaning, no non-string keys, no implicit dates, no
tags. JSON is the wire form. A test asserts the restriction rather than trusting
it.

### D3 — Validation by a standards-conformant validator, not a bespoke checker

**Accepted.** Structural validation is performed by an off-the-shelf draft 2020-12
validator. The reference implementation used in this repository is the Python
`jsonschema` package, driven from `pytest`. Neither is vendored, matching how
`shellcheck` and `kubeconform` are already treated.

### D4 — No code generation in V1

**Accepted.** No types, clients, or stubs are generated from contract schemas
during V1. Schemas are validated, not compiled.

### D5 — Schema identifiers are namespaces, not retrieval URLs

**Accepted.** Every contract schema carries an `$id` under
`https://inferops.io/contracts/...`. Nothing is served there. Validators resolve
schemas from this repository.

### D6 — This is not the repository-wide toolchain decision

**Accepted as a boundary.** Choosing `pytest` to drive contract validation does not
select the project's Python packaging, linting, typing, or test toolchain, and does
not select a continuous-integration lane. Those remain open.

## Alternatives considered

### Schema language

| Alternative | Why not |
|---|---|
| **JSON Schema 2020-12** | **Selected.** Widest validator availability across languages; `$defs`, `$ref`, and applicator keywords cover the structure this contract needs; the vocabulary a Kubernetes-adjacent audience already reads |
| JSON Schema draft-07 | Better legacy tool support, but no `$defs`/`$dynamicRef`, weaker applicator semantics, and it starts the project one migration behind |
| OpenAPI 3.1 schema objects | Aligned with the future model-access API, but an OpenAPI document is an API description. A workload contract is a document, not an endpoint, and it would have to be extracted before use |
| CUE | Genuinely better at cross-field constraints — the exact rules JSON Schema cannot express here. Rejected on reach: it requires every consumer to adopt a language most have not, for a contract whose whole purpose is to be easy to consume |
| Protocol Buffers | Strong codegen and wire efficiency; poor fit for a hand-authored declarative document, and it makes optionality and unknown-field policy harder to state, not easier |
| Kubernetes CRD OpenAPI v3 | The natural end state if InferOps becomes a controller. Premature: it would bind the contract to a Kubernetes API server before any component reads a contract at all |

The deciding consideration is that this contract is written by humans and read by
tools in several languages. JSON Schema is the only candidate that is native to
both.

### Authoring form

| Alternative | Why not |
|---|---|
| **YAML authoring, JSON wire** | **Selected.** Comments matter in a document a team maintains, and the integration specification already describes the contract in YAML. JSON stays the interchange form |
| JSON authoring | No comments. A contract fixture that cannot explain a pinned digest is a fixture that will be pinned wrongly |
| YAML with the full feature set | Anchors, tags, and implicit typing produce documents that differ between loaders. Restricting to the JSON subset removes a class of bug for a cost nobody will notice |
| TOML | Poor fit for the nesting depth here |

### Validation approach

| Alternative | Why not |
|---|---|
| **`jsonschema` driven from `pytest`** | **Selected.** Already conformant, already deterministic, and it lets the schema, the fixtures, the fixture-to-ADR links, and the mock boundary be asserted in one place |
| `check-jsonschema` command-line only | Simpler to invoke, but it only answers "does this instance validate". It cannot assert that a fixture's digest matches the accepted ADR, or that a mock cannot be edited into a real contract |
| `ajv` under Node | Equally conformant. Rejected to avoid introducing a second language runtime for one check; the repository's `.gitignore` already anticipates Python |
| A hand-written validator | Every argument for a hand-written validator is an argument that ends in maintaining a worse one |

Nothing prevents adding a command-line validator later for consumers who do not
want a Python dependency. That is an addition, not a reversal.

### Code generation

| Alternative | Why not |
|---|---|
| **None in V1** | **Selected.** No component reads a contract yet, so generated types would have no consumer and would still need a generator, a pinned version, a check that output is current, and a review path for the output |
| Generate types at build time | Reconsider when a component consumes contracts. The cost is real and the benefit is currently zero |
| Commit generated types | Adds a class of review where the diff is machine output, for no present gain |

## Consequences

- Contract validation needs a Python interpreter and two packages. That is one more
  prerequisite than a repository of Markdown and shell scripts had, and it is not
  free for a contributor on a locked-down machine.
- Cross-field rules — replica ranges, model and runtime compatibility, detecting a
  secret pasted into a reference field — **cannot** be expressed in JSON Schema.
  They need a validation layer above it. This ADR accepts that split knowingly:
  the structural half is portable to every consumer, and the semantic half stays in
  one place where it can be tested. The cost is that a consumer validating against
  the raw schema gets less than the platform does, so the contract document has to
  say which rules are which. It does.
- Choosing draft 2020-12 excludes validators that stop at draft-07. That is a real
  exclusion in some ecosystems and is accepted for the applicator semantics the
  profile discriminator uses.
- `$id` values are not retrievable. Anyone expecting to fetch a schema by its `$id`
  will be disappointed; the contract document says so explicitly.
- Choosing `pytest` here creates gravity toward `pytest` repository-wide. That is
  acknowledged rather than denied — but it is not the decision, and the test and
  continuous-integration strategy remains free to select differently and adapt
  this suite.

## Compatibility impact

None. This record introduces no contract, changes no published schema, and breaks
no consumer, because there is no prior schema tooling to be compatible with. It
constrains how the first schema is written, which lands in
[the WorkloadContract v1alpha1 contract](../../contracts/workload-contract.md).

## Security considerations

- **The schema is a security control, weakly.** Closed objects mean there is no
  field a secret value can be written into. That is a structural guarantee and it
  is worth having. It is not detection: a secret pasted into a field meant for a
  locator still validates, and the contract document says so rather than implying
  coverage that does not exist.
- **No schema is fetched at validation time.** `$ref` resolution stays inside the
  document. A validator that resolved `$id` over the network would make contract
  validation depend on a remote host, which is both a availability risk and a
  supply-chain one.
- **Validation runs on untrusted input by design.** A contract is authored by a
  team and validated by the platform. Using a maintained conformant validator
  rather than a bespoke parser keeps that surface with a project that maintains it.
- **Two new third-party runtime dependencies** enter the validation path. They are
  not vendored and not pinned here, which is the same posture the repository takes
  for `shellcheck` and `kubeconform`; a dependency and supply-chain policy is a
  separate, open decision.

## Evidence

Documented and executed, on 2026-08-24, on the same Windows host as the earlier
Sprint 0 records:

| Component | Version |
|---|---|
| Python | 3.12.6 |
| `jsonschema` | 4.26.0 |
| `pytest` | 8.3.4 |
| `PyYAML` | 6.0.2 |

```text
python -m pytest tests/contracts -q
37 passed
```

That result establishes that the tooling chosen here validates the schema and its
fixtures on one host. It establishes nothing about any workload, any runtime, or
any other host.
