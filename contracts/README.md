# Contract package

Machine-readable public contracts. Each schema here is the artifact a consumer
validates against; the prose that explains what it means, how it is versioned, and
which of its rules are not yet enforced lives under
[`docs/contracts/`](../docs/contracts/README.md).

| Contract | Version | Schema | Documentation |
|---|---|---|---|
| WorkloadContract | `v1alpha1` | [`workload/workload-contract.v1alpha1.schema.json`](workload/workload-contract.v1alpha1.schema.json) | [WorkloadContract v1alpha1](../docs/contracts/workload-contract.md) |

| Supporting data | Version | File |
|---|---|---|
| Runtime and model compatibility matrix | `v1alpha1` | [`workload/compatibility/runtime-model-compatibility.v1alpha1.json`](workload/compatibility/runtime-model-compatibility.v1alpha1.json) |

Nothing in this repository reads a contract yet. A published schema is a commitment
about what will be accepted, not evidence that anything accepts it.

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
```

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
   checked on every change. A rule with no fixture that fails because of it is a
   claim rather than a rule.
3. **A refusal is published, not just produced.** Each invalid fixture's canonical
   error code, rule identifier, and field location are committed beside it and
   compared on every run, so what a consumer is told cannot drift silently.
4. **Unknown fields are rejected.** Every object declares its additional-property
   policy explicitly rather than inheriting a default.
5. **A contract references secrets and never carries one.** No schema here defines
   a field a secret value belongs in, and no validation message repeats a value
   read out of a document.
6. **A mock artifact says so in its own contents**, so that the label survives
   being copied out of the directory it sits in.

## Validation

```sh
python -m pytest tests/contracts -q
```

To validate a document that is not a committed fixture:

```sh
python -m tools.contract_validation path/to/workload.yaml
```

Requires `jsonschema`, `pytest`, and `PyYAML`, which are not vendored. The choice
of schema language, authoring form, and validator is
[ADR 0003](../docs/architecture/decisions/ADR-0003-workload-contract-schema-tooling.md).
