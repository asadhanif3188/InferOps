# Contract package

Machine-readable public contracts. Each schema here is the artifact a consumer
validates against; the prose that explains what it means, how it is versioned, and
which of its rules are not yet enforced lives under
[`docs/contracts/`](../docs/contracts/README.md).

| Contract | Version | Schema | Documentation |
|---|---|---|---|
| WorkloadContract | `v1alpha1` | [`workload/workload-contract.v1alpha1.schema.json`](workload/workload-contract.v1alpha1.schema.json) | [WorkloadContract v1alpha1](../docs/contracts/workload-contract.md) |

Nothing in this repository reads a contract yet. A published schema is a commitment
about what will be accepted, not evidence that anything accepts it.

## Layout

```text
contracts/
|-- CHANGELOG.md                 contract-package history, versioned separately
+-- workload/
    |-- workload-contract.v1alpha1.schema.json
    |-- examples/
    |   +-- valid/               fixtures that must validate
    +-- fixtures/                deterministic payloads referenced by contracts
```

Further schemas named in the integration specification — capability descriptor,
runtime descriptor, evaluation result, cost record, policy decision — are not
present. They will be added when the capability behind each exists, not in advance.

## Rules

1. **Every schema declares its dialect and its `$id`.** An `$id` is a namespace,
   not a retrieval URL; nothing is served at `inferops.io`.
2. **Every schema ships valid fixtures**, and every fixture is validated on every
   change.
3. **Unknown fields are rejected.** Every object declares its additional-property
   policy explicitly rather than inheriting a default.
4. **A contract references secrets and never carries one.** No schema here defines
   a field a secret value belongs in.
5. **A mock artifact says so in its own contents**, so that the label survives
   being copied out of the directory it sits in.

## Validation

```sh
python -m pytest tests/contracts -q
```

Requires `jsonschema`, `pytest`, and `PyYAML`, which are not vendored. The choice
of schema language, authoring form, and validator is
[ADR 0003](../docs/architecture/decisions/ADR-0003-workload-contract-schema-tooling.md).
