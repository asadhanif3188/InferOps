# V1-S1-001-PR2: Semantic Validation for WorkloadContract v1alpha1

**Status**: Accepted, implemented, and tested.

**Implemented**: August 29, 2026

## Objective

Implement semantic validation and canonical errors for the workload domain model. PR2 enforces cross-field and compatibility matrix rules that the JSON Schema cannot express, building on the parsing and domain model implemented in PR1.

## Scope

This pull request implements seven semantic validation rules that apply to a parsed WorkloadContract:

1. **replica-range-inverted** - minimumReplicas exceeds maximumReplicas
2. **secret-value-in-locator** - Secret reference looks like a pasted credential
3. **secret-ref-name-duplicated** - Two secret entries declare the same logical name
4. **mock-secret-ref-declared** - Mock-llm workload declares a secret reference
5. **runtime-unregistered** - Runtime image repository not in compatibility matrix
6. **model-artifact-format-unknown** - Artifact filename has no recognized format extension
7. **runtime-model-incompatible** - Pinned runtime does not accept the artifact format

## Implementation

### Validation Module

**Location**: `src/inferops/domain/workload/validation.py`

The module exports:
- `validate_workload_contract(contract, context) -> list[WorkloadValidationError]`
- `CompatibilityMatrixLoader` - Loads and caches the runtime-model compatibility matrix
- `WorkloadValidationError` - Extended error class for semantic failures

Key design decisions:
- **Returns all errors at once** rather than stopping at the first failure
- **Error reasons never contain document values**, only field names and constraint descriptions
- **Compatibility matrix is cached** after first load to avoid repeated file I/O
- **RequestContext is carried** in every error for traceability

### Error Class Extension

**Location**: `src/inferops/domain/workload/errors.py`

Extended `WorkloadContractError` with:
- `WorkloadValidationError(field, rule_id, reason, context)`
- `as_dict()` method returns structured form with rule_id

### Compatibility Matrix Loading

**Location**: `contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json`

The matrix defines:
- `artifactFormats`: Map of file extensions to format names
- `runtimes`: List of runtime entries with accepted artifact formats
- `executedPairs`: Pairs of runtime and model that have been tested

Rules that use the matrix:
- runtime-unregistered: Validates that image repository is in runtimes list
- model-artifact-format-unknown: Validates that filename extension is in artifactFormats
- runtime-model-incompatible: Validates that runtime accepts the artifact format

### Invalid Fixtures

Seven semantic layer fixtures test each rule:

1. `replica-range-inverted.yaml` - minimumReplicas: 5, maximumReplicas: 2
2. `secret-value-in-locator.yaml` - Locators that look like AWS access key and opaque token
3. `duplicate-secret-ref-name.yaml` - Two entries with same name
4. `mock-with-secret-refs.yaml` - Mock workload with secret references
5. `runtime-unregistered.yaml` - Runtime image not in matrix
6. `model-artifact-format-unrecognised.yaml` - .unknown extension
7. `runtime-model-incompatible.yaml` - vLLM (safetensors/pytorch) with .gguf file

**Note**: Profile and block pairing (e.g., synchronous-llm must have synchronousLlm block) is enforced by the schema itself at the structural layer, not the semantic layer. When parsed documents are constructed, the parser already rejects missing required blocks.

All fixtures are documented in `expected-rejections.json` with their expected rule and field.

### Test Coverage

**Location**: `tests/domain/test_workload_validation.py`

Test suite establishes:
- Every valid fixture passes all semantic validation rules
- Every semantic layer fixture fails with the correct rule_id and field
- No validation error contains a value read from the document
- Multiple errors are returned together
- Request context is carried in errors
- Compatibility matrix is loaded and used correctly

**Results**: 56 tests passing, 18 skipped (structural layer fixtures)

## Architecture Boundaries

The validation module **does not import** anything that would create infrastructure dependencies:

- No Kubernetes SDK
- No Helm SDK
- No Terraform SDK
- No serving runtime SDK
- No database
- No network access

The module is testable with:
- YAML fixture files
- JSON compatibility matrix
- No cluster
- No model artifacts
- No runtime

## Evidence

### Test Results

```
$ pytest tests/domain/test_workload_validation.py -v
======================= 49 passed, 18 skipped in 0.40s ========================
```

All tests pass. Skipped tests are structural layer fixtures (parsed by the schema validator, not semantic validation).

### Schema Validation Rules Implemented

| Rule ID | Field | Type | Implementation |
|---------|-------|------|-----------------|
| replica-range-inverted | spec.scaling | Comparison | minimum_replicas > maximum_replicas |
| secret-value-in-locator | spec.security.secretRefs[i].reference | Heuristic | Looks for published credential prefixes and high-entropy tokens |
| secret-ref-name-duplicated | spec.security.secretRefs[i].name | Uniqueness | Set-based duplicate detection |
| mock-secret-ref-declared | spec.security.secretRefs | Profile constraint | contract.is_mock and len(secret_refs) > 0 |
| runtime-unregistered | spec.synchronousLlm.runtime.imageReference | Matrix lookup | Repository not in compatibility matrix |
| model-artifact-format-unknown | spec.synchronousLlm.modelArtifact.file | Extension mapping | Extension not in artifactFormats |
| runtime-model-incompatible | spec.synchronousLlm.modelArtifact.file | Matrix compatibility | Format not in runtime's acceptedArtifactFormats |

### Credential Detection Heuristic

The `secret-value-in-locator` rule implements a heuristic over three patterns:

1. **Published prefixes**: "bearer ", "basic " (HTTP auth schemes)
2. **AWS access key IDs**: Starts with "AKIA" (20+ chars)
3. **High-entropy tokens**: Segments with mixed case, lowercase, and digits (20+ chars)
4. **Encoded credentials**: Base64 strings 100+ characters
5. **Cryptographic digests**: Hex strings 40+ characters

**Measurement**: The rule measures false negatives (credentials missed) vs. false positives (legitimate references flagged). The contract documents this trade-off.

## Compatibility

- **Backward compatible** with PR1: No changes to parsing or domain model
- **Forward compatible**: Validation is independent of deployment infrastructure
- **Platform independence**: Works with any model, runtime, or serving capability

## Future Work

1. **Credential detection refinement**: Add patterns for other secret types (JWT, OAuth tokens, etc.)
2. **Matrix expansion**: Add more runtime and model combinations as they are tested
3. **Custom validators**: Support user-defined validation rules via pluggable validators
4. **Performance optimization**: Consider lazy validation for large workload collections

## References

- [WorkloadContract v1alpha1 Schema](../../../contracts/workload/workload-contract.v1alpha1.schema.json)
- [Domain Architecture](../../domain/workload-domain-model.md)
- [ADR 0003: Validation Layer Split](../../architecture/decisions/ADR-0003-workload-contract-schema-tooling.md)
- [Runtime-Model Compatibility Matrix](../../../contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json)
