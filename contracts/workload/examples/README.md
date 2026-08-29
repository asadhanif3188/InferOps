# WorkloadContract examples

Fixtures for [the WorkloadContract v1alpha1 schema](../workload-contract.v1alpha1.schema.json).
Every file under `valid/` must validate and every file under `invalid/` must be
refused; a failure either way is a defect in the schema, the validator, the
fixture, or the change that broke one of them.

These are **contract examples, not deployable workloads.** No controller, adapter,
or serving path in this repository reads a WorkloadContract, so nothing here has
been deployed and none of it is evidence that the workload it describes runs. Every
file under `valid/` is additionally parsed into a domain object by
[`tests/domain/`](../../../tests/domain/), which is what keeps the platform's typed
objects and these fixtures from drifting apart; parsing one deploys nothing.

| Fixture | Profile | What it demonstrates |
|---|---|---|
| [`valid/synchronous-llm-local.yaml`](valid/synchronous-llm-local.yaml) | `synchronous-llm` | The real profile, pinned to the runtime digest and model revision that ADR 0002 selected |
| [`valid/mock-llm-ci.yaml`](valid/mock-llm-ci.yaml) | `mock-llm` | The continuous-integration profile, structurally unable to present itself as real serving |
| [`valid/synchronous-llm-secret-refs.yaml`](valid/synchronous-llm-secret-refs.yaml) | `synchronous-llm` | The secret-reference block. A shape example; the secrets it names do not exist |

## Two things the fixtures deliberately do not do

**They declare no capability that does not exist.** `modelAccess` and `evaluation`
are absent from every fixture, because V1 has no model-access gateway and no
evaluation capability. Declaring a dependency on something unbuilt would be the
same overclaim the contract exists to prevent. `telemetry` is declared because the
schema requires a workload to name its telemetry dependency — that is a statement
of what the workload needs, not a claim that the capability is running.

**They cite no proof they do not have.** The real fixture links the executed
feasibility record. The mock fixture links the boundary rule and nothing else,
because a mock has no runtime proof to cite and the schema caps it at zero entries.

## Invalid fixtures

Every file under `invalid/` must be refused, and must be refused for exactly the
canonical error code, rule identifier, and field location recorded in
[`invalid/expected-rejections.json`](invalid/expected-rejections.json). The
manifest is compared with the validator's output field by field, so a change that
alters what a consumer is told fails the build rather than quietly changing the
interface.

The `layer` column says which half of validation refuses the document.
**Structural** means the published JSON Schema alone refuses it, so any draft
2020-12 validator in any language reaches the same verdict. **Semantic** means the
schema *accepts* it and only the rules above the schema refuse it — those are the
fixtures that prove the second layer is load-bearing.

| Fixture | Layer | Refused for |
|---|---|---|
| [`invalid/missing-owner.yaml`](invalid/missing-owner.yaml) | Structural | No `metadata.owner` |
| [`invalid/owner-not-dns-safe.yaml`](invalid/owner-not-dns-safe.yaml) | Structural | An owner that cannot be used as a label |
| [`invalid/malformed-identifiers.yaml`](invalid/malformed-identifiers.yaml) | Structural | Four identifiers malformed at once — name, version, annotation key, tenant |
| [`invalid/unsupported-api-version.yaml`](invalid/unsupported-api-version.yaml) | Structural | A contract version that does not exist. The one fixture carrying `version-unsupported` |
| [`invalid/unsupported-profile.yaml`](invalid/unsupported-profile.yaml) | Structural | A profile `v1alpha1` does not define |
| [`invalid/unknown-field.yaml`](invalid/unknown-field.yaml) | Structural | `maxiumumReplicas` — the misspelling the closed-object rule exists for |
| [`invalid/resource-free-workload.yaml`](invalid/resource-free-workload.yaml) | Structural | No `spec.resources` in any environment |
| [`invalid/secret-value-in-value-field.yaml`](invalid/secret-value-in-value-field.yaml) | Structural | A secret entry with a value-shaped field |
| [`invalid/mock-presented-as-real.yaml`](invalid/mock-presented-as-real.yaml) | Structural | A mock edited to read as real serving, in all four ways at once |
| [`invalid/replica-range-inverted.yaml`](invalid/replica-range-inverted.yaml) | Semantic | A replica range no replica count satisfies |
| [`invalid/secret-value-in-locator.yaml`](invalid/secret-value-in-locator.yaml) | Semantic | Two locators shaped like pasted credentials, one per heuristic |
| [`invalid/duplicate-secret-ref-name.yaml`](invalid/duplicate-secret-ref-name.yaml) | Semantic | Two secret entries sharing one logical name |
| [`invalid/mock-with-secret-refs.yaml`](invalid/mock-with-secret-refs.yaml) | Semantic | A mock asking for a credential it has nothing to use one for |
| [`invalid/runtime-model-incompatible.yaml`](invalid/runtime-model-incompatible.yaml) | Semantic | A GGUF artifact pinned to a runtime that does not load GGUF |
| [`invalid/runtime-unregistered.yaml`](invalid/runtime-unregistered.yaml) | Semantic | A runtime nothing has characterised |
| [`invalid/model-artifact-format-unrecognised.yaml`](invalid/model-artifact-format-unrecognised.yaml) | Semantic | An artifact in no format the compatibility matrix knows |

**No invalid fixture contains a credential.** Where one has to look like a
credential to demonstrate the check, it uses a vendor's own published placeholder
or a fixed synthetic string, and its header says so. Synthetic image digests are
written as an obvious run of repeated digits, so that no reader mistakes one for a
pin on a published image.

## Adding a fixture

A valid fixture is picked up automatically by
[the schema suite](../../../tests/contracts/test_workload_contract_v1alpha1.py) from
`valid/*.yaml`. It must validate under both layers, stay inside the
JSON-representable subset of YAML, contain no field name that could hold a secret,
and have every repository-relative path it references resolve to a real file.

An invalid fixture is picked up by
[the rejection suite](../../../tests/contracts/test_workload_contract_validation.py)
from `invalid/*.yaml`, and adding one means adding its entry to the manifest in the
same change. A fixture the manifest does not know about, or a manifest entry with
no fixture, is a test failure.

A fixture belongs to the rule it demonstrates rather than to the change that added
it: adding a semantic rule adds a fixture, removing a rule removes its fixture in
the same change, and a valid fixture is never edited to make a change pass — a
change that would invalidate one is breaking by definition. Two structural rules
have no fixture on purpose; the contract document names them and says why.
