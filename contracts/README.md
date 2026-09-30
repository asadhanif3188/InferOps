# Contract package

Machine-readable public contracts. Each schema here is the artifact a consumer
validates against; the prose that explains what it means, how it is versioned, and
which of its rules are not yet enforced lives under
[`docs/contracts/`](../docs/contracts/README.md).

| Contract | Version | Schema | Documentation |
|---|---|---|---|
| WorkloadContract | `v1alpha1` | [`workload/workload-contract.v1alpha1.schema.json`](workload/workload-contract.v1alpha1.schema.json) | [WorkloadContract v1alpha1](../docs/contracts/workload-contract.md) |
| EnvironmentBinding | `v1alpha1` | [`environment/environment-binding.v1alpha1.schema.json`](environment/environment-binding.v1alpha1.schema.json) | [EnvironmentBinding v1alpha1](../docs/contracts/environment-binding.md) |
| RenderedWorkloadRelease | `v1alpha1` | [`release/rendered-workload-release.v1alpha1.schema.json`](release/rendered-workload-release.v1alpha1.schema.json) | [RenderedWorkloadRelease v1alpha1](../docs/contracts/rendered-workload-release.md) |

| Supporting data | Version | File |
|---|---|---|
| Runtime and model compatibility matrix | `v1alpha1` | [`workload/compatibility/runtime-model-compatibility.v1alpha1.json`](workload/compatibility/runtime-model-compatibility.v1alpha1.json) |

The platform domain reads a WorkloadContract into typed objects; nothing in this
repository deploys, serves, or admits a workload from one. The platform domain
also reads an EnvironmentBinding, refuses bindings that conflict with each other, and
selects the one that serves a contract; nothing renders one, and its schema and
fixtures are published ahead of the renderer that will consume them, and say so.
The platform domain reads a RenderedWorkloadRelease too, computes the digests and the
identifier one should record, and refuses one whose identifier is not derived, whose
values look like a credential, or that disagrees with the contract and binding it
names. Nothing produces a release: its schema and fixtures are published ahead of the
renderer that will write one. A published schema is a commitment about what will be
accepted, not evidence that anything accepts it.

## Layout

```text
contracts/
|-- CHANGELOG.md                 contract-package history, versioned separately
+-- workload/
    |-- workload-contract.v1alpha1.schema.json
    |-- compatibility/           runtime and model matrix, as data rather than code
    |-- examples/
    |   |-- valid/               fixtures that must validate
    |   +-- invalid/             fixtures that must be refused, plus the refusal each
    |                            one must produce
    +-- fixtures/                deterministic payloads referenced by contracts
+-- environment/
    |-- environment-binding.v1alpha1.schema.json
    +-- examples/
        |-- valid/               bindings that must validate
        +-- invalid/             bindings that must be refused, plus the refusal
                                 each one must produce
+-- release/
    |-- rendered-workload-release.v1alpha1.schema.json
    +-- examples/
        |-- valid/               releases that must validate
        +-- invalid/             releases that must be refused, plus the refusal
                                 each one must produce
```

An EnvironmentBinding carries the facts one environment supplies to a release
that are not workload intent, and has no field a WorkloadContract owns. Every rule
it has is structural, so the bare schema refuses everything the published
validator does.

A RenderedWorkloadRelease records where one rendered release came from — the
workload, the digests of the contract and binding, the renderer and platform-defaults
revisions, a derived release identifier, and the digest of the generated values — and
carries none of their content. It is a repository document, not a cluster resource.
Every rule its schema and validator apply is structural too; the rules that need a
recomputation or a second document are the platform domain's, have no fixture file
here, and are each provoked by a test instead.

The rules a schema cannot express — comparing two sibling values, consulting the
compatibility matrix, judging whether a locator is a pasted credential — live in
[`tools/contract_validation/`](../tools/contract_validation/) rather than here,
because they are not part of the artifact a consumer validates against. What that
split costs a consumer is published in
[the contract document](../docs/contracts/workload-contract.md).

Further schemas named in the integration specification — capability descriptor,
runtime descriptor, evaluation result, cost record, policy decision — are not
present. They will be added when the capability behind each exists, not in advance.

## Rules

1. **Every schema declares its dialect and its `$id`.** An `$id` is a namespace,
   not a retrieval URL; nothing is served at `inferops.io`.
2. **Every schema ships valid *and* invalid fixtures**, and every fixture is
   checked on every change. A semantic rule with no fixture that fails because of
   it is a claim rather than a rule, and the suite refuses to let one exist.
3. **A refusal is published, not just produced.** Each invalid fixture's canonical
   error code, rule identifier, and field location are committed beside it and
   compared on every run, so what a consumer is told cannot drift silently.
4. **Unknown fields are rejected.** Every object declares its additional-property
   policy explicitly rather than inheriting a default.
5. **A contract references secrets and never carries one.** No schema here defines
   a field a secret value belongs in, and no part of a validation finding — its
   message or its field location — repeats a value read out of a document.
6. **A mock artifact says so in its own contents**, so that the label survives
   being copied out of the directory it sits in.

## Validation

```sh
python -m pytest tests/contracts -q
```

To validate a WorkloadContract document that is not a committed fixture:

```sh
python -m tools.contract_validation path/to/workload.yaml
```

Requires `jsonschema`, `pytest`, and `PyYAML`, which are not vendored. The choice
of schema language, authoring form, and validator is
[ADR 0003](../docs/architecture/decisions/ADR-0003-workload-contract-schema-tooling.md).
