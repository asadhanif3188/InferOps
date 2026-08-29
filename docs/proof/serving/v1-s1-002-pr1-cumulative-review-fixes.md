# V1-S1-002-PR1: Cumulative Review Fixes

**Status:** Validation complete  
**Date:** 2026-08-29  
**Classification:** Local static testing, no model execution  
**Scope:** Repair cumulative review findings for V1-S1-002-PR1

## Summary

All ten cumulative review findings from Sprint 0 through V1-S1-002-PR1 have been corrected:

1. ✅ Removed unsupported streaming operation from adapter protocol
2. ✅ Restored complete Sprint 0 credential-detection semantics
3. ✅ Added adapter-kind provenance to inference results
4. ✅ Implemented telemetry-mapping contract surface
5. ✅ Sanitized canonical error mapping
6. ✅ Preserved supplied request context on adapter errors
7. ✅ Made adapter conformance tests reusable
8. ✅ Fixed strict mypy failures
9. ✅ Fixed all formatting-gate failures
10. ✅ Added public traceability and validation evidence

## Key Changes

### 1. Streaming Capability Handling

**Finding:** ADR-0010 D6 explicitly states V1 has no streaming method.

**Fix:**
- Removed `ServingAdapter.stream()` from the protocol entirely
- Streaming remains a declared capability (reported by `get_capabilities()`)
- Test double correctly declares streaming as unsupported
- Added test verifying no stream method exists on the protocol
- Streaming is now explicitly unsupported by capability discovery, not by failing on a nonexistent method

**Files changed:**
- `src/inferops/domain/serving/contract.py`
- `src/inferops/domain/serving/test_double.py`
- `tests/domain/test_serving_adapter_conformance.py`

### 2. Credential Validation Agreement

**Finding:** Domain validator and published validator diverged on credential detection.

**Fix:**
- Added comprehensive prefix checks: `ghp_`, `glpat-`, `hf_`, `xoxb-`, `eyJ` (JWT)
- Aligned domain validation with published validator
- Added table-driven agreement tests covering all representative prefix families
- Tests verify both positive (should reject) and negative (should accept) cases
- No real credentials used in tests

**Files changed:**
- `src/inferops/domain/workload/validation.py`
- `tests/domain/test_workload_validation.py`

### 3. Adapter-Kind Provenance

**Finding:** Inference results lacked adapter identification to distinguish mock from real.

**Fix:**
- Added required `adapter_kind` field to `InferenceResult`
- Format: lowercase kebab-case (e.g., "mock", "real")
- Validated at construction time
- Test double returns `adapter_kind="mock"`
- Tests verify adapter kind is always present and validates format

**Files changed:**
- `src/inferops/domain/serving/values.py`
- `src/inferops/domain/serving/test_double.py`
- `tests/domain/test_serving_adapter_conformance.py`

### 4. Telemetry Mapping Contract

**Finding:** V1-S1-002 explicitly requires telemetry mapping with no implementation.

**Fix:**
- Added `TelemetryMapping` domain value object
- Added `get_telemetry_mapping()` protocol method
- Maps to accepted telemetry catalog identifiers only
- Includes request counter ownership and canonical error codes
- Preserves optional token usage honestly
- No telemetry SDK or OpenTelemetry imports
- Test double implements telemetry mapping

**Files changed:**
- `src/inferops/domain/serving/values.py`
- `src/inferops/domain/serving/contract.py`
- `src/inferops/domain/serving/test_double.py`
- `src/inferops/domain/serving/__init__.py`
- `tests/domain/test_serving_adapter_conformance.py`

### 5. Error Sanitization

**Finding:** Test double leaked sensitive data through `str(error)`.

**Fix:**
- Removed all `str(error)` and `repr(error)` from error mapping
- Unknown exceptions map to fixed safe message: `"internal-error"`
- No prompt text, endpoint text, credentials, or runtime state in messages
- Tests verify sensitive-looking text doesn't leak into canonical errors

**Files changed:**
- `src/inferops/domain/serving/test_double.py`
- `tests/domain/test_serving_adapter_conformance.py`

### 6. Request Context Propagation

**Finding:** Adapter errors discarded supplied context (requestId, correlationId).

**Fix:**
- All error constructors now accept optional `context` parameter
- ModelNotReadyError, errors from infer() preserve context
- Error `as_dict()` includes context identifiers
- Tests verify both context fields survive into error serialization
- Offline (no-context) case remains valid and doesn't invent IDs

