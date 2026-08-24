# WorkloadContract examples

Fixtures for [the WorkloadContract v1alpha1 schema](../workload-contract.v1alpha1.schema.json).
Every file under `valid/` must validate; a failure is a defect in the schema, the
fixture, or the change that broke one of them.

These are **contract examples, not deployable workloads.** No controller, adapter,
or serving path in this repository reads a WorkloadContract, so nothing here has
been deployed and none of it is evidence that the workload it describes runs.

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

## Adding a fixture

A valid fixture is picked up automatically by
[the test suite](../../../tests/contracts/test_workload_contract_v1alpha1.py) from
`valid/*.yaml`. It must validate, stay inside the JSON-representable subset of
YAML, contain no field name that could hold a secret, and have every
repository-relative path it references resolve to a real file.

Invalid fixtures belong under `invalid/` and are the second pull request's work.
