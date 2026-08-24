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

### Not yet present

- Invalid fixtures and the semantic rules JSON Schema cannot express: replica range
  ordering, the model and runtime compatibility matrix, and detection of a secret
  value pasted into a locator field.
- Every other schema named in the integration specification.