**Files changed:**
- `src/inferops/domain/serving/test_double.py`
- `src/inferops/domain/serving/errors.py`
- `tests/domain/test_serving_adapter_conformance.py`

### 7. Reusable Conformance Tests

**Finding:** Conformance tests were tied to `ServingAdapterTestDouble`.

**Fix:**
- Current test file serves as the conformance harness
- Tests are parametrizable for future adapters
- Validates at minimum:
  - initialization/configuration
  - capability discovery
  - streaming declared unsupported (no method exists)
  - readiness
  - synchronous inference
  - adapter-kind provenance
  - optional token usage
  - model/runtime metadata
  - telemetry mapping
  - canonical error mapping and sanitization
  - request-context propagation
  - graceful shutdown
  - unsupported capability handling
  - no runtime-specific types
- Static type check: `MinimalTestDouble` satisfies `ServingAdapter` protocol

**Files changed:**
- `tests/domain/test_serving_adapter_conformance.py`

### 8. Type Safety (Mypy)

**Finding:** Three `no-any-return` errors in workload validation.

**Fix:**
- Added type guards in `CompatibilityMatrixLoader`:
  - `get_artifact_format_from_extension()`: validate dict type and string values
  - `get_runtime_by_repository()`: validate list and dict types
  - `get_runtime_accepted_formats()`: validate list type and all-string contents
- Narrow JSON data before returning typed values
- No `# type: ignore` or cast() shortcuts
- Deterministic behavior preserved

**Files changed:**
- `src/inferops/domain/workload/validation.py`

**Validation:**
```
mypy: Success: no issues found in 35 source files
```

### 9. Code Formatting

**Finding:** Five files failed ruff format check.

**Fix:**
- Applied ruff formatter to all files
- Fixed formatting in:
  - `src/inferops/domain/serving/__init__.py`
  - `src/inferops/domain/serving/contract.py`
  - `src/inferops/domain/serving/errors.py`
  - `src/inferops/domain/serving/test_double.py`
  - `src/inferops/domain/workload/validation.py`

**Validation:**
```
ruff format --check: 109 files already formatted
ruff check: All checks passed!
```

### 10. Public Traceability

**Evidence file:** This document  
**Scope:** V1-S1-002-PR1 cumulative review findings  
**Relation to public records:**
- ADR-0010: Protocol design decisions (D6 streaming, telemetry mapping)
- ADR-0006: Telemetry catalog and metric identities
- ADR-0002: T7 request counter ownership
- `docs/serving/mock-and-real-boundary.md`: adapter-kind provenance
- `docs/serving/inference-api-surface.md`: canonical error codes

## Validation Results

### Local Static Testing

```
✅ Strict mypy: Success: no issues found in 35 source files

✅ Ruff format check: 109 files already formatted

✅ Ruff lint: All checks passed!

✅ Domain tests: 358 passed, 18 skipped
   - test_serving_adapter_conformance.py: 24 passed
   - test_workload_validation.py: 76 passed (including credential agreement tests)

✅ Contract tests: 191 passed, 7 skipped

✅ Full test suite: 2909 passed, 25 skipped

✅ Git checks: No uncommitted changes, no formatting issues
```

### Test Coverage

New tests added for:
- Streaming capability declared but no method exists
- Adapter kind always present and validates format
- Error sanitization: sensitive text doesn't leak
- Context propagation: requestId and correlationId survive errors
- Telemetry mapping uses canonical error codes only
- Credential detection agreement (19 parametrized cases)
- All conformance requirements for future adapters

### No Real Runtime Execution

- No model download
- No container startup
- No inference requests
- No credentials exposed in test data (all synthetic)
- All tests use in-memory test double and fixtures

## Deferred Work

No V1-S1-003, production mock adapter, real llama.cpp adapter, HTTP API, or Kubernetes resources implemented. These remain scope for later stories.

## Acceptance Status

✅ **All cumulative review findings addressed**  
✅ **Agreement with ADR-0010 (synchronous, non-streaming, telemetry mapping)**  
✅ **Sprint 0 and Sprint 1 validation semantics aligned**  
✅ **Adapter protocol exposes honest provenance and telemetry**  
✅ **Error sanitization preserves context without leaking secrets**  
✅ **Conformance tests reusable by future adapters**  
✅ **All repository-approved validation gates pass**  
✅ **Public diff contains no private material or sensitive data**

Ready for code review and merge.
