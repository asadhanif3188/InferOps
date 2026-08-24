# Contract package changelog

The contract package is versioned independently of the project. A published schema
version is never redefined: a breaking change gets a new `apiVersion`, and the old
one stays readable for as long as its support window runs.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **WorkloadContract `v1alpha1`** — the first machine-readable public contract.
  Covers workload identity, owner, profile, environment, model and runtime
  reference, resources, replica bounds, platform integrations, security
  classification, secret references, attribution, and evidence links.
- A closed additional-property policy on every object, so an unknown field is a
  validation error rather than a silently accepted typo.
- Structural pinning for the real serving profile: the runtime image by digest, and
  the model by upstream revision **and** per-file content hash.
- Structural separation of the `mock-llm` profile, which is confined to the `ci`
  environment, bound to the mock serving capability, and forbidden from citing
  real-runtime proof.
- A secret-reference block that requires a provider, a locator, an owner, and a
  rotation responsibility, and that has no field a secret value could be written
  into.
- `metadata.annotations` as the contract's single, non-normative extension point.
- Valid fixtures for the `synchronous-llm` and `mock-llm` profiles, plus a
  secret-reference shape example, and a deterministic mock chat-completion response
  fixture that identifies itself as a mock from its own contents.

- **A semantic validation layer above the schema**, applying the rules JSON Schema
  cannot express: replica range ordering, the runtime and model compatibility
  matrix, duplicate secret names, a mock declaring a credential, and detection of
  a secret value pasted into a locator field. Compatibility classification:
  **conditionally compatible** — no committed valid fixture becomes invalid, and
  no schema constraint changed, but a document the bare schema accepts can now be
  refused.
- **A published rejection interface.** Every refusal carries a canonical error
  code, a stable rule identifier, and a field location, and every one of the
  fifteen rules is listed in the contract document.
- **A runtime and model compatibility matrix**, as data rather than code, at
  `workload/compatibility/runtime-model-compatibility.v1alpha1.json`. It records
  what each runtime accepts, which runtimes are selected against merely recorded,
  and the one runtime-and-model pair this project has actually executed.
- **Sixteen invalid fixtures** under `workload/examples/invalid/`, each with its
  expected canonical code, rule, field location, and validation layer committed
  beside it in `expected-rejections.json`.
- Published compatibility classes for changes to this contract: compatible,
  **conditionally compatible**, and breaking, with the class of each change
  recorded in its changelog entry from here on.
- Fixture ownership rules: a rule without an invalid fixture is refused by a test,
  a removed rule takes its fixture with it, and a valid fixture is never edited to
  make a change pass.

### Changed

- Validation messages no longer repeat any value read out of the document. The
  underlying validator embeds the offending value in its own message; this package
  now generates its own text instead, because the field most likely to be refused
  for looking wrong is the field most likely to hold a secret. Compatibility
  classification: **conditionally compatible** — the verdict is unchanged and the
  message text is not.

### Not yet present

- Enforcement of three rules the integration specification names, each blocked on
  a capability that does not exist: undeclared required capability, policy
  exception without owner and reason and expiry, and entitlement of a claimed
  tenant.
- Every other schema named in the integration specification.
